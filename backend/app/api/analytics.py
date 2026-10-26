"""Analytics and station configuration endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..models import StationConfig, PricePoint, VehicleSession
from ..services import schedule_service

router = APIRouter()


@router.get("/health")
def health():
    from ..ai import public_configuration

    return {
        "application": "chargewise",
        "status": "ok",
        "scheduler": "OR-Tools SCIP",
        "agent": public_configuration(),
        "persistence": "in-memory",
        "simulated": True,
    }


@router.get("/state")
def get_state():
    schedule_service.load_demo_if_empty()
    return schedule_service.STATE.snapshot()


@router.get("/analytics")
def get_analytics():
    schedule_service.load_demo_if_empty()
    snap = schedule_service.STATE.snapshot()
    return snap["analytics"]


class StationBody(BaseModel):
    station: StationConfig


class ScenarioBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sessions: list[VehicleSession] = Field(min_length=1, max_length=100)
    prices: list[PricePoint] = Field(min_length=1, max_length=2000)
    station: StationConfig


@router.put("/scenario")
def put_scenario(body: ScenarioBody):
    try:
        return schedule_service.replace_scenario(body.sessions, body.prices, body.station)
    except schedule_service.Conflict:
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/station")
def put_station(body: StationBody):
    try:
        return schedule_service.update_station(body.station.model_dump())
    except schedule_service.Conflict:
        raise
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
