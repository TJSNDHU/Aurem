"""
AUREM Platform Authentication Router
Admin-only JWT authentication for AUREM platform
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import jwt
import hashlib
import bcrypt
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/platform/auth", tags=["Platform Auth"])

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET environment variable not set.")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7  # 1 week

# In-memory admin store — uses bcrypt from ENV
ADMIN_USERS = {
    "admin@aurem.live": {
        "password_hash": os.getenv("ADMIN_PASSWORD_HASH_2", "").replace("$$", "$"),
        "full_name": "AUREM Admin",
        "company_name": "AUREM Platform",
        "role": "admin",
        "created_at": datetime.utcnow().isoformat(),
        "is_bcrypt": True
    }
}

# MongoDB connection (will be set by server.py)
db = None

def set_db(database):
    global db
    db = database

class LoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    identifier: Optional[str] = None  # BIN or email — takes precedence if provided
    password: str

class RegisterRequest(BaseModel):
    """Signup payload — accepts both legacy (full_name + company_name)
    and the live frontend shape (first_name + last_name + company).
    Optional fields keep backward compatibility with existing API callers
    while the live PlatformAuth.jsx form uses the split fields."""
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    # iter 322z — accept the live frontend shape
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    terms_accepted: bool = False
    # iter 322bg — optional 4–6 digit PIN set at signup
    pin: Optional[str] = None

    def normalized_full_name(self) -> str:
        if self.full_name:
            return self.full_name.strip()
        parts = [self.first_name or "", self.last_name or ""]
        joined = " ".join(p.strip() for p in parts if p and p.strip())
        return joined or "Customer"

    def normalized_company(self) -> str:
        return (self.company_name or self.company or "").strip()

class TokenResponse(BaseModel):
    token: str
    email: str
    full_name: str
    company_name: str
    role: str

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def verify_password_hash(password: str, stored_hash: str) -> bool:
    """Verify password — supports bcrypt and legacy SHA-256 with auto-migration."""
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash

def create_token(email: str, role: str = "user", *, extra: dict | None = None) -> str:
    import uuid as _uuid
    payload = {
        "email": email,
        "role": role,
        "jti": _uuid.uuid4().hex,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow()
    }
    if extra:
        # Allow callers to embed BIN context (business_id / plan /
        # services_unlocked) so BinContextMiddleware + service_gate can
        # gate routes without a per-request DB round-trip.
        for k in ("business_id", "plan", "services_unlocked", "user_id", "is_admin"):
            if k in extra and extra[k] is not None:
                payload[k] = extra[k]
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def verify_token_with_blocklist(token: str) -> dict:
    """Verify token AND check MongoDB blocklist (iter 322y — was external cache)."""
    payload = verify_token(token)
    jti = payload.get("jti")
    if jti:
        from services.jwt_blocklist import is_blocked
        if await is_blocked(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")
    return payload

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login to AUREM Platform — accepts email OR BIN as identifier.

    STRICT SEPARATION: This endpoint is for CLIENT (tenant) accounts only.
    Admin / super_admin accounts MUST use /api/auth/login — we reject them
    here even if the password matches, to eliminate privilege-escalation
    collision risk between the two user collections.
    """
    from services.bin_generator import is_bin, normalize_bin

    raw_identifier = (request.identifier or request.email or "").strip()
    if not raw_identifier:
        raise HTTPException(status_code=400, detail="Email or BIN is required")

    # Detect BIN vs email
    looked_up_email = None
    if is_bin(raw_identifier):
        bid = normalize_bin(raw_identifier)
        if db is not None:
            try:
                bin_user = await db.platform_users.find_one({"business_id": bid, "business_id_active": True})
                if not bin_user:
                    bin_user = await db.users.find_one({"business_id": bid, "business_id_active": True})
                if bin_user:
                    looked_up_email = (bin_user.get("email") or "").lower()
            except Exception as e:
                logger.warning(f"[PLATFORM AUTH] BIN lookup error: {e}")
        if not looked_up_email:
            raise HTTPException(status_code=401, detail="Invalid BIN or password")
        email = looked_up_email
    else:
        email = raw_identifier.lower()

    logger.info(f"[PLATFORM AUTH] Login attempt for: {email}")

    # iter 322bg — UNIFIED LOGIN. Admins, super-admins AND customers all log in
    # through this single endpoint so the ORA PWA & customer portal work for
    # every role. We try admin (db.users) first if the email exists there, then
    # fall through to client (db.platform_users). No more 403 collision walls.
    if db is not None:
        try:
            admin_row = await db.users.find_one(
                {"email": email},
                {"_id": 0, "email": 1, "password": 1, "password_hash": 1,
                 "is_admin": 1, "is_super_admin": 1, "role": 1,
                 "name": 1, "user_id": 1, "business_id": 1, "plan": 1,
                 "services_unlocked": 1},
            )
            if admin_row:
                stored = admin_row.get("password_hash") or admin_row.get("password") or ""
                # Also accept ADMIN_PASSWORD_HASH_1/2 from env for legacy
                # founder accounts that live in `users` without a stored hash.
                if not stored:
                    for slot in ("ADMIN_PASSWORD_HASH_1", "ADMIN_PASSWORD_HASH_2"):
                        cand = os.getenv(slot, "").replace("$$", "$")
                        if cand and verify_password_hash(request.password, cand):
                            stored = cand
                            break
                if stored and verify_password_hash(request.password, stored):
                    is_admin_flag = bool(
                        admin_row.get("is_admin")
                        or admin_row.get("is_super_admin")
                        or admin_row.get("role") in ("admin", "super_admin")
                    )
                    role_value = (
                        "super_admin" if admin_row.get("is_super_admin")
                        else ("admin" if is_admin_flag else (admin_row.get("role") or "user"))
                    )
                    token = create_token(
                        email, role_value,
                        extra={
                            "business_id": admin_row.get("business_id") or "",
                            "plan": admin_row.get("plan") or "founder",
                            "services_unlocked": admin_row.get("services_unlocked") or [],
                            "user_id": admin_row.get("user_id") or "admin",
                            "is_admin": is_admin_flag,
                        },
                    )
                    return TokenResponse(
                        token=token,
                        email=email,
                        full_name=admin_row.get("name") or "AUREM Admin",
                        company_name="AUREM Platform",
                        role=role_value,
                    )
        except Exception as e:
            logger.debug(f"[PLATFORM AUTH] unified admin check skipped: {e}")

    # Check in-memory admin users first (bcrypt from ENV)
    if email in ADMIN_USERS:
        user = ADMIN_USERS[email]
        if user.get("password_hash") and verify_password_hash(request.password, user["password_hash"]):
            token = create_token(email, user.get("role", "admin"))
            return TokenResponse(
                token=token,
                email=email,
                full_name=user["full_name"],
                company_name=user["company_name"],
                role=user.get("role", "admin")
            )

    # Check MongoDB if available
    if db is not None:
        try:
            user = await db.platform_users.find_one({"email": email})
            if user and verify_password_hash(request.password, user.get("password_hash", "")):
                user_role = (user.get("role") or "user").lower()
                # Auto-migrate SHA-256 to bcrypt on successful login
                if not user.get("password_hash", "").startswith("$2b$"):
                    new_hash = hash_password(request.password)
                    await db.platform_users.update_one(
                        {"email": email},
                        {"$set": {"password_hash": new_hash}}
                    )
                    logger.info(f"[PLATFORM AUTH] Migrated {email} password to bcrypt")
                token = create_token(
                    email, user_role,
                    extra={
                        "business_id": user.get("business_id") or "",
                        "plan": user.get("plan") or "trial",
                        "services_unlocked": user.get("services_unlocked") or [],
                        "user_id": user.get("user_id") or user.get("id") or "",
                        "is_admin": user_role in ("admin", "super_admin"),
                    },
                )
                return TokenResponse(
                    token=token,
                    email=email,
                    full_name=user.get("full_name", ""),
                    company_name=user.get("company_name", ""),
                    role=user_role
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"[AUTH] DB error: {e}")

    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, req: Request = None):
    """Register new AUREM Platform user. Requires terms acceptance."""
    if not request.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms of Service and Privacy Policy to continue.")

    email = request.email.lower()

    if email in ADMIN_USERS:
        raise HTTPException(status_code=400, detail="Email already registered")

    if db is not None:
        existing = await db.platform_users.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        client_ip = ""
        if req:
            client_ip = req.headers.get("x-forwarded-for", req.client.host if req.client else "")

        user_data = {
            "email": email,
            "password_hash": hash_password(request.password),
            "full_name": request.normalized_full_name(),
            "company_name": request.normalized_company(),
            "first_name": (request.first_name or "").strip(),
            "last_name": (request.last_name or "").strip(),
            "phone": (request.phone or "").strip(),
            "role": "user",
            "created_at": datetime.utcnow().isoformat(),
            "terms_accepted": True,
            "terms_version": "1.0",
            "terms_accepted_at": datetime.utcnow().isoformat(),
            "terms_accepted_ip": client_ip,
        }
        # iter 322bg — optional PIN at signup (4–6 digits, bcrypt-hashed)
        if request.pin:
            import re as _re_pin
            if not _re_pin.match(r"^\d{4,6}$", request.pin.strip()):
                raise HTTPException(status_code=400, detail="PIN must be 4–6 digits")
            user_data["pin_hash"] = bcrypt.hashpw(
                request.pin.strip().encode("utf-8"), bcrypt.gensalt(rounds=12)
            ).decode("utf-8")
            user_data["pin_set_at"] = datetime.utcnow().isoformat()
            user_data["pin_failed_count"] = 0
            user_data["pin_locked_until"] = None
        await db.platform_users.insert_one(user_data)

        # iter 322 — start 7-day trial via SSOT trial engine. This sets
        # plan, services_unlocked, usage_limits, trial_ends_at on the
        # platform_users row + aurem_billing.
        try:
            from routers.business_id_router import ensure_business_id
            from services.trial_engine import start_trial as _start_trial
            refreshed_user = await db.platform_users.find_one({"email": email}, {"_id": 0})
            if refreshed_user:
                await ensure_business_id(refreshed_user)
                refreshed_user = await db.platform_users.find_one({"email": email}, {"_id": 0}) or refreshed_user
                bin_id = (
                    refreshed_user.get("business_id")
                    or refreshed_user.get("tenant_id")
                    or refreshed_user.get("id")
                )
                if bin_id:
                    try:
                        await _start_trial(db, bin_id, email)
                    except Exception as _trial_err:
                        logger.warning(f"[signup] trial_engine.start_trial failed: {_trial_err}")
                # Trigger welcome package (async, non-blocking). First arg MUST be
                # the tenant_id (business_id) — passing email worked by accident
                # because user_doc is also supplied, but every record written
                # inside send_welcome_package uses that first arg as tenant_id.
                import asyncio
                from services.welcome_package import send_welcome_package
                tenant_id_for_welcome = (
                    refreshed_user.get("business_id")
                    or refreshed_user.get("tenant_id")
                    or refreshed_user.get("id")
                    or email
                )
                asyncio.get_event_loop().create_task(
                    send_welcome_package(tenant_id_for_welcome, refreshed_user)
                )
        except Exception as e:
            logging.getLogger(__name__).warning(f"[REGISTER] Business ID/Welcome error: {e}")

        # ═══ ITER 320 — tenant_customers + aurem_onboarding wire-up ═══
        # Fixes: earlier signup never wrote to tenant_customers OR aurem_onboarding,
        # leaving the Admin Mission Control counts at zero. Now every new signup
        # produces one record in each + queues the 10-min pixel reminder.
        try:
            final_user = await db.platform_users.find_one({"email": email}, {"_id": 0})
            tenant_id = (
                (final_user or {}).get("business_id")
                or (final_user or {}).get("tenant_id")
                or (final_user or {}).get("id")
                or email  # last-resort stable key
            )
            now_iso = datetime.utcnow().isoformat()
            now_dt = datetime.utcnow()

            # tenant_customers row (AUREM-as-tenant marker record)
            tc_doc = {
                "tenant_id": tenant_id,
                "business_id": (final_user or {}).get("business_id", ""),
                "business_name": request.normalized_company() or request.normalized_full_name() or email,
                "email": email,
                "plan": "trial",
                "status": "onboarding",
                "pixel_installed": False,
                "pixel_reminder_sent_at": None,
                "channels_enabled": [],
                "record_type": "aurem_tenant",   # distinguishes from CRM contacts
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            await db.tenant_customers.update_one(
                {"tenant_id": tenant_id, "record_type": "aurem_tenant"},
                {"$setOnInsert": tc_doc},
                upsert=True,
            )

            # aurem_onboarding seed (uses existing task schema from admin/seed-tenant)
            onb_doc = {
                "tenant_id": tenant_id,
                "email": email,
                "business_name": tc_doc["business_name"],
                "plan": "trial",
                "started_at": now_iso,
                "target_first_win": (now_dt + timedelta(days=7)).isoformat(),
                "tasks": [
                    {"key": "tenant_created", "label": "Account Created",
                     "status": "done", "completed_at": now_iso},
                    {"key": "install_pixel", "label": "Install AUREM Pixel",
                     "status": "required", "blocking": True, "eta_minutes": 2},
                    {"key": "google_scan", "label": "Google Business Scan",
                     "status": "queued", "eta_minutes": 10},
                    {"key": "website_draft", "label": "Free Website Draft",
                     "status": "queued", "eta_hours": 24},
                    {"key": "first_customer", "label": "First New Customer",
                     "status": "pending", "eta_days": 7},
                ],
                "domain": "",
                "pixel_installed": False,
                "ora_greeting_sent": False,
                "seeded_via": "signup",
            }
            await db.aurem_onboarding.update_one(
                {"tenant_id": tenant_id},
                {"$setOnInsert": onb_doc},
                upsert=True,
            )

            # ═══ ITER 322n — BILLING CUSTOMER WIRE-UP (P0 FUNNEL FIX) ═══
            # Without this, /api/aurem-billing/checkout returns "Business
            # not found in billing" → user can never reach Stripe → ZERO
            # paying customers despite signups completing. Creates:
            #   • aurem_workspaces row (with business_id)
            #   • Stripe Customer (live or test depending on env)
            #   • aurem_billing row in TRIALING state
            # All wrapped in a single try so a Stripe outage NEVER blocks
            # signup. Worst case: billing seed runs lazily on first
            # checkout call instead of at signup.
            try:
                from shared.commercial.billing_service import get_billing_service

                billing_svc = get_billing_service(db)

                # Use the SAME business_id that platform_users already has.
                # Do NOT call workspace_service.create_workspace — it always
                # generates a fresh ID (`biz_xxxx`) ignoring the one we
                # passed, which would orphan billing under a different ID
                # than platform_users.business_id → checkout 400.
                ws_business_id = (final_user or {}).get("business_id") or tenant_id

                # Ensure aurem_workspaces row exists with OUR business_id
                # (subscription state changes update this row by biz_id).
                from datetime import datetime as _dt, timezone as _tz
                _now = _dt.now(_tz.utc)
                await db.aurem_workspaces.update_one(
                    {"business_id": ws_business_id},
                    {"$setOnInsert": {
                        "business_id": ws_business_id,
                        "business_name": tc_doc["business_name"],
                        "owner_email": email,
                        "plan": "trial",
                        "status": "active",
                        "created_at": _now,
                        "updated_at": _now,
                    }},
                    upsert=True,
                )

                # Stripe customer + aurem_billing row keyed by OUR biz_id.
                # Idempotent — billing_service.create_customer checks for
                # existing record first.
                await billing_svc.create_customer(
                    business_id=ws_business_id,
                    email=email,
                    business_name=tc_doc["business_name"],
                    ip_address=client_ip,
                )
                logging.getLogger(__name__).info(
                    f"[REGISTER] billing seeded for {email} biz={ws_business_id}"
                )
            except Exception as _be:
                import traceback
                logging.getLogger(__name__).warning(
                    f"[REGISTER] billing seed deferred ({email}): {_be}\n"
                    f"{traceback.format_exc()[:500]}"
                )
        except Exception as _e:
            logging.getLogger(__name__).warning(f"[REGISTER] onboarding wire-up error: {_e}")

        token = create_token(email, "user")
        # iter 322ar — ORA universal learner hook (HOOK 8: signup)
        try:
            import asyncio as _asyncio
            from services.ora_universal_learner import ora_learn as _ora_learn
            _asyncio.create_task(_ora_learn({
                "source": "platform",
                "event": "CUSTOMER_SIGNUP",
                "category": "customer_action",
                "summary": (
                    f"New customer signed up. Plan: trial. "
                    f"Has company: {bool(request.normalized_company())}"
                ),
                "outcome": "signup",
                "agent": "platform_auth",
                "bin_id": locals().get("ws_business_id") or "system",
            }))
        except Exception:
            pass

        # ═══ ITER 322ca — AUTO-AUDIT on signup ═══════════════════════════
        # If the signup form captured a website URL, fire the SEO + Ads-Waste
        # audit in the background so the customer sees a populated dashboard
        # widget within ~60s of landing on /my. Sticky upsell hook for $49/mo.
        try:
            site_url = (
                (getattr(request, "website", None) or "").strip()
                or (getattr(request, "domain", None) or "").strip()
                or (getattr(request, "company_website", None) or "").strip()
            )
            if site_url and not site_url.startswith("http"):
                site_url = "https://" + site_url
            if site_url:
                import asyncio as _asyncio_audit
                from services.customer_audit_service import run_audit as _run_audit
                _asyncio_audit.create_task(_run_audit(
                    url=site_url,
                    customer_id=email,
                    bin=(locals().get("ws_business_id") or None),
                    db=db,
                ))
        except Exception:
            pass
        # ═══════════════════════════════════════════════════════════════

        return TokenResponse(
            token=token,
            email=email,
            full_name=request.normalized_full_name(),
            company_name=request.normalized_company(),
            role="user"
        )

    raise HTTPException(status_code=500, detail="Database not available")

@router.get("/verify")
async def verify_auth(token: str):
    """Verify JWT token is valid"""
    payload = verify_token(token)
    return {"valid": True, "email": payload.get("email"), "role": payload.get("role")}

@router.post("/logout")
async def logout(request: Request):
    """Logout — revoke JWT token via MongoDB blocklist (iter 322y)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"success": True, "message": "No token to revoke"}
    token = auth.split(" ", 1)[1]
    try:
        payload = verify_token(token)
        jti = payload.get("jti")
        if jti:
            from services.jwt_blocklist import block_token
            exp = payload.get("exp", 0)
            import time
            ttl = max(int(exp - time.time()), 60)
            await block_token(token, jti, ttl_seconds=ttl)
            return {"success": True, "message": "Token revoked"}
        return {"success": True, "message": "Token has no JTI (legacy token)"}
    except Exception:
        return {"success": True, "message": "Token already invalid"}


@router.post("/add-admin")
async def add_admin(email: str, password: str, full_name: str, master_key: str):
    """
    Add a new admin user (requires master key)
    Master key should be set as AUREM_MASTER_KEY environment variable
    """
    expected_key = os.environ.get("AUREM_MASTER_KEY", "aurem-master-2024")
    if master_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid master key")
    
    email = email.lower()
    if email in ADMIN_USERS:
        raise HTTPException(status_code=400, detail="Admin already exists")
    
    ADMIN_USERS[email] = {
        "password_hash": hash_password(password),
        "full_name": full_name,
        "company_name": "AUREM Platform",
        "role": "admin",
        "created_at": datetime.utcnow().isoformat()
    }
    
    return {"message": f"Admin {email} added successfully"}

@router.get("/health")
async def health():
    return {"status": "ok", "service": "platform-auth"}
