import json

from backend.app.ai.tools import SimulateEventArgs, execute_tool
from backend.app.services import schedule_service


def test_get_state_tool():
    schedule_service.load_demo_if_empty()
    state = execute_tool("get_state", {}, allow_changes=False)
    assert "analytics" in state
    assert state["station"]["simulated"] is True


def test_optimize_requires_allow_changes():
    blocked = execute_tool("optimize_schedule", {}, allow_changes=False)
    assert "error" in blocked


def test_model_cannot_add_undeclared_tool_arguments():
    result = execute_tool("simulate_event", {"event": {}, "override_permissions": True}, allow_changes=True)
    assert "error" in result
    assert not schedule_service.STATE.events


def test_schedule_tool_provides_checked_energy_and_duration_facts():
    schedule_service.load_demo_if_empty()
    schedule_service.run_optimization()
    state = execute_tool("get_schedule", {"vehicle_id": "VAN-01"}, allow_changes=False)
    assert state["selected_facts"]["battery_energy_delivered_kwh"] == 18
    assert abs(state["selected_facts"]["active_charging_hours"] - 2.25) < 1e-5
    assert state["selected_facts"]["allocation_count"] == len(state["allocations"])


def test_nested_event_json_is_validated_without_bypassing_permissions():
    event = {"event_id": "nested-json", "type": "CHARGER_FAILED", "charger_id": "CH-01",
             "start_time": "2026-10-24T08:00:00Z", "end_time": "2026-10-24T12:00:00Z"}
    assert SimulateEventArgs.model_validate({"event": json.dumps(event)}).event.charger_id == "CH-01"
    blocked = execute_tool("simulate_event", {"event": json.dumps(event)}, allow_changes=False)
    assert "allow_changes is false" in blocked["error"]
    invalid = execute_tool("simulate_event", {"event": '{"type":"invented"}'}, allow_changes=True)
    assert "fields" in invalid
