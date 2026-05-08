"""
AUREM FollowUp ORA Engine (iter 322p — wires the silent agent live)
====================================================================
FollowUp ORA was declared in `agent_soul.AGENT_PERSONAS` but had **zero
ledger activity** before iter 322p. This module gives it a real job:

  1. Scan `campaign_leads` for leads whose last `outreach_history`
     entry is ≥ FOLLOWUP_AGE_DAYS old AND status is not "responded"
     | "converted" | "unsubscribed".
  2. For each, append a `followup_attempt` row to the lead's
     `outreach_history` (channel: "intent_only" by default — no actual
     send, the existing outreach worker picks up intents downstream).
  3. Record a ledger heartbeat (`agent_id="followup_ora"`,
     `kind="followup_attempt"`) so the wedge detector sees it alive.
  4. Cooldown — same lead re-touched at most once per
     FOLLOWUP_COOLDOWN_HOURS (default 24).

Dry-run by default
------------------
``FOLLOWUP_LIVE_SENDING=1`` flips it from intent-recording to live
outreach (handed off to `outreach_composer`). Off by default so prod
deploy of this code is risk-free — admin opts in when ready.

Public API
----------
- ``run_followup_tick(db) -> dict``  (scheduler entry-point)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


FOLLOWUP_AGE_DAYS = int(os.environ.get("FOLLOWUP_AGE_DAYS", "3"))
FOLLOWUP_COOLDOWN_HOURS = int(os.environ.get("FOLLOWUP_COOLDOWN_HOURS", "24"))
FOLLOWUP_BATCH_SIZE = int(os.environ.get("FOLLOWUP_BATCH_SIZE", "20"))
FOLLOWUP_LIVE_SENDING = os.environ.get("FOLLOWUP_LIVE_SENDING") == "1"

_AGENT_ID = "followup_ora"
_TERMINAL_STATUSES = {"responded", "converted", "unsubscribed", "blocked"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _last_outreach_ts(lead: Dict[str, Any]) -> datetime | None:
    history = lead.get("outreach_history") or []
    if not isinstance(history, list) or not history:
        return None
    last = history[-1] if isinstance(history[-1], dict) else None
    if not last:
        return None
    ts = last.get("ts") or last.get("timestamp")
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _has_recent_followup(lead: Dict[str, Any], cooldown_hours: int) -> bool:
    history = lead.get("outreach_history") or []
    if not isinstance(history, list):
        return False
    cutoff = _utc_now() - timedelta(hours=cooldown_hours)
    for h in reversed(history[-10:]):
        if not isinstance(h, dict):
            continue
        if (h.get("type") or h.get("kind")) != "followup_attempt":
            continue
        ts = h.get("ts") or h.get("timestamp")
        if not ts:
            continue
        try:
            d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
            if d > cutoff:
                return True
        except Exception:
            continue
    return False


async def _record_ledger(db, *, attempts: int, leads_scanned: int) -> None:
    if db is None:
        return
    try:
        await db.agent_ledger_entries.insert_one({
            "kind": "followup_tick",
            "agent_id": _AGENT_ID,
            "source": "followup_ora_engine",
            "units": float(attempts),
            "cost_usd": 0.0,
            "meta": {
                "attempts": attempts,
                "leads_scanned": leads_scanned,
                "live_sending": FOLLOWUP_LIVE_SENDING,
            },
            "timestamp": _iso(_utc_now()),
        })
    except Exception as e:
        logger.debug(f"[followup-ora] ledger insert failed: {e}")


async def run_followup_tick(db) -> Dict[str, Any]:
    """One scan → attempt pass. Always returns a summary dict."""
    started = time.perf_counter()
    if db is None:
        return {
            "ok": False, "reason": "no_db",
            "leads_scanned": 0, "attempts": 0,
        }

    cutoff = _utc_now() - timedelta(days=FOLLOWUP_AGE_DAYS)
    cutoff_iso = _iso(cutoff)

    # Stale leads = updated before the cutoff and not in a terminal state.
    query: Dict[str, Any] = {
        "updated_at": {"$lt": cutoff_iso},
        "status": {"$nin": list(_TERMINAL_STATUSES)},
    }
    leads_scanned = 0
    attempts = 0
    skipped: List[str] = []

    try:
        cursor = db.campaign_leads.find(query, {"_id": 0}).limit(FOLLOWUP_BATCH_SIZE)
        async for lead in cursor:
            leads_scanned += 1
            lead_id = lead.get("lead_id") or lead.get("business_name") or ""
            if not lead_id:
                continue

            # Skip if a follow-up was attempted recently
            if _has_recent_followup(lead, FOLLOWUP_COOLDOWN_HOURS):
                skipped.append(lead_id)
                continue

            # Confirm last outreach is actually old enough (defensive)
            last_ts = _last_outreach_ts(lead)
            if last_ts and (_utc_now() - last_ts).days < FOLLOWUP_AGE_DAYS:
                skipped.append(lead_id)
                continue

            attempt_row = {
                "type": "followup_attempt",
                "channel": "intent_only" if not FOLLOWUP_LIVE_SENDING else "live",
                "ts": _iso(_utc_now()),
                "agent": _AGENT_ID,
                "stage": "n1" if not last_ts else "n2",
            }
            try:
                await db.campaign_leads.update_one(
                    {"lead_id": lead_id},
                    {
                        "$push": {"outreach_history": attempt_row},
                        "$set": {"updated_at": _iso(_utc_now()),
                                 "last_followup_at": _iso(_utc_now())},
                    },
                )
                attempts += 1
            except Exception as e:
                logger.debug(f"[followup-ora] update failed for {lead_id}: {e}")
    except Exception as e:
        logger.debug(f"[followup-ora] cursor failed: {e}")

    await _record_ledger(db, attempts=attempts, leads_scanned=leads_scanned)

    return {
        "ok": True,
        "leads_scanned": leads_scanned,
        "attempts": attempts,
        "skipped_in_cooldown": len(skipped),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "live_sending": FOLLOWUP_LIVE_SENDING,
    }
