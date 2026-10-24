import json

import httpx
import pytest

from backend.app.ai.agent import chat, execute_tool
from backend.app.services.schedule_service import replan


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("NEBIUS_MODEL", "nvidia/Nemotron-test")
    monkeypatch.setenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")


def test_real_protocol_tool_loop_with_mocked_provider(small_scenario, configured):
    s = small_scenario
    assert replan(s)
    calls = []
    def provider(request):
        body = json.loads(request.content)
        calls.append(body)
        assert request.url.host == "api.tokenfactory.nebius.com"
        assert body["model"] == "nvidia/Nemotron-test"
        if len(calls) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "state-1", "type": "function", "function": {"name": "get_state", "arguments": "{}"}}]}}]})
        tool = body["messages"][-1]
        assert tool["role"] == "tool" and tool["tool_call_id"] == "state-1"
        measured = json.loads(tool["content"])
        assert measured["metrics"]["unserved_kwh"] < 1e-5
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "The validated plan meets the energy target."}}]})
    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        reply = chat(s, "Explain the plan", False, 1, client=client)
    assert reply["mode"] == "nemotron" and len(reply["tool_calls"]) == 1
    assert len(calls) == 2
    assert "test-only-not-a-real-key" not in json.dumps(reply)


def test_read_only_chat_cannot_mutate_and_unknown_tools_are_rejected(small_scenario):
    s = small_scenario
    with pytest.raises(ValueError, match="not enabled"):
        execute_tool(s, "optimize_schedule", {"expected_version": 1}, False, 1)
    with pytest.raises(ValueError, match="not allowed"):
        execute_tool(s, "run_shell", {"command": "anything"}, True, 1)
    with pytest.raises(ValueError):
        execute_tool(s, "get_state", {"unexpected": "argument"}, False, 1)
    assert s.state_version == 1 and s.schedule_version == 0


def test_allowed_simulation_tool_is_typed_and_versioned(small_scenario):
    s = small_scenario
    result = execute_tool(s, "simulate_event", {"expected_version": 1, "event": {"event_id": "agent-price", "type": "PRICE_CHANGED",
                           "start_time": s.start.isoformat(), "end_time": s.end.isoformat(), "add_eur_per_kwh": .2}}, True, 1)
    assert result["status"] == "replanned" and result["state_version"] == 2
    assert s.optimized.validated


def test_provider_error_is_visible_and_never_a_fake_answer(small_scenario, configured):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401, text="private provider details"))) as client:
        reply = chat(small_scenario, "hello", False, 1, client=client)
    assert reply["mode"] == "error"
    assert "HTTP 401" in reply["message"]
    assert "private provider details" not in str(reply)


def test_answer_is_rejected_if_simulation_changes_during_inference(small_scenario, configured):
    def provider(request):
        small_scenario.state_version += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "An answer about stale state"}}]})
    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        reply = chat(small_scenario, "hello", False, 1, client=client)
    assert reply["mode"] == "error" and "changed" in reply["message"]


def test_no_credential_or_non_nvidia_model_does_not_call_provider(small_scenario, monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    assert chat(small_scenario, "hello", False, 1)["mode"] == "unavailable"
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("NEBIUS_MODEL", "another/model")
    assert chat(small_scenario, "hello", False, 1)["mode"] == "unavailable"
