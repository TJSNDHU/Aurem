"""
ASI-Evolve Router — Self-Improvement Dashboard API
"""
import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/asi-evolve", tags=["ASI-Evolve"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database
    # Also set DB on the service
    from services.asi_evolve import set_db as evolve_set_db
    evolve_set_db(database)


def get_db():
    if _db is None:
        raise HTTPException(503, "Database not initialized")
    return _db


def _require_admin(request: Request):
    """Admin-role gate: valid JWT + (is_admin OR role in [admin, super_admin])."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        payload = jwt.decode(
            auth.split(" ", 1)[1],
            (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
            algorithms=["HS256"]
        )
    except Exception:
        raise HTTPException(401, "Invalid token")

    role = (payload.get("role") or "").lower()
    is_admin = bool(payload.get("is_admin") or payload.get("is_super_admin"))
    if role not in ("admin", "super_admin") and not is_admin:
        raise HTTPException(403, "Admin role required")
    return payload


@router.get("/stats")
async def evolution_stats(request: Request):
    """Get ASI-Evolve statistics for dashboard"""
    _require_admin(request)
    from services.asi_evolve import get_evolution_stats
    return await get_evolution_stats()


@router.get("/history")
async def evolution_history(request: Request, limit: int = 20):
    """Get evolution history with lineage"""
    _require_admin(request)
    db = get_db()

    evolutions = await db.self_improvement.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    return {"evolutions": evolutions, "total": len(evolutions)}


@router.get("/active-instructions")
async def active_instructions(request: Request):
    """Get all currently active evolved instructions in knowledge_base"""
    _require_admin(request)
    db = get_db()

    instructions = await db.knowledge_base.find(
        {"type": "evolved_instruction"},
        {"_id": 0}
    ).sort("deployed_at", -1).to_list(50)

    return {"instructions": instructions, "count": len(instructions)}


@router.get("/pending")
async def pending_approvals(request: Request):
    """Get evolutions awaiting manual approval"""
    _require_admin(request)
    db = get_db()

    pending = await db.self_improvement.find(
        {"status": "pending_approval"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)

    return {"pending": pending, "count": len(pending)}


@router.post("/trigger")
async def trigger_evolution(request: Request):
    """Manually trigger an evolution cycle"""
    _require_admin(request)
    from services.asi_evolve import run_evolution_cycle
    result = await run_evolution_cycle()
    return result


@router.post("/approve/{pattern_id}")
async def approve(pattern_id: str, request: Request):
    """Approve a pending evolution for protected domains"""
    _require_admin(request)
    from services.asi_evolve import approve_evolution
    return await approve_evolution(pattern_id)


@router.post("/reject/{pattern_id}")
async def reject(pattern_id: str, request: Request):
    """Reject a pending evolution"""
    _require_admin(request)
    from services.asi_evolve import reject_evolution
    return await reject_evolution(pattern_id)
