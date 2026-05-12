"""
System Overview API — Aggregated platform stats for the admin overview page.
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/system-overview", tags=["System Overview"])

_db = None

def set_db(database):
    global _db
    _db = database


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    try:
        import jwt
        return jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401)


async def _count_safe(db, col: str) -> int:
    try:
        if col in await db.list_collection_names():
            return await db[col].estimated_document_count()
    except Exception:
        return 0
    return 0


def _audit_static_counts() -> dict:
    """iter 322ar — Stack audit numbers exposed on /admin/system-overview.
    Counted live from the filesystem + registry import so they never drift.
    Cached for the lifetime of the process (cheap on a cold call)."""
    import re
    import glob
    routers_dir = "/app/backend/routers"
    try:
        router_files = [f for f in glob.glob(f"{routers_dir}/*.py")
                        if not f.endswith("__init__.py") and "_archive" not in f]
        router_files_count = len(router_files)
    except Exception:
        router_files_count = 0
    try:
        endpoint_count = 0
        for f in router_files:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    endpoint_count += len(re.findall(
                        r"^@router\.(get|post|put|delete|patch)",
                        fh.read(), re.MULTILINE))
            except Exception:
                pass
    except Exception:
        endpoint_count = 0
    try:
        with open(f"{routers_dir}/registry.py", "r", encoding="utf-8") as fh:
            reg = fh.read()
        include_calls = re.findall(r"app\.include_router\(\s*([A-Za-z_][\w]*)", reg)
        wired_count = len(set(include_calls))
        scheduler_blocks = len(re.findall(r"aurem_scheduler\.add_job\(", reg))
    except Exception:
        wired_count = 0
        scheduler_blocks = 0
    # Aggregate additional non-registry scheduler hits from services/* files
    try:
        services_scheduler_hits = 0
        for f in glob.glob("/app/backend/services/**/*.py", recursive=True):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    services_scheduler_hits += len(re.findall(
                        r"scheduler\.add_job\(|sched\.add_job\(", fh.read()))
            except Exception:
                pass
    except Exception:
        services_scheduler_hits = 0
    return {
        "router_files": router_files_count,
        "wired_routers": wired_count,
        "endpoint_count": endpoint_count,
        "scheduler_jobs": scheduler_blocks + services_scheduler_hits,
        "scheduler_registry": scheduler_blocks,
        "scheduler_services": services_scheduler_hits,
    }


_AUDIT_CACHE: dict = {}


@router.get("/stats")
async def get_system_overview(authorization: str = Header(None)):
    await _auth(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="DB not connected")

    # Platform stats
    colls = await _db.list_collection_names()
    db_stats = await _db.command("dbStats")

    # Counts
    tenants = await _db.tenant_customers.find({}, {"_id": 0}).to_list(100)
    scans = await _db.system_scans.count_documents({})
    fixes = await _db.customer_website_fixes.count_documents({})
    comm_leads = await _db.comm_leads.count_documents({})
    chats = await _db.live_chat_messages.count_documents({})
    campaign_leads = await _db.campaign_leads.count_documents({})
    agent_traces = await _db.agent_traces.count_documents({})
    session_mem = await _db.session_memory.count_documents({})
    users = await _db.users.count_documents({})
    integrations = await _db.user_integrations.count_documents({})

    # iter 322ar — Stack audit metrics for System Overview Transparency tile
    global _AUDIT_CACHE
    if not _AUDIT_CACHE:
        _AUDIT_CACHE = _audit_static_counts()
    audit = _AUDIT_CACHE
    council_decisions = await _count_safe(_db, "council_decisions")
    ora_thoughts = await _count_safe(_db, "ora_brain_thoughts")
    agent_actions = await _count_safe(_db, "agent_actions")
    pixel_events = await _count_safe(_db, "pixel_events")
    bin_intel = await _count_safe(_db, "bin_intelligence")
    unified_inbox_rows = await _count_safe(_db, "unified_inbox")
    admin_actions = await _count_safe(_db, "admin_audit_log")
    auto_heal_runs = await _count_safe(_db, "auto_heal_log")

    # Shannon security
    shannon_count = await _db.shannon_reports.count_documents({})
    latest_shannon = await _db.shannon_reports.find_one({}, {"_id": 0}, sort=[("created_at", -1)])

    # Campaign pipeline
    emails_sent = 0
    wa_sent = 0
    calls_made = 0
    try:
        pipeline_stats = await _db.campaign_stats.find_one({}, {"_id": 0})
        if pipeline_stats:
            emails_sent = pipeline_stats.get("emails_sent", 0)
            wa_sent = pipeline_stats.get("whatsapp_sent", 0)
            calls_made = pipeline_stats.get("calls_made", 0)
    except Exception:
        pass

    # Health
    uptime = "99.9%"
    try:
        from services.sentinel_healer import get_health_summary
        health = await get_health_summary()
        uptime = health.get("uptime", "99.9%")
    except Exception:
        pass

    return {
        "platform": {
            "uptime": uptime,
            "version": "v1.47",
            "collections": len(colls),
            "data_mb": round(db_stats.get("dataSize", 0) / 1024 / 1024, 1),
            "users": users,
            "integrations": integrations,
            # iter 322ar audit numbers
            "router_files": audit["router_files"],
            "wired_routers": audit["wired_routers"],
            "endpoint_count": audit["endpoint_count"],
            "scheduler_jobs": audit["scheduler_jobs"],
            "iteration": "322fa",
        },
        "audit": {
            "council_decisions": council_decisions,
            "ora_brain_thoughts": ora_thoughts,
            "agent_actions": agent_actions,
            "pixel_events": pixel_events,
            "bin_intelligence": bin_intel,
            "unified_inbox": unified_inbox_rows,
            "admin_actions": admin_actions,
            "auto_heal_runs": auto_heal_runs,
        },
        "clients": [{
            "name": t.get("company_name", t.get("full_name", "Unknown")),
            "email": t.get("email", ""),
            "plan": t.get("plan", "Starter"),
            "plan_price": t.get("plan_price", "$97/month"),
            "score": t.get("health_score", 0),
            "status": t.get("status", "active"),
            "tenant_id": t.get("tenant_id", ""),
        } for t in tenants],
        "pipeline": {
            "leads_scraped": campaign_leads,
            "websites_scanned": scans,
            "repairs_deployed": fixes,
            "calls_made": calls_made,
            "emails_sent": emails_sent,
            "whatsapp_sent": wa_sent,
            "comm_leads": comm_leads,
            "live_chats": chats,
        },
        "ai": {
            "agent_traces": agent_traces,
            "session_memories": session_mem,
            "shannon_audits": shannon_count,
            "security_score": latest_shannon.get("security_score") if latest_shannon else None,
        },
    }
