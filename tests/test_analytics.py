from backend.app.models import StationConfig, VehicleSession
from backend.app.services.analytics_service import compute_analytics
from backend.app.services.csv_validator import validate_sessions_csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_analytics_counts():
    sessions = validate_sessions_csv((ROOT / "data" / "sample_charging_sessions.csv").read_bytes())
    station = StationConfig(station_power_limit_kw=80, charger_count=10)
    stats = compute_analytics(sessions, station)
    assert stats["vehicle_count"] == len(sessions)
    assert stats["total_energy_required_kwh"] > 0
    assert stats["simulated"] is True
