"""FCFS reference and lexicographic OR-Tools SCIP optimization.

Equivalent chargers are pooled in the MIP to remove assignment symmetry. Each
positive allocation is then matched to a physical compatible charger per slot.
Vehicles may pause or change compatible chargers at interval boundaries.
"""

from collections import defaultdict
import time

from ortools.linear_solver import pywraplp

from ..models import Allocation, Schedule
from .scenario import available_at, hours, intervals, price_at, remaining_energy


class SchedulingError(RuntimeError):
    pass


def allocation(scenario, session, charger, start, end, power):
    return Allocation(vehicle_id=session.vehicle_id, charger_id=charger.charger_id,
                      start_time=start, end_time=end, power_kw=power,
                      charging_efficiency=scenario.station.charging_efficiency)


def baseline(scenario):
    began = time.perf_counter()
    remaining = remaining_energy(scenario)
    records = list(scenario.history)
    attached = {}
    ordered = sorted(scenario.sessions, key=lambda s: (s.arrival_time, s.vehicle_id))
    for start, end in intervals(scenario):
        usable = {c.charger_id: c for c in scenario.station.chargers if available_at(scenario, c, start)}
        eligible = {s.vehicle_id: s for s in ordered if s.arrival_time <= start and end <= s.departure_time and remaining[s.vehicle_id] > 1e-8}
        attached = {vehicle: charger for vehicle, charger in attached.items() if vehicle in eligible and charger in usable}
        free = set(usable) - set(attached.values())
        for session in ordered:
            if session.vehicle_id in eligible and session.vehicle_id not in attached:
                matching = sorted(key for key in free if usable[key].connector_type == session.connector_type)
                if matching:
                    attached[session.vehicle_id] = matching[0]
                    free.remove(matching[0])
        budget = scenario.station.station_power_limit_kw
        for session in ordered:
            charger_id = attached.get(session.vehicle_id)
            if charger_id is None or budget <= 1e-8:
                continue
            charger = usable[charger_id]
            rate = min(session.max_charging_power_kw, charger.max_power_kw, budget,
                       remaining[session.vehicle_id] / (hours(start, end) * scenario.station.charging_efficiency))
            if rate > 1e-8:
                records.append(allocation(scenario, session, charger, start, end, rate))
                remaining[session.vehicle_id] -= rate * hours(start, end) * scenario.station.charging_efficiency
                budget -= rate
    return Schedule(kind="baseline", allocations=records, state_version=scenario.state_version,
                    schedule_version=scenario.schedule_version + 1, solver_status="FCFS",
                    runtime_seconds=time.perf_counter() - began)


def optimize(scenario, time_limit_seconds=8):
    began = time.perf_counter()
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise SchedulingError("OR-Tools SCIP backend is unavailable")
    solver.SetNumThreads(1)
    solver.SetTimeLimit(int(time_limit_seconds * 500))
    solver.SetSolverSpecificParametersAsString("numerics/feastol = 1e-9")
    parameters = pywraplp.MPSolverParameters()
    parameters.SetDoubleParam(pywraplp.MPSolverParameters.RELATIVE_MIP_GAP, 0)
    groups = defaultdict(list)
    for charger in scenario.station.chargers:
        groups[(charger.connector_type, charger.max_power_kw)].append(charger)
    group_list = list(groups.values())
    slots = intervals(scenario)
    remaining = remaining_energy(scenario)
    powers = {}
    vehicle_energy = defaultdict(list)
    slot_power, slot_group, slot_vehicle = defaultdict(list), defaultdict(list), defaultdict(list)
    for t, (start, end) in enumerate(slots):
        for v, session in enumerate(scenario.sessions):
            if remaining[session.vehicle_id] <= 1e-8 or session.arrival_time > start or session.departure_time < end:
                continue
            for g, chargers in enumerate(group_list):
                if chargers[0].connector_type != session.connector_type or not any(available_at(scenario, c, start) for c in chargers):
                    continue
                if len(powers) >= 40000:
                    raise SchedulingError("Scenario exceeds the interactive model budget; reduce horizon or charger types")
                rate = min(session.max_charging_power_kw, chargers[0].max_power_kw, scenario.station.station_power_limit_kw)
                key = (v, g, t)
                p = solver.NumVar(0, rate, f"p_{v}_{g}_{t}")
                assigned = solver.BoolVar(f"a_{v}_{g}_{t}")
                solver.Add(p <= rate * assigned)
                powers[key] = p
                vehicle_energy[v].append(p * hours(start, end) * scenario.station.charging_efficiency)
                slot_power[t].append(p)
                slot_group[t, g].append(assigned)
                slot_vehicle[t, v].append(assigned)
    shortfalls = []
    for v, session in enumerate(scenario.sessions):
        shortfall = solver.NumVar(0, remaining[session.vehicle_id], f"shortfall_{v}")
        solver.Add(solver.Sum(vehicle_energy[v]) + shortfall == remaining[session.vehicle_id])
        shortfalls.append(shortfall)
    for t, terms in slot_power.items():
        solver.Add(solver.Sum(terms) <= scenario.station.station_power_limit_kw)
    for (t, g), terms in slot_group.items():
        count = sum(available_at(scenario, c, slots[t][0]) for c in group_list[g])
        solver.Add(solver.Sum(terms) <= count)
    for terms in slot_vehicle.values():
        solver.Add(solver.Sum(terms) <= 1)
    total_shortfall = solver.Sum(shortfalls)
    solver.Minimize(total_shortfall)
    first_status = solver.Solve(parameters)
    if first_status not in (solver.OPTIMAL, solver.FEASIBLE):
        raise SchedulingError("No feasible schedule found within the solver budget")
    best_shortfall = sum(value.solution_value() for value in shortfalls)
    saved = {key: p.solution_value() for key, p in powers.items()}
    solver.Add(total_shortfall <= best_shortfall + 1e-7)
    solver.Minimize(solver.Sum(p * hours(*slots[t]) * price_at(scenario, slots[t][0]) for (v, g, t), p in powers.items()))
    second_status = solver.Solve(parameters)
    if second_status in (solver.OPTIMAL, solver.FEASIBLE):
        saved = {key: p.solution_value() for key, p in powers.items()}
    records = list(scenario.history)
    selected = defaultdict(list)
    for (v, g, t), value in saved.items():
        if value > 1e-7:
            selected[t, g].append((v, value))
    for t, (start, end) in enumerate(slots):
        for g, chargers in enumerate(group_list):
            available = sorted((c for c in chargers if available_at(scenario, c, start)), key=lambda c: c.charger_id)
            charging = sorted(selected[t, g])
            if len(charging) > len(available):
                raise SchedulingError("Solver returned an invalid charger assignment")
            for (v, power), charger in zip(charging, available):
                records.append(allocation(scenario, scenario.sessions[v], charger, start, end, power))
    phase1 = first_status == solver.OPTIMAL
    phase2 = second_status == solver.OPTIMAL
    return Schedule(kind="optimized", allocations=records, state_version=scenario.state_version,
                    schedule_version=scenario.schedule_version + 1,
                    solver_status="OPTIMAL" if phase1 and phase2 else "FEASIBLE_TIME_LIMIT",
                    shortfall_optimal=phase1, cost_optimal=phase1 and phase2,
                    runtime_seconds=time.perf_counter() - began)
