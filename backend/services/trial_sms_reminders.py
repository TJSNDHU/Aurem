"""
Trial SMS Reminders — A2P 10DLC live (iter 282r)
================================================

Three-step trial reminder cadence over Twilio SMS, sent from
+14314500004 (A2P approved) to platform_users on free trial:

  • welcome      → 1 day after signup ("Welcome, here's how to start")
  • ending_soon  → 1 day before trial_ends_at ("Trial ending tomorrow")
  • last_day     → on the day trial_ends_at falls ("Today is your last day")

Schedule:
  Daily 10:00 AM America/Toronto — single cron entry runs all three windows
  in one pass and deduplicates via the `trial_sms_log` collection.

Idempotency:
  Each (user_id, kind) pair is recorded in `trial_sms_log` with
  `{kind, user_id, sid, status, sent_at}`. Re-running the cron the same day
  is a no-op for any user already logged.

Compliance:
  Every message includes a STOP opt-out footer + the AUREM brand prefix.
  Numbers in the `dnc_list` collection are skipped.

Test:
  python3 -c "import asyncio; from services.trial_sms_reminders import \
    run_trial_sms_reminders; from shared.memory_tiers import _get_db; \
    asyncio.run(run_trial_sms_reminders(_get_db()))"
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

logger = logging.getLogger("trial-sms-reminders")

# ─── Templates ──────────────────────────────────────────────────────────
# Kept short, single-link, no emoji to minimise carrier-filter risk (30007).

_BASE = os.environ.get("APP_BASE_URL", "https://aurem.live")

_WELCOME_TPL = (
    "AUREM: Welcome {first}. Your 14-day trial is live. "
    "Sign in at {url}/login to launch your first AI agent. "
    "Reply STOP to opt out."
)

_ENDING_SOON_TPL = (
    "AUREM: Hi {first}, your free trial ends tomorrow. "
    "Upgrade at {url}/billing to keep your agents running. "
    "Reply STOP to opt out."
)

_LAST_DAY_TPL = (
    "AUREM: {first}, today is the last day of your free trial. "
    "Upgrade at {url}/billing before midnight to avoid service pause. "
    "Reply STOP to opt out."
)

_KINDS = ("welcome", "ending_soon", "last_day")


# ─── Helpers ────────────────────────────────────────────────────────────


def _coerce_dt(value) -> Optional[datetime]:
    """Accept datetime, ISO string, or None — return aware UTC datetime or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None
    return None


def _first_name(user: dict) -> str:
    fn = user.get("first_name") or ""
    if fn.strip():
        return fn.strip().split()[0]
    full = user.get("full_name") or user.get("company_name") or ""
    return full.strip().split()[0] if full.strip() else "there"


def _phone(user: dict) -> str:
    for f in ("phone", "mobile", "whatsapp"):
        v = (user.get(f) or "").strip()
        if v:
            return v
    return ""


# ─── Core eligibility windows ───────────────────────────────────────────


async def _eligible_for_welcome(db, now_utc: datetime) -> Iterable[dict]:
    """Users who signed up between 24h and 48h ago (Day-1 window)."""
    cutoff_lo = now_utc - timedelta(hours=48)
    cutoff_hi = now_utc - timedelta(hours=24)
    cur = db.platform_users.find(
        {
            "created_at": {"$gte": cutoff_lo, "$lt": cutoff_hi},
            "tier_status": "trial",
        },
        {"_id": 1, "email": 1, "phone": 1, "mobile": 1, "whatsapp": 1,
         "first_name": 1, "full_name": 1, "company_name": 1, "created_at": 1},
    )
    return [u async for u in cur]


async def _eligible_for_ending_soon(db, now_utc: datetime) -> Iterable[dict]:
    """Users whose trial_ends_at is between 24h and 48h from now."""
    lo = now_utc + timedelta(hours=24)
    hi = now_utc + timedelta(hours=48)
    cur = db.platform_users.find(
        {
            "trial_ends_at": {"$gte": lo, "$lt": hi},
            "tier_status": "trial",
        },
        {"_id": 1, "email": 1, "phone": 1, "mobile": 1, "whatsapp": 1,
         "first_name": 1, "full_name": 1, "company_name": 1, "trial_ends_at": 1},
    )
    return [u async for u in cur]


async def _eligible_for_last_day(db, now_utc: datetime) -> Iterable[dict]:
    """Users whose trial_ends_at falls in the next 24h (final day)."""
    lo = now_utc
    hi = now_utc + timedelta(hours=24)
    cur = db.platform_users.find(
        {
            "trial_ends_at": {"$gte": lo, "$lt": hi},
            "tier_status": "trial",
        },
        {"_id": 1, "email": 1, "phone": 1, "mobile": 1, "whatsapp": 1,
         "first_name": 1, "full_name": 1, "company_name": 1, "trial_ends_at": 1},
    )
    return [u async for u in cur]


# ─── Sender ─────────────────────────────────────────────────────────────


async def _send_one(db, kind: str, user: dict) -> dict:
    """Idempotent single-shot send for (user, kind). Returns result dict."""
    user_id = user.get("_id") or user.get("id")
    if not user_id:
        return {"sent": False, "reason": "no_user_id"}

    # Idempotency: never send the same kind twice
    if await db.trial_sms_log.find_one({"user_id": user_id, "kind": kind}, {"_id": 1}):
        return {"sent": False, "reason": "already_sent"}

    phone = _phone(user)
    if not phone:
        await db.trial_sms_log.insert_one({
            "user_id": user_id,
            "kind": kind,
            "status": "skipped_no_phone",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"sent": False, "reason": "no_phone"}

    # DNC guard
    if await db.dnc_list.find_one({"phone": phone}, {"_id": 1}):
        await db.trial_sms_log.insert_one({
            "user_id": user_id,
            "kind": kind,
            "to": phone,
            "status": "skipped_dnc",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"sent": False, "reason": "dnc"}

    tpl = {
        "welcome": _WELCOME_TPL,
        "ending_soon": _ENDING_SOON_TPL,
        "last_day": _LAST_DAY_TPL,
    }[kind]
    body = tpl.format(first=_first_name(user), url=_BASE)

    from shared.providers.twilio import send_sms
    res = await send_sms(phone, body)
    sid = res.get("message_sid")
    success = bool(res.get("success"))

    await db.trial_sms_log.insert_one({
        "user_id": user_id,
        "kind": kind,
        "to": phone,
        "sid": sid,
        "status": "sent" if success else "failed",
        "error": res.get("error"),
        "channel": res.get("channel", "sms"),
        "body_preview": body[:160],
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info(
        f"[trial-sms] kind={kind} user={user_id} to={phone[:5]}*** "
        f"status={'sent' if success else 'failed'} sid={sid}"
    )
    return {"sent": success, "sid": sid, "kind": kind, "user_id": user_id}


# ─── Public entrypoint ──────────────────────────────────────────────────


async def run_trial_sms_reminders(db) -> dict:
    """Scheduler-callable: process all 3 windows, return summary stats."""
    if db is None:
        logger.warning("[trial-sms] no DB available")
        return {"error": "no_db"}

    now = datetime.now(timezone.utc)
    summary = {kind: {"matched": 0, "sent": 0, "skipped": 0, "failed": 0} for kind in _KINDS}
    sent_records = []

    windows = (
        ("welcome", await _eligible_for_welcome(db, now)),
        ("ending_soon", await _eligible_for_ending_soon(db, now)),
        ("last_day", await _eligible_for_last_day(db, now)),
    )

    for kind, users in windows:
        users = list(users)
        summary[kind]["matched"] = len(users)
        for u in users:
            res = await _send_one(db, kind, u)
            if res.get("sent"):
                summary[kind]["sent"] += 1
                sent_records.append(res)
            elif res.get("reason") == "already_sent":
                summary[kind]["skipped"] += 1
            else:
                summary[kind]["failed"] += 1

    logger.info(f"[trial-sms] cron run complete: {summary}")
    return {"ran_at": now.isoformat(), "summary": summary, "sent": sent_records}
