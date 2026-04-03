"""
Authentication Routes: Login, Register, Google SSO, Password Reset
"""
import logging
import os
import re
import uuid
import time
import secrets
import jwt
import httpx
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import EmailStr

from config import get_database, JWT_SECRET, JWT_ALGORITHM, RESEND_API_KEY
from models.auth import UserCreate, UserLogin, User, TokenResponse, PasswordResetRequest, PasswordResetConfirm
from utils.auth import (
    hash_password, verify_password, create_token, get_current_user,
    require_auth, SUPER_ADMIN_PERMISSIONS
)

# Initialize router
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Get database - LAZY: don't create at import time to avoid blocking on mongodb+srv:// DNS
_db = None

def get_auth_db():
    """Lazy database getter to avoid blocking during import"""
    global _db
    if _db is None:
        _db = get_database()
    return _db

# Admin email whitelist for Google OAuth
ADMIN_EMAIL_WHITELIST = [
    "admin@reroots.ca",
    "teji.ss1986@gmail.com",
]

# Failed login tracking
failed_logins = defaultdict(list)
LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = 900  # 15 minutes


def validate_email(email: str) -> bool:
    """Basic email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password_strength(password: str) -> tuple:
    """Check password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    return True, "Password is strong"


def sanitize_input(text: str) -> str:
    """Sanitize user input"""
    import html
    return html.escape(text.strip())[:200]


def check_account_lockout(identifier: str) -> bool:
    """Check if account is locked"""
    current_time = time.time()
    failed_logins[identifier] = [
        t for t in failed_logins[identifier] if current_time - t < LOCKOUT_DURATION
    ]
    return len(failed_logins[identifier]) >= LOCKOUT_THRESHOLD


def record_failed_login(identifier: str):
    failed_logins[identifier].append(time.time())


def clear_failed_logins(identifier: str):
    failed_logins[identifier] = []


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    """Register a new user"""
    email = user_data.email.lower().strip()
    first_name = sanitize_input(user_data.first_name)
    last_name = sanitize_input(user_data.last_name)
    phone = user_data.phone.strip() if user_data.phone else None

    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    phone_digits = ''.join(filter(str.isdigit, phone))
    if len(phone_digits) < 10:
        raise HTTPException(status_code=400, detail="Please enter a valid phone number")

    if not validate_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    is_valid, message = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    existing = await get_auth_db().users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if phone:
        existing_phone = await get_auth_db().users.find_one({"phone": phone})
        if existing_phone:
            raise HTTPException(status_code=400, detail="Phone number already registered")

    user = User(email=email, first_name=first_name, last_name=last_name, phone=phone)
    user_dict = user.model_dump()
    user_dict["password"] = hash_password(user_data.password)
    user_dict["created_at"] = user_dict["created_at"].isoformat()

    await get_auth_db().users.insert_one(user_dict)
    token = create_token(user.id, user.is_admin)

    logging.info(f"New user registered: {email}")

    # Credit pending points from guest checkouts
    try:
        pending_points = await get_auth_db().pending_points.find({"email": email}).to_list(100)
        if pending_points:
            total_pending = sum(p.get("points", 0) for p in pending_points)
            if total_pending > 0:
                await get_auth_db().loyalty_points.update_one(
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
                await get_auth_db().pending_points.delete_many({"email": email})
                logging.info(f"Credited {total_pending} pending points to {email}")
    except Exception as e:
        logging.error(f"Failed to credit pending points: {e}")

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


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with email or phone"""
    if not credentials.email and not credentials.phone:
        raise HTTPException(status_code=400, detail="Email or phone number required")

    identifier = (
        credentials.email.lower().strip() if credentials.email
        else credentials.phone.strip()
    )

    if check_account_lockout(identifier):
        raise HTTPException(
            status_code=429,
            detail="Account temporarily locked. Please try again in 15 minutes."
        )

    query = {"email": credentials.email.lower().strip()} if credentials.email else {"phone": credentials.phone.strip()}

    # Check regular users
    user = await get_auth_db().users.find_one(query, {"_id": 0})
    
    # Check if user signed up with Google OAuth - they must use Google Sign-in
    if user:
        logging.info(f"Login attempt for {credentials.email}, auth_provider: {user.get('auth_provider')}")
        if user.get("auth_provider") == "google":
            logging.info(f"Blocking password login for Google user: {credentials.email}")
            raise HTTPException(
                status_code=403,
                detail="This account was created with Google. Please use 'Sign in with Google' button."
            )
    
    # SECURITY: Block password login for whitelisted admin emails - must use Google SSO
    if user and credentials.email:
        email_lower = credentials.email.lower().strip()
        if email_lower in [e.lower() for e in ADMIN_EMAIL_WHITELIST]:
            # Check if this admin requires Google SSO
            if user.get("auth_provider") == "google" or user.get("require_sso"):
                raise HTTPException(
                    status_code=403,
                    detail="This admin account requires Google SSO login. Please use 'Sign in with Google'."
                )
    
    if user and verify_password(credentials.password, user.get("password", "")):
        clear_failed_logins(identifier)
        token = create_token(user["id"], user.get("is_admin", False))

        response_data = {
            "id": user["id"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "phone": user.get("phone"),
            "is_admin": user.get("is_admin", False),
        }

        if user.get("is_admin"):
            response_data["is_super_admin"] = True
            response_data["permissions"] = SUPER_ADMIN_PERMISSIONS

        return TokenResponse(token=token, user=response_data)

    # Check team members
    if credentials.email:
        team_member = await get_auth_db().team_members.find_one(
            {"email": credentials.email.lower().strip()}, {"_id": 0}
        )
        if team_member and team_member.get("status") == "active":
            if team_member.get("password_hash") and verify_password(
                credentials.password, team_member["password_hash"]
            ):
                clear_failed_logins(identifier)

                token_payload = {
                    "user_id": team_member["id"],
                    "is_admin": True,
                    "is_team_member": True,
                    "exp": datetime.now(timezone.utc) + timedelta(days=7),
                }
                token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

                role = await get_auth_db().roles.find_one({"id": team_member.get("role_id")}, {"_id": 0})

                return TokenResponse(
                    token=token,
                    user={
                        "id": team_member["id"],
                        "email": team_member["email"],
                        "first_name": team_member.get("first_name", ""),
                        "last_name": team_member.get("last_name", ""),
                        "is_admin": True,
                        "is_team_member": True,
                        "permissions": role.get("permissions", {}) if role else {},
                        "role_name": role.get("name", "Team Member") if role else "Team Member",
                    },
                )

    record_failed_login(identifier)
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/me")
async def get_me(request: Request):
    """Get current user info"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ============= GOOGLE OAUTH =============
# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS

@router.post("/google/admin-session")
async def process_admin_google_session(data: dict, response: Response):
    """Process Google OAuth for admin login"""
    session_id = data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    try:
        auth_service_url = os.environ.get("AUTH_SERVICE_URL", "https://demobackend.emergentagent.com")
        async with httpx.AsyncClient() as client:
            auth_response = await client.get(
                f"{auth_service_url}/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
            )

            if auth_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session")

            google_user = auth_response.json()
    except Exception as e:
        logging.error(f"Google admin auth error: {e}")
        raise HTTPException(status_code=401, detail="Failed to verify Google session")

    email = google_user.get("email", "").lower().strip()
    name = google_user.get("name", "")
    picture = google_user.get("picture", "")
    session_token = google_user.get("session_token")

    # Check whitelist or team member
    is_whitelisted = email in [e.lower() for e in ADMIN_EMAIL_WHITELIST]
    team_member = await get_auth_db().team_members.find_one({"email": email, "status": "active"}, {"_id": 0})

    if not is_whitelisted and not team_member:
        logging.warning(f"Unauthorized admin login attempt: {email}")
        raise HTTPException(status_code=403, detail="This Google account is not authorized for admin access.")

    # Handle team member
    if team_member:
        await get_auth_db().team_members.update_one(
            {"email": email},
            {"$set": {"google_picture": picture, "last_login": datetime.now(timezone.utc).isoformat(), "auth_provider": "google"}}
        )

        role = await get_auth_db().roles.find_one({"id": team_member.get("role_id")}, {"_id": 0})

        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        await get_auth_db().google_sessions.update_one(
            {"user_id": team_member["id"]},
            {"$set": {"user_id": team_member["id"], "session_token": session_token, "expires_at": expires_at.isoformat()}},
            upsert=True
        )

        token_payload = {
            "user_id": team_member["id"],
            "is_admin": True,
            "is_team_member": True,
            "exp": expires_at,
        }
        token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60)

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

    # Handle whitelisted admin
    existing_user = await get_auth_db().users.find_one({"email": email}, {"_id": 0})

    if existing_user:
        user_id = existing_user["id"]
        await get_auth_db().users.update_one(
            {"email": email},
            {"$set": {"is_admin": True, "google_picture": picture, "last_login": datetime.now(timezone.utc).isoformat(), "auth_provider": "google"}}
        )
    else:
        name_parts = name.split(" ", 1)
        user_id = f"google-admin-{uuid.uuid4().hex[:12]}"
        new_user = {
            "id": user_id,
            "email": email,
            "first_name": name_parts[0] if name_parts else "Admin",
            "last_name": name_parts[1] if len(name_parts) > 1 else "",
            "google_picture": picture,
            "password": "",
            "is_admin": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auth_provider": "google",
        }
        await get_auth_db().users.insert_one(new_user)
        logging.info(f"New Google admin: {email}")

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await get_auth_db().google_sessions.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "session_token": session_token, "expires_at": expires_at.isoformat()}},
        upsert=True
    )

    token = create_token(user_id, True)

    response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60)

    user = await get_auth_db().users.find_one({"id": user_id}, {"_id": 0, "password": 0})

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


@router.post("/google/session")
async def process_google_session(data: dict, response: Response):
    """Process Google OAuth for regular users"""
    session_id = data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    try:
        auth_service_url = os.environ.get("AUTH_SERVICE_URL", "https://demobackend.emergentagent.com")
        async with httpx.AsyncClient() as client:
            auth_response = await client.get(
                f"{auth_service_url}/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
            )

            if auth_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session")

            google_user = auth_response.json()
    except Exception as e:
        logging.error(f"Google auth error: {e}")
        raise HTTPException(status_code=401, detail="Failed to verify Google session")

    email = google_user.get("email", "").lower()
    name = google_user.get("name", "")
    picture = google_user.get("picture", "")
    session_token = google_user.get("session_token")

    existing_user = await get_auth_db().users.find_one({"email": email}, {"_id": 0})

    if existing_user:
        user_id = existing_user["id"]
        await get_auth_db().users.update_one(
            {"email": email},
            {"$set": {"google_picture": picture, "last_login": datetime.now(timezone.utc).isoformat()}}
        )
    else:
        name_parts = name.split(" ", 1)
        user_id = str(uuid.uuid4())
        new_user = {
            "id": user_id,
            "email": email,
            "first_name": name_parts[0] if name_parts else "User",
            "last_name": name_parts[1] if len(name_parts) > 1 else "",
            "google_picture": picture,
            "password": "",
            "is_admin": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auth_provider": "google",
        }
        await get_auth_db().users.insert_one(new_user)
        logging.info(f"New Google user: {email}")

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await get_auth_db().google_sessions.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "session_token": session_token, "expires_at": expires_at.isoformat()}},
        upsert=True
    )

    token = create_token(user_id, False)

    response.set_cookie(key="session_token", value=session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60)

    user = await get_auth_db().users.find_one({"id": user_id}, {"_id": 0, "password": 0})

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


# ============= PASSWORD RESET =============

@router.post("/forgot-password")
async def forgot_password(request_data: PasswordResetRequest, request: Request):
    """Send password reset email"""
    email = request_data.email.lower().strip()
    
    user = await get_auth_db().users.find_one({"email": email}, {"_id": 0})
    if not user:
        # Don't reveal if email exists
        return {"message": "If this email exists, you will receive reset instructions."}

    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    await get_auth_db().password_resets.update_one(
        {"email": email},
        {"$set": {"token": reset_token, "expires_at": expires_at.isoformat(), "used": False}},
        upsert=True
    )

    # Use /app route for PWA reset flow - dynamic origin only, no hardcoded fallback
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(status_code=400, detail="Origin header required for password reset")
    reset_link = f"{origin}/app?reset_token={reset_token}"
    
    # Get user's name for personalized email
    name = user.get("name") or user.get("first_name") or "there"

    try:
        import resend
        resend.api_key = RESEND_API_KEY

        resend.Emails.send({
            "from": "ReRoots <hello@reroots.ca>",
            "to": email,
            "subject": "Reset your ReRoots password",
            "html": f"""
            <div style="background:#060608;color:#F0EBE0;padding:40px;font-family:Georgia,serif;">
                <h2 style="color:#C9A86E;margin-bottom:20px;">Password Reset</h2>
                <p style="margin-bottom:16px;">Hi {name},</p>
                <p style="margin-bottom:24px;">Click below to reset your password. Link expires in 1 hour.</p>
                <a href="{reset_link}" 
                   style="background:#C9A86E;color:#060608;padding:14px 28px;
                          text-decoration:none;border-radius:4px;display:inline-block;
                          font-family:sans-serif;letter-spacing:0.1em;font-size:12px;">
                    RESET PASSWORD
                </a>
                <p style="color:#5C5548;font-size:12px;margin-top:24px;">
                    If you didn't request this, ignore this email.
                </p>
                <hr style="border:none;border-top:1px solid #1a1a1a;margin:30px 0;"/>
                <p style="color:#3a3a3a;font-size:11px;">reroots.ca · Canadian Biotech Skincare</p>
            </div>
            """
        })
        logging.info(f"Password reset email sent to {email}")
    except Exception as e:
        logging.error(f"Failed to send password reset email: {e}")

    return {"message": "If this email exists, you will receive reset instructions."}


@router.post("/reset-password")
async def reset_password(request_data: PasswordResetConfirm):
    """Reset password with token"""
    reset_record = await get_auth_db().password_resets.find_one(
        {"token": request_data.token, "used": False}, {"_id": 0}
    )

    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    expires_at = datetime.fromisoformat(reset_record["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired")

    is_valid, message = validate_password_strength(request_data.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    new_hash = hash_password(request_data.new_password)

    await get_auth_db().users.update_one(
        {"email": reset_record["email"]},
        {"$set": {"password": new_hash}}
    )

    await get_auth_db().password_resets.update_one(
        {"token": request_data.token},
        {"$set": {"used": True}}
    )

    logging.info(f"Password reset successful for {reset_record['email']}")

    return {"message": "Password reset successful"}


@router.get("/verify-reset-token")
async def verify_reset_token(token: str):
    """Verify if reset token is valid"""
    reset_record = await get_auth_db().password_resets.find_one(
        {"token": token, "used": False}, {"_id": 0}
    )

    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid token")

    expires_at = datetime.fromisoformat(reset_record["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")

    return {"valid": True}
