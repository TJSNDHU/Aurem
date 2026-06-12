"""
AUREM Follow-up ORA — Phase 1 (T1 Pipeline)
============================================
Subscribes to BLAST_SENT — arms 3 follow-up touches at Day 2 / 5 / 9.
Fires due touches via blast_chain.advance_chain (existing scheduler does this).
After Day 5 with no engagement, emits NO_REPLY_DAY5 → Closer arms call.

The actual touch firing is handled by `blast_chain.chain_advance_scheduler`
(which already runs in P1 worker). Follow-up's job here is:
  • on BLAST_SENT → record schedule rows in `scheduled_followups`
  • on Day 2 / 5 → check engagement, emit NO_REPLY_DAY{2,5} if cold

Public:
  await arm(payload)
  await tick()                       # daily — emits NO_REPLY_DAY{2,5}
  register_subscriptions()
  followup_tick_scheduler()          # daily 9 AM Toronto
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# Days at which to check engagement / emit no-reply events
CHECK_DAYS = [2, 5, 9]


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────
# arm — runs on BLAST_SENT
# ─────────────────────────────────────────────────────────────────────

async def arm(payload: Dict[str, Any]) -> Dict[str, Any]:
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    try:
        from services.agent_registry import heartbeat, log_action
        await heartbeat("followup")
    except Exception:
        log_action = None

    lead_id = (payload.get("lead_id") or "").strip()
    if not lead_id:
        return {"ok": False, "error": "lead_id missing"}

    # ── Council gate (CASL required, advisory: qa) ─────────────────────
    # Arming a follow-up chain commits us to multi-touch outbound. CASL
    # must approve the lead's contact eligibility before we schedule any
    # touches; QA advises on cadence quality.
    try:
        # Lightweight context — pull just the consent + dnc fields if available.
        lead_ctx = await db.campaign_leads.find_one(
            {"lead_id": lead_id, "business_id": FOUNDER_BIN},
            {"_id": 0, "lead_id": 1, "consent": 1, "dnc": 1, "country": 1,
             "channel": 1, "email": 1, "phone": 1},
        ) or {"lead_id": lead_id}
    except Exception:
        lead_ctx = {"lead_id": lead_id}
    try:
        from services.council_deliberate import deliberate
        verdict = await deliberate(
            "followup_arm", "followup_ora", lead_ctx,
            required=["casl"], advisory=["qa"],
        )
    except Exception as e:
        verdict = {"verdict": "APPROVED", "votes": {},
                   "confidence": 0.5, "_council_error": str(e)}
    if verdict.get("verdict") == "REJECTED":
        if log_action:
            await log_action(
                "followup", "REJECTED_BY_COUNCIL",
                f"arm rejected: {verdict.get('votes')}",
                lead_id=lead_id, success=False,
                metadata={"votes": verdict.get("votes")},
            )
        return {"ok": False, "rejected": True, "verdict": verdict}

    armed_at = _utc_now()
    docs = [{
        "lead_id": lead_id,
        "scheduled_day": d,
        "scheduled_for": armed_at + timedelta(days=d),
        "armed_at": armed_at,
        "status": "pending",
    } for d in CHECK_DAYS]

    try:
        await db.scheduled_followups.insert_many(docs)
    except Exception as e:
        logger.warning(f"[followup] insert_many failed: {e}")
        return {"ok": False, "error": str(e)}

    if log_action:
        await log_action("followup", "FOLLOWUP_ARMED",
                         f"Days {CHECK_DAYS} armed",
                         lead_id=lead_id)
    return {"ok": True, "armed_days": CHECK_DAYS}


# ─────────────────────────────────────────────────────────────────────
# tick — runs daily, fires NO_REPLY_DAY{N} for cold leads
# ─────────────────────────────────────────────────────────────────────

async def tick() -> Dict[str, Any]:
    """Daily — find leads at Day 2/5/9 with no engagement and emit signals."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    try:
        from services.agent_registry import heartbeat, log_action
        await heartbeat("followup")
    except Exception:
        log_action = None

    now = _utc_now()
    # Find followups whose scheduled_for has arrived and still pending
    cur = db.scheduled_followups.find(
        {"scheduled_for": {"$lte": now}, "status": "pending"},
        {"_id": 1, "lead_id": 1, "scheduled_day": 1},
    ).limit(200)
    rows: List[Dict[str, Any]] = await cur.to_list(200)

    if not rows:
        return {"ok": True, "checked": 0, "emitted": 0}

    # Fetch all leads in one shot
    lead_ids = list({r["lead_id"] for r in rows})
    leads_cur = db.campaign_leads.find(
        {"lead_id": {"$in": lead_ids}, "business_id": FOUNDER_BIN},
        {"_id": 0, "lead_id": 1, "hot_lead_flag": 1, "dnc": 1,
         "blast_chain": 1, "status": 1},
    )
    leads = {ld["lead_id"]: ld async for ld in leads_cur}

    emit_count = 0
    rejected_count = 0
    update_ids: List[Any] = []
    rejected_ids: List[Any] = []
    try:
        from services.a2a_bus import bus
    except Exception:
        bus = None
    try:
        from services.council_deliberate import deliberate as _deliberate
    except Exception:
        _deliberate = None

    for row in rows:
        lead = leads.get(row["lead_id"]) or {}
        # Skip if hot or DNC
        if lead.get("hot_lead_flag") or lead.get("dnc"):
            update_ids.append(row["_id"])
            continue
        # Skip if chain already halted
        chain = lead.get("blast_chain") or {}
        if chain.get("halted_reason"):
            update_ids.append(row["_id"])
            continue
        day = int(row.get("scheduled_day") or 0)
        event = f"NO_REPLY_DAY{day}"

        # ── Council gate per emit (CASL required, advisory: qa) ────────
        # Each NO_REPLY_DAY{N} signal triggers another outbound touch
        # (blast, email, or call). CASL re-validates because consent /
        # DNC state can change between Day-0 arm and Day-N touch.
        if _deliberate is not None:
            council_payload = {
                "lead_id": row["lead_id"],
                "scheduled_day": day,
                "event": event,
                "lead_status": lead.get("status"),
                "consent": lead.get("consent"),
                "dnc": lead.get("dnc"),
            }
            try:
                verdict = await _deliberate(
                    f"followup_emit_day{day}", "followup_ora", council_payload,
                    required=["casl"], advisory=["qa"],
                )
            except Exception as e:
                verdict = {"verdict": "APPROVED", "votes": {},
                           "confidence": 0.5, "_council_error": str(e)}
            if verdict.get("verdict") == "REJECTED":
                rejected_ids.append(row["_id"])
                rejected_count += 1
                if log_action:
                    await log_action(
                        "followup", "REJECTED_BY_COUNCIL",
                        f"day{day} emit rejected: {verdict.get('votes')}",
                        lead_id=row["lead_id"], success=False,
                        metadata={"day": day, "votes": verdict.get("votes")},
                    )
                continue

        update_ids.append(row["_id"])
        if bus is not None:
            try:
                await bus.emit("followup", event, {
                    "lead_id": row["lead_id"],
                    "trigger": event.lower(),
                })
                emit_count += 1
            except Exception as e:
                logger.warning(f"[followup] emit {event} failed: {e}")

    # Bulk-mark all checked followups as 'done'
    if update_ids:
        await db.scheduled_followups.update_many(
            {"_id": {"$in": update_ids}},
            {"$set": {"status": "done", "checked_at": now}},
        )
    if rejected_ids:
        await db.scheduled_followups.update_many(
            {"_id": {"$in": rejected_ids}},
            {"$set": {"status": "council_rejected", "checked_at": now}},
        )

    if log_action and (emit_count or rejected_count):
        await log_action("followup", "TICK",
                         f"checked={len(rows)} emitted={emit_count} "
                         f"council_rejected={rejected_count}")
    return {"ok": True, "checked": len(rows),
            "emitted": emit_count, "council_rejected": rejected_count}


# ─────────────────────────────────────────────────────────────────────
# Subscription + scheduler
# ─────────────────────────────────────────────────────────────────────

def register_subscriptions() -> None:
    from services.a2a_bus import bus
    bus.subscribe("BLAST_SENT", arm)
    logger.info("[followup] subscribed to BLAST_SENT")


async def followup_tick_scheduler():
    """Forever loop — every 1 hour, run the tick."""
    print("[followup] tick scheduler alive — 90s grace", flush=True)
    await asyncio.sleep(90)
    while True:
        try:
            res = await tick()
            if (res.get("emitted") or 0) > 0:
                print(f"[followup] tick: {res}", flush=True)
            await asyncio.sleep(3600)  # 1 hour
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[followup] tick error: {e}", exc_info=True)
            await asyncio.sleep(300)
