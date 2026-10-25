"""Counterexamples found in 2eefaa2; verify the fixes through independent checks."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from backend.app.main import app
from backend.app.models import Allocation, Charger, DemandTariff, PricePoint, StationConfig, VehicleSession, SimulationEvent
from backend.app.services.csv_validator import InputError
from backend.app.services.cost_calculator import compute_metrics
from backend.app.services.optimizer import optimize_schedule
from backend.app.services.schedule_validator import InvalidSchedule, validate_schedule
from backend.app.services.simulation_service import apply_event

START = datetime(2026, 10, 25, 6, tzinfo=timezone.utc)


def inputs(count=1, **kwargs):
    sessions = [VehicleSession(vehicle_id=f"V{i}", arrival_time=START, departure_time=START + timedelta(hours=1),
                energy_required_kwh=1, max_charging_power_kw=2) for i in range(count)]
    station = StationConfig(station_power_limit_kw=22, charger_count=1, charger_max_power_kw=2,
                            demand_tariff=DemandTariff(eur_per_kw=0), **kwargs)
    prices = [PricePoint(timestamp=START + timedelta(minutes=15 * q), price_eur_per_kwh=.2) for q in range(4)]
    return sessions, station, prices


def test_idle_fixed_plug_cannot_be_reused_before_departure():
    sessions, station, prices = inputs(2)
    result = optimize_schedule(sessions, station, prices)
    assert result.validated and result.shortfall_optimal
    assert result.metrics.unserved_kwh == pytest.approx(1, abs=1e-5)
    assert len({r.vehicle_id for r in result.allocations}) == 1


def test_duplicate_explicit_occupancy_is_rejected():
    sessions, station, prices = inputs(2)
    for s in sessions:
        s.charger_id = "CH-01"
    with pytest.raises(InputError, match="Overlapping"):
        optimize_schedule(sessions, station, prices)


def test_heterogeneous_bound_port_limits_actual_output():
    sessions, station, prices = inputs()
    sessions[0].energy_required_kwh, sessions[0].max_charging_power_kw, sessions[0].charger_id = 6, 11, "CH-01"
    station.chargers = [Charger(charger_id="CH-01", max_power_kw=1), Charger(charger_id="CH-02", max_power_kw=11)]
    result = optimize_schedule(sessions, station, prices)
    assert result.metrics.unserved_kwh == pytest.approx(5, abs=1e-5)
    assert all(r.charger_id == "CH-01" and r.power_kw <= 1 for r in result.allocations)


def test_partial_vehicle_window_is_not_discarded():
    sessions, station, prices = inputs()
    sessions[0].arrival_time, sessions[0].departure_time = START + timedelta(minutes=7), START + timedelta(minutes=22)
    sessions[0].energy_required_kwh = .5
    result = optimize_schedule(sessions, station, prices)
    assert result.metrics.unserved_kwh < 1e-5
    assert min(r.start_time for r in result.allocations) == sessions[0].arrival_time


def test_outage_inside_a_grid_slot_is_enforced():
    sessions, station, prices = inputs()
    outage = ("CH-01", START + timedelta(minutes=7), START + timedelta(minutes=22))
    result = optimize_schedule(sessions, station, prices, [outage])
    assert result.validated and result.metrics.unserved_kwh < 1e-5
    assert not any(r.start_time < outage[2] and r.end_time > outage[1] for r in result.allocations)


def test_high_soc_enforces_declining_power():
    sessions, station, prices = inputs()
    sessions[0] = VehicleSession(**{**sessions[0].model_dump(), "energy_required_kwh": 1.6, "max_charging_power_kw": 11,
                                   "battery_capacity_kwh": 40, "initial_soc": .95})
    station.chargers[0].max_power_kw = 11
    result = optimize_schedule(sessions, station, prices)
    assert result.validated and result.metrics.unserved_kwh > .05
    assert all(r.power_kw < 2.75 for r in result.allocations)


def test_independent_validator_rejects_tampering():
    sessions, station, prices = inputs()
    result = optimize_schedule(sessions, station, prices)
    result.allocations[0].power_kw = 12
    with pytest.raises(InvalidSchedule, match="rating|limit"):
        validate_schedule(sessions, station, result)


def test_demand_uses_quarter_hour_average():
    sessions, station, prices = inputs()
    station.demand_tariff.eur_per_kw = 10
    record = Allocation(vehicle_id="V0", charger_id="CH-01", start_time=START, end_time=START + timedelta(minutes=6), power_kw=10)
    result = compute_metrics(sessions, [record], station, prices)
    assert result.demand_cost_eur == 40  # 10 kW * 6/15 minutes, not the instantaneous 10 kW.


def test_billing_months_are_separate():
    sessions, station, _ = inputs()
    sessions[0].arrival_time = datetime(2026, 1, 31, 22, tzinfo=timezone.utc)
    sessions[0].departure_time = datetime(2026, 2, 1, 0, 15, tzinfo=timezone.utc)
    station.demand_tariff.eur_per_kw = 10
    records = [Allocation(vehicle_id="V0", charger_id="CH-01", start_time=t, end_time=t + timedelta(minutes=15), power_kw=1)
               for t in (sessions[0].arrival_time, sessions[0].departure_time - timedelta(minutes=15))]
    prices = [PricePoint(timestamp=sessions[0].arrival_time + timedelta(minutes=15 * q), price_eur_per_kwh=0) for q in range(9)]
    result = compute_metrics(sessions, records, station, prices)
    assert result.demand_cost_eur == 20
    assert set(result.billing_peaks_kw) == {"2026-01", "2026-02"}


def test_recovery_does_not_enable_an_administratively_disabled_port():
    _, station, _ = inputs()
    station.chargers[0].available = False
    apply_event(station, [], SimulationEvent(event_id="r", type="CHARGER_RECOVERED", charger_id="CH-01", time=START))
    assert not station.chargers[0].available


def test_inconsistent_soc_goal_is_rejected():
    sessions, _, _ = inputs()
    with pytest.raises(ValidationError, match="conflicts"):
        VehicleSession(**{**sessions[0].model_dump(), "battery_capacity_kwh": 40, "initial_soc": .25, "requested_soc": .8})


def test_keyless_demo_downloads_comparisons_and_browser_isolation():
    with TestClient(app) as a, TestClient(app) as b:
        assert a.get("/api/sample/sessions").status_code == 200
        assert a.get("/api/sample/prices").status_code == 200
        result = a.post("/api/optimize").json()
        assert len(result["sessions"]) == 4 and result["optimized"]["validated"]
        assert set(result["references"]) == {"EDF", "LLF"}
        assert result["optimized"]["metrics"]["unserved_kwh"] < 1e-5
        assert b.get("/api/state").json()["optimized"] is None
        reply = a.post("/api/chat", json={"message": "Explain the plan"}).json()["reply"]
        assert reply["mode"] == "local_summary" and reply["model"] is None
        assert "no AI model call" in reply["message"]
        assert a.post("/api/optimize", headers={"If-Match": "0"}).status_code == 409


def test_early_outage_does_not_lose_bound_vehicle_energy():
    with TestClient(app) as client:
        client.post("/api/optimize")
        event = {"event_id": "early", "type": "CHARGER_FAILED", "charger_id": "CH-01",
                 "start_time": "2026-10-24T08:00:00Z", "end_time": "2026-10-24T12:00:00Z"}
        result = client.post("/api/events", json={"event": event}).json()
        assert result["optimized"]["validated"] and result["optimized"]["metrics"]["unserved_kwh"] < 1e-5
        assert result["optimized"]["metrics"]["peak_power_kw"] == pytest.approx(10, abs=1e-4)
        replay = client.post("/api/events", json={"event": event}, headers={"If-Match": "0"})
        assert replay.status_code == 200 and not replay.json()["event_result"]["applied"]
        changed = client.post("/api/events", json={"event": {**event, "end_time": "2026-10-24T13:00:00Z"}})
        assert changed.status_code == 409


def test_advance_preserves_delivered_energy_and_efficiency():
    with TestClient(app) as client:
        old = client.post("/api/optimize").json()
        moment = "2026-10-24T07:00:00Z"
        advanced = client.post("/api/advance", json={"time": moment})
        assert advanced.status_code == 200
        history = [r for r in advanced.json()["optimized"]["allocations"] if r["end_time"] <= moment]
        config = {**old["station"], "charging_efficiency": .8}
        assert client.put("/api/station", json={"station": config}).status_code == 200
        result = client.post("/api/optimize").json()
        assert [r for r in result["optimized"]["allocations"] if r["end_time"] <= moment] == history
        assert all(r["charging_efficiency"] == .9 for r in history)


def test_capacity_proof_uses_actual_hardware_and_checks_smaller_counts():
    with TestClient(app) as client:
        result = client.post("/api/capacity", json={"counts": [1, 2]}).json()["capacity_study"]
        assert result["minimum_proven"] and result["recommendation"]["validated"]
        assert result["recommendation"]["charger_count"] == 2
        assert result["recommendation"]["station_power_limit_kw"] == pytest.approx(80 / 9, abs=1e-4)
        assert result["candidates"][0]["outcome"] == "infeasible"


def test_self_hosted_nemotron_needs_no_api_token(monkeypatch):
    import httpx
    from backend.app.ai import nemotron_client
    from backend.app.config import get_settings
    monkeypatch.setenv("NEMOTRON_BASE_URL", "http://127.0.0.1:8001/v1")
    monkeypatch.setenv("NEMOTRON_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16")
    get_settings.cache_clear()
    def respond(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": "test"}}]})
    try:
        assert nemotron_client.public_configuration()["provider"] == "self-hosted"
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            nemotron_client.chat_completion([], [], client)
    finally:
        get_settings.cache_clear()


def test_self_hosted_url_cannot_target_an_arbitrary_service(monkeypatch):
    from backend.app.ai.nemotron_client import public_configuration
    from backend.app.config import get_settings
    monkeypatch.setenv("NEMOTRON_BASE_URL", "http://169.254.169.254/v1")
    monkeypatch.setenv("NEMOTRON_MODEL", "nvidia/Nemotron")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        assert not public_configuration()["configured"]
    finally:
        get_settings.cache_clear()


def test_changed_events_invalidate_capacity_proof_and_reset_versions_increase():
    with TestClient(app) as client:
        before = client.post("/api/capacity", json={"counts": [1, 2]}).json()
        assert before["capacity_study"]["minimum_proven"]
        event = {"event_id": "invalidate", "type": "CHARGER_FAILED", "charger_id": "CH-01",
                 "start_time": "2026-10-24T08:00:00Z", "end_time": "2026-10-24T12:00:00Z"}
        changed = client.post("/api/events", json={"event": event}).json()
        assert changed["capacity_study"] is None
        reset = client.post("/api/reset").json()
        assert reset["state_version"] > changed["state_version"]
