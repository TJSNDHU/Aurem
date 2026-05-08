"""
ORA Brain Observer — Phase 2 (T4)
==================================
Subscribes to ALL A2A bus events, persists each as a thought, and routes
critical events to specialized handlers:

  HOT_REPLY         → log + flag for manual visibility
  COUNCIL_REJECTED  → if agent has > N rejections in 24h, pause it
  WEDGE_DETECTED    → log
  WEDGE_HEALED      → log
  LEARNING_PROMOTED → upsert into ora_knowledge (Tier-3 permanent)
  CODE_FIX_APPLIED  → upsert as code_fix pattern
  DEPLOY_DETECTED   → log + memory_sync stamp

Non-blocking: every handler is fired via `asyncio.create_task` so the bus
publisher is never delayed.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Events ORA Brain wants to observe explicitly. The bus emits to specific
# event names — we register the same observer for each relevant event.
OBSERVED_EVENTS = (
    "LEADS_FOUND", "LEADS_QUALIFIED", "BLAST_SENT",
    "FOLLOWUP_ARMED", "NO_REPLY_DAY2", "NO_REPLY_DAY5", "NO_REPLY_DAY9",
    "HOT_REPLY", "DNC_REPLY",
    "CLOSER_ARMED", "CALL_COMPLETE",
    "SUBSCRIPTION_CREATED", "REFERRAL_SENT",
    "COUNCIL_APPROVED", "COUNCIL_REJECTED", "CASL_VIOLATION",
    "WEDGE_DETECTED", "WEDGE_HEALED",
    "LEARNING_PROMOTED",
    "ORA_DECISION", "ORA_ALERT",
    "CODE_FIX_APPLIED", "DEPLOY_DETECTED", "HEALTH_FAILED",
)

REJECTION_THRESHOLD_24H = int(os.environ.get("ORA_REJECT_THRESHOLD", "5"))
HOT_AUTOCALL_TIMEOUT_S = int(os.environ.get("ORA_HOT_AUTOCALL_S", "7200"))


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────
# Top-level event observer (subscribed to many events)
# ─────────────────────────────────────────────────────────────────────

async def on_event(event_type: str, payload: Dict[str, Any]) -> None:
    """Single async dispatcher — invoked once per event by `_observer_for(e)`."""
    db = _get_db()
    if db is None:
        return
    # Heartbeat (best-effort)
    try:
        from services.agent_registry import heartbeat
        await heartbeat("ora_brain")
    except Exception:
        pass

    # Persist thought + route concurrently
    persist = db.ora_brain_thoughts.insert_one({
        "event": event_type,
        "payload": payload or {},
        "ts": _utc_now(),
    })
    routed = _route_event(event_type, payload or {})
    await asyncio.gather(persist, routed, return_exceptions=True)


def _observer_for(event_type: str):
    """Return a closure that calls on_event with the event name baked in."""
    async def _observer(payload):
        await on_event(event_type, payload)
    _observer.__name__ = f"ora_brain_obs_{event_type}"
    return _observer


def register_subscriptions() -> None:
    """Register ORA Brain observer for every OBSERVED_EVENT."""
    from services.a2a_bus import bus
    for ev in OBSERVED_EVENTS:
        bus.subscribe(ev, _observer_for(ev))
    logger.info(f"[ora_brain_observer] subscribed to {len(OBSERVED_EVENTS)} events")


# ─────────────────────────────────────────────────────────────────────
# Event router
# ─────────────────────────────────────────────────────────────────────

async def _route_event(event_type: str, payload: Dict[str, Any]) -> None:
    handlers = {
        "COUNCIL_REJECTED":  _handle_rejection,
        "HOT_REPLY":         _handle_hot,
        "WEDGE_DETECTED":    _handle_wedge,
        "LEARNING_PROMOTED": _apply_learning,
        "CODE_FIX_APPLIED":  _log_code_fix,
        "DEPLOY_DETECTED":   _verify_deploy,
        "HEALTH_FAILED":     _handle_health_fail,
    }
    fn = handlers.get(event_type)
    if fn:
        try:
            await fn(payload)
        except Exception as e:
            logger.warning(f"[ora_brain] handler {event_type} failed: {e}")


# ─────────────────────────────────────────────────────────────────────
# Specialized handlers
# ─────────────────────────────────────────────────────────────────────

async def _handle_rejection(payload: Dict[str, Any]) -> None:
    """If an agent crosses REJECTION_THRESHOLD_24H, pause it + alert founder."""
    db = _get_db()
    if db is None:
        return
    agent = payload.get("agent", "")
    if not agent:
        return
    cutoff = _utc_now() - timedelta(hours=24)
    rejects = await db.council_decisions_detailed.count_documents({
        "requesting_agent": agent,
        "verdict": "REJECTED",
        "ts": {"$gte": cutoff},
    })
    if rejects < REJECTION_THRESHOLD_24H:
        return

    # Pause the agent + alert
    await asyncio.gather(
        db.agent_heartbeats.update_one(
            {"agent": agent},
            {"$set": {
                "status": "paused",
                "paused_reason": "high_rejection",
                "paused_at": _utc_now(),
                "paused_rejects_24h": rejects,
            }},
            upsert=True,
        ),
        _ora_sms(
            f"⚠️ {agent} paused — {rejects} council rejections in 24h",
        ),
        return_exceptions=True,
    )


async def _handle_hot(payload: Dict[str, Any]) -> None:
    """Log hot replies; the actual auto-call is fired by Closer ORA."""
    db = _get_db()
    if db is None:
        return
    await db.ora_hot_log.insert_one({
        "lead_id": payload.get("lead_id"),
        "channel": payload.get("channel"),
        "text": (payload.get("text") or "")[:500],
        "ts": _utc_now(),
        "auto_call_window_until": _utc_now() + timedelta(seconds=HOT_AUTOCALL_TIMEOUT_S),
    })


async def _handle_wedge(payload: Dict[str, Any]) -> None:
    db = _get_db()
    if db is None:
        return
    await db.ora_wedge_log.insert_one({
        "agent": payload.get("agent"),
        "tier": payload.get("tier"),
        "ts": _utc_now(),
        "payload": payload,
    })


async def _apply_learning(payload: Dict[str, Any]) -> None:
    """Upsert promoted learning into the permanent `ora_knowledge` store."""
    db = _get_db()
    if db is None:
        return
    pattern = (payload.get("pattern") or "").strip()
    if not pattern:
        return
    await db.ora_knowledge.update_one(
        {"pattern": pattern},
        {"$set": {
            "pattern": pattern,
            "kind": payload.get("kind", ""),
            "confidence": float(payload.get("confidence", 0.5)),
            "last_confirmed": _utc_now(),
            "active": True,
            "payload": payload.get("payload", {}),
        },
            "$inc": {"times_seen": 1},
            "$setOnInsert": {"first_learned": _utc_now()}},
        upsert=True,
    )


async def _log_code_fix(payload: Dict[str, Any]) -> None:
    """Stamp every Emergent code fix into ORA's permanent memory."""
    db = _get_db()
    if db is None:
        return
    pattern = f"code_fix_{(payload.get('error_type') or payload.get('fix_description', ''))[:40]}"
    await db.ora_knowledge.update_one(
        {"pattern": pattern},
        {"$set": {
            "pattern": pattern,
            "kind": "code_fix",
            "category": "code_fix",
            "confidence": 1.0,
            "last_confirmed": _utc_now(),
            "active": True,
            "source": "emergent",
        },
            "$inc": {"times_seen": 1},
            "$push": {"evidence": {
                "fix": payload.get("fix_description"),
                "files_changed": payload.get("files_changed"),
                "ts": _utc_now(),
            }},
            "$setOnInsert": {"first_learned": _utc_now()}},
        upsert=True,
    )


async def _verify_deploy(payload: Dict[str, Any]) -> None:
    db = _get_db()
    if db is None:
        return
    await db.ora_deploy_log.insert_one({
        "old_version": payload.get("old"),
        "new_version": payload.get("new"),
        "ts": _utc_now(),
    })


async def _handle_health_fail(payload: Dict[str, Any]) -> None:
    """Health probe red — write to ledger + ping founder once per hour."""
    db = _get_db()
    if db is None:
        return
    last = await db.ora_health_alerts.find_one(
        {}, sort=[("ts", -1)],
    )
    now = _utc_now()
    suppress = (last and (now - last.get("ts", now)).total_seconds() < 3600)
    await db.ora_health_alerts.insert_one({
        "error": payload.get("error"),
        "ts": now,
    })
    if not suppress:
        await _ora_sms(f"🚨 health check FAILED: {payload.get('error', '?')[:140]}")


# ─────────────────────────────────────────────────────────────────────
# SMS helper
# ─────────────────────────────────────────────────────────────────────

async def _ora_sms(message: str) -> None:
    """Critical alerts only — never approval prompts."""
    to = (os.environ.get("ADMIN_ALERT_PHONE")
          or os.environ.get("FOUNDER_PHONE")
          or "").strip()
    if not to:
        logger.debug("[ora_brain] ADMIN_ALERT_PHONE/FOUNDER_PHONE missing — SMS skipped")
        return
    try:
        from services.twilio_service import send_sms
        await send_sms(to, f"🤖 ORA: {message}")
    except Exception as e:
        logger.debug(f"[ora_brain] SMS failed: {e}")
