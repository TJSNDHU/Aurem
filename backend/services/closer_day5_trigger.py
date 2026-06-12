"""
services/closer_day5_trigger.py — iter 330 FIX 1

Walks `campaign_leads` where the blast chain is at touch #3 (i.e. the
last email touch fired and Day 5 is up next) and hands each lead to
`closer_ora.arm()` so a Retell AI phone call goes out.

Cadence: every 30 minutes via APScheduler.
Cap: 20 calls/run by default (env `CLOSER_DAY5_CAP_PER_RUN`).

Idempotency: Once a call is queued for a lead, the lead is stamped with
`closer_day5_armed_at` so the same lead is never queued twice.

Eligibility (all must hold):
  • `blast_chain.next_touch_n == 4`         (next is voice)
  • `blast_chain.next_touch_at <= now`       (due)
  • `phone` present
  • not in `do_not_contact`
  • `closer_day5_armed_at` missing
  • `status` not in {'signed_up','not_interested','do_not_contact'}

The actual call uses `closer_ora.arm()` which itself:
  • Checks business-hours window (America/Toronto 9 AM – 6 PM weekday)
  • Defers to next business window if off-hours
  • Calls `_retell_create_phone_call` with the fixed iter-325h kwargs
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

_CAP = int(os.environ.get("CLOSER_DAY5_CAP_PER_RUN", "20"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def run_closer_day5_sweep(db) -> dict:
    """One pass. Best-effort — never raises.

    Returns: {"ok": bool, "armed": int, "skipped": int, "errors": int, "details": [...]}.
    """
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    armed = 0
    skipped = 0
    errors = 0
    details: list[dict] = []
    now = _now()

    try:
        cur = db.campaign_leads.find(
            {
                "business_id": FOUNDER_BIN,
                "blast_chain.next_touch_n":  4,
                "blast_chain.next_touch_at": {"$lte": now.isoformat()},
                "closer_day5_armed_at":      {"$exists": False},
                "phone":                     {"$nin": [None, ""]},
                "status": {"$nin": ["signed_up", "not_interested", "do_not_contact"]},
            },
            {"_id": 0},
        ).limit(_CAP)
        rows = await cur.to_list(length=_CAP)
    except Exception as e:
        logger.warning(f"[closer-day5] query failed: {e}")
        return {"ok": False, "error": str(e)[:200]}

    for lead in rows:
        lead_id = lead.get("lead_id") or lead.get("id")
        phone = (lead.get("phone") or "").strip()
        try:
            # CASL — final guard before we dial.
            dnc = await db.do_not_contact.find_one(
                {"$or": [{"phone": phone}, {"email": lead.get("email")}]}
            )
            if dnc:
                skipped += 1
                details.append({"lead_id": lead_id, "skipped": "do_not_contact"})
                # Stamp so we don't keep evaluating this lead.
                await db.campaign_leads.update_one(
                    {"lead_id": lead_id, "business_id": FOUNDER_BIN},
                    {"$set": {"closer_day5_armed_at": now, "closer_day5_skip_reason": "dnc"}},
                )
                continue

            from services.agents import closer_ora
            result = await closer_ora.arm({
                "lead":    lead,
                "trigger": "no_reply_day5",
                "source":  "closer_day5_sweep",
            })
            # Mark the lead either way so we don't retry on every tick.
            await db.campaign_leads.update_one(
                {"lead_id": lead_id, "business_id": FOUNDER_BIN},
                {"$set": {
                    "closer_day5_armed_at":   now,
                    "closer_day5_result":     (result or {}).get("ok"),
                    "closer_day5_queued":     bool((result or {}).get("queued")),
                    "closer_day5_call_id":    (result or {}).get("call_id"),
                }},
            )
            if (result or {}).get("ok"):
                armed += 1
                details.append({
                    "lead_id": lead_id,
                    "armed":   True,
                    "queued":  bool((result or {}).get("queued")),
                    "call_id": (result or {}).get("call_id"),
                })
            else:
                errors += 1
                details.append({"lead_id": lead_id, "error": (result or {}).get("error")})
        except Exception as e:
            errors += 1
            details.append({"lead_id": lead_id, "error": f"{type(e).__name__}: {e}"})

    # Persist a run row for the Outreach Health card.
    try:
        await db.closer_day5_runs.insert_one({
            "ts":      now,
            "armed":   armed,
            "skipped": skipped,
            "errors":  errors,
            "cap":     _CAP,
        })
    except Exception as e:
        logger.debug(f"[closer-day5] persist failed: {e}")

    return {
        "ok":      True,
        "armed":   armed,
        "skipped": skipped,
        "errors":  errors,
        "details": details[:50],
    }
