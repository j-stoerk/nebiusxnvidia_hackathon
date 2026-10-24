"""Mutable workspace state and pure time/availability helpers."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading

from .csv_validator import check_scenario
from ..models import Allocation, Event, Price, Schedule, Session, Station


@dataclass
class Scenario:
    workspace_id: str
    sessions: list[Session]
    station: Station
    prices: list[Price]
    label: str = "Synthetic demo"
    state_version: int = 1
    schedule_version: int = 0
    events: dict[str, Event] = field(default_factory=dict)
    history: list[Allocation] = field(default_factory=list)
    baseline: Schedule | None = None
    optimized: Schedule | None = None
    references: dict[str, Schedule] = field(default_factory=dict)
    max_horizon_days: int = 3
    stale: bool = False
    last_error: str | None = None
    recovery_seconds: float | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self):
        self.start, self.end = check_scenario(self.sessions, self.station, self.prices, self.max_horizon_days)
        self.now = self.start
        self.price_map = {p.timestamp: p.price_eur_per_kwh for p in self.prices}


def hours(start, end):
    return (end - start).total_seconds() / 3600


def battery_energy(allocation):
    return allocation.power_kw * hours(allocation.start_time, allocation.end_time) * allocation.charging_efficiency


def remaining_energy(scenario):
    remaining = {s.vehicle_id: s.energy_required_kwh for s in scenario.sessions}
    for record in scenario.history:
        remaining[record.vehicle_id] -= battery_energy(record)
    return {key: max(0, value) for key, value in remaining.items()}


def price_at(scenario, instant):
    stamp = instant.replace(minute=(instant.minute // 15) * 15, second=0, microsecond=0)
    value = scenario.price_map[stamp]
    return value + sum(e.add_eur_per_kwh for e in scenario.events.values()
                       if e.type == "PRICE_CHANGED" and e.start_time <= instant < e.end_time)


def available_at(scenario, charger, instant):
    recoveries = [e.time for e in scenario.events.values() if e.type == "CHARGER_RECOVERED" and e.charger_id == charger.charger_id]
    # A recovery clears a simulated fault; it does not enable a charger disabled in settings.
    available = charger.available
    for event in scenario.events.values():
        if event.type == "CHARGER_FAILED" and event.charger_id == charger.charger_id:
            until = min([event.end_time, *[time for time in recoveries if time >= event.start_time]])
            if event.start_time <= instant < until:
                return False
    return available


def intervals(scenario):
    boundaries = {scenario.now, scenario.end}
    # Price observations and configured grid; other boundaries refine slots exactly.
    cursor = scenario.start
    while cursor <= scenario.end:
        boundaries.add(cursor)
        cursor += timedelta(minutes=15)
    for session in scenario.sessions:
        boundaries.update((session.arrival_time, session.departure_time))
    for event in scenario.events.values():
        boundaries.update(time for time in (event.start_time, event.end_time, event.time) if time is not None)
    ordered = sorted(time for time in boundaries if scenario.now <= time <= scenario.end)
    return list(zip(ordered, ordered[1:]))


def freeze_history(scenario, instant):
    active = scenario.optimized if scenario.optimized is not None and not scenario.stale else scenario.baseline
    if active is None or scenario.stale:
        raise ValueError("Create a current validated schedule before advancing simulation time")
    records = []
    for record in active.allocations:
        if record.start_time < instant:
            records.append(record.model_copy(update={"end_time": min(instant, record.end_time)}))
    return records
