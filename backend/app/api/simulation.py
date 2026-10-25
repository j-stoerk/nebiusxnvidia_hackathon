"""Simulated event endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..models import SimulationEvent
from datetime import datetime
from pydantic import field_validator
from ..utils.datetime_utils import ensure_utc
from ..services import schedule_service
from ..services.optimizer import OptimizationError

router = APIRouter()


class AdvanceBody(BaseModel):
    time: datetime
    _parse = field_validator("time", mode="before")(ensure_utc)


@router.post("/advance")
def advance_time(body: AdvanceBody):
    try:
        return schedule_service.advance(body.time)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


class EventBody(BaseModel):
    event: SimulationEvent
    reoptimize: bool = Field(default=True)


@router.post("/events")
def create_event(body: EventBody):
    schedule_service.load_demo_if_empty()
    try:
        return schedule_service.simulate(body.event, reoptimize=body.reoptimize)
    except schedule_service.Conflict:
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except OptimizationError as exc:
        raise HTTPException(422, str(exc)) from exc
