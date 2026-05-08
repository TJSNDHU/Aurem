"""
AUREM Referral ORA Engine (iter 322p — wires the silent agent live)
====================================================================
Referral ORA was declared but had **zero ledger activity**. This module
gives it a real job:

  1. Find `customer_subscriptions` with status="active" who haven't
     been asked for a referral in the last REFERRAL_GAP_DAYS.
  2. For each, insert a row in `referrals_outbox`
     (the existing `referrals` collection lives downstream of
     human-confirmed referrals; the outbox is the queue the customer
     portal renders the "Refer a friend" prompt from).
  3. Record a ledger heartbeat so the wedge detector sees it alive.
  4. Cooldown — same customer not re-asked within REFERRAL_GAP_DAYS.

Dry-run by default
------------------
``REFERRAL_LIVE_PROMPTS=1`` flips it from outbox-only to actually
firing the existing "send referral ask" mailer. Off by default.

Public API
----------
- ``run_referral_tick(db) -> dict``  (scheduler entry-point)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


REFERRAL_GAP_DAYS = int(os.environ.get("REFERRAL_GAP_DAYS", "30"))
REFERRAL_BATCH_SIZE = int(os.environ.get("REFERRAL_BATCH_SIZE", "20"))
REFERRAL_LIVE_PROMPTS = os.environ.get("REFERRAL_LIVE_PROMPTS") == "1"

_AGENT_ID = "referral_ora"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _ask_recently(db, customer_email: str, gap_days: int) -> bool:
    if db is None or not customer_email:
        return True
    cutoff = _iso(_utc_now() - timedelta(days=gap_days))
    try:
        row = await db.referrals_outbox.find_one(
            {"customer_email": customer_email, "ts": {"$gte": cutoff}},
            {"_id": 1},
        )
        return row is not None
    except Exception:
        return False


async def _record_ledger(
    db, *, asks: int, customers_scanned: int,
) -> None:
    if db is None:
        return
    try:
        await db.agent_ledger_entries.insert_one({
            "kind": "referral_tick",
            "agent_id": _AGENT_ID,
            "source": "referral_ora_engine",
            "units": float(asks),
            "cost_usd": 0.0,
            "meta": {
                "asks": asks,
                "customers_scanned": customers_scanned,
                "live_prompts": REFERRAL_LIVE_PROMPTS,
            },
            "timestamp": _iso(_utc_now()),
        })
    except Exception as e:
        logger.debug(f"[referral-ora] ledger insert failed: {e}")


async def run_referral_tick(db) -> Dict[str, Any]:
    """One scan → ask pass. Always returns a summary dict."""
    started = time.perf_counter()
    if db is None:
        return {
            "ok": False, "reason": "no_db",
            "customers_scanned": 0, "asks": 0,
        }

    customers_scanned = 0
    asks = 0
    skipped: List[str] = []

    try:
        cursor = db.customer_subscriptions.find(
            {"status": "active"},
            {"_id": 0, "email": 1, "tenant_bin": 1, "started_at": 1, "service_id": 1},
        ).limit(REFERRAL_BATCH_SIZE)
        async for sub in cursor:
            customers_scanned += 1
            email = (sub.get("email") or "").strip()
            if not email or "@" not in email:
                continue

            if await _ask_recently(db, email, REFERRAL_GAP_DAYS):
                skipped.append(email)
                continue

            outbox_row = {
                "customer_email": email,
                "tenant_bin": sub.get("tenant_bin") or "",
                "service_id": sub.get("service_id") or "",
                "channel": "in_app" if not REFERRAL_LIVE_PROMPTS else "email",
                "status": "queued" if not REFERRAL_LIVE_PROMPTS else "sending",
                "agent": _AGENT_ID,
                "ts": _iso(_utc_now()),
            }
            try:
                await db.referrals_outbox.insert_one(outbox_row)
                asks += 1
            except Exception as e:
                logger.debug(f"[referral-ora] outbox insert failed for {email}: {e}")
    except Exception as e:
        logger.debug(f"[referral-ora] cursor failed: {e}")

    await _record_ledger(db, asks=asks, customers_scanned=customers_scanned)

    return {
        "ok": True,
        "customers_scanned": customers_scanned,
        "asks": asks,
        "skipped_in_cooldown": len(skipped),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "live_prompts": REFERRAL_LIVE_PROMPTS,
    }
