"""
AUREM Auto Double-Lock — Fully Automated Origin-Write Pipeline
===============================================================

Closes the OODA repair loop end-to-end with zero human clicks:

  Scan → Fix → Verify → Anchor → Proof

When fixes are deployed (status = "deployed"):
  1. Auto-compile origin files
  2. Auto-commit to origin
  3. Schedule PageSpeed verification (10-min delay)
  4. Log to Sentinel
  5. WhatsApp notification on success/failure
  6. Morning Brief integration

Triggers from:
  - free_tier_deploy (PIN unlock)
  - Stripe webhook (paid tier)
  - self_scan auto-deploy
  - Manual "Commit to Origin" button
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from server import db
        return db
    except Exception:
        return None


async def auto_trigger_origin_write(site_url: str, user_id: str, deploy_id: str = None):
    """
    Automatically trigger the Origin-Write pipeline after fixes are deployed.
    This is the "Anchor" phase of the Double-Lock Fix.
    
    Called from: free_deploy, stripe_webhook, self_scan_auto
    """
    db = _get_db()
    if db is None:
        logger.warning("[DoubleLock] DB not available")
        return

    now = datetime.now(timezone.utc).isoformat()

    try:
        # Step 1: Compile origin files
        from services.origin_write_engine import compile_origin_files
        compiled = await compile_origin_files(site_url, user_id)

        if "error" in compiled and compiled.get("fix_count", 0) == 0:
            logger.info(f"[DoubleLock] No fixes to compile for {site_url}")
            return

        # Step 2: Commit to origin
        from services.origin_write_engine import commit_to_origin
        commit_result = await commit_to_origin(site_url, user_id)

        commit_id = commit_result.get("commit_id", "unknown")
        fix_count = commit_result.get("fix_count", 0)

        logger.info(f"[DoubleLock] Origin committed: {commit_id} ({fix_count} fixes) for {site_url}")

        # Step 3: Log to Sentinel
        await db.auto_heal_log.insert_one({
            "type": "double_lock_triggered",
            "site_url": site_url,
            "user_id": user_id,
            "deploy_id": deploy_id,
            "commit_id": commit_id,
            "fix_count": fix_count,
            "phase": "origin_committed",
            "timestamp": now,
        })

        # Step 4: Schedule PageSpeed verification in 10 minutes
        asyncio.create_task(_delayed_pagespeed_verify(site_url, user_id, commit_id, delay_seconds=600))

        # Step 5: Update all deployed fixes with double-lock metadata
        await db.repair_fixes.update_many(
            {"user_id": user_id, "scan_url": site_url, "status": "deployed"},
            {"$set": {
                "double_lock_status": "origin_committed",
                "origin_commit_id": commit_id,
                "origin_committed_at": now,
            }},
        )

    except Exception as e:
        logger.error(f"[DoubleLock] Auto Origin-Write failed for {site_url}: {e}")
        await db.auto_heal_log.insert_one({
            "type": "double_lock_failed",
            "site_url": site_url,
            "error": str(e),
            "timestamp": now,
        })


async def _delayed_pagespeed_verify(site_url: str, user_id: str, commit_id: str, delay_seconds: int = 600):
    """Wait for Google to crawl, then verify with PageSpeed."""
    logger.info(f"[DoubleLock] Scheduling PageSpeed verify for {site_url} in {delay_seconds}s")

    await asyncio.sleep(delay_seconds)

    db = _get_db()
    if db is None:
        return

    now = datetime.now(timezone.utc).isoformat()

    try:
        from services.origin_write_engine import verify_origin_commit
        result = await verify_origin_commit(site_url, user_id)

        scores = result.get("external_scores", {})
        match = result.get("match", False)

        # Update fix statuses
        if match:
            # Success: Mark as double-locked
            await db.repair_fixes.update_many(
                {"user_id": user_id, "scan_url": site_url, "status": "deployed"},
                {"$set": {
                    "double_lock_status": "verified",
                    "pagespeed_verified_at": now,
                    "pagespeed_scores": scores,
                }},
            )

            await db.origin_commits.update_one(
                {"scan_url": site_url, "user_id": user_id},
                {"$set": {"double_lock_status": "verified", "verified_at": now}},
            )

            logger.info(f"[DoubleLock] VERIFIED: {site_url} scores={scores}")

            # WhatsApp success notification (if Twilio configured)
            await _send_whatsapp_alert(
                f"AUREM: Fix anchored to origin.\n"
                f"PageSpeed: {_format_scores(scores)}\n"
                f"URL: {site_url}"
            )

        else:
            # Scores didn't improve — flag for review
            await db.repair_fixes.update_many(
                {"user_id": user_id, "scan_url": site_url, "status": "deployed"},
                {"$set": {
                    "double_lock_status": "pending_verification",
                    "pagespeed_check_at": now,
                    "pagespeed_scores": scores,
                }},
            )

            logger.warning(f"[DoubleLock] PENDING: {site_url} scores={scores} — needs manual check")

            await _send_whatsapp_alert(
                f"AUREM: Origin fix applied but PageSpeed unchanged.\n"
                f"Scores: {_format_scores(scores)}\n"
                f"URL: {site_url}\n"
                f"Manual check needed."
            )

        # Log verification result
        await db.auto_heal_log.insert_one({
            "type": "double_lock_verified" if match else "double_lock_pending",
            "site_url": site_url,
            "commit_id": commit_id,
            "scores": scores,
            "match": match,
            "timestamp": now,
        })

    except Exception as e:
        logger.error(f"[DoubleLock] PageSpeed verify failed for {site_url}: {e}")
        await db.auto_heal_log.insert_one({
            "type": "double_lock_verify_failed",
            "site_url": site_url,
            "error": str(e),
            "timestamp": now,
        })


def _format_scores(scores: dict) -> str:
    if not scores:
        return "unavailable"
    parts = []
    for cat, score in scores.items():
        label = cat.replace("-", " ").title()
        parts.append(f"{label}: {score}")
    return ", ".join(parts)


async def _send_whatsapp_alert(message: str):
    """Send WhatsApp notification via Twilio (if configured)."""
    import os
    from services.channel_config import get_twilio_credentials, get_twilio_whatsapp_from
    creds = get_twilio_credentials()
    sid = creds["sid"]
    token = creds["token"]
    whatsapp_from = get_twilio_whatsapp_from() or "whatsapp:+14155238886"
    whatsapp_to = (
        os.environ.get("ADMIN_ALERT_PHONE")
        or os.environ.get("FOUNDER_PHONE")
        or os.environ.get("TJ_WHATSAPP_NUMBER")
        or ""
    ).strip()

    if not sid or not token:
        logger.info(f"[DoubleLock] WhatsApp alert (Twilio not configured): {message[:100]}")
        return

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(
            body=message,
            from_=whatsapp_from,
            to=f"whatsapp:{whatsapp_to}",
        )
        logger.info(f"[DoubleLock] WhatsApp sent to {whatsapp_to}")
    except Exception as e:
        logger.warning(f"[DoubleLock] WhatsApp failed: {e}")


async def get_double_lock_stats() -> dict:
    """Get Double-Lock stats for morning brief and dashboard."""
    db = _get_db()
    if db is None:
        return {}

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(hours=24)).isoformat()

    try:
        # Last 24h
        locked_24h = await db.auto_heal_log.count_documents({
            "type": "double_lock_verified",
            "timestamp": {"$gte": yesterday},
        })

        pending = await db.auto_heal_log.count_documents({
            "type": {"$in": ["double_lock_triggered", "double_lock_pending"]},
            "timestamp": {"$gte": yesterday},
        })

        # All time
        total_locked = await db.origin_commits.count_documents({"double_lock_status": "verified"})
        total_committed = await db.origin_commits.count_documents({})

        return {
            "locked_last_24h": locked_24h,
            "pending_verification": pending,
            "total_locked": total_locked,
            "total_committed": total_committed,
        }
    except Exception as e:
        logger.warning(f"[DoubleLock] Stats error: {e}")
        return {}


async def get_morning_brief_double_lock() -> str:
    """Double-Lock summary for morning brief."""
    stats = await get_double_lock_stats()
    return (
        f"Fixes double-locked last 24h: {stats.get('locked_last_24h', 0)}. "
        f"Pending verification: {stats.get('pending_verification', 0)}. "
        f"Total sites anchored: {stats.get('total_committed', 0)}."
    )
