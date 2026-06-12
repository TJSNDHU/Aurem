"""
Inbound email webhook router — iter 282al-9.

  POST /api/email/inbound       — Resend Inbound / generic webhook receiver
  GET  /api/email/inbound/health
  GET  /api/email/inbound/recent — admin (last 50 inbound replies + intent)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from services.inbound_reply_handler import handle_inbound_reply

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)
router = APIRouter()

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server  # noqa: WPS433
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


# ─────────────────────────────────────────────────────────────────────
# iter D-76 dedupe — /api/email/inbound and /api/email/inbound/health
# moved fully to routers/email_inbound_router.py (the comprehensive
# Cloudflare-Worker → ORA-reply pipeline with threading headers,
# dedup guard, founder-loop guard, max-reply rate limiting). The thin
# inbound_reply_handler-only variant here was producing duplicates.
# Keeping only /api/email/inbound/recent (admin glance, unique).
# ─────────────────────────────────────────────────────────────────────
def _verify_admin(authorization: Optional[str]) -> None:
    """Light auth — same shape as other admin endpoints. Reuses JWT."""
    if not authorization:
        raise HTTPException(status_code=401, detail="missing token")
    try:
        import os
        import jwt
        token = authorization.replace("Bearer ", "").strip()
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        if not secret:
            raise HTTPException(status_code=500, detail="JWT_SECRET unset")
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        if not decoded.get("is_admin"):
            raise HTTPException(status_code=403, detail="admin only")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")


@router.get("/api/email/inbound/recent")
async def inbound_recent(authorization: Optional[str] = Header(None)) -> dict:
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        return {"items": [], "total": 0}
    try:
        cur = db.inbound_replies.find(
            {"business_id": FOUNDER_BIN},
            projection={"_id": 0, "text": 0, "html": 0},
        ).sort("received_at", -1).limit(50)
        items = [d async for d in cur]
        # Cast datetimes for JSON
        for it in items:
            if isinstance(it.get("received_at"), datetime):
                it["received_at"] = it["received_at"].isoformat()
        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.warning(f"[inbound] recent fetch failed: {e}")
        return {"items": [], "total": 0, "error": str(e)[:200]}
