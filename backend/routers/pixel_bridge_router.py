"""
Pixel → ORA Bridge admin router — iter 323g
═══════════════════════════════════════════════════════════════════════════
Admin-only endpoints to observe and manually trigger the Pixel→ORA Bridge.
The cron itself lives in `services.pixel_to_ora_bridge.PixelToOraBridge` and
is wired into `aurem_scheduler` by `routers.registry`.
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/pixel-bridge", tags=["admin · pixel-bridge"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


async def _require_admin(request: Request) -> Dict[str, Any]:
    """Resolve caller and enforce admin role. Same fallback strategy as
    customer_vanguard_router to survive incremental boot."""
    user: Optional[Dict[str, Any]] = None
    try:
        from utils.auth_utils import get_current_user as _auth_get
        user = await _auth_get(request)
    except Exception:
        user = None
    if not user:
        try:
            import jwt as _jwt
            secret = os.environ.get("JWT_SECRET") or ""
            hdr = request.headers.get("Authorization") or ""
            if secret and hdr.lower().startswith("bearer "):
                payload = _jwt.decode(hdr.split(" ", 1)[1].strip(), secret, algorithms=["HS256"])
                user = {
                    "user_id": payload.get("user_id") or payload.get("sub"),
                    "email": payload.get("email"),
                    "is_admin": bool(payload.get("is_admin")),
                    "role": payload.get("role"),
                }
        except Exception:
            user = None
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not (user.get("is_admin") or user.get("role") in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/status")
async def status(request: Request) -> Dict[str, Any]:
    """Bridge monitor health + cumulative counters."""
    await _require_admin(request)
    from services.pixel_to_ora_bridge import PixelToOraBridge

    last_run = PixelToOraBridge.last_run_at
    last_event_count = PixelToOraBridge.last_event_count
    monitor_alive = bool(last_run and (
        datetime.now(timezone.utc) - last_run < timedelta(minutes=10)
    ))

    tasks_24h = 0
    dedup_skips_24h = 0
    if _db is not None:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            tasks_24h = await _db.pixel_ora_tasks.count_documents(
                {"created_at": {"$gte": cutoff}}
            )
        except Exception as e:
            logger.debug(f"[pixel-bridge/status] tasks count failed: {e}")
        dedup_skips_24h = (PixelToOraBridge.last_summary or {}).get("skipped_dedup", 0)

    return {
        "monitor_alive": monitor_alive,
        "last_run_at": last_run.isoformat() if last_run else None,
        "last_event_count": last_event_count,
        "last_summary": PixelToOraBridge.last_summary or {},
        "tasks_24h": tasks_24h,
        "dedup_skips_24h": dedup_skips_24h,
    }


@router.post("/trigger")
async def trigger(request: Request) -> Dict[str, Any]:
    """Manually invoke one bridge cycle (for testing / demo)."""
    await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="DB not initialised")
    from services.pixel_to_ora_bridge import PixelToOraBridge
    summary = await PixelToOraBridge().run_cycle(_db)
    return {"ok": True, "summary": summary}


@router.get("/tasks")
async def tasks(request: Request, limit: int = 50) -> Dict[str, Any]:
    """Recent pixel_ora_tasks for inspection."""
    await _require_admin(request)
    if _db is None:
        return {"tasks": [], "count": 0, "note": "db_unavailable"}
    out = []
    try:
        cursor = _db.pixel_ora_tasks.find({}, {"_id": 0}).sort("created_at", -1).limit(max(1, min(int(limit), 200)))
        async for t in cursor:
            ca = t.get("created_at")
            if isinstance(ca, datetime):
                t["created_at"] = ca.isoformat()
            out.append(t)
    except Exception as e:
        logger.warning(f"[pixel-bridge/tasks] list failed: {e}")
    return {"tasks": out, "count": len(out)}


__all__ = ["router", "set_db"]
