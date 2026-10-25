"""Cost and energy metrics derived from schedule allocations."""

from collections import defaultdict
from datetime import timedelta

from ..models import Allocation, PricePoint, ScheduleMetrics, StationConfig, VehicleSession
from ..models.schedule import PowerPoint, VehicleMetric
from ..utils.datetime_utils import hours, iter_slots
from .physics import battery_energy
from .tariffs import demand_cost as metered_demand_cost


def price_at(prices: list[PricePoint], moment, adjustments: list[tuple] | None = None) -> float:
    """Lookup EUR/kWh at moment; adjustments are (start, end, add_eur_per_kwh)."""
    if not prices:
        base = 0.20
    else:
        base = prices[0].price_eur_per_kwh
        for point in prices:
            if point.timestamp <= moment:
                base = point.price_eur_per_kwh
            else:
                break
    if adjustments:
        for start, end, add in adjustments:
            if start <= moment < end:
                base += add
    return base


def compute_metrics(
    sessions: list[VehicleSession],
    allocations: list[Allocation],
    station: StationConfig,
    prices: list[PricePoint],
    price_adjustments: list[tuple] | None = None,
) -> ScheduleMetrics:
    efficiency = station.charging_efficiency
    delivered = defaultdict(float)
    energy_cost = 0.0
    changes = defaultdict(float)
    bound_charger = {}

    for record in allocations:
        duration = hours(record.start_time, record.end_time)
        delivered[record.vehicle_id] += battery_energy(record)
        bound_charger.setdefault(record.vehicle_id, record.charger_id)
        cuts = {record.start_time, record.end_time}
        cursor = record.start_time.replace(
            minute=(record.start_time.minute // station.slot_minutes) * station.slot_minutes,
            second=0,
            microsecond=0,
        ) + timedelta(minutes=station.slot_minutes)
        while cursor < record.end_time:
            cuts.add(cursor)
            cursor += timedelta(minutes=station.slot_minutes)
        cuts.update(t for a, b, _ in price_adjustments or [] for t in (a, b) if record.start_time < t < record.end_time)
        ordered = sorted(cuts)
        for a, b in zip(ordered, ordered[1:]):
            energy_cost += record.power_kw * hours(a, b) * price_at(prices, a, price_adjustments)
        changes[record.start_time] += record.power_kw
        changes[record.end_time] -= record.power_kw

    power = peak = 0.0
    for instant in sorted(changes):
        power += changes[instant]
        peak = max(peak, power)

    tariff = station.demand_tariff
    prior = tariff.prior_peak_kw
    demand_cost, billing_peaks = metered_demand_cost(sessions, allocations, tariff)
    total_cost = energy_cost + demand_cost

    vehicles = []
    for session in sorted(sessions, key=lambda s: (s.departure_time, s.vehicle_id)):
        got = delivered[session.vehicle_id]
        shortfall = max(0.0, session.energy_required_kwh - got)
        final_soc = None
        if session.battery_capacity_kwh is not None and session.initial_soc is not None:
            final_soc = min(1.0, session.initial_soc + got / session.battery_capacity_kwh)
        vehicles.append(
            VehicleMetric(
                vehicle_id=session.vehicle_id,
                required_kwh=session.energy_required_kwh,
                delivered_kwh=round(got, 4),
                shortfall_kwh=round(shortfall, 4),
                target_met=shortfall <= 1e-5,
                arrival_time=session.arrival_time,
                departure_time=session.departure_time,
                battery_capacity_kwh=session.battery_capacity_kwh,
                initial_soc=session.initial_soc,
                requested_soc=session.requested_soc,
                final_soc=round(final_soc, 4) if final_soc is not None else None,
                charger_id=session.charger_id or bound_charger.get(session.vehicle_id),
            )
        )

    if sessions:
        start = min(s.arrival_time for s in sessions)
        end = max(s.departure_time for s in sessions)
    else:
        start = end = None

    series = []
    if start and end:
        for a, b in iter_slots(start, end, station.slot_minutes):
            energy = sum(
                rec.power_kw * max(0.0, hours(max(a, rec.start_time), min(b, rec.end_time)))
                for rec in allocations
                if rec.start_time < b and rec.end_time > a
            )
            series.append(
                PowerPoint(
                    timestamp=a,
                    power_kw=round(energy / hours(a, b), 4) if hours(a, b) else 0.0,
                    price_eur_per_kwh=price_at(prices, a, price_adjustments),
                )
            )

    met = sum(1 for v in vehicles if v.target_met)
    return ScheduleMetrics(
        cost_eur=round(total_cost, 4),
        energy_cost_eur=round(energy_cost, 4),
        demand_cost_eur=round(demand_cost, 4),
        peak_power_kw=round(peak, 4),
        prior_peak_kw=prior,
        demand_tariff_eur_per_kw=tariff.eur_per_kw,
        charging_efficiency=efficiency,
        delivered_kwh=round(sum(delivered.values()), 4),
        unserved_kwh=round(sum(v.shortfall_kwh for v in vehicles), 4),
        target_success_percent=round(100.0 * met / len(vehicles), 2) if vehicles else 0.0,
        vehicles=vehicles,
        power_series=series,
        billing_peaks_kw=billing_peaks,
    )
