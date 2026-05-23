"""
routers/developer_portal_router.py — iter 331d

Tenant-facing + admin endpoints for the Developer Portal foundation:

Tenant:
  POST  /api/developers/signup
  POST  /api/developers/verify-otp
  POST  /api/developers/login
  GET   /api/developers/me
  POST  /api/developers/byok
  POST  /api/developers/pixel-domain
  POST  /api/developers/share/upload-request

Admin:
  GET   /api/admin/developers
  GET   /api/admin/shares
  POST  /api/admin/shares/{request_id}/approve
  POST  /api/admin/shares/{request_id}/reject

Portability: zero Emergent imports. Plain FastAPI + Pydantic.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(db):
    global _db
    _db = db
    try:
        from services import developer_portal_core as _D
        _D.set_db(db)
    except Exception:
        pass


def _client_ip(request: Request) -> str:
    ip = request.headers.get("x-forwarded-for", "") or request.client.host or ""
    return (ip.split(",")[0] or "0.0.0.0").strip()


def _hash_password(plain: str) -> str:
    """bcrypt-shaped fallback hash. The platform already has stronger
    auth elsewhere — this is the dev-portal specific hash."""
    try:
        import bcrypt
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    except Exception:
        # Last resort — never log this, never let it ship without bcrypt.
        salt = secrets.token_hex(16)
        return f"sha256${salt}${hashlib.sha256(f'{salt}{plain}'.encode()).hexdigest()}"


def _verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        import bcrypt
        if hashed.startswith("$2"):
            return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        pass
    if hashed.startswith("sha256$"):
        _, salt, want = hashed.split("$", 2)
        return hmac.compare_digest(
            want,
            hashlib.sha256(f"{salt}{plain}".encode()).hexdigest(),
        )
    return False


# ── Tenant: signup + OTP + login ───────────────────────────────────

class SignupBody(BaseModel):
    email: str
    name: str
    password: str = Field(min_length=8)
    github_username: str = ""
    build_intent: str = ""
    referral_code: str = ""


@router.post("/api/developers/signup")
async def signup(body: SignupBody, request: Request) -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.developer_portal_core import create_signup
    pw_hash = _hash_password(body.password)
    r = await create_signup(
        email=body.email,
        name=body.name,
        password_hash=pw_hash,
        github_username=body.github_username,
        build_intent=body.build_intent,
        referral_code=body.referral_code,
        ip=_client_ip(request),
    )
    if not r.get("ok"):
        raise HTTPException(400, r.get("message") or r.get("error") or "signup_failed")
    # Don't echo the password hash back
    r.pop("password_hash", None)
    return r


class OtpBody(BaseModel):
    email: str
    otp: str


@router.post("/api/developers/verify-otp")
async def verify_otp_route(body: OtpBody) -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.developer_portal_core import verify_otp
    r = await verify_otp(email=body.email, otp=body.otp)
    if not r.get("ok"):
        raise HTTPException(400, r.get("error") or "verify_failed")
    return r


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/api/developers/login")
async def login(body: LoginBody) -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db not ready")
    acc = await _db.developer_accounts.find_one(
        {"email": body.email.strip().lower()},
        {"_id": 0},
    )
    if not acc:
        raise HTTPException(401, "invalid_credentials")
    if not acc.get("email_verified"):
        raise HTTPException(403, "email_not_verified")
    if not _verify_password(body.password, acc.get("password_hash", "")):
        raise HTTPException(401, "invalid_credentials")
    if acc.get("abuse_flagged"):
        raise HTTPException(403, "account_under_review")
    from services.developer_portal_core import issue_jwt
    token = issue_jwt(acc["user_id"], acc["email"])
    return {
        "ok":               True,
        "user_id":          acc["user_id"],
        "email":            acc["email"],
        "tokens_remaining": acc.get("tokens_remaining", 0),
        "jwt":              token,
    }


async def _current_dev(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    token = authorization.split(" ", 1)[1]
    from services.developer_portal_core import decode_dev_jwt, get_account
    payload = decode_dev_jwt(token)
    if not payload or payload.get("kind") != "developer":
        raise HTTPException(401, "invalid_or_expired_token")
    acc = await get_account(payload["sub"])
    if not acc:
        raise HTTPException(401, "account_missing")
    if acc.get("abuse_flagged"):
        raise HTTPException(403, "account_under_review")
    return acc


@router.get("/api/developers/me")
async def me(authorization: str = Header(None)) -> dict[str, Any]:
    return await _current_dev(authorization)


# ── BYOK ───────────────────────────────────────────────────────────

class ByokBody(BaseModel):
    anthropic: str = ""
    deepseek:  str = ""
    gemini:    str = ""


@router.post("/api/developers/byok")
async def byok(body: ByokBody, authorization: str = Header(None)) -> dict[str, Any]:
    me = await _current_dev(authorization)
    from services.developer_portal_core import save_byok_keys
    r = await save_byok_keys(me["user_id"], body.model_dump())
    if not r.get("ok"):
        raise HTTPException(400, r.get("error") or "byok_failed")
    return r


# ── Pixel domain validation ────────────────────────────────────────

class PixelDomainBody(BaseModel):
    domain: str


@router.post("/api/developers/pixel-domain")
async def pixel_domain(
    body: PixelDomainBody,
    authorization: str = Header(None),
) -> dict[str, Any]:
    me = await _current_dev(authorization)
    from services.developer_portal_core import validate_pixel_domain
    v = validate_pixel_domain(body.domain)
    if not v["ok"]:
        raise HTTPException(400, v.get("message") or v.get("reason"))
    if _db is not None:
        await _db.developer_accounts.update_one(
            {"user_id": me["user_id"]},
            {"$set": {"pixel_domain": v["domain"]}},
        )
    return {"ok": True, "domain": v["domain"]}


# ── Screenshot share request ───────────────────────────────────────

class ShareUploadBody(BaseModel):
    screenshot_url: str
    platform: str = ""   # twitter | linkedin | other
    note: str = ""


@router.post("/api/developers/share/upload-request")
async def share_upload(
    body: ShareUploadBody,
    authorization: str = Header(None),
) -> dict[str, Any]:
    me = await _current_dev(authorization)
    if not body.screenshot_url or not body.screenshot_url.startswith("http"):
        raise HTTPException(400, "screenshot_url must be a public URL")
    if _db is None:
        raise HTTPException(503, "db not ready")
    import uuid as _uuid
    req_id = _uuid.uuid4().hex[:16]
    await _db.developer_share_requests.insert_one({
        "request_id":     req_id,
        "user_id":        me["user_id"],
        "screenshot_url": body.screenshot_url,
        "platform":       body.platform or "other",
        "note":           body.note[:500] if body.note else "",
        "status":         "pending",
        "submitted_at":   datetime.now(timezone.utc).isoformat(),
        "reviewed_at":    None,
        "tokens_awarded": 0,
    })
    return {
        "ok":         True,
        "request_id": req_id,
        "status":     "pending",
        "message":    "Submitted for review. We'll add 2500 tokens within 24 hours of approval.",
    }


# ── Admin endpoints ────────────────────────────────────────────────

def _ensure_admin(request: Request) -> None:
    try:
        from routers.admin_ora_router import _ensure_admin as _outer
        return _outer(request)
    except Exception as e:
        raise HTTPException(503, f"admin gate unavailable: {e}")


@router.get("/api/admin/developers")
async def admin_developers_list(
    request: Request, limit: int = 50,
) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    cursor = _db.developer_accounts.find(
        {},
        {"_id": 0, "password_hash": 0, "byok_keys": 0,
         "signup_ip": 0},
        sort=[("created_at", -1)],
        limit=max(1, min(int(limit), 500)),
    )
    rows = await cursor.to_list(length=500)
    flagged = await _db.developer_accounts.count_documents({"abuse_flagged": True})
    total = await _db.developer_accounts.estimated_document_count()
    return {"ok": True, "total": total, "flagged": flagged, "rows": rows}


@router.get("/api/admin/shares")
async def admin_shares_list(
    request: Request, status: str = "pending",
) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    cursor = _db.developer_share_requests.find(
        {"status": status},
        {"_id": 0},
        sort=[("submitted_at", -1)],
        limit=200,
    )
    rows = await cursor.to_list(length=200)
    return {"ok": True, "status": status, "count": len(rows), "rows": rows}


@router.post("/api/admin/shares/{request_id}/approve")
async def admin_share_approve(request_id: str, request: Request) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    req = await _db.developer_share_requests.find_one(
        {"request_id": request_id}, {"_id": 0},
    )
    if not req:
        raise HTTPException(404, "share_request_not_found")
    if req.get("status") != "pending":
        raise HTTPException(400, f"already_{req['status']}")
    from services.developer_portal_core import SHARE_REWARD_TOKENS
    # Award tokens
    await _db.developer_accounts.update_one(
        {"user_id": req["user_id"]},
        {"$inc": {"tokens_remaining": SHARE_REWARD_TOKENS}},
    )
    await _db.developer_share_requests.update_one(
        {"request_id": request_id},
        {"$set": {"status": "approved",
                   "reviewed_at": datetime.now(timezone.utc).isoformat(),
                   "tokens_awarded": SHARE_REWARD_TOKENS}},
    )
    return {"ok": True, "request_id": request_id,
             "tokens_awarded": SHARE_REWARD_TOKENS}


@router.post("/api/admin/shares/{request_id}/reject")
async def admin_share_reject(
    request_id: str,
    request: Request,
    reason: str = "",
) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    r = await _db.developer_share_requests.update_one(
        {"request_id": request_id, "status": "pending"},
        {"$set": {"status": "rejected",
                   "reviewed_at": datetime.now(timezone.utc).isoformat(),
                   "rejection_reason": (reason or "")[:200]}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "share_request_not_pending")
    return {"ok": True, "request_id": request_id, "status": "rejected"}
