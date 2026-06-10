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
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/autonomous", tags=["Autonomous Stack"])

from config import JWT_SECRET  # safe 3-tier resolver (env -> file -> ephemeral)
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
    """Cached 15s (D-71 perf) — 11-component snapshot, polled by /admin/brain."""
    await _require_admin(request)
    db = _get_db()
    from services.autonomous_stack import get_overview
    from services.poll_cache import cached as _poll_cached
    # iter D-71h — TTL 15s → 45s (3× the AdminBrainPage 15s poll interval)
    return await _poll_cached(
        key="autonomous:overview",
        ttl_sec=45,
        loader=lambda: get_overview(db),
    )


@router.get("/pipeline-flow")
async def pipeline_flow(request: Request, limit: int = 10) -> Dict[str, Any]:
    await _require_admin(request)
    db = _get_db()
    from services.autonomous_stack import get_pipeline_flow
    from services.poll_cache import cached as _poll_cached
    limit = max(1, min(50, limit))
    return await _poll_cached(
        key=f"autonomous:pipeline-flow:{limit}",
        ttl_sec=30,    # iter D-71h — was 10s, well under 15s poll → 0% hit
        loader=lambda: get_pipeline_flow(db, limit=limit),
    )


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


# ─── iter 322u — Founder notifications (HIGH-risk + watchdog events) ───
@router.get("/notifications")
async def notifications(
    request: Request, limit: int = 25, unread_only: bool = False,
) -> Dict[str, Any]:
    """List recent founder notifications. Used by /admin/brain badge +
    list. unread_only=true returns only unread rows."""
    await _require_admin(request)
    db = _get_db()
    limit = max(1, min(100, limit))
    q: Dict[str, Any] = {}
    if unread_only:
        q["read"] = False
    rows = []
    cur = db.founder_notifications.find(
        q, {"_id": 0},
    ).sort("created_at", -1).limit(limit)
    async for r in cur:
        rows.append(r)
    unread = await db.founder_notifications.count_documents({"read": False})
    high_risk_unread = await db.founder_notifications.count_documents(
        {"read": False, "type": "HIGH_RISK_PROPOSAL"}
    )
    return {
        "ok": True,
        "unread_total": unread,
        "high_risk_unread": high_risk_unread,
        "count": len(rows),
        "rows": rows,
    }


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    request: Request, body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Mark notifications as read. body={"ids":[...]} marks specific
    rows; body={"all":true} marks all unread; body={"type":"HIGH_RISK_PROPOSAL"}
    marks all unread of that type."""
    await _require_admin(request)
    db = _get_db()
    body = body or {}
    q: Dict[str, Any] = {"read": False}
    ids = body.get("ids") if isinstance(body.get("ids"), list) else None
    if ids:
        q["proposal_id"] = {"$in": ids}
    elif body.get("type"):
        q["type"] = body["type"]
    elif not body.get("all"):
        return {"ok": False, "error": "must supply ids[], type, or all=true"}
    res = await db.founder_notifications.update_many(
        q, {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "modified": res.modified_count}
