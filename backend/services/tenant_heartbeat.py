"""
Per-Tenant Heartbeat — Health monitoring per active tenant.
Runs every 10 Sentinel cycles. Checks pipeline, leads, sessions, knowledge freshness.
"""

import logging
from datetime import datetime, timezone, timedelta

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
        import os
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


async def run_tenant_heartbeat(tenant_id: str) -> dict:
    """Run health check for a single tenant."""
    db = _get_db()
    if db is None:
        return {"tenant_id": tenant_id, "health_score": 0, "pipeline_status": "unknown"}

    now = datetime.now(timezone.utc)
    score = 100
    issues = []

    # 1. Pipeline status — last run < 24h ago?
    pipeline_status = "healthy"
    last_run = await db.pipeline_runs.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "started_at": 1, "final_status": 1},
        sort=[("started_at", -1)]
    )
    if last_run:
        last_ts = datetime.fromisoformat(last_run["started_at"])
        hours_since = (now - last_ts).total_seconds() / 3600
        if hours_since > 48:
            pipeline_status = "degraded"
            score -= 30
            issues.append(f"No pipeline run in {int(hours_since)}h")
        elif hours_since > 24:
            pipeline_status = "stale"
            score -= 15
            issues.append(f"Last pipeline run {int(hours_since)}h ago")
        if last_run.get("final_status", "").startswith("abort") or last_run.get("final_status") == "error":
            pipeline_status = "degraded"
            score -= 20
            issues.append(f"Last run status: {last_run['final_status']}")
    else:
        pipeline_status = "no_runs"
        score -= 10

    # 2. Last lead processed
    last_lead = await db.leads.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "created_at": 1},
        sort=[("created_at", -1)]
    )
    last_lead_ts = None
    if last_lead and last_lead.get("created_at"):
        try:
            last_lead_ts = last_lead["created_at"]
            lead_dt = datetime.fromisoformat(last_lead_ts) if isinstance(last_lead_ts, str) else last_lead_ts
            lead_hours = (now - lead_dt).total_seconds() / 3600
            if lead_hours > 48:
                score -= 10
                issues.append(f"No new leads in {int(lead_hours)}h")
        except Exception:
            pass

    # 3. Last ORA session
    last_session = await db.chat_sessions.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "created_at": 1},
        sort=[("created_at", -1)]
    )
    last_session_ts = None
    if last_session and last_session.get("created_at"):
        last_session_ts = last_session["created_at"]

    # 4. Knowledge freshness
    knowledge_count = await db.known_fixes.count_documents({"tenant_id": tenant_id})
    knowledge_age_hours = 0
    last_knowledge = await db.known_fixes.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "last_success": 1},
        sort=[("last_success", -1)]
    )
    if last_knowledge and last_knowledge.get("last_success"):
        try:
            k_dt = datetime.fromisoformat(last_knowledge["last_success"])
            knowledge_age_hours = int((now - k_dt).total_seconds() / 3600)
            if knowledge_age_hours > 168:  # 7 days
                score -= 10
                issues.append(f"Knowledge not updated in {knowledge_age_hours}h")
        except Exception:
            pass

    score = max(0, min(100, score))

    health_doc = {
        "tenant_id": tenant_id,
        "timestamp": now.isoformat(),
        "pipeline_status": pipeline_status,
        "last_lead_processed": last_lead_ts,
        "last_session": last_session_ts,
        "knowledge_entries": knowledge_count,
        "knowledge_age_hours": knowledge_age_hours,
        "health_score": score,
        "issues": issues,
        "status": "healthy" if score >= 70 else "degraded" if score >= 40 else "down",
    }

    # Store in tenant_health collection
    await db.tenant_health.update_one(
        {"tenant_id": tenant_id},
        {"$set": health_doc},
        upsert=True,
    )

    return health_doc


async def run_all_heartbeats() -> dict:
    """Run heartbeat for all active tenants."""
    db = _get_db()
    if db is None:
        return {"checked": 0}

    # Get active tenants (those with pipeline runs in last 7 days)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    pipeline = db.pipeline_runs.aggregate([
        {"$match": {"started_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$tenant_id"}},
    ])
    tenant_ids = [doc["_id"] async for doc in pipeline if doc.get("_id")]

    # Also include tenants from users table
    users = await db.users.find(
        {"is_admin": True}, {"_id": 0, "id": 1}
    ).to_list(100)
    for u in users:
        if u.get("id") and u["id"] not in tenant_ids:
            tenant_ids.append(u["id"])

    results = []
    alerts = []
    for tid in tenant_ids:
        health = await run_tenant_heartbeat(tid)
        results.append(health)
        if health["health_score"] < 50:
            alerts.append(health)

    # Send alerts for unhealthy tenants
    for alert in alerts:
        try:
            from services.flow_coordinator import _send_alert
            await _send_alert(
                f"Tenant {alert['tenant_id'][:12]} needs attention.\n"
                f"Health score: {alert['health_score']}/100\n"
                f"Issues: {', '.join(alert.get('issues', [])[:3])}",
                priority="high"
            )
        except Exception:
            pass

    return {
        "checked": len(results),
        "healthy": sum(1 for r in results if r["status"] == "healthy"),
        "degraded": sum(1 for r in results if r["status"] == "degraded"),
        "down": sum(1 for r in results if r["status"] == "down"),
        "alerts_sent": len(alerts),
    }


async def get_tenant_health(tenant_id: str) -> dict:
    """Get latest health status for a tenant."""
    db = _get_db()
    if db is None:
        return {}
    doc = await db.tenant_health.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    return doc or {}


async def get_all_health() -> list:
    """Get health status for all monitored tenants."""
    db = _get_db()
    if db is None:
        return []
    cursor = db.tenant_health.find({}, {"_id": 0}).sort("health_score", 1)
    return await cursor.to_list(length=100)
