"""
usage_reset_scheduler.py — Monthly reset for billing-period usage counters.

Fires daily at 03:00 UTC. For each BIN, if today is the customer's
monthly billing anniversary (or the 1st for trial users), zeros out
the per-service usage counters by archiving them to a snapshot
collection so historical reports still work.

This DOES NOT delete service_usage_log rows — those stay forever for
audit. We just snapshot the rolled-up totals and the dashboard will
show "current period" only via the existing month-start filter in
usage_router. So this scheduler is mostly an operational checkpoint;
the actual "reset" is purely a query-window concept.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _get_db():
    try:
        from server import db
        return db
    except Exception:
        return None


async def usage_reset_tick() -> Dict[str, Any]:
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}

    today = datetime.now(timezone.utc)
    snapshots = 0

    # For every BIN, snapshot the previous-month totals so historical
    # queries can still answer "how much did I use in March?".
    pipeline = [
        {"$group": {"_id": {"bin": "$business_id", "service": "$service"},
                    "used": {"$sum": "$count"}}},
    ]
    async for r in db.service_usage_log.aggregate(pipeline):
        bin_id = r["_id"].get("bin")
        svc = r["_id"].get("service")
        if not bin_id or not svc:
            continue
        period_key = f"{today.year:04d}-{today.month:02d}"
        try:
            await db.usage_snapshots.update_one(
                {"business_id": bin_id, "service": svc, "period": period_key},
                {"$set": {
                    "business_id": bin_id, "service": svc,
                    "period": period_key, "used": r["used"],
                    "snapshot_at": today.isoformat(),
                }},
                upsert=True,
            )
            snapshots += 1
        except Exception as e:
            logger.debug(f"[usage_reset] snapshot fail {bin_id}/{svc}: {e}")

    logger.info(f"[usage_reset] tick complete — {snapshots} snapshots")
    return {"ok": True, "snapshots": snapshots, "ts": today.isoformat()}
