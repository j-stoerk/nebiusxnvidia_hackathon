"""SCIP schedules actual physical ports; never reassign/drop energy after solving."""
from collections import defaultdict
import time

from ortools.linear_solver import pywraplp

from ..models import Allocation, ScheduleResult
from ..utils.datetime_utils import hours
from .cost_calculator import compute_metrics, price_at
from .csv_validator import check_scenario, InputError
from .physics import available, battery_energy, planning_slots
from .tariffs import demand_windows, overlap, prior_peak


class OptimizationError(RuntimeError):
    pass


def _variables(solver, sessions, station, ports, slots, outages, history):
    powers, attach = {}, {}
    previous = {r.vehicle_id: r.charger_id for r in history}
    for v, session in enumerate(sessions):
        fixed = session.charger_id or previous.get(session.vehicle_id)
        compatible = [c for c in ports if c.connector_type == session.connector_type and (not fixed or c.charger_id == fixed)]
        if fixed and not compatible:
            raise InputError(f"Candidate hardware excludes bound charger {fixed}")
        if station.fixed_connections:
            for c in compatible:
                attach[v, c.charger_id] = solver.BoolVar(f"plug_{v}_{c.charger_id}")
            total = solver.Sum(attach[v, c.charger_id] for c in compatible)
            solver.Add(total == 1 if fixed else total <= 1)
        for t, (a, b) in enumerate(slots):
            if not session.arrival_time <= a < b <= session.departure_time:
                continue
            for c in compatible:
                if not available(c, a, b, outages):
                    continue
                key = (v, c.charger_id, t)
                enabled = attach[v, c.charger_id] if station.fixed_connections else solver.BoolVar(f"on_{v}_{c.charger_id}_{t}")
                if not station.fixed_connections:
                    attach[key] = enabled
                cap = min(session.max_charging_power_kw, c.max_power_kw, station.station_power_limit_kw)
                powers[key] = solver.NumVar(0, cap, f"p_{v}_{c.charger_id}_{t}")
                solver.Add(powers[key] <= cap * enabled)
                if len(powers) > 40000:
                    raise InputError("Scenario exceeds the interactive solver budget; use a shorter roster or fewer chargers")
    return powers, attach


def _constraints(solver, sessions, station, ports, slots, powers, attach, history, limit):
    delivered = defaultdict(float)
    for r in history:
        delivered[r.vehicle_id] += battery_energy(r)
    shortfalls = []
    for v, s in enumerate(sessions):
        terms = [p * hours(*slots[t]) * station.charging_efficiency for (vehicle, c, t), p in powers.items() if vehicle == v]
        remaining = max(0, s.energy_required_kwh - delivered[s.vehicle_id])
        missing = solver.NumVar(0, remaining, f"missing_{v}")
        solver.Add(solver.Sum(terms) + missing == remaining)
        shortfalls.append(missing)
        for t in range(len(slots)):
            group = [p for (vehicle, c, slot), p in powers.items() if vehicle == v and slot == t]
            if not group:
                continue
            if not station.fixed_connections:
                solver.Add(solver.Sum(flag for (vehicle, c, slot), flag in attach.items() if vehicle == v and slot == t) <= 1)
            if s.battery_capacity_kwh is not None:
                cumulative = solver.Sum(p * hours(*slots[slot]) * station.charging_efficiency
                    for (vehicle, c, slot), p in powers.items() if vehicle == v and slot <= t)
                headroom = s.battery_capacity_kwh * (1 - s.initial_soc) - delivered[s.vehicle_id]
                scale = s.battery_capacity_kwh * (1 - s.transition_soc)
                solver.Add(solver.Sum(group) <= s.max_charging_power_kw * (headroom - cumulative) / scale)
    for t, (a, b) in enumerate(slots):
        solver.Add(solver.Sum(p for (v, c, slot), p in powers.items() if slot == t) <= limit)
        for port in ports:
            if station.fixed_connections:
                flags = [flag for (v, c), flag in attach.items() if c == port.charger_id and sessions[v].arrival_time < b and sessions[v].departure_time > a]
            else:
                flags = [flag for (v, c, slot), flag in attach.items() if c == port.charger_id and slot == t]
            solver.Add(solver.Sum(flags) <= 1)
    return solver.Sum(shortfalls)


def _objectives(solver, sessions, station, prices, adjustments, slots, powers, history):
    peak = solver.NumVar(0, solver.infinity(), "instantaneous_peak")
    for t in range(len(slots)):
        solver.Add(peak >= solver.Sum(p for (v, c, slot), p in powers.items() if slot == t))
    changes = defaultdict(float)
    for r in history:
        changes[r.start_time] += r.power_kw
        changes[r.end_time] -= r.power_kw
    current = 0
    for _, change in sorted(changes.items()):
        current += change
        solver.Add(peak >= current)
    tariff, billing = station.demand_tariff, {}
    for a, b, period in demand_windows(sessions, tariff):
        if period not in billing:
            billing[period] = solver.NumVar(prior_peak(tariff, period), solver.infinity(), f"meter_{period}")
        future = solver.Sum(p * overlap(a, b, *slots[t]) / .25 for (v, c, t), p in powers.items() if slots[t][0] < b and slots[t][1] > a)
        past = sum(r.power_kw * overlap(a, b, r.start_time, r.end_time) / .25 for r in history)
        solver.Add(billing[period] >= future + past)
    energy = solver.Sum(p * hours(*slots[t]) * price_at(prices, slots[t][0], adjustments) for (v, c, t), p in powers.items())
    demand = solver.Sum((value - prior_peak(tariff, key)) * tariff.eur_per_kw for key, value in billing.items())
    return peak, energy + demand


def _solve(solver, shortfall, peak, cost, powers, goal, report):
    report("energy", "running")
    solver.Minimize(shortfall)
    first = solver.Solve()
    if first not in (solver.OPTIMAL, solver.FEASIBLE):
        raise OptimizationError("No valid plan found within the solver budget")
    values = {key: p.solution_value() for key, p in powers.items()}
    solver.Add(shortfall <= solver.Objective().Value() + 1e-7)
    peak_optimal = cost_optimal = False
    stages = [(peak, "peak"), (cost, "cost")] if goal == "peak" else [(cost, "cost")]
    for objective, name in stages:
        report(name, "running")
        solver.Minimize(objective)
        status = solver.Solve()
        if status not in (solver.OPTIMAL, solver.FEASIBLE):
            break  # Retain the previous valid incumbent on a timeout.
        values = {key: p.solution_value() for key, p in powers.items()}
        if name == "peak":
            peak_optimal = first == solver.OPTIMAL and status == solver.OPTIMAL
            solver.Add(peak <= solver.Objective().Value() + 1e-7)
        else:
            cost_optimal = first == solver.OPTIMAL and status == solver.OPTIMAL and (goal != "peak" or peak_optimal)
    return values, first == solver.OPTIMAL, peak_optimal, cost_optimal


def optimize_schedule(sessions, station, prices, outages=None, price_adjustments=None,
                      time_limit_seconds=8, charger_ids=None, power_limit_kw=None, history=None, now=None, goal=None, max_horizon_hours=72, report=None):
    from .schedule_validator import validate_schedule
    began = time.perf_counter()
    report = report or (lambda *_: None)
    check_scenario(sessions, station, prices, max_horizon_hours)
    outages, adjustments, history = outages or [], price_adjustments or [], history or []
    ports = [c for c in station.chargers if charger_ids is None or c.charger_id in charger_ids]
    limit = station.station_power_limit_kw if power_limit_kw is None else min(power_limit_kw, station.station_power_limit_kw)
    if not ports or limit <= 0:
        raise InputError("Candidate needs installed chargers and positive site power")
    goal = goal or station.optimization_goal
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise OptimizationError("OR-Tools SCIP is unavailable")
    solver.SetNumThreads(1)
    solver.SetTimeLimit(max(100, int(time_limit_seconds * 1000 / (3 if goal == "peak" else 2))))
    solver.SetSolverSpecificParametersAsString("numerics/feastol = 1e-9")
    slots = planning_slots(sessions, outages, adjustments, now)
    powers, attach = _variables(solver, sessions, station, ports, slots, outages, history)
    shortfall = _constraints(solver, sessions, station, ports, slots, powers, attach, history, limit)
    peak, cost = _objectives(solver, sessions, station, prices, adjustments, slots, powers, history)
    values, energy_ok, peak_ok, cost_ok = _solve(solver, shortfall, peak, cost, powers, goal, report)
    records = [*history, *[Allocation(vehicle_id=sessions[v].vehicle_id, charger_id=c,
        start_time=slots[t][0], end_time=slots[t][1], power_kw=p, charging_efficiency=station.charging_efficiency)
        for (v, c, t), p in values.items() if p > 1e-6]]
    result = ScheduleResult(kind="optimized", allocations=records, metrics=compute_metrics(sessions, records, station, prices, adjustments),
        solver_status="OR-Tools/OPTIMAL" if cost_ok else "OR-Tools/FEASIBLE_TIME_LIMIT", runtime_seconds=time.perf_counter() - began,
        shortfall_optimal=energy_ok, peak_optimal=peak_ok, cost_optimal=cost_ok)
    report("validation", "running")
    validate_schedule(sessions, station, result, outages, history, now, charger_ids, limit)
    result.validated = True
    return result
