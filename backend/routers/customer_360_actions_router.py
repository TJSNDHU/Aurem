"""
Customer 360 Action Panel — Iteration 209
==========================================
Admin-only dangerous actions against a single customer, all routed through
one router so every action is audit-logged centrally.

All endpoints under /api/admin/customer-360/{identifier}/actions/*

  POST /reset-password     → {new_temp, sent_via}
  POST /send-whatsapp      → {sent: bool, phone}
  POST /change-plan        → {plan}
  POST /rotate-api-key     → {new_key_preview}
  POST /trigger-scan       → {scan_id, queued: true}
  POST /impersonate        → {impersonation_token, expires_in}

Audit: every action writes to `admin_action_log` collection with
  {admin_email, target_email, action, detail, ip, timestamp, ttl_at}.
"""
from __future__ import annotations

import os
import re
import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/customer-360", tags=["Customer 360 Actions"])

from config import JWT_SECRET  # safe 3-tier resolver (env -> file -> ephemeral)
IMPERSONATE_TTL_MIN = 30
VALID_PLANS = {"trial", "starter", "growth", "enterprise"}

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(503, "DB not available")
    return _db


async def _require_admin(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    if payload.get("role") in ("admin", "super_admin") or payload.get("is_admin") or payload.get("is_super_admin"):
        return payload
    raise HTTPException(403, "Admin only")


async def _resolve_target(db, identifier: str) -> Dict[str, Any]:
    """Return {email, business_id, platform_user, tenant_customer, workspace} for the customer."""
    from services.bin_generator import is_bin, normalize_bin

    ident = (identifier or "").strip()
    email: Optional[str] = None
    if is_bin(ident):
        bid = normalize_bin(ident)
        u = await db.platform_users.find_one({"business_id": bid}) \
            or await db.tenant_customers.find_one({"business_id": bid})
        if u:
            email = (u.get("email") or "").lower()
    else:
        email = ident.lower()

    if not email:
        raise HTTPException(404, f"Customer not found: {identifier}")

    pu = await db.platform_users.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}}) or {}
    tc = await db.tenant_customers.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}}) or {}
    ws = await db.aurem_workspaces.find_one(
        {"$or": [
            {"owner_email": {"$regex": f"^{email}$", "$options": "i"}},
            {"email": {"$regex": f"^{email}$", "$options": "i"}},
        ]}
    ) or {}

    return {
        "email": email,
        "business_id": pu.get("business_id") or tc.get("business_id") or "",
        "phone": pu.get("phone") or tc.get("phone") or ws.get("phone") or "",
        "platform_user": pu,
        "tenant_customer": tc,
        "workspace": ws,
    }


async def _audit(db, admin: Dict, target_email: str, action: str, detail: Dict, ip: str = "") -> None:
    try:
        await db.admin_action_log.insert_one({
            "admin_email": (admin.get("email") or admin.get("sub") or "").lower(),
            "target_email": target_email,
            "action": action,
            "detail": detail,
            "ip": ip,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ttl_at": datetime.now(timezone.utc),  # TTL-eligible (30 days once indexed)
        })
    except Exception as e:
        logger.warning(f"[AdminAction] audit failed: {e}")


def _hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


# ═══════════════════════════════════════════
# 1. Reset Password
# ═══════════════════════════════════════════
class ResetPasswordBody(BaseModel):
    notify: bool = True


@router.post("/{identifier}/actions/reset-password")
async def action_reset_password(identifier: str, body: ResetPasswordBody, request: Request):
    admin = await _require_admin(request)
    db = _get_db()
    t = await _resolve_target(db, identifier)

    # Generate temp password (14 chars, letter+digit+symbol)
    temp = "A-" + secrets.token_urlsafe(10)
    new_hash = _hash_password(temp)
    now_iso = datetime.now(timezone.utc).isoformat()

    await db.platform_users.update_one(
        {"email": t["email"]},
        {"$set": {
            "password_hash": new_hash,
            "must_set_password": True,
            "password_reset_at": now_iso,
            "password_reset_by": admin.get("email"),
        }},
    )
    # Invalidate cached customer-context
    try:
        from services.aurem_cache import cache_delete
        await cache_delete(f"ctx:{t['email']}")
    except Exception:
        pass

    sent_via: list = []
    if body.notify and t["phone"]:
        try:
            from routers.whatsapp_alerts import send_whatsapp
            await send_whatsapp(
                t["phone"],
                f"🔐 AUREM — password reset by admin\n\n"
                f"Temp password: {temp}\n"
                f"Log in at https://aurem.live and set a new password immediately.",
            )
            sent_via.append("whatsapp")
        except Exception as e:
            logger.warning(f"[AdminAction] reset-password WA failed: {e}")

    await _audit(db, admin, t["email"], "reset_password",
                 {"notify": body.notify, "sent_via": sent_via},
                 request.client.host if request.client else "")
    return {"success": True, "temp_password": temp, "sent_via": sent_via}


# ═══════════════════════════════════════════
# 2. Send Manual WhatsApp
# ═══════════════════════════════════════════
class WhatsAppBody(BaseModel):
    message: str


@router.post("/{identifier}/actions/send-whatsapp")
async def action_send_whatsapp(identifier: str, body: WhatsAppBody, request: Request):
    admin = await _require_admin(request)
    db = _get_db()
    t = await _resolve_target(db, identifier)

    if not t["phone"]:
        raise HTTPException(400, "No phone number on file for this customer")

    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(400, "Message is required")

    from routers.whatsapp_alerts import send_whatsapp
    result = await send_whatsapp(t["phone"], msg)

    await _audit(db, admin, t["email"], "send_whatsapp",
                 {"phone": t["phone"], "message_preview": msg[:120], "whapi_ok": bool(result)},
                 request.client.host if request.client else "")
    return {"success": True, "phone": t["phone"], "whapi_response": bool(result)}


# ═══════════════════════════════════════════
# 3. Change Plan (upgrade / downgrade)
# ═══════════════════════════════════════════
class ChangePlanBody(BaseModel):
    plan: str  # trial | starter | growth | enterprise


@router.post("/{identifier}/actions/change-plan")
async def action_change_plan(identifier: str, body: ChangePlanBody, request: Request):
    admin = await _require_admin(request)
    db = _get_db()
    t = await _resolve_target(db, identifier)

    plan = (body.plan or "").strip().lower()
    if plan not in VALID_PLANS:
        raise HTTPException(400, f"Invalid plan: {plan}. Must be one of {sorted(VALID_PLANS)}")

    now_iso = datetime.now(timezone.utc).isoformat()
    prev_plan = (t["platform_user"].get("plan_status") or t["tenant_customer"].get("plan") or "").lower()

    await db.platform_users.update_one(
        {"email": t["email"]},
        {"$set": {"plan_status": plan, "plan_changed_at": now_iso, "plan_changed_by": admin.get("email")}},
    )
    await db.tenant_customers.update_one(
        {"email": {"$regex": f"^{t['email']}$", "$options": "i"}},
        {"$set": {"plan": plan, "plan_changed_at": now_iso}},
    )
    # Invalidate cache
    try:
        from services.aurem_cache import cache_delete
        await cache_delete(f"ctx:{t['email']}")
        await cache_delete(f"plan_limits:{plan}")
    except Exception:
        pass

    await _audit(db, admin, t["email"], "change_plan",
                 {"from": prev_plan, "to": plan},
                 request.client.host if request.client else "")
    return {"success": True, "from": prev_plan, "to": plan}


# ═══════════════════════════════════════════
# 4. Rotate API Key
# ═══════════════════════════════════════════
@router.post("/{identifier}/actions/rotate-api-key")
async def action_rotate_api_key(identifier: str, request: Request):
    admin = await _require_admin(request)
    db = _get_db()
    t = await _resolve_target(db, identifier)

    # Find existing key (either field)
    existing = await db.api_keys.find_one(
        {"$or": [
            {"email": {"$regex": f"^{t['email']}$", "$options": "i"}},
            {"owner_email": {"$regex": f"^{t['email']}$", "$options": "i"}},
        ]},
    )
    tenant_id = (existing or {}).get("tenant_id") or (t["workspace"] or {}).get("owner_id") or f"tenant_{uuid.uuid4().hex[:12]}"

    # Deactivate all old keys for this owner
    await db.api_keys.update_many(
        {"$or": [
            {"email": {"$regex": f"^{t['email']}$", "$options": "i"}},
            {"owner_email": {"$regex": f"^{t['email']}$", "$options": "i"}},
        ]},
        {"$set": {"is_active": False, "active": False, "deactivated_at": datetime.now(timezone.utc).isoformat(), "deactivated_by": admin.get("email")}},
    )

    # Create fresh key — same schema as aurem_keys_router
    new_raw = f"aurem_{uuid.uuid4().hex}"
    new_hash = hashlib.sha256(new_raw.encode()).hexdigest()
    key_preview = new_raw[:12] + "•" * 20 + new_raw[-4:]
    now_iso = datetime.now(timezone.utc).isoformat()

    await db.api_keys.insert_one({
        "key_id": f"key_{uuid.uuid4().hex[:16]}",
        "key_hash": new_hash,
        "api_key_hash": new_hash,          # legacy field
        "key_preview": key_preview,
        "email": t["email"],
        "owner_email": t["email"],
        "tenant_id": tenant_id,
        "business_id": t["business_id"],
        "is_active": True,
        "active": True,
        "created_at": now_iso,
        "rotated_by": admin.get("email"),
        "permissions": ["pixel", "webhooks", "ai_chat", "scanner"],
        "hit_count": 0,
    })

    await _audit(db, admin, t["email"], "rotate_api_key",
                 {"tenant_id": tenant_id, "key_preview": key_preview},
                 request.client.host if request.client else "")

    # Return raw key ONCE (user must copy immediately — not stored plaintext after this)
    return {
        "success": True,
        "new_key": new_raw,
        "key_preview": key_preview,
        "tenant_id": tenant_id,
        "warning": "Save this key now — it cannot be recovered.",
    }


# ═══════════════════════════════════════════
# 5. Trigger Scan Now
# ═══════════════════════════════════════════
@router.post("/{identifier}/actions/trigger-scan")
async def action_trigger_scan(identifier: str, request: Request):
    admin = await _require_admin(request)
    db = _get_db()
    t = await _resolve_target(db, identifier)

    website = (t["workspace"] or {}).get("website") or \
              (t["platform_user"] or {}).get("website") or \
              (t["tenant_customer"] or {}).get("website") or ""
    if not website:
        raise HTTPException(400, "No website on file for this customer. Add a website first.")

    scan_id = f"scan_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)
    await db.scan_queue.insert_one({
        "scan_id": scan_id,
        "tenant_email": t["email"],
        "tenant_id": (t["workspace"] or {}).get("owner_id", ""),
        "website": website,
        "queued_at": now.isoformat(),
        "queued_by": admin.get("email"),
        "status": "queued",
        "ttl_at": now,
    })

    await _audit(db, admin, t["email"], "trigger_scan",
                 {"scan_id": scan_id, "website": website},
                 request.client.host if request.client else "")
    return {"success": True, "scan_id": scan_id, "website": website, "status": "queued"}


# ═══════════════════════════════════════════
# 6. Impersonate (login-as)
# ═══════════════════════════════════════════
@router.post("/{identifier}/actions/impersonate")
async def action_impersonate(identifier: str, request: Request):
    admin = await _require_admin(request)
    db = _get_db()
    t = await _resolve_target(db, identifier)

    # Short-lived token with impersonation flag
    payload = {
        "email": t["email"],
        "sub": t["email"],
        "role": t["platform_user"].get("role") or "user",
        "jti": uuid.uuid4().hex,
        "exp": datetime.utcnow() + timedelta(minutes=IMPERSONATE_TTL_MIN),
        "iat": datetime.utcnow(),
        "impersonated": True,
        "impersonator": (admin.get("email") or admin.get("sub") or "").lower(),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    await _audit(db, admin, t["email"], "impersonate",
                 {"ttl_minutes": IMPERSONATE_TTL_MIN, "jti": payload["jti"]},
                 request.client.host if request.client else "")
    return {
        "success": True,
        "impersonation_token": token,
        "expires_in": IMPERSONATE_TTL_MIN * 60,
        "target_email": t["email"],
        "warning": "Token expires in 30 minutes. All actions are audit-logged as impersonation.",
    }


# ═══════════════════════════════════════════
# Audit history for a customer
# ═══════════════════════════════════════════
@router.get("/{identifier}/actions/history")
async def action_history(identifier: str, request: Request, limit: int = 20):
    await _require_admin(request)
    db = _get_db()
    t = await _resolve_target(db, identifier)
    limit = max(1, min(limit, 100))
    cursor = db.admin_action_log.find(
        {"target_email": t["email"]},
        {"_id": 0},
    ).sort("timestamp", -1).limit(limit)
    return {"history": await cursor.to_list(limit)}


@router.get("/actions/impersonation-log")
async def impersonation_log(request: Request, limit: int = 100):
    """Platform-wide impersonation history for CASL/compliance review."""
    await _require_admin(request)
    db = _get_db()
    limit = max(1, min(limit, 500))
    cursor = db.admin_action_log.find(
        {"action": "impersonate"},
        {"_id": 0},
    ).sort("timestamp", -1).limit(limit)
    rows = await cursor.to_list(limit)
    total = await db.admin_action_log.count_documents({"action": "impersonate"})
    return {"total": total, "count": len(rows), "log": rows}


@router.get("/actions/health")
async def actions_health():
    return {"status": "ok", "service": "customer-360-actions"}
