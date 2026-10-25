"""Bounded Nemotron tool loop; OR-Tools remains the scheduler."""

import json

import httpx
from fastapi.encoders import jsonable_encoder

from ..services import schedule_service
from .nemotron_client import chat_completion, public_configuration
from .prompts import SYSTEM_PROMPT
from .tools import TOOL_SPECS, execute_tool

MAX_TOOL_ROUNDS = 4


def _openai_tools() -> list:
    tools = []
    for name, (model, description) in TOOL_SPECS.items():
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": model.model_json_schema(),
                },
            }
        )
    return tools


def local_summary():
    """Useful credential-free fallback; explicitly not an AI/model response."""
    state = schedule_service.STATE.snapshot()
    plan = state["optimized"] or state["baseline"]
    if not plan:
        message = "Run the optimizer to calculate a checked charging plan. No model inference is enabled."
    else:
        m = plan["metrics"]
        message = (f"Local computed summary — no AI model call.\n"
            f"Targets met: {m['target_success_percent']:.0f}%; unserved energy: {m['unserved_kwh']:.3f} kWh.\n"
            f"Peak: {m['peak_power_kw']:.2f} kW. Energy cost: EUR {m['energy_cost_eur']:.2f}; "
            f"incremental demand cost: EUR {m['demand_cost_eur']:.2f}.\n"
            f"Independent constraints: {'passed' if plan['validated'] else 'not certified'}. "
            f"{'The plan is stale; re-optimize after the latest change.' if state['stale'] else 'This is a simulated planning result.'}")
    return {"mode": "local_summary", "message": message, "model": None, "tool_calls": [], "workspace": state}


def chat(message: str, allow_changes: bool = False) -> dict:
    config = public_configuration()
    if not config["configured"]:
        return local_summary()

    context = {
        "allow_changes": allow_changes,
        "runtime_provider": config["provider"],
        "current_state": execute_tool("get_state", {}, False),
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(jsonable_encoder(context))},
        {"role": "user", "content": message},
    ]
    trace = []

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            payload = chat_completion(messages, _openai_tools())
            choice = payload["choices"][0]["message"]
            calls = choice.get("tool_calls") or []
            if not calls:
                return {
                    "mode": "assistant",
                    "message": choice.get("content") or "",
                    "model": config["model"],
                    "tool_calls": trace,
                    "workspace": schedule_service.STATE.snapshot(),
                }

            messages.append(
                {
                    "role": "assistant",
                    "content": choice.get("content"),
                    "tool_calls": calls,
                }
            )
            for call in calls:
                name = call["function"]["name"]
                raw = call["function"].get("arguments") or "{}"
                try:
                    args = json.loads(raw)
                except json.JSONDecodeError:
                    args = {}
                result = execute_tool(name, args, allow_changes)
                trace.append({"tool": name, "arguments": args, "result_keys": list(result.keys())})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(jsonable_encoder(result))[:12000],
                    }
                )

        return {
            "mode": "assistant",
            "message": "Reached the tool-call limit. Inspect completed tools and ask a follow-up.",
            "model": config["model"],
            "tool_calls": trace,
            "workspace": schedule_service.STATE.snapshot(),
        }
    except httpx.HTTPStatusError as exc:
        provider = (config.get("provider") or "provider").title()
        detail = ""
        try:
            detail = exc.response.text[:400]
        except Exception:
            pass
        code = exc.response.status_code
        if code == 402:
            hint = (
                "Your HF token works, but this account has no Inference Provider credits. "
                "Add credits or PRO at https://huggingface.co/settings/billing — "
                "or set NEBIUS_API_KEY in .env (Nebius gives ~$1 trial / Builder $25 free credits) "
                "with NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B and leave HF_TOKEN empty "
                "to use Nebius instead. "
            )
        elif code == 400 and "provider" in detail.lower():
            hint = (
                "Enable Featherless (or set HF_PROVIDER) under "
                "https://huggingface.co/settings/inference-providers. "
            )
        else:
            hint = "Check HF_TOKEN permissions (Inference) and HF_MODEL. "
        return {
            "mode": "error",
            "message": f"{provider} HTTP {code}. {hint}{detail}".strip(),
            "model": config["model"],
            "tool_calls": trace,
        }
    except Exception as exc:
        return {
            "mode": "error",
            "message": f"Nemotron request failed: {exc}. Scheduling remains available.",
            "model": config["model"],
            "tool_calls": trace,
        }
