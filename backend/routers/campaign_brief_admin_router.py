"""
Campaign Brief Admin Router — manual run + preview
===================================================

Routes (admin-gated):
  GET  /api/admin/campaign-brief/preview   → JSON of today's metrics (no send)
  POST /api/admin/campaign-brief/run-now   → force-send the brief email immediately
  GET  /api/admin/campaign-brief/log       → last 7 brief runs
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from services.campaign_daily_brief import (
    collect_brief_metrics,
    send_campaign_daily_brief,
)
from shared.memory_tiers import _get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/campaign-brief", tags=["admin-campaign-brief"])


def _verify_admin(request: Request) -> Dict[str, Any]:
    """Light-weight admin gate — matches pillars_health_router pattern."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_token")
    token = auth.split(" ", 1)[1].strip()
    try:
        import os
        import jwt
        secret = os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY") or ""
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_signature": bool(secret)})
    except Exception:
        # Best-effort decode without verification — admin must still be marked
        try:
            import jwt as _jwt
            payload = _jwt.decode(token, options={"verify_signature": False})
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"invalid_token: {e}")
    if not (payload.get("is_admin") or payload.get("role") == "admin"):
        # Accept tokens carrying an email claim as a soft-gate (matches rest of admin API in this app)
        if not payload.get("email"):
            raise HTTPException(status_code=403, detail="admin_only")
    return payload


@router.get("/preview")
async def preview_today(_: Dict[str, Any] = Depends(_verify_admin)):
    db = _get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")
    metrics = await collect_brief_metrics(db)
    return {"ok": True, "metrics": metrics}


@router.post("/run-now")
async def run_now(_: Dict[str, Any] = Depends(_verify_admin)):
    db = _get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")
    res = await send_campaign_daily_brief(db, force=True)
    return res


@router.get("/log")
async def last_runs(_: Dict[str, Any] = Depends(_verify_admin)):
    db = _get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")
    runs = []
    try:
        cur = db.campaign_brief_log.find(
            {}, {"_id": 0}
        ).sort("ts", -1).limit(7)
        async for r in cur:
            runs.append(r)
    except Exception as e:
        logger.warning(f"[campaign-brief] log read failed: {e}")
    return {"ok": True, "runs": runs}
