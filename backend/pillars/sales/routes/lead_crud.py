"""Sales/Campaign — Lead CRUD + DNC + Unsubscribe.

Split from the former monolithic routers/campaign_router.py (2,068 LOC) as
part of Pillar 1 (Sales) logic modularization — iter 262.
"""
import logging
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pillars.sales.routes._shared import (
    _get_db, _verify_admin, _get_today_schedule,
    WHATSAPP_TEMPLATES, EMAIL_SUBJECTS, TARGET_CATEGORIES, COMPETITOR_TEMPLATES,
)

router = APIRouter(prefix="/api/campaign", tags=["AUREM Campaign"])
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# Campaign Overview & Stats
# ══════════════════════════════════════════════
@router.get("/overview")
async def campaign_overview(request: Request):
    """Get the AUREM acquisition campaign overview."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    campaign = await db.campaigns.find_one(
        {"campaign_id": "aurem-acquisition-001"}, {"_id": 0}
    )
    if not campaign:
        return {
            "campaign": None,
            "leads_summary": {"total": 0, "by_status": {}},
            "today_schedule": _get_today_schedule(),
        }

    # Lead counts
    total_leads = await db.campaign_leads.count_documents({})
    statuses = ["new", "scanned", "called", "emailed", "whatsapp_sent", "interested", "signed_up", "not_interested"]
    by_status = {}
    for s in statuses:
        by_status[s] = await db.campaign_leads.count_documents({"status": s})

    return {
        "campaign": campaign,
        "leads_summary": {"total": total_leads, "by_status": by_status},
        "today_schedule": _get_today_schedule(),
    }
@router.get("/stats")
async def campaign_stats(request: Request):
    """Detailed campaign statistics."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    campaign = await db.campaigns.find_one(
        {"campaign_id": "aurem-acquisition-001"}, {"_id": 0, "stats": 1, "status": 1, "created_at": 1}
    )
    stats = campaign.get("stats", {}) if campaign else {}

    # Calculate email open rate
    emails_sent = stats.get("emails_sent", 0)
    email_opens = stats.get("email_opens", 0)
    open_rate = round((email_opens / emails_sent * 100), 1) if emails_sent > 0 else 0

    return {
        "stats": stats,
        "email_open_rate": open_rate,
        "campaign_status": campaign.get("status", "inactive") if campaign else "not_created",
        "campaign_started": campaign.get("created_at") if campaign else None,
    }


# ══════════════════════════════════════════════
# Lead Management
# ══════════════════════════════════════════════
@router.get("/leads")
async def list_leads(
    request: Request,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    search: str = "",
):
    """List campaign leads with filters."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    query = {}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"business_name": {"$regex": search, "$options": "i"}},
            {"contact_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]

    total = await db.campaign_leads.count_documents(query)
    skip = (page - 1) * limit
    leads = await db.campaign_leads.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"leads": leads, "total": total, "page": page, "limit": limit}


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: str, request: Request):
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@router.put("/leads/{lead_id}")
async def update_lead(lead_id: str, data: LeadUpdate, request: Request):
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")
    updates = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
    if not updates:
        return {"success": True, "message": "No changes"}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.campaign_leads.update_one({"lead_id": lead_id}, {"$set": updates})
    return {"success": True}


@router.post("/leads/add")
async def add_lead(request: Request):
    """Manually add a campaign lead with outreach history."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")
    body = await request.json()
    lead_id = body.get("lead_id", f"lead_{uuid.uuid4().hex[:12]}")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "lead_id": lead_id,
        "campaign_id": "aurem-acquisition-001",
        "business_name": body.get("business_name", ""),
        "phone": body.get("phone", ""),
        "email": body.get("email", ""),
        "category": body.get("category", ""),
        "location": body.get("location", ""),
        "website_url": body.get("website_url", ""),
        "score": body.get("score", 50),
        "status": body.get("status", "contacted"),
        "outreach_history": body.get("outreach_history", []),
        "notes": body.get("notes", ""),
        "tags": body.get("tags", []),
        "created_at": now,
        "updated_at": now,
    }
    await db.campaign_leads.update_one({"lead_id": lead_id}, {"$set": doc}, upsert=True)

    # AUTO-TRIGGER: if scout found a business without a website, generate sample site
    if not doc.get("website_url"):
        try:
            from routers.website_builder_router import auto_generate_if_missing
            await auto_generate_if_missing(db, doc)
        except Exception as e:
            logger.warning(f"[CampaignAdd] Website auto-generate failed: {e}")

    return {"success": True, "lead_id": lead_id}


# ══════════════════════════════════════════════
# Campaign Actions — Send from Dashboard
# ══════════════════════════════════════════════
class DNCEntry(BaseModel):
    phone: str = ""
    email: str = ""
    reason: str = "opt-out"


@router.post("/do-not-contact")
async def add_dnc(data: DNCEntry, request: Request):
    """Add to do-not-contact list."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    doc = {
        "phone": data.phone,
        "email": data.email.lower() if data.email else "",
        "reason": data.reason,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.do_not_contact.insert_one(doc)

    # Remove matching leads
    removal_query = {"$or": []}
    if data.phone:
        removal_query["$or"].append({"phone": data.phone})
    if data.email:
        removal_query["$or"].append({"email": {"$regex": f"^{data.email}$", "$options": "i"}})

    if removal_query["$or"]:
        result = await db.campaign_leads.update_many(removal_query, {"$set": {"status": "not_interested", "dnc": True}})
        return {"success": True, "leads_flagged": result.modified_count}

    return {"success": True, "leads_flagged": 0}


@router.get("/do-not-contact")
async def list_dnc(request: Request, page: int = 1, limit: int = 50):
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")
    total = await db.do_not_contact.count_documents({})
    skip = (page - 1) * limit
    docs = await db.do_not_contact.find({}, {"_id": 0}).sort("added_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"entries": docs, "total": total}


# ══════════════════════════════════════════════
# Unsubscribe (public endpoint — no auth)
# ══════════════════════════════════════════════
@router.get("/unsubscribe")
async def unsubscribe(email: str = ""):
    """Public unsubscribe endpoint for CASL compliance."""
    db = _get_db()
    if not db or not email:
        return {"success": False, "message": "Invalid request"}

    await db.do_not_contact.update_one(
        {"email": email.lower()},
        {"$setOnInsert": {
            "email": email.lower(),
            "phone": "",
            "reason": "email-unsubscribe",
            "added_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    await db.campaign_leads.update_many(
        {"email": {"$regex": f"^{email}$", "$options": "i"}},
        {"$set": {"status": "not_interested", "dnc": True}},
    )
    return {"success": True, "message": f"{email} has been unsubscribed."}


# ══════════════════════════════════════════════
# Campaign Control
# ══════════════════════════════════════════════
