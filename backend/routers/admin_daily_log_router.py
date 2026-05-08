"""
Admin Daily Log Router — iter 282m
====================================
Surfaces the `daily_verification_log` collection so the founder can audit
real vs. claimed numbers from the daily brief system at any time.

GET  /api/admin/daily-log              — last 30 days of events grouped by date
GET  /api/admin/daily-log/today        — today only
POST /api/admin/daily-log/run-eod      — manually trigger the 6 PM email
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from zoneinfo import ZoneInfo

from routers.ora_dev_actions_router import verify_admin
from services.founder_daily_brief import (
    VERIFICATION_COLLECTION,
    send_end_of_day_email,
    push_morning_armed,
    push_scout_complete,
    push_architect_complete,
    push_envoy_complete,
    push_midday_check,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/daily-log", tags=["Admin Daily Log"])
_db = None
_TZ_EST = ZoneInfo("America/Toronto")


def set_db(database) -> None:
    global _db
    _db = database


def _get_db():
    return _db


@router.get("")
async def list_days(
    days: int = Query(30, ge=1, le=90),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")
    cur = db[VERIFICATION_COLLECTION].find(
        {}, {"_id": 0},
    ).sort("ts_utc", -1).limit(int(days) * 20)
    rows = await cur.to_list(length=int(days) * 20)
    # Group by date
    by_date: Dict[str, list] = {}
    for r in rows:
        d = r.get("date") or r.get("ts_utc", "")[:10]
        by_date.setdefault(d, []).append(r)
    days_out = [
        {"date": d, "events": evs, "event_count": len(evs)}
        for d, evs in sorted(by_date.items(), reverse=True)[:days]
    ]
    return {"ok": True, "days": days_out, "total_events": len(rows)}


@router.get("/today")
async def list_today(
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")
    today = datetime.now(_TZ_EST).date().isoformat()
    cur = db[VERIFICATION_COLLECTION].find(
        {"date": today}, {"_id": 0},
    ).sort("ts_utc", 1)
    events = await cur.to_list(length=200)
    return {"ok": True, "date": today, "events": events, "count": len(events)}


@router.post("/run-eod")
async def trigger_end_of_day(
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Manually trigger the 6 PM end-of-day email. Useful for testing."""
    verify_admin(authorization)
    res = await send_end_of_day_email()
    return res


@router.post("/test-push/{event}")
async def trigger_test_push(
    event: str,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Manually fire one of the step pushes for testing.

    event ∈ {morning_armed, scout_complete, architect_complete,
             envoy_complete, midday_check}
    """
    verify_admin(authorization)
    handlers = {
        "morning_armed":      push_morning_armed,
        "scout_complete":     push_scout_complete,
        "architect_complete": push_architect_complete,
        "envoy_complete":     push_envoy_complete,
        "midday_check":       push_midday_check,
    }
    fn = handlers.get(event)
    if not fn:
        raise HTTPException(400, f"Unknown event. Valid: {list(handlers)}")
    await fn()
    return {"ok": True, "event": event, "fired": True}
