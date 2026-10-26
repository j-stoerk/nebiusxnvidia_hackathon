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
    """Prefer the hackathon runtime on Nebius; Hugging Face is optional."""
    settings = get_settings()
    local = urlparse(settings.nemotron_base_url)
    if local.scheme in {"http", "https"} and local.hostname in {"127.0.0.1", "localhost", "::1"} and not local.username and _is_nemotron(settings.nemotron_model):
        return {"configured": True, "provider": "self-hosted", "hf_provider": None,
                "model": settings.nemotron_model, "request_model": settings.nemotron_model,
                "base": settings.nemotron_base_url, "key": "", "reason": None}

    host = urlparse(settings.nebius_base_url)
    if settings.cloud_inference_enabled and settings.nebius_api_key and host.scheme == "https" and (host.hostname or "").endswith(".nebius.com") and not host.username and _is_nemotron(settings.nebius_model):
        return {"configured": True, "provider": "nebius", "hf_provider": None,
                "model": settings.nebius_model, "request_model": settings.nebius_model,
                "base": settings.nebius_base_url, "key": settings.nebius_api_key, "reason": None}

    if settings.cloud_inference_enabled and settings.hf_token and _is_nemotron(settings.hf_model):
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
    configured = bool(settings.cloud_inference_enabled and settings.nebius_api_key and valid_host and _is_nemotron(model))
    reason = None
    if not configured:
        reason = (
            "Local computed summaries are enabled without credentials. "
            "NVIDIA model inference on Nebius is not configured."
        )
        if (settings.nebius_api_key or settings.hf_token) and not settings.cloud_inference_enabled:
            reason = "Cloud inference is disabled. A key alone never enables paid calls. Local computed summaries remain available."
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
        "available": True,
        "mode": "model" if config["configured"] else "local_summary",
    }


def chat_completion(messages: list, tools: list, client: httpx.Client | None = None) -> dict:
    config = agent_configuration()
    if not config["configured"]:
        raise RuntimeError(config["reason"])

    body = {
        "model": config["request_model"] or config["model"],
        "messages": messages,
        "max_tokens": get_settings().cloud_max_tokens,
        "temperature": 0.2,
    }
    # Some providers reject tools; only send when the caller supplies them.
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    if config["provider"] == "self-hosted":
        body["chat_template_kwargs"] = {"enable_thinking": False}
    else:
        from .cloud_budget import reserve
        reserve(config, body)

    own = client is None
    client = client or httpx.Client(timeout=120.0)
    try:
        response = client.post(
            f"{config['base']}/chat/completions",
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {config['key']}"} if config["key"] else {})},
            json=body,
        )
        response.raise_for_status()
        payload = response.json()
        if config["provider"] != "self-hosted":
            from .cloud_budget import record_usage
            record_usage(config, payload.get("usage"))
        return payload
    finally:
        if own:
            client.close()
