"""
Outreach Dedup Admin Router
=============================
Visibility + control for the dedup layer.

GET  /api/admin/outreach-dedup/stats          → 24h counts + skipped count
GET  /api/admin/outreach-dedup/recent          → last N sends with phone hash
GET  /api/admin/outreach-dedup/check/{phone}   → recent history for one number
DELETE /api/admin/outreach-dedup/entry/{phone}/{message_type}
                                                 → clear one phone's entry
                                                 → use ONLY when intentionally
                                                 → re-sending after a 24h block
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/outreach-dedup", tags=["Outreach Dedup"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    try:
        from services.outreach_dedup import set_db as _set_dd
        _set_dd(database)
    except Exception:
        pass


def _get_db():
    if _db is None:
        raise HTTPException(503, "DB not available")
    return _db


async def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        p = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    if p.get("role") not in ("admin", "super_admin") and not p.get("is_admin"):
        raise HTTPException(403, "Admin only")
    return p


def _mask(phone: str) -> str:
    if not phone or len(phone) < 4:
        return "***"
    return phone[:3] + "***" + phone[-4:]


@router.get("/stats")
async def stats(request: Request):
    await _require_admin(request)
    db = _get_db()
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    sms_24h = await db.outreach_log.count_documents(
        {"message_type": "sms", "sent_at": {"$gte": cutoff_24h}}
    )
    wa_24h = await db.outreach_log.count_documents(
        {"message_type": "whatsapp", "sent_at": {"$gte": cutoff_24h}}
    )
    total_7d = await db.outreach_log.count_documents(
        {"sent_at": {"$gte": cutoff_7d}}
    )
    unique_phones_24h = len(await db.outreach_log.distinct(
        "phone", {"sent_at": {"$gte": cutoff_24h}}
    ))
    return {
        "sms_sent_24h": sms_24h,
        "whatsapp_sent_24h": wa_24h,
        "total_sent_7d": total_7d,
        "unique_phones_24h": unique_phones_24h,
        "checked_at": now.isoformat(),
    }


@router.get("/recent")
async def recent(request: Request, limit: int = 50):
    await _require_admin(request)
    db = _get_db()
    rows = await db.outreach_log.find(
        {}, {"_id": 0}
    ).sort("sent_at", -1).limit(min(limit, 500)).to_list(min(limit, 500))
    # Mask phones in the response
    for r in rows:
        r["phone_masked"] = _mask(r.get("phone", ""))
        r.pop("phone", None)
    return {"count": len(rows), "rows": rows}


@router.get("/check/{phone:path}")
async def check_phone(phone: str, request: Request, limit: int = 20):
    await _require_admin(request)
    db = _get_db()
    rows = await db.outreach_log.find(
        {"phone": phone}, {"_id": 0}
    ).sort("sent_at", -1).limit(min(limit, 100)).to_list(min(limit, 100))
    return {
        "phone_masked": _mask(phone),
        "count": len(rows),
        "history": rows,
    }


@router.delete("/entry/{phone:path}/{message_type}")
async def clear_entry(
    phone: str, message_type: str, request: Request,
    older_than_hours: Optional[int] = None,
):
    """Clear dedup entries so a phone can be re-sent. USE WITH CARE."""
    await _require_admin(request)
    if message_type not in ("sms", "whatsapp", "voice"):
        raise HTTPException(400, "message_type must be sms|whatsapp|voice")
    db = _get_db()
    q = {"phone": phone, "message_type": message_type}
    if older_than_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        q["sent_at"] = {"$lt": cutoff}
    res = await db.outreach_log.delete_many(q)
    return {
        "phone_masked": _mask(phone),
        "message_type": message_type,
        "deleted": res.deleted_count,
    }
