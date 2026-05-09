"""
backfill_business_id.py — One-shot migration that pulls business_id onto
every BIN-scoped doc that's missing it. Idempotent + safe to re-run.

Strategy: for each scoped collection, find docs lacking business_id.
Resolve from existing tenant_id / user_id / owner_id / email by joining
against platform_users. Write business_id back. Log untouched orphans.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

LINK_FIELDS = ["tenant_id", "user_id", "owner_id", "plat_user_id"]

SCOPED_COLLECTIONS = [
    "campaign_leads", "leads", "tenant_customers", "sent_emails",
    "sms_logs", "voice_call_logs", "payment_transactions",
    "customer_repair_log", "customer_health_log",
    "pixel_events", "client_errors", "service_usage_log",
    "user_integrations", "aurem_workspaces", "scout_runs", "campaign_runs",
]


async def _build_uid_to_bin_map(db) -> Dict[str, str]:
    m: Dict[str, str] = {}
    async for u in db.platform_users.find(
        {}, {"_id": 0, "user_id": 1, "id": 1, "business_id": 1, "email": 1},
    ):
        bin_id = u.get("business_id")
        if not bin_id:
            continue
        for k in ("user_id", "id"):
            v = u.get(k)
            if v:
                m[v] = bin_id
        em = u.get("email")
        if em:
            m[em.lower()] = bin_id
    return m


async def backfill_business_id(db) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}
    uid_map = await _build_uid_to_bin_map(db)
    summary: Dict[str, Dict[str, int]] = {}

    for c in SCOPED_COLLECTIONS:
        touched = 0
        orphan = 0
        try:
            cursor = db[c].find(
                {"$or": [{"business_id": {"$exists": False}}, {"business_id": None}, {"business_id": ""}]},
                {"_id": 1, "tenant_id": 1, "user_id": 1, "owner_id": 1, "plat_user_id": 1, "email": 1},
            )
            async for d in cursor:
                resolved = None
                for f in LINK_FIELDS:
                    v = d.get(f)
                    if v and v in uid_map:
                        resolved = uid_map[v]
                        break
                if not resolved:
                    em = (d.get("email") or "").lower() if d.get("email") else ""
                    if em and em in uid_map:
                        resolved = uid_map[em]
                if resolved:
                    await db[c].update_one(
                        {"_id": d["_id"]}, {"$set": {"business_id": resolved}}
                    )
                    touched += 1
                else:
                    orphan += 1
        except Exception as e:
            summary[c] = {"error": str(e)[:120]}
            continue
        summary[c] = {"backfilled": touched, "orphan": orphan}

    total_touched = sum(v.get("backfilled", 0) for v in summary.values() if isinstance(v, dict))
    total_orphan = sum(v.get("orphan", 0) for v in summary.values() if isinstance(v, dict))
    logger.info(f"[backfill] business_id touched={total_touched} orphan={total_orphan}")
    return {"ok": True, "total_backfilled": total_touched, "total_orphan": total_orphan, "by_collection": summary}
