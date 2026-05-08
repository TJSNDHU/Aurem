"""
Channel-Gating Refresh (iter 297) — P0
======================================
Re-computes `channel_gating` for every existing lead using the current
`_compute_channel_gating` rules (iter 295 decoupled per-channel risk model)
without re-scraping. Source of truth: `verified_lead_profile.consolidated`.

Writes back to:
  • verified_lead_profile.channel_gating
  • campaign_leads.verification.channel_gating

Run modes:
  python -m scripts.refresh_channel_gating          # all leads
  python -m scripts.refresh_channel_gating --dry    # preview only
  python -m scripts.refresh_channel_gating --limit 50
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger("refresh_gating")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def refresh_channel_gating(db, dry_run: bool = False, limit: int = 0) -> Dict[str, Any]:
    """
    Returns: {scanned, updated, unchanged, missing_consolidated, sample_diffs[<=10]}
    """
    from services.accurate_scout import _compute_channel_gating

    cursor = db.verified_lead_profile.find(
        {}, {"_id": 0, "lead_id": 1, "consolidated": 1, "channel_gating": 1, "business_name": 1},
    )
    if limit and limit > 0:
        cursor = cursor.limit(int(limit))

    scanned = updated = unchanged = missing = 0
    sample_diffs: List[Dict[str, Any]] = []
    started = datetime.now(timezone.utc).isoformat()

    async for prof in cursor:
        scanned += 1
        lead_id = prof.get("lead_id")
        consolidated = prof.get("consolidated") or {}
        if not lead_id or not consolidated:
            missing += 1
            continue

        old_gating = prof.get("channel_gating") or {}
        new_gating = _compute_channel_gating(consolidated)
        if old_gating == new_gating:
            unchanged += 1
            continue

        if len(sample_diffs) < 10:
            sample_diffs.append({
                "lead_id": lead_id,
                "business_name": prof.get("business_name"),
                "old": old_gating,
                "new": new_gating,
            })

        if not dry_run:
            await db.verified_lead_profile.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "channel_gating": new_gating,
                    "channel_gating_refreshed_at": started,
                }},
            )
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "verification.channel_gating": new_gating,
                    "verification.channel_gating_refreshed_at": started,
                }},
            )
        updated += 1

    summary = {
        "scanned": scanned,
        "updated": updated,
        "unchanged": unchanged,
        "missing_consolidated": missing,
        "dry_run": bool(dry_run),
        "sample_diffs": sample_diffs,
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Audit row for traceability
    if not dry_run:
        try:
            await db.channel_gating_refresh_log.insert_one(summary | {"source": "script"})
        except Exception as e:
            logger.warning(f"audit log skip: {e}")

    logger.info(f"[refresh_gating] {summary}")
    return summary


async def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    out = await refresh_channel_gating(db, dry_run=args.dry, limit=args.limit)
    print(out)
    client.close()


if __name__ == "__main__":
    asyncio.run(_main())
