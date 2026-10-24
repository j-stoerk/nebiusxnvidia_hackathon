"""Dashboard analytics from uploaded sessions and station settings."""

from ..models import PricePoint, StationConfig, VehicleSession
from ..utils.datetime_utils import hours


def compute_analytics(
    sessions: list[VehicleSession],
    station: StationConfig,
    prices: list[PricePoint] | None = None,
) -> dict:
    if not sessions:
        return {
            "vehicle_count": 0,
            "session_count": 0,
            "total_energy_required_kwh": 0.0,
            "average_energy_kwh": 0.0,
            "earliest_arrival": None,
            "latest_departure": None,
            "station_power_limit_kw": station.station_power_limit_kw,
            "available_chargers": sum(1 for c in station.chargers if c.available),
            "total_chargers": len(station.chargers),
            "slot_minutes": station.slot_minutes,
            "price_points": len(prices or []),
            "charging_efficiency": station.charging_efficiency,
            "fixed_connections": station.fixed_connections,
            "demand_tariff_eur_per_kw": station.demand_tariff.eur_per_kw,
            "prior_peak_kw": station.demand_tariff.prior_peak_kw,
            "sessions_with_soc": 0,
            "simulated": True,
        }

    total_energy = sum(s.energy_required_kwh for s in sessions)
    with_soc = sum(1 for s in sessions if s.battery_capacity_kwh is not None)
    return {
        "vehicle_count": len(sessions),
        "session_count": len(sessions),
        "total_energy_required_kwh": round(total_energy, 4),
        "average_energy_kwh": round(total_energy / len(sessions), 4),
        "earliest_arrival": min(s.arrival_time for s in sessions),
        "latest_departure": max(s.departure_time for s in sessions),
        "max_dwell_hours": round(
            max(hours(s.arrival_time, s.departure_time) for s in sessions), 2
        ),
        "station_power_limit_kw": station.station_power_limit_kw,
        "available_chargers": sum(1 for c in station.chargers if c.available),
        "total_chargers": len(station.chargers),
        "slot_minutes": station.slot_minutes,
        "price_points": len(prices or []),
        "charging_efficiency": station.charging_efficiency,
        "fixed_connections": station.fixed_connections,
        "demand_tariff_eur_per_kw": station.demand_tariff.eur_per_kw,
        "prior_peak_kw": station.demand_tariff.prior_peak_kw,
        "sessions_with_soc": with_soc,
        "simulated": True,
    }
