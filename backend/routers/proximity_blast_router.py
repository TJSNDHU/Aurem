"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Proximity Blast Router
======================
Geofenced local lead discovery & promotion campaigns.
Add-on: $49/month for Starter/Growth tiers.
"""
import logging
import os
from fastapi import APIRouter, Depends, Header, HTTPException, Body

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/proximity", tags=["Proximity Blast"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.proximity_blast import set_db as set_pb_db
    set_pb_db(database)


async def _get_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        import jwt as pyjwt
        secret = os.environ.get("JWT_SECRET", "")
        token = authorization.replace("Bearer ", "")
        payload = pyjwt.decode(token, secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if not user_id or not _db:
            raise HTTPException(status_code=401, detail="Unauthorized")
        user = await _db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/config")
async def get_config(user=Depends(_get_user)):
    """Get proximity blast configuration for the tenant."""
    from services.proximity_blast import get_proximity_config
    tenant_id = user.get("tenant_id", "aurem_platform")
    return await get_proximity_config(tenant_id)


@router.post("/config")
async def update_config(body: dict = Body(...), user=Depends(_get_user)):
    """Update proximity blast configuration."""
    from services.proximity_blast import save_proximity_config
    tenant_id = user.get("tenant_id", "aurem_platform")
    return await save_proximity_config(tenant_id, body)


@router.post("/blast")
async def run_blast(body: dict = Body(...), user=Depends(_get_user)):
    """Execute a proximity blast — discover leads within radius.
    Body: {lat: float, lng: float, radius_km: float, count?: int}
    """
    from services.proximity_blast import run_blast as do_blast
    tenant_id = user.get("tenant_id", "aurem_platform")

    lat = body.get("lat")
    lng = body.get("lng")
    radius_km = body.get("radius_km", 10)
    count = min(body.get("count", 20), 50)

    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="lat and lng are required")
    if radius_km < 1 or radius_km > 50:
        raise HTTPException(status_code=400, detail="radius_km must be 1-50")

    return await do_blast(tenant_id, lat, lng, radius_km, count)


@router.get("/campaigns")
async def list_campaigns(user=Depends(_get_user)):
    """List past proximity blast campaigns."""
    tenant_id = user.get("tenant_id", "aurem_platform")
    if _db is None:
        return {"campaigns": []}
    cursor = _db.proximity_campaigns.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("created_at", -1).limit(20)
    campaigns = await cursor.to_list(length=20)
    return {"campaigns": campaigns}


@router.post("/deploy-envoy")
async def deploy_envoy(body: dict = Body(...), user=Depends(_get_user)):
    """Deploy Envoy outreach agent on discovered proximity leads.
    Body: {leads: [...], radius_km: float}
    Creates outreach tasks for each lead via the Envoy agent.
    """
    from datetime import datetime, timezone as tz
    tenant_id = user.get("tenant_id", "aurem_platform")
    leads = body.get("leads", [])
    radius_km = body.get("radius_km", 10)

    if not leads:
        raise HTTPException(status_code=400, detail="No leads provided")

    # Generate outreach scripts for each lead
    outreach_tasks = []
    for lead in leads[:50]:
        task = {
            "tenant_id": tenant_id,
            "lead_id": lead.get("lead_id"),
            "business_name": lead.get("business_name"),
            "owner_name": lead.get("owner_name"),
            "email": lead.get("email"),
            "phone": lead.get("phone"),
            "business_type": lead.get("business_type"),
            "distance_km": lead.get("distance_km"),
            "outreach_type": "proximity_blast",
            "radius_km": radius_km,
            "status": "queued",
            "script": f"Hi {lead.get('owner_name', 'there')}, I noticed your {lead.get('business_type', 'business')} is just {lead.get('distance_km', 'nearby')}km from a partner business in our network. We help local businesses like yours automate lead generation and customer engagement. Would you be open to a quick 10-minute discovery call this week?",
            "created_at": datetime.now(tz.utc).isoformat(),
        }
        outreach_tasks.append(task)

    # Store in envoy_outreach collection
    if _db is not None and outreach_tasks:
        clean_tasks = [{k: v for k, v in t.items()} for t in outreach_tasks]
        await _db.envoy_outreach.insert_many(clean_tasks)

    return {
        "deployed": True,
        "tasks_created": len(outreach_tasks),
        "radius_km": radius_km,
        "agent": "envoy",
        "status": "Outreach scripts generated and queued for delivery",
    }


@router.post("/envoy-feedback")
async def envoy_feedback(body: dict = Body(...), user=Depends(_get_user)):
    """Record outreach response for conversion feedback loop.
    Body: {lead_id: str, response_type: 'opened'|'replied'|'converted'|'bounced'|'ignored'}
    """
    from services.oracle_proactive import update_envoy_response
    tenant_id = user.get("tenant_id", "aurem_platform")
    lead_id = body.get("lead_id")
    response_type = body.get("response_type")
    if not lead_id or response_type not in ("opened", "replied", "converted", "bounced", "ignored"):
        raise HTTPException(status_code=400, detail="lead_id and valid response_type required")
    return await update_envoy_response(tenant_id, lead_id, response_type)


@router.get("/conversion-metrics")
async def conversion_metrics(user=Depends(_get_user)):
    """Get conversion metrics for the tenant's Envoy pipeline."""
    from services.oracle_proactive import get_conversion_metrics
    tenant_id = user.get("tenant_id", "aurem_platform")
    return await get_conversion_metrics(tenant_id)
