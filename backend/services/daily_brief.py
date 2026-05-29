"""
services/daily_brief.py — iter D-58

Compose + dispatch the morning (09:00 ET) and evening (21:00 ET)
operations brief. The brief is plain-English, 6-bullet max, mirrors
Rule Zero (no JSON dumps).

Channels:
  • Resend email → admin email (env: ADMIN_DAILY_BRIEF_EMAIL)
  • Twilio WhatsApp → admin number (env: ADMIN_DAILY_BRIEF_WA_TO)

Both channels are best-effort; a failure on one is logged but does
NOT block the other.

The brief is persisted to `daily_briefs` so the admin widget +
`/api/cto/brief/latest` endpoint can render it without re-computing.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_db = None
_ADMIN_EMAIL = os.environ.get("ADMIN_DAILY_BRIEF_EMAIL", "")
_ADMIN_WA    = os.environ.get("ADMIN_DAILY_BRIEF_WA_TO", "")


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _gather_stats(window_hours: int = 24) -> dict[str, Any]:
    """Pull the numbers the brief needs in one DB roundtrip."""
    if _db is None:
        return {}
    since = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()

    # Leads created
    new_leads = await _db.campaign_leads.count_documents({
        "created_at": {"$gte": since},
    })
    # Leads with hot_lead_flag in window (opens / clicks)
    hot_window = await _db.campaign_leads.count_documents({
        "hot_lead_flag": True,
        "hot_lead_signal_at": {"$gte": since},
    })
    hot_clicked = await _db.campaign_leads.count_documents({
        "hot_lead_flag": True,
        "hot_lead_reason": "email_clicked",
        "hot_lead_signal_at": {"$gte": since},
    })
    # Actual deliveries (Resend IDs in outreach_history)
    delivered_email = 0
    delivered_sms   = 0
    pipe = [
        {"$match": {"ts": {"$gte": since}}},
        {"$unwind": "$result.sent"},
        {"$match": {
            "$or": [
                {"result.sent.channel": "email", "result.sent.id":  {"$exists": True}},
                {"result.sent.channel": "sms",   "result.sent.sid": {"$exists": True}},
            ],
        }},
        {"$group": {"_id": "$result.sent.channel", "n": {"$sum": 1}}},
    ]
    async for d in _db.outreach_history.aggregate(pipe):
        if d["_id"] == "email":
            delivered_email = d["n"]
        elif d["_id"] == "sms":
            delivered_sms = d["n"]

    # Last blast run info
    abc = await _db.auto_blast_config.find_one({"tenant_id": "global"},
                                                  {"_id": 0})
    abc = abc or {}

    # Eligible leads (engine-style query)
    eligible = await _db.campaign_leads.count_documents({
        "last_blast_at": {"$exists": False},
        "noise_flag": {"$ne": True},
        "$or": [
            {"email": {"$nin": ["", None]}},
            {"phone": {"$nin": ["", None]}},
        ],
        "status": {"$nin": ["signed_up", "not_interested", "unsubscribed"]},
    })

    return {
        "window_hours":    window_hours,
        "new_leads":       new_leads,
        "hot_window":      hot_window,
        "hot_clicked":     hot_clicked,
        "delivered_email": delivered_email,
        "delivered_sms":   delivered_sms,
        "eligible_leads":  eligible,
        "last_blast_at":   abc.get("last_run_at", ""),
        "last_blast_sent": abc.get("last_run_sent", 0),
        "last_blast_note": abc.get("last_run_note", ""),
    }


def _morning_text(stats: dict[str, Any]) -> str:
    eligible = stats.get("eligible_leads", 0)
    tasks = []
    if eligible == 0:
        tasks.append("Run Ghost Scout for fresh leads (pool empty)")
    elif eligible < 25:
        tasks.append(f"Top up lead pool — only {eligible} eligible")
    if stats.get("hot_window", 0):
        tasks.append(f"Reply to {stats['hot_window']} hot leads (email opens/clicks)")
    if stats.get("delivered_email", 0) == 0:
        tasks.append("Verify Resend delivery — 0 emails landed in 24h")
    if not tasks:
        tasks.append("Maintain blast cadence; review weekly template stats")
    if len(tasks) < 3:
        tasks.append("Review revenue dashboard")

    return (
        "🌅 AUREM Morning Brief\n"
        f"• {stats.get('new_leads', 0)} new leads in last 24h\n"
        f"• {stats.get('delivered_email', 0)} emails delivered, "
        f"{stats.get('hot_window', 0)} opens "
        f"({stats.get('hot_clicked', 0)} clicked)\n"
        f"• {stats.get('eligible_leads', 0)} leads eligible for today's blast\n"
        "Top 3 today:\n"
        + "\n".join(f"  {i+1}. {t}" for i, t in enumerate(tasks[:3]))
    )


def _evening_text(stats: dict[str, Any]) -> str:
    return (
        "🌙 AUREM Evening Wrap\n"
        f"• Contacted {stats.get('delivered_email', 0)} via email + "
        f"{stats.get('delivered_sms', 0)} via SMS today\n"
        f"• {stats.get('hot_window', 0)} replies / opens "
        f"({stats.get('hot_clicked', 0)} clicked)\n"
        f"• Last blast {stats.get('last_blast_note', 'n/a')} "
        f"(sent {stats.get('last_blast_sent', 0)})\n"
        f"• Tomorrow: {stats.get('eligible_leads', 0)} eligible leads "
        f"queued, {stats.get('new_leads', 0)} fresh this cycle"
    )


async def _send_email(subject: str, body: str) -> dict[str, Any]:
    if not _ADMIN_EMAIL:
        return {"ok": False, "skipped": "no_admin_email"}
    try:
        from services.email_service import send_email
        return await send_email(_ADMIN_EMAIL, subject, body)
    except Exception as e:
        logger.warning(f"[daily-brief] email send failed: {e}")
        return {"ok": False, "error": str(e)}


async def _send_whatsapp(body: str) -> dict[str, Any]:
    if not _ADMIN_WA:
        return {"ok": False, "skipped": "no_admin_wa"}
    try:
        from shared.providers.twilio import send_whatsapp_message
        return await send_whatsapp_message(_ADMIN_WA, body)
    except Exception as e:
        logger.warning(f"[daily-brief] WA send failed: {e}")
        return {"ok": False, "error": str(e)}


async def _persist(kind: str, text: str, stats: dict[str, Any],
                    email_result: dict[str, Any],
                    wa_result: dict[str, Any]) -> str:
    if _db is None:
        return ""
    brief_id = str(uuid.uuid4())
    doc = {
        "brief_id":     brief_id,
        "kind":         kind,
        "text":         text,
        "stats":        stats,
        "email_result": {k: v for k, v in (email_result or {}).items()
                          if k in ("ok", "id", "error", "skipped")},
        "wa_result":    {k: v for k, v in (wa_result or {}).items()
                          if k in ("ok", "success", "message_sid",
                                    "error", "skipped")},
        "generated_at": _now(),
    }
    try:
        await _db.daily_briefs.insert_one(doc)
    except Exception as e:
        logger.warning(f"[daily-brief] persist failed: {e}")
    return brief_id


async def send_morning_brief() -> dict[str, Any]:
    stats = await _gather_stats(window_hours=24)
    text  = _morning_text(stats)
    em    = await _send_email("AUREM Morning Brief", text)
    wa    = await _send_whatsapp(text)
    bid   = await _persist("morning", text, stats, em, wa)
    logger.info(f"[daily-brief] morning sent bid={bid}")
    return {"ok": True, "brief_id": bid, "kind": "morning",
             "stats": stats, "email": em, "whatsapp": wa,
             "text": text}


async def send_evening_brief() -> dict[str, Any]:
    stats = await _gather_stats(window_hours=12)
    text  = _evening_text(stats)
    em    = await _send_email("AUREM Evening Wrap", text)
    wa    = await _send_whatsapp(text)
    bid   = await _persist("evening", text, stats, em, wa)
    logger.info(f"[daily-brief] evening sent bid={bid}")
    return {"ok": True, "brief_id": bid, "kind": "evening",
             "stats": stats, "email": em, "whatsapp": wa,
             "text": text}


async def latest_brief() -> dict[str, Any] | None:
    if _db is None:
        return None
    doc = await _db.daily_briefs.find_one(
        {}, {"_id": 0}, sort=[("generated_at", -1)],
    )
    return doc
