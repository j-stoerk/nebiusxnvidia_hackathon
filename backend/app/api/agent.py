"""Nemotron agent chat endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..ai import agent as nemotron_agent
from ..services import schedule_service

router = APIRouter()


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    allow_changes: bool = False


@router.post("/chat")
def chat(body: ChatBody):
    schedule_service.load_demo_if_empty()
    reply = nemotron_agent.chat(body.message, body.allow_changes)
    workspace = reply.pop("workspace", None) or schedule_service.STATE.snapshot()
    return {"reply": reply, "workspace": workspace}


@router.get("/agent/status")
def agent_status():
    return nemotron_agent.public_configuration()
