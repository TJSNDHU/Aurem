"""
Social Presence Admin Router (iter 306)
========================================
Admin-only endpoints for Sherlock-style social presence:
  POST /api/admin/social/check        — manual check by business_name + city
  POST /api/admin/social/scan-lead    — re-run check for an existing lead
  GET  /api/admin/social/priority-a   — list Priority A leads (social + no website)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/social", tags=["Social Presence"])

_db = None


def set_db(db):
    global _db
    _db = db


def _require_admin(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "auth required")
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
    try:
        p = pyjwt.decode(authorization.split(" ", 1)[1], secret,
                         algorithms=["HS256"], options={"verify_exp": False})
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")
    if not (p.get("is_admin") or p.get("is_super_admin")
            or p.get("role") in ("admin", "super_admin")):
        raise HTTPException(403, "admin only")
    return p


class CheckRequest(BaseModel):
    business_name: str
    city: Optional[str] = None


@router.post("/check")
async def check(body: CheckRequest, authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    from services.social_presence_checker import (
        check_social_presence, classify_lead,
    )
    res = await check_social_presence(body.business_name, body.city)
    return {**res, "priority_no_website": classify_lead(False, res["social_score"])}


class ScanLeadRequest(BaseModel):
    lead_id: str


@router.post("/scan-lead")
async def scan_lead(body: ScanLeadRequest,
                     authorization: Optional[str] = Header(None)):
    _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "db unavailable")
    lead = await _db.campaign_leads.find_one(
        {"lead_id": body.lead_id},
        {"_id": 0, "business_name": 1, "city": 1, "website_url": 1, "website": 1},
    )
    if not lead:
        raise HTTPException(404, "lead not found")
    has_website = bool((lead.get("website_url") or lead.get("website") or "").strip())
    from services.accurate_scout import _run_social_audit
    await _run_social_audit(_db, body.lead_id,
                              lead.get("business_name") or "",
                              lead.get("city") or "")
    # Override priority/eligibility if lead already has a website
    if has_website:
        from services.social_presence_checker import classify_lead
        fresh_doc = await _db.campaign_leads.find_one(
            {"lead_id": body.lead_id}, {"_id": 0, "social_score": 1}
        ) or {}
        await _db.campaign_leads.update_one(
            {"lead_id": body.lead_id},
            {"$set": {
                "lead_priority": classify_lead(True, fresh_doc.get("social_score", 0)),
                "website_builder_eligible": False,
            }},
        )
    fresh = await _db.campaign_leads.find_one(
        {"lead_id": body.lead_id},
        {"_id": 0, "social_profiles": 1, "social_score": 1,
         "social_audit_at": 1, "website_builder_eligible": 1,
         "lead_priority": 1, "social_usernames_tried": 1},
    )
    return {"ok": True, **(fresh or {})}


@router.get("/priority-a")
async def priority_a(limit: int = Query(50, ge=1, le=200),
                       authorization: Optional[str] = Header(None)):
    """List leads with social presence AND no website — hottest Builder leads."""
    _require_admin(authorization)
    if _db is None:
        return {"leads": []}
    cursor = _db.campaign_leads.find(
        {"lead_priority": "A", "website_builder_eligible": True},
        {"_id": 0, "lead_id": 1, "business_name": 1, "city": 1, "phone": 1,
         "email": 1, "social_profiles": 1, "social_score": 1,
         "lead_priority": 1, "social_audit_at": 1},
    ).sort("social_score", -1).limit(limit)
    leads = await cursor.to_list(length=limit)
    return {"count": len(leads), "leads": leads}
