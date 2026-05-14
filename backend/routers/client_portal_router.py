"""
Client Portal Router — BIN, Onboarding, Activity Feed, Profile
================================================================
All client-facing endpoints beyond the base dashboard.
"""

import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/client", tags=["Client Portal"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


async def _auth(request: Request):
    import jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        return jwt.decode(auth.split(" ", 1)[1], (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))), algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


# ═══════════════════════════════════════════════════
# BIN — Business Intelligence Node (PUBLIC)
# ═══════════════════════════════════════════════════

@router.get("/bin/{bin_id}")
async def get_bin(bin_id: str):
    """Public BIN endpoint — returns live aggregated metrics. Rate limited: 60/min."""
    db = _get_db()
    if not db:
        raise HTTPException(503, "Database not available")

    from services.bin_service import get_bin_data
    data = await get_bin_data(db, bin_id)
    if not data:
        raise HTTPException(404, "BIN not found")
    return data


@router.get("/bin-id")
async def get_my_bin_id(request: Request):
    """Get the BIN ID for the logged-in user."""
    user = await _auth(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "Database not available")

    tenant_id = user.get("tenant_id", user.get("user_id", ""))
    from services.bin_service import ensure_bin
    bin_id = await ensure_bin(db, tenant_id)
    return {"bin_id": bin_id, "tenant_id": tenant_id}


# ═══════════════════════════════════════════════════
# ONBOARDING
# ═══════════════════════════════════════════════════

class OnboardingStep1(BaseModel):
    business_name: str
    website_url: str
    industry: Optional[str] = "general"


@router.get("/onboarding-status")
async def onboarding_status(request: Request):
    """Check if onboarding is complete."""
    user = await _auth(request)
    db = _get_db()
    if not db:
        return {"onboarding_complete": True}

    email = user.get("email", "")
    workspace = await db.aurem_workspaces.find_one({"owner_email": email}, {"_id": 0, "onboarding_complete": 1, "website": 1})
    has_scans = False
    if workspace and workspace.get("website"):
        has_scans = await db.system_auto_repairs.count_documents({"site_url": workspace["website"]}) > 0

    return {
        "onboarding_complete": workspace.get("onboarding_complete", False) if workspace else False,
        "has_workspace": workspace is not None,
        "has_scans": has_scans,
    }


@router.post("/onboarding/step1")
async def onboarding_step1(body: OnboardingStep1, request: Request):
    """Save business info and create/update workspace."""
    user = await _auth(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "Database not available")

    email = user.get("email", "")
    user_id = user.get("user_id", "")
    now = datetime.now(timezone.utc).isoformat()

    # Ensure website has protocol
    website = body.website_url.strip()
    if website and not website.startswith("http"):
        website = f"https://{website}"

    # Update or create workspace
    await db.aurem_workspaces.update_one(
        {"owner_email": email},
        {"$set": {
            "business_name": body.business_name,
            "website": website,
            "industry": body.industry,
            "updated_at": now,
        }, "$setOnInsert": {
            "owner_email": email,
            "created_at": now,
            "plan": "trial",
            "status": "active",
        }},
        upsert=True,
    )

    # Update user record
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"business_name": body.business_name, "website": website}},
    )

    return {"success": True, "website": website}


@router.post("/onboarding/complete")
async def onboarding_complete(request: Request):
    """Mark onboarding as complete."""
    user = await _auth(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "Database not available")

    email = user.get("email", "")
    tenant_id = user.get("tenant_id", user.get("user_id", ""))

    await db.aurem_workspaces.update_one(
        {"owner_email": email},
        {"$set": {"onboarding_complete": True}},
    )

    # Ensure BIN exists
    from services.bin_service import ensure_bin
    bin_id = await ensure_bin(db, tenant_id)

    return {"success": True, "bin_id": bin_id}


# ═══════════════════════════════════════════════════
# ACTIVITY FEED
# ═══════════════════════════════════════════════════

@router.get("/activity")
async def get_activity_feed(request: Request):
    """Get last 10 activity events for the client."""
    user = await _auth(request)
    db = _get_db()
    if not db:
        return {"events": []}

    tenant_id = user.get("tenant_id", user.get("user_id", ""))

    # Pull from audit_chain — has all system events
    events = []
    cursor = db.audit_chain.find(
        {},
        {"_id": 0, "event_type": 1, "description": 1, "timestamp": 1, "agent": 1, "category": 1}
    ).sort("timestamp", -1).limit(15)

    async for doc in cursor:
        evt_type = doc.get("event_type", doc.get("category", ""))
        desc = doc.get("description", "")
        ts = doc.get("timestamp", "")
        agent = doc.get("agent", "")

        # Classify icon
        icon = "activity"
        if any(k in evt_type.lower() for k in ["scan", "repair", "fix", "heal"]):
            icon = "scan"
        elif any(k in evt_type.lower() for k in ["email", "whatsapp", "message", "outreach"]):
            icon = "message"
        elif any(k in evt_type.lower() for k in ["lead", "pipeline", "campaign"]):
            icon = "lead"
        elif any(k in evt_type.lower() for k in ["voice", "call", "ora"]):
            icon = "voice"
        elif any(k in evt_type.lower() for k in ["security", "shannon", "threat"]):
            icon = "security"

        events.append({
            "icon": icon,
            "type": evt_type,
            "description": desc[:200] if desc else evt_type,
            "timestamp": ts,
            "agent": agent,
        })

    return {"events": events[:10]}


# ═══════════════════════════════════════════════════
# CLIENT PROFILE SETTINGS
# ═══════════════════════════════════════════════════

class ProfileUpdate(BaseModel):
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    services: Optional[List[str]] = None
    tone: Optional[str] = None
    website: Optional[str] = None


@router.put("/profile")
async def update_profile(body: ProfileUpdate, request: Request):
    """Update client business profile."""
    user = await _auth(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "Database not available")

    email = user.get("email", "")
    updates = {}
    ai_updates = {}

    if body.business_name is not None:
        updates["business_name"] = body.business_name
    if body.website is not None:
        updates["website"] = body.website
    if body.business_description is not None:
        ai_updates["ai_context.business_description"] = body.business_description
    if body.services is not None:
        ai_updates["ai_context.services"] = body.services
    if body.tone is not None:
        ai_updates["ai_context.tone"] = body.tone

    all_updates = {**updates, **ai_updates, "updated_at": datetime.now(timezone.utc).isoformat()}

    if all_updates:
        await db.aurem_workspaces.update_one(
            {"owner_email": email},
            {"$set": all_updates},
        )

    return {"success": True, "updated_fields": list(all_updates.keys())}


# ═══════════════════════════════════════════════════
# PUSH NOTIFICATION PREFERENCES
# ═══════════════════════════════════════════════════

class NotificationPreferences(BaseModel):
    scan_complete: bool = True
    repair_deployed: bool = True
    new_lead: bool = True
    ora_action_required: bool = True
    morning_brief: bool = True


@router.get("/notification-preferences")
async def get_notification_preferences(request: Request):
    """Get push notification preferences."""
    user = await _auth(request)
    db = _get_db()
    if not db:
        return NotificationPreferences().dict()

    user_id = user.get("user_id", "")
    doc = await db.push_preferences.find_one({"user_id": user_id}, {"_id": 0})
    if doc:
        return {k: v for k, v in doc.items() if k != "user_id"}
    return NotificationPreferences().dict()


@router.put("/notification-preferences")
async def update_notification_preferences(body: NotificationPreferences, request: Request):
    """Update push notification preferences."""
    user = await _auth(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "Database not available")

    user_id = user.get("user_id", "")
    await db.push_preferences.update_one(
        {"user_id": user_id},
        {"$set": {**body.dict(), "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"success": True}
