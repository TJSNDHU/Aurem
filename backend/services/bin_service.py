"""
BIN — Business Intelligence Node
==================================
Each tenant gets a unique BIN ID on account creation.
BIN aggregates live business metrics from all AUREM systems.
Public endpoint for PWA + watch consumption.
"""

import os
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)


def generate_bin_id(tenant_id: str) -> str:
    """Generate a deterministic BIN ID from tenant_id."""
    h = hashlib.sha256(tenant_id.encode()).hexdigest()[:6].upper()
    return f"BIN-{tenant_id[:12]}-{h}"


async def ensure_bin(db, tenant_id: str) -> str:
    """Ensure a BIN ID exists for the tenant. Create if missing."""
    doc = await db.tenant_customers.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "bin_id": 1}
    )
    if doc and doc.get("bin_id"):
        return doc["bin_id"]

    bin_id = generate_bin_id(tenant_id)
    await db.tenant_customers.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"bin_id": bin_id}},
        upsert=True,
    )
    logger.info(f"[BIN] Created {bin_id} for {tenant_id}")
    return bin_id


async def get_bin_data(db, bin_id: str) -> Dict:
    """Aggregate live BIN data from all AUREM subsystems."""
    tenant = await db.tenant_customers.find_one(
        {"bin_id": bin_id}, {"_id": 0}
    )
    if not tenant:
        return None

    tenant_id = tenant.get("tenant_id", "")
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    # 1. Site health score (latest scan)
    site_health = tenant.get("health_score", 0)
    latest_scan = await db.system_auto_repairs.find_one(
        {}, {"_id": 0, "overall_score": 1, "scanned_at": 1},
        sort=[("scanned_at", -1)]
    )
    if latest_scan:
        site_health = latest_scan.get("overall_score", site_health)

    # 2. Active campaigns
    active_campaigns = await db.campaigns.count_documents({"status": {"$in": ["active", "running"]}})

    # 3. Leads in pipeline
    leads_pipeline = await db.campaign_leads.count_documents({"status": {"$nin": ["closed", "converted", "rejected"]}})
    if leads_pipeline == 0:
        leads_pipeline = await db.envoy_outreach.count_documents({"status": {"$nin": ["closed", "completed"]}})

    # 4. Messages sent today
    wa_today = await db.whatsapp_message_log.count_documents({
        "sent_at": {"$gte": today_str}
    })
    email_today = await db.email_logs.count_documents({
        "sent_at": {"$gte": today_str}
    })

    # 5. ORA sessions today
    ora_today = await db.audit_chain.count_documents({
        "event_type": {"$regex": "ora|chat|voice", "$options": "i"},
        "timestamp": {"$gte": today_str}
    })

    # 6. Last repair deployed
    last_repair = await db.system_auto_repairs.find_one(
        {}, {"_id": 0, "completed_at": 1}, sort=[("completed_at", -1)]
    )

    # 7. Monthly usage percent
    usage_doc = await db.usage_tracking.find_one(
        {"tenant_id": tenant_id, "month": now.strftime("%Y-%m")},
        {"_id": 0, "actions_used": 1}
    )
    actions_used = usage_doc.get("actions_used", 0) if usage_doc else 0
    plan_limit = 500  # default starter
    if tenant.get("plan_status") == "active":
        plan_limit = 5000
    usage_pct = min(round(actions_used / max(plan_limit, 1) * 100), 100)

    # 8. Next scheduled scan
    next_scan = None

    return {
        "bin_id": bin_id,
        "tenant_id": tenant_id,
        "generated_at": now.isoformat(),
        "metrics": {
            "site_health_score": site_health,
            "active_campaigns": active_campaigns,
            "leads_in_pipeline": leads_pipeline,
            "messages_sent_today": wa_today + email_today,
            "wa_sent_today": wa_today,
            "email_sent_today": email_today,
            "ora_sessions_today": ora_today,
            "last_repair_deployed": last_repair.get("completed_at") if last_repair else None,
            "monthly_usage_percent": usage_pct,
            "actions_used": actions_used,
            "next_scheduled_scan": next_scan,
        },
    }
