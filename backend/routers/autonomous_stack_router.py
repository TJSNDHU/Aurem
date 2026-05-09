"""
autonomous_stack_router.py — read-only admin endpoints for /admin/brain.

Surface:
  GET /api/admin/autonomous/overview            — 11-component snapshot
  GET /api/admin/autonomous/pipeline-flow       — recent flow trace
  GET /api/admin/autonomous/recent-decisions    — Council audit feed
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/autonomous", tags=["Autonomous Stack"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _get_db():
    if _db is None:
        raise HTTPException(503, "DB not available")
    return _db


async def _require_admin(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(
            auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"]
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = payload.get("role", "")
    if (role in ("admin", "super_admin")
            or payload.get("is_admin")
            or payload.get("is_super_admin")):
        return payload
    raise HTTPException(403, "Admin only")


@router.get("/overview")
async def overview(request: Request) -> Dict[str, Any]:
    await _require_admin(request)
    db = _get_db()
    from services.autonomous_stack import get_overview
    return await get_overview(db)


@router.get("/pipeline-flow")
async def pipeline_flow(request: Request, limit: int = 10) -> Dict[str, Any]:
    await _require_admin(request)
    db = _get_db()
    from services.autonomous_stack import get_pipeline_flow
    limit = max(1, min(50, limit))
    return await get_pipeline_flow(db, limit=limit)


@router.get("/recent-decisions")
async def recent_decisions(
    request: Request,
    limit: int = 50,
    action: Optional[str] = None,
    verdict: Optional[str] = None,
) -> Dict[str, Any]:
    await _require_admin(request)
    db = _get_db()
    from services.autonomous_stack import get_recent_decisions
    limit = max(1, min(200, limit))
    return await get_recent_decisions(
        db, limit=limit, action_filter=action, verdict_filter=verdict,
    )
