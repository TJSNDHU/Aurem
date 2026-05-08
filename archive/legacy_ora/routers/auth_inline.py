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
                        "$inc": {"balance": total_pending, "lifetime_earned": total_pending},
                        "$setOnInsert": {
                            "id": str(uuid.uuid4()),
                            "user_id": user.id,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        },
                        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                    },
                    upsert=True
                )
                
                # Update orders to show points are no longer pending
                for p in pending_points:
                    await db.orders.update_one(
                        {"id": p.get("order_id")},
                        {"$set": {"points_pending": False, "user_id": user.id}}
                    )
                
                # Delete pending points records
                await db.pending_points.delete_many({"email": email})
                
                logging.info(f"[Registration] Credited {total_pending} pending points to new user {email}")
    except Exception as e:
        logging.error(f"[Registration] Failed to credit pending points: {e}")

    # Send welcome email
    try:
        from routers.email_service import send_welcome_email
        name = first_name or email.split("@")[0]
        send_welcome_email(email, name, "Silver", 0)
    except Exception as e:
        logging.warning(f"[Registration] Welcome email failed: {e}")

    return TokenResponse(
        token=token,
        user={
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "is_admin": user.is_admin,
        },
    )



# ═══════════════════════════════════════════════════════════════════════════════
# LOYALTY POINTS REDEMPTION
# ═══════════════════════════════════════════════════════════════════════════════

class RedeemPointsRequest(BaseModel):
    points: int

@router.post("/loyalty/redeem")
async def redeem_loyalty_points(request: RedeemPointsRequest, current_user: dict = Depends(get_current_user)):
    """Redeem loyalty points for store credit"""
    try:
        user_id = current_user.get("id")
        points_to_redeem = request.points
        
        if points_to_redeem <= 0:
            raise HTTPException(status_code=400, detail="Invalid points amount")
        
        # Get user's loyalty balance
        loyalty = await db.loyalty_points.find_one({"user_id": user_id}, {"_id": 0})
        current_balance = loyalty.get("balance", 0) if loyalty else 0
        
        if points_to_redeem > current_balance:
            raise HTTPException(status_code=400, detail="Insufficient points")
        
        # Calculate store credit (100 points = $1)
        credit_amount = points_to_redeem * 0.01
        
        # Update loyalty balance
        await db.loyalty_points.update_one(
            {"user_id": user_id},
            {
                "$inc": {"balance": -points_to_redeem, "lifetime_redeemed": points_to_redeem},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        # Add store credit to user
        await db.users.update_one(
            {"id": user_id},
            {"$inc": {"store_credit": credit_amount}}
        )
        
        # Log the redemption
        await db.loyalty_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": "redemption",
            "points": -points_to_redeem,
            "credit_amount": credit_amount,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        logging.info(f"[Loyalty] User {user_id} redeemed {points_to_redeem} points for ${credit_amount}")
        
        return {
            "success": True,
            "points_redeemed": points_to_redeem,
            "credit_amount": credit_amount,
            "new_balance": current_balance - points_to_redeem
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[Loyalty] Redemption error: {e}")
        raise HTTPException(status_code=500, detail="Failed to redeem points")



@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, credentials: UserLogin):
    # Support login with email OR phone
    if not credentials.email and not credentials.phone:
        raise HTTPException(status_code=400, detail="Email or phone number required")

    identifier = (
        credentials.email.lower().strip()
        if credentials.email
        else credentials.phone.strip()
    )

    # Check for account lockout
    if check_account_lockout(identifier):
        raise HTTPException(
            status_code=429,
            detail="Account temporarily locked due to too many failed login attempts. Please try again in 15 minutes.",
        )

    # Build query - search by email OR phone
    if credentials.email:
        query = {"email": credentials.email.lower().strip()}
    else:
        query = {"phone": credentials.phone.strip()}

    # First check regular users
    user = await db.users.find_one(query, {"_id": 0})
    
    # Check if user signed up with Google OAuth - they must use Google Sign-in
    if user and user.get("auth_provider") == "google":
        raise HTTPException(
            status_code=403,
            detail="This account was created with Google. Please use 'Sign in with Google' button instead."
        )
    
    if user and verify_password(credentials.password, user["password"]):
        # Clear failed login attempts on success
        clear_failed_logins(identifier)

        token = create_token(user["id"], user.get("is_admin", False), email=user.get("email"))

        # Log successful login
        logging.info(f"Successful login for user: {user['email']}")

        response_data = {
            "id": user["id"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "phone": user.get("phone"),
            "is_admin": user.get("is_admin", False),
        }

        # Add super admin flag and permissions only if user has is_super_admin=true in DB
        if user.get("is_super_admin"):
            response_data["is_super_admin"] = True
            response_data["permissions"] = SUPER_ADMIN_PERMISSIONS
            # Add RLS info - super admins can access all brands
            response_data["rls"] = {
                "role": "super_admin",
                "brand_ids": ["reroots", "lavela"],  # Access to all brands
                "can_switch_brands": True
            }
        else:
            response_data["is_super_admin"] = False
            # Non-super-admin users get limited RLS scope
            response_data["rls"] = {
                "role": "tenant_admin",
                "brand_ids": [user.get("tenant_id", "reroots")],
                "can_switch_brands": False
            }

        return TokenResponse(token=token, user=response_data)

    # Check team members (email only for team members)
    team_member = None
    if credentials.email:
        team_member = await db.team_members.find_one(
            {"email": credentials.email.lower().strip()}, {"_id": 0}
        )
        if team_member and team_member.get("status") == "active":
            if team_member.get("password_hash") and verify_password(
                credentials.password, team_member["password_hash"]
            ):
                # Clear failed login attempts on success
                clear_failed_logins(identifier)

                # Create token with team member flag
                token_payload = {
                    "user_id": team_member["id"],
                    "is_admin": True,
                    "is_team_member": True,
                    "exp": datetime.now(timezone.utc) + timedelta(days=7),
                }
                token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

                # Get role and permissions
                role = await db.roles.find_one(
                    {"id": team_member.get("role_id")}, {"_id": 0}
                )
                permissions = (
                    role.get("permissions", DEFAULT_PERMISSIONS)
                    if role
                    else DEFAULT_PERMISSIONS
                )
                role_name = role.get("name", "Team Member") if role else "Team Member"

                # Update last login
                await db.team_members.update_one(
                    {"id": team_member["id"]},
                    {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}},
                )

                logging.info(f"Successful team member login: {team_member['email']}")

                return TokenResponse(
                    token=token,
                    user={
                        "id": team_member["id"],
                        "email": team_member["email"],
                        "first_name": team_member["first_name"],
                        "last_name": team_member["last_name"],
                        "is_admin": True,
                        "is_team_member": True,
                        "is_super_admin": False,
                        "role_id": team_member.get("role_id"),
                        "role_name": role_name,
                        "permissions": permissions,
                        # RLS info for team members - scope to assigned brands
                        "rls": {
                            "role": "brand_admin",
                            "brand_ids": team_member.get("brand_ids", ["reroots"]),
                            "can_switch_brands": len(team_member.get("brand_ids", ["reroots"])) > 1
                        }
                    },
                )

        # Check if team member exists but disabled
        if team_member and team_member.get("status") == "disabled":
            raise HTTPException(
                status_code=403,
                detail="Account has been disabled. Contact administrator.",
            )

        # Check if team member exists but pending
        if team_member and team_member.get("status") == "pending":
            raise HTTPException(
                status_code=403,
                detail="Account is pending activation. Please check your email for the activation link.",
            )

    # Invalid credentials
    record_failed_login(identifier)
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ============= GOOGLE OAUTH LOGIN =============
# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

# Google OAuth Configuration (Custom credentials from user's Google Cloud Console)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "https://reroots.ca/auth/google/callback")

# Admin email whitelist for Google OAuth admin access
ADMIN_EMAIL_WHITELIST = [
    "admin@reroots.ca",
    "teji.ss1986@gmail.com",
]


@router.get("/auth/google/config")
async def get_google_oauth_config():
    """Return Google OAuth Client ID for frontend use"""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    return {"client_id": GOOGLE_CLIENT_ID}


@router.post("/auth/google/verify-token")
async def verify_google_token(data: dict, response: Response):
    """
    Verify Google ID token from frontend @react-oauth/google library.
    This handles the new custom OAuth flow using user's own Google credentials.
    """
    credential = data.get("credential")
    is_admin_login = data.get("is_admin", False)
    
    if not credential:
        raise HTTPException(status_code=400, detail="Google credential token required")
    
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured on server")
    
    try:
        # Verify the ID token with Google's tokeninfo endpoint
        client = await get_auth_client()
        verify_response = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
        )
        
        if verify_response.status_code != 200:
            logging.error(f"[GoogleAuth] Token verification failed: {verify_response.text}")
            raise HTTPException(status_code=401, detail="Invalid Google token")
        
        google_user = verify_response.json()
        
        # Verify the token was issued for our app
        if google_user.get("aud") != GOOGLE_CLIENT_ID:
            logging.error(f"[GoogleAuth] Token audience mismatch: {google_user.get('aud')} != {GOOGLE_CLIENT_ID}")
            raise HTTPException(status_code=401, detail="Token was not issued for this application")
        
        email = google_user.get("email", "").lower().strip()
        name = google_user.get("name", "")
        picture = google_user.get("picture", "")
        
        logging.info(f"[GoogleAuth] Verified token for: {email}")
        
    except httpx.TimeoutException:
        logging.error("[GoogleAuth] Token verification timeout")
        raise HTTPException(status_code=401, detail="Auth service timeout - please try again")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[GoogleAuth] Token verification error: {e}")
        raise HTTPException(status_code=401, detail="Failed to verify Google token")
    
    # Handle admin login
    if is_admin_login:
        # Check if email is in admin whitelist OR is an active team member
        is_whitelisted_admin = email in [e.lower() for e in ADMIN_EMAIL_WHITELIST]
        
        team_member = await db.team_members.find_one(
            {"email": email, "status": "active"}, {"_id": 0}
        )
        
        if not is_whitelisted_admin and not team_member:
            logging.warning(f"[GoogleAuth] Unauthorized admin login attempt from: {email}")
            raise HTTPException(
                status_code=403,
                detail="This Google account is not authorized for admin access. Contact your administrator."
            )
        
        # Handle team member login
        if team_member:
            await db.team_members.update_one(
                {"email": email},
                {
                    "$set": {
                        "google_picture": picture,
                        "last_login": datetime.now(timezone.utc).isoformat(),
                        "auth_provider": "google",
                    }
                },
            )
            
            role = await db.roles.find_one({"id": team_member.get("role_id")}, {"_id": 0})
            
            token_payload = {
                "user_id": team_member["id"],
                "is_admin": True,
                "is_team_member": True,
                "exp": datetime.now(timezone.utc) + timedelta(days=7),
            }
            token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
            
            logging.info(f"[GoogleAuth] Team member login successful: {email}")
            
            return {
                "token": token,
                "user": {
                    "id": team_member["id"],
                    "email": team_member["email"],
                    "first_name": team_member.get("first_name", ""),
                    "last_name": team_member.get("last_name", ""),
                    "is_admin": True,
                    "is_team_member": True,
                    "permissions": role.get("permissions", {}) if role else {},
                    "role_name": role.get("name", "Team Member") if role else "Team Member",
                    "google_picture": picture,
                },
            }
        
        # Handle whitelisted admin login
        existing_user = await db.users.find_one({"email": email}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["id"]
            await db.users.update_one(
                {"email": email},
                {
                    "$set": {
                        "is_admin": True,
                        "google_picture": picture,
                        "last_login": datetime.now(timezone.utc).isoformat(),
                        "auth_provider": "google",
                    }
                },
            )
        else:
            name_parts = name.split(" ", 1)
            first_name = name_parts[0] if name_parts else "Admin"
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            
            user_id = f"google-admin-{uuid.uuid4().hex[:12]}"
            new_user = {
                "id": user_id,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "google_picture": picture,
                "password": "",
                "is_admin": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "auth_provider": "google",
            }
            await db.users.insert_one(new_user)
            logging.info(f"[GoogleAuth] New admin registered: {email}")
        
        token_payload = {
            "user_id": user_id,
            "is_admin": True,
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
        }
        token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        
        logging.info(f"[GoogleAuth] Admin login successful: {email}")
        
        return {
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user.get("last_name", ""),
                "is_admin": True,
                "google_picture": user.get("google_picture"),
            },
        }
    
    # Handle regular user login
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["id"]
        await db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "google_picture": picture,
                    "last_login": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
    else:
        name_parts = name.split(" ", 1)
        first_name = name_parts[0] if name_parts else "User"
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        user_id = str(uuid.uuid4())
        new_user = {
            "id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "google_picture": picture,
            "password": "",
            "is_admin": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auth_provider": "google",
        }
        await db.users.insert_one(new_user)
        logging.info(f"[GoogleAuth] New user registered: {email}")
    
    token = create_token(user_id, False, email=email)
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user.get("last_name", ""),
            "is_admin": user.get("is_admin", False),
            "google_picture": user.get("google_picture"),
        },
    }


# Legacy endpoints for backward compatibility (Emergent-managed OAuth)
@router.post("/auth/google/admin-session")
async def process_admin_google_session(data: dict, response: Response):
    """Process Google OAuth for ADMIN login - only whitelisted emails allowed (Legacy Emergent flow)"""
    session_id = data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    # Exchange session_id for user data from Emergent Auth
    # Uses global HTTP client for connection pooling and speed
    try:
        client = await get_auth_client()
        auth_response = await client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id},
        )

        if auth_response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session")

        google_user = auth_response.json()
    except httpx.TimeoutException:
        logging.error("Google admin auth timeout")
        raise HTTPException(status_code=401, detail="Auth service timeout - please try again")
    except Exception as e:
        logging.error(f"Google admin auth error: {e}")
        raise HTTPException(status_code=401, detail="Failed to verify Google session")

    email = google_user.get("email", "").lower().strip()
    name = google_user.get("name", "")
    picture = google_user.get("picture", "")
    session_token = google_user.get("session_token")

    # SECURITY: Check if email is in admin whitelist OR is an active team member
    is_whitelisted_admin = email in [e.lower() for e in ADMIN_EMAIL_WHITELIST]
    
    # Check if this email belongs to an active team member
    team_member = await db.team_members.find_one(
        {"email": email, "status": "active"}, {"_id": 0}
    )
    
    if not is_whitelisted_admin and not team_member:
        logging.warning(f"Unauthorized admin login attempt from: {email}")
        raise HTTPException(
            status_code=403,
            detail="This Google account is not authorized for admin access. Contact your administrator."
        )

    # Handle team member login
    if team_member:
        # Update team member with Google auth
        await db.team_members.update_one(
            {"email": email},
            {
                "$set": {
                    "google_picture": picture,
                    "last_login": datetime.now(timezone.utc).isoformat(),
                    "auth_provider": "google",
                }
            },
        )
        
        # Get role and permissions
        role = await db.roles.find_one({"id": team_member.get("role_id")}, {"_id": 0})
        
        # Store session
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        await db.google_sessions.update_one(
            {"user_id": team_member["id"]},
            {
                "$set": {
                    "user_id": team_member["id"],
                    "session_token": session_token,
                    "expires_at": expires_at.isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            upsert=True,
        )
        
        # Create JWT token for team member
        token_payload = {
            "user_id": team_member["id"],
            "is_admin": True,
            "is_team_member": True,
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
        }
        token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        # Set cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=7 * 24 * 60 * 60,
        )
        
        logging.info(f"Team member Google OAuth login successful: {email}")
        
        return {
            "token": token,
            "user": {
                "id": team_member["id"],
                "email": team_member["email"],
                "first_name": team_member.get("first_name", ""),
                "last_name": team_member.get("last_name", ""),
                "is_admin": True,
                "is_team_member": True,
                "permissions": role.get("permissions", {}) if role else {},
                "role_name": role.get("name", "Team Member") if role else "Team Member",
                "google_picture": picture,
            },
        }

    # Handle whitelisted admin login
    # Check if admin user exists
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})

    if existing_user:
        # Update existing user to admin
        user_id = existing_user["id"]
        await db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "is_admin": True,
                    "google_picture": picture,
                    "last_login": datetime.now(timezone.utc).isoformat(),
                    "auth_provider": "google",
                }
            },
        )
    else:
        # Create new admin user from Google data
        name_parts = name.split(" ", 1)
        first_name = name_parts[0] if name_parts else "Admin"
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        user_id = f"google-admin-{uuid.uuid4().hex[:12]}"
        new_user = {
            "id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "google_picture": picture,
            "password": "",  # No password for Google SSO users
            "is_admin": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auth_provider": "google",
        }
        await db.users.insert_one(new_user)
        logging.info(f"New Google admin registered: {email}")

    # Store session in database
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.google_sessions.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "session_token": session_token,
                "expires_at": expires_at.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    # Create JWT token with admin privileges
    token = create_token(user_id, True, email=email)  # is_admin=True

    # Set httpOnly cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    # Get user data
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})

    logging.info(f"Admin Google OAuth login successful: {email}")

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "is_admin": True,
            "is_super_admin": True,
            "permissions": SUPER_ADMIN_PERMISSIONS,
            "google_picture": user.get("google_picture"),
        },
    }


@router.post("/auth/google/session")
async def process_google_session(data: dict, response: Response):
    """Process Google OAuth session_id and create user session"""
    session_id = data.get("session_id")
    logging.info("[GoogleAuth] Received session exchange request")
    
    if not session_id:
        logging.error("[GoogleAuth] No session_id provided")
        raise HTTPException(status_code=400, detail="session_id required")

    logging.info(f"[GoogleAuth] Session ID received (first 10 chars): {session_id[:10]}...")

    # Exchange session_id for user data from Emergent Auth
    # Uses global HTTP client for connection pooling and speed
    try:
        client = await get_auth_client()
        logging.info("[GoogleAuth] Calling Emergent Auth API...")
        auth_response = await client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id},
        )
        
        logging.info(f"[GoogleAuth] Emergent Auth response status: {auth_response.status_code}")
        
        if auth_response.status_code != 200:
            error_body = auth_response.text
            logging.error(f"[GoogleAuth] Invalid session, status: {auth_response.status_code}, body: {error_body}")
            # Try to parse the error message
            try:
                error_json = auth_response.json()
                detail = error_json.get('detail', {})
                if isinstance(detail, dict):
                    error_desc = detail.get('error_description', 'Session expired or invalid')
                else:
                    error_desc = str(detail) if detail else 'Session expired or invalid'
            except:
                error_desc = 'Session expired or invalid'
            raise HTTPException(status_code=401, detail=error_desc)

        google_user = auth_response.json()
        logging.info(f"[GoogleAuth] Got user data for: {google_user.get('email', 'unknown')}")
    except httpx.TimeoutException as e:
        logging.error(f"[GoogleAuth] Timeout error: {e}")
        raise HTTPException(status_code=401, detail="Auth service timeout")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[GoogleAuth] Unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=401, detail="Failed to verify Google session")

    email = google_user.get("email", "").lower()
    name = google_user.get("name", "")
    picture = google_user.get("picture", "")
    session_token = google_user.get("session_token")

    # Check if user exists
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})

    if existing_user:
        # Update existing user
        user_id = existing_user["id"]
        await db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "google_picture": picture,
                    "last_login": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
    else:
        # Create new user from Google data
        name_parts = name.split(" ", 1)
        first_name = name_parts[0] if name_parts else "User"
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        user_id = str(uuid.uuid4())
        new_user = {
            "id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "google_picture": picture,
            "password": "",  # No password for Google users
            "is_admin": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auth_provider": "google",
        }
        await db.users.insert_one(new_user)
        logging.info(f"New Google user registered: {email}")

    # Store session in database
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.google_sessions.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "session_token": session_token,
                "expires_at": expires_at.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    # Create JWT token for the app
    token = create_token(user_id, False, email=email)

    # Set httpOnly cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    # Get user data
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "is_admin": user.get("is_admin", False),
            "google_picture": user.get("google_picture"),
        },
    }


