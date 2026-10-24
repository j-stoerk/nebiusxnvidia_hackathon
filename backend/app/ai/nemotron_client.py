"""HTTP client for NVIDIA Nemotron via Hugging Face Inference Providers (or Nebius)."""

from urllib.parse import urlparse

import httpx

from ..config import get_settings


def _is_nemotron(model: str) -> bool:
    m = (model or "").lower().split(":", 1)[0]
    return m.startswith("nvidia/") and "nemotron" in m


def _hf_request_model(model: str, provider: str) -> str:
    """Append :provider so HF routes to a live Inference Provider (e.g. featherless-ai)."""
    base = (model or "").strip()
    if not base:
        return base
    if ":" in base:
        return base
    provider = (provider or "").strip()
    if not provider or provider in {"auto", "none"}:
        return base
    return f"{base}:{provider}"


def agent_configuration() -> dict:
    """Prefer Hugging Face when HF_TOKEN is set; otherwise fall back to Nebius."""
    settings = get_settings()

    if settings.hf_token and _is_nemotron(settings.hf_model):
        host = urlparse(settings.hf_base_url)
        valid_host = (
            host.scheme == "https"
            and (host.hostname or "") in {"router.huggingface.co", "api-inference.huggingface.co"}
            and host.username is None
        )
        if valid_host:
            display_model = settings.hf_model.split(":", 1)[0]
            return {
                "configured": True,
                "provider": "huggingface",
                "hf_provider": settings.hf_provider or None,
                "model": display_model,
                "request_model": _hf_request_model(settings.hf_model, settings.hf_provider),
                "base": settings.hf_base_url,
                "key": settings.hf_token,
                "reason": None,
            }

    host = urlparse(settings.nebius_base_url)
    valid_host = (
        host.scheme == "https"
        and (host.hostname or "").endswith(".nebius.com")
        and host.username is None
    )
    model = settings.nebius_model
    configured = bool(settings.nebius_api_key and valid_host and _is_nemotron(model))
    reason = None
    if not configured:
        reason = (
            "Set HF_TOKEN + NVIDIA Nemotron HF_MODEL (recommended), "
            "or NEBIUS_API_KEY + NEBIUS_MODEL for Nebius."
        )
    return {
        "configured": configured,
        "provider": "nebius" if configured else None,
        "hf_provider": None,
        "model": model or None,
        "request_model": model or None,
        "base": settings.nebius_base_url,
        "key": settings.nebius_api_key,
        "reason": reason,
    }


def public_configuration() -> dict:
    config = agent_configuration()
    return {
        "configured": config["configured"],
        "provider": config.get("provider"),
        "hf_provider": config.get("hf_provider"),
        "model": config["model"],
        "reason": config["reason"],
    }


def chat_completion(messages: list, tools: list, client: httpx.Client | None = None) -> dict:
    config = agent_configuration()
    if not config["configured"]:
        raise RuntimeError(config["reason"])

    body = {
        "model": config["request_model"] or config["model"],
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.2,
    }
    # Some providers reject tools; only send when the caller supplies them.
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    own = client is None
    client = client or httpx.Client(timeout=120.0)
    try:
        response = client.post(
            f"{config['base']}/chat/completions",
            headers={
                "Authorization": f"Bearer {config['key']}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        return response.json()
    finally:
        if own:
            client.close()
