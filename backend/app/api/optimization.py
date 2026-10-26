"""Baseline + OR-Tools optimization and capacity study endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from contextvars import copy_context
from queue import Queue
import asyncio
import json
import threading

from ..services import schedule_service
from ..services.optimizer import OptimizationError

router = APIRouter()
STREAM_SLOTS = threading.BoundedSemaphore(2)


@router.post("/optimize/stream")
def optimize_stream():
    """Real solver stages; presentation pacing belongs in the browser."""
    schedule_service.load_demo_if_empty()
    if not STREAM_SLOTS.acquire(blocking=False):
        raise HTTPException(503, "Both planners are busy; retry shortly")
    messages, context = Queue(), copy_context()

    def calculate():
        def report(stage, status, metrics=None):
            messages.put({"type": "progress", "stage": stage, "status": status, "metrics": metrics})
        try:
            result = schedule_service.run_optimization(report=report)
            messages.put({"type": "result", "workspace": result})
        except Exception as exc:
            messages.put({"type": "error", "message": str(exc)})
        finally:
            STREAM_SLOTS.release()

    threading.Thread(target=context.run, args=(calculate,), daemon=True).start()

    async def stream():
        while True:
            event = await asyncio.to_thread(messages.get)
            yield "data: " + json.dumps(jsonable_encoder(event)) + "\n\n"
            if event["type"] != "progress":
                break

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/optimize")
def optimize():
    schedule_service.load_demo_if_empty()
    try:
        return schedule_service.run_optimization()
    except schedule_service.Conflict:
        raise
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
    except schedule_service.Conflict:
        raise
    except OptimizationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
