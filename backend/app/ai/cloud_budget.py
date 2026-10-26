"""Reserve a conservative local credit allowance before every cloud request.

No refunds after timeouts: the provider may have processed a request. The ledger
persists across restarts. This is an application cap, not an account-wide cap.
"""
from contextlib import contextmanager
import json
import os
import time

from ..config import ROOT, get_settings

LEDGER = ROOT / ".cache/cloud-inference-budget.json"
# Public Nebius list rates verified 2026-10-26; unpriced models fail closed.
# https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference
RATES = {("nebius", "nvidia/Nemotron-3_5-Lightning"): (.06, .24)}


@contextmanager
def locked():
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    path = LEDGER.with_suffix(".lock")
    deadline = time.monotonic() + 2
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise RuntimeError("Cloud budget is locked; no request sent")
            time.sleep(.02)
    try:
        yield
    finally:
        os.close(descriptor)
        path.unlink()


def reserve(config, body):
    rates = RATES.get((config["provider"], config["model"]))
    if not rates:
        raise RuntimeError("No verified price allowance for this model; no request sent")
    encoded = json.dumps({"messages": body["messages"], "tools": body.get("tools", [])}, ensure_ascii=False).encode("utf-8")
    if len(encoded) > 32000:
        raise RuntimeError("Prompt exceeds the capped demo allowance; no request sent")
    # Byte-based bound plus generous chat/schema framing; doubled for headroom.
    input_bound = len(encoded) * 2 + 512 * (len(body["messages"]) + 1)
    allowance = round(2 * (input_bound * rates[0] + body["max_tokens"] * rates[1]) / 1e6, 10)
    settings = get_settings()
    with locked():
        ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"reserved_usd": 0, "requests": []}
        total = round(ledger["reserved_usd"] + allowance, 10)
        if total > settings.cloud_budget_usd or len(ledger["requests"]) >= settings.cloud_max_requests:
            raise RuntimeError("Local cloud allowance exhausted; no request sent")
        ledger["reserved_usd"] = total
        ledger["requests"].append({"model": config["model"], "reserved_usd": allowance, "input_token_bound": input_bound, "max_output_tokens": body["max_tokens"]})
        temporary = LEDGER.with_suffix(".tmp")
        temporary.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        os.replace(temporary, LEDGER)


def record_usage(config, usage):
    """Record provider token counts, without prompts, responses, or credentials."""
    if not usage:
        return
    rates = RATES[(config["provider"], config["model"])]
    price = (usage.get("prompt_tokens", 0)*rates[0] + usage.get("completion_tokens", 0)*rates[1])/1e6
    with locked():
        ledger = json.loads(LEDGER.read_text())
        ledger["reported_estimated_usd"] = round(ledger.get("reported_estimated_usd", 0)+price, 10)
        ledger["reported_prompt_tokens"] = ledger.get("reported_prompt_tokens", 0)+usage.get("prompt_tokens", 0)
        ledger["reported_completion_tokens"] = ledger.get("reported_completion_tokens", 0)+usage.get("completion_tokens", 0)
        temporary = LEDGER.with_suffix(".tmp")
        temporary.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        os.replace(temporary, LEDGER)
