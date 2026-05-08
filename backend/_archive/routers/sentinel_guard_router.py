"""
Sentinel Guard API Router
=========================
Endpoints feeding the Admin sidebar heartbeat + War Room panel.

  GET  /api/sentinel/heartbeat       — {item_id: "healthy"|"degraded"|"error"}
  GET  /api/sentinel/patterns        — top recurring error patterns
  GET  /api/sentinel/rca             — run a fresh root-cause check
  POST /api/sentinel/ack/{fingerprint} — clear an escalated pattern
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sentinel", tags=["Sentinel Guard"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

_db = None


def set_db(db) -> None:
    global _db
    _db = db
    from services.sentinel_guard import set_db as set_guard_db
    set_guard_db(db)


async def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    if payload.get("is_admin") or payload.get("is_super_admin") \
            or payload.get("role") in ("admin", "super_admin"):
        return payload
    raise HTTPException(403, "Admin only")


@router.get("/heartbeat")
async def heartbeat(request: Request):
    """Per-sidebar-item live status for the heartbeat dots."""
    await _require_admin(request)
    from services.sentinel_guard import sidebar_heartbeat
    status = await sidebar_heartbeat()
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "status": status,  # keyed by sidebar item id
        "count": len(status),
    }


@router.get("/patterns")
async def patterns(request: Request, limit: int = 10):
    """Top recurring error patterns (War Room view)."""
    await _require_admin(request)
    from services.sentinel_guard import get_top_patterns
    items = await get_top_patterns(limit=limit)
    return {"count": len(items), "items": items}


@router.get("/rca")
async def rca(request: Request):
    """Run an on-demand root-cause check."""
    await _require_admin(request)
    from services.sentinel_guard import root_cause_analysis
    return await root_cause_analysis()


@router.post("/ack/{fingerprint}")
async def ack_pattern(fingerprint: str, request: Request):
    """Mark an escalated error pattern as acknowledged (clears the dot)."""
    admin = await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "DB not available")
    result = await _db["error_patterns"].update_one(
        {"fingerprint": fingerprint},
        {"$set": {
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            "acknowledged_by": admin.get("email", "admin"),
            "last_escalated_at": None,  # clear the red state
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Pattern not found")
    return {"success": True, "fingerprint": fingerprint}
