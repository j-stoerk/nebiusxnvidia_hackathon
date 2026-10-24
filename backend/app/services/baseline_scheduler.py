"""First-come-first-served baseline schedule for cost comparison."""

import time

from ..models import Allocation, PricePoint, ScheduleResult, StationConfig, VehicleSession
from ..utils.datetime_utils import hours, iter_slots
from .cost_calculator import compute_metrics


def _available_chargers(station: StationConfig, moment, outages: list[tuple]):
    unavailable = set()
    for charger_id, start, end in outages:
        if start <= moment < end:
            unavailable.add(charger_id)
    return [c for c in station.chargers if c.available and c.charger_id not in unavailable]


def build_baseline(
    sessions: list[VehicleSession],
    station: StationConfig,
    prices: list[PricePoint],
    outages: list[tuple] | None = None,
    price_adjustments: list[tuple] | None = None,
) -> ScheduleResult:
    """Greedy FCFS: earlier arrivals get priority; fixed plug means no mid-session switching."""
    began = time.perf_counter()
    outages = outages or []
    efficiency = station.charging_efficiency
    remaining = {s.vehicle_id: s.energy_required_kwh for s in sessions}
    attached: dict[str, str] = {s.vehicle_id: s.charger_id for s in sessions if s.charger_id}
    records: list[Allocation] = []

    if not sessions:
        metrics = compute_metrics([], [], station, prices, price_adjustments)
        return ScheduleResult(
            kind="baseline",
            allocations=[],
            metrics=metrics,
            solver_status="FCFS",
            runtime_seconds=time.perf_counter() - began,
        )

    start = min(s.arrival_time for s in sessions)
    end = max(s.departure_time for s in sessions)

    for slot_start, slot_end in iter_slots(start, end, station.slot_minutes):
        duration = hours(slot_start, slot_end)
        if duration <= 0:
            continue
        free = {c.charger_id: c for c in _available_chargers(station, slot_start, outages)}
        budget = station.station_power_limit_kw
        ordered = sorted(sessions, key=lambda s: (s.arrival_time, s.vehicle_id))

        for session in ordered:
            if remaining[session.vehicle_id] <= 1e-8:
                continue
            if not (session.arrival_time <= slot_start and slot_end <= session.departure_time):
                continue
            reserved = attached.get(session.vehicle_id)
            if station.fixed_connections and reserved:
                if reserved not in free:
                    continue
                candidates = [reserved]
            else:
                candidates = sorted(free)
            if not candidates or budget <= 1e-8:
                continue
            charger = free.pop(candidates[0])
            attached[session.vehicle_id] = charger.charger_id
            rate = min(
                session.max_charging_power_kw,
                charger.max_power_kw,
                budget,
                remaining[session.vehicle_id] / (duration * efficiency),
            )
            if rate <= 1e-8:
                continue
            records.append(
                Allocation(
                    vehicle_id=session.vehicle_id,
                    charger_id=charger.charger_id,
                    start_time=slot_start,
                    end_time=slot_end,
                    power_kw=rate,
                )
            )
            remaining[session.vehicle_id] -= rate * duration * efficiency
            budget -= rate

    metrics = compute_metrics(sessions, records, station, prices, price_adjustments)
    return ScheduleResult(
        kind="baseline",
        allocations=records,
        metrics=metrics,
        solver_status="FCFS",
        runtime_seconds=round(time.perf_counter() - began, 4),
    )
