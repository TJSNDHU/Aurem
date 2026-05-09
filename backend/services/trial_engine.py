"""
trial_engine.py — 7-day trial lifecycle.
═══════════════════════════════════════════════════════════════════════════
  • start_trial(db, business_id, email): called from signup. Sets
    trial_started_at + trial_ends_at, plan="trial", services_unlocked from
    PLANS["trial"], usage_limits from PLANS["trial"], subscription_status="trialing"
  • is_expired: pure datetime check on trial_ends_at
  • apply_expiry: sets services_unlocked=[], status=trial_expired
  • find_trials_due: helper for reminder scheduler
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from aurem_config.plans import PLANS

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def start_trial(db, business_id: str, email: str) -> Dict[str, Any]:
    """Idempotent — call once on signup. If a trial already exists with a
    future trial_ends_at, returns it untouched."""
    if db is None or not business_id:
        return {"ok": False, "reason": "missing_args"}

    now = _now()
    ends = now + timedelta(days=PLANS["trial"]["duration_days"])

    existing_billing = await db.aurem_billing.find_one(
        {"business_id": business_id}, {"_id": 0, "trial_ends_at": 1, "status": 1}
    )
    if existing_billing:
        ends_existing = existing_billing.get("trial_ends_at")
        if ends_existing:
            try:
                ee = (
                    datetime.fromisoformat(ends_existing.replace("Z", "+00:00"))
                    if isinstance(ends_existing, str) else ends_existing
                )
                if ee.tzinfo is None:
                    ee = ee.replace(tzinfo=timezone.utc)
                if ee > now and existing_billing.get("status") == "trialing":
                    return {"ok": True, "trial_ends_at": _iso(ee), "reused": True}
            except Exception:
                pass

    trial_plan = PLANS["trial"]
    await db.aurem_billing.update_one(
        {"business_id": business_id},
        {"$set": {
            "business_id": business_id,
            "email": email,
            "plan": "trial",
            "status": "trialing",
            "trial_started_at": _iso(now),
            "trial_ends_at": _iso(ends),
            "current_period_start": _iso(now),
            "current_period_end": _iso(ends),
            "updated_at": _iso(now),
        }, "$setOnInsert": {"created_at": _iso(now)}},
        upsert=True,
    )
    # Mirror onto platform_users so JWT bake/decode reflects state.
    await db.platform_users.update_one(
        {"business_id": business_id},
        {"$set": {
            "plan": "trial",
            "subscription_status": "trialing",
            "trial_started_at": _iso(now),
            "trial_ends_at": _iso(ends),
            "services_unlocked": list(trial_plan["services"]),
            "usage_limits": dict(trial_plan["limits"]),
            "plan_resolved_at": _iso(now),
        }},
    )
    logger.info(f"[trial_engine] trial started for {business_id} ({email}) ends={_iso(ends)}")
    return {"ok": True, "business_id": business_id, "trial_ends_at": _iso(ends), "reused": False}


def is_expired(billing: Dict[str, Any]) -> bool:
    if (billing or {}).get("status") not in ("trialing", "trial"):
        return False
    ends = (billing or {}).get("trial_ends_at")
    if not ends:
        return False
    try:
        ee = datetime.fromisoformat(ends.replace("Z", "+00:00")) if isinstance(ends, str) else ends
        if ee.tzinfo is None:
            ee = ee.replace(tzinfo=timezone.utc)
        return ee <= _now()
    except Exception:
        return False


async def apply_expiry(db, business_id: str) -> Dict[str, Any]:
    """Mark trial as expired. Data is preserved — only access locked."""
    if db is None or not business_id:
        return {"ok": False}
    now = _now()
    await db.aurem_billing.update_one(
        {"business_id": business_id},
        {"$set": {"status": "trial_expired", "expired_at": _iso(now)}},
    )
    await db.platform_users.update_one(
        {"business_id": business_id},
        {"$set": {
            "plan": "trial_expired",
            "subscription_status": "trial_expired",
            "services_unlocked": [],
            "plan_resolved_at": _iso(now),
        }},
    )
    logger.info(f"[trial_engine] trial expired for {business_id}")
    return {"ok": True, "business_id": business_id}


async def find_trials_due(db, days_until_end: Optional[int] = None,
                          ended_within_hours: Optional[int] = None) -> List[Dict[str, Any]]:
    """Helper for the reminder scheduler.

    days_until_end:    finds trials where trial_ends_at is between
                       now+(D-1h) and now+(D+1h). Used for "day 6" reminder.
    ended_within_hours: finds trials whose trial_ends_at is in the past
                       within the last H hours (sweep candidates).
    """
    if db is None:
        return []
    now = _now()
    rows: List[Dict[str, Any]] = []
    if days_until_end is not None:
        target = now + timedelta(days=days_until_end)
        lo = (target - timedelta(hours=1)).isoformat()
        hi = (target + timedelta(hours=1)).isoformat()
        async for d in db.aurem_billing.find({
            "status": "trialing",
            "trial_ends_at": {"$gte": lo, "$lte": hi},
        }, {"_id": 0}):
            rows.append(d)
    elif ended_within_hours is not None:
        cutoff_lo = (now - timedelta(hours=ended_within_hours)).isoformat()
        cutoff_hi = now.isoformat()
        async for d in db.aurem_billing.find({
            "status": "trialing",
            "trial_ends_at": {"$gte": cutoff_lo, "$lte": cutoff_hi},
        }, {"_id": 0}):
            rows.append(d)
    return rows
