"""
AUREM A2A Swarm Router — Agent Cards & Orchestration API
=========================================================
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/swarm", tags=["A2A Swarm"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        payload = jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


class RegisterWorkerRequest(BaseModel):
    skill_name: str
    capabilities: List[str]
    model: str = "qwen2:0.5b"


class RouteTaskRequest(BaseModel):
    query: str
    prefer_worker: bool = True


@router.get("/cards")
async def list_agent_cards(authorization: str = Header(None)):
    """List all agent cards in the swarm registry."""
    await _auth(authorization)
    from services.agent_cards import get_all_cards
    return {"agents": get_all_cards()}


@router.get("/cards/{agent_id}")
async def get_card(agent_id: str, authorization: str = Header(None)):
    """Get a specific agent's card."""
    await _auth(authorization)
    from services.agent_cards import get_agent_card
    card = get_agent_card(agent_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return card


@router.post("/register-worker")
async def register_worker(req: RegisterWorkerRequest, authorization: str = Header(None)):
    """Register a BitNet worker as an agent in the swarm."""
    await _auth(authorization)
    from services.agent_cards import register_worker
    return register_worker(req.skill_name, req.capabilities, req.model)


@router.post("/route")
async def route_task(req: RouteTaskRequest, authorization: str = Header(None)):
    """Find the best agent for a task based on capability matching."""
    await _auth(authorization)
    from services.agent_cards import find_agent_for_task
    match = find_agent_for_task(req.query, req.prefer_worker)
    if not match:
        return {"matched": False, "message": "No agent matched this task"}
    return {"matched": True, "agent": match}


@router.get("/stats")
async def swarm_stats(authorization: str = Header(None)):
    """Get swarm-level statistics for Overwatch."""
    await _auth(authorization)
    from services.agent_cards import get_swarm_stats
    return get_swarm_stats()


@router.get("/log")
async def swarm_log(limit: int = 20, authorization: str = Header(None)):
    """Get recent swarm execution log."""
    await _auth(authorization)
    from services.agent_cards import get_swarm_log
    return {"log": get_swarm_log(limit)}
