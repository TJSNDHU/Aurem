"""
services/outreach_health.py — iter 330 FIX 5

Aggregates the live state of all 7 outreach channels into one
founder-readable snapshot. Used by the Outreach Health card in the
ORA-CTO Cockpit and by the Morning Brief.

Channels (in display order):
  1. Email          (Resend)
  2. WhatsApp       (Twilio WABA primary, WHAPI fallback)
  3. SMS            (Twilio)
  4. Voice          (Retell)
  5. Daily Hunt     (lead scout)
  6. Proactive      (30-day follow-ups, abandoned browse)
  7. Social         (LinkedIn via Brightbean)

For each channel returns:
  • status        — "green" | "yellow" | "red"
  • last_fire_at  — ISO timestamp or None
  • last_24h_count — sends/fires in the last 24h
  • success_pct   — last-24h delivered/attempted ratio
  • note          — one-line plain-English explanation
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _email_health(db) -> dict:
    cutoff = _now() - timedelta(hours=24)
    try:
        cur = db.outreach_history.find(
            {"ts": {"$gte": cutoff.isoformat()}},
            {"_id": 0, "channels_attempted": 1, "result": 1, "ts": 1},
        ).sort("ts", -1).limit(500)
        rows = await cur.to_list(length=500)
    except Exception as e:
        return _row("Email", "red", note=f"db read failed: {str(e)[:80]}")
    attempted = 0
    delivered = 0
    last_at = None
    for r in rows:
        chans = r.get("channels_attempted") or []
        if "email" not in chans:
            continue
        attempted += 1
        if not last_at:
            last_at = r.get("ts")
        sent = ((r.get("result") or {}).get("sent")) or []
        if any(s.get("channel") == "email" and (s.get("ok") is not False) for s in sent):
            delivered += 1
    if attempted == 0:
        return _row("Email", "yellow", note="no email sends in last 24h", last_at=last_at)
    pct = round(100 * delivered / attempted, 1)
    status = "green" if pct >= 95 else ("yellow" if pct >= 80 else "red")
    return _row("Email", status, last_at=last_at, count=attempted, success=pct,
                  note=f"{delivered}/{attempted} delivered in last 24h")


async def _whatsapp_health(db) -> dict:
    tw_set = bool((os.environ.get("TWILIO_WA_FROM_NUMBER") or "").strip())
    whapi_disabled = (os.environ.get("WHAPI_BLAST_DISABLED", "false").lower()
                      in ("1", "true", "yes", "on"))
    if not tw_set and whapi_disabled:
        return _row("WhatsApp", "red",
                      note="TWILIO_WA_FROM_NUMBER empty and WHAPI disabled — set Twilio WABA env to unlock")
    cutoff = _now() - timedelta(hours=24)
    try:
        cur = db.outreach_history.find(
            {"ts": {"$gte": cutoff.isoformat()}},
            {"_id": 0, "result": 1, "ts": 1},
        ).limit(500)
        rows = await cur.to_list(length=500)
    except Exception:
        return _row("WhatsApp", "red", note="db read failed")
    sent = 0
    ok = 0
    last_at = None
    for r in rows:
        for s in (((r.get("result") or {}).get("sent")) or []):
            if s.get("channel") == "whatsapp":
                sent += 1
                if not last_at:
                    last_at = r.get("ts")
                if s.get("ok") is True:
                    ok += 1
    if sent == 0:
        return _row("WhatsApp", "yellow" if tw_set else "red",
                      note="ready, no sends yet — set TWILIO_WA_FROM_NUMBER" if not tw_set else "ready, no sends in last 24h")
    pct = round(100 * ok / sent, 1)
    return _row("WhatsApp", "green" if pct >= 80 else "yellow",
                  last_at=last_at, count=sent, success=pct)


async def _sms_health(db) -> dict:
    disabled = (os.environ.get("SMS_DISABLED", "true").lower()
                in ("1", "true", "yes", "on"))
    if disabled:
        return _row("SMS", "yellow",
                      note="kill-switch ON — waiting Twilio A2P 10DLC approval")
    cutoff = _now() - timedelta(hours=24)
    try:
        cur = db.outreach_history.find(
            {"ts": {"$gte": cutoff.isoformat()}}, {"_id": 0, "result": 1, "ts": 1},
        ).limit(500)
        rows = await cur.to_list(length=500)
    except Exception:
        return _row("SMS", "red", note="db read failed")
    sent = 0
    ok = 0
    last_at = None
    for r in rows:
        for s in (((r.get("result") or {}).get("sent")) or []):
            if s.get("channel") == "sms":
                sent += 1
                if not last_at:
                    last_at = r.get("ts")
                if s.get("ok") is True:
                    ok += 1
    if sent == 0:
        return _row("SMS", "yellow", note="enabled but no sends in last 24h")
    pct = round(100 * ok / sent, 1)
    return _row("SMS", "green" if pct >= 90 else "yellow",
                  last_at=last_at, count=sent, success=pct)


async def _voice_health(db) -> dict:
    if not (os.environ.get("RETELL_API_KEY") or "").strip():
        return _row("Voice (Retell)", "red", note="RETELL_API_KEY not set")
    cutoff = _now() - timedelta(hours=24)
    try:
        runs = await db.closer_day5_runs.count_documents({"ts": {"$gte": cutoff}})
        armed_24h = 0
        async for r in db.closer_day5_runs.find({"ts": {"$gte": cutoff}}, {"_id": 0, "armed": 1, "ts": 1}).sort("ts", -1).limit(50):
            armed_24h += int(r.get("armed") or 0)
        last_run_row = await db.closer_day5_runs.find_one(
            {}, {"_id": 0, "ts": 1, "armed": 1}, sort=[("ts", -1)],
        )
    except Exception:
        return _row("Voice (Retell)", "red", note="db read failed")
    last_at = (last_run_row or {}).get("ts")
    if not last_at:
        return _row("Voice (Retell)", "red",
                      note="Day-5 trigger never fired — check closer_day5 cron")
    return _row("Voice (Retell)", "green" if armed_24h else "yellow",
                  last_at=last_at.isoformat() if hasattr(last_at, "isoformat") else last_at,
                  count=armed_24h,
                  note=f"{runs} sweeps in 24h, {armed_24h} calls armed")


async def _daily_hunt_health(db) -> dict:
    cutoff = _now() - timedelta(hours=36)
    try:
        last = await db.hunt_commands.find_one(
            {"kind": "auto_daily_hunt"}, sort=[("fired_at", -1)],
        )
    except Exception:
        return _row("Daily Hunt", "red", note="db read failed")
    if not last:
        return _row("Daily Hunt", "red", note="never fired — check 06:00 UTC cron")
    last_at = last.get("fired_at")
    ok = False
    try:
        if isinstance(last_at, str):
            ok = last_at >= cutoff.isoformat()
        else:
            ok = last_at >= cutoff
    except Exception:
        ok = False
    return _row("Daily Hunt", "green" if ok else "yellow", last_at=last_at,
                  count=int(last.get("leads_added") or 0),
                  note=f"{last.get('leads_added', 0)} leads added in last run")


async def _proactive_health(db) -> dict:
    try:
        last_log = await db.proactive_outreach_log.find_one(
            {}, sort=[("sent_at", -1)],
        )
        last_run = await db.proactive_outreach_runs.find_one(
            {}, sort=[("ts", -1)],
        )
    except Exception:
        return _row("Proactive Follow-up", "red", note="db read failed")
    if not last_log and not last_run:
        return _row("Proactive Follow-up", "yellow",
                      note="no qualifying customers yet (orders / abandoned browses)")
    last_at = (last_run or {}).get("ts") or (last_log or {}).get("sent_at")
    return _row("Proactive Follow-up", "green", last_at=last_at,
                  note="scheduler firing daily at 10:00 EST")


async def _social_health(db) -> dict:
    try:
        last = await db.social_autopilot_posts.find_one(
            {}, sort=[("ts", -1)],
        )
    except Exception:
        return _row("Social (LinkedIn)", "red", note="db read failed")
    if not last:
        return _row("Social (LinkedIn)", "yellow",
                      note="autopilot wired, awaiting next 10:00 ET run")
    last_at = last.get("ts")
    ok = last.get("publish_ok") is True
    return _row("Social (LinkedIn)", "green" if ok else "yellow",
                  last_at=last_at.isoformat() if hasattr(last_at, "isoformat") else last_at,
                  count=1, note=last.get("topic_key") or "")


def _row(label: str, status: str, *,
            last_at: str | None = None, count: int = 0,
            success: float | None = None, note: str = "") -> dict:
    return {
        "label":         label,
        "status":        status,
        "last_fire_at":  last_at,
        "last_24h_count": count,
        "success_pct":   success,
        "note":          note,
    }


async def outreach_health_snapshot(db) -> dict:
    """One-shot snapshot of all 7 channels."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}
    channels = [
        await _email_health(db),
        await _whatsapp_health(db),
        await _sms_health(db),
        await _voice_health(db),
        await _daily_hunt_health(db),
        await _proactive_health(db),
        await _social_health(db),
    ]
    overall = "green"
    if any(c["status"] == "red" for c in channels):
        overall = "red"
    elif any(c["status"] == "yellow" for c in channels):
        overall = "yellow"
    return {
        "ok":       True,
        "ts":       _now().isoformat(),
        "overall":  overall,
        "channels": channels,
    }
