"""
Founding member system, milestone unlocks, data hub, email/SMS offers
Extracted from server.py during modularization.
"""

import os
try:
    import resend
except ImportError:
    resend = None
import random
import asyncio
import logging
import json
import hashlib
import secrets
import time
import uuid
import re
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Query, Body, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from utils.stubs import (
    MILESTONE_REFERRAL_THRESHOLD, MILESTONE_EMAIL_TRIGGER,
    MILESTONE_DISCOUNT_PERCENT, send_milestone_almost_there_email,
)
try:
    from models.server_models import (
        UserBase, UserCreate, UserLogin, CartItem, Cart, ComboCartRequest,
        ShippingCalculatorRequest, EmailOfferRequest, SMSOfferRequest,
        SUPPORTED_CURRENCIES, COUNTRY_TO_CURRENCY,
        POINTS_PER_REFERRAL, POINTS_TO_DOLLARS
    )
except ImportError:
    pass
try:
    from services.email_templates import (
        get_email_base_styles, generate_email_action_token, verify_email_action_token,
        generate_goal_achieved_email, generate_newsletter_confirmation_email
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')
try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
async def validate_whatsapp_number(*args, **kwargs): return True  # Stub
ws_manager = None  # WebSocket manager stub
async def process_payment_webhook_internally(*args, **kwargs): pass  # Stub
async def send_discord_notification(*args, **kwargs): pass  # Stub
def calculate_order_tax(*args, **kwargs): return 0  # Stub
async def unlock_milestone_discount(*args, **kwargs): return {}  # Stub
async def set_cached(*args, **kwargs): pass  # Cache stub
async def send_whatsapp_message(*args, **kwargs): pass  # Stub: WhatsApp not configured
twilio_client = None
try:
    from twilio.rest import Client as TwilioClient
    _sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
    _tok = os.environ.get('TWILIO_AUTH_TOKEN', '')
    if _sid and _tok:
        twilio_client = TwilioClient(_sid, _tok)
except ImportError:
    pass
try:
    from services.twilio_service import normalize_phone_number
except ImportError:
    def normalize_phone_number(phone, country_code='1'): return phone
try:
    from services.milestone_system import get_milestone_progress, verify_referral_for_milestone, generate_device_fingerprint
except ImportError:
    async def get_milestone_progress(referrer_code): return {}
    async def verify_referral_for_milestone(*args, **kwargs): return False
    async def generate_device_fingerprint(*args, **kwargs): return "unknown"


# Environment variables
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@aurem.live')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')


# Common imports from server.py scope
import bcrypt
import jwt
try:
    import stripe
except ImportError:
    stripe = None

try:
    from performance_patch import limiter
except ImportError:
    limiter = type('obj', (object,), {'limit': lambda self, *a, **kw: lambda f: f})()

from middleware.security import sanitize_input, validate_email

try:
    from middleware.websocket_manager import WebSocketConnectionManager
    manager = WebSocketConnectionManager()
except ImportError:
    manager = None

from config import JWT_SECRET
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
SITE_URL = os.environ.get("SITE_URL", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# MongoDB client reference (set at startup)
client = None

def set_client(c):
    global client
    client = c

# Helpers from server.py scope
ROOT_DIR = __import__("pathlib").Path(os.path.dirname(os.path.abspath(__file__)))

async def get_current_user(request: Request):
    """Extract user from JWT token in request."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        token = auth.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except Exception:
        return None

async def require_admin(request: Request):
    """Verify admin role from JWT."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ("admin", "founder", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def generate_jwt_token(user_data: dict, expires_hours: int = 24):
    """Generate JWT token."""
    import time as _time
    payload = {
        **user_data,
        "exp": int(_time.time()) + (expires_hours * 3600),
        "iat": int(_time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")



# Shared state — set by server.py at startup
db = None
api_router = None

def set_db(database):
    global db
    db = database

def set_router(router):
    global api_router
    api_router = router

def get_db():
    return db

router = APIRouter()

# ============ FOUNDING MEMBER SYSTEM ============


@router.post("/founding-member/join")
async def join_founding_member(data: dict):
    """Join the Founding Member program"""
    email = data.get("email", "").lower().strip()
    name = data.get("name", "").strip()
    referrer_code = data.get("referrer_code", "").upper().strip()
    from_scan = data.get(
        "from_scan", ""
    ).strip()  # Bio-scan referral code if coming from scan
    concern = data.get("concern", "")  # Primary concern from scan

    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    # Check if already a member
    existing = await db.founding_members.find_one({"email": email}, {"_id": 0})
    if existing:
        position = await db.founding_members.count_documents(
            {"created_at": {"$lte": existing.get("created_at")}}
        )
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Already a Founding Member",
                "already_member": True,
                "position": position,
                "referral_code": existing.get("referral_code"),
            },
        )

    # Generate unique referral code
    referral_code = f"FOUND-{str(uuid.uuid4())[:6].upper()}"

    # Calculate position
    position = await db.founding_members.count_documents({}) + 1

    # Create member record with attribution tracking
    member_record = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": name,
        "referral_code": referral_code,
        "referred_by": referrer_code if referrer_code else None,
        "from_scan": from_scan if from_scan else None,  # Track bio-scan attribution
        "concern": concern if concern else None,  # Track primary concern
        "position": position,
        "tier": "founding",
        "perks": [
            "beta_access",
            "grandfathered_pricing",
            "priority_access",
            "lab_feedback",
        ],
        "referral_count": 0,
        "source": (
            "bio_scan" if from_scan else ("referral" if referrer_code else "direct")
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.founding_members.insert_one(member_record)

    # Track referral if applicable
    if referrer_code:
        # Update referrer's count
        await db.founding_members.update_one(
            {"referral_code": referrer_code}, {"$inc": {"referral_count": 1}}
        )
        await db.waitlist.update_one(
            {"referral_code": referrer_code}, {"$inc": {"referral_count": 1}}
        )

        # Update partner earnings if referrer is a partner
        partner = await db.partners.find_one(
            {"referral_code": referrer_code}, {"_id": 0}
        )
        if partner:
            # Credit $7 commission (10% of $70) to partner
            commission = 7.00
            await db.partners.update_one(
                {"referral_code": referrer_code},
                {
                    "$inc": {
                        "sales": 1,
                        "earnings": commission,
                        "pending_earnings": commission,
                    },
                    "$push": {
                        "conversions": {
                            "id": str(uuid.uuid4()),
                            "type": "founding_member",
                            "amount": 70.00,
                            "commission": commission,
                            "email": email[:3] + "***",  # Privacy
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                },
            )
            logger.info(
                f"Partner {partner.get('email')} earned ${commission} from founding member sale"
            )

    # Send welcome email asynchronously
    try:
        await send_founding_member_welcome_email(email, name, referral_code, position)
    except Exception as e:
        logger.error(f"Failed to send founding member welcome email: {e}")

    logger.info(f"New Founding Member: {email} (#{position})")

    return {
        "success": True,
        "position": position,
        "referral_code": referral_code,
        "message": "Welcome to the Founding Circle!",
    }


async def send_founding_member_welcome_email(
    email: str, name: str, referral_code: str, position: int
):
    """Send welcome email to new Founding Member"""
    if not RESEND_API_KEY:
        return

    share_url = f"https://reroots.ca/founding-member?ref={referral_code}"
    first_name = name.split()[0] if name else "Friend"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #0a0a0a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 40px;">
                <img src="https://reroots.ca/reroots-logo-light.png" alt="ReRoots" style="height: 40px; margin-bottom: 20px;">
            </div>
            
            <!-- Welcome Banner -->
            <div style="background: linear-gradient(135deg, rgba(212, 175, 55, 0.15) 0%, rgba(212, 175, 55, 0.05) 100%); border: 1px solid rgba(212, 175, 55, 0.3); border-radius: 16px; padding: 30px; text-align: center; margin-bottom: 30px;">
                <p style="color: #D4AF37; font-size: 12px; text-transform: uppercase; letter-spacing: 3px; margin: 0 0 10px 0;">
                    Welcome to the Lab
                </p>
                <h1 style="color: white; font-size: 28px; margin: 0 0 10px 0; font-family: Georgia, serif;">
                    You're Founding Member #{position}
                </h1>
                <p style="color: rgba(255,255,255,0.6); font-size: 14px; margin: 0;">
                    Welcome to the inner circle of ReRoots Aesthetics Inc.
                </p>
            </div>
            
            <!-- Message -->
            <div style="background: rgba(255,255,255,0.05); border-radius: 16px; padding: 30px; margin-bottom: 30px;">
                <p style="color: white; font-size: 16px; margin: 0 0 20px 0;">
                    Hi {first_name},
                </p>
                <p style="color: rgba(255,255,255,0.7); font-size: 14px; line-height: 1.7; margin: 0 0 20px 0;">
                    You weren't just selected for your interest in skincare—you're joining because you understand the difference between <strong style="color: white;">cosmetic marketing</strong> and <strong style="color: #D4AF37;">biotech science</strong>.
                </p>
                <p style="color: rgba(255,255,255,0.7); font-size: 14px; line-height: 1.7; margin: 0;">
                    As a Founding Member, you now have access to:
                </p>
            </div>
            
            <!-- Perks List -->
            <div style="margin-bottom: 30px;">
                <div style="background: rgba(255,255,255,0.03); border-left: 3px solid #D4AF37; padding: 15px 20px; margin-bottom: 10px; border-radius: 0 8px 8px 0;">
                    <p style="color: #D4AF37; font-size: 12px; font-weight: bold; margin: 0 0 5px 0;">LIFETIME BETA ACCESS</p>
                    <p style="color: rgba(255,255,255,0.6); font-size: 13px; margin: 0;">Test new formulations before anyone else</p>
                </div>
                <div style="background: rgba(255,255,255,0.03); border-left: 3px solid #D4AF37; padding: 15px 20px; margin-bottom: 10px; border-radius: 0 8px 8px 0;">
                    <p style="color: #D4AF37; font-size: 12px; font-weight: bold; margin: 0 0 5px 0;">GRANDFATHERED PRICING</p>
                    <p style="color: rgba(255,255,255,0.6); font-size: 13px; margin: 0;">Your price is locked forever—immune to inflation</p>
                </div>
                <div style="background: rgba(255,255,255,0.03); border-left: 3px solid #D4AF37; padding: 15px 20px; margin-bottom: 10px; border-radius: 0 8px 8px 0;">
                    <p style="color: #D4AF37; font-size: 12px; font-weight: bold; margin: 0 0 5px 0;">DIRECT-TO-LAB FEEDBACK</p>
                    <p style="color: rgba(255,255,255,0.6); font-size: 13px; margin: 0;">Vote on our next product focus each month</p>
                </div>
            </div>
            
            <!-- Referral Section -->
            <div style="background: linear-gradient(135deg, rgba(248, 165, 184, 0.1) 0%, rgba(248, 165, 184, 0.05) 100%); border: 1px solid rgba(248, 165, 184, 0.2); border-radius: 16px; padding: 25px; text-align: center; margin-bottom: 30px;">
                <p style="color: #F8A5B8; font-size: 14px; font-weight: bold; margin: 0 0 10px 0;">
                    🎁 Your Referral Reward
                </p>
                <p style="color: rgba(255,255,255,0.7); font-size: 13px; margin: 0 0 15px 0;">
                    Invite 3 friends to the Founding Circle and get a <strong style="color: white;">FREE Aura-Gen bottle</strong>.
                </p>
                <div style="background: rgba(0,0,0,0.3); border-radius: 8px; padding: 12px; margin-bottom: 15px;">
                    <p style="color: rgba(255,255,255,0.5); font-size: 11px; margin: 0 0 5px 0;">YOUR REFERRAL LINK</p>
                    <p style="color: #D4AF37; font-size: 14px; font-weight: bold; margin: 0; word-break: break-all;">
                        {share_url}
                    </p>
                </div>
            </div>
            
            <!-- CTA -->
            <div style="text-align: center; margin-bottom: 30px;">
                <a href="https://reroots.ca/Bio-Age-Repair-Scan" style="display: inline-block; background: linear-gradient(135deg, #D4AF37 0%, #B8960F 100%); color: #0a0a0a; text-decoration: none; padding: 16px 40px; border-radius: 50px; font-weight: bold; font-size: 14px;">
                    Take Your Bio-Age Scan
                </a>
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 30px;">
                <p style="color: rgba(255,255,255,0.5); font-size: 12px; margin: 0;">
                    Stay Radiant,<br>
                    <strong style="color: white;">The ReRoots Team</strong>
                </p>
                <p style="color: rgba(255,255,255,0.3); font-size: 11px; margin-top: 20px;">
                    ReRoots Aesthetics Inc. | Canadian Biotech Skincare
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        params = {
            "from": SENDER_EMAIL,
            "to": email,
            "subject": "Welcome to the Lab: Your ReRoots Founding Member Portal 🧬",
            "html": html_content,
        }
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Founding member welcome email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send founding member email: {e}")


@router.get("/founding-member/stats")
async def get_founding_member_stats():
    """Get Founding Member program statistics"""
    total = await db.founding_members.count_documents({})
    this_week = await db.founding_members.count_documents(
        {
            "created_at": {
                "$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            }
        }
    )

    return {"total_members": total, "this_week": this_week}


# ============ MILESTONE UNLOCK SYSTEM API ENDPOINTS ============


@router.get("/milestone/progress/{referral_code}")
async def get_user_milestone_progress(referral_code: str):
    """Get milestone progress for a user's referral code"""
    code = referral_code.upper()
    progress = await get_milestone_progress(code)
    return progress


@router.post("/milestone/verify-referral")
async def api_verify_referral(request: Request, data: dict):
    """
    Verify a referral for milestone progress.
    Called when a referred user completes their Bio-Age Scan.
    """
    referrer_code = data.get("referrer_code", "").upper()
    referred_email = data.get("referred_email", "").lower().strip()
    device_fingerprint = data.get("device_fingerprint", "")

    if not referrer_code or not referred_email:
        raise HTTPException(
            status_code=400, detail="Missing referrer_code or referred_email"
        )

    # Get client IP
    ip_address = request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip_address = forwarded.split(",")[0].strip()

    # Generate server-side fingerprint component
    server_fingerprint = await generate_device_fingerprint(request, device_fingerprint)

    result = await verify_referral_for_milestone(
        referrer_code,
        referred_email,
        ip_address,
        server_fingerprint,
    )

    return result


@router.post("/milestone/check-pending")
async def check_pending_referrals(data: dict):
    """
    Check and verify any pending referrals for a user.
    Called periodically or when user logs in.
    """
    referral_code = data.get("referral_code", "").upper()

    if not referral_code:
        raise HTTPException(status_code=400, detail="Missing referral_code")

    # Find all bio-scan completions that were referred by this code but not yet verified
    pending = await db.bio_scans.find(
        {
            "referred_by": referral_code,
        },
        {"_id": 0, "email": 1, "id": 1},
    ).to_list(100)

    verified_count = 0
    for scan in pending:
        # Check if already verified
        existing = await db.verified_referrals.find_one(
            {
                "referrer_code": referral_code,
                "referred_email": scan.get("email", "").lower(),
            }
        )
        if not existing and scan.get("email"):
            # Auto-verify (without fraud check since this is backend reconciliation)
            verified_referral = {
                "id": str(uuid.uuid4()),
                "referrer_code": referral_code,
                "referred_email": scan["email"].lower(),
                "bio_scan_id": scan.get("id"),
                "ip_address": "auto-verified",
                "device_fingerprint": "auto-verified",
                "fraud_risk_score": 0,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "auto_verified": True,
            }
            await db.verified_referrals.insert_one(verified_referral)
            verified_count += 1

    # Update counts
    if verified_count > 0:
        await db.founding_members.update_one(
            {"referral_code": referral_code},
            {"$inc": {"verified_referral_count": verified_count}},
        )

    progress = await get_milestone_progress(referral_code)

    # Check if milestone reached
    if progress["count"] >= MILESTONE_REFERRAL_THRESHOLD and not progress["unlocked"]:
        await unlock_milestone_discount(referral_code)
        progress = await get_milestone_progress(referral_code)

    # Check if at 8/10 trigger point
    elif progress["count"] == MILESTONE_EMAIL_TRIGGER:
        await send_milestone_almost_there_email(referral_code, progress["count"])

    return {
        "newly_verified": verified_count,
        "milestone_progress": progress,
    }


@router.post("/milestone/validate-unlock-code")
async def validate_unlock_code(data: dict):
    """Validate an unlock code for discount application"""
    code = data.get("code", "").upper().strip()

    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    # Check if this is a valid unlock code
    member = await db.founding_members.find_one(
        {"unlock_code": code, "milestone_unlocked": True},
        {"_id": 0, "email": 1, "name": 1, "permanent_discount_percent": 1},
    )
    if not member:
        member = await db.waitlist.find_one(
            {"unlock_code": code, "milestone_unlocked": True},
            {"_id": 0, "email": 1, "name": 1, "permanent_discount_percent": 1},
        )

    if member:
        return {
            "valid": True,
            "discount_percent": member.get(
                "permanent_discount_percent", MILESTONE_DISCOUNT_PERCENT
            ),
            "owner_name": (
                member.get("name", "").split()[0] if member.get("name") else None
            ),
        }

    return {"valid": False, "message": "Invalid or expired code"}


# ============ DATA HUB ADMIN ENDPOINTS ============


@router.get("/admin/founding-members")
async def get_all_founding_members(request: Request):
    """Get all founding members for admin Data Hub"""
    await require_admin(request)
    members = (
        await db.founding_members.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(10000)
    )
    return {"members": members, "total": len(members)}


@router.get("/admin/quiz-submissions")
async def get_all_quiz_submissions(request: Request):
    """Get all quiz submissions for admin Data Hub"""
    await require_admin(request)
    # Check multiple possible collection names
    submissions = []

    # Try quiz_submissions collection
    quiz_data = (
        await db.quiz_submissions.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(10000)
    )
    submissions.extend(quiz_data)

    # Also check users with quiz data (legacy)
    quiz_users = await db.users.find(
        {"quiz_completed": True},
        {
            "_id": 0,
            "email": 1,
            "primary_concern": 1,
            "recommended_product": 1,
            "age_group": 1,
            "quiz_completed_at": 1,
        },
    ).to_list(10000)

    for u in quiz_users:
        if u.get("email") and u.get("email") not in [
            s.get("email") for s in submissions
        ]:
            submissions.append(
                {
                    "email": u.get("email"),
                    "primary_concern": u.get("primary_concern"),
                    "recommended_product": u.get("recommended_product"),
                    "age_group": u.get("age_group"),
                    "created_at": u.get("quiz_completed_at"),
                }
            )

    return {"submissions": submissions, "total": len(submissions)}


@router.get("/admin/bio-age-scans")
async def get_all_bio_age_scans(request: Request):
    """Get all bio-age scan submissions for admin Data Hub"""
    await require_admin(request)
    # Check bio_scan_submissions collection
    scans = (
        await db.bio_scan_submissions.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(10000)
    )

    # Also check bio_age_scans collection
    alt_scans = (
        await db.bio_age_scans.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(10000)
    )

    # Merge, avoiding duplicates by email
    seen_emails = set()
    all_scans = []
    for scan in scans + alt_scans:
        email = scan.get("email")
        if email and email not in seen_emails:
            seen_emails.add(email)
            all_scans.append(scan)

    return {"scans": all_scans, "total": len(all_scans)}


@router.get("/admin/subscribers")
async def get_all_subscribers_datahub(request: Request):
    """Get all newsletter subscribers for admin Data Hub"""
    await require_admin(request)
    subscribers = (
        await db.newsletter_subscribers.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(10000)
    )
    return {"subscribers": subscribers, "total": len(subscribers)}


@router.get("/crm/subscribers")
async def get_crm_subscribers(request: Request):
    """
    CRM Subscriber List - Returns all users with their opt-in status.
    Alias endpoint for the AdminPanel's Subscribers section.
    """
    await require_admin(request)
    users = await db.users.find().sort("created_at", -1).to_list(1000)
    result = []
    
    for u in users:
        name = u.get("name") or f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
        result.append({
            "id": str(u.get("_id", u.get("id", ""))),
            "name": name,
            "email": u.get("email", ""),
            "skin_type": u.get("skin_type", ""),
            "birthday": str(u.get("birthday", "")) if u.get("birthday") else "",
            "tier": u.get("tier", "Silver"),
            "loyalty_points": u.get("loyalty_points", 0),
            "offers_opt_in": u.get("offers_opt_in", True),
            "created_at": str(u.get("created_at", "")) if u.get("created_at") else "",
        })
    
    return result


@router.patch("/crm/subscribers/{user_id}")
async def update_crm_subscriber(user_id: str, request: Request):
    """Toggle a subscriber's offer opt-in status"""
    await require_admin(request)
    
    body = await request.json()
    offers_opt_in = body.get("offers_opt_in")
    
    update_data = {"updated_at": datetime.now(timezone.utc)}
    if offers_opt_in is not None:
        update_data["offers_opt_in"] = offers_opt_in

    try:
        from bson import ObjectId
        result = await db.users.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=True
        )
    except:
        result = await db.users.find_one_and_update(
            {"id": user_id},
            {"$set": update_data},
            return_document=True
        )

    if not result:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    name = result.get("name") or f"{result.get('first_name', '')} {result.get('last_name', '')}".strip()

    return {
        "id": str(result.get("_id", result.get("id", ""))),
        "name": name,
        "email": result.get("email", ""),
        "skin_type": result.get("skin_type", ""),
        "birthday": str(result.get("birthday", "")) if result.get("birthday") else "",
        "tier": result.get("tier", "Silver"),
        "offers_opt_in": result.get("offers_opt_in", True),
        "created_at": str(result.get("created_at", "")) if result.get("created_at") else "",
    }


# ============= EMAIL OFFERS FEATURE =============

@router.get("/admin/email-offers/recipients")
async def get_email_offer_recipients(request: Request):
    """
    Get aggregated list of all emails from various programs for Email Offers feature.
    Each email includes its source program for color-coding.
    """
    await require_admin(request)
    
    seen_emails = {}  # email -> {source, name, created_at}
    
    # 1. Newsletter Subscribers (source: "newsletter")
    newsletter_subs = await db.newsletter_subscribers.find({}, {"_id": 0}).to_list(10000)
    for sub in newsletter_subs:
        email = sub.get("email", "").lower().strip()
        if email and email not in seen_emails:
            seen_emails[email] = {
                "email": email,
                "name": sub.get("name", ""),
                "source": "newsletter",
                "source_label": "Newsletter",
                "created_at": sub.get("created_at", sub.get("subscribed_at", ""))
            }
    
    # 2. Bio-Age Scans (source: "bio_scan")
    bio_scans = await db.bio_scans.find({}, {"_id": 0}).to_list(10000)
    bio_scan_subs = await db.bio_scan_submissions.find({}, {"_id": 0}).to_list(10000)
    bio_age_scans = await db.bio_age_scans.find({}, {"_id": 0}).to_list(10000)
    for scan in bio_scans + bio_scan_subs + bio_age_scans:
        email = scan.get("email", "").lower().strip()
        if email and email not in seen_emails:
            seen_emails[email] = {
                "email": email,
                "name": scan.get("name", scan.get("full_name", "")),
                "source": "bio_scan",
                "source_label": "Bio-Age Scan",
                "created_at": scan.get("created_at", scan.get("submitted_at", ""))
            }
    
    # 3. Waitlist / Founding Members (source: "waitlist")
    waitlist = await db.waitlist.find({}, {"_id": 0}).to_list(10000)
    founding_members = await db.founding_members.find({}, {"_id": 0}).to_list(10000)
    for member in waitlist + founding_members:
        email = member.get("email", "").lower().strip()
        if email and email not in seen_emails:
            seen_emails[email] = {
                "email": email,
                "name": member.get("name", member.get("full_name", "")),
                "source": "waitlist",
                "source_label": "Waitlist",
                "created_at": member.get("created_at", member.get("joined_at", ""))
            }
    
    # 4. Partners / Influencers (source: "partner")
    partners = await db.influencer_applications.find({"status": "approved"}, {"_id": 0}).to_list(10000)
    for partner in partners:
        email = partner.get("email", "").lower().strip()
        if email and email not in seen_emails:
            seen_emails[email] = {
                "email": email,
                "name": partner.get("full_name", partner.get("name", "")),
                "source": "partner",
                "source_label": "Partner",
                "created_at": partner.get("created_at", partner.get("approved_at", ""))
            }
    
    # 5. Customers (from orders) (source: "customer")
    orders = await db.orders.find({}, {"_id": 0, "email": 1, "customer_email": 1, "customer": 1, "created_at": 1}).to_list(10000)
    for order in orders:
        email = (order.get("email") or order.get("customer_email") or order.get("customer", {}).get("email", "")).lower().strip()
        if email and email not in seen_emails:
            customer_name = order.get("customer", {}).get("name", order.get("customer", {}).get("firstName", ""))
            seen_emails[email] = {
                "email": email,
                "name": customer_name,
                "source": "customer",
                "source_label": "Customer",
                "created_at": order.get("created_at", "")
            }
    
    # Convert to list and sort by source then email
    recipients = list(seen_emails.values())
    
    # Add unique ID to each recipient
    for i, recipient in enumerate(recipients):
        recipient["id"] = f"recipient_{i}_{recipient['email'].replace('@', '_').replace('.', '_')}"
    
    # Sort by source priority (newsletter first, then bio_scan, waitlist, partner, customer)
    source_priority = {"newsletter": 0, "bio_scan": 1, "waitlist": 2, "partner": 3, "customer": 4}
    recipients.sort(key=lambda x: (source_priority.get(x["source"], 99), x["email"]))
    
    # Get counts per source
    source_counts = {}
    for r in recipients:
        src = r["source_label"]
        source_counts[src] = source_counts.get(src, 0) + 1
    
    return {
        "recipients": recipients,
        "total": len(recipients),
        "source_counts": source_counts
    }


class EmailOfferRequest(BaseModel):
    subject: str
    title: str
    message: str
    discount_code: Optional[str] = None
    discount_percent: Optional[int] = None
    recipient_emails: List[str] = []
    recipient_phones: Optional[List[str]] = []  # For SMS offers
    brand_prefix: Optional[str] = None  # Optional prefix for discount code


@router.post("/admin/email-offers/send")
async def send_email_offers(request: Request, offer_data: EmailOfferRequest):
    """
    Send promotional email offers to selected recipients.
    Also supports sending SMS to phone numbers.
    Optionally generates a discount code with brand prefix.
    """
    await require_admin(request)
    
    if not RESEND_API_KEY:
        raise HTTPException(status_code=400, detail="Email service not configured (missing RESEND_API_KEY)")
    
    if not offer_data.recipient_emails and not offer_data.recipient_phones:
        raise HTTPException(status_code=400, detail="No recipients selected")
    
    # Get store settings for branding
    store_settings = await db.store_settings.find_one({}, {"_id": 0}) or {}
    store_name = store_settings.get("store_name", "ReRoots")
    support_email = store_settings.get("support_email", "support@reroots.ca")
    
    # Generate discount code if discount percent is provided but no code given
    discount_code = offer_data.discount_code
    if offer_data.discount_percent and not discount_code:
        # Generate code with optional brand prefix
        prefix = offer_data.brand_prefix.upper() if offer_data.brand_prefix else store_name.upper().replace(" ", "")
        random_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=5))
        discount_code = f"{prefix}{offer_data.discount_percent}{random_suffix}"
    
    # Create the discount code in database if one was generated/provided
    if discount_code and offer_data.discount_percent:
        existing_code = await db.offers.find_one({"code": discount_code})
        if not existing_code:
            await db.offers.insert_one({
                "id": str(uuid.uuid4()),
                "code": discount_code,
                "discount_percent": offer_data.discount_percent,
                "discount_value": offer_data.discount_percent,
                "min_order_amount": 0,
                "max_uses": None,
                "uses_count": 0,
                "is_active": True,
                "is_email_offer": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "offer_title": offer_data.title,
                "offer_subject": offer_data.subject
            })
            # Also add to coupons collection for checkout compatibility
            await db.coupons.insert_one({
                "id": str(uuid.uuid4()),
                "code": discount_code,
                "discount_percent": offer_data.discount_percent,
                "discount_value": offer_data.discount_percent,
                "min_order_amount": 0,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    # Generate the email HTML
    discount_section = ""
    if discount_code and offer_data.discount_percent:
        discount_section = f"""
        <div style="background: linear-gradient(135deg, #F8A5B8 0%, #E88FA0 100%); padding: 25px; border-radius: 12px; text-align: center; margin: 25px 0;">
            <p style="margin: 0 0 10px 0; font-size: 14px; color: white; text-transform: uppercase; letter-spacing: 2px;">Your Exclusive Code</p>
            <p style="margin: 0; font-size: 32px; font-weight: bold; color: white; letter-spacing: 4px; font-family: monospace;">{discount_code}</p>
            <p style="margin: 15px 0 0 0; font-size: 18px; color: white;">{offer_data.discount_percent}% OFF Your Order</p>
        </div>
        """
    
    email_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{offer_data.title}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f5f5f5;">
            <tr>
                <td style="padding: 40px 20px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3D3A3E 100%); padding: 35px 30px; text-align: center;">
                                <h1 style="margin: 0; font-size: 28px; font-weight: bold; color: #F8A5B8;">{store_name}</h1>
                                <p style="margin: 10px 0 0 0; color: rgba(255, 255, 255, 0.8); font-size: 14px;">Special Offer Just For You</p>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <h2 style="margin: 0 0 20px 0; font-size: 24px; color: #2D2A2E; font-weight: 600;">{offer_data.title}</h2>
                                <p style="margin: 0 0 25px 0; font-size: 16px; color: #5A5A5A; line-height: 1.6;">
                                    {offer_data.message}
                                </p>
                                
                                {discount_section}
                                
                                <div style="text-align: center; margin-top: 30px;">
                                    <a href="{store_settings.get('shop_url', 'https://reroots.ca')}/shop" 
                                       style="display: inline-block; background: linear-gradient(135deg, #2D2A2E 0%, #3D3A3E 100%); color: white; padding: 16px 40px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                                        Shop Now
                                    </a>
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f9f9f9; padding: 25px 30px; text-align: center; border-top: 1px solid #eee;">
                                <p style="margin: 0 0 10px 0; font-size: 14px; color: #888;">
                                    Questions? Contact us at <a href="mailto:{support_email}" style="color: #F8A5B8; text-decoration: none;">{support_email}</a>
                                </p>
                                <p style="margin: 0; font-size: 12px; color: #888;">
                                    © 2025 {store_name}. All rights reserved.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    # Send emails
    sent_count = 0
    failed_emails = []
    
    for email in offer_data.recipient_emails:
        try:
            params = {
                "from": f"{store_name} <{SENDER_EMAIL}>",
                "to": [email],
                "subject": offer_data.subject,
                "html": email_html
            }
            await asyncio.to_thread(resend.Emails.send, params)
            sent_count += 1
        except Exception as e:
            logging.error(f"Failed to send email offer to {email}: {e}")
            failed_emails.append(email)
    
    # Send SMS to phone numbers if any
    sms_sent_count = 0
    failed_phones = []
    
    if offer_data.recipient_phones:
        # Prepare SMS message
        sms_message = f"🎉 {offer_data.title}\n\n{offer_data.message}"
        if discount_code and offer_data.discount_percent:
            sms_message += f"\n\n🏷️ Use code: {discount_code} for {offer_data.discount_percent}% off!"
        sms_message += f"\n\n🛒 Shop now: {store_settings.get('shop_url', 'https://reroots.ca')}/shop"
        
        for phone in offer_data.recipient_phones:
            try:
                # Format phone number (ensure it has country code)
                formatted_phone = phone.strip()
                if not formatted_phone.startswith('+'):
                    formatted_phone = '+1' + formatted_phone  # Default to US/Canada
                
                # Try sending via WhatsApp first (WHAPI)
                try:
                    await send_whatsapp_message(formatted_phone, sms_message)
                    sms_sent_count += 1
                except Exception as whapi_error:
                    # Fallback to Twilio SMS if WhatsApp fails
                    logging.warning(f"WhatsApp failed for {phone}, trying Twilio SMS: {whapi_error}")
                    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
                        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                        twilio_client.messages.create(
                            body=sms_message,
                            from_=os.environ.get("TWILIO_PHONE_NUMBER", "+15005550006"),
                            to=formatted_phone
                        )
                        sms_sent_count += 1
                    else:
                        raise Exception("Twilio not configured")
            except Exception as e:
                logging.error(f"Failed to send SMS offer to {phone}: {e}")
                failed_phones.append(phone)
    
    # Log the email offer campaign
    total_sent = sent_count + sms_sent_count
    total_recipients = len(offer_data.recipient_emails) + len(offer_data.recipient_phones or [])
    
    campaign_record = {
        "id": str(uuid.uuid4()),
        "subject": offer_data.subject,
        "title": offer_data.title,
        "message": offer_data.message,
        "discount_code": discount_code,
        "discount_percent": offer_data.discount_percent,
        "total_recipients": total_recipients,
        "sent_count": total_sent,
        "email_sent": sent_count,
        "sms_sent": sms_sent_count,
        "failed_count": len(failed_emails) + len(failed_phones),
        "failed_emails": failed_emails,
        "failed_phones": failed_phones,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.email_offer_campaigns.insert_one(campaign_record)
    
    return {
        "success": True,
        "message": f"Offers sent to {total_sent} recipients ({sent_count} emails, {sms_sent_count} SMS)",
        "sent_count": total_sent,
        "email_sent": sent_count,
        "sms_sent": sms_sent_count,
        "failed_count": len(failed_emails) + len(failed_phones),
        "discount_code": discount_code,
        "campaign_id": campaign_record["id"]
    }


@router.get("/admin/email-offers/campaigns")
async def get_email_offer_campaigns(request: Request):
    """Get history of email offer campaigns"""
    await require_admin(request)
    
    campaigns = await db.email_offer_campaigns.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"campaigns": campaigns, "total": len(campaigns)}


# ============= SMS OFFERS FEATURE (WHAPI) =============

@router.get("/admin/sms-offers/recipients")
async def get_sms_offer_recipients(request: Request):
    """
    Get aggregated list of all phone numbers from various programs for SMS/WhatsApp Offers.
    Each phone includes its source program for color-coding.
    """
    await require_admin(request)
    
    seen_phones = {}  # normalized_phone -> {source, name, created_at}
    
    # 1. Bio-Age Scans (source: "bio_scan")
    bio_scans = await db.bio_scans.find({}, {"_id": 0}).to_list(10000)
    bio_scan_subs = await db.bio_scan_submissions.find({}, {"_id": 0}).to_list(10000)
    bio_age_scans = await db.bio_age_scans.find({}, {"_id": 0}).to_list(10000)
    for scan in bio_scans + bio_scan_subs + bio_age_scans:
        phone = scan.get("phone") or scan.get("whatsapp") or scan.get("whatsapp_number")
        if phone:
            normalized = normalize_phone_number(phone)
            if normalized and normalized not in seen_phones:
                seen_phones[normalized] = {
                    "phone": normalized,
                    "display_phone": f"+{normalized}" if not normalized.startswith('+') else normalized,
                    "name": scan.get("name", scan.get("full_name", "")),
                    "email": scan.get("email", ""),
                    "source": "bio_scan",
                    "source_label": "Bio-Age Scan",
                    "created_at": scan.get("created_at", scan.get("submitted_at", "")),
                    "whatsapp_verified": scan.get("whatsapp_verified", False)
                }
    
    # 2. Waitlist / Founding Members (source: "waitlist")
    waitlist = await db.waitlist.find({}, {"_id": 0}).to_list(10000)
    founding_members = await db.founding_members.find({}, {"_id": 0}).to_list(10000)
    for member in waitlist + founding_members:
        phone = member.get("phone") or member.get("whatsapp") or member.get("phone_number")
        if phone:
            normalized = normalize_phone_number(phone)
            if normalized and normalized not in seen_phones:
                seen_phones[normalized] = {
                    "phone": normalized,
                    "display_phone": f"+{normalized}" if not normalized.startswith('+') else normalized,
                    "name": member.get("name", member.get("full_name", "")),
                    "email": member.get("email", ""),
                    "source": "waitlist",
                    "source_label": "Waitlist",
                    "created_at": member.get("created_at", member.get("joined_at", "")),
                    "whatsapp_verified": member.get("whatsapp_verified", False)
                }
    
    # 3. Partners / Influencers (source: "partner")
    partners = await db.influencer_applications.find({"status": "approved"}, {"_id": 0}).to_list(10000)
    for partner in partners:
        phone = partner.get("phone") or partner.get("whatsapp")
        if phone:
            normalized = normalize_phone_number(phone)
            if normalized and normalized not in seen_phones:
                seen_phones[normalized] = {
                    "phone": normalized,
                    "display_phone": f"+{normalized}" if not normalized.startswith('+') else normalized,
                    "name": partner.get("full_name", partner.get("name", "")),
                    "email": partner.get("email", ""),
                    "source": "partner",
                    "source_label": "Partner",
                    "created_at": partner.get("created_at", partner.get("approved_at", "")),
                    "whatsapp_verified": partner.get("whatsapp_verified", False)
                }
    
    # 4. Customers (from orders) (source: "customer")
    orders = await db.orders.find({}, {"_id": 0, "phone": 1, "customer": 1, "shipping_address": 1, "created_at": 1}).to_list(10000)
    for order in orders:
        phone = order.get("phone") or order.get("customer", {}).get("phone") or order.get("shipping_address", {}).get("phone")
        if phone:
            normalized = normalize_phone_number(phone)
            if normalized and normalized not in seen_phones:
                customer_name = order.get("customer", {}).get("name", order.get("customer", {}).get("firstName", ""))
                seen_phones[normalized] = {
                    "phone": normalized,
                    "display_phone": f"+{normalized}" if not normalized.startswith('+') else normalized,
                    "name": customer_name,
                    "email": order.get("customer", {}).get("email", ""),
                    "source": "customer",
                    "source_label": "Customer",
                    "created_at": order.get("created_at", ""),
                    "whatsapp_verified": False
                }
    
    # 5. Newsletter subscribers with phone (source: "newsletter")
    newsletter_subs = await db.newsletter_subscribers.find({}, {"_id": 0}).to_list(10000)
    for sub in newsletter_subs:
        phone = sub.get("phone") or sub.get("phone_number")
        if phone:
            normalized = normalize_phone_number(phone)
            if normalized and normalized not in seen_phones:
                seen_phones[normalized] = {
                    "phone": normalized,
                    "display_phone": f"+{normalized}" if not normalized.startswith('+') else normalized,
                    "name": sub.get("name", ""),
                    "email": sub.get("email", ""),
                    "source": "newsletter",
                    "source_label": "Newsletter",
                    "created_at": sub.get("created_at", sub.get("subscribed_at", "")),
                    "whatsapp_verified": False
                }
    
    # Convert to list and sort by source then phone
    recipients = list(seen_phones.values())
    
    # Add unique ID to each recipient
    for i, recipient in enumerate(recipients):
        recipient["id"] = f"sms_recipient_{i}_{recipient['phone'][-4:]}"
    
    # Sort by source priority
    source_priority = {"bio_scan": 0, "waitlist": 1, "partner": 2, "customer": 3, "newsletter": 4}
    recipients.sort(key=lambda x: (source_priority.get(x["source"], 99), x["phone"]))
    
    # Get counts per source
    source_counts = {}
    for r in recipients:
        src = r["source_label"]
        source_counts[src] = source_counts.get(src, 0) + 1
    
    # Count verified WhatsApp numbers
    verified_count = sum(1 for r in recipients if r.get("whatsapp_verified"))
    
    return {
        "recipients": recipients,
        "total": len(recipients),
        "verified_count": verified_count,
        "source_counts": source_counts
    }


class SMSOfferRequest(BaseModel):
    message: str
    discount_code: Optional[str] = None
    discount_percent: Optional[int] = None
    recipient_phones: List[str]
    brand_prefix: Optional[str] = None
    message_type: str = "whatsapp"  # "whatsapp" or "sms"


@router.post("/admin/sms-offers/send")
async def send_sms_offers(request: Request, offer_data: SMSOfferRequest):
    """
    Send promotional SMS/WhatsApp offers to selected recipients.
    - WhatsApp messages are sent via WHAPI
    - SMS messages are sent via Twilio
    Optionally generates a discount code with brand prefix.
    """
    await require_admin(request)
    
    if not offer_data.recipient_phones:
        raise HTTPException(status_code=400, detail="No recipients selected")
    
    # Check which service is configured based on message type
    if offer_data.message_type == "whatsapp":
        whapi_token = os.environ.get("WHAPI_API_TOKEN")
        if not whapi_token:
            raise HTTPException(status_code=400, detail="WHAPI not configured (missing WHAPI_API_TOKEN)")
    else:  # sms
        if not twilio_client:
            raise HTTPException(status_code=400, detail="Twilio not configured (missing TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN)")
    
    # Get store settings for branding
    store_settings = await db.store_settings.find_one({}, {"_id": 0}) or {}
    store_name = store_settings.get("store_name", "ReRoots")
    
    # Generate discount code if discount percent is provided but no code given
    discount_code = offer_data.discount_code
    if offer_data.discount_percent and not discount_code:
        prefix = offer_data.brand_prefix.upper() if offer_data.brand_prefix else store_name.upper().replace(" ", "")
        random_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=5))
        discount_code = f"{prefix}{offer_data.discount_percent}{random_suffix}"
    
    # Create the discount code in database if one was generated/provided
    if discount_code and offer_data.discount_percent:
        existing_code = await db.offers.find_one({"code": discount_code})
        if not existing_code:
            await db.offers.insert_one({
                "id": str(uuid.uuid4()),
                "code": discount_code,
                "discount_percent": offer_data.discount_percent,
                "discount_value": offer_data.discount_percent,
                "min_order_amount": 0,
                "max_uses": None,
                "uses_count": 0,
                "is_active": True,
                "is_sms_offer": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "offer_message": offer_data.message
            })
            # Also add to coupons collection for checkout compatibility
            await db.coupons.insert_one({
                "id": str(uuid.uuid4()),
                "code": discount_code,
                "discount_percent": offer_data.discount_percent,
                "discount_value": offer_data.discount_percent,
                "min_order_amount": 0,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    # Build the message with discount code if present
    message_text = offer_data.message
    if discount_code and offer_data.discount_percent:
        if offer_data.message_type == "whatsapp":
            message_text += f"\n\n🎁 Your exclusive code: *{discount_code}* ({offer_data.discount_percent}% OFF)\n\nShop: https://reroots.ca/shop"
        else:
            # SMS - shorter format, no markdown
            message_text += f"\n\nCode: {discount_code} ({offer_data.discount_percent}% OFF) Shop: reroots.ca/shop"
    
    # Send messages based on type
    sent_count = 0
    failed_phones = []
    
    for phone in offer_data.recipient_phones:
        normalized = normalize_phone_number(phone)
        if not normalized:
            failed_phones.append({"phone": phone, "error": "Invalid phone format"})
            continue
        
        if offer_data.message_type == "whatsapp":
            # Send via WHAPI
            result = await send_whatsapp_message(normalized, message_text)
            if result.get("success"):
                sent_count += 1
            else:
                failed_phones.append({"phone": phone, "error": result.get("error", "Send failed")})
        else:
            # Send via Twilio SMS
            try:
                # Format phone for Twilio (+1XXXXXXXXXX)
                to_phone = f"+{normalized}" if not normalized.startswith("+") else normalized
                
                # Use Twilio Messaging API
                message = twilio_client.messages.create(
                    body=message_text,
                    from_=os.environ.get("TWILIO_PHONE_NUMBER", "+12076193027"),  # Your Twilio number
                    to=to_phone
                )
                
                if message.sid:
                    sent_count += 1
                    logger.info(f"SMS sent to {to_phone}: {message.sid}")
                else:
                    failed_phones.append({"phone": phone, "error": "No message SID returned"})
            except Exception as e:
                logger.error(f"Twilio SMS error for {phone}: {str(e)}")
                failed_phones.append({"phone": phone, "error": str(e)})
    
    # Log the SMS offer campaign
    campaign_record = {
        "id": str(uuid.uuid4()),
        "message": offer_data.message,
        "message_type": offer_data.message_type,
        "discount_code": discount_code,
        "discount_percent": offer_data.discount_percent,
        "total_recipients": len(offer_data.recipient_phones),
        "sent_count": sent_count,
        "failed_count": len(failed_phones),
        "failed_phones": failed_phones,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.sms_offer_campaigns.insert_one(campaign_record)
    
    return {
        "success": True,
        "message": f"SMS/WhatsApp offers sent to {sent_count} recipients",
        "sent_count": sent_count,
        "failed_count": len(failed_phones),
        "discount_code": discount_code,
        "campaign_id": campaign_record["id"]
    }


@router.get("/admin/sms-offers/campaigns")
async def get_sms_offer_campaigns(request: Request):
    """Get history of SMS/WhatsApp offer campaigns"""
    await require_admin(request)
    
    campaigns = await db.sms_offer_campaigns.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"campaigns": campaigns, "total": len(campaigns)}


@router.get("/admin/export/concern-report")
async def export_concern_report(request: Request):
    """
    Export Lab-Ready Concern Report CSV.
    Admin only - contains verified user data for R&D analysis.

    Includes:
    - User Profile (Whapi-verified phone, Email)
    - Bio-Age Data (Calculated Bio-Age vs Actual Age)
    - Top Concerns (AI-identified skin issues)
    - Referral Status (successful referrals count)
    """
    await require_admin(request)

    # Get all bio-age scans
    scans = await db.bio_scan_submissions.find({}, {"_id": 0}).to_list(10000)
    alt_scans = await db.bio_age_scans.find({}, {"_id": 0}).to_list(10000)

    # Merge scans by email
    seen_emails = set()
    all_scans = []
    all_emails = []
    for scan in scans + alt_scans:
        email = scan.get("email")
        if email and email not in seen_emails:
            seen_emails.add(email)
            all_scans.append(scan)
            all_emails.append(email.lower())

    # OPTIMIZED: Batch queries instead of N+1
    # Get all waitlist entries in one query
    waitlist_entries = await db.waitlist.find(
        {"email": {"$in": all_emails}}, {"_id": 0}
    ).to_list(10000)
    waitlist_map = {entry.get("email", "").lower(): entry for entry in waitlist_entries}
    
    # Get all founding member entries in one query
    founding_entries = await db.founding_members.find(
        {"email": {"$in": all_emails}}, {"_id": 0}
    ).to_list(10000)
    founding_map = {entry.get("email", "").lower(): entry for entry in founding_entries}
    
    # Get all referral codes from scans and user entries
    all_referral_codes = set()
    for scan in all_scans:
        if scan.get("referral_code"):
            all_referral_codes.add(scan.get("referral_code"))
    for entry in list(waitlist_map.values()) + list(founding_map.values()):
        if entry.get("referral_code"):
            all_referral_codes.add(entry.get("referral_code"))
    
    # Batch query for all referral counts
    referral_counts = {}
    if all_referral_codes:
        for code in all_referral_codes:
            count = await db.referrals.count_documents(
                {"referrer_code": code, "verified": True}
            )
            referral_counts[code] = count

    # Enrich with waitlist/founding member data for phone and referral info
    enriched_data = []
    for scan in all_scans:
        email = scan.get("email", "").lower()

        # Look up user in pre-fetched dictionaries (no database query)
        waitlist_entry = waitlist_map.get(email)
        founding_entry = founding_map.get(email)
        user_entry = waitlist_entry or founding_entry or {}

        # Get phone verification status
        phone = (
            scan.get("whatsapp_number")
            or scan.get("phone")
            or user_entry.get("phone_number")
            or user_entry.get("phone")
            or ""
        )
        whapi_verified = user_entry.get("whatsapp_verified", False) or scan.get(
            "whatsapp_verified", False
        )

        # Get referral count from pre-fetched dictionary (no database query)
        referral_code = (
            user_entry.get("referral_code") or scan.get("referral_code") or ""
        )
        referral_count = referral_counts.get(referral_code, 0) if referral_code else 0

        # Extract concerns from scan data
        concerns = scan.get("concerns", [])
        primary_concern = scan.get("primary_concern") or scan.get("main_concern") or ""
        if isinstance(concerns, list):
            top_concerns = ", ".join(concerns[:5]) if concerns else primary_concern
        else:
            top_concerns = concerns or primary_concern

        # Bio-age data
        bio_age = (
            scan.get("bio_age")
            or scan.get("calculated_bio_age")
            or scan.get("result")
            or ""
        )
        actual_age = (
            scan.get("actual_age")
            or scan.get("age")
            or scan.get("chronological_age")
            or ""
        )
        age_gap = ""
        if bio_age and actual_age:
            try:
                age_gap = int(bio_age) - int(actual_age)
            except (ValueError, TypeError):
                pass

        enriched_data.append(
            {
                "email": email,
                "phone": phone,
                "whapi_verified": "Yes" if whapi_verified else "No",
                "name": scan.get("name")
                or scan.get("full_name")
                or user_entry.get("name")
                or "",
                "actual_age": actual_age,
                "bio_age": bio_age,
                "age_gap": age_gap,
                "top_concerns": top_concerns,
                "skin_type": scan.get("skin_type") or "",
                "recommended_products": scan.get("recommended_products")
                or scan.get("recommendation")
                or "",
                "referral_code": referral_code,
                "verified_referrals": referral_count,
                "scan_date": (
                    scan.get("created_at", "")[:10] if scan.get("created_at") else ""
                ),
                "source": scan.get("source") or scan.get("referred_by") or "direct",
            }
        )

    return {
        "report_name": "ReRoots Lab Concern Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(enriched_data),
        "data": enriched_data,
        "columns": [
            "email",
            "phone",
            "whapi_verified",
            "name",
            "actual_age",
            "bio_age",
            "age_gap",
            "top_concerns",
            "skin_type",
            "recommended_products",
            "referral_code",
            "verified_referrals",
            "scan_date",
            "source",
        ],
    }


@router.post("/admin/bio-age-scans/upload-result")
async def upload_bio_age_scan_result(
    request: Request,
    file: UploadFile = File(...),
    scan_id: str = Form(...)
):
    """Upload PDF result for a bio-age scan to Cloudinary"""
    await require_admin(request)
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Read file content
    content = await file.read()
    
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")
    
    try:
        # Upload to Cloudinary
        import base64
        base64_content = base64.b64encode(content).decode('utf-8')
        
        upload_result = cloudinary.uploader.upload(
            f"data:application/pdf;base64,{base64_content}",
            resource_type="raw",
            folder="bio-age-results",
            public_id=f"result_{scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            format="pdf"
        )
        
        pdf_url = upload_result.get('secure_url')
        
        if not pdf_url:
            raise HTTPException(status_code=500, detail="Failed to get upload URL")
        
        # Update scan record with PDF URL
        # Try multiple collections where scan might exist
        update_data = {
            "result_pdf_url": pdf_url,
            "results_uploaded": True,
            "results_uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Try updating in bio_age_scans collection
        result = await db.bio_age_scans.update_one(
            {"$or": [{"id": scan_id}, {"_id": scan_id}]},
            {"$set": update_data}
        )
        
        # Also try bio_age_submissions
        if result.modified_count == 0:
            result = await db.bio_age_submissions.update_one(
                {"$or": [{"id": scan_id}, {"_id": scan_id}]},
                {"$set": update_data}
            )
        
        # Also try quiz_results (might have bio-age data)
        if result.modified_count == 0:
            await db.quiz_results.update_one(
                {"$or": [{"id": scan_id}, {"email": scan_id}]},
                {"$set": update_data}
            )
        
        logging.info(f"Bio-age result PDF uploaded: {pdf_url} for scan {scan_id}")
        
        return {
            "success": True,
            "pdf_url": pdf_url,
            "message": "Result PDF uploaded successfully"
        }
        
    except Exception as e:
        logging.error(f"Error uploading bio-age result PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/admin/bio-age-scans/send-results")
async def send_bio_age_results_notification(request: Request, data: dict = Body(...)):
    """Send results notification email to customer with PDF link"""
    await require_admin(request)
    
    scan_id = data.get("scan_id")
    email = data.get("email")
    name = data.get("name", "Valued Customer")
    bio_age = data.get("bio_age", "")
    pdf_url = data.get("pdf_url", "")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    if not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="Email service not configured")
    
    # Build beautiful results email
    pdf_button = ""
    if pdf_url:
        pdf_button = f"""
        <tr>
            <td align="center" style="padding: 20px 0;">
                <a href="{pdf_url}" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #F8A5B8 0%, #E88DA0 100%); color: white; padding: 16px 40px; border-radius: 30px; text-decoration: none; font-weight: 600; font-size: 16px; box-shadow: 0 4px 15px rgba(248, 165, 184, 0.4);">
                    📄 Download Your Full Report
                </a>
            </td>
        </tr>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f5f5f5; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width: 600px; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
                                <div style="font-size: 28px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
                                <div style="color: #D4AF37; font-size: 11px; letter-spacing: 2px; margin-top: 5px;">BIOTECH SKINCARE</div>
                            </td>
                        </tr>
                        
                        <!-- Main Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <h1 style="color: #2D2A2E; font-size: 24px; margin: 0 0 20px 0; text-align: center;">
                                    🎉 Your Results Are Ready!
                                </h1>
                                
                                <p style="color: #5A5A5A; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                    Hi {name},
                                </p>
                                
                                <p style="color: #5A5A5A; font-size: 16px; line-height: 1.6; margin: 0 0 25px 0;">
                                    Great news! Your personalized Bio-Age Repair Scan results have been analyzed by our team and are ready for you to review.
                                </p>
                                
                                <!-- Bio-Age Result Card -->
                                <div style="background: linear-gradient(135deg, #f8f4ff 0%, #e8f4ff 100%); border-radius: 12px; padding: 25px; text-align: center; margin: 20px 0;">
                                    <p style="color: #666; font-size: 14px; margin: 0 0 10px 0;">Your Bio-Age</p>
                                    <p style="color: #7C3AED; font-size: 48px; font-weight: bold; margin: 0;">{bio_age if bio_age else '--'}</p>
                                    <p style="color: #888; font-size: 12px; margin: 10px 0 0 0;">years</p>
                                </div>
                                
                                {pdf_button}
                                
                                <p style="color: #5A5A5A; font-size: 14px; line-height: 1.6; margin: 25px 0 0 0; text-align: center;">
                                    Questions about your results? Reply to this email or book a free consultation with our skincare experts.
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f8f8f8; padding: 25px 30px; text-align: center; border-top: 1px solid #eee;">
                                <p style="color: #999; font-size: 12px; margin: 0;">
                                    © {datetime.now().year} ReRoots Biotech Skincare. All rights reserved.
                                </p>
                                <p style="color: #bbb; font-size: 11px; margin: 10px 0 0 0;">
                                    Made with 💖 in Canada
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    try:
        import resend
        resend.api_key = RESEND_API_KEY
        
        email_response = resend.Emails.send({
            "from": "ReRoots <results@reroots.ca>",
            "to": [email],
            "subject": "🎉 Your Bio-Age Scan Results Are Ready!",
            "html": html_content
        })
        
        # Update scan record to mark results as sent
        update_data = {
            "results_sent": True,
            "results_sent_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Update in multiple possible collections
        await db.bio_age_scans.update_one(
            {"$or": [{"id": scan_id}, {"email": email}]},
            {"$set": update_data}
        )
        await db.bio_age_submissions.update_one(
            {"$or": [{"id": scan_id}, {"email": email}]},
            {"$set": update_data}
        )
        
        logging.info(f"Bio-age results notification sent to {email}")
        
        return {
            "success": True,
            "message": f"Results notification sent to {email}"
        }
        
    except Exception as e:
        logging.error(f"Error sending bio-age results notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")
async def send_offer_to_lead(request: Request, data: dict = Body(...)):
    """Send personalized offer email to a lead"""
    await require_admin(request)

    email = data.get("email")
    name = data.get("name", "Valued Customer")
    subject = data.get("subject", "Special Offer Just for You!")
    message = data.get("message", "")
    discount_code = data.get("discount_code", "")
    discount_percent = data.get("discount_percent", 10)

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    if not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="Email service not configured")

    # Build email HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f5f5f5; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width: 600px; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
                                <div style="font-size: 28px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
                                <div style="color: #D4AF37; font-size: 11px; letter-spacing: 2px; margin-top: 5px;">BIOTECH SKINCARE</div>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <h1 style="color: #2D2A2E; margin: 0 0 20px 0; font-size: 24px;">Hi {name.split()[0] if name else 'there'}!</h1>
                                
                                <p style="color: #5A5A5A; line-height: 1.7; margin: 0 0 20px 0;">
                                    {message if message else "We have a special offer just for you!"}
                                </p>
                                
                                {f'''
                                <div style="background: linear-gradient(135deg, #F8A5B8 0%, #E88DA0 100%); border-radius: 12px; padding: 25px; text-align: center; margin: 25px 0;">
                                    <p style="color: white; font-size: 14px; margin: 0 0 10px 0; text-transform: uppercase; letter-spacing: 1px;">Your Exclusive Code</p>
                                    <p style="color: white; font-size: 32px; font-weight: bold; margin: 0; letter-spacing: 3px;">{discount_code}</p>
                                    <p style="color: rgba(255,255,255,0.9); font-size: 18px; margin: 10px 0 0 0;">{discount_percent}% OFF your order</p>
                                </div>
                                ''' if discount_code else ''}
                                
                                <div style="text-align: center; margin: 30px 0;">
                                    <a href="https://reroots.ca/shop" style="display: inline-block; background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); color: white; padding: 15px 35px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                                        Shop Now
                                    </a>
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background: #fafafa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
                                <p style="color: #999; font-size: 12px; margin: 0;">
                                    ReRoots Biotech Skincare | Canada<br>
                                    <a href="https://reroots.ca" style="color: #F8A5B8;">reroots.ca</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [email],
            "subject": subject,
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)

        # Log the offer sent
        await db.offer_history.insert_one(
            {
                "email": email,
                "name": name,
                "subject": subject,
                "discount_code": discount_code,
                "discount_percent": discount_percent,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "sent_by": "admin",
            }
        )

        logger.info(f"Offer sent to {email}")
        return {"success": True, "message": f"Offer sent to {email}"}

    except Exception as e:
        logger.error(f"Failed to send offer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ END DATA HUB ENDPOINTS ============


# ============ CUSTOMIZABLE DASHBOARD ENDPOINTS ============


@router.get("/admin/dashboard-layout")
async def get_dashboard_layout(request: Request):
    """Get user's saved dashboard layout"""
    user = await require_admin(request)
    user_id = user.get("id") or user.get("email")

    layout = await db.dashboard_layouts.find_one({"user_id": user_id}, {"_id": 0})

    return {"layout": layout.get("layout") if layout else None}


@router.put("/admin/dashboard-layout")
async def save_dashboard_layout(request: Request, data: dict = Body(...)):
    """Save user's dashboard layout to database"""
    user = await require_admin(request)
    user_id = user.get("id") or user.get("email")

    layout_data = {
        "layout": data.get("layout"),
        "activeWidgets": data.get("activeWidgets"),
        "widgetTitles": data.get("widgetTitles", {}),
        "isLocked": data.get("isLocked", False),
    }

    await db.dashboard_layouts.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "layout": layout_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    return {"success": True, "message": "Layout saved"}


@router.get("/admin/sidebar-config")
async def get_sidebar_config(request: Request):
    """Get user's saved sidebar configuration"""
    user = await require_admin(request)
    user_id = user.get("id") or user.get("email")

    config = await db.sidebar_configs.find_one({"user_id": user_id}, {"_id": 0})

    if config:
        return {"menu_items": config.get("menu_items", [])}
    return {"menu_items": []}


@router.post("/admin/sidebar-config")
async def save_sidebar_config(request: Request, data: dict = Body(...)):
    """Save user's sidebar configuration to database"""
    user = await require_admin(request)
    user_id = user.get("id") or user.get("email")

    menu_items = data.get("menu_items", [])

    await db.sidebar_configs.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "menu_items": menu_items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    return {"success": True, "message": "Sidebar configuration saved"}




@router.get("/admin/dashboard-stats")
async def get_dashboard_stats(request: Request, brand: Optional[str] = None):
    """Get aggregated stats for dashboard widgets, filtered by brand"""
    await require_admin(request)
    
    # Build brand filter
    active_brand = brand or getattr(request.state, 'brand', 'reroots')
    brand_filter = {}
    if active_brand == "lavela":
        brand_filter = {"$or": [{"brand": "lavela"}, {"items.brand": "lavela"}, {"tags": {"$in": ["lavela", "teen"]}}]}
    elif active_brand == "reroots":
        brand_filter = {"brand": {"$ne": "lavela"}}

    # Revenue stats - filtered by brand
    orders_query = brand_filter if brand_filter else {}
    orders = await db.orders.find(orders_query).to_list(1000)
    total_revenue = sum(float(o.get("total", 0)) for o in orders)
    orders_count = len(orders)
    avg_order = total_revenue / orders_count if orders_count > 0 else 0

    # Quiz stats
    quiz_total = await db.quiz_submissions.count_documents({})
    quiz_users = await db.users.count_documents({"quiz_completed": True})
    quiz_count = quiz_total + quiz_users
    quiz_week = await db.quiz_submissions.count_documents(
        {
            "created_at": {
                "$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            }
        }
    )

    # Bio-age scan stats
    bio_total = await db.bio_scan_submissions.count_documents({})
    bio_alt = await db.bio_age_scans.count_documents({})
    bio_count = bio_total + bio_alt
    bio_month = await db.bio_scan_submissions.count_documents(
        {
            "created_at": {
                "$gte": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            }
        }
    )

    # Blog stats
    blogs = (
        await db.blogs.find({}, {"title": 1, "views": 1})
        .sort("created_at", -1)
        .to_list(10)
    )
    blog_total = await db.blogs.count_documents({})

    # Partners stats
    partners_total = await db.partners.count_documents({})
    partners_pending = await db.partners.count_documents({"status": "pending"})
    partner_sales = await db.partners.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$sales"}}}]
    ).to_list(1)

    # Founding members stats
    founding_total = await db.founding_members.count_documents({})
    founding_week = await db.founding_members.count_documents(
        {
            "created_at": {
                "$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            }
        }
    )
    founding_referrals = await db.founding_members.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$referral_count"}}}]
    ).to_list(1)

    # Subscribers stats
    subs_total = await db.newsletter_subscribers.count_documents({})
    subs_month = await db.newsletter_subscribers.count_documents(
        {
            "created_at": {
                "$gte": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            }
        }
    )

    # Recent orders - filtered by brand
    recent_orders = (
        await db.orders.find(orders_query, {"_id": 0}).sort("created_at", -1).to_list(10)
    )

    return {
        "revenue": {
            "total": f"{total_revenue:.2f}",
            "orders_count": orders_count,
            "avg_order": f"{avg_order:.2f}",
            "trend": 0,  # Would calculate from historical data
        },
        "quiz": {
            "total": quiz_count,
            "this_week": quiz_week,
            "conversion_rate": 87.5,  # Placeholder - would calculate
        },
        "bio_age": {
            "total": bio_count,
            "emails_captured": bio_count,
            "this_month": bio_month,
        },
        "blog": {
            "posts": [
                {"title": b.get("title", "Untitled"), "views": b.get("views", 0)}
                for b in blogs
            ],
            "total": blog_total,
        },
        "orders": {"orders": recent_orders[:5]},
        "partners": {
            "total": partners_total,
            "pending": partners_pending,
            "total_sales": partner_sales[0]["total"] if partner_sales else 0,
        },
        "founding": {
            "total": founding_total,
            "this_week": founding_week,
            "referrals": founding_referrals[0]["total"] if founding_referrals else 0,
        },
        "subscribers": {"total": subs_total, "this_month": subs_month},
    }


# ============ END CUSTOMIZABLE DASHBOARD ============


# ============ END FOUNDING MEMBER SYSTEM ============


