"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Viral Gate Service — 7-Day Taste Strategy
==========================================
Social Brain access model:
  - Day 1-7: Full Social Brain access (trial period)
  - Day 8+:  Locked until Google review confirmed via API
  - Permanently unlocked once review_completed = True
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_db = None

TRIAL_DAYS = 7


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


async def get_viral_status(tenant_id: str) -> dict:
    """Get the current viral gate status for a tenant."""
    db = _get_db()
    now = datetime.now(timezone.utc)

    defaults = {
        "tenant_id": tenant_id,
        "trial_started_at": None,
        "trial_days": TRIAL_DAYS,
        "trial_days_remaining": TRIAL_DAYS,
        "trial_active": False,
        "trial_expired": False,
        "review_completed": False,
        "unlocked": False,
        "phase": "not_started",
    }

    if db is None:
        return defaults

    record = await db.viral_gate.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    if not record:
        return defaults

    trial_started = record.get("trial_started_at")
    review_done = record.get("review_completed", False)

    # Permanently unlocked if review completed
    if review_done:
        return {
            "tenant_id": tenant_id,
            "trial_started_at": trial_started,
            "trial_days": TRIAL_DAYS,
            "trial_days_remaining": 0,
            "trial_active": False,
            "trial_expired": True,
            "review_completed": True,
            "review_url": record.get("review_url"),
            "unlocked": True,
            "unlocked_at": record.get("unlocked_at"),
            "phase": "unlocked",
        }

    # Trial not started yet
    if not trial_started:
        return defaults

    # Parse trial start date
    if isinstance(trial_started, str):
        trial_start_dt = datetime.fromisoformat(trial_started.replace("Z", "+00:00"))
    else:
        trial_start_dt = trial_started
    if trial_start_dt.tzinfo is None:
        trial_start_dt = trial_start_dt.replace(tzinfo=timezone.utc)

    elapsed = (now - trial_start_dt).days
    remaining = max(0, TRIAL_DAYS - elapsed)
    trial_active = elapsed < TRIAL_DAYS
    trial_expired = elapsed >= TRIAL_DAYS

    if trial_active:
        phase = "trial_active"
    else:
        phase = "review_required"

    return {
        "tenant_id": tenant_id,
        "trial_started_at": trial_started,
        "trial_days": TRIAL_DAYS,
        "trial_days_remaining": remaining,
        "trial_active": trial_active,
        "trial_expired": trial_expired,
        "review_completed": False,
        "unlocked": trial_active,
        "phase": phase,
    }


async def start_trial(tenant_id: str) -> dict:
    """Start the 7-day Social Brain trial for a tenant. Idempotent."""
    db = _get_db()
    if db is None:
        return {"error": "Database unavailable"}

    now_iso = datetime.now(timezone.utc).isoformat()

    await db.viral_gate.update_one(
        {"tenant_id": tenant_id},
        {
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "trial_started_at": now_iso,
                "review_completed": False,
                "created_at": now_iso,
            },
            "$set": {"updated_at": now_iso},
        },
        upsert=True,
    )

    # If trial_started_at wasn't set (first time), set it now
    existing = await db.viral_gate.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if existing and not existing.get("trial_started_at"):
        await db.viral_gate.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"trial_started_at": now_iso}},
        )

    return await get_viral_status(tenant_id)


async def record_review(tenant_id: str, review_url: str = "") -> dict:
    """Record a Google review completion — permanently unlocks Social Brain."""
    db = _get_db()
    if db is None:
        return {"error": "Database unavailable"}

    now_iso = datetime.now(timezone.utc).isoformat()

    await db.viral_gate.update_one(
        {"tenant_id": tenant_id},
        {
            "$set": {
                "review_completed": True,
                "review_url": review_url,
                "review_at": now_iso,
                "unlocked_at": now_iso,
                "updated_at": now_iso,
            },
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "trial_started_at": now_iso,
                "created_at": now_iso,
            },
        },
        upsert=True,
    )

    logger.info(f"[ViralGate] Tenant {tenant_id} UNLOCKED via Google Review")
    return await get_viral_status(tenant_id)


async def is_social_scan_unlocked(tenant_id: str) -> bool:
    """Quick check: can this tenant use social media deep-scans?

    Returns True if:
      - Within 7-day trial period, OR
      - Review completed (permanent unlock)
    Auto-starts trial on first check.
    """
    status = await get_viral_status(tenant_id)

    # Already unlocked (trial active or review done)
    if status["unlocked"]:
        return True

    # Trial not started yet — auto-start it
    if status["phase"] == "not_started":
        new_status = await start_trial(tenant_id)
        return new_status.get("unlocked", False)

    # Trial expired, review not done
    return False


async def get_gate_message(tenant_id: str) -> str:
    """Return the appropriate ORA message based on gate status."""
    status = await get_viral_status(tenant_id)

    if status["unlocked"]:
        return ""  # No gate message needed

    if status["phase"] == "review_required":
        return (
            "I've analyzed your social footprint for 7 days. To keep this "
            "'Social Brain' active permanently, please leave a 5-star Google "
            "Review for your business. Go to Settings \u2192 ORA Rewards to "
            "submit your review link. In the meantime, you can upload a "
            "screenshot via the attachment menu (\u22EE)."
        )

    # Not started — will auto-start
    return ""
