"""Settlement demand is quarter-hour mean power grouped by the local billing calendar."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from ..utils.datetime_utils import floor_slot, hours


def overlap(start, end, a, b):
    return hours(max(start, a), min(end, b))


def demand_windows(sessions, tariff):
    cursor = floor_slot(min(s.arrival_time for s in sessions), 15)
    end = max(s.departure_time for s in sessions)
    while cursor < end:
        period = cursor.astimezone(ZoneInfo(tariff.timezone)).strftime("%Y-%m" if tariff.period == "month" else "%Y")
        yield cursor, cursor + timedelta(minutes=15), period
        cursor += timedelta(minutes=15)


def prior_peak(tariff, period):
    return tariff.prior_peaks_kw.get(period, tariff.prior_peak_kw)


def demand_cost(sessions, records, tariff):
    peaks = {}
    if sessions:
        for a, b, period in demand_windows(sessions, tariff):
            average = sum(r.power_kw * overlap(a, b, r.start_time, r.end_time) for r in records) / .25
            peaks[period] = max(peaks.get(period, prior_peak(tariff, period)), average)
    return sum(max(0, peak - prior_peak(tariff, k)) for k, peak in peaks.items()) * tariff.eur_per_kw, peaks
