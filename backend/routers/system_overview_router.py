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
