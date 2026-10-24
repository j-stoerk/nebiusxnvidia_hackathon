"""HTTP routes delegate ingestion, state, scheduling, and agent behavior to their modules."""

import json
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..ai import agent
from ..services.csv_validator import MAX_UPLOAD
from ..models import AdvanceRequest, ChatRequest, EventRequest, SettingsRequest, VersionRequest
from pydantic import Field
from ..services.planning import capacity_frontier
from ..services.schedule_service import ROOT, Workspaces, advance, apply_event, expected, replan, snapshot, update_station, upload

router = APIRouter(prefix="/api")
store = Workspaces()


def workspace(workspace_id):
    try:
        return store.get(workspace_id)
    except KeyError as exc:
        raise HTTPException(404, "Workspace expired or not found; load a new demo") from exc


def view(scenario):
    return {**snapshot(scenario), "agent": agent.public_configuration()}


@router.get("/health")
def health():
    return {"application": "chargewise", "status": "ok", "scheduler": "OR-Tools SCIP", "agent": agent.public_configuration(), "persistence": "in-memory"}


class CreateWorkspace(BaseModel):
    demo: Literal["normal", "stress", "capacity"] = "normal"


@router.post("/workspaces", status_code=201)
def create_workspace(body: CreateWorkspace):
    scenario = store.create(stress=body.demo == "stress", capacity=body.demo == "capacity")
    return view(scenario)


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str):
    scenario = workspace(workspace_id)
    with scenario.lock:
        return view(scenario)


@router.post("/workspaces/{workspace_id}/optimize")
def optimize_workspace(workspace_id: str, body: VersionRequest):
    scenario = workspace(workspace_id)
    with scenario.lock:
        expected(scenario, body.expected_version)
        replan(scenario)
        return view(scenario)


class CapacityRequest(VersionRequest):
    counts: list[int] = Field(min_length=1, max_length=10)


@router.post("/workspaces/{workspace_id}/capacity")
def capacity_workspace(workspace_id: str, body: CapacityRequest):
    scenario = workspace(workspace_id)
    with scenario.lock:
        expected(scenario, body.expected_version)
        try:
            return capacity_frontier(scenario, body.counts)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


@router.post("/workspaces/{workspace_id}/events")
def event_workspace(workspace_id: str, body: EventRequest):
    scenario = workspace(workspace_id)
    with scenario.lock:
        result = apply_event(scenario, body.event, body.expected_version)
        return {"event_result": result, **view(scenario)}


@router.post("/workspaces/{workspace_id}/advance")
def advance_workspace(workspace_id: str, body: AdvanceRequest):
    scenario = workspace(workspace_id)
    with scenario.lock:
        advance(scenario, body.time, body.expected_version)
        return view(scenario)


@router.put("/workspaces/{workspace_id}/station")
def settings_workspace(workspace_id: str, body: SettingsRequest):
    scenario = workspace(workspace_id)
    with scenario.lock:
        update_station(scenario, body.station, body.expected_version)
        return view(scenario)


@router.post("/workspaces/{workspace_id}/upload")
async def upload_workspace(workspace_id: str, expected_version: int = Form(...),
                           sessions: UploadFile = File(...), prices: UploadFile | None = File(default=None)):
    session_data = await sessions.read(MAX_UPLOAD + 1)
    price_data = await prices.read(MAX_UPLOAD + 1) if prices and prices.filename else None
    if len(session_data) > MAX_UPLOAD or (price_data is not None and len(price_data) > MAX_UPLOAD):
        raise HTTPException(413, "Each CSV must be at most 2 MiB")
    scenario = workspace(workspace_id)
    # Solver work is blocking; run it off the ASGI event loop.
    from starlette.concurrency import run_in_threadpool
    def ingest():
        with scenario.lock:
            upload(scenario, session_data, price_data, expected_version)
            return view(scenario)
    return await run_in_threadpool(ingest)


@router.post("/workspaces/{workspace_id}/chat")
def chat_workspace(workspace_id: str, body: ChatRequest):
    scenario = workspace(workspace_id)
    with scenario.lock:
        expected(scenario, body.expected_version)
    response = agent.chat(scenario, body.message, body.allow_changes, body.expected_version)
    with scenario.lock:
        return {"reply": response, "workspace": view(scenario)}


@router.get("/demo/scenarios")
def demo_scenarios():
    return json.loads((ROOT / "data" / "demo" / "events.json").read_text(encoding="utf-8"))


@router.get("/demo/{name}")
def demo_file(name: Literal["sessions", "stress", "prices"]):
    filename = {"sessions": "sample_charging_sessions.csv", "stress": "infeasible_charging_sessions.csv", "prices": "synthetic_prices_15min.csv"}[name]
    return FileResponse(ROOT / "data" / "demo" / filename, filename=filename, media_type="text/csv")
