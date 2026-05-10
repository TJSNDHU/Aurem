"""
Admin BIN Detail Router — `/api/admin/customer-health/*` enhancements.

Endpoints (admin-only, JWT verified):
  GET    /api/admin/customer-health/bin-detail/{bin_id}
  POST   /api/admin/customer-health/force-unlock/{bin_id}
  POST   /api/admin/customer-health/reset-password/{bin_id}
  PATCH  /api/admin/customer-health/update/{bin_id}
  POST   /api/admin/promote-now/{bin_id}

Designed for the right-panel "Enhanced BIN Detail" view in
CustomerHealthPanel.jsx — 5 sections + 4 action buttons.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin BIN Detail"])

_db = None


def set_db(db) -> None:
    global _db
    _db = db


def _decode(token: str) -> dict:
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
    if not secret:
        raise HTTPException(500, "JWT secret not configured")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


async def _require_admin(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    claims = _decode(auth[7:])
    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(401, "Token missing email")
    if _db is None:
        raise HTTPException(503, "DB not ready")
    user = await _db.users.find_one(
        {"email": email},
        {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1},
    )
    if not user or not (
        user.get("is_admin") or user.get("is_super_admin")
        or user.get("role") in ("admin", "super_admin")
    ):
        raise HTTPException(403, "Admin access required")
    return {"email": email, **user}


# ═══════════════════════════════════════════════════════════════════════
# GET /bin-detail/{bin_id} — full BIN snapshot for the right panel.
# ═══════════════════════════════════════════════════════════════════════
@router.get("/customer-health/bin-detail/{bin_id}")
async def bin_detail(bin_id: str, _admin: dict = Depends(_require_admin)):
    pu = await _db.platform_users.find_one(
        {"business_id": bin_id},
        {"_id": 0, "password_hash": 0, "pin_hash": 0},
    )
    if not pu:
        # Fallback: check by email match via tenant_customers.
        tc = await _db.tenant_customers.find_one(
            {"business_id": bin_id}, {"_id": 0, "email": 1},
        )
        if tc:
            pu = await _db.platform_users.find_one(
                {"email": tc["email"]}, {"_id": 0, "password_hash": 0, "pin_hash": 0},
            )
    if not pu:
        raise HTTPException(404, f"no platform_users record for {bin_id}")

    email = (pu.get("email") or "").lower()
    user_row = await _db.users.find_one(
        {"email": email},
        {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1},
    ) or {}

    # Account access checks
    has_password = bool(pu.get("password_hash")) if pu else False
    # platform_users password_hash was projected out; check existence with separate query
    pw_doc = await _db.platform_users.find_one(
        {"business_id": bin_id}, {"_id": 0, "password_hash": 1},
    )
    has_password = bool((pw_doc or {}).get("password_hash"))

    is_locked = bool(pu.get("is_locked", False))
    role_is_user = (pu.get("role") or "user") == "user"
    user_is_admin = bool(user_row.get("is_admin") or user_row.get("is_super_admin"))

    access_ok = (not is_locked) and has_password and role_is_user and (not user_is_admin)
    blockers: list[str] = []
    if is_locked:
        blockers.append("account locked")
    if not has_password:
        blockers.append("no password set")
    if not role_is_user:
        blockers.append(f"role={pu.get('role')}")
    if user_is_admin:
        blockers.append("is_admin=true (admin collision guard will reject)")

    # Pixel status
    pixel_install = await _db.pixel_installations.find_one(
        {"business_id": bin_id}, {"_id": 0},
    ) or {}
    last_evt = await _db.pixel_events.find_one(
        {"bin_id": bin_id}, {"_id": 0, "timestamp": 1, "page": 1},
        sort=[("timestamp", -1)],
    )
    last_evt_ts = last_evt.get("timestamp") if last_evt else None
    if isinstance(last_evt_ts, datetime):
        last_evt_iso = last_evt_ts.isoformat()
    else:
        last_evt_iso = None
    since_24h = datetime.now(timezone.utc).replace(microsecond=0)
    from datetime import timedelta as _td
    yesterday = since_24h - _td(hours=24)
    events_24h = await _db.pixel_events.count_documents(
        {"bin_id": bin_id, "timestamp": {"$gte": yesterday}}
    )

    # Subscriptions
    active_subs = await _db.customer_subscriptions.count_documents(
        {"tenant_bin": bin_id, "status": "active"}
    )
    last_usage = await _db.service_usage_log.find_one(
        {"business_id": bin_id}, {"_id": 0, "service": 1, "ts": 1},
        sort=[("ts", -1)],
    ) or {}

    return {
        "ok": True,
        "bin_id": bin_id,
        "account": {
            "email": email,
            "plan": pu.get("plan") or "trial",
            "tier": pu.get("tier"),
            "status": (
                "locked" if is_locked else
                pu.get("subscription_status") or pu.get("tier_status") or "active"
            ),
            "is_locked": is_locked,
            "failed_attempts": int(pu.get("failed_attempts") or 0),
            "last_login": pu.get("last_login_at") and (
                pu["last_login_at"].isoformat() if isinstance(pu["last_login_at"], datetime) else pu["last_login_at"]
            ),
            "trial_ends_at": pu.get("trial_ends_at") and (
                pu["trial_ends_at"].isoformat() if isinstance(pu["trial_ends_at"], datetime) else pu["trial_ends_at"]
            ),
            "notes": pu.get("notes") or "",
            "is_dogfood": bool(pu.get("is_dogfood")),
            "is_founder": bool(pu.get("is_founder")),
        },
        "pixel": {
            "installed": bool(pixel_install.get("installed")),
            "verified": bool(pixel_install.get("verified")),
            "auto_installed": bool(pixel_install.get("auto_installed")),
            "domain": pixel_install.get("domain"),
            "last_event_at": last_evt_iso,
            "last_event_page": (last_evt or {}).get("page", ""),
            "events_24h": events_24h,
        },
        "access": {
            "can_login": access_ok,
            "checks": {
                "is_locked_false": not is_locked,
                "password_hash_exists": has_password,
                "role_is_user": role_is_user,
                "users_is_admin_false": not user_is_admin,
            },
            "blockers": blockers,
        },
        "services": {
            "services_unlocked": pu.get("services_unlocked") or [],
            "active_subscriptions": active_subs,
            "last_service_used": last_usage.get("service"),
            "last_service_used_at": (
                last_usage["ts"] if isinstance(last_usage.get("ts"), str) else
                (last_usage["ts"].isoformat() if isinstance(last_usage.get("ts"), datetime) else None)
            ),
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# POST /force-unlock/{bin_id} — clears all lockout + admin-collision flags.
# ═══════════════════════════════════════════════════════════════════════
@router.post("/customer-health/force-unlock/{bin_id}")
async def force_unlock(bin_id: str, _admin: dict = Depends(_require_admin)):
    pu = await _db.platform_users.find_one(
        {"business_id": bin_id}, {"_id": 0, "email": 1},
    )
    if not pu:
        raise HTTPException(404, f"no platform_users record for {bin_id}")
    email = (pu.get("email") or "").lower()
    now = datetime.now(timezone.utc)

    r1 = await _db.platform_users.update_one(
        {"business_id": bin_id},
        {"$set": {
            "is_locked": False,
            "failed_attempts": 0,
            "role": "user",
            "updated_at": now,
        }, "$unset": {
            "locked_until": "", "pin_locked_until": "",
            "pin_failed_count": "", "login_failed_count": "",
        }},
    )
    r2 = await _db.users.update_one(
        {"email": email},
        {"$set": {
            "is_admin": False,
            "is_super_admin": False,
            "role": "user",
            "updated_at": now,
        }, "$unset": {
            "locked_until": "", "is_locked": "",
        }},
    )
    for coll in ("login_attempts", "pin_login_attempts", "failed_logins", "auth_attempts"):
        try:
            await _db[coll].delete_many({"$or": [{"email": email}, {"key": {"$regex": bin_id}}]})
        except Exception:
            pass

    return {"ok": True, "platform_users_modified": r1.modified_count,
            "users_modified": r2.modified_count}


# ═══════════════════════════════════════════════════════════════════════
# POST /reset-password/{bin_id} — generates strong password, sets, returns.
# ═══════════════════════════════════════════════════════════════════════
@router.post("/customer-health/reset-password/{bin_id}")
async def reset_password(bin_id: str, _admin: dict = Depends(_require_admin)):
    pu = await _db.platform_users.find_one(
        {"business_id": bin_id}, {"_id": 0, "email": 1},
    )
    if not pu:
        raise HTTPException(404, f"no platform_users record for {bin_id}")
    new_pw = "AuremReset_" + secrets.token_urlsafe(8)
    pw_hash = bcrypt.hashpw(new_pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    email = (pu.get("email") or "").lower()
    now = datetime.now(timezone.utc)

    await _db.platform_users.update_one(
        {"business_id": bin_id},
        {"$set": {"password_hash": pw_hash, "updated_at": now}},
    )
    await _db.users.update_one(
        {"email": email},
        {"$set": {"password": pw_hash, "password_hash": pw_hash, "updated_at": now}},
    )
    logger.info(f"[admin/reset-password] BIN={bin_id} email={email} by={_admin.get('email')}")
    return {
        "ok": True,
        "email": email,
        "new_password": new_pw,
        "note": "Share with customer securely. Force a change on first login.",
    }


# ═══════════════════════════════════════════════════════════════════════
# PATCH /update/{bin_id} — inline edit plan/status/trial/notes.
# ═══════════════════════════════════════════════════════════════════════
ALLOWED_PLANS = {"starter", "growth", "enterprise", "lifetime_free", "trial"}
ALLOWED_STATUS = {"active", "locked", "suspended", "cancelled"}


@router.patch("/customer-health/update/{bin_id}")
async def update_account(
    bin_id: str,
    body: Dict[str, Any] = Body(...),
    _admin: dict = Depends(_require_admin),
):
    sets: Dict[str, Any] = {}
    if "plan" in body:
        p = (body["plan"] or "").lower()
        if p not in ALLOWED_PLANS:
            raise HTTPException(400, f"plan must be one of {sorted(ALLOWED_PLANS)}")
        sets["plan"] = p
        sets["tier"] = p
    if "status" in body:
        s = (body["status"] or "").lower()
        if s not in ALLOWED_STATUS:
            raise HTTPException(400, f"status must be one of {sorted(ALLOWED_STATUS)}")
        sets["subscription_status"] = s
        sets["tier_status"] = "active" if s == "active" else s
        sets["is_locked"] = (s == "locked")
    if "trial_ends_at" in body:
        v = body["trial_ends_at"]
        if v in (None, ""):
            sets["trial_ends_at"] = None
        else:
            try:
                sets["trial_ends_at"] = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            except Exception:
                raise HTTPException(400, "trial_ends_at must be ISO-8601")
    if "notes" in body:
        sets["notes"] = str(body["notes"] or "")[:1000]

    if not sets:
        raise HTTPException(400, "no editable fields supplied")
    sets["updated_at"] = datetime.now(timezone.utc)

    res = await _db.platform_users.update_one(
        {"business_id": bin_id}, {"$set": sets},
    )
    if res.matched_count == 0:
        raise HTTPException(404, f"no platform_users record for {bin_id}")
    return {"ok": True, "modified": res.modified_count, "updates": list(sets.keys())}


# ═══════════════════════════════════════════════════════════════════════
# POST /promote-now/{bin_id} — manual trigger of intelligence promote cron.
# ═══════════════════════════════════════════════════════════════════════
@router.post("/promote-now/{bin_id}")
async def promote_now(bin_id: str, _admin: dict = Depends(_require_admin)):
    """Manually run the verified-contact promotion cron for a single BIN."""
    try:
        from services.bin_intelligence import promote_verified_to_pipeline
        res = await promote_verified_to_pipeline(_db, bin_id)
        logger.info(f"[admin/promote-now] BIN={bin_id} {res} by={_admin.get('email')}")
        return {"ok": True, "bin_id": bin_id, **res}
    except Exception as e:
        logger.warning(f"[admin/promote-now] failed for {bin_id}: {e}")
        raise HTTPException(500, f"promote failed: {e}")
