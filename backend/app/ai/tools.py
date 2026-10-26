"""Approved backend tools the Nemotron agent may call."""

import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..models import SimulationEvent
from ..services import schedule_service


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadStateArgs(ToolArgs):
    pass


class ReadScheduleArgs(ToolArgs):
    vehicle_id: str | None = Field(default=None, max_length=80)


class OptimizeArgs(ToolArgs):
    pass


class SimulateEventArgs(ToolArgs):
    event: SimulationEvent

    @field_validator("event", mode="before")
    @classmethod
    def decode_event(cls, value):
        """Some inference providers serialize nested function arguments twice."""
        return json.loads(value) if isinstance(value, str) else value


TOOL_SPECS = {
    "get_state": (ReadStateArgs, "Read analytics, comparison, at-risk vehicles, events, and station status."),
    "get_schedule": (ReadScheduleArgs, "Read optimized or baseline schedule allocations, optionally for one vehicle."),
    "optimize_schedule": (OptimizeArgs, "Run FCFS baseline + OR-Tools optimization. Requires allow_changes."),
    "simulate_event": (SimulateEventArgs, "Apply a simulated charger or price event and re-optimize. Requires allow_changes."),
}


def execute_tool(name: str, arguments: dict, allow_changes: bool) -> dict:
    if name not in TOOL_SPECS:
        return {"error": f"Unknown tool: {name}"}
    try:
        TOOL_SPECS[name][0].model_validate(arguments)
    except ValidationError as exc:
        return {"error": "Tool arguments do not match the declared schema; no change applied",
                "fields": [{"path": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]}
    if name == "get_state":
        snap = schedule_service.STATE.snapshot()
        return {
            "analytics": snap["analytics"],
            "comparison": snap["comparison"],
            "at_risk": snap["at_risk"][:20],
            "events": snap["events"][-10:],
            "station": {
                "station_power_limit_kw": snap["station"]["station_power_limit_kw"],
                "available_chargers": sum(1 for c in snap["station"]["chargers"] if c["available"]),
                "total_chargers": len(snap["station"]["chargers"]),
                "fixed_connections": snap["station"]["fixed_connections"],
                "simulated": True,
            },
            "stale": snap["stale"],
            "last_error": snap["last_error"],
        }

    if name == "get_schedule":
        args = ReadScheduleArgs.model_validate(arguments)
        snap = schedule_service.STATE.snapshot()
        plan = snap["optimized"] or snap["baseline"]
        if not plan:
            return {"message": "No schedule yet. Run optimize_schedule first."}
        allocations = plan["allocations"]
        if args.vehicle_id:
            allocations = [a for a in allocations if a["vehicle_id"] == args.vehicle_id]
        from datetime import datetime
        def duration(record):
            return (datetime.fromisoformat(record["end_time"]) - datetime.fromisoformat(record["start_time"])).total_seconds() / 3600
        facts = {
            "charger_ids": sorted({a["charger_id"] for a in allocations}),
            "fixed_connections": snap["station"]["fixed_connections"],
            "allocation_count": len(allocations),
            "active_charging_hours": round(sum(duration(a) for a in allocations), 6),
            "battery_energy_delivered_kwh": round(sum(a["power_kw"] * duration(a) * a["charging_efficiency"] for a in allocations), 6),
            "earliest_charge": min((a["start_time"] for a in allocations), default=None),
            "latest_charge": max((a["end_time"] for a in allocations), default=None),
            "note": "First/last endpoints may contain idle gaps. Active duration is summed from actual allocations. Do not infer uninterrupted charging.",
        }
        return {
            "kind": plan["kind"],
            "solver_status": plan["solver_status"],
            "metrics": {
                "cost_eur": plan["metrics"]["cost_eur"],
                "unserved_kwh": plan["metrics"]["unserved_kwh"],
                "peak_power_kw": plan["metrics"]["peak_power_kw"],
                "target_success_percent": plan["metrics"]["target_success_percent"],
            },
            "allocations": allocations[:40],
            "allocations_truncated": len(allocations) > 40,
            "selected_facts": facts,
        }

    if name == "optimize_schedule":
        if not allow_changes:
            return {"error": "allow_changes is false; optimization not run"}
        return schedule_service.run_optimization()["comparison"] or {"status": "optimized"}

    if name == "simulate_event":
        if not allow_changes:
            return {"error": "allow_changes is false; simulation not applied"}
        args = SimulateEventArgs.model_validate(arguments)
        result = schedule_service.simulate(args.event, reoptimize=True)
        return {
            "event_result": result["event_result"],
            "comparison": result.get("comparison"),
            "at_risk_count": len(result.get("at_risk") or []),
            "stale": result.get("stale"),
            "validated": bool(result.get("optimized", {}).get("validated")),
        }

    return {"error": f"Unknown tool: {name}"}
