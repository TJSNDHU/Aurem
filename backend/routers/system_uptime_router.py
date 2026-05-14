"""
system_uptime_router.py — single-shot revenue heartbeat endpoint (iter 322g+).
══════════════════════════════════════════════════════════════════════════════
Founder asked: "system offline ja rha hai baar baar, koi pakka solution kar de,
campaign properly chalti rahe, paisa aata rahe."

THIS endpoint is that pakka solution from the monitoring side. Hit it from
your phone, your laptop, anywhere. ONE URL gives you the whole picture in
<200ms with no auth (data is non-sensitive aggregate counts):

    GET {APP_URL}/api/system/uptime

Returns:
    {
      "ts": "2026-02-...T...Z",
      "env": "production" | "preview",
      "campaign": {
        "enabled": bool,
        "sent_24h": int,             # ← THE money number
        "sent_today": int,
        "queued_leads": int,
        "last_run_at": "ISO-8601",
        "last_run_sent": int,
        "last_run_processed": int,
        "health": "healthy" | "degraded" | "stopped",
        "tripped": [...],
        "zero_sent_streak": int
      },
      "ora_chat": {
        "daemon_alive": bool,
        "daemon_last_poll_seconds_ago": int | null,
        "status": "online" | "stale" | "offline" | "never"
      },
      "revenue_today": {
        "signups": int,              # platform_users created today
        "leads_added": int,          # campaign_leads added today
        "outreach_events": int
      }
    }

ZERO Legion calls, ZERO LLM calls, ZERO external API hits.
ALL data is DB-only — runs the same in preview AND production.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("system_uptime")

router = APIRouter(prefix="/api/system", tags=["system"])

_db: AsyncIOMotorDatabase | None = None


def set_db(database: AsyncIOMotorDatabase) -> None:
    global _db
    _db = database


def _get_db() -> AsyncIOMotorDatabase | None:
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


async def _safe_count(coll, query: dict) -> int:
    try:
        return await coll.count_documents(query)
    except Exception as e:
        logger.warning(f"[uptime] count failed: {e}")
        return -1


@router.get("/uptime")
async def system_uptime() -> dict[str, Any]:
    """Single-shot revenue + ORA heartbeat for the founder. <200ms."""
    db = _get_db()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    try:
        from services.prod_guard import env_label
        env = env_label()
    except Exception:
        env = "unknown"

    if db is None:
        return {
            "ts": now_iso, "env": env,
            "error": "db_not_ready",
        }

    since_24h = (now_dt - timedelta(hours=24)).isoformat()
    since_today = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    # ── Campaign engine state ────────────────────────────────────────
    cfg = await db.auto_blast_config.find_one(
        {"tenant_id": "global"}, {"_id": 0}
    ) or {}

    sent_24h = await _safe_count(
        db.outreach_history, {"sent_at": {"$gte": since_24h}}
    )
    sent_today = await _safe_count(
        db.outreach_history, {"sent_at": {"$gte": since_today}}
    )
    queued = await _safe_count(
        db.campaign_leads,
        {"last_blast_at": {"$exists": False},
         "status": {"$nin": ["signed_up", "not_interested", "unsubscribed"]}},
    )

    # ── Watchdog health ──────────────────────────────────────────────
    health = await db.ora_campaign_health.find_one(
        {"_id": "global"}, {"_id": 0}
    ) or {}
    tripped = health.get("tripped") or []
    streak = int(health.get("zero_sent_streak") or 0)

    enabled = bool(cfg.get("enabled"))
    if not enabled:
        campaign_health = "stopped"
    elif tripped or sent_24h == 0:
        campaign_health = "degraded"
    else:
        campaign_health = "healthy"

    # ── ORA daemon state (laptop reach) ──────────────────────────────
    daemon_doc = await db.legion_daemon_status.find_one(
        {"_id": "global"}, {"_id": 0, "last_poll_ts": 1}
    )
    last_ts = float((daemon_doc or {}).get("last_poll_ts") or 0)
    age_s: int | None = int(time.time() - last_ts) if last_ts else None
    if age_s is None:
        ora_status = "never"
        daemon_alive = False
    elif age_s < 60:
        ora_status = "online"
        daemon_alive = True
    elif age_s < 300:
        ora_status = "stale"
        daemon_alive = False
    else:
        ora_status = "offline"
        daemon_alive = False

    # ── Revenue heartbeat ────────────────────────────────────────────
    # FIX #12 (audit) — `created_at` is stored as an ISO-8601 string in
    # Mongo, but the previous code compared it against a tz-aware datetime
    # object via `$gte`. Mongo's BSON comparator treats those as different
    # types → match-rate was always 0, signups_today was permanently zero.
    # Now we compare ISO-string to ISO-string, matching how every other
    # collection in this file already does it (since_today, etc).
    signups_today = await _safe_count(
        db.platform_users, {"created_at": {"$gte": since_today}}
    )
    leads_added_today = await _safe_count(
        db.campaign_leads, {"created_at": {"$gte": since_today}}
    )
    outreach_today = sent_today  # alias for clarity

    return {
        "ts": now_iso,
        "env": env,
        "campaign": {
            "enabled": enabled,
            "sent_24h": sent_24h,
            "sent_today": sent_today,
            "queued_leads": queued,
            "last_run_at": cfg.get("last_run_at"),
            "last_run_sent": cfg.get("last_run_sent", 0),
            "last_run_processed": cfg.get("last_run_processed", 0),
            "health": campaign_health,
            "tripped": tripped,
            "zero_sent_streak": streak,
        },
        "ora_chat": {
            "daemon_alive": daemon_alive,
            "daemon_last_poll_seconds_ago": age_s,
            "status": ora_status,
        },
        "revenue_today": {
            "signups": signups_today,
            "leads_added": leads_added_today,
            "outreach_events": outreach_today,
        },
    }
