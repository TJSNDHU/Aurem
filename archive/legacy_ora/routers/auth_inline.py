"""
Auth helpers + login/register + Google OAuth
Extracted from server.py during modularization.
"""

import os
try:
    import httpx
except ImportError:
    httpx = None
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
try:
    from models.server_models import (
        DEFAULT_PERMISSIONS, SUPER_ADMIN_PERMISSIONS,
        TokenResponse, User, UserCreate, UserLogin, Order, Review
    )
except ImportError:
    pass
try:
    from services.email_templates import (
        check_account_lockout, clear_failed_logins,
        record_failed_login, validate_password_strength
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)

_auth_client = None
async def get_auth_client():
    global _auth_client
    if httpx and (_auth_client is None or _auth_client.is_closed):
        _auth_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )
    return _auth_client


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
JWT_ALGORITHM = "HS256"
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

# ============= AUTH HELPERS =============


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: str, is_admin: bool = False, tenant_id: str = None, email: str = None) -> str:
    payload = {
        "user_id": user_id,
        "is_admin": is_admin,
        "tenant_id": tenant_id or user_id,
        "exp": datetime.now(timezone.utc).timestamp() + 86400 * 7,  # 7 days
    }
    if email:
        payload["email"] = email
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> Optional[dict]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        is_team_member = payload.get("is_team_member", False)

        if is_team_member:
            # Fetch team member
            team_member = await db.team_members.find_one(
                {"id": user_id}, {"_id": 0, "password_hash": 0}
            )
            if team_member and team_member.get("status") == "active":
                # Get role permissions
                role = await db.roles.find_one(
                    {"id": team_member.get("role_id")}, {"_id": 0}
                )
                team_member["permissions"] = (
                    role.get("permissions", DEFAULT_PERMISSIONS)
                    if role
                    else DEFAULT_PERMISSIONS
                )
                team_member["role_name"] = (
                    role.get("name", "Unknown") if role else "Unknown"
                )
                team_member["is_team_member"] = True
                team_member["is_admin"] = True  # Grant admin panel access
                return team_member
            return None
        else:
            # Regular user or super admin
            user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
            if user and user.get("is_admin"):
                user["is_super_admin"] = True
                user["permissions"] = SUPER_ADMIN_PERMISSIONS
            return user
    except Exception:
        return None


async def require_auth(request: Request) -> dict:
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


# ============ DATA GOLD MINE - Customer Record Helper ============

async def ensure_customer_record(email: str, phone: str = None, source: str = "unknown"):
    """
    Ensure customer record exists and has complete data.
    Called from: Quiz, Order, Waitlist, Review, Gift Roots, Account creation.
    
    This is the "Data Gold Mine" - every customer touchpoint feeds into this.
    """
    if not email:
        return None
        
    existing = await db.customers.find_one({"email": email.lower()})
    
    if existing:
        # Update phone if it was missing and we now have it
        update_fields = {}
        if phone and not existing.get("phone"):
            update_fields["phone"] = phone
        if source and source not in existing.get("sources", []):
            # Track all sources where we acquired this customer's data
            sources = existing.get("sources", [])
            sources.append(source)
            update_fields["sources"] = sources
        
        if update_fields:
            update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.customers.update_one(
                {"email": email.lower()},
                {"$set": update_fields}
            )
        return existing.get("id", str(existing.get("_id", "")))
    else:
        # Create new customer record
        customer_id = str(uuid.uuid4())
        await db.customers.insert_one({
            "id": customer_id,
            "email": email.lower(),
            "phone": phone,
            "sources": [source] if source else [],
            "loyalty_balance": 0,
            "tags": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        return customer_id


async def log_ai_insight(insight_type: str, data: dict):
    """
    Log data point to AI insights collection for machine learning.
    Every significant customer action should call this.
    """
    try:
        await db.ai_insights.insert_one({
            "type": insight_type,
            "data": data,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        print(f"Failed to log AI insight: {e}")


async def require_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(request: Request) -> dict:
    """Only the main admin account can access this"""
    user = await get_current_user(request)
    if not user or not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


def check_permission(user: dict, feature: str, action: str) -> bool:
    """Check if user has permission for a specific action on a feature"""
    if user.get("is_super_admin"):
        return True
    permissions = user.get("permissions", {})
    feature_perms = permissions.get(feature, {})
    return feature_perms.get(action, False)


async def require_permission(request: Request, feature: str, action: str) -> dict:
    """Require specific permission for an action"""
    user = await require_admin(request)
    if not check_permission(user, feature, action):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {action} access required for {feature}",
        )
    return user


# ============= AUTH ROUTES =============


@router.post("/auth/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(request: Request, user_data: UserCreate):
    # Sanitize inputs
    email = user_data.email.lower().strip()
    first_name = sanitize_input(user_data.first_name.strip())
    last_name = sanitize_input(user_data.last_name.strip())
    phone = user_data.phone.strip() if user_data.phone else None

    # Phone is optional for PWA signups
    if phone:
        # Validate phone format (basic check)
        phone_digits = ''.join(filter(str.isdigit, phone))
        if len(phone_digits) < 10:
            raise HTTPException(status_code=400, detail="Please enter a valid phone number (at least 10 digits)")

    # Validate email format
    if not validate_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Validate password strength
    is_valid, message = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    # Check if email already exists
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if phone already exists (if provided)
    if phone:
        existing_phone = await db.users.find_one({"phone": phone})
        if existing_phone:
            raise HTTPException(
                status_code=400, detail="Phone number already registered"
            )

    user = User(email=email, first_name=first_name, last_name=last_name, phone=phone)
    user_dict = user.model_dump()
    user_dict["password"] = hash_password(user_data.password)
    user_dict["created_at"] = user_dict["created_at"].isoformat()

    await db.users.insert_one(user_dict)
    token = create_token(user.id, user.is_admin, tenant_id=user.id, email=email)

    logging.info(f"New user registered: {email}")
    
    # Credit any pending points from guest checkouts
    try:
        pending_points = await db.pending_points.find({"email": email}).to_list(100)
        if pending_points:
            total_pending = sum(p.get("points", 0) for p in pending_points)
            if total_pending > 0:
                # Credit the points to the new user
                await db.loyalty_points.update_one(
                    {"user_id": user.id},
                    {
                        "$inc": {"