"""
Founder Daily Briefs (iter 302)
================================
7 AM Toronto → Morning Brief → WhatsApp +16134000000
7 PM Toronto → Evening Digest → WhatsApp +16134000000

Both run as a single 60s-poll background loop. Idempotent per-day via
`last_fired_iso` tracking + ±2 minute window. Records to db.founder_brief_runs.

Sends via WHAPI (global token). If WHAPI fails, falls back to Telegram.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

ADMIN_WHATSAPP = os.environ.get("ADMIN_WHATSAPP", "+16134000000")
TZ = ZoneInfo("America/Toronto")
COLLECTION = "founder_brief_runs"

_db = None


def set_db(db):
    global _db
    _db = db


async def _send_whatsapp(message: str) -> Dict[str, Any]:
    """Send via WHAPI global; fall back to Telegram if WHAPI fails."""
    import httpx
    token = os.environ.get("WHAPI_API_TOKEN", "").strip()
    base = os.environ.get("WHAPI_API_URL", "https://gate.whapi.cloud").rstrip("/")
    if token:
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                r = await cli.post(
                    f"{base}/messages/text",
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/json"},
                    json={"to": ADMIN_WHATSAPP.lstrip("+"), "body": message},
                )
            if r.status_code in (200, 201):
                return {"ok": True, "engine": "whapi", "to": ADMIN_WHATSAPP}
            logger.warning(f"[founder-brief] whapi {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.warning(f"[founder-brief] whapi exception: {e}")
    # Fallback: Telegram
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if tg_token and tg_chat:
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                await cli.post(
                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    json={"chat_id": tg_chat, "text": message,
                          "parse_mode": "Markdown"},
                )
            return {"ok": True, "engine": "telegram_fallback", "to": tg_chat}
        except Exception as e:
            logger.warning(f"[founder-brief] telegram fallback failed: {e}")
    return {"ok": False, "error": "no_dispatch_channel"}


async def _morning_brief_text() -> str:
    """Pull live numbers from DB."""
    if _db is None:
        return "AUREM Morning Brief\n(db unavailable)"
    now = datetime.now(timezone.utc)
    today_iso = now.date().isoformat()
    since_24h = (now - timedelta(hours=24)).isoformat()

    leads_total = await _db.campaign_leads.count_documents({})
    leads_unblasted = await _db.campaign_leads.count_documents(
        {"last_blast_at": {"$exists": False}}
    )
    sites_built = await _db.auto_built_sites.count_documents(
        {"created_at": {"$gte": since_24h}}
    )
    autopilot_cfg = await _db.platform_config.find_one(
        {"config_key": "master_autopilot"}, {"_id": 0, "next_fire_at": 1, "enabled": 1}
    ) or {}
    awb_state = await _db.awb_autopilot_state.find_one(
        {"_id": "singleton"}, {"_id": 0, "enabled": 1, "last_run_at": 1}
    ) or {}
    return (
        f"☀️ *AUREM Morning Brief* — {today_iso}\n\n"
        f"📋 Leads in DB: *{leads_total}* "
        f"(*{leads_unblasted}* never blasted)\n"
        f"🏗️ Sites built last 24h: *{sites_built}*\n"
        f"🤖 Autopilot: "
        f"{'ON' if autopilot_cfg.get('enabled') else 'OFF'} · "
        f"next fire `{autopilot_cfg.get('next_fire_at','—')}`\n"
        f"🛠️ AWB Pilot: "
        f"{'ON' if awb_state.get('enabled') else 'OFF'} · "
        f"last run `{awb_state.get('last_run_at','—')}`\n\n"
        f"Today's plan: scout → hunt → blast → report."
    )


async def _evening_digest_text() -> str:
    if _db is None:
        return "AUREM Evening Digest\n(db unavailable)"
    now = datetime.now(timezone.utc)
    since_24h = (now - timedelta(hours=24)).isoformat()
    today_iso = now.date().isoformat()

    blasted_today = await _db.campaign_leads.count_documents(
        {"last_blast_at": {"$gte": since_24h}}
    )
    sites_built = await _db.auto_built_sites.count_documents(
        {"created_at": {"$gte": since_24h}}
    )
    drips = 0
    try:
        drips = await _db.outreach_log.count_documents(
            {"sent_at": {"$gte": since_24h},
             "campaign_type": {"$in": ["drip_day1_wa_nudge", "drip_day3_email_trial",
                                       "drip_day7_wa_objection", "drip_day14_sms_urgency",
                                       "drip_day30_ora_redial", "drip_day60_email_final_offer"]}}
        )
    except Exception:
        pass
    last_autopilot = await _db.autopilot_runs.find_one(
        {}, {"_id": 0, "duration_seconds": 1, "finished_at": 1, "phases": 1},
        sort=[("started_at", -1)],
    ) or {}
    return (
        f"🌙 *AUREM Evening Digest* — {today_iso}\n\n"
        f"📤 Outreach blasts today: *{blasted_today}*\n"
        f"🏗️ Sites built today: *{sites_built}*\n"
        f"💧 Drip messages today: *{drips}*\n"
        f"⚡ Last autopilot run: `{last_autopilot.get('finished_at','—')}` "
        f"({last_autopilot.get('duration_seconds','—')}s)\n\n"
        f"Tomorrow 8 AM Toronto: autopilot fires again."
    )


async def _record_run(kind: str, message: str, dispatch: Dict[str, Any]) -> None:
    if _db is None:
        return
    try:
        await _db[COLLECTION].insert_one({
            "kind": kind,
            "ts": datetime.now(timezone.utc).isoformat(),
            "message_preview": message[:500],
            "dispatch": dispatch,
        })
    except Exception as e:
        logger.warning(f"[founder-brief] record failed: {e}")


async def founder_briefs_scheduler() -> None:
    """60s polling loop. Fires at 07:00 and 19:00 Toronto, ±2 min window."""
    print("[founder-briefs] scheduler alive — 60s poll", flush=True)
    last_fired: Dict[str, str] = {"morning": "", "evening": ""}
    await asyncio.sleep(15)
    while True:
        try:
            now_local = datetime.now(TZ)
            today = now_local.date().isoformat()
            for kind, hh in (("morning", 7), ("evening", 19)):
                if last_fired[kind] == today:
                    continue
                target = now_local.replace(hour=hh, minute=0, second=0, microsecond=0)
                delta = (now_local - target).total_seconds()
                if 0 <= delta < 120:
                    text = (await _morning_brief_text()) if kind == "morning" \
                        else (await _evening_digest_text())
                    res = await _send_whatsapp(text)
                    await _record_run(kind, text, res)
                    last_fired[kind] = today
                    print(f"[founder-briefs] fired {kind} → {res}", flush=True)
        except Exception as e:
            print(f"[founder-briefs] tick error: {e}", flush=True)
        await asyncio.sleep(60)
