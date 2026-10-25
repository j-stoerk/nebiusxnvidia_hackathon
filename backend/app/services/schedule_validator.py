"""Independent certification of emitted records, never solver variables or labels."""
from collections import Counter, defaultdict
import math

from .physics import available, battery_energy, taper_ceiling


class InvalidSchedule(ValueError):
    pass


def signature(record):
    return (record.vehicle_id, record.charger_id, record.start_time, record.end_time, record.power_kw, record.charging_efficiency)


def validate_schedule(sessions, station, result, outages=(), history=(), now=None, charger_ids=None, power_limit_kw=None):
    errors, energy, used, changes = set(), defaultdict(float), defaultdict(set), defaultdict(float)
    vehicles, ports = {s.vehicle_id: s for s in sessions}, {c.charger_id: c for c in station.chargers}
    records = result.allocations
    limit = station.station_power_limit_kw if power_limit_kw is None else min(power_limit_kw, station.station_power_limit_kw)
    frozen = [r for r in records if now and r.end_time <= now]
    if Counter(map(signature, frozen)) != Counter(map(signature, history)):
        errors.add("Completed delivery history changed")
    for r in records:
        s, c = vehicles.get(r.vehicle_id), ports.get(r.charger_id)
        if not s or not c:
            errors.add("Unknown vehicle/charger")
            continue
        if not math.isfinite(r.power_kw) or r.power_kw <= 0 or r.end_time <= r.start_time:
            errors.add("Invalid allocation power/window")
        if not s.arrival_time <= r.start_time < r.end_time <= s.departure_time:
            errors.add("Charging outside vehicle availability")
        if r.charging_efficiency <= 0 or r.charging_efficiency > 1:
            errors.add("Invalid allocation efficiency")
        energy[s.vehicle_id] += battery_energy(r)
        used[s.vehicle_id].add(c.charger_id)
        if now and r.end_time <= now:
            continue  # Past records were checked when frozen; new settings cannot rewrite them.
        if r.power_kw > min(s.max_charging_power_kw, c.max_power_kw) + 1e-5:
            errors.add("Vehicle/charger power rating exceeded")
        if s.connector_type != c.connector_type or s.charger_id and s.charger_id != c.charger_id:
            errors.add("Connector or fixed binding violated")
        if charger_ids is not None and c.charger_id not in charger_ids:
            errors.add("Candidate uses an excluded physical charger")
        if not available(c, r.start_time, r.end_time, outages):
            errors.add("Charging on an unavailable charger")
        if abs(r.charging_efficiency - station.charging_efficiency) > 1e-8:
            errors.add("Future allocation has wrong efficiency")
        changes[r.start_time] += r.power_kw
        changes[r.end_time] -= r.power_kw
        terminal = sum(battery_energy(a) for a in records if a.vehicle_id == s.vehicle_id and a.end_time <= r.end_time)
        if r.power_kw > taper_ceiling(s, terminal) + 1e-5:
            errors.add("Terminal SoC taper ceiling exceeded")
    current = 0
    for _, change in sorted(changes.items()):
        current += change
        if current > limit + 1e-5:
            errors.add("Site power limit exceeded")
    for i, r in enumerate(records):
        for other in records[:i]:
            if r.start_time < other.end_time and r.end_time > other.start_time:
                if r.charger_id == other.charger_id or r.vehicle_id == other.vehicle_id:
                    errors.add("Simultaneous charger/vehicle allocations")
    for i, s in enumerate(sessions):
        if s.charger_id:
            used[s.vehicle_id].add(s.charger_id)  # Even a zero-energy plugged vehicle occupies its port.
        if station.fixed_connections and len(used[s.vehicle_id]) > 1:
            errors.add("Fixed vehicle switches chargers")
        if energy[s.vehicle_id] > s.energy_required_kwh + 1e-5:
            errors.add("Vehicle overcharged")
        for other in sessions[:i]:
            overlap = max(s.arrival_time, other.arrival_time, now or s.arrival_time) < min(s.departure_time, other.departure_time)
            if station.fixed_connections and overlap and used[s.vehicle_id] & used[other.vehicle_id]:
                errors.add("Overlapping whole-session plug occupancy")
    if errors:
        raise InvalidSchedule("; ".join(sorted(errors)))
    return True
