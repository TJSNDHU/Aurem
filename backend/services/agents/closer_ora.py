"""
AUREM Closer ORA — Phase 1 (T1 Pipeline)
=========================================
Subscribes to:
  • HOT_REPLY      → fire Retell call immediately (subject to time gate)
  • NO_REPLY_DAY5  → arm Retell call for the lead

Behaviour per spec:
  - Idempotent (one call per (lead_id, trigger))
  - Council-gated (CASL required, advisory: pricing + qa)
  - Time-gated (10–16 local time, Mon–Fri only); else queued for next window
  - Logs: agent_registry.log_action + a2a_bus emit `CLOSER_ARMED`

Public:
  await arm(payload)             # subscribed handler
  register_subscriptions()       # called by P1 worker on boot
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Local-time window for outbound calls (lead's timezone)
CALL_HOUR_START = 10
CALL_HOUR_END = 16  # exclusive
WEEKDAY_MAX = 5  # Mon=1 ... Fri=5


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _next_business_window(tz_name: str) -> datetime:
    """Return next Mon-Fri 10:00 in lead's timezone, as UTC datetime."""
    try:
        import pytz
        tz = pytz.timezone(tz_name or "America/Toronto")
    except Exception:
        import pytz
        tz = pytz.timezone("America/Toronto")
    local_now = datetime.now(tz)
    # If past 16:00 local, advance to next morning
    candidate = local_now.replace(
        hour=CALL_HOUR_START, minute=0, second=0, microsecond=0,
    )
    if local_now.hour >= CALL_HOUR_END:
        candidate += timedelta(days=1)
    # Skip weekends
    while candidate.isoweekday() > WEEKDAY_MAX:
        candidate += timedelta(days=1)
    return candidate.astimezone(pytz.UTC)


def _within_calling_window(tz_name: str) -> bool:
    try:
        import pytz
        tz = pytz.timezone(tz_name or "America/Toronto")
    except Exception:
        return True
    local_now = datetime.now(tz)
    if local_now.isoweekday() > WEEKDAY_MAX:
        return False
    return CALL_HOUR_START <= local_now.hour < CALL_HOUR_END


# ─────────────────────────────────────────────────────────────────────
# Main handler
# ─────────────────────────────────────────────────────────────────────

async def arm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handler — invoked by A2A bus on HOT_REPLY / NO_REPLY_DAY5."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    # Heartbeat (best-effort)
    try:
        from services.agent_registry import heartbeat, log_action
        await heartbeat("closer")
    except Exception:
        log_action = None

    lead_id = (payload.get("lead_id") or "").strip()
    trigger = payload.get("trigger") or "no_reply_day5"
    if not lead_id:
        return {"ok": False, "error": "lead_id missing"}

    # Parallel: fetch lead + idempotency check
    lead, existing_call = await asyncio.gather(
        db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0}),
        db.auto_call_log.find_one({"lead_id": lead_id, "trigger": trigger}),
        return_exceptions=True,
    )
    if isinstance(lead, Exception) or not lead:
        if log_action:
            await log_action("closer", "SKIPPED",
                             f"lead {lead_id} not found",
                             lead_id=lead_id, success=False)
        return {"ok": False, "error": "lead not found"}
    phone = (lead.get("phone") or lead.get("phone_e164") or "").strip()
    if not phone:
        if log_action:
            await log_action("closer", "SKIPPED",
                             "No phone on lead",
                             lead_id=lead_id, success=False)
        return {"ok": False, "error": "no phone"}
    if existing_call:
        return {"ok": True, "skipped": "idempotency"}

    # Council gate
    try:
        from services.council_deliberate import deliberate
        verdict = await deliberate(
            "retell_call", "closer", lead,
            required=["casl"], advisory=["pricing", "qa"],
        )
    except Exception as e:
        verdict = {"verdict": "APPROVED",
                   "votes": {},
                   "confidence": 0.5,
                   "_council_error": str(e)}
    if verdict.get("verdict") == "REJECTED":
        if log_action:
            await log_action("closer", "REJECTED_BY_COUNCIL",
                             str(verdict.get("votes")),
                             lead_id=lead_id, success=False)
        return {"ok": False, "rejected": True, "verdict": verdict}

    # Time-of-day gate (lead's local timezone)
    tz_name = (lead.get("timezone")
               or lead.get("tz")
               or "America/Toronto")
    if not _within_calling_window(tz_name):
        # Queue for next business window
        next_at = _next_business_window(tz_name)
        await db.scheduled_calls.insert_one({
            "lead_id": lead_id,
            "trigger": trigger,
            "scheduled_for": next_at,
            "queued_at": _utc_now(),
            "status": "pending",
        })
        if log_action:
            await log_action("closer", "QUEUED_FOR_WINDOW",
                             f"Outside hours ({tz_name}); next={next_at.isoformat()}",
                             lead_id=lead_id, metadata={"trigger": trigger})
        return {"ok": True, "queued": True, "scheduled_for": next_at.isoformat()}

    # Fire the Retell call.
    # iter 325h — fixed: was calling _retell_create_phone_call with
    # `lead_context=` (kwarg that didn't exist) and no `agent_id` →
    # every closer attempt was failing with TypeError, silently
    # swallowed by the `except Exception` below. Now passes agent_id
    # explicitly + uses lead_context for retell_llm_dynamic_variables.
    plan = ((verdict.get("votes") or {}).get("pricing") or {}).get(
        "reason", "starter")
    call_result: Dict[str, Any] = {}
    agent_id = (
        lead.get("retell_agent_id")
        or os.environ.get("RETELL_AGENT_ID", "").strip()
    )
    try:
        from routers.voice_agent_router import _retell_create_phone_call
        call_result = await asyncio.wait_for(
            _retell_create_phone_call(
                agent_id=agent_id,
                to_number=phone,
                lead_context={
                    "business_name": lead.get("business_name"),
                    "owner_name": (lead.get("owner_first_name")
                                   or lead.get("name")
                                   or "there"),
                    "trigger": trigger,
                    "plan": plan,
                },
            ),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        call_result = {"ok": False, "error": "retell_timeout"}
    except Exception as e:
        call_result = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    call_id = call_result.get("call_id")
    success = bool(call_id) and call_result.get("ok", True)

    # Persist + emit (parallel)
    persist_tasks = [
        db.auto_call_log.insert_one({
            "lead_id": lead_id,
            "trigger": trigger,
            "phone": phone,
            "call_id": call_id,
            "result": call_result,
            "called_at": _utc_now(),
        }),
    ]
    if log_action:
        persist_tasks.append(log_action(
            "closer",
            "CALL_INITIATED" if success else "CALL_FAILED",
            f"phone={phone} trigger={trigger} call_id={call_id}",
            lead_id=lead_id,
            metadata={"plan": plan, "trigger": trigger},
            success=success,
        ))
    try:
        from services.a2a_bus import bus
        persist_tasks.append(bus.emit("closer", "CLOSER_ARMED", {
            "lead_id": lead_id,
            "trigger": trigger,
            "call_id": call_id,
            "success": success,
        }))
    except Exception:
        pass
    await asyncio.gather(*persist_tasks, return_exceptions=True)

    return {"ok": success, "call_id": call_id, "trigger": trigger}


# ─────────────────────────────────────────────────────────────────────
# Subscription wiring
# ─────────────────────────────────────────────────────────────────────

def register_subscriptions() -> None:
    """Register Closer handlers on the A2A bus."""
    from services.a2a_bus import bus
    bus.subscribe("HOT_REPLY", arm)
    bus.subscribe("NO_REPLY_DAY5", arm)
    logger.info("[closer] subscribed to HOT_REPLY + NO_REPLY_DAY5")


# ─────────────────────────────────────────────────────────────────────
# Time-window scheduler — release queued calls when window opens
# ─────────────────────────────────────────────────────────────────────

async def closer_window_scheduler():
    """Forever loop — every 10 min, fire any queued calls now in window."""
    print("[closer] window scheduler alive — 60s grace before first cycle",
          flush=True)
    await asyncio.sleep(60)
    while True:
        try:
            db = _get_db()
            if db is None:
                await asyncio.sleep(60)
                continue
            now = _utc_now()
            cur = db.scheduled_calls.find(
                {"scheduled_for": {"$lte": now},
                 "status": "pending"},
                {"_id": 1, "lead_id": 1, "trigger": 1},
            ).limit(50)
            rows = await cur.to_list(50)
            fired = 0
            for row in rows:
                # Mark as firing
                await db.scheduled_calls.update_one(
                    {"_id": row["_id"]},
                    {"$set": {"status": "firing", "fired_at": now}},
                )
                res = await arm({"lead_id": row["lead_id"],
                                 "trigger": row.get("trigger", "scheduled")})
                await db.scheduled_calls.update_one(
                    {"_id": row["_id"]},
                    {"$set": {"status": "done" if res.get("ok") else "failed",
                              "result": res}},
                )
                if res.get("ok") and not res.get("queued"):
                    fired += 1
            if fired:
                print(f"[closer] window cycle: fired={fired}", flush=True)
            await asyncio.sleep(600)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[closer] window scheduler error: {e}",
                         exc_info=True)
            await asyncio.sleep(120)
