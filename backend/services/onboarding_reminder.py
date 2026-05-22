"""
AUREM Onboarding Reminder Cron
===============================
Scans `tenant_customers` every 2 min for AUREM tenants whose pixel
has not been installed 10 min after signup, sends a Resend email
once, marks `pixel_reminder_sent_at`, and repeats the process
every 24 h until the pixel is verified (max 3 nudges).

Runs inside Pillar 4 (command_hub) so an unhandled failure inside
the reminder loop never crashes the main event loop.
"""
from __future__ import annotations

import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

CYCLE_SECONDS = 120               # Poll every 2 min
FIRST_NUDGE_AFTER_MIN = 10        # 10-min gap before first reminder
NUDGE_REPEAT_HOURS = 24           # 24 h between subsequent nudges
MAX_NUDGES = 3                    # Stop after 3 reminders


def _resend_client():
    """Return a ready-to-use resend module or None if key missing."""
    try:
        from services.email_engine import resend as _resend  # iter 326x defensive
    except ImportError:
        return None
    key = os.environ.get("RESEND_API_KEY", "").strip()
    if not key:
        return None
    _resend.api_key = key
    return _resend


def _reminder_email_html(business_name: str, tenant_id: str, pixel_snippet_url: str) -> str:
    """Minimal, clean reminder email body."""
    return f"""
<!DOCTYPE html>
<html><body style="font-family: -apple-system, Helvetica, Arial, sans-serif; color: #1a1a1a; max-width: 560px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #8B6F2A; margin-bottom: 8px;">One step left to unlock your dashboard</h2>
  <p style="color: #555; font-size: 15px;">Hi {business_name},</p>
  <p style="font-size: 15px;">Your AUREM workspace is ready, but we haven't detected the tracking pixel on your site yet.</p>
  <p style="font-size: 15px;">Paste this single line into your site's &lt;head&gt; and click <b>Verify</b> in the dashboard:</p>
  <div style="background: #F5F2EB; border-left: 3px solid #D4AF37; padding: 12px 14px; font-family: 'SF Mono', monospace; font-size: 12px; color: #333; border-radius: 4px; word-break: break-all; margin: 14px 0;">
    &lt;script src="{pixel_snippet_url}" data-aurem-key="{tenant_id}" async&gt;&lt;/script&gt;
  </div>
  <p style="font-size: 15px;">Or grab the WordPress one-click plugin from your onboarding panel.</p>
  <p style="color: #888; font-size: 13px; margin-top: 32px;">— AUREM</p>
</body></html>
"""


async def _send_one_reminder(db, row: dict) -> bool:
    """Send one Resend reminder + mark the row. Returns True on success."""
    resend = _resend_client()
    if resend is None:
        logger.debug("[onboarding-reminder] Resend not configured — skipping send")
        return False

    email = row.get("email")
    business_name = row.get("business_name") or "there"
    tenant_id = row.get("tenant_id") or ""
    base = os.environ.get("APP_URL", "").rstrip("/") or "https://aurem.live"
    pixel_url = f"{base}/api/pixel/aurem-pixel.js"
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "AUREM <hello@aurem.live>")

    try:
        # Resend SDK is sync — run in a thread to not block the loop.
        def _do_send():
            return resend.Emails.send({
                "from": from_addr,
                "to": [email],
                "subject": "One step left — install your AUREM pixel",
                "html": _reminder_email_html(business_name, tenant_id, pixel_url),
            })
        result = await asyncio.to_thread(_do_send)
        msg_id = (result or {}).get("id", "")
        logger.info(f"[onboarding-reminder] sent to {email[:5]}*** msg_id={msg_id}")

        # Mark sent + bump counter
        nudge_count = int(row.get("pixel_nudge_count") or 0) + 1
        await db.tenant_customers.update_one(
            {"tenant_id": tenant_id, "record_type": "aurem_tenant"},
            {"$set": {
                "pixel_reminder_sent_at": datetime.now(timezone.utc).isoformat(),
                "pixel_nudge_count": nudge_count,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        return True
    except Exception as e:
        logger.warning(f"[onboarding-reminder] send failed for {email}: {e}")
        return False


async def _scan_and_nudge(db) -> dict:
    """One pass: find eligible rows and send reminders.

    Eligibility rules:
      - record_type == "aurem_tenant"
      - status == "onboarding"
      - pixel_installed == False
      - age ≥ FIRST_NUDGE_AFTER_MIN
      - pixel_nudge_count < MAX_NUDGES
      - last nudge either never sent OR ≥ NUDGE_REPEAT_HOURS ago
    """
    if db is None:
        return {"skipped": "no_db"}
    now = datetime.now(timezone.utc)
    first_cutoff_iso = (now - timedelta(minutes=FIRST_NUDGE_AFTER_MIN)).isoformat()
    repeat_cutoff_iso = (now - timedelta(hours=NUDGE_REPEAT_HOURS)).isoformat()

    query = {
        "record_type": "aurem_tenant",
        "status": "onboarding",
        "pixel_installed": False,
        "created_at": {"$lte": first_cutoff_iso},
        "$or": [
            {"pixel_reminder_sent_at": None},
            {"pixel_reminder_sent_at": {"$exists": False}},
            {"pixel_reminder_sent_at": {"$lte": repeat_cutoff_iso}},
        ],
        "$expr": {"$lt": [{"$ifNull": ["$pixel_nudge_count", 0]}, MAX_NUDGES]},
    }

    candidates = await db.tenant_customers.find(query, {"_id": 0}).to_list(50)
    sent = 0
    for row in candidates:
        ok = await _send_one_reminder(db, row)
        if ok:
            sent += 1
    return {"candidates": len(candidates), "sent": sent}


async def onboarding_reminder_scheduler():
    """Long-lived loop — attached to Pillar 4 worker."""
    logger.info("[onboarding-reminder] scheduler started (2-min cycle)")
    # small grace so server.db has finished set_db
    await asyncio.sleep(30)

    # Lazy DB import (server.db is the live motor DB)
    from server import db as _db_ref

    while True:
        try:
            await _scan_and_nudge(_db_ref)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"[onboarding-reminder] cycle error: {e}")
        await asyncio.sleep(CYCLE_SECONDS)


__all__ = [
    "onboarding_reminder_scheduler",
    "_scan_and_nudge",
    "CYCLE_SECONDS",
    "FIRST_NUDGE_AFTER_MIN",
    "MAX_NUDGES",
]
