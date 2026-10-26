import httpx
import pytest
from backend.app.ai.nemotron_client import chat_completion, public_configuration
from backend.app.config import get_settings


def test_key_alone_cannot_make_paid_inference_calls(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key-never-a-real-secret")
    monkeypatch.setenv("NEBIUS_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
    monkeypatch.delenv("CLOUD_INFERENCE_ENABLED", raising=False)
    monkeypatch.delenv("NEMOTRON_BASE_URL", raising=False)
    get_settings.cache_clear()
    attempts = []
    try:
        config = public_configuration()
        assert not config["configured"] and config["mode"] == "local_summary"
        assert "disabled" in config["reason"]
        with httpx.Client(transport=httpx.MockTransport(lambda request: attempts.append(request))) as client:
            with pytest.raises(RuntimeError, match="disabled"):
                chat_completion([], [], client)
        assert not attempts
    finally:
        get_settings.cache_clear()


def test_explicit_cloud_opt_in_can_be_verified_with_a_mock_only(monkeypatch, tmp_path):
    from backend.app.ai import cloud_budget
    monkeypatch.setattr(cloud_budget, "LEDGER", tmp_path / "budget.json")
    monkeypatch.setenv("CLOUD_INFERENCE_ENABLED", "true")
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key-never-a-real-secret")
    monkeypatch.setenv("NEBIUS_MODEL", "nvidia/Nemotron-3_5-Lightning")
    monkeypatch.delenv("NEMOTRON_BASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        def respond(request):
            assert request.url.host == "api.tokenfactory.nebius.com"
            return httpx.Response(200, json={"choices": [{"message": {"content": "Mock only"}}]})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            assert chat_completion([], [], client)["choices"][0]["message"]["content"] == "Mock only"
    finally:
        get_settings.cache_clear()


def test_allowance_is_reserved_and_survives_settings_reload(monkeypatch, tmp_path):
    import json
    from backend.app.ai import cloud_budget
    path = tmp_path / "budget.json"
    monkeypatch.setattr(cloud_budget, "LEDGER", path)
    monkeypatch.setenv("CLOUD_INFERENCE_MAX_REQUESTS", "1")
    get_settings.cache_clear()
    config = {"provider": "nebius", "model": "nvidia/Nemotron-3_5-Lightning"}
    body = {"messages": [{"role": "user", "content": "short test"}], "max_tokens": 128}
    try:
        cloud_budget.reserve(config, body)
        get_settings.cache_clear()
        with pytest.raises(RuntimeError, match="allowance exhausted"):
            cloud_budget.reserve(config, body)
        saved = json.loads(path.read_text())
        assert len(saved["requests"]) == 1 and 0 < saved["reserved_usd"] < .05
        with pytest.raises(RuntimeError, match="verified price"):
            cloud_budget.reserve({**config, "model": "unpriced/model"}, body)
    finally:
        get_settings.cache_clear()
