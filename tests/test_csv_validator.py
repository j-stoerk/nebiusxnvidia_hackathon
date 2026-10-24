from pathlib import Path

import pytest

from backend.app.services.csv_validator import InputError, validate_sessions_csv

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = (ROOT / "data" / "sample_charging_sessions.csv").read_bytes()


def test_valid_sample():
    sessions = validate_sessions_csv(SAMPLE)
    assert len(sessions) >= 1
    assert sessions[0].vehicle_id


def test_missing_column_rejected():
    bad = b"vehicle_id,arrival_time\nEV-1,2019-01-07T06:00:00Z\n"
    with pytest.raises(InputError):
        validate_sessions_csv(bad)
