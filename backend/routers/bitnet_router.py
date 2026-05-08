"""
AUREM BitNet Worker Router — Skill Offloading API
===================================================
Manages stability scoring, skill offloading, and the qwen2:0.5b worker.
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/bitnet", tags=["BitNet Worker"])
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


class ExecuteRequest(BaseModel):
    skill_name: str
    task_input: str


class TestWorkerRequest(BaseModel):
    message: str = "Hello, identify yourself in one sentence."


@router.get("/stats")
async def worker_stats(authorization: str = Header(None)):
    """Get BitNet worker stats: stability scores, offloaded skills, execution metrics."""
    await _auth(authorization)
    from services.bitnet_worker import get_worker_stats
    return get_worker_stats()


@router.get("/stability")
async def all_stability(authorization: str = Header(None)):
    """Get stability data for all skills."""
    await _auth(authorization)
    from services.bitnet_worker import get_all_stability
    return {"skills": get_all_stability()}


@router.get("/stability/{skill_name}")
async def skill_stability(skill_name: str, authorization: str = Header(None)):
    """Get stability data for a specific skill."""
    await _auth(authorization)
    from services.bitnet_worker import get_skill_stability
    return get_skill_stability(skill_name)


@router.post("/execute")
async def execute_skill(req: ExecuteRequest, authorization: str = Header(None)):
    """
    Execute a task using an offloaded skill via the BitNet worker (qwen2:0.5b).
    The skill document is loaded as context for the micro-worker.
    Stability score is updated based on execution result.
    """
    await _auth(authorization)
    from services.bitnet_worker import execute_offloaded_skill, get_skill_stability

    data = get_skill_stability(req.skill_name)
    if not data.get("offloaded") and data.get("score", 0) < 100:
        return {
            "warning": f"Skill '{req.skill_name}' not yet at 100% stability (current: {data.get('score', 0)}%). Executing via main brain instead.",
            "offloaded": False,
            "stability": data,
        }

    result = await execute_offloaded_skill(req.skill_name, req.task_input)
    return result


@router.post("/test")
async def test_worker(req: TestWorkerRequest, authorization: str = Header(None)):
    """Test the BitNet worker (qwen2:0.5b) connection."""
    await _auth(authorization)
    from services.bitnet_worker import call_worker
    result = await call_worker(req.message)
    return result


@router.post("/offload/{skill_name}")
async def force_offload(skill_name: str, authorization: str = Header(None)):
    """Manually force-offload a skill to the BitNet worker (sets score to 100)."""
    await _auth(authorization)
    from services.bitnet_worker import update_stability, get_skill_stability

    # Set to 100% by marking 5 consecutive successes
    for _ in range(5):
        update_stability(skill_name, True)

    data = get_skill_stability(skill_name)
    return {"skill": skill_name, "stability": data, "message": f"Skill force-offloaded to qwen2:0.5b"}


@router.get("/offloaded")
async def list_offloaded(authorization: str = Header(None)):
    """List all skills currently offloaded to the BitNet worker."""
    await _auth(authorization)
    from services.bitnet_worker import get_offloaded_skills, get_skill_stability
    offloaded = get_offloaded_skills()
    return {
        "offloaded": [
            {"name": name, **get_skill_stability(name)}
            for name in offloaded
        ],
        "total": len(offloaded),
    }
