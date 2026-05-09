"""
db_indexes.py — Compound indexes for BIN-scoped queries.
═══════════════════════════════════════════════════════════════════════════
Called once at backend startup. Idempotent (Mongo create_index is safe to
re-run). Indexes guarantee O(1) per-tenant lookups even at scale.
"""
from __future__ import annotations
import logging
from typing import Any, List

from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)

# Collections that are BIN-scoped. Each gets a (business_id, _id) compound
# + a (business_id, ts/created_at) compound for time-sorted queries.
BIN_SCOPED_COLLECTIONS: List[str] = [
    "campaign_leads", "leads", "tenant_customers", "sent_emails",
    "sms_logs", "voice_call_logs", "payment_transactions",
    "customer_repair_log", "customer_health_log", "customer_health_history",
    "pixel_events", "client_errors", "service_usage_log",
    "trial_reminders_sent", "user_integrations", "aurem_workspaces",
    "aurem_billing", "customer_subscriptions", "platform_users",
    "aurem_pixels", "scout_runs", "campaign_runs",
]

TIME_FIELDS_BY_COLLECTION = {
    "campaign_leads":      "created_at",
    "leads":               "created_at",
    "tenant_customers":    "created_at",
    "sent_emails":         "ts",
    "sms_logs":            "ts",
    "voice_call_logs":     "ts",
    "payment_transactions": "created_at",
    "customer_repair_log": "ts",
    "customer_health_log": "ts",
    "customer_health_history": "ts",
    "pixel_events":        "received_at",
    "client_errors":       "ts",
    "service_usage_log":   "ts",
    "trial_reminders_sent": "ts",
    "scout_runs":          "ts",
    "campaign_runs":       "ts",
}


async def ensure_bin_indexes(db) -> dict:
    """Idempotent — call at startup. Returns {collection: created_count}."""
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}
    summary = {}
    for c in BIN_SCOPED_COLLECTIONS:
        try:
            count = 0
            # Compound 1: business_id + _id
            await db[c].create_index(
                [("business_id", ASCENDING)], background=True, sparse=True,
            )
            count += 1
            # Compound 2: business_id + time field DESC for paginated reads
            tf = TIME_FIELDS_BY_COLLECTION.get(c)
            if tf:
                await db[c].create_index(
                    [("business_id", ASCENDING), (tf, DESCENDING)],
                    background=True, sparse=True,
                )
                count += 1
            summary[c] = count
        except Exception as e:
            logger.debug(f"[db_indexes] {c}: {e}")
            summary[c] = f"err:{str(e)[:60]}"
    logger.info(f"[db_indexes] ensured indexes on {len(summary)} collections")
    return {"ok": True, "indexes": summary}
