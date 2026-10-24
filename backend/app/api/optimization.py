"""Baseline + OR-Tools optimization and capacity study endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services import schedule_service
from ..services.optimizer import OptimizationError

router = APIRouter()


@router.post("/optimize")
def optimize():
    schedule_service.load_demo_if_empty()
    try:
        return schedule_service.run_optimization()
    except OptimizationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


class CapacityBody(BaseModel):
    counts: list[int] | None = Field(default=None, max_length=10)


@router.post("/capacity")
def capacity(body: CapacityBody | None = None):
    schedule_service.load_demo_if_empty()
    try:
        return schedule_service.run_capacity(counts=(body.counts if body else None))
    except OptimizationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
