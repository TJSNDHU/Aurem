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
from pydantic import EmailStr, BaseModel

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

# Admin email whitelist — single source of truth in utils.admin_guard.
# Re-exported here for backward compatibility with existing call sites.
from utils.admin_guard import ADMIN_EMAIL_WHITELIST  # noqa: E402,F401

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
    token = create_token(user.id, user.is_admin, email=email)

    logging.info(f"New user registered: {email}")

    # ═══ ITER 322n — BILLING CUSTOMER WIRE-UP (P0 FUNNEL FIX) ═══
    # Mirror of the platform_auth_router fix. Without this, /api/aurem-
    # billing/checkout returns "Business not found in billing" → user
    # can never reach Stripe. Idempotent + non-blocking.
    try:
        from shared.commercial.billing_service import get_billing_service
        from datetime import datetime as _dt, timezone as _tz

        _db = get_auth_db()
        billing_svc = get_billing_service(_db)

        biz_name = f"{user.first_name} {user.last_name}".strip() or email
        # Generate a stable business_id keyed off user.id so the same
        # user always maps to the same billing row.
        ws_business_id = f"u_{user.id[:16]}"

        _now = _dt.now(_tz.utc)
        await _db.aurem_workspaces.update_one(
            {"business_id": ws_business_id},
            {"$setOnInsert": {
                "business_id": ws_business_id,
                "business_name": biz_name,
                "owner_email": email,
                "owner_id": user.id,
                "plan": "trial",
                "status": "active",
                "created_at": _now,
                "updated_at": _now,
            }},
            upsert=True,
        )
        await billing_svc.create_customer(
            business_id=ws_business_id,
            email=email,
            business_name=biz_name,
        )
        # Backfill business_id onto the user row so checkout can find it.
        await _db.users.update_one(
            {"id": user.id},
            {"$set": {"business_id": ws_business_id}},
        )
        logging.info(f"[REGISTER] billing seeded for {email} biz={ws_business_id}")
    except Exception as _be:
        logging.warning(f"[REGISTER] billing seed deferred ({email}): {_be}")

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
    """Login with email, phone, or AUREM Business ID (BIN)."""
    if not credentials.email and not credentials.phone:
        raise HTTPException(status_code=400, detail="Email or phone number required")

    # ─── BIN-or-email resolution (P0 customer convenience) ────────
    # If `credentials.email` looks like a BIN (e.g. "RERO-3DEJ"),
    # resolve to the underlying email before everything else runs.
    if credentials.email:
        raw = credentials.email.strip()
        if "@" not in raw:
            import re as _re
            bin_pat = _re.compile(r"^[a-z]{3,5}-[a-z0-9]{3,6}$", _re.IGNORECASE)
            if bin_pat.match(raw):
                bid = raw.upper()
                _adb = get_auth_db()
                resolved_email = None
                # Try platform_users (modern) then users (legacy)
                doc = await _adb.platform_users.find_one(
                    {"business_id": bid}, {"_id": 0, "email": 1}
                )
                if doc and doc.get("email"):
                    resolved_email = doc["email"]
                else:
                    doc = await _adb.users.find_one(
                        {"business_id": bid}, {"_id": 0, "email": 1}
                    )
                    if doc and doc.get("email"):
                        resolved_email = doc["email"]
                if resolved_email:
                    credentials.email = resolved_email
                else:
                    # Unknown BIN — generic 401 (no enumeration)
                    raise HTTPException(status_code=401, detail="Invalid credentials")
            else:
                # Not an email AND not a valid BIN format → 401
                raise HTTPException(status_code=401, detail="Invalid credentials")

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
        token = create_token(user["id"], user.get("is_admin", False), email=user.get("email"))

        response_data = {
            "id": user["id"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "phone": user.get("phone"),
            "is_admin": user.get("is_admin", False),
        }

        # Only set is_super_admin=true if the user actually has that flag in DB
        if user.get("is_super_admin"):
            response_data["is_super_admin"] = True
            response_data["permissions"] = SUPER_ADMIN_PERMISSIONS
        else:
            response_data["is_super_admin"] = False

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


# ============= ADMIN LOGIN (Separated) =============

# Admin login lockout: stricter (5 attempts, 15 min)
admin_failed_logins = defaultdict(list)
ADMIN_LOCKOUT_THRESHOLD = 5
ADMIN_LOCKOUT_DURATION = 900  # 15 minutes


@router.post("/admin/login")
async def admin_login(credentials: UserLogin, request: Request):
    """
    Admin-only login endpoint.
    Only users with is_super_admin=True can authenticate.
    No biometric gate. Strong password only.
    Logs suspicious IPs.
    """
    if not credentials.email:
        raise HTTPException(status_code=400, detail="Email required")

    email = credentials.email.lower().strip()
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")

    # Check admin lockout (stricter: 5 attempts, 15 min)
    current_time = time.time()
    admin_failed_logins[email] = [
        t for t in admin_failed_logins[email] if current_time - t < ADMIN_LOCKOUT_DURATION
    ]
    if len(admin_failed_logins[email]) >= ADMIN_LOCKOUT_THRESHOLD:
        # Log suspicious activity
        try:
            await get_auth_db().suspicious_ips.insert_one({
                "ip": client_ip,
                "email": email,
                "event": "admin_lockout_triggered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        raise HTTPException(
            status_code=429,
            detail="Admin account locked. Try again in 15 minutes."
        )

    # Lookup user
    user = await get_auth_db().users.find_one({"email": email}, {"_id": 0})

    if not user:
        admin_failed_logins[email].append(time.time())
        # Log unknown admin attempt
        try:
            await get_auth_db().suspicious_ips.insert_one({
                "ip": client_ip,
                "email": email,
                "event": "admin_login_unknown_email",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # ROLE CHECK: must be super_admin
    if not user.get("is_super_admin"):
        admin_failed_logins[email].append(time.time())
        # Log role violation attempt
        try:
            await get_auth_db().suspicious_ips.insert_one({
                "ip": client_ip,
                "email": email,
                "event": "admin_login_wrong_role",
                "actual_role": "tenant" if not user.get("is_admin") else "admin",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")

    # Password check
    if not verify_password(credentials.password, user.get("password", "")):
        admin_failed_logins[email].append(time.time())
        try:
            await get_auth_db().suspicious_ips.insert_one({
                "ip": client_ip,
                "email": email,
                "event": "admin_login_wrong_password",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # ── 2FA TOTP gate (founder hardening) ──
    totp_secret = user.get("totp_secret")
    totp_enabled = bool(user.get("totp_enabled") and totp_secret)
    if totp_enabled:
        from services.totp_service import verify_totp
        if not credentials.totp_code:
            # Signal frontend to prompt for code without burning a failed attempt
            raise HTTPException(status_code=401, detail="2fa_required")
        if not verify_totp(totp_secret, credentials.totp_code):
            admin_failed_logins[email].append(time.time())
            try:
                await get_auth_db().suspicious_ips.insert_one({
                    "ip": client_ip,
                    "email": email,
                    "event": "admin_login_wrong_totp",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass
            raise HTTPException(status_code=401, detail="Invalid 2FA code")

    # Success — clear lockout
    admin_failed_logins[email] = []

    # Short-lived admin JWT (8h) + rotating refresh token (7d)
    from services.totp_service import (
        ADMIN_ACCESS_TOKEN_HOURS,
        issue_refresh_token,
    )
    user_agent = request.headers.get("user-agent", "")[:300]
    token_payload = {
        "user_id": user["id"],
        "is_admin": True,
        "is_super_admin": True,
        "role": "super_admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=ADMIN_ACCESS_TOKEN_HOURS),
    }
    token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    refresh = await issue_refresh_token(
        get_auth_db(), user["id"], ip=client_ip, ua=user_agent,
    )

    return TokenResponse(
        token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "is_admin": True,
            "is_super_admin": True,
            "role": "super_admin",
            "totp_enabled": totp_enabled,
            "refresh_token": refresh,
            "expires_in": ADMIN_ACCESS_TOKEN_HOURS * 3600,
        }
    )


# ============= ADMIN 2FA TOTP + REFRESH =============

class _TOTPSetupBody(BaseModel):
    pass


class _TOTPEnableBody(BaseModel):
    code: str


class _RefreshBody(BaseModel):
    refresh_token: str


@router.post("/admin/2fa/setup")
async def admin_2fa_setup(request: Request):
    """Generate (or re-show pending) TOTP secret + QR for the authenticated super-admin.
    Secret is stored as `pending_totp_secret` until verified via /admin/2fa/enable.
    """
    user = await require_auth(request)
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    from services.totp_service import (
        generate_totp_secret,
        provisioning_uri,
        qr_data_url,
    )
    db = get_auth_db()
    secret = generate_totp_secret()
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"pending_totp_secret": secret,
                  "pending_totp_secret_at": datetime.now(timezone.utc).isoformat()}},
    )
    uri = provisioning_uri(secret, user["email"])
    return {
        "secret": secret,
        "otpauth_uri": uri,
        "qr_data_url": qr_data_url(uri),
        "issuer": os.environ.get("AUREM_TOTP_ISSUER", "AUREM Admin"),
    }


@router.post("/admin/2fa/enable")
async def admin_2fa_enable(body: _TOTPEnableBody, request: Request):
    """Verify the first TOTP code and enable 2FA for this admin."""
    user = await require_auth(request)
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_auth_db()
    row = await db.users.find_one({"id": user["id"]}, {"_id": 0, "pending_totp_secret": 1})
    pending = (row or {}).get("pending_totp_secret")
    if not pending:
        raise HTTPException(status_code=400, detail="No pending 2FA setup. Call /admin/2fa/setup first.")

    from services.totp_service import verify_totp
    if not verify_totp(pending, body.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"totp_secret": pending,
                  "totp_enabled": True,
                  "totp_enabled_at": datetime.now(timezone.utc).isoformat()},
         "$unset": {"pending_totp_secret": "", "pending_totp_secret_at": ""}},
    )
    return {"success": True, "totp_enabled": True}


@router.post("/admin/2fa/disable")
async def admin_2fa_disable(body: _TOTPEnableBody, request: Request):
    """Disable 2FA — requires a valid current TOTP code (no plain-password override)."""
    user = await require_auth(request)
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_auth_db()
    row = await db.users.find_one({"id": user["id"]}, {"_id": 0, "totp_secret": 1, "totp_enabled": 1})
    if not (row and row.get("totp_enabled") and row.get("totp_secret")):
        raise HTTPException(status_code=400, detail="2FA is not enabled")

    from services.totp_service import verify_totp, revoke_all_refresh_tokens
    if not verify_totp(row["totp_secret"], body.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"totp_enabled": False},
         "$unset": {"totp_secret": "", "pending_totp_secret": "", "pending_totp_secret_at": ""}},
    )
    await revoke_all_refresh_tokens(db, user["id"])
    return {"success": True, "totp_enabled": False}


@router.get("/admin/2fa/status")
async def admin_2fa_status(request: Request):
    user = await require_auth(request)
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"totp_enabled": bool(user.get("totp_enabled"))}


@router.post("/admin/refresh")
async def admin_refresh(body: _RefreshBody, request: Request):
    """Exchange a refresh token for a fresh 8h admin access token (rotated)."""
    from services.totp_service import (
        consume_refresh_token,
        issue_refresh_token,
        ADMIN_ACCESS_TOKEN_HOURS,
    )
    db = get_auth_db()
    user_id = await consume_refresh_token(db, body.refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user or not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Admin privileges required")

    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    ua = request.headers.get("user-agent", "")[:300]
    token = jwt.encode(
        {
            "user_id": user["id"],
            "is_admin": True,
            "is_super_admin": True,
            "role": "super_admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=ADMIN_ACCESS_TOKEN_HOURS),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    new_refresh = await issue_refresh_token(db, user["id"], ip=client_ip, ua=ua)
    return {
        "token": token,
        "refresh_token": new_refresh,
        "expires_in": ADMIN_ACCESS_TOKEN_HOURS * 3600,
    }


@router.post("/admin/refresh/revoke-all")
async def admin_refresh_revoke_all(request: Request):
    """Founder kill-switch: revoke every refresh token for this admin."""
    user = await require_auth(request)
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.totp_service import revoke_all_refresh_tokens
    n = await revoke_all_refresh_tokens(get_auth_db(), user["id"])
    return {"success": True, "revoked": n}




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

    token = create_token(user_id, True, email=email)

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

    token = create_token(user_id, False, email=email)

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


@router.post("/google/callback")
async def process_google_callback(data: dict, response: Response):
    """
    Unified Google OAuth callback — entrypoint hit by GoogleAuthCallback.jsx
    after Emergent's OAuth gateway redirects back with a session_id.

    Routes intelligently:
      • Email in ADMIN_EMAIL_WHITELIST or active team_member → admin-session flow
      • Anyone else → regular customer session flow

    The frontend then inspects the returned JWT's `is_admin` claim to redirect
    to /admin/console vs /my.
    """
    session_id = data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    # First verify the Google session via Emergent's auth gateway so we can
    # peek at the email and decide which flow to use.
    try:
        auth_service_url = os.environ.get(
            "AUTH_SERVICE_URL", "https://demobackend.emergentagent.com"
        )
        async with httpx.AsyncClient() as client:
            auth_response = await client.get(
                f"{auth_service_url}/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
            )
            if auth_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session")
            google_user = auth_response.json()
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Google callback verify error: {e}")
        raise HTTPException(status_code=401, detail="Failed to verify Google session")

    email = (google_user.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Google session missing email")

    is_whitelisted = email in [e.lower() for e in ADMIN_EMAIL_WHITELIST]
    team_member = await get_auth_db().team_members.find_one(
        {"email": email, "status": "active"}, {"_id": 0}
    )

    if is_whitelisted or team_member:
        # Admin / team-member flow — delegate to the existing admin handler.
        logging.info(f"[GOOGLE-CALLBACK] admin route for {email}")
        return await process_admin_google_session(data, response)

    # Regular customer flow.
    logging.info(f"[GOOGLE-CALLBACK] customer route for {email}")
    return await process_google_session(data, response)


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

    # Use /my route which is the new Luxe customer portal.
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(status_code=400, detail="Origin header required for password reset")
    reset_link = f"{origin}/my?reset_token={reset_token}"

    # Get user's name for personalized email
    name = user.get("name") or user.get("first_name") or "there"

    try:
        import resend
        resend.api_key = RESEND_API_KEY

        resend.Emails.send({
            "from": "AUREM <hello@aurem.live>",
            "to": email,
            "subject": "Reset your AUREM password",
            "html": f"""
            <div style="background:#0A0C10;color:#F0EBE0;padding:40px;font-family:Georgia,serif;">
                <div style="text-align:center;margin-bottom:24px;">
                  <span style="display:inline-block;width:36px;height:36px;border-radius:9px;
                               background:linear-gradient(135deg,#FFE4A8,#C9A84C);color:#0A0C10;
                               font-family:Inter,sans-serif;font-weight:700;font-size:18px;
                               line-height:36px;text-align:center;">A</span>
                </div>
                <h2 style="color:#FFE4A8;margin-bottom:20px;font-family:Georgia,serif;letter-spacing:0.05em;">Password Reset</h2>
                <p style="margin-bottom:16px;">Hi {name},</p>
                <p style="margin-bottom:24px;">Click below to reset your AUREM password. The link expires in 1 hour.</p>
                <div style="text-align:center;margin:30px 0;">
                  <a href="{reset_link}"
                     style="background:linear-gradient(135deg,#FFE4A8,#C9A84C);color:#0A0C10;
                            padding:14px 32px;text-decoration:none;border-radius:6px;
                            display:inline-block;font-family:Inter,sans-serif;
                            letter-spacing:0.18em;font-size:12px;font-weight:600;
                            text-transform:uppercase;">
                      Reset Password
                  </a>
                </div>
                <p style="color:#8a8275;font-size:12px;margin-top:24px;">
                    If you didn't request this, you can safely ignore this email.
                </p>
                <hr style="border:none;border-top:1px solid #1a1a1a;margin:30px 0;"/>
                <p style="color:#6a6560;font-size:11px;font-family:monospace;letter-spacing:0.1em;">
                  AUREM · Autonomous Intelligence Platform · Mississauga, Canada
                </p>
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

    # Sync BOTH `password` and `password_hash` so admin/customer login flows
    # (which read different fields) stay in lockstep.
    await get_auth_db().users.update_one(
        {"email": reset_record["email"]},
        {"$set": {"password": new_hash, "password_hash": new_hash}}
    )
    # Also mirror to platform_users + aurem_users (best-effort).
    try:
        await get_auth_db().platform_users.update_one(
            {"email": reset_record["email"]},
            {"$set": {"password_hash": new_hash}}
        )
        await get_auth_db().aurem_users.update_one(
            {"email": reset_record["email"]},
            {"$set": {"password_hash": new_hash}}
        )
    except Exception as _e:
        logging.warning(f"[RESET] secondary mirror failed: {_e}")

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
