"""
BIN Auth Router — First-Login Flow, WhatsApp OTP Password Reset, Admin Search
==============================================================================
Works alongside platform_auth_router.py (which handles BIN-or-Email login).

Endpoints:
    POST /api/bin-auth/first-login/set-password   -- User sets their real password
    GET  /api/bin-auth/first-login/status          -- Check if wizard needed
    POST /api/bin-auth/first-login/complete         -- Mark 4-step wizard done
    POST /api/bin-auth/forgot-password              -- Send OTP via WhatsApp (+ SMS fallback)
    POST /api/bin-auth/verify-otp                   -- Verify OTP, return reset token
    POST /api/bin-auth/reset-password               -- Use reset token to set new password
    GET  /api/bin-auth/admin/search                 -- Admin-only BIN search
"""

import os
import re
import time
import random
import string
import logging
import secrets
import hashlib
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bin-auth", tags=["BIN Auth"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")
JWT_ALGORITHM = "HS256"

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(503, "Database not available")
    return _db


def _hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_password(pw: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        try:
            return bcrypt.checkpw(pw.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    return hashlib.sha256(pw.encode()).hexdigest() == stored


def _decode_jwt(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    try:
        return jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


async def _find_user_by_identifier(db, identifier: str) -> Optional[dict]:
    """Locate user by BIN or email. Returns (user, collection_name)."""
    from services.bin_generator import is_bin, normalize_bin

    ident = (identifier or "").strip()
    if not ident:
        return None

    if is_bin(ident):
        bid = normalize_bin(ident)
        u = await db.platform_users.find_one({"business_id": bid})
        if u:
            return {**u, "_collection": "platform_users"}
        u = await db.users.find_one({"business_id": bid})
        if u:
            return {**u, "_collection": "users"}
        return None

    email = ident.lower()
    u = await db.platform_users.find_one({"email": email})
    if u:
        return {**u, "_collection": "platform_users"}
    u = await db.users.find_one({"email": email})
    if u:
        return {**u, "_collection": "users"}
    return None


async def _update_user(db, user: dict, update: dict):
    coll = user.get("_collection", "platform_users")
    await db[coll].update_one({"email": user["email"]}, update)


# ═══════════════════════════════════════════════════════════════
# FIRST-LOGIN FLOW (force password set + 4-step wizard)
# ═══════════════════════════════════════════════════════════════

class SetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


@router.get("/first-login/status")
async def first_login_status(request: Request):
    """Returns must_set_password + onboarding_wizard_complete flags."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = (payload.get("email") or payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(401, "Invalid token")

    user = await db.platform_users.find_one({"email": email}, {"_id": 0}) \
        or await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    return {
        "must_set_password": bool(user.get("must_set_password", False)),
        "wizard_complete": bool(user.get("onboarding_wizard_complete", False)),
        "wizard_step": int(user.get("onboarding_wizard_step", 0)),
        "business_id": user.get("business_id", ""),
    }


@router.post("/first-login/set-password")
async def first_login_set_password(body: SetPasswordRequest, request: Request):
    """Replace temp password with user's real password. Clears must_set_password flag."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = (payload.get("email") or payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(401, "Invalid token")

    user = await _find_user_by_identifier(db, email)
    if not user:
        raise HTTPException(404, "User not found")

    new_hash = _hash_password(body.new_password)
    await _update_user(db, user, {"$set": {
        "password_hash": new_hash,
        "must_set_password": False,
        "password_set_at": datetime.now(timezone.utc).isoformat(),
    }})
    # Invalidate cached customer-context for this email
    try:
        from services.aurem_cache import cache_delete
        await cache_delete(f"ctx:{email}")
    except Exception:
        pass
    logger.info(f"[BIN-AUTH] Password set for {email}")
    return {"success": True}


class WizardStepRequest(BaseModel):
    step: int = Field(ge=0, le=4)
    data: Optional[dict] = None


@router.post("/first-login/wizard")
async def first_login_wizard(body: WizardStepRequest, request: Request):
    """Save wizard progress. step=4 marks complete."""
    payload = _decode_jwt(request)
    db = _get_db()
    email = (payload.get("email") or payload.get("sub") or "").lower()
    user = await _find_user_by_identifier(db, email)
    if not user:
        raise HTTPException(404, "User not found")

    update_set = {
        "onboarding_wizard_step": body.step,
        "onboarding_wizard_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if body.data:
        # Only allow whitelisted wizard fields
        allowed = {"business_name", "industry", "city", "phone", "website", "services",
                   "tone", "goals", "notification_prefs"}
        for k, v in (body.data or {}).items():
            if k in allowed:
                update_set[f"wizard.{k}"] = v
    if body.step >= 4:
        update_set["onboarding_wizard_complete"] = True
        update_set["onboarding_wizard_completed_at"] = datetime.now(timezone.utc).isoformat()

    await _update_user(db, user, {"$set": update_set})
    # Invalidate cached customer-context — user just changed state
    try:
        from services.aurem_cache import cache_delete
        await cache_delete(f"ctx:{email}")
    except Exception:
        pass
    return {"success": True, "step": body.step, "complete": body.step >= 4}


# ═══════════════════════════════════════════════════════════════
# WHATSAPP OTP PASSWORD RESET  (+ Twilio SMS fallback)
# ═══════════════════════════════════════════════════════════════

class ForgotPasswordRequest(BaseModel):
    identifier: str  # BIN or email


class VerifyOtpRequest(BaseModel):
    identifier: str
    otp: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)


# Redis-backed OTP store (falls back to in-memory for dev)
_OTP_MEMORY = {}


async def _otp_store_set(key: str, value: dict, ttl_seconds: int = 600):
    try:
        from utils.redis_pool import get_redis
        r = await get_redis()
        if r:
            import json as _json
            await r.setex(key, ttl_seconds, _json.dumps(value))
            return
    except Exception as e:
        logger.debug(f"[BIN-AUTH] Redis unavailable, using memory store: {e}")
    _OTP_MEMORY[key] = {**value, "_expires": time.time() + ttl_seconds}


async def _otp_store_get(key: str) -> Optional[dict]:
    try:
        from utils.redis_pool import get_redis
        r = await get_redis()
        if r:
            import json as _json
            v = await r.get(key)
            return _json.loads(v) if v else None
    except Exception:
        pass
    rec = _OTP_MEMORY.get(key)
    if not rec:
        return None
    if rec.get("_expires", 0) < time.time():
        _OTP_MEMORY.pop(key, None)
        return None
    return {k: v for k, v in rec.items() if k != "_expires"}


async def _otp_store_del(key: str):
    try:
        from utils.redis_pool import get_redis
        r = await get_redis()
        if r:
            await r.delete(key)
            return
    except Exception:
        pass
    _OTP_MEMORY.pop(key, None)


async def _send_whatsapp_otp(phone: str, otp: str, business_name: str = "") -> bool:
    """Send OTP via WHAPI. Returns True on success."""
    if not phone:
        return False
    try:
        from routers.whatsapp_alerts import send_whatsapp
        msg = (f"🔐 AUREM Password Reset\n\n"
               f"Your one-time code: *{otp}*\n"
               f"Valid for 10 minutes.\n\n"
               f"If you didn't request this, ignore this message.\n"
               f"— AUREM Security")
        result = await send_whatsapp(phone, msg)
        return bool(result)
    except Exception as e:
        logger.warning(f"[BIN-AUTH] WhatsApp OTP failed: {e}")
        return False


async def _send_sms_otp(phone: str, otp: str) -> bool:
    """Fallback: Send OTP via Twilio SMS."""
    if not phone:
        return False
    try:
        from services.twilio_service import send_sms  # type: ignore
        msg = f"AUREM: Your password reset code is {otp}. Valid for 10 min."
        result = await send_sms(phone, msg)
        return bool(result)
    except Exception as e:
        logger.warning(f"[BIN-AUTH] SMS OTP failed: {e}")
        return False


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, request: Request):
    """Send OTP via WhatsApp (primary) + SMS (fallback) to user's phone."""
    db = _get_db()
    user = await _find_user_by_identifier(db, body.identifier)
    if not user:
        # Don't leak whether user exists
        return {"success": True, "message": "If that account exists, a code has been sent."}

    phone = (user.get("phone") or user.get("whatsapp") or user.get("business_phone") or "").strip()
    if not phone:
        raise HTTPException(400, "No phone number on file. Contact support to reset.")

    # Rate limit: max 3 OTP requests per 10 min per user
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    rl_key = f"bin_otp_rl:{user['email']}"
    try:
        from utils.redis_pool import get_redis
        r = await get_redis()
        if r:
            cnt = await r.incr(rl_key)
            if cnt == 1:
                await r.expire(rl_key, 600)
            if cnt > 3:
                raise HTTPException(429, "Too many reset requests. Try again in 10 minutes.")
    except HTTPException:
        raise
    except Exception:
        pass  # Redis down — skip rate limit

    # Security: use `secrets` (CSPRNG) not `random` for OTP generation
    otp = "".join(secrets.choice(string.digits) for _ in range(6))
    business_name = user.get("company_name") or user.get("business_name") or ""

    otp_key = f"bin_otp:{user['email']}"
    await _otp_store_set(otp_key, {
        "otp_hash": hashlib.sha256(otp.encode()).hexdigest(),
        "email": user["email"],
        "created_at": int(time.time()),
        "attempts": 0,
        "ip": ip,
    }, ttl_seconds=600)

    wa_ok = await _send_whatsapp_otp(phone, otp, business_name)
    sms_ok = False
    if not wa_ok:
        sms_ok = await _send_sms_otp(phone, otp)

    if not wa_ok and not sms_ok:
        # Still return success to avoid leaking; log it
        logger.error(f"[BIN-AUTH] OTP delivery failed for {user['email']} (phone={phone[:6]}...)")
        raise HTTPException(502, "Unable to send reset code. Please try again or contact support.")

    return {
        "success": True,
        "message": "Reset code sent.",
        "channel": "whatsapp" if wa_ok else "sms",
        # Masked phone hint
        "phone_hint": f"{phone[:3]}•••{phone[-2:]}" if len(phone) > 5 else "•••",
    }


@router.post("/verify-otp")
async def verify_otp(body: VerifyOtpRequest):
    """Verify OTP, return a short-lived reset token."""
    db = _get_db()
    user = await _find_user_by_identifier(db, body.identifier)
    if not user:
        raise HTTPException(400, "Invalid code")

    otp_key = f"bin_otp:{user['email']}"
    rec = await _otp_store_get(otp_key)
    if not rec:
        raise HTTPException(400, "Code expired or not found. Request a new one.")

    # Attempt limiting
    attempts = int(rec.get("attempts", 0)) + 1
    if attempts > 5:
        await _otp_store_del(otp_key)
        raise HTTPException(429, "Too many attempts. Request a new code.")
    rec["attempts"] = attempts
    await _otp_store_set(otp_key, rec, ttl_seconds=600)

    if hashlib.sha256(body.otp.strip().encode()).hexdigest() != rec.get("otp_hash"):
        raise HTTPException(400, "Invalid code")

    # Issue short-lived reset token (15 min)
    reset_token = jwt.encode(
        {
            "purpose": "password_reset",
            "email": user["email"],
            "jti": secrets.token_urlsafe(12),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(timezone.utc),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    await _otp_store_del(otp_key)
    return {"success": True, "reset_token": reset_token}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    """Use reset token to set new password."""
    db = _get_db()
    try:
        payload = jwt.decode(body.reset_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Reset token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid reset token")

    if payload.get("purpose") != "password_reset":
        raise HTTPException(400, "Invalid reset token")

    email = (payload.get("email") or "").lower()
    user = await _find_user_by_identifier(db, email)
    if not user:
        raise HTTPException(404, "User not found")

    new_hash = _hash_password(body.new_password)
    await _update_user(db, user, {"$set": {
        "password_hash": new_hash,
        "must_set_password": False,
        "password_reset_at": datetime.now(timezone.utc).isoformat(),
    }})
    logger.info(f"[BIN-AUTH] Password reset for {email}")
    return {"success": True}


# ═══════════════════════════════════════════════════════════════
# ADMIN BIN SEARCH
# ═══════════════════════════════════════════════════════════════

def _require_admin(payload: dict):
    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin access required")


@router.get("/admin/search")
async def admin_search_bin(
    request: Request,
    q: str = Query(..., min_length=2, description="BIN, email, or business name fragment"),
    limit: int = Query(20, ge=1, le=100),
):
    """Admin-only: Search users by BIN, email, or business name."""
    payload = _decode_jwt(request)
    _require_admin(payload)

    db = _get_db()
    from services.bin_generator import is_bin, normalize_bin

    term = q.strip()
    or_query = []

    if is_bin(term):
        or_query.append({"business_id": normalize_bin(term)})
    or_query.extend([
        {"email": {"$regex": re.escape(term), "$options": "i"}},
        {"business_id": {"$regex": re.escape(term), "$options": "i"}},
        {"company_name": {"$regex": re.escape(term), "$options": "i"}},
        {"full_name": {"$regex": re.escape(term), "$options": "i"}},
    ])
    query = {"$or": or_query}

    projection = {
        "_id": 0,
        "email": 1, "business_id": 1, "company_name": 1, "full_name": 1,
        "role": 1, "created_at": 1, "business_id_active": 1,
        "must_set_password": 1, "onboarding_wizard_complete": 1,
        "plan_status": 1, "stripe_customer_id": 1, "phone": 1,
    }

    results = []
    seen_emails = set()
    for coll_name in ("platform_users", "users"):
        cursor = db[coll_name].find(query, projection).limit(limit)
        async for doc in cursor:
            em = (doc.get("email") or "").lower()
            if em in seen_emails:
                continue
            seen_emails.add(em)
            doc["_source"] = coll_name
            results.append(doc)
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break

    return {"query": q, "count": len(results), "results": results[:limit]}


# ═══════════════════════════════════════════════════════════════
# CUSTOMER CONTEXT (for ORA)
# ═══════════════════════════════════════════════════════════════

@router.get("/customer-context")
async def customer_context(request: Request):
    """Returns the logged-in customer's context so ORA can personalize responses.
    Does NOT include admin metadata.

    Iter 206 — cache-through (60s TTL). Mutations (set-password, smart-onboarding
    complete) invalidate via `aurem_cache.cache_delete`.
    """
    payload = _decode_jwt(request)
    db = _get_db()
    email = (payload.get("email") or payload.get("sub") or "").lower()

    # Fast path — 60-second cache
    try:
        from services.aurem_cache import cache_get, cache_set
        cached = await cache_get(f"ctx:{email}")
        if cached is not None:
            return cached
    except Exception:
        cache_get = None  # noqa — cache layer unavailable

    user = await _find_user_by_identifier(db, email)
    if not user:
        raise HTTPException(404, "User not found")

    # Load workspace
    ws = await db.aurem_workspaces.find_one({"owner_email": email}, {"_id": 0}) or {}

    result = {
        "bin": user.get("business_id", ""),
        "email": user.get("email", ""),
        "full_name": user.get("full_name", ""),
        "business_name": user.get("company_name") or ws.get("business_name", ""),
        "industry": user.get("industry") or ws.get("industry", ""),
        "city": user.get("city") or ws.get("city", ""),
        "website": ws.get("website", ""),
        "plan": user.get("plan_status") or "trial",
        "must_set_password": bool(user.get("must_set_password", False)),
        "wizard_complete": bool(user.get("onboarding_wizard_complete", False)),
        "smart_onboarding_complete": bool(user.get("smart_onboarding_complete", False)),
        "role": user.get("role", "user"),
    }

    try:
        from services.aurem_cache import cache_set
        await cache_set(f"ctx:{email}", result, 60)   # 60-second TTL
    except Exception:
        pass  # silent — cache is a best-effort optimization
    return result
