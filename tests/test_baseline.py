from pathlib import Path

from backend.app.models import StationConfig
from backend.app.services.baseline_scheduler import build_baseline
from backend.app.services.csv_validator import validate_prices_csv, validate_sessions_csv

ROOT = Path(__file__).resolve().parents[1]


def test_fcfs_baseline_runs():
    sessions = validate_sessions_csv((ROOT / "data/demo" / "sample_charging_sessions.csv").read_bytes())[:8]
    prices = validate_prices_csv((ROOT / "data/demo" / "synthetic_prices_15min.csv").read_bytes())
    station = StationConfig(station_power_limit_kw=80, charger_count=6)
    result = build_baseline(sessions, station, prices)
    assert result.kind == "baseline"
    assert result.solver_status == "FCFS"
    assert result.metrics.delivered_kwh >= 0
