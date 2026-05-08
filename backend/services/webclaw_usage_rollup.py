"""
webclaw_usage daily rollup — iter 282af (Prompt 3).

Once-a-day cron. Idempotent: re-running for the same date is a no-op.
Registered against the shared aurem_scheduler.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def run_daily_rollup(db, for_date: str | None = None) -> dict:
    """Roll up the previous calendar day of webclaw_usage into webclaw_usage_daily.

    Args:
      db: motor async database handle
      for_date: ISO "YYYY-MM-DD" — defaults to today (UTC). Exposed as arg
                for backfill / manual run-now.

    Returns: the rollup doc actually persisted, or {"skipped": reason}.
    """
    from services.website_diff import build_rollup_doc

    if db is None:
        return {"skipped": "db is None"}

    date_str = for_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Idempotent
    try:
        existing = await db.webclaw_usage_daily.find_one(
            {"date": date_str}, projection={"_id": 0},
        )
        if existing:
            return {"skipped": "already_rolled_up", "date": date_str}
    except Exception as e:
        logger.debug(f"[rollup] existence check failed: {e}")

    # Aggregate — cheap, one-shot
    try:
        pipeline = [
            {"$match": {"date": date_str}},
            {"$group": {
                "_id": None,
                "count":               {"$sum": 1},
                "brand_sum":           {"$sum": {"$cond": ["$brand_extracted", 1, 0]}},
                "contacts_sum":        {"$sum": {"$cond": ["$contacts_extracted", 1, 0]}},
                "avg_content_length":  {"$avg": "$content_length"},
            }},
        ]
        agg = await db.webclaw_usage.aggregate(pipeline).to_list(1)
    except Exception as e:
        logger.warning(f"[rollup] aggregate failed: {e}")
        agg = []

    if not agg:
        doc = build_rollup_doc(date_str, 0, 0.0, 0.0, 0)
    else:
        r = agg[0]
        n = r.get("count") or 0
        doc = build_rollup_doc(
            date_str,
            n,
            (r.get("brand_sum") or 0) / n if n else 0.0,
            (r.get("contacts_sum") or 0) / n if n else 0.0,
            int(r.get("avg_content_length") or 0),
        )

    try:
        await db.webclaw_usage_daily.insert_one(dict(doc))
        logger.info(f"[rollup] webclaw_usage_daily written for {date_str}: {doc['count']} scans")
    except Exception as e:
        logger.warning(f"[rollup] insert failed: {e}")
    return doc


__all__ = ["run_daily_rollup"]
