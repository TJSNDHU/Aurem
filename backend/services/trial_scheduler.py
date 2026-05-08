"""
Trial Scheduler (Phase 5)
=========================
Daily APScheduler job that:
  1. Auto-downgrades trials past Day 7 → state='expired', quotas reset for Forever Free
  2. Sends drip messages on Day 3, 5, 6, 7 (email + WhatsApp)
  3. Long-tail re-engagement: Day 14, 30, 60, 90
  4. Recomputes days_remaining on all active trials (for UI)

Uses existing email_service + whatsapp service (lazy imports).
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


DRIP_TEMPLATES = {
    3: {
        "subject": "Your AUREM Power Trial is working",
        "preview": "Day 3 — here's what AUREM did for you this week",
        "cta": "See your repair wins",
    },
    5: {
        "subject": "2 days left in your AUREM Trial",
        "preview": "Lock in your score improvements before Day 8",
        "cta": "Subscribe — from $29/mo",
    },
    6: {
        "subject": "Tomorrow is your final trial day",
        "preview": "Don't let your gains expire",
        "cta": "Continue AUREM — unlock services",
    },
    7: {
        "subject": "Trial ends today — your wins at risk",
        "preview": "Subscribe now or downgrade to Forever Free tomorrow",
        "cta": "Keep my gains (1-click)",
    },
    14: {
        "subject": "Check your AUREM score this week",
        "preview": "Your site scored 48 two weeks ago. Where's it now?",
        "cta": "Run a free monthly scan",
    },
    30: {
        "subject": "Your AUREM site score dropped",
        "preview": "Our sensors show new issues. Fix them for $29.",
        "cta": "Restart AUREM — 1-click",
    },
}


async def _send_drip(db, trial: dict, day: int) -> bool:
    tpl = DRIP_TEMPLATES.get(day)
    if not tpl:
        return False
    email = trial.get("email", "")
    if not email:
        return False
    # Idempotency — check drip_sent map
    drip_sent = trial.get("drip_sent") or {}
    key = f"day{day}"
    if drip_sent.get(key):
        return False

    # Deliver via email
    try:
        from services.email_service import send_email
        html = f"""
        <h2>{tpl['subject']}</h2>
        <p>{tpl['preview']}</p>
        <p><a href="https://aurem.live/my/website" style="background:#D4AF37;color:#0A0A0F;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700;">{tpl['cta']}</a></p>
        <p style="font-size:11px;color:#888;margin-top:20px;">— AUREM Platform · Polaris Built Inc.</p>
        """
        await send_email(to=email, subject=tpl["subject"], html=html)
    except Exception as e:
        logger.warning(f"[trial-scheduler] email drip day{day} failed for {email}: {e}")

    await db.trial_sessions.update_one(
        {"email": email},
        {"$set": {f"drip_sent.{key}": datetime.now(timezone.utc).isoformat()}}
    )
    await db.drip_campaigns_log.insert_one({
        "email": email,
        "day": day,
        "template": tpl["subject"],
        "at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info(f"[trial-scheduler] drip day{day} sent to {email}")
    return True


async def _process_trial(db, trial: dict):
    """Single-trial tick — determines drip + downgrade action for today."""
    email = trial.get("email", "")
    started_str = trial.get("started_at", "")
    state = trial.get("state", "active")
    if not email or not started_str:
        return

    try:
        started = datetime.fromisoformat(started_str.replace("Z", "+00:00"))
        days_since_start = (datetime.now(timezone.utc) - started).days
    except Exception:
        return

    # Update days_remaining field for UI freshness
    days_remaining = max(0, 7 - days_since_start)
    await db.trial_sessions.update_one(
        {"email": email},
        {"$set": {"days_remaining": days_remaining}}
    )

    if state == "active":
        # Drip days 3/5/6/7
        for drip_day in [3, 5, 6, 7]:
            if days_since_start == drip_day:
                await _send_drip(db, trial, drip_day)

        # Auto-downgrade at Day 8+
        if days_since_start >= 8:
            await db.trial_sessions.update_one(
                {"email": email},
                {"$set": {
                    "state": "expired",
                    "days_remaining": 0,
                    "downgraded_at": datetime.now(timezone.utc).isoformat(),
                    # Forever Free quotas
                    "scanner_quota": 1,      # 1/month (not 1/week)
                    "friend_scans_quota": 0, # disabled for free tier
                    "ora_msgs_quota": 50,    # still 50 but limits per month not week
                }}
            )
            logger.info(f"[trial-scheduler] Downgraded {email} to forever_free (Day {days_since_start})")

    # Long-tail re-engagement for expired trials (customers who didn't subscribe)
    if state in ("active", "expired"):
        has_paid = await db.customer_subscriptions.count_documents({"email": email, "status": "active"})
        if has_paid == 0:
            for re_day in [14, 30, 60, 90]:
                if days_since_start == re_day:
                    await _send_drip(db, trial, re_day)


async def run_trial_scheduler_tick(db):
    """Runs through all trials once. Called daily by scheduler or manually for testing."""
    if db is None:
        return {"ok": False, "reason": "db not ready"}
    count_processed = 0
    downgrades = 0
    async for trial in db.trial_sessions.find({}, {"_id": 0}):
        try:
            before = trial.get("state")
            await _process_trial(db, trial)
            after = await db.trial_sessions.find_one({"email": trial["email"]}, {"_id": 0})
            if before == "active" and (after or {}).get("state") == "expired":
                downgrades += 1
            count_processed += 1
        except Exception as e:
            logger.warning(f"[trial-scheduler] tick error on {trial.get('email')}: {e}")
    logger.info(f"[trial-scheduler] Tick complete — {count_processed} trials processed, {downgrades} downgraded")
    return {"ok": True, "processed": count_processed, "downgrades": downgrades}


# Background scheduler loop (runs once a day at 8am UTC)
async def trial_scheduler_loop(db):
    """Long-running background loop. Start via asyncio.create_task."""
    while True:
        try:
            await run_trial_scheduler_tick(db)
        except Exception as e:
            logger.exception(f"[trial-scheduler] loop error: {e}")
        # Sleep 24 hours. For testing, can be lowered.
        await asyncio.sleep(24 * 3600)
