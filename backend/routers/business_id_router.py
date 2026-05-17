"""
AUREM Business ID System
Generates unique Business IDs (PREFIX-XXXX) for each tenant.
Supports team member connect, QR codes, and ID regeneration.
"""
import os
import re
import random
import string
import io
import base64
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional

import jwt

try:
    import qrcode
except ImportError:
    qrcode = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/business-id", tags=["Business ID"])

_db = None
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")
JWT_ALGORITHM = "HS256"

# Rate limiter for connect endpoint
_connect_attempts = defaultdict(list)


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(500, "Database not available")
    return _db


def generate_business_id(business_name: str, industry: str = None, city: str = None) -> str:
    """Generate a unique BIN (Business Intelligence Number).
    New format: {INDUSTRY}-{CITY}-{4CHARS}  e.g., AUT-MSS-7K92, SAL-TOR-3M41
    Falls back to legacy PREFIX-XXXX if industry/city are both missing.
    """
    if industry or city:
        from services.bin_generator import generate_bin
        return generate_bin(industry=industry, city=city)

    # Legacy fallback (no industry/city context)
    if not business_name:
        business_name = "AURM"
    prefix = business_name[:4].upper()
    prefix = re.sub(r'[^A-Z]', 'X', prefix)
    if len(prefix) < 4:
        prefix = prefix.ljust(4, 'X')
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    suffix = ''.join(random.choices(chars, k=4))
    return f"{prefix}-{suffix}"


async def ensure_business_id(user_doc: dict) -> str:
    """Ensure a user has a business_id (BIN). Generate and store if missing."""
    db = _get_db()
    if user_doc.get("business_id"):
        return user_doc["business_id"]
    business_name = user_doc.get("company") or user_doc.get("company_name") or user_doc.get("business_name") or user_doc.get("first_name", "USER")
    industry = user_doc.get("industry") or user_doc.get("business_type") or ""
    city = user_doc.get("city") or user_doc.get("business_city") or ""
    email = user_doc.get("email", "")
    for _ in range(10):
        bid = generate_business_id(business_name, industry=industry, city=city)
        existing_u = await db.users.find_one({"business_id": bid})
        existing_p = await db.platform_users.find_one({"business_id": bid})
        if not existing_u and not existing_p:
            # Update in whichever collection holds this user
            update = {"$set": {
                "business_id": bid,
                "business_id_created": datetime.now(timezone.utc).isoformat(),
                "business_id_active": True,
            }}
            if email:
                await db.users.update_one({"email": email}, update)
                await db.platform_users.update_one({"email": email}, update)
            logger.info(f"[BIZ-ID] Generated {bid} for {email}")
            return bid
    raise HTTPException(500, "Failed to generate unique Business ID")


def _decode_jwt(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    try:
        return jwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


def _get_client_ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")


class ConnectRequest(BaseModel):
    business_id: str


@router.get("/mine")
async def get_my_business_id(request: Request):
    """Get the current user's Business ID and basic info."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = payload.get("email") or payload.get("sub")
    user_id = payload.get("user_id")

    user = None
    if email:
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            user = await db.platform_users.find_one({"email": email}, {"_id": 0})
    if not user and user_id:
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    bid = await ensure_business_id(user)
    plan_doc = await db.tenant_plans.find_one({"tenant_id": user.get("tenant_id", user.get("id"))}, {"_id": 0})

    return {
        "business_id": bid,
        "business_name": user.get("company") or user.get("company_name") or user.get("business_name") or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
        "plan": plan_doc.get("plan_name", "Starter") if plan_doc else "Starter",
        "connected_since": user.get("created_at", ""),
        "business_id_active": user.get("business_id_active", True),
    }


@router.post("/connect")
async def connect_with_business_id(data: ConnectRequest, request: Request):
    """Connect to a business using their Business ID. Returns scoped team member token."""
    db = _get_db()
    ip = _get_client_ip(request)

    now = datetime.now(timezone.utc)
    _connect_attempts[ip] = [t for t in _connect_attempts[ip] if (now - t).total_seconds() < 3600]
    if len(_connect_attempts[ip]) >= 5:
        raise HTTPException(429, "Too many attempts. Try again in 1 hour.")
    _connect_attempts[ip].append(now)

    bid = data.business_id.strip().upper()
    owner = await db.users.find_one({"business_id": bid, "business_id_active": True}, {"_id": 0})
    if not owner:
        owner = await db.platform_users.find_one({"business_id": bid, "business_id_active": True}, {"_id": 0})
    if not owner:
        raise HTTPException(404, "Business ID not found or inactive")

    tenant_id = owner.get("tenant_id") or owner.get("id")
    token_payload = {
        "role": "team_member",
        "tenant_id": tenant_id,
        "business_id_used": bid,
        "owner_email": owner.get("email"),
        "permissions": ["read_only", "ora_chat"],
        "exp": now + timedelta(days=30),
        "iat": now,
    }
    token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    await db.team_connections.update_one(
        {"business_id": bid, "ip": ip},
        {"$set": {
            "business_id": bid,
            "tenant_id": tenant_id,
            "ip": ip,
            "connected_at": now.isoformat(),
            "last_active": now.isoformat(),
            "user_agent": request.headers.get("user-agent", ""),
        }},
        upsert=True
    )

    plan_doc = await db.tenant_plans.find_one({"tenant_id": tenant_id}, {"_id": 0})
    plan = plan_doc.get("plan_name", "Starter") if plan_doc else "Starter"

    return {
        "token": token,
        "role": "team_member",
        "tenant_id": tenant_id,
        "business_name": owner.get("company") or owner.get("company_name") or owner.get("business_name", ""),
        "plan": plan,
        "permissions": ["read_only", "ora_chat"],
        "expires_in_days": 30,
    }


@router.get("/qr/{business_id}")
async def get_qr_code(business_id: str):
    """Generate a QR code PNG (base64) for the given Business ID."""
    if qrcode is None:
        raise HTTPException(500, "QR code library not installed")
    db = _get_db()
    bid = business_id.strip().upper()
    owner = await db.users.find_one({"business_id": bid, "business_id_active": True})
    if not owner:
        owner = await db.platform_users.find_one({"business_id": bid, "business_id_active": True})
    if not owner:
        raise HTTPException(404, "Business ID not found")

    base_url = os.environ.get("APP_BASE_URL", "https://aurem.live")
    url = f"{base_url}/ora?id={bid}"

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#C9A84C", back_color="#050507")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "qr_base64": b64,
        "url_encoded": url,
        "business_id": bid,
    }


@router.post("/regenerate")
async def regenerate_business_id(request: Request):
    """Regenerate Business ID. Owner only. Old ID immediately invalidated."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = payload.get("email") or payload.get("sub")
    user_id = payload.get("user_id")

    user = None
    if email:
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            user = await db.platform_users.find_one({"email": email}, {"_id": 0})
    if not user and user_id:
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    if payload.get("role") == "team_member":
        raise HTTPException(403, "Only the business owner can regenerate the ID")

    old_bid = user.get("business_id")
    business_name = user.get("company") or user.get("company_name") or user.get("business_name") or user.get("first_name", "USER")
    industry = user.get("industry") or user.get("business_type") or ""
    city = user.get("city") or user.get("business_city") or ""

    for _ in range(10):
        new_bid = generate_business_id(business_name, industry=industry, city=city)
        if new_bid != old_bid:
            existing_u = await db.users.find_one({"business_id": new_bid})
            existing_p = await db.platform_users.find_one({"business_id": new_bid})
            if not existing_u and not existing_p:
                update = {"$set": {
                    "business_id": new_bid,
                    "business_id_created": datetime.now(timezone.utc).isoformat(),
                    "business_id_active": True,
                }}
                await db.users.update_one({"email": user["email"]}, update)
                await db.platform_users.update_one({"email": user["email"]}, update)
                if old_bid:
                    await db.team_connections.delete_many({"business_id": old_bid})
                logger.info(f"[BIZ-ID] Regenerated {old_bid} -> {new_bid} for {user['email']}")
                return {
                    "business_id": new_bid,
                    "old_business_id": old_bid,
                    "message": "Business ID regenerated. Old ID is now invalid.",
                    "disconnected_devices": True,
                }

    raise HTTPException(500, "Failed to generate unique Business ID")


@router.get("/team")
async def get_team_connections(request: Request):
    """Get all devices/team members connected via this Business ID."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = payload.get("email") or payload.get("sub")
    user_id = payload.get("user_id")

    user = None
    if email:
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            user = await db.platform_users.find_one({"email": email}, {"_id": 0})
    if not user and user_id:
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    bid = user.get("business_id")
    if not bid:
        return {"connections": [], "count": 0}

    connections = []
    cursor = db.team_connections.find({"business_id": bid}, {"_id": 0})
    async for conn in cursor:
        connections.append({
            "ip": conn.get("ip", "")[:10] + "***",
            "connected_at": conn.get("connected_at"),
            "last_active": conn.get("last_active"),
            "user_agent": conn.get("user_agent", "")[:60],
        })

    return {"connections": connections, "count": len(connections)}


@router.post("/revoke/{ip_prefix}")
async def revoke_team_connection(ip_prefix: str, request: Request):
    """Revoke a specific team connection."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = payload.get("email") or payload.get("sub")
    user = await db.users.find_one({"email": email}, {"_id": 0}) if email else None
    if not user and email:
        user = await db.platform_users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    bid = user.get("business_id")
    if not bid:
        raise HTTPException(400, "No Business ID set")

    result = await db.team_connections.delete_many({
        "business_id": bid,
        "ip": {"$regex": f"^{re.escape(ip_prefix)}"}
    })
    return {"revoked": result.deleted_count}


@router.post("/resend-welcome")
async def resend_welcome_to_self(request: Request):
    """Resend welcome package to the current user."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = payload.get("email") or payload.get("sub")
    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")

    user = None
    if email:
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            user = await db.platform_users.find_one({"email": email}, {"_id": 0})
    if not user and user_id:
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user and tenant_id:
        user = await db.users.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    tid = user.get("tenant_id") or user.get("id") or user.get("email")

    from services.welcome_package import send_welcome_package
    result = await send_welcome_package(tid, user)
    return {"message": "Welcome package resent to your email", "success": bool(result)}


@router.get("/welcome-status")
async def get_welcome_status(request: Request):
    """Check if welcome card should be shown."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = payload.get("email") or payload.get("sub")
    user_id = payload.get("user_id")

    user = None
    if email:
        user = await db.users.find_one({"email": email}, {"_id": 0, "show_welcome_card": 1, "business_id": 1})
        if not user:
            user = await db.platform_users.find_one({"email": email}, {"_id": 0, "show_welcome_card": 1, "business_id": 1})
    if not user and user_id:
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "show_welcome_card": 1, "business_id": 1})
    if not user:
        return {"show_welcome_card": False}

    return {
        "show_welcome_card": user.get("show_welcome_card", False),
        "business_id": user.get("business_id", ""),
    }


@router.post("/dismiss-welcome")
async def dismiss_welcome_card(request: Request):
    """Dismiss the welcome card (never show again)."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = payload.get("email") or payload.get("sub")
    user_id = payload.get("user_id")

    update = {"$set": {"show_welcome_card": False}}
    if email:
        await db.users.update_one({"email": email}, update)
        await db.platform_users.update_one({"email": email}, update)
    if user_id:
        await db.users.update_one({"id": user_id}, update)
    return {"dismissed": True}
