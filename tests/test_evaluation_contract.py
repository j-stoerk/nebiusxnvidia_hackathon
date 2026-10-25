from datetime import datetime, timedelta, timezone

import pytest

from backend.app.models import VehicleSession, StationConfig, PricePoint, DemandTariff
from backend.app.services.evaluation import conformal_quantile, paired_bootstrap
from scripts.evaluate import paired_replay


def test_overnight_replay_does_not_reset_or_double_deliver_energy():
    start = datetime(2026, 10, 24, 23, tzinfo=timezone.utc)
    session = VehicleSession(vehicle_id="overnight", arrival_time=start, departure_time=start + timedelta(hours=2),
                             energy_required_kwh=1, max_charging_power_kw=1)
    station = StationConfig(station_power_limit_kw=1, charger_count=1, charger_max_power_kw=1,
                            demand_tariff=DemandTariff(eur_per_kw=0))
    prices = [PricePoint(timestamp=start + timedelta(minutes=15 * q), price_eur_per_kwh=.2) for q in range(8)]
    rows = paired_replay([session], station, prices, seconds=1)
    for name in ("FCFS", "EDF", "LLF", "OR-Tools"):
        assert sum(r["delivered_kwh"] for r in rows if r["policy"] == name) == pytest.approx(1, abs=1e-5)
        assert sum(r["unserved_kwh"] for r in rows if r["policy"] == name) < 1e-5


def test_finite_sample_calibration_and_paired_block_bootstrap():
    with pytest.raises(ValueError, match="Insufficient"):
        conformal_quantile([1, 2], .025)
    assert conformal_quantile([0] * 39, .025) == 0
    report = paired_bootstrap([2] * 14, repetitions=100, block_days=7)
    assert report["ci95"] == [2, 2] and report["days"] == 14
