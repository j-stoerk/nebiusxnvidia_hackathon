from pathlib import Path

from backend.app.models import StationConfig
from backend.app.services.csv_validator import validate_prices_csv, validate_sessions_csv
from backend.app.services.optimizer import optimize_schedule

ROOT = Path(__file__).resolve().parents[1]


def test_ortools_optimizer_runs():
    sessions = validate_sessions_csv((ROOT / "data/demo" / "sample_charging_sessions.csv").read_bytes())[:6]
    prices = validate_prices_csv((ROOT / "data/demo" / "synthetic_prices_15min.csv").read_bytes())
    station = StationConfig(station_power_limit_kw=80, charger_count=5)
    result = optimize_schedule(sessions, station, prices, time_limit_seconds=5)
    assert result.kind == "optimized"
    assert "OR-Tools" in result.solver_status
    assert result.metrics.cost_eur >= 0
