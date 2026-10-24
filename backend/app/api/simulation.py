"""Simulated event endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..models import SimulationEvent
from ..services import schedule_service
from ..services.optimizer import OptimizationError

router = APIRouter()


class EventBody(BaseModel):
    event: SimulationEvent
    reoptimize: bool = Field(default=True)


@router.post("/events")
def create_event(body: EventBody):
    schedule_service.load_demo_if_empty()
    try:
        return schedule_service.simulate(body.event, reoptimize=body.reoptimize)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except OptimizationError as exc:
        raise HTTPException(422, str(exc)) from exc
