"""
trial_reminder_scheduler.py — Hourly trial drip + expiry sweep.
═══════════════════════════════════════════════════════════════════════════
Scheduled in routers/registry.py via aurem_scheduler (60-min interval).

Drip rules:
  • Day 4 reminder (3 days remaining) — emailed once per BIN
  • Day 6 reminder (1 day remaining) — emailed once per BIN
  • On expiry — apply_expiry() + final email "Trial ended"
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from services import trial_engine

logger = logging.getLogger(__name__)


def _get_db():
    try:
        from server import db
        return db
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _send_email(db, business_id: str, email: str, kind: str, payload: Dict[str, Any]):
    """Best-effort email via Resend service if available; logs to
    sent_emails regardless so reminder de-duplication works without Resend."""
    if db is None:
        return
    # Idempotency — has this kind already been sent for this BIN?
    seen = await db.trial_reminders_sent.find_one(
        {"business_id": business_id, "kind": kind}, {"_id": 1}
    )
    if seen:
        return
    # Send (fire and forget)
    try:
        from services.resend_email import send_email
        subject_map = {
            "day4_midway": "Quick check-in — 3 days left in your AUREM trial",
            "day6_final": "24 hours left in your AUREM trial",
            "expired": "Your AUREM trial has ended — pick a plan to continue",
        }
        body = (
            f"<p>Hi,</p><p>{payload.get('intro','')}</p>"
            f"<p><a href='https://aurem.live/my/billing' style='background:#2D7A4A;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none'>Pick a plan</a></p>"
            f"<p>— AUREM Team</p>"
        )
        await send_email(
            to_email=email,
            subject=subject_map.get(kind, "AUREM update"),
            html_body=body,
        )
    except Exception as e:
        logger.debug(f"[trial_reminder] resend send skipped: {e}")
    # Mark sent
    await db.trial_reminders_sent.insert_one({
        "business_id": business_id,
        "email": email,
        "kind": kind,
        "ts": _now_iso(),
    })


async def trial_reminder_tick() -> Dict[str, Any]:
    """Hourly cron entry-point."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}

    summary = {"day4": 0, "day6": 0, "expired": 0}

    # Day-4 nudges (3 days remaining)
    rows = await trial_engine.find_trials_due(db, days_until_end=3)
    for r in rows:
        await _send_email(db, r["business_id"], r.get("email", ""), "day4_midway",
                          {"intro": "You have 3 days left in your AUREM trial."})
        summary["day4"] += 1

    # Day-6 nudges (1 day remaining)
    rows = await trial_engine.find_trials_due(db, days_until_end=1)
    for r in rows:
        await _send_email(db, r["business_id"], r.get("email", ""), "day6_final",
                          {"intro": "Your trial ends in 24 hours."})
        summary["day6"] += 1

    # Expiry sweep — anything that ended within the last 25 hours
    rows = await trial_engine.find_trials_due(db, ended_within_hours=25)
    for r in rows:
        if trial_engine.is_expired(r):
            await trial_engine.apply_expiry(db, r["business_id"])
            await _send_email(db, r["business_id"], r.get("email", ""), "expired",
                              {"intro": "Your AUREM trial has ended. Your data is preserved — pick a plan to keep going."})
            summary["expired"] += 1

    logger.info(f"[trial_reminder] tick complete: {summary}")
    return {"ok": True, "summary": summary, "ts": _now_iso()}
