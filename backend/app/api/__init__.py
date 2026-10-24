from fastapi import APIRouter

from . import agent, analytics, optimization, simulation, upload

api_router = APIRouter(prefix="/api")
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(optimization.router, tags=["optimization"])
api_router.include_router(simulation.router, tags=["simulation"])
api_router.include_router(agent.router, tags=["agent"])
