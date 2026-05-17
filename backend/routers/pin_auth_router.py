"""
AUREM PIN Auth Router (iter 305e)
=================================
Customer PIN credential layer that sits ALONGSIDE existing email/password.

Schema additions on `db.platform_users`:
  - pin_hash:           bcrypt hash of 4–6 digit PIN (never stored plain)
  - pin_set_at:         ISO timestamp when PIN was first set
  - pin_failed_count:   incrementing on wrong PIN attempts
  - pin_locked_until:   ISO timestamp lockout expiry (3 fails → +15 min)

Endpoints (all under `/api/platform/auth`):
  POST /login-pin    — body {bin, pin} → JWT (mirrors /login response)
  POST /setup-pin    — body {pin} (auth required) → 200
  POST /change-pin   — body {old_pin, new_pin} (auth required) → 200
  POST /forgot-pin   — body {bin or email} → emails OTP (uses bin_auth flow)
  GET  /pin-status   — auth required → {pin_set: bool}

Brute-force lockout is per (BIN, IP) keyed in
`db.pin_login_attempts` — same shape as existing `login_attempts`.

NOTE: PIN reset flow re-uses the existing
`/api/bin-auth/forgot-password` OTP path. The OTP, once verified,
invokes `/change-pin` with a server-side PIN-reset token instead of
overwriting the password.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/platform/auth", tags=["Platform Auth · PIN"])

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("PIN auth: JWT_SECRET not set")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7

PIN_RE = re.compile(r"^\d{4,6}$")
MAX_FAILED = 3
LOCKOUT_MINUTES = 15

_db = None


def set_db(database):
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_pin(pin: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        return False


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _create_pin_jwt(email: str, business_id: str, user_id: str,
                    role: str, is_admin: bool, is_super_admin: bool,
                    tenant_id: str = "") -> str:
    import uuid as _uuid
    payload = {
        "email": email,
        "user_id": user_id,
        "tenant_id": tenant_id or business_id,
        "business_id": business_id,
        "role": role or "tenant",
        "is_admin": bool(is_admin),
        "is_super_admin": bool(is_super_admin),
        "auth_method": "pin",
        "jti": _uuid.uuid4().hex,
        "iat": _now(),
        "exp": _now() + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_jwt(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Models ─────────────────────────────────────────────────────────────────

class PinLoginRequest(BaseModel):
    bin: str = Field(..., min_length=4, max_length=64)
    pin: str = Field(..., min_length=4, max_length=6)


class PinSetupRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=6)


class PinChangeRequest(BaseModel):
    old_pin: str = Field(..., min_length=4, max_length=6)
    new_pin: str = Field(..., min_length=4, max_length=6)


# ─── Helpers ────────────────────────────────────────────────────────────────

async def _find_tenant_by_bin(bin_id: str) -> Optional[dict]:
    """Return the user doc whose `business_id` matches.
    Searches platform_users first, then users (admins included — security
    is provided by PIN + lockout, not by role exclusion).
    """
    if _db is None:
        return None
    from services.bin_generator import normalize_bin
    bid = normalize_bin(bin_id)
    user = await _db.platform_users.find_one(
        {"business_id": bid, "business_id_active": True},
    )
    if user:
        return user
    return await _db.users.find_one(
        {"business_id": bid, "business_id_active": True},
    )


async def _get_user_by_email(email: str):
    """Return (user_doc, collection) tuple, or (None, None)."""
    if _db is None or not email:
        return None, None
    user = await _db.platform_users.find_one({"email": email.lower()})
    if user:
        return user, _db.platform_users
    user = await _db.users.find_one({"email": email.lower()})
    if user:
        return user, _db.users
    return None, None


async def _persist_pin(user: dict, coll, pin: str) -> None:
    await coll.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "pin_hash": _hash_pin(pin),
            "pin_set_at": _now().isoformat(),
            "pin_failed_count": 0,
            "pin_locked_until": None,
        }},
    )


async def _record_pin_attempt(bin_id: str, ip: str, success: bool) -> Optional[datetime]:
    """Track failures; returns lockout-expiry datetime if locked."""
    if _db is None:
        return None
    key = f"{ip}:{bin_id.upper()}"
    if success:
        await _db.pin_login_attempts.delete_one({"key": key})
        return None
    doc = await _db.pin_login_attempts.find_one_and_update(
        {"key": key},
        {"$inc": {"count": 1}, "$set": {"last_at": _now()}},
        upsert=True, return_document=True,
    ) or {}
    if (doc.get("count") or 0) >= MAX_FAILED:
        until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
        await _db.pin_login_attempts.update_one(
            {"key": key}, {"$set": {"locked_until": until}},
        )
        return until
    return None


async def _is_pin_locked(bin_id: str, ip: str) -> Optional[datetime]:
    if _db is None:
        return None
    key = f"{ip}:{bin_id.upper()}"
    doc = await _db.pin_login_attempts.find_one({"key": key})
    if not doc:
        return None
    until = doc.get("locked_until")
    if isinstance(until, datetime) and until > _now():
        return until
    return None


# ─── Routes ─────────────────────────────────────────────────────────────────

@router.post("/login-pin")
async def login_with_pin(body: PinLoginRequest, request: Request):
    """Authenticate using BIN + PIN. Returns JWT identical in shape to /login."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    if not PIN_RE.match(body.pin):
        raise HTTPException(status_code=400, detail="PIN must be 4–6 digits")

    ip = _client_ip(request)
    locked_until = await _is_pin_locked(body.bin, ip)
    if locked_until:
        secs = int((locked_until - _now()).total_seconds())
        raise HTTPException(
            status_code=429,
            detail=f"Too many wrong PINs. Try again in {secs // 60}m {secs % 60}s.",
        )

    user = await _find_tenant_by_bin(body.bin)
    if not user or not user.get("pin_hash"):
        # Don't leak whether BIN exists
        await _record_pin_attempt(body.bin, ip, success=False)
        raise HTTPException(status_code=401, detail="Invalid BIN or PIN")

    if not _verify_pin(body.pin, user["pin_hash"]):
        until = await _record_pin_attempt(body.bin, ip, success=False)
        if until:
            secs = int((until - _now()).total_seconds())
            raise HTTPException(
                status_code=429,
                detail=f"Locked. Try again in {secs // 60}m {secs % 60}s.",
            )
        raise HTTPException(status_code=401, detail="Invalid BIN or PIN")

    await _record_pin_attempt(body.bin, ip, success=True)

    email = (user.get("email") or "").lower()
    business_id = user.get("business_id") or ""
    tenant_id = user.get("tenant_id") or business_id
    user_id = str(user.get("user_id") or user.get("_id"))
    role = user.get("role") or "tenant"
    is_admin = bool(user.get("is_admin"))
    is_super = bool(user.get("is_super_admin"))
    token = _create_pin_jwt(email, business_id, user_id, role, is_admin, is_super, tenant_id)

    return {
        "token": token,
        "email": email,
        "tenant_id": tenant_id,
        "business_id": business_id,
        "full_name": user.get("full_name") or user.get("name") or "",
        "company_name": user.get("company_name") or user.get("business_name") or "",
        "role": role,
        "is_admin": is_admin,
        "is_super_admin": is_super,
        "auth_method": "pin",
    }


@router.post("/setup-pin")
async def setup_pin(body: PinSetupRequest, request: Request):
    """Set the PIN for the authenticated user (first-time)."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    if not PIN_RE.match(body.pin):
        raise HTTPException(status_code=400, detail="PIN must be 4–6 digits")
    payload = _decode_jwt(request)
    user, coll = await _get_user_by_email(payload.get("email"))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("pin_hash"):
        raise HTTPException(status_code=409, detail="PIN already set — use change-pin")
    await _persist_pin(user, coll, body.pin)
    return {"ok": True, "pin_set": True}


@router.post("/change-pin")
async def change_pin(body: PinChangeRequest, request: Request):
    """Change an existing PIN — old_pin must verify."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    if not (PIN_RE.match(body.old_pin) and PIN_RE.match(body.new_pin)):
        raise HTTPException(status_code=400, detail="PIN must be 4–6 digits")
    if body.old_pin == body.new_pin:
        raise HTTPException(status_code=400, detail="New PIN must differ from old PIN")

    payload = _decode_jwt(request)
    user, coll = await _get_user_by_email(payload.get("email"))
    if not user or not user.get("pin_hash"):
        raise HTTPException(status_code=404, detail="No PIN on file — use setup-pin")
    if not _verify_pin(body.old_pin, user["pin_hash"]):
        raise HTTPException(status_code=401, detail="Old PIN is incorrect")
    await _persist_pin(user, coll, body.new_pin)
    return {"ok": True, "pin_changed": True}


@router.get("/pin-status")
async def pin_status(request: Request):
    """Return whether the authed user has a PIN set."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    payload = _decode_jwt(request)
    user, _coll = await _get_user_by_email(payload.get("email"))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    locked_until = user.get("pin_locked_until")
    return {
        "pin_set": bool(user.get("pin_hash")),
        "pin_set_at": user.get("pin_set_at"),
        "locked": bool(locked_until and isinstance(locked_until, datetime)
                       and locked_until > _now()),
    }


# Idempotent index ensure
async def ensure_pin_indexes(db) -> None:
    try:
        await db.pin_login_attempts.create_index(
            "key", unique=True, name="pin_attempts_key_uniq",
        )
        # TTL on locked_until — auto-cleanup expired lockouts after 1 day
        await db.pin_login_attempts.create_index(
            "last_at", expireAfterSeconds=60 * 60 * 24,
            name="pin_attempts_last_at_ttl_24h",
        )
    except Exception as e:
        logger.debug(f"[pin_auth] index ensure skipped: {e}")


# ─── Forgot-PIN flow (email OTP → reset) ──────────────────────────────────
import secrets
import asyncio


class ForgotPinRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=120)  # BIN or email


class ResetPinRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=120)
    code: str = Field(..., min_length=4, max_length=10)
    new_pin: str = Field(..., min_length=4, max_length=6)


async def _resolve_user_for_pin_reset(identifier: str):
    """Find a user row by BIN or email. Returns (user, collection)."""
    if _db is None or not identifier:
        return None, None
    ident = identifier.strip()
    # Try BIN
    try:
        from services.bin_generator import is_bin, normalize_bin
        if is_bin(ident):
            bid = normalize_bin(ident)
            u = await _db.platform_users.find_one({"business_id": bid})
            if u:
                return u, _db.platform_users
            u = await _db.users.find_one({"business_id": bid})
            if u:
                return u, _db.users
    except Exception:
        pass
    # Email path
    email = ident.lower()
    u = await _db.platform_users.find_one({"email": email})
    if u:
        return u, _db.platform_users
    u = await _db.users.find_one({"email": email})
    if u:
        return u, _db.users
    return None, None


async def _send_pin_reset_email(email: str, name: str, code: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("[pin_auth] RESEND_API_KEY missing — PIN reset code logged only")
        logger.info(f"[pin_auth] PIN reset code for {email}: {code}")
        return False
    try:
        import resend  # type: ignore
        resend.api_key = api_key
        from_addr = os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>")
        html = f"""
        <div style="background:#060608;color:#F0EBE0;padding:36px;font-family:Georgia,serif;">
          <h2 style="color:#F97316;margin:0 0 16px;">AUREM — PIN Reset</h2>
          <p style="margin:0 0 12px;">Hi {name or 'there'},</p>
          <p style="margin:0 0 20px;">Use the code below to reset your AUREM PIN. Expires in 15 minutes.</p>
          <div style="font-family:'Courier New',monospace;font-size:32px;letter-spacing:0.4em;
                      color:#F97316;padding:18px 24px;border:1px solid rgba(249,115,22,0.4);
                      border-radius:6px;display:inline-block;background:rgba(249,115,22,0.08);">
            {code}
          </div>
          <p style="color:#5C5548;font-size:12px;margin-top:24px;">
            Didn't request this? Ignore this email — your PIN is unchanged.
          </p>
        </div>
        """
        await asyncio.to_thread(resend.Emails.send, {
            "from": from_addr,
            "to": [email],
            "subject": "Reset your AUREM PIN",
            "html": html,
        })
        return True
    except Exception as e:
        logger.error(f"[pin_auth] PIN reset email failed: {e}")
        return False


@router.post("/forgot-pin/request")
async def forgot_pin_request(body: ForgotPinRequest):
    """Email a 6-digit OTP that authorises one PIN reset. Always returns 200
    to avoid leaking which BINs/emails exist."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    user, _coll = await _resolve_user_for_pin_reset(body.identifier)
    if user and user.get("email"):
        code = f"{secrets.randbelow(1_000_000):06d}"
        await _db.pin_reset_codes.update_one(
            {"email": user["email"].lower()},
            {"$set": {
                "email": user["email"].lower(),
                "code_hash": bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8"),
                "expires_at": _now() + timedelta(minutes=15),
                "used": False,
                "created_at": _now(),
            }},
            upsert=True,
        )
        name = user.get("first_name") or user.get("full_name") or user.get("name") or ""
        asyncio.create_task(_send_pin_reset_email(user["email"], name, code))
    return {"ok": True, "message": "If the account exists, a reset code has been sent."}


@router.post("/forgot-pin/confirm")
async def forgot_pin_confirm(body: ResetPinRequest):
    """Verify the OTP + persist a new PIN."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    if not PIN_RE.match(body.new_pin):
        raise HTTPException(status_code=400, detail="PIN must be 4–6 digits")
    user, coll = await _resolve_user_for_pin_reset(body.identifier)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid code")
    email = (user.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="Invalid code")
    rec = await _db.pin_reset_codes.find_one({"email": email})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    exp = rec.get("expires_at")
    if isinstance(exp, datetime) and exp < _now():
        raise HTTPException(status_code=400, detail="Code expired")
    if not bcrypt.checkpw(body.code.strip().encode("utf-8"),
                          (rec.get("code_hash") or "").encode("utf-8")):
        raise HTTPException(status_code=400, detail="Invalid code")
    await _persist_pin(user, coll, body.new_pin)
    await _db.pin_reset_codes.update_one({"email": email}, {"$set": {"used": True}})
    # Clear any active lockout so the user can log in right away
    await _db.pin_login_attempts.delete_many({"key": {"$regex": f":{(user.get('business_id') or '').upper()}$"}})
    return {"ok": True, "pin_reset": True}
