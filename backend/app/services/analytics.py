"""Metrics independently reconstructed from allocation records."""

from collections import defaultdict
from datetime import timedelta

from .scenario import battery_energy, hours, price_at


def metrics(scenario, schedule):
    delivered, changes, costs = defaultdict(float), defaultdict(float), 0.0
    for record in schedule.allocations:
        delivered[record.vehicle_id] += battery_energy(record)
        # Split at prices and event boundaries so historical/partial records price correctly.
        cuts = {record.start_time, record.end_time}
        cursor = record.start_time.replace(minute=record.start_time.minute // 15 * 15, second=0, microsecond=0) + timedelta(minutes=15)
        while cursor < record.end_time:
            cuts.add(cursor)
            cursor += timedelta(minutes=15)
        for event in scenario.events.values():
            if event.type == "PRICE_CHANGED":
                cuts.update(time for time in (event.start_time, event.end_time) if record.start_time < time < record.end_time)
        cuts = sorted(cuts)
        costs += sum(record.power_kw * hours(a, b) * price_at(scenario, a) for a, b in zip(cuts, cuts[1:]))
        changes[record.start_time] += record.power_kw
        changes[record.end_time] -= record.power_kw
    power, peak = 0, 0
    for instant in sorted(changes):
        power += changes[instant]
        peak = max(peak, power)
    vehicles = []
    for session in sorted(scenario.sessions, key=lambda s: (s.departure_time, s.vehicle_id)):
        shortfall = max(0, session.energy_required_kwh - delivered[session.vehicle_id])
        vehicles.append({"vehicle_id": session.vehicle_id, "required_kwh": session.energy_required_kwh,
                         "delivered_kwh": delivered[session.vehicle_id], "shortfall_kwh": shortfall,
                         "target_met": shortfall <= 1e-5, "departure_time": session.departure_time,
                         "arrival_time": session.arrival_time})
    series = []
    cursor = scenario.start
    while cursor < scenario.end:
        end = min(cursor + timedelta(minutes=15), scenario.end)
        energy = sum(record.power_kw * max(0, hours(max(cursor, record.start_time), min(end, record.end_time)))
                     for record in schedule.allocations if record.start_time < end and record.end_time > cursor)
        series.append({"timestamp": cursor, "power_kw": energy / hours(cursor, end), "price_eur_per_kwh": price_at(scenario, cursor)})
        cursor = end
    return {"cost_eur": costs, "peak_power_kw": peak, "delivered_kwh": sum(delivered.values()),
            "unserved_kwh": sum(v["shortfall_kwh"] for v in vehicles),
            "target_success_percent": 100 * sum(v["target_met"] for v in vehicles) / len(vehicles),
            "vehicles": vehicles, "power_series": series}
