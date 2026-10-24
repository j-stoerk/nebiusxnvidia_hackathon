"""Validate raw allocations independently of the optimizer's model and assignments."""

from collections import Counter, defaultdict
import math

from .scenario import available_at, battery_energy

TOLERANCE = 1e-5


class InvalidSchedule(ValueError):
    pass


def signature(record):
    return (record.vehicle_id, record.charger_id, record.start_time, record.end_time,
            round(record.power_kw, 9), record.charging_efficiency)


def _future_errors(scenario, record, session, charger):
    errors = []
    if record.start_time < scenario.now:
        errors.append("Future allocation overlaps completed history")
    if charger.connector_type != session.connector_type:
        errors.append(f"Incompatible connector for {session.vehicle_id}")
    if session.charger_id is not None and record.charger_id != session.charger_id:
        errors.append(f"Wrong assigned charger for {session.vehicle_id}")
    if record.power_kw > min(session.max_charging_power_kw, charger.max_power_kw) + TOLERANCE:
        errors.append(f"Power rating exceeded for {session.vehicle_id}")
    if abs(record.charging_efficiency - scenario.station.charging_efficiency) > TOLERANCE:
        errors.append("Wrong future charging efficiency")
    # A long allocation can cross a failure even when its starting instant is valid.
    boundaries = {record.start_time}
    for event in scenario.events.values():
        boundaries.update(t for t in (event.start_time, event.end_time, event.time)
                          if t is not None and record.start_time < t < record.end_time)
    if any(not available_at(scenario, charger, t) for t in boundaries):
        errors.append(f"Charging on unavailable charger {charger.charger_id}")
    return errors


def _record_errors(record, session, index):
    errors = []
    if not math.isfinite(record.power_kw) or record.power_kw <= 0:
        errors.append(f"Invalid power at allocation {index}")
    if record.end_time <= record.start_time:
        errors.append(f"Invalid duration at allocation {index}")
    if record.start_time < session.arrival_time or record.end_time > session.departure_time:
        errors.append(f"Charging outside availability for {session.vehicle_id}")
    return errors


def _concurrency_errors(scenario, changes):
    errors, active = [], {}
    for instant in sorted(changes):
        # End before start: half-open intervals allow immediate reassignment.
        for direction, key, record in sorted(changes[instant], key=lambda item: item[0]):
            if direction == -1:
                active.pop(key, None)
            else:
                active[key] = record
        if sum(r.power_kw for r in active.values()) > scenario.station.station_power_limit_kw + TOLERANCE:
            errors.append(f"Station cap exceeded at {instant.isoformat()}")
        if len({r.vehicle_id for r in active.values()}) != len(active):
            errors.append(f"Vehicle uses multiple connectors at {instant.isoformat()}")
        if len({r.charger_id for r in active.values()}) != len(active):
            errors.append(f"Charger serves multiple vehicles at {instant.isoformat()}")
    return errors


def _allocations_errors(scenario, schedule):
    errors, energy, changes = [], defaultdict(float), defaultdict(list)
    sessions = {s.vehicle_id: s for s in scenario.sessions}
    chargers = {c.charger_id: c for c in scenario.station.chargers}
    for index, record in enumerate(schedule.allocations):
        session = sessions.get(record.vehicle_id)
        if session is None:
            errors.append(f"Unknown vehicle at allocation {index}")
            continue
        errors.extend(_record_errors(record, session, index))
        energy[record.vehicle_id] += battery_energy(record)
        if record.end_time <= scenario.now:
            continue  # History is checked against its immutable ledger, not new limits.
        charger = chargers.get(record.charger_id)
        if charger is None:
            errors.append(f"Unknown charger {record.charger_id}")
            continue
        errors.extend(_future_errors(scenario, record, session, charger))
        changes[record.start_time].append((1, index, record))
        changes[record.end_time].append((-1, index, record))
    errors.extend(f"Excess energy delivered to {v}" for v, value in energy.items()
                  if value > sessions[v].energy_required_kwh + TOLERANCE)
    return errors + _concurrency_errors(scenario, changes) + _taper_errors(scenario, schedule) + _connection_errors(scenario, schedule)


def _connection_errors(scenario, schedule):
    if not scenario.station.fixed_connections:
        return []
    errors, reservations = [], defaultdict(list)
    for session in scenario.sessions:
        records = [r for r in schedule.allocations if r.vehicle_id == session.vehicle_id]
        future = {r.charger_id for r in records if r.end_time > scenario.now}
        past = sorted((r for r in records if r.end_time <= scenario.now), key=lambda r: r.end_time)
        ids = future | ({past[-1].charger_id} if past else set()) | ({session.charger_id} if session.charger_id else set())
        if len(ids) > 1:
            errors.append(f"Fixed connection changed for {session.vehicle_id}")
        if ids and session.departure_time > scenario.now:
            reservations[next(iter(ids))].append((max(session.arrival_time, scenario.now), session.departure_time))
    for charger, windows in reservations.items():
        windows.sort()
        if any(a[1] > b[0] for a, b in zip(windows, windows[1:])):
            errors.append(f"Fixed plug occupancy overlaps on {charger}")
    return errors


def _taper_errors(scenario, schedule):
    errors = []
    for session in scenario.sessions:
        if session.battery_capacity_kwh is None:
            continue
        delivered = 0
        records = sorted((r for r in schedule.allocations if r.vehicle_id == session.vehicle_id), key=lambda r: r.start_time)
        for record in records:
            delivered += battery_energy(record)
            # Reconstruct terminal SoC independently; maximum power only decreases.
            headroom = session.battery_capacity_kwh * (1 - session.initial_soc) - delivered
            ceiling = session.max_charging_power_kw * max(0, headroom) / (session.battery_capacity_kwh * (1 - session.transition_soc))
            if record.power_kw > ceiling + TOLERANCE:
                errors.append(f"CC/CV taper exceeded for {session.vehicle_id}")
    return errors


def validate_schedule(scenario, schedule, charger_budget=None):
    errors = []
    if schedule.state_version != scenario.state_version:
        errors.append("Schedule was calculated from stale state")
    history = [r for r in schedule.allocations if r.end_time <= scenario.now]
    if Counter(map(signature, history)) != Counter(map(signature, scenario.history)):
        errors.append("Completed charging history changed")
    errors.extend(_allocations_errors(scenario, schedule))
    used = {r.charger_id for r in schedule.allocations} | {s.charger_id for s in scenario.sessions if s.charger_id is not None}
    if charger_budget is not None and len(used) > charger_budget:
        errors.append("Physical charger count exceeded")
    if errors:
        raise InvalidSchedule("; ".join(dict.fromkeys(errors)))
    return True
