from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app

client = TestClient(app)
DEMO = Path(__file__).resolve().parents[1] / "data" / "demo"


def test_full_demo_upload_optimize_event_replay_and_versions(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    response = client.post("/api/workspaces", json={"demo": "normal"})
    assert response.status_code == 201
    state = response.json()
    prefix = f"/api/workspaces/{state['workspace_id']}"
    assert state["analytics"]["vehicles"] == 50
    assert state["baseline"]["validated"] and state["optimized"] is None
    state = client.post(prefix + "/optimize", json={"expected_version": 1}).json()
    assert state["optimized"]["validated"] and not state["stale"]
    assert state["comparison"]["equal_delivered_energy"]
    body = {"expected_version": 1, "event": {"event_id": "api-outage", "type": "CHARGER_FAILED", "charger_id": "CH-01",
                                            "start_time": "2019-01-07T09:00:00Z", "end_time": "2019-01-07T12:00:00Z"}}
    applied = client.post(prefix + "/events", json=body)
    assert applied.status_code == 200
    assert applied.json()["state_version"] == 2
    assert applied.json()["event_result"]["status"] == "replanned"
    duplicate = client.post(prefix + "/events", json=body)
    assert duplicate.json()["event_result"]["status"] == "duplicate_ignored"
    assert duplicate.json()["state_version"] == 2
    assert client.post(prefix + "/optimize", json={"expected_version": 1}).status_code == 409
    bad = client.post(prefix + "/upload", data={"expected_version": "2"}, files={"sessions": ("bad.csv", b"bad\n1", "text/csv")})
    assert bad.status_code == 422
    assert client.get(prefix).json()["state_version"] == 2
    uploaded = client.post(prefix + "/upload", data={"expected_version": "2"}, files={
        "sessions": ("sessions.csv", (DEMO / "sample_charging_sessions.csv").read_bytes(), "text/csv"),
        "prices": ("", b"", "application/octet-stream"),
    })
    assert uploaded.status_code == 200
    state = uploaded.json()
    assert state["state_version"] == 3 and not state["events"]
    assert state["optimized"]["validated"]
    offline = client.post(prefix + "/chat", json={"expected_version": 3, "message": "Why this schedule?"})
    assert offline.json()["reply"]["mode"] == "unavailable"
    assert offline.json()["reply"]["tool_calls"] == []


def test_workspace_isolation_and_expiry():
    one = client.post("/api/workspaces", json={}).json()
    two = client.post("/api/workspaces", json={"demo": "stress"}).json()
    assert one["workspace_id"] != two["workspace_id"]
    assert client.get(f"/api/workspaces/{one['workspace_id']}").json()["analytics"]["vehicles"] == 50
    assert two["analytics"]["vehicles"] == 100
    assert client.get("/api/workspaces/nonexistent").status_code == 404


def test_settings_and_price_csv_validation():
    state = client.post("/api/workspaces", json={}).json()
    prefix = f"/api/workspaces/{state['workspace_id']}"
    station = state["station"]
    station["station_power_limit_kw"] = 50
    result = client.put(prefix + "/station", json={"expected_version": 1, "station": station})
    assert result.status_code == 200
    assert result.json()["optimized"]["metrics"]["peak_power_kw"] <= 50 + 1e-5
    bad = client.post(prefix + "/upload", data={"expected_version": "2"}, files={
        "sessions": ("sessions.csv", (DEMO / "sample_charging_sessions.csv").read_bytes()),
        "prices": ("prices.csv", b"timestamp,price_eur_per_kwh\n2019-01-07T06:00Z,0.2\n"),
    })
    assert bad.status_code == 422
    assert "Missing" in str(bad.json())


def test_large_upload_and_downloads():
    state = client.post("/api/workspaces", json={}).json()
    response = client.post(f"/api/workspaces/{state['workspace_id']}/upload", data={"expected_version": "1"}, files={"sessions": ("large.csv", b"x" * (2 * 1024 * 1024 + 1))})
    assert response.status_code == 413
    assert client.get("/api/demo/sessions").content == (DEMO / "sample_charging_sessions.csv").read_bytes()
    assert client.get("/api/health").json()["scheduler"] == "OR-Tools SCIP"
    scenarios = client.get("/api/demo/scenarios")
    assert scenarios.status_code == 200 and "price_spike" in scenarios.json()["scenarios"]
