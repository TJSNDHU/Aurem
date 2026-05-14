"""
Lead Enrichment Router — API endpoints for lead enrichment + ABM + pre-call briefs
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header, Body
from typing import Optional

from utils.tenant import current_tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enrichment", tags=["Lead Enrichment"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.lead_enrichment import set_db as set_le_db
    set_le_db(database)


async def _get_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        user_id = payload.get("user_id", "")
        email = payload.get("email", "")
        if _db is not None:
            user = None
            if user_id:
                user = await _db.users.find_one({"id": user_id}, {"_id": 0})
            if not user and email:
                user = await _db.users.find_one({"email": email}, {"_id": 0})
            if user and (user.get("is_admin") or user.get("role") == "admin"):
                return user
        # Fallback: trust JWT role claim if DB lookup fails
        if payload.get("role") == "admin":
            return {"id": user_id or email, "email": email, "role": "admin"}
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/enrich/{lead_id}")
async def enrich_lead_api(lead_id: str, tenant_id: str = Depends(current_tenant), admin=Depends(_get_admin)):
    from services.lead_enrichment import enrich_lead
    result = await enrich_lead(lead_id, tenant_id)
    return {"status": "ok", **result}


@router.post("/enrich-all")
async def enrich_all_api(body: dict = Body({}), admin=Depends(_get_admin)):
    tenant_id = body.get("tenant_id", "aurem_platform")
    from services.lead_enrichment import enrich_all_new_leads
    result = await enrich_all_new_leads(tenant_id)
    return {"status": "ok", **result}


@router.post("/precall-brief/{lead_id}")
async def precall_brief_api(lead_id: str, tenant_id: str = Depends(current_tenant), admin=Depends(_get_admin)):
    from services.lead_enrichment import write_precall_brief
    result = await write_precall_brief(tenant_id, lead_id)
    return {"status": "ok", **result}


@router.get("/stats")
async def enrichment_stats_api(tenant_id: Optional[str] = None, admin=Depends(_get_admin)):
    from services.lead_enrichment import get_enrichment_stats
    stats = await get_enrichment_stats(tenant_id)
    return {"status": "ok", **stats}
