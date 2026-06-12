"""
AUREM Accurate Scout — Nightly Re-Verification Cron
====================================================
Runs at 2 AM UTC every night. Finds every `campaign_leads` doc whose
`verification.verified_at` is either absent or >14 days old, and
re-runs `full_business_verify`.

Alerts on confidence regressions:
  HIGH phone → MEDIUM/LOW → sends SMS via fallback_monitor
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# Re-verify any lead whose last check was more than this many days ago
REVERIFY_AFTER_DAYS = 14

# Max leads processed per run — prevent runaway cost
MAX_LEADS_PER_RUN = 200


def _get_db():
    """Best-effort async Motor client (matches other services)."""
    try:
        from server import db as _db
        if _db is not None:
            return _db
    except Exception:
        pass
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        db_name = os.environ.get("DB_NAME", "aurem_db").strip().strip('"').strip("'")
        if mongo_url:
            return AsyncIOMotorClient(mongo_url)[db_name]
    except Exception:
        pass
    return None


async def _alert_regression(db, lead: Dict, old_conf: str, new_conf: str) -> None:
    """Send SMS alert when phone confidence drops HIGH→MEDIUM/LOW."""
    try:
        from services.fallback_monitor import _send_sms_alert
        phone = os.environ.get("ADMIN_ALERT_PHONE", "").strip()
        if not phone:
            return
        await _send_sms_alert(
            phone,
            f"AUREM VERIFICATION REGRESSION: {lead.get('business_name', lead.get('lead_id'))} "
            f"phone confidence dropped {old_conf}→{new_conf}. Review CRM.",
        )
        # also persist to fallback_usage_log for the dashboard
        await db.fallback_usage_log.insert_one({
            "service": "verification",
            "primary": "accurate_scout",
            "used": "reverification",
            "result": "regression",
            "reason": f"{lead.get('lead_id')}: phone {old_conf}→{new_conf}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ttl_at": datetime.now(timezone.utc),  # Iter 206: 30-day TTL
        })
    except Exception as e:
        logger.debug(f"[ReverifyCron] Alert failed: {e}")


async def run_reverification_cycle() -> Dict[str, int]:
    """Re-verify stale leads. Returns summary counts."""
    db = _get_db()
    if db is None:
        return {"error": "no_db"}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=REVERIFY_AFTER_DAYS)).isoformat()
    # Target: leads without verification OR with verified_at < cutoff
    query = {
        "$or": [
            {"verification.verified_at": {"$exists": False}},
            {"verification.verified_at": {"$lt": cutoff}},
        ]
    }

    cursor = db.campaign_leads.find(
        {**query, "business_id": FOUNDER_BIN},
        {"_id": 0, "lead_id": 1, "business_name": 1,
                                             "city": 1, "address": 1, "website_url": 1,
                                             "verification": 1}).limit(MAX_LEADS_PER_RUN)
    leads = await cursor.to_list(MAX_LEADS_PER_RUN)
    logger.info(f"[ReverifyCron] {len(leads)} stale leads queued")

    from services.accurate_scout import full_business_verify, save_verified_profile

    results = {"total": len(leads), "succeeded": 0, "failed": 0, "regressions": 0, "upgrades": 0}
    for lead in leads:
        name = lead.get("business_name") or ""
        city = lead.get("city") or ""
        if not name:
            results["failed"] += 1
            continue

        # Throttle — don't hammer external APIs
        await asyncio.sleep(0.5)

        try:
            country = "ca" if ("ON" in (lead.get("address") or "") or city.lower() in
                               ("toronto", "brampton", "mississauga", "ottawa", "vancouver",
                                "calgary", "edmonton", "montreal", "quebec")) else "us"
            verified = await full_business_verify(
                name, city, country=country,
                website_url=lead.get("website_url") or "",
            )
            await save_verified_profile(db, lead["lead_id"], verified)

            # Regression detection
            old = (lead.get("verification") or {}).get("phone_confidence", "NONE")
            new = (verified.get("consolidated", {}).get("phone") or {}).get("confidence", "NONE")
            if old == "HIGH" and new in ("MEDIUM", "LOW", "NONE"):
                results["regressions"] += 1
                await _alert_regression(db, lead, old, new)
            elif old in ("LOW", "NONE", "MEDIUM") and new == "HIGH":
                results["upgrades"] += 1

            results["succeeded"] += 1
        except Exception as e:
            logger.warning(f"[ReverifyCron] Failed for {lead.get('lead_id')}: {e}")
            results["failed"] += 1

    logger.info(f"[ReverifyCron] Cycle done: {results}")
    # Stamp a cron summary doc
    try:
        await db.cron_runs.insert_one({
            "job": "accurate_scout_reverification",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
        })
    except Exception:
        pass
    return results


async def reverification_scheduler():
    """Background task — run re-verification every night at 2 AM UTC."""
    target_hour_utc = 2
    while True:
        try:
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=target_hour_utc, minute=0, second=0, microsecond=0)
            if now.hour >= target_hour_utc:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"[ReverifyCron] Next run in {wait_seconds/3600:.1f}h")
            await asyncio.sleep(wait_seconds)
            await run_reverification_cycle()
            await asyncio.sleep(60)  # don't double-fire
        except Exception as e:
            logger.error(f"[ReverifyCron] Scheduler error: {e}")
            await asyncio.sleep(3600)
