"""Conservative terminal-SoC CC/CV envelope; missing telemetry keeps constant power.

This is a scheduling approximation, not a calibrated battery chemistry model.
"""
import math
from datetime import timedelta

from ..utils.datetime_utils import floor_slot, ceil_slot


def taper_ceiling(session, delivered_kwh):
    if session.battery_capacity_kwh is None:
        return session.max_charging_power_kw
    scale = session.battery_capacity_kwh * (1 - session.transition_soc)
    headroom = session.battery_capacity_kwh * (1 - session.initial_soc) - delivered_kwh
    return min(session.max_charging_power_kw, session.max_charging_power_kw * max(0, headroom) / scale)


def sustainable_power(session, delivered_kwh, duration, efficiency):
    if session.battery_capacity_kwh is None:
        return session.max_charging_power_kw
    scale = session.battery_capacity_kwh * (1 - session.transition_soc)
    headroom = session.battery_capacity_kwh * (1 - session.initial_soc) - delivered_kwh
    return max(0, min(session.max_charging_power_kw, session.max_charging_power_kw * headroom /
                      (scale + session.max_charging_power_kw * duration * efficiency)))


def minimum_hours(session, delivered, remaining, rate, efficiency):
    if remaining <= 0:
        return 0
    if rate <= 0:
        return math.inf
    if session.battery_capacity_kwh is None:
        return remaining / (rate * efficiency)
    headroom = session.battery_capacity_kwh * (1 - session.initial_soc) - delivered
    scale = session.battery_capacity_kwh * (1 - session.transition_soc)
    flat = min(remaining, max(0, headroom - scale * rate / session.max_charging_power_kw))
    if remaining - flat <= 1e-10:
        return flat / (rate * efficiency)
    if headroom - remaining <= 0:
        return math.inf
    return flat / (rate * efficiency) + scale / (session.max_charging_power_kw * efficiency) * math.log((headroom - flat) / (headroom - remaining))


def planning_slots(sessions, outages=(), adjustments=(), now=None):
    start, end = min(s.arrival_time for s in sessions), max(s.departure_time for s in sessions)
    start = max(start, now) if now else start
    cuts = {start, end, *[s.arrival_time for s in sessions], *[s.departure_time for s in sessions]}
    cuts.update(t for _, a, b in outages for t in (a, b))
    cuts.update(t for a, b, _ in adjustments for t in (a, b))
    cursor = floor_slot(start, 15)
    while cursor < ceil_slot(end, 15):
        cuts.add(cursor)
        cursor += timedelta(minutes=15)
    ordered = sorted(c for c in cuts if start <= c <= end)
    return list(zip(ordered, ordered[1:]))


def available(charger, start, end, outages):
    return charger.available and not any(cid == charger.charger_id and a < end and b > start for cid, a, b in outages)


def battery_energy(record):
    return record.power_kw * (record.end_time - record.start_time).total_seconds() / 3600 * record.charging_efficiency
