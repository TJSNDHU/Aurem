"""
aurem_cto.routers.engagement — Gap 4 (iter D-33)

Read-only surfaces over existing data:
  GET /aurem-cto/referrals/my   — referral link + clicks + conversions
  GET /aurem-cto/streak/me      — consecutive daily build streak

Re-uses existing `referrals`, `referral_profiles`, `verified_referrals`,
and `onboarding_token_wallets.ledger` — does not duplicate any storage.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header

from ..services.auth import current_dev
from ..services.db import require_db

router = APIRouter(tags=["AUREM CTO Engagement"])


# ─── Referrals ───────────────────────────────────────────────────────
@router.get("/referrals/my")
async def my_referrals(authorization: str = Header(None)) -> dict[str, Any]:
    me  = await current_dev(authorization)
    db  = require_db()
    uid = me["user_id"]
    # Re-use existing collections.
    profile = await db.referral_profiles.find_one(
        {"user_id": uid}, {"_id": 0},
    )
    invites = await db.referrals.count_documents({"referrer_user_id": uid})
    verified = await db.verified_referrals.count_documents({"referrer_user_id": uid})
    # Public referral link uses account ID as ref param.
    link = f"https://aurem.live/?ref={uid}"
    return {
        "ref_link":         link,
        "ref_code":         uid,
        "invites_sent":     invites,
        "verified_signups": verified,
        "profile":          profile,
    }


# ─── Build streak ────────────────────────────────────────────────────
@router.get("/streak/me")
async def my_streak(authorization: str = Header(None)) -> dict[str, Any]:
    """Reads onboarding_token_wallets.ledger and counts consecutive days
    on which the user spent at least one cheap/frontier debit."""
    me  = await current_dev(authorization)
    db  = require_db()
    uid = me["user_id"]
    wallet = await db.onboarding_token_wallets.find_one(
        {"user_id": uid}, {"_id": 0, "ledger": 1},
    )
    ledger = (wallet or {}).get("ledger") or []
    debit_days: set[str] = set()
    for e in ledger:
        kind = e.get("kind") or ""
        if not kind.startswith("debit_"):
            continue
        ts = e.get("ts")
        if not ts:
            continue
        # Normalise to UTC YYYY-MM-DD.
        if isinstance(ts, str):
            try:
                day = ts[:10]
            except Exception:
                continue
        elif hasattr(ts, "isoformat"):
            day = ts.astimezone(timezone.utc).date().isoformat()
        else:
            continue
        debit_days.add(day)

    # Walk back from today (UTC) and count consecutive days.
    today = datetime.now(timezone.utc).date()
    streak = 0
    cursor = today
    while cursor.isoformat() in debit_days:
        streak += 1
        cursor = cursor.fromordinal(cursor.toordinal() - 1)

    return {
        "user_id":        uid,
        "current_streak": streak,
        "total_build_days": len(debit_days),
        "today_active":   today.isoformat() in debit_days,
        "longest_streak": _longest_streak(debit_days),
    }


def _longest_streak(days: set[str]) -> int:
    if not days:
        return 0
    sorted_days = sorted(datetime.fromisoformat(d).date() for d in days)
    longest = 1
    run = 1
    for i in range(1, len(sorted_days)):
        if (sorted_days[i] - sorted_days[i - 1]).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    return longest
