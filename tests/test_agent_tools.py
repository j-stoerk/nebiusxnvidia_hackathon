from backend.app.ai.tools import execute_tool
from backend.app.services import schedule_service


def test_get_state_tool():
    schedule_service.load_demo_if_empty()
    state = execute_tool("get_state", {}, allow_changes=False)
    assert "analytics" in state
    assert state["station"]["simulated"] is True


def test_optimize_requires_allow_changes():
    blocked = execute_tool("optimize_schedule", {}, allow_changes=False)
    assert "error" in blocked
