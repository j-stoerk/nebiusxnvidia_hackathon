"""Independent sweep-line physical checks, not constraints copied from the MIP.

Completed history must match the previously validated immutable delivery ledger.
Future records are checked against current constraints, including event boundaries.
"""

from collections import Counter, defaultdict
import math

from .scenario import available_at, battery_energy

TOLERANCE = 1e-5


class InvalidSchedule(ValueError):
    pass


def signature(record):
    return (record.vehicle_id, record.charger_id, record.start_time, record.end_time,
            round(record.power_kw, 9), record.charging_efficiency)


def validate_schedule(scenario, schedule):
    errors = []
    if schedule.state_version != scenario.state_version:
        errors.append("Schedule was calculated from stale state")
    sessions = {s.vehicle_id: s for s in scenario.sessions}
    chargers = {c.charger_id: c for c in scenario.station.chargers}
    supplied_history = [record for record in schedule.allocations if record.end_time <= scenario.now]
    if Counter(map(signature, supplied_history)) != Counter(map(signature, scenario.history)):
        errors.append("Completed charging history changed")
    energy = defaultdict(float)
    changes = defaultdict(list)
    for index, record in enumerate(schedule.allocations):
        session = sessions.get(record.vehicle_id)
        if session is None:
            errors.append(f"Unknown vehicle at allocation {index}")
            continue
        if not math.isfinite(record.power_kw) or record.power_kw <= 0:
            errors.append(f"Invalid power at allocation {index}")
        if record.end_time <= record.start_time:
            errors.append(f"Invalid duration at allocation {index}")
        if record.start_time < session.arrival_time or record.end_time > session.departure_time:
            errors.append(f"Charging outside availability for {session.vehicle_id}")
        energy[record.vehicle_id] += battery_energy(record)
        if record.end_time <= scenario.now:
            continue
        if record.start_time < scenario.now:
            errors.append("Future allocation overlaps completed history")
        charger = chargers.get(record.charger_id)
        if charger is None:
            errors.append(f"Unknown charger {record.charger_id}")
            continue
        if charger.connector_type != session.connector_type:
            errors.append(f"Incompatible connector for {session.vehicle_id}")
        if record.power_kw > min(session.max_charging_power_kw, charger.max_power_kw) + TOLERANCE:
            errors.append(f"Power rating exceeded for {session.vehicle_id}")
        if abs(record.charging_efficiency - scenario.station.charging_efficiency) > TOLERANCE:
            errors.append("Wrong future charging efficiency")
        boundaries = {record.start_time}
        for event in scenario.events.values():
            boundaries.update(time for time in (event.start_time, event.end_time, event.time)
                              if time is not None and record.start_time < time < record.end_time)
        if any(not available_at(scenario, charger, time) for time in boundaries):
            errors.append(f"Charging on unavailable charger {charger.charger_id}")
        changes[record.start_time].append((1, index, record))
        changes[record.end_time].append((-1, index, record))
    for vehicle, value in energy.items():
        if value > sessions[vehicle].energy_required_kwh + TOLERANCE:
            errors.append(f"Excess energy delivered to {vehicle}")
    active = {}
    for instant in sorted(changes):
        # End before start: half-open intervals allow immediate reassignment.
        for direction, key, record in sorted(changes[instant], key=lambda item: item[0]):
            if direction == -1:
                active.pop(key, None)
            else:
                active[key] = record
        if sum(record.power_kw for record in active.values()) > scenario.station.station_power_limit_kw + TOLERANCE:
            errors.append(f"Station cap exceeded at {instant.isoformat()}")
        if len({record.vehicle_id for record in active.values()}) != len(active):
            errors.append(f"Vehicle uses multiple connectors at {instant.isoformat()}")
        if len({record.charger_id for record in active.values()}) != len(active):
            errors.append(f"Charger serves multiple vehicles at {instant.isoformat()}")
    if errors:
        raise InvalidSchedule("; ".join(dict.fromkeys(errors)))
    return True
