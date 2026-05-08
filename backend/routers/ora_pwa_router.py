"""
ORA AI PWA Lead Capture Router
================================
Handles the 2-field pre-install gate and post-install profile enrichment.

Endpoints:
  POST /api/ora/capture    → 2-field gate (email + phone)
  PUT  /api/ora/enrich     → Post-install profile (name, occupation, etc.)
  GET  /api/ora/lead/:email → Get lead data
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ora", tags=["ora-pwa"])

db = None

def set_db(database):
    global db
    db = database


class LeadCaptureRequest(BaseModel):
    email: str
    phone: str
    country_code: str = "+1"
    source: str = "aurem.live"
    user_agent: Optional[str] = None
    referrer: Optional[str] = None


class ProfileEnrichRequest(BaseModel):
    email: str
    full_name: Optional[str] = None
    occupation: Optional[str] = None
    company: Optional[str] = None
    use_type: Optional[str] = None  # "business" or "personal"
    challenge: Optional[str] = None  # dropdown selection
    website: Optional[str] = None   # business website (optional)


@router.post("/capture")
async def capture_lead(body: LeadCaptureRequest):
    """
    2-field pre-install gate.
    Saves email + phone to MongoDB leads collection.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    email = body.email.strip().lower()
    phone = body.phone.strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    if not phone or len(phone) < 7:
        raise HTTPException(status_code=400, detail="Valid phone number required")

    lead_data = {
        "email": email,
        "phone": phone,
        "country_code": body.country_code,
        "source": body.source,
        "user_agent": body.user_agent,
        "referrer": body.referrer,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": "captured",
        "enriched": False,
    }

    await db.ora_leads.update_one(
        {"email": email},
        {"$set": lead_data, "$setOnInsert": {"first_seen": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )

    logger.info(f"[ORA] Lead captured: {email}")
    return {"success": True, "message": "Access granted", "email": email}


@router.put("/enrich")
async def enrich_lead(body: ProfileEnrichRequest):
    """
    Post-install profile enrichment.
    Updates existing lead with additional fields.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    email = body.email.strip().lower()
    update = {"enriched": True, "enriched_at": datetime.now(timezone.utc).isoformat()}

    if body.full_name:
        update["full_name"] = body.full_name
    if body.occupation:
        update["occupation"] = body.occupation
    if body.company:
        update["company"] = body.company
    if body.use_type:
        update["use_type"] = body.use_type
    if body.challenge:
        update["challenge"] = body.challenge
    if body.website:
        update["website"] = body.website

    result = await db.ora_leads.update_one(
        {"email": email},
        {"$set": update},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")

    return {"success": True, "message": "Profile updated"}


@router.get("/lead/{email}")
async def get_lead(email: str):
    """Get lead data by email."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    lead = await db.ora_leads.find_one(
        {"email": email.strip().lower()},
        {"_id": 0}
    )

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return lead


@router.get("/leads")
async def list_leads():
    """Admin: List all ORA leads with their collected details."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    cursor = db.ora_leads.find({}, {"_id": 0}).sort("captured_at", -1)
    leads = await cursor.to_list(length=500)
    return {"leads": leads, "total": len(leads)}


class ReferralRequest(BaseModel):
    email: str
    referred_emails: list


@router.post("/referral")
async def track_referral(body: ReferralRequest):
    """Track referral shares for social media unlock."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    email = body.email.strip().lower()
    referred = [e.strip().lower() for e in body.referred_emails if e.strip()]

    if not referred:
        raise HTTPException(status_code=400, detail="At least one referral required")

    result = await db.ora_leads.update_one(
        {"email": email},
        {
            "$addToSet": {"referrals": {"$each": referred}},
            "$set": {"last_referral_at": datetime.now(timezone.utc).isoformat()},
        },
    )

    # Check total referrals
    lead = await db.ora_leads.find_one({"email": email}, {"_id": 0, "referrals": 1})
    total = len(lead.get("referrals", [])) if lead else 0
    unlocked = total >= 5

    if unlocked:
        await db.ora_leads.update_one(
            {"email": email},
            {"$set": {"social_unlocked": True, "social_unlocked_at": datetime.now(timezone.utc).isoformat()}},
        )

    return {"success": True, "total_referrals": total, "unlocked": unlocked, "remaining": max(0, 5 - total)}


@router.put("/name")
async def update_user_name(body: dict):
    """Update user name from ORA conversation."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    email = body.get("email", "").strip().lower()
    name = body.get("name", "").strip()

    if not email or not name:
        raise HTTPException(status_code=400, detail="Email and name required")

    await db.ora_leads.update_one(
        {"email": email},
        {"$set": {"full_name": name, "name_updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"success": True}


@router.get("/settings")
async def get_ora_settings():
    """Get ORA PWA settings (review URL, etc.)."""
    if db is None:
        return {"review_url": "", "google_review_url": ""}

    settings = await db.ora_settings.find_one({"type": "pwa"}, {"_id": 0})
    return settings or {"review_url": "", "google_review_url": ""}


@router.put("/settings")
async def update_ora_settings(body: dict):
    """Admin: Update ORA PWA settings."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    allowed = {"google_review_url", "review_url"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid settings provided")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.ora_settings.update_one(
        {"type": "pwa"},
        {"$set": updates},
        upsert=True,
    )
    return {"success": True}
