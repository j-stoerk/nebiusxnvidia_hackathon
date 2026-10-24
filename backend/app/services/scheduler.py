"""FCFS reference and OR-Tools scheduling: serve energy first, then reduce cost."""

from collections import defaultdict
from dataclasses import dataclass
import time

from ortools.linear_solver import pywraplp

from ..models import Allocation, Schedule
from .scenario import available_at, hours, intervals, price_at, remaining_energy


class SchedulingError(RuntimeError):
    pass


@dataclass
class _Problem:
    solver: object
    slots: list
    groups: list
    powers: dict
    shortfall: object


def allocation(scenario, session, charger, start, end, power):
    return Allocation(vehicle_id=session.vehicle_id, charger_id=charger.charger_id,
                      start_time=start, end_time=end, power_kw=power,
                      charging_efficiency=scenario.station.charging_efficiency)


def baseline(scenario):
    """Keep connected vehicles first; serve waiting vehicles in arrival/ID order."""
    began, remaining = time.perf_counter(), remaining_energy(scenario)
    records, attached = list(scenario.history), {}
    ordered = sorted(scenario.sessions, key=lambda s: (s.arrival_time, s.vehicle_id))
    for start, end in intervals(scenario):
        usable = {c.charger_id: c for c in scenario.station.chargers if available_at(scenario, c, start)}
        eligible = {s.vehicle_id for s in ordered if s.arrival_time <= start and end <= s.departure_time and remaining[s.vehicle_id] > 1e-8}
        attached = {v: c for v, c in attached.items() if v in eligible and c in usable}
        free = set(usable) - set(attached.values())
        for session in ordered:
            if session.vehicle_id in eligible and session.vehicle_id not in attached:
                matches = sorted(c for c in free if usable[c].connector_type == session.connector_type)
                if matches:
                    attached[session.vehicle_id] = matches[0]
                    free.remove(matches[0])
        budget = scenario.station.station_power_limit_kw
        for session in ordered:
            charger_id = attached.get(session.vehicle_id)
            if charger_id is None or budget <= 1e-8:
                continue
            rate = min(session.max_charging_power_kw, usable[charger_id].max_power_kw, budget,
                       remaining[session.vehicle_id] / (hours(start, end) * scenario.station.charging_efficiency))
            if rate > 1e-8:
                records.append(allocation(scenario, session, usable[charger_id], start, end, rate))
                remaining[session.vehicle_id] -= rate * hours(start, end) * scenario.station.charging_efficiency
                budget -= rate
    return Schedule(kind="baseline", allocations=records, state_version=scenario.state_version,
                    schedule_version=scenario.schedule_version + 1, solver_status="FCFS",
                    runtime_seconds=time.perf_counter() - began)


def _variables(scenario, solver, slots, groups, remaining):
    # Index power by (vehicle, identical-charger group, interval).
    powers, energy = {}, defaultdict(list)
    limits = {name: defaultdict(list) for name in ("station", "charger", "vehicle")}
    for t, (start, end) in enumerate(slots):
        for v, session in enumerate(scenario.sessions):
            if remaining[session.vehicle_id] <= 1e-8 or session.arrival_time > start or session.departure_time < end:
                continue
            for g, chargers in enumerate(groups):
                if chargers[0].connector_type != session.connector_type or not any(available_at(scenario, c, start) for c in chargers):
                    continue
                if len(powers) >= 40000:
                    raise SchedulingError("Scenario exceeds the interactive model budget; reduce horizon or charger types")
                rate = min(session.max_charging_power_kw, chargers[0].max_power_kw, scenario.station.station_power_limit_kw)
                power = solver.NumVar(0, rate, f"p_{v}_{g}_{t}")
                assigned = solver.BoolVar(f"a_{v}_{g}_{t}")
                solver.Add(power <= rate * assigned)
                powers[v, g, t] = power
                energy[v].append(power * hours(start, end) * scenario.station.charging_efficiency)
                limits["station"][t].append(power)
                limits["charger"][t, g].append(assigned)
                limits["vehicle"][t, v].append(assigned)
    return powers, energy, limits


def _constraints(scenario, solver, slots, groups, remaining, energy, limits):
    shortfalls = []
    for v, session in enumerate(scenario.sessions):
        shortfall = solver.NumVar(0, remaining[session.vehicle_id], f"shortfall_{v}")
        solver.Add(solver.Sum(energy[v]) + shortfall == remaining[session.vehicle_id])
        shortfalls.append(shortfall)
    for terms in limits["station"].values():
        solver.Add(solver.Sum(terms) <= scenario.station.station_power_limit_kw)
    for (t, g), terms in limits["charger"].items():
        solver.Add(solver.Sum(terms) <= sum(available_at(scenario, c, slots[t][0]) for c in groups[g]))
    for terms in limits["vehicle"].values():
        solver.Add(solver.Sum(terms) <= 1)
    return solver.Sum(shortfalls)


def _build_problem(scenario, time_limit):
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise SchedulingError("OR-Tools SCIP backend is unavailable")
    solver.SetNumThreads(1)
    solver.SetTimeLimit(int(time_limit * 500))  # Half the budget for each objective.
    solver.SetSolverSpecificParametersAsString("numerics/feastol = 1e-9")
    groups = defaultdict(list)
    for charger in scenario.station.chargers:
        groups[charger.connector_type, charger.max_power_kw].append(charger)
    # Identical chargers share variables; physical IDs are assigned after solving.
    groups, slots, remaining = list(groups.values()), intervals(scenario), remaining_energy(scenario)
    powers, energy, limits = _variables(scenario, solver, slots, groups, remaining)
    shortfall = _constraints(scenario, solver, slots, groups, remaining, energy, limits)
    return _Problem(solver, slots, groups, powers, shortfall)


def _solve(scenario, problem):
    solver, powers = problem.solver, problem.powers
    parameters = pywraplp.MPSolverParameters()
    parameters.SetDoubleParam(pywraplp.MPSolverParameters.RELATIVE_MIP_GAP, 0)
    solver.Minimize(problem.shortfall)
    first = solver.Solve(parameters)
    if first not in (solver.OPTIMAL, solver.FEASIBLE):
        raise SchedulingError("No feasible schedule found within the solver budget")
    values = {key: power.solution_value() for key, power in powers.items()}
    # Freeze the best served energy before reducing cost; undercharging is not savings.
    solver.Add(problem.shortfall <= solver.Objective().Value() + 1e-7)
    solver.Minimize(solver.Sum(power * hours(*problem.slots[t]) * price_at(scenario, problem.slots[t][0])
                              for (v, g, t), power in powers.items()))
    second = solver.Solve(parameters)
    if second in (solver.OPTIMAL, solver.FEASIBLE):
        values = {key: power.solution_value() for key, power in powers.items()}
    return values, first == solver.OPTIMAL, first == second == solver.OPTIMAL


def _assign_chargers(scenario, problem, values):
    records, selected = list(scenario.history), defaultdict(list)
    for (vehicle, group, slot), power in values.items():
        if power > 1e-7:
            selected[slot, group].append((vehicle, power))
    for t, (start, end) in enumerate(problem.slots):
        for g, chargers in enumerate(problem.groups):
            available = sorted((c for c in chargers if available_at(scenario, c, start)), key=lambda c: c.charger_id)
            charging = sorted(selected[t, g])
            if len(charging) > len(available):
                raise SchedulingError("Solver returned an invalid charger assignment")
            records.extend(allocation(scenario, scenario.sessions[v], charger, start, end, power)
                           for (v, power), charger in zip(charging, available))
    return records


def optimize(scenario, time_limit_seconds=8):
    began = time.perf_counter()
    problem = _build_problem(scenario, time_limit_seconds)
    values, energy_optimal, cost_optimal = _solve(scenario, problem)
    return Schedule(kind="optimized", allocations=_assign_chargers(scenario, problem, values),
                    state_version=scenario.state_version, schedule_version=scenario.schedule_version + 1,
                    solver_status="OPTIMAL" if cost_optimal else "FEASIBLE_TIME_LIMIT",
                    shortfall_optimal=energy_optimal, cost_optimal=cost_optimal,
                    runtime_seconds=time.perf_counter() - began)
