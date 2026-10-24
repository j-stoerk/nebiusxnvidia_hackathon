from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.app.models import DemandTariff, Price, Session
from backend.app.services.evaluation import ConformalNeeds, chronological_split, conformal_quantile, coverage, paired_bootstrap, pinball
from backend.app.services.tariffs import demand_windows
from scripts.evaluate import paired_replay
from scripts.fetch_acn import fetch, import_export


def sessions(days=180):
    start = datetime(2019, 1, 1, 9, tzinfo=timezone.utc)
    return [Session(vehicle_id=str(i), arrival_time=start + timedelta(days=i),
                    departure_time=start + timedelta(days=i, hours=1), energy_required_kwh=1,
                    max_charging_power_kw=2) for i in range(days)]


def test_chronological_conformal_never_uses_holdout_targets():
    train, cal, test = chronological_split(sessions())
    assert max(s.departure_time for s in train) < min(s.arrival_time for s in cal)
    assert max(s.departure_time for s in cal) < min(s.arrival_time for s in test)
    model = ConformalNeeds.fit(train, cal)
    first = model.bounds(test[0])
    assert coverage(model, test)["joint_coverage"] == 1
    for s in test:
        s.energy_required_kwh = 10
        s.departure_time = s.arrival_time + timedelta(minutes=30)
    assert model.bounds(test[0]) == first
    assert coverage(model, test)["joint_coverage"] == 0
    assert coverage(model, test)["energy_pinball_kwh"] > 0


def test_finite_sample_quantile_and_pinball():
    with pytest.raises(ValueError, match="Insufficient"):
        conformal_quantile(list(range(38)), .025)
    assert conformal_quantile(list(range(39)), .025) == 38
    assert pinball(2, 1, .9) == pytest.approx(.9)
    assert pinball(1, 2, .1) == pytest.approx(.9)


def test_paired_block_bootstrap_is_reproducible():
    report = paired_bootstrap([-1] * 28)
    assert report["mean"] == -1 and report["ci95"] == [-1, -1]
    assert paired_bootstrap(list(range(28))) == paired_bootstrap(list(range(28)))
    with pytest.raises(ValueError):
        paired_bootstrap([1] * 13)


def test_berlin_billing_period_uses_local_month_and_year(small_scenario):
    s = small_scenario
    s.start = datetime(2026, 10, 31, 22, 45, tzinfo=timezone.utc)
    s.end = s.start + timedelta(minutes=30)
    assert [key for _, _, key in demand_windows(s)] == ["2026-10", "2026-11"]
    s.station.demand_tariff = DemandTariff(period="year")
    s.start = datetime(2026, 12, 31, 22, 45, tzinfo=timezone.utc)
    s.end = s.start + timedelta(minutes=30)
    assert [key for _, _, key in demand_windows(s)] == ["2026", "2027"]


def test_official_client_adapter_streams_without_pii(tmp_path):
    s = sessions(1)[0]
    class Client:
        def get_sessions_by_time(self, site, start, end, timeseries=False):
            assert not timeseries
            yield {"connectionTime": s.arrival_time, "disconnectTime": s.departure_time,
                   "kWhDelivered": 1, "stationID": "PUBLIC-PORT", "userID": "private-user", "userInputs": [{"secret": "private"}]}
            yield {"connectionTime": s.arrival_time, "disconnectTime": s.departure_time,
                   "kWhDelivered": 0, "stationID": "IDLE-PORT"}
    target = tmp_path / "sessions.csv"
    metadata = fetch(Client(), "caltech", s.arrival_time, s.departure_time, target, 6.6)
    assert metadata["kept"] == 2 and len(metadata["sha256"]) == 64
    assert "private" not in target.read_text() and "userID" not in target.read_text()
    assert "PUBLIC-PORT" in target.read_text() and "IDLE-PORT" in target.read_text()
    assert json.loads(target.with_suffix(".metadata.json").read_text())["sha256"] == metadata["sha256"]
    with pytest.raises(ValueError, match="exists"):
        fetch(Client(), "caltech", s.arrival_time, s.departure_time, target, 6.6)


def test_overnight_replay_preserves_delivered_energy_and_billing_peak(small_scenario):
    s = small_scenario
    start = s.start.replace(hour=23)
    visits = [Session(vehicle_id="night", arrival_time=start, departure_time=start + timedelta(hours=2),
                      energy_required_kwh=1, max_charging_power_kw=2)]
    prices = [Price(timestamp=s.start + timedelta(minutes=15 * i), price_eur_per_kwh=.2) for i in range(192)]
    s.station.demand_tariff = DemandTariff(eur_per_kw=10)
    rows = paired_replay(visits, s.station, prices, 1)
    for name in ("FCFS", "EDF", "LLF", "OR-Tools"):
        selected = [r for r in rows if r["policy"] == name]
        assert sum(r["delivered_kwh"] for r in selected) == pytest.approx(1, abs=1e-5)
        assert sum(r["unserved_kwh"] for r in selected) == pytest.approx(0, abs=1e-5)
        assert sum(r["demand_cost_eur"] for r in selected) == pytest.approx(10 * max(r["peak_power_kw"] for r in selected), abs=1e-5)


def test_web_json_import_needs_no_client_and_rejects_partial_pages(tmp_path):
    raw = {"_meta": {"total": 1}, "_items": [{"connectionTime": "Mon, 25 Mar 2019 16:24:42 GMT",
           "disconnectTime": "Tue, 26 Mar 2019 01:32:12 GMT", "kWhDelivered": 0,
           "stationID": "PORT", "userID": "private"}]}
    target = tmp_path / "web.csv"
    metadata = import_export(json.dumps(raw).encode(), "office001", target, 6.6)
    assert metadata["kept"] == 1 and len(metadata["source_json_sha256"]) == 64
    assert "private" not in target.read_text() and "2019-03-25T16:24:42+00:00" in target.read_text()
    raw["_links"] = {"next": {"href": "page2"}}
    with pytest.raises(ValueError, match="incomplete"):
        import_export(json.dumps(raw).encode(), "office001", tmp_path / "partial.csv", 6.6)
