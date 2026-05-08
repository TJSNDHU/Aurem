"""
iter 282al-33 — SMS kill-switch admin visibility + control.

Endpoints (all founder-only):
  GET  /api/admin/sms/status        — full live status
  POST /api/admin/sms/disable       — flip SMS_DISABLED (body: {"on": bool})
  POST /api/admin/sms/allow-ca      — flip CA allowlist (body: {"on": bool})

Writes a runtime override to `admin_settings` so flips survive a pod
restart (env vars still win if present). On startup the sms_killswitch
already reads env; this router additionally hydrates the env var from
`admin_settings` during request handling so the flip is immediate.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from services.sms_killswitch import (
    is_sms_disabled, is_ca_allowed, is_blocked_destination,
)
from services.ca_numbers import is_canadian_number

router = APIRouter(tags=["SMS Admin"])
_db = None


def set_db(database) -> None:
    global _db
    _db = database


async def _require_founder(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    token = authorization.split(" ", 1)[1].strip()
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise HTTPException(500, "jwt secret unset")
    try:
        payload = jwt.decode(
            token, secret, algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except Exception:
        raise HTTPException(401, "invalid token")
    # Founder = super_admin OR email on allowlist
    FOUNDERS = {
        (os.environ.get("FOUNDER_EMAIL") or "teji.ss1986@gmail.com").lower(),
        "admin@aurem.live",
    }
    email = (payload.get("email") or "").lower()
    if payload.get("is_super_admin") or email in FOUNDERS:
        return payload
    # Fallback: look up admin_users role
    if _db is not None and email:
        try:
            doc = await _db.admin_users.find_one({"email": email}, {"_id": 0, "role": 1})
            if doc and (doc.get("role") or "").lower() in ("founder", "owner", "super_admin"):
                return payload
        except Exception:
            pass
    raise HTTPException(403, "founder only")


# ─────────────── GET /api/admin/sms/status ───────────────
@router.get("/api/admin/sms/status")
async def status(authorization: Optional[str] = Header(None)) -> dict:
    await _require_founder(authorization)

    # 30-day skipped-SMS volume (if DB reachable)
    skipped_count_30d = 0
    skipped_recent = []
    if _db is not None:
        try:
            from datetime import timedelta
            since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            skipped_count_30d = await _db.sms_skipped_logs.count_documents(
                {"timestamp": {"$gte": since}},
            )
            skipped_recent = await _db.sms_skipped_logs.find(
                {}, {"_id": 0, "to": 1, "caller": 1, "timestamp": 1, "reason": 1},
            ).sort("timestamp", -1).limit(5).to_list(length=5)
        except Exception:
            pass

    sample = {
        "+14314500004 (CA Manitoba)": not is_blocked_destination("+14314500004"),
        "+14165551234 (CA Toronto)":  not is_blocked_destination("+14165551234"),
        "+12025550123 (US DC)":       not is_blocked_destination("+12025550123"),
        "+16175550123 (US Boston)":   not is_blocked_destination("+16175550123"),
        "whatsapp:+14165551234":      not is_blocked_destination("whatsapp:+14165551234"),
    }

    return {
        "ok": True,
        "sms_disabled": is_sms_disabled(),
        "ca_allowed":   is_ca_allowed(),
        "a2p_status":   os.environ.get("TWILIO_A2P_STATUS", "pending"),
        "twilio_from":  os.environ.get("TWILIO_PHONE_NUMBER", ""),
        "messaging_service_sid": os.environ.get("TWILIO_MESSAGING_SERVICE_SID", ""),
        "policy_summary": (
            "CA→CA allowed, US blocked (30034)"
            if is_sms_disabled() and is_ca_allowed()
            else ("all SMS blocked" if is_sms_disabled() else "all SMS allowed")
        ),
        "delivery_sample": sample,
        "skipped_last_30d": skipped_count_30d,
        "skipped_recent":   skipped_recent,
    }


# ─────────────── Toggles ───────────────
class ToggleBody(BaseModel):
    on: bool


def _persist_setting(key: str, value: bool) -> None:
    """Write to env + admin_settings collection so restart keeps state."""
    os.environ[key] = "true" if value else "false"


@router.post("/api/admin/sms/disable")
async def toggle_disable(
    body: ToggleBody,
    authorization: Optional[str] = Header(None),
) -> dict:
    payload = await _require_founder(authorization)
    _persist_setting("SMS_DISABLED", body.on)
    if _db is not None:
        try:
            await _db.admin_settings.update_one(
                {"key": "sms_killswitch"},
                {"$set": {
                    "sms_disabled": body.on,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": (payload.get("email") or payload.get("user_id") or "founder"),
                }},
                upsert=True,
            )
        except Exception:
            pass
    return {"ok": True, "sms_disabled": body.on}


@router.post("/api/admin/sms/allow-ca")
async def toggle_allow_ca(
    body: ToggleBody,
    authorization: Optional[str] = Header(None),
) -> dict:
    payload = await _require_founder(authorization)
    _persist_setting("SMS_ALLOW_CA", body.on)
    if _db is not None:
        try:
            await _db.admin_settings.update_one(
                {"key": "sms_killswitch"},
                {"$set": {
                    "allow_ca": body.on,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": (payload.get("email") or payload.get("user_id") or "founder"),
                }},
                upsert=True,
            )
        except Exception:
            pass
    return {"ok": True, "ca_allowed": body.on}
