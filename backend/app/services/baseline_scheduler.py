"""FCFS, earliest deadline, and rolling least-laxity share the same physical model."""
from collections import defaultdict
import time

from ..models import Allocation, ScheduleResult
from ..utils.datetime_utils import hours
from .cost_calculator import compute_metrics
from .csv_validator import check_scenario
from .physics import available, battery_energy, minimum_hours, planning_slots, sustainable_power
from .schedule_validator import validate_schedule


def _priority(policy, session, when, remaining, delivered, station):
    rates = [c.max_power_kw for c in station.chargers if c.available and c.connector_type == session.connector_type]
    rate = min(session.max_charging_power_kw, max(rates, default=0), station.station_power_limit_kw)
    if policy == "EDF":
        return (session.departure_time, session.arrival_time, session.vehicle_id)
    if policy == "LLF":
        laxity = hours(when, session.departure_time) - minimum_hours(session, delivered, remaining, rate, station.charging_efficiency)
        return (laxity, session.departure_time, session.vehicle_id)
    return (session.arrival_time, session.vehicle_id)


def build_baseline(sessions, station, prices, outages=None, price_adjustments=None, policy="FCFS", history=None, now=None, max_horizon_hours=72):
    began = time.perf_counter()
    check_scenario(sessions, station, prices, max_horizon_hours)
    if policy not in {"FCFS", "EDF", "LLF"}:
        raise ValueError("Unknown comparison policy")
    outages, adjustments, history = outages or [], price_adjustments or [], history or []
    delivered = defaultdict(float)
    for r in history:
        delivered[r.vehicle_id] += battery_energy(r)
    bindings = {r.vehicle_id: r.charger_id for r in history}
    bindings.update({s.vehicle_id: s.charger_id for s in sessions if s.charger_id})
    records = list(history)
    for a, b in planning_slots(sessions, outages, adjustments, now):
        duration, budget = hours(a, b), station.station_power_limit_kw
        active = [s for s in sessions if s.arrival_time <= a < b <= s.departure_time]
        reserved = {bindings[s.vehicle_id]: s.vehicle_id for s in active if station.fixed_connections and s.vehicle_id in bindings}
        taken = set()
        ordered = sorted(active, key=lambda s: _priority(policy, s, a, max(0, s.energy_required_kwh - delivered[s.vehicle_id]), delivered[s.vehicle_id], station))
        for s in ordered:
            remaining = max(0, s.energy_required_kwh - delivered[s.vehicle_id])
            if remaining <= 1e-8:
                continue
            bound = bindings.get(s.vehicle_id) if station.fixed_connections else None
            candidates = [c for c in station.chargers if c.connector_type == s.connector_type and
                c.charger_id not in taken and (not bound or c.charger_id == bound) and
                reserved.get(c.charger_id, s.vehicle_id) == s.vehicle_id and available(c, a, b, outages)]
            if station.fixed_connections and not bound:
                candidates = [c for c in candidates if not any(bindings.get(other.vehicle_id) == c.charger_id and
                    other.arrival_time < s.departure_time and other.departure_time > s.arrival_time for other in sessions)]
            if not candidates:
                continue
            c = min(candidates, key=lambda port: port.charger_id)
            if station.fixed_connections:
                bindings[s.vehicle_id], reserved[c.charger_id] = c.charger_id, s.vehicle_id
            rate = min(s.max_charging_power_kw, c.max_power_kw, budget, remaining / (duration * station.charging_efficiency),
                       sustainable_power(s, delivered[s.vehicle_id], duration, station.charging_efficiency))
            if rate <= 1e-8:
                continue
            record = Allocation(vehicle_id=s.vehicle_id, charger_id=c.charger_id, start_time=a, end_time=b,
                                power_kw=rate, charging_efficiency=station.charging_efficiency)
            records.append(record)
            delivered[s.vehicle_id] += battery_energy(record)
            taken.add(c.charger_id)
            budget -= rate
    result = ScheduleResult(kind="baseline", allocations=records, metrics=compute_metrics(sessions, records, station, prices, adjustments),
                            solver_status=policy, runtime_seconds=time.perf_counter() - began)
    validate_schedule(sessions, station, result, outages, history, now)
    result.validated = True
    return result
