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


def test_explicit_cloud_opt_in_can_be_verified_with_a_mock_only(monkeypatch):
    monkeypatch.setenv("CLOUD_INFERENCE_ENABLED", "true")
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key-never-a-real-secret")
    monkeypatch.setenv("NEBIUS_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
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
