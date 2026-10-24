"""Identical physical assumptions for FCFS/EDF/LLF and lexicographic OR-Tools."""

from collections import defaultdict
from dataclasses import dataclass
import time

from ortools.linear_solver import pywraplp

from ..models import Allocation, Schedule
from .scenario import available_at, hours, intervals, price_at, remaining_energy
from .physics import minimum_hours, sustainable_power
from .tariffs import demand_windows, overlap_hours


class SchedulingError(RuntimeError):
    pass


@dataclass
class _Problem:
    solver: object
    slots: list
    groups: list
    powers: dict
    shortfall: object
    demand_cost: object
    peak: object


def allocation(scenario, session, charger, start, end, power):
    return Allocation(vehicle_id=session.vehicle_id, charger_id=charger.charger_id,
                      start_time=start, end_time=end, power_kw=power,
                      charging_efficiency=scenario.station.charging_efficiency)


def _priority(session, policy, start, remaining, scenario, attached):
    if policy == "EDF":
        return session.departure_time, session.arrival_time, session.vehicle_id
    if policy == "LLF":
        rates = [c.max_power_kw for c in scenario.station.chargers
                 if c.connector_type == session.connector_type and available_at(scenario, c, start)
                 and (not scenario.station.fixed_connections or session.vehicle_id not in attached or c.charger_id == attached[session.vehicle_id])]
        rate = min(session.max_charging_power_kw, max(rates, default=0), scenario.station.station_power_limit_kw)
        needed = minimum_hours(session, session.energy_required_kwh - remaining, remaining, rate, scenario.station.charging_efficiency)
        laxity = hours(start, session.departure_time) - needed
        return laxity, session.departure_time, session.vehicle_id
    return session.arrival_time, session.vehicle_id


def _greedy_slot(scenario, ordered, start, end, remaining, attached):
    usable = {c.charger_id: c for c in scenario.station.chargers if available_at(scenario, c, start)}
    free = set(usable)
    sessions = {s.vehicle_id: s for s in scenario.sessions}
    budget, records = scenario.station.station_power_limit_kw, []
    duration, efficiency = hours(start, end), scenario.station.charging_efficiency
    for session in ordered:
        if not session.arrival_time <= start < end <= session.departure_time:
            continue
        if remaining[session.vehicle_id] <= 1e-8:
            continue
        reserved = attached.get(session.vehicle_id) if scenario.station.fixed_connections else None
        blocked = {c for v, c in attached.items() if v != session.vehicle_id
                   and sessions[v].arrival_time < session.departure_time and sessions[v].departure_time > session.arrival_time} if scenario.station.fixed_connections else set()
        matches = [reserved] if reserved in usable else sorted(c for c in free - blocked if usable[c].connector_type == session.connector_type) if not reserved else []
        if not matches or budget <= 1e-8:
            continue
        charger = usable.pop(matches[0])
        free.discard(charger.charger_id)
        if scenario.station.fixed_connections:
            attached[session.vehicle_id] = charger.charger_id
        delivered = session.energy_required_kwh - remaining[session.vehicle_id]
        rate = min(sustainable_power(session, delivered, duration, efficiency), charger.max_power_kw,
                   budget, remaining[session.vehicle_id] / (duration * efficiency))
        if rate > 1e-8:
            records.append(allocation(scenario, session, charger, start, end, rate))
            remaining[session.vehicle_id] -= rate * duration * efficiency
            budget -= rate
    return records


def baseline(scenario, policy="FCFS"):
    """Re-rank each interval (LLF uses current remaining energy); allow preemption."""
    if policy not in {"FCFS", "EDF", "LLF"}:
        raise ValueError("Unknown scheduling policy")
    began, remaining = time.perf_counter(), remaining_energy(scenario)
    records = list(scenario.history)
    attached = {s.vehicle_id: s.charger_id for s in scenario.sessions if s.charger_id is not None}
    attached.update({r.vehicle_id: r.charger_id for r in sorted(scenario.history, key=lambda r: r.end_time)})
    for start, end in intervals(scenario):
        ordered = sorted(scenario.sessions, key=lambda s: _priority(s, policy, start, remaining[s.vehicle_id], scenario, attached))
        records.extend(_greedy_slot(scenario, ordered, start, end, remaining, attached))
    return Schedule(kind="baseline", allocations=records, state_version=scenario.state_version,
                    schedule_version=scenario.schedule_version + 1, solver_status=policy,
                    runtime_seconds=time.perf_counter() - began)


def _variables(scenario, solver, slots, groups, remaining):
    # Index power by (vehicle, identical-charger group, interval).
    powers, energy = {}, defaultdict(list)
    connections = {}
    previous = {r.vehicle_id: r.charger_id for r in sorted(scenario.history, key=lambda r: r.end_time)}
    fixed = scenario.station.fixed_connections
    limits = {name: defaultdict(list) for name in ("station", "charger", "vehicle")}
    for t, (start, end) in enumerate(slots):
        for v, session in enumerate(scenario.sessions):
            if (remaining[session.vehicle_id] <= 1e-8 and not fixed) or session.arrival_time > start or session.departure_time < end:
                continue
            for g, chargers in enumerate(groups):
                if chargers[0].connector_type != session.connector_type or (not fixed and not any(available_at(scenario, c, start) for c in chargers)):
                    continue
                if fixed and session.vehicle_id in previous and previous[session.vehicle_id] not in {c.charger_id for c in chargers}:
                    continue
                if session.charger_id is not None and session.charger_id not in {c.charger_id for c in chargers}:
                    continue
                if len(powers) >= 40000:
                    raise SchedulingError("Scenario exceeds the interactive model budget; reduce horizon or charger types")
                rate = min(session.max_charging_power_kw, chargers[0].max_power_kw, scenario.station.station_power_limit_kw)
                if not any(available_at(scenario, c, start) for c in chargers) or remaining[session.vehicle_id] <= 1e-8:
                    rate = 0
                power = solver.NumVar(0, rate, f"p_{v}_{g}_{t}")
                if fixed:
                    if (v, g) not in connections:
                        connections[v, g] = solver.BoolVar(f"connection_{v}_{g}")
                        if session.vehicle_id in previous or session.charger_id is not None:
                            solver.Add(connections[v, g] == 1)
                    assigned = connections[v, g]
                else:
                    assigned = solver.BoolVar(f"a_{v}_{g}_{t}")
                solver.Add(power <= rate * assigned)
                powers[v, g, t] = power
                energy[v].append(power * hours(start, end) * scenario.station.charging_efficiency)
                limits["station"][t].append(power)
                limits["charger"][t, g].append(assigned)
                limits["vehicle"][t, v].append(assigned)
    return powers, energy, limits


def _constraints(scenario, solver, slots, groups, remaining, energy, limits, charger_budget):
    active = {}
    if charger_budget is not None:
        active = {g: solver.IntVar(0, len(chargers), f"installed_{g}") for g, chargers in enumerate(groups)}
        solver.Add(solver.Sum(active.values()) <= charger_budget)
    shortfalls = []
    for v, session in enumerate(scenario.sessions):
        shortfall = solver.NumVar(0, remaining[session.vehicle_id], f"shortfall_{v}")
        solver.Add(solver.Sum(energy[v]) + shortfall == remaining[session.vehicle_id])
        shortfalls.append(shortfall)
    for terms in limits["station"].values():
        solver.Add(solver.Sum(terms) <= scenario.station.station_power_limit_kw)
    for (t, g), terms in limits["charger"].items():
        count = len(groups[g]) if scenario.station.fixed_connections else sum(available_at(scenario, c, slots[t][0]) for c in groups[g])
        solver.Add(solver.Sum(terms) <= active.get(g, count))
    for terms in limits["vehicle"].values():
        solver.Add(solver.Sum(terms) <= 1)
    return solver.Sum(shortfalls)


def _taper_constraints(scenario, solver, slots, powers, remaining):
    for v, session in enumerate(scenario.sessions):
        if session.battery_capacity_kwh is None:
            continue
        delivered = session.energy_required_kwh - remaining[session.vehicle_id]
        scale = session.battery_capacity_kwh * (1 - session.transition_soc)
        headroom = session.battery_capacity_kwh * (1 - session.initial_soc)
        for t, slot in enumerate(slots):
            power = solver.Sum(p for (vehicle, g, interval), p in powers.items() if vehicle == v and interval == t)
            delivered += power * hours(*slot) * scenario.station.charging_efficiency
            solver.Add(power * scale <= session.max_charging_power_kw * (headroom - delivered))


def _demand_model(scenario, solver, slots, powers):
    tariff, peaks = scenario.station.demand_tariff, {}
    peak = solver.NumVar(0, solver.infinity(), "connection_peak")
    for start, end, period in demand_windows(scenario):
        if period not in peaks:
            peaks[period] = solver.NumVar(tariff.prior_peaks_kw.get(period, 0), solver.infinity(), f"meter_peak_{period}")
        future = solver.Sum(p * overlap_hours(start, end, *slots[t]) / .25
                            for (v, g, t), p in powers.items() if slots[t][0] < end and slots[t][1] > start)
        history = sum(r.power_kw * overlap_hours(start, end, r.start_time, r.end_time) / .25 for r in scenario.history)
        solver.Add(peaks[period] >= future + history)
    # Connection sizing must respect instantaneous power, including partial slots.
    for t in range(len(slots)):
        solver.Add(peak >= solver.Sum(p for (v, g, interval), p in powers.items() if interval == t))
    cost = solver.Sum((p - tariff.prior_peaks_kw.get(key, 0)) * tariff.eur_per_kw for key, p in peaks.items())
    return cost, peak


def _build_problem(scenario, time_limit, charger_budget):
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise SchedulingError("OR-Tools SCIP backend is unavailable")
    solver.SetNumThreads(1)
    solver.SetTimeLimit(int(time_limit * 500))  # Half the budget for each objective.
    solver.SetSolverSpecificParametersAsString("numerics/feastol = 1e-9")
    groups, slots = defaultdict(list), intervals(scenario)
    bound = {s.charger_id for s in scenario.sessions if s.charger_id is not None}
    for charger in scenario.station.chargers:
        key = (charger.connector_type, charger.max_power_kw)
        if scenario.station.fixed_connections:
            key += (tuple(available_at(scenario, charger, a) for a, b in slots),)
        if charger.charger_id in bound:
            key += (charger.charger_id,)
        groups[key].append(charger)
    # Identical chargers share variables; physical IDs are assigned after solving.
    groups, remaining = list(groups.values()), remaining_energy(scenario)
    powers, energy, limits = _variables(scenario, solver, slots, groups, remaining)
    shortfall = _constraints(scenario, solver, slots, groups, remaining, energy, limits, charger_budget)
    _taper_constraints(scenario, solver, slots, powers, remaining)
    demand_cost, peak = _demand_model(scenario, solver, slots, powers)
    return _Problem(solver, slots, groups, powers, shortfall, demand_cost, peak)


def _solve(scenario, problem, capacity=False):
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
    cost = solver.Sum(power * hours(*problem.slots[t]) * price_at(scenario, problem.slots[t][0])
                      for (v, g, t), power in powers.items()) + problem.demand_cost
    solver.Minimize(problem.peak if capacity else cost)
    second = solver.Solve(parameters)
    if second in (solver.OPTIMAL, solver.FEASIBLE):
        values = {key: power.solution_value() for key, power in powers.items()}
    return values, first == solver.OPTIMAL, first == second == solver.OPTIMAL


def _assign_chargers(scenario, problem, values):
    if scenario.station.fixed_connections:
        return _assign_fixed(scenario, problem, values)
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


def _assign_fixed(scenario, problem, values):
    """Color whole-session intervals onto identical plugs, preserving old bindings."""
    previous = {r.vehicle_id: r.charger_id for r in sorted(scenario.history, key=lambda r: r.end_time)}
    bindings, occupied = {}, defaultdict(list)
    for session in scenario.sessions:
        if session.vehicle_id in previous and session.departure_time > scenario.now:
            occupied[previous[session.vehicle_id]].append((scenario.now, session.departure_time))
    selected = {(v, g) for (v, g, t), power in values.items() if power > 1e-7}
    for v, g in sorted(selected, key=lambda item: (scenario.sessions[item[0]].arrival_time, scenario.sessions[item[0]].vehicle_id)):
        session = scenario.sessions[v]
        start, end = max(scenario.now, session.arrival_time), session.departure_time
        candidates = sorted(problem.groups[g], key=lambda c: c.charger_id)
        old = previous.get(session.vehicle_id)
        charger = next((c for c in candidates if (c.charger_id == old if old else
                        all(b <= start or a >= end for a, b in occupied[c.charger_id]))), None)
        if charger is None:
            raise SchedulingError("No physical fixed-plug assignment found")
        bindings[v, g] = charger
        if session.vehicle_id not in previous:
            occupied[charger.charger_id].append((start, end))
    return [*scenario.history, *[allocation(scenario, scenario.sessions[v], bindings[v, g], *problem.slots[t], power)
                                for (v, g, t), power in values.items() if power > 1e-7]]


def optimize(scenario, time_limit_seconds=8, capacity=False, charger_budget=None):
    began = time.perf_counter()
    problem = _build_problem(scenario, time_limit_seconds, charger_budget)
    values, energy_optimal, cost_optimal = _solve(scenario, problem, capacity)
    return Schedule(kind="optimized", allocations=_assign_chargers(scenario, problem, values),
                    state_version=scenario.state_version, schedule_version=scenario.schedule_version + 1,
                    solver_status="OPTIMAL" if cost_optimal else "FEASIBLE_TIME_LIMIT",
                    shortfall_optimal=energy_optimal, cost_optimal=cost_optimal,
                    runtime_seconds=time.perf_counter() - began)
