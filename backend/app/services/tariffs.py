"""Meter demand is a 15-minute energy average, not instantaneous dispatch power."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from .scenario import hours


def demand_windows(scenario):
    cursor, tariff = scenario.start, scenario.station.demand_tariff
    zone = ZoneInfo(tariff.timezone)
    while cursor < scenario.end:
        key = cursor.astimezone(zone).strftime("%Y-%m" if tariff.period == "month" else "%Y")
        yield cursor, cursor + timedelta(minutes=15), key
        cursor += timedelta(minutes=15)


def overlap_hours(start, end, a, b):
    return max(0, hours(max(start, a), min(end, b)))


def demand_cost(scenario, records):
    tariff, peaks = scenario.station.demand_tariff, {}
    for start, end, period in demand_windows(scenario):
        average = sum(r.power_kw * overlap_hours(start, end, r.start_time, r.end_time) for r in records) / .25
        peaks[period] = max(peaks.get(period, tariff.prior_peaks_kw.get(period, 0)), average)
    increment = sum(max(0, peak - tariff.prior_peaks_kw.get(period, 0)) for period, peak in peaks.items())
    return increment * tariff.eur_per_kw, peaks
