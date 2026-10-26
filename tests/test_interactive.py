import json
from fastapi.testclient import TestClient
from backend.app.main import app


def draft(client):
    state = client.get("/api/state").json()
    return {k: state[k] for k in ("sessions", "prices", "station")}


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_atomic_editor_renames_hardware_and_binding_together():
    with TestClient(app) as client:
        body = draft(client)
        body["station"]["chargers"][0]["charger_id"] = "NEW-PORT"
        for s in body["sessions"]:
            if s["charger_id"] == "CH-01":
                s["charger_id"] = "NEW-PORT"
        body["sessions"][0]["energy_required_kwh"] = 16
        body["sessions"][0]["requested_soc"] = .65
        body["prices"][0]["price_eur_per_kwh"] = -.05
        response = client.put("/api/scenario", json=body)
        assert response.status_code == 200, response.text
        assert response.json()["sessions"][0]["energy_required_kwh"] == 16
        result = events(client.post("/api/optimize/stream"))[-1]
        assert result["type"] == "result" and result["workspace"]["optimized"]["validated"]
        assert result["workspace"]["optimized"]["metrics"]["unserved_kwh"] == 0


def test_invalid_draft_does_not_partially_mutate_inputs_or_plan():
    with TestClient(app) as client:
        before = client.post("/api/optimize").json()
        body = draft(client)
        body["prices"].pop(2)
        body["station"]["station_power_limit_kw"] = 5
        assert client.put("/api/scenario", json=body).status_code == 422
        assert client.get("/api/state").json() == before
        body = draft(client)
        body["prices"][1]["timestamp"] = body["prices"][0]["timestamp"]
        assert client.put("/api/scenario", json=body).status_code == 422


def test_stream_contains_real_stages_and_same_result_as_sync():
    with TestClient(app) as client:
        trace = events(client.post("/api/optimize/stream"))
        stages = [e["stage"] for e in trace if e["type"] == "progress"]
        assert stages == ["inputs", "FCFS", "FCFS", "EDF", "EDF", "LLF", "LLF", "energy", "cost", "validation"]
        completed = [e for e in trace if e.get("metrics")]
        assert [e["stage"] for e in completed] == ["FCFS", "EDF", "LLF"]
        assert all(e["metrics"]["unserved_kwh"] == 0 for e in completed)
        assert trace[-1]["workspace"]["comparison"] == client.post("/api/optimize").json()["comparison"]
        stale = events(client.post("/api/optimize/stream", headers={"If-Match": "0"}))
        assert stale[-1]["type"] == "error" and "changed" in stale[-1]["message"]


def test_edit_versions_and_streams_are_browser_scoped():
    with TestClient(app) as a, TestClient(app) as b:
        body = draft(a)
        body["station"]["demand_tariff"]["period"] = "year"
        body["station"]["demand_tariff"]["prior_peaks_kw"] = {"2026": 12}
        assert a.put("/api/scenario", json=body, headers={"If-Match": "0"}).status_code == 409
        assert a.put("/api/scenario", json=body).status_code == 200
        events(a.post("/api/optimize/stream"))
        untouched = b.get("/api/state").json()
        assert untouched["optimized"] is None and untouched["station"]["demand_tariff"]["period"] == "month"
