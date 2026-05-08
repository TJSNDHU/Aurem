"""
Smart Onboarding Router — P1
=============================
Endpoints:
    POST /api/onboarding/detect   — {business_name, website_url, city} -> smart form data
    POST /api/onboarding/start     — {form_data} -> kicks off all subsystems
    GET  /api/onboarding/status   — current customer's onboarding state
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any

import jwt

from services.smart_onboarding_service import detect_everything, start_aurem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/smart-onboarding", tags=["Smart Onboarding"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(503, "DB not available")
    return _db


async def _auth(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        return jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


class DetectRequest(BaseModel):
    business_name: str
    website_url: Optional[str] = ""
    city: Optional[str] = ""


@router.post("/detect")
async def detect(body: DetectRequest, request: Request):
    """Run all auto-detection jobs in parallel, return smart-form-ready data."""
    await _auth(request)
    if not body.business_name.strip():
        raise HTTPException(400, "business_name required")
    result = await detect_everything(
        business_name=body.business_name.strip(),
        website_url=(body.website_url or "").strip(),
        city=(body.city or "").strip(),
    )
    return result


class StartRequest(BaseModel):
    business_name: str
    website_url: Optional[str] = ""
    platform: str = "custom"
    connection_method: str = "gtm"
    social_media: Optional[Dict[str, str]] = None
    google_places: Optional[Dict[str, Any]] = None


@router.post("/start")
async def start(body: StartRequest, request: Request):
    """Kick off all subsystems based on confirmed form data."""
    payload = await _auth(request)
    db = _get_db()
    email = (payload.get("email") or payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(401, "Invalid token")
    form_data = body.dict()
    result = await start_aurem(db, email, form_data)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Failed to start"))
    return result


@router.get("/me")
async def me(request: Request):
    """Return current onboarding state for the logged-in customer."""
    payload = await _auth(request)
    db = _get_db()
    email = (payload.get("email") or payload.get("sub") or "").lower()
    user = await db.platform_users.find_one({"email": email}, {"_id": 0}) \
        or await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")
    return {
        "email": email,
        "onboarded": bool(user.get("smart_onboarding_complete", False)),
        "onboarded_at": user.get("smart_onboarded_at", ""),
        "platform": user.get("onboarded_platform", ""),
        "business_name": user.get("company_name") or user.get("business_name", ""),
        "website": user.get("website", ""),
    }


@router.get("/health")
async def health():
    return {"status": "ok", "service": "smart-onboarding"}
