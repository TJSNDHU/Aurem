"""
routers/outreach_admin_router.py — iter 330

Founder-only endpoints:
  GET  /api/admin/outreach/health        — 7-channel snapshot
  POST /api/admin/outreach/closer-day5/run — kick the Retell sweep now
  POST /api/admin/outreach/reply-inbox/run — process pending replies now
  POST /api/admin/outreach/social/post-now — fire today's LinkedIn post
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/admin/outreach", tags=["outreach-admin"])

_db = None


def set_db(database):
    global _db
    _db = database


def _admin_dep():
    from routers.ora_agent_router import get_admin_user
    return get_admin_user


@router.get("/health")
async def health(user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.outreach_health import outreach_health_snapshot
    return await outreach_health_snapshot(_db)


@router.post("/closer-day5/run")
async def fire_closer_day5(user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.closer_day5_trigger import run_closer_day5_sweep
    return await run_closer_day5_sweep(_db)


@router.post("/reply-inbox/run")
async def fire_reply_inbox(user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.reply_inbox_processor import reply_inbox_sweep
    return await reply_inbox_sweep(_db)


@router.post("/social/post-now")
async def fire_social_post(user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.social_autopilot import run_daily_social_post
    return await run_daily_social_post(_db)


@router.get("/unmatched-pixels")
async def list_unmatched_pixels(limit: int = 50,
                                    user: dict = Depends(_admin_dep())):
    """iter 330b — Review pixel hits that landed without a resolvable tenant.

    Returns the last `limit` rows from `unmatched_pixel_events` (cap 500)
    plus a 24-hour count so the Outreach Health card can show a badge.
    """
    if _db is None:
        raise HTTPException(503, "db not ready")
    limit = max(1, min(int(limit or 50), 500))
    cur = _db.unmatched_pixel_events.find(
        {}, {"_id": 0},
    ).sort("ts", -1).limit(limit)
    entries = await cur.to_list(length=limit)
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    count_24h = await _db.unmatched_pixel_events.count_documents({"ts": {"$gte": cutoff}})
    total = await _db.unmatched_pixel_events.count_documents({})
    return {
        "ok":         True,
        "entries":    entries,
        "count":      len(entries),
        "count_24h":  count_24h,
        "total":      total,
    }
