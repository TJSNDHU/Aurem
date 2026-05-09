"""
trial_expiry_sweep.py — iter 322w STEP 2.

Hourly scheduler job that:
  1. Finds aurem_billing rows where status='trialing' AND trial_ends_at < now
  2. Calls trial_engine.apply_expiry() — flips services_unlocked to [],
     plan to 'trial_expired', subscription_status to 'trial_expired'
  3. Sends a single "Trial ended — pick a plan" email per expired account
  4. Records a row in db.trial_expiry_audit for traceability

Idempotent — already-expired rows are skipped because apply_expiry
flips status off "trialing".
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def _send_expiry_email(db, business_id: str, email: str) -> bool:
    """Best-effort. Returns True if attempted, False if no email or service."""
    if not email:
        return False
    try:
        # Lazy import — keeps this module clean if email service is missing.
        from services.email_service import send_email  # type: ignore
    except Exception:
        try:
            from utils.email_sender import send_email  # type: ignore
        except Exception:
            logger.debug("[trial-expiry] no email service available — skipping send")
            return False
    subject = "Your AUREM trial ended — pick a plan to keep your services"
    body = (
        "Hi,\n\n"
        "Your 7-day AUREM trial has ended. Your data is safe, but services "
        "are now locked until you pick a plan.\n\n"
        "Activate a plan in 1 click:\n"
        "  https://aurem.live/pricing\n\n"
        "Plans start at $29/mo with full Voice + Email + SMS unlocked.\n\n"
        "— AUREM"
    )
    try:
        await send_email(to=email, subject=subject, body=body)
        return True
    except Exception as e:
        logger.debug(f"[trial-expiry] email send to {email} failed: {e}")
        return False


async def trial_expiry_sweep(db=None) -> Dict[str, Any]:
    """Single hourly tick. Safe to call from APScheduler or manually."""
    if db is None:
        try:
            from server import db as _server_db
            db = _server_db
        except Exception:
            return {"ok": False, "reason": "db_unavailable"}
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}

    from services.trial_engine import find_trials_due, apply_expiry

    now = datetime.now(timezone.utc)
    expired_rows = await find_trials_due(db, ended_within_hours=24 * 30)
    processed = 0
    expired_count = 0
    emails_sent = 0
    for row in expired_rows:
        bid = row.get("business_id")
        if not bid:
            continue
        try:
            await apply_expiry(db, bid)
            expired_count += 1
            user = await db.platform_users.find_one(
                {"business_id": bid}, {"_id": 0, "email": 1}
            )
            email_addr = (user or {}).get("email")
            sent = await _send_expiry_email(db, bid, email_addr)
            if sent:
                emails_sent += 1
            await db.trial_expiry_audit.insert_one({
                "business_id": bid,
                "email": email_addr,
                "expired_at": now.isoformat(),
                "trial_ends_at": row.get("trial_ends_at"),
                "email_sent": sent,
            })
            processed += 1
        except Exception as e:
            logger.warning(f"[trial-expiry] {bid} failed: {e}")
    if processed:
        logger.info(
            f"[trial-expiry] swept — processed={processed} expired={expired_count} "
            f"emails_sent={emails_sent}"
        )
    return {
        "ok": True,
        "processed": processed,
        "expired_count": expired_count,
        "emails_sent": emails_sent,
        "ts": now.isoformat(),
    }
