"""OR-Tools charging schedule optimizer (SCIP)."""

import time
from collections import defaultdict

from ortools.linear_solver import pywraplp

from ..models import Allocation, PricePoint, ScheduleResult, StationConfig, VehicleSession
from ..utils.datetime_utils import hours, iter_slots
from .cost_calculator import compute_metrics, price_at


class OptimizationError(RuntimeError):
    pass


def _available_chargers(station: StationConfig, moment, outages: list[tuple], charger_ids=None):
    unavailable = set()
    for charger_id, start, end in outages:
        if start <= moment < end:
            unavailable.add(charger_id)
    chargers = station.chargers
    if charger_ids is not None:
        allowed = set(charger_ids)
        chargers = [c for c in chargers if c.charger_id in allowed]
    return [c for c in chargers if c.available and c.charger_id not in unavailable]


def _intervals_overlap(a0, a1, b0, b1) -> bool:
    return a0 < b1 and b0 < a1


def _assign_fixed(sessions, slots, power_by_vt, station, outages, charger_ids=None):
    """
    Bind each vehicle to one charger ID for all of its charging slots (no switching).
    Conflicts are checked on overlapping charge intervals (and explicit CSV bindings).
    """
    vehicles_power = defaultdict(list)
    for (v, t), pw in power_by_vt.items():
        if pw > 1e-7:
            vehicles_power[v].append((t, pw))

    # charger_id -> list of (start, end) already reserved by charging or CSV binding
    occupied = defaultdict(list)
    bindings = {}
    for session in sessions:
        if session.charger_id:
            bindings[session.vehicle_id] = session.charger_id
            occupied[session.charger_id].append((session.arrival_time, session.departure_time))

    ordered = sorted(
        ((v, sessions[v]) for v in vehicles_power),
        key=lambda item: (item[1].arrival_time, item[1].vehicle_id),
    )
    for v, session in ordered:
        charge_windows = [slots[t] for t, _ in vehicles_power[v]]
        if session.vehicle_id in bindings:
            cid = bindings[session.vehicle_id]
            occupied[cid].extend(charge_windows)
            continue

        candidates = sorted(
            {
                c.charger_id
                for t, _ in vehicles_power[v]
                for c in _available_chargers(station, slots[t][0], outages, charger_ids)
            }
        )
        pool = candidates or sorted(
            c.charger_id for c in station.chargers if charger_ids is None or c.charger_id in set(charger_ids)
        )
        chosen = None
        for cid in pool:
            if all(
                not _intervals_overlap(w0, w1, a, b)
                for w0, w1 in charge_windows
                for a, b in occupied[cid]
            ):
                chosen = cid
                break
        if chosen is None:
            # Last resort: still bind one id (may share idle gaps); prefer least-used.
            usage = {cid: len(occupied[cid]) for cid in pool} or {c.charger_id: 0 for c in station.chargers}
            chosen = min(usage, key=usage.get)
        bindings[session.vehicle_id] = chosen
        occupied[chosen].extend(charge_windows)

    records = []
    for v, items in vehicles_power.items():
        session = sessions[v]
        charger_id = bindings[session.vehicle_id]
        for t, pw in items:
            start, end = slots[t]
            if charger_id not in {
                c.charger_id for c in _available_chargers(station, start, outages, charger_ids)
            }:
                continue
            records.append(
                Allocation(
                    vehicle_id=session.vehicle_id,
                    charger_id=charger_id,
                    start_time=start,
                    end_time=end,
                    power_kw=round(pw, 6),
                )
            )
    return records


def optimize_schedule(
    sessions: list[VehicleSession],
    station: StationConfig,
    prices: list[PricePoint],
    outages: list[tuple] | None = None,
    price_adjustments: list[tuple] | None = None,
    time_limit_seconds: float = 8.0,
    charger_ids: list[str] | None = None,
    power_limit_kw: float | None = None,
) -> ScheduleResult:
    """
    Lexicographic MIP:
      1) minimize unserved battery energy
      2) minimize station peak power (capacity / peak reduction)
      3) minimize energy + incremental demand cost
    """
    began = time.perf_counter()
    outages = outages or []
    limit = power_limit_kw if power_limit_kw is not None else station.station_power_limit_kw
    efficiency = station.charging_efficiency

    if not sessions:
        metrics = compute_metrics([], [], station, prices, price_adjustments)
        return ScheduleResult(
            kind="optimized",
            allocations=[],
            metrics=metrics,
            solver_status="EMPTY",
            runtime_seconds=0.0,
        )

    slots = list(
        iter_slots(
            min(s.arrival_time for s in sessions),
            max(s.departure_time for s in sessions),
            station.slot_minutes,
        )
    )
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise OptimizationError("OR-Tools SCIP backend is unavailable")
    solver.SetNumThreads(1)
    # Split budget across three stages.
    stage_ms = max(500, int(time_limit_seconds * 1000 / 3))
    solver.SetTimeLimit(stage_ms)

    power_vars = {}
    assign_vars = {}
    energy_terms = defaultdict(list)
    station_terms = defaultdict(list)
    charger_terms = defaultdict(list)

    for t, (start, end) in enumerate(slots):
        available = _available_chargers(station, start, outages, charger_ids)
        n_chargers = len(available)
        max_charger = max((c.max_power_kw for c in available), default=0.0)
        for v, session in enumerate(sessions):
            if not (session.arrival_time <= start and end <= session.departure_time):
                continue
            if n_chargers == 0:
                continue
            cap = min(session.max_charging_power_kw, max_charger, limit)
            p = solver.NumVar(0.0, cap, f"p_{v}_{t}")
            a = solver.BoolVar(f"a_{v}_{t}")
            solver.Add(p <= cap * a)
            power_vars[v, t] = p
            assign_vars[v, t] = a
            energy_terms[v].append(p * hours(start, end) * efficiency)
            station_terms[t].append(p)
            charger_terms[t].append(a)
        if charger_terms[t]:
            solver.Add(solver.Sum(charger_terms[t]) <= n_chargers)
        if station_terms[t]:
            solver.Add(solver.Sum(station_terms[t]) <= limit)

    shortfalls = []
    for v, session in enumerate(sessions):
        shortfall = solver.NumVar(0.0, session.energy_required_kwh, f"s_{v}")
        terms = energy_terms[v]
        solver.Add((solver.Sum(terms) if terms else 0) + shortfall == session.energy_required_kwh)
        shortfalls.append(shortfall)

    peak = solver.NumVar(0.0, limit, "peak")
    for t, terms in station_terms.items():
        if terms:
            solver.Add(peak >= solver.Sum(terms))

    # Stage 1: minimize unserved energy.
    solver.Minimize(solver.Sum(shortfalls))
    status = solver.Solve()
    if status not in (solver.OPTIMAL, solver.FEASIBLE):
        raise OptimizationError("No feasible schedule found within the solver budget")
    best_shortfall = solver.Objective().Value()
    solver.Add(solver.Sum(shortfalls) <= best_shortfall + 1e-6)

    # Stage 2: minimize peak power (capacity advantage).
    solver.SetTimeLimit(stage_ms)
    solver.Minimize(peak)
    status_peak = solver.Solve()
    if status_peak not in (solver.OPTIMAL, solver.FEASIBLE):
        raise OptimizationError("Peak stage failed after fixing unserved energy")
    best_peak = peak.solution_value()
    solver.Add(peak <= best_peak + 1e-5)

    # Stage 3: minimize energy + demand cost.
    tariff = station.demand_tariff
    energy_terms_cost = []
    for (v, t), p in power_vars.items():
        start, end = slots[t]
        rate = price_at(prices, start, price_adjustments)
        energy_terms_cost.append(p * hours(start, end) * rate)
    demand_extra = solver.NumVar(0.0, solver.infinity(), "demand_extra")
    solver.Add(demand_extra >= peak - tariff.prior_peak_kw)
    cost_expr = (solver.Sum(energy_terms_cost) if energy_terms_cost else 0) + demand_extra * tariff.eur_per_kw
    solver.SetTimeLimit(stage_ms)
    solver.Minimize(cost_expr)
    status2 = solver.Solve()
    if status2 not in (solver.OPTIMAL, solver.FEASIBLE):
        raise OptimizationError("Cost stage failed after fixing peak")

    power_by_vt = {key: var.solution_value() for key, var in power_vars.items()}
    if station.fixed_connections:
        records = _assign_fixed(sessions, slots, power_by_vt, station, outages, charger_ids)
    else:
        records = []
        attached = {s.vehicle_id: s.charger_id for s in sessions if s.charger_id}
        for t, (start, end) in enumerate(slots):
            available = {c.charger_id: c for c in _available_chargers(station, start, outages, charger_ids)}
            active = []
            for v, session in enumerate(sessions):
                pw = power_by_vt.get((v, t), 0.0)
                if pw > 1e-7:
                    active.append((session, pw))
            active.sort(key=lambda item: (item[0].arrival_time, item[0].vehicle_id))
            for session, pw in active:
                reserved = attached.get(session.vehicle_id)
                if reserved and reserved in available:
                    charger_id = reserved
                else:
                    candidates = sorted(available)
                    if not candidates:
                        continue
                    charger_id = candidates[0]
                available.pop(charger_id, None)
                attached[session.vehicle_id] = charger_id
                records.append(
                    Allocation(
                        vehicle_id=session.vehicle_id,
                        charger_id=charger_id,
                        start_time=start,
                        end_time=end,
                        power_kw=round(pw, 6),
                    )
                )

    # Metrics use the real station config (including demand tariff), even if a capacity
    # candidate temporarily lowered the power limit during the solve.
    metrics = compute_metrics(sessions, records, station, prices, price_adjustments)
    label = "OPTIMAL" if status2 == solver.OPTIMAL else "FEASIBLE"
    return ScheduleResult(
        kind="optimized",
        allocations=records,
        metrics=metrics,
        solver_status=f"OR-Tools/{label}+peak",
        runtime_seconds=round(time.perf_counter() - began, 4),
    )
