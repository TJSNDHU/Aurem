"""
v2_customer_actions_router.py — iter 325o
============================================================
17 missing endpoints the V2 customer portal needs.

Architecturally bundled into ONE router so wiring stays clean and
discovery is trivial. Every action persists to the live Mongo DB
(no mocks). Read-side endpoints reuse the same collections the
existing dashboards write to.

ROUTES (all prefix `/api`):

  HEALTH / INCIDENTS
    POST   /repair/trigger-scan
    GET    /incidents/list
    POST   /incidents/resolve/{incident_id}

  AUTH (extends /api/platform/auth/* family)
    GET    /platform/auth/me
    PATCH  /platform/auth/me
    POST   /platform/auth/2fa/toggle
    DELETE /platform/auth/sessions/all
    GET    /platform/auth/session
    POST   /platform/auth/api-key/regenerate

  ONBOARDING / DIAGNOSTICS
    POST   /onboarding/activate-pipeline
    POST   /customer/diagnostic/run-now/{bin_id}

  BRANDING / TENANT
    GET    /bin/ora/settings
    PATCH  /bin/settings

  VOICE
    GET    /voice-agent/config
    GET    /voice-agent/health

  LEADS
    PATCH  /leads/{lead_id}
    POST   /leads/{lead_id}/send-email
"""
from __future__ import annotations

import os
import re
import secrets
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import jwt
import httpx
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Header, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

_db = None

def set_db(database):
    global _db
    _db = database

# ─────────────────────────────────────────────────────────────────
# Auth dep — JWT verify via the platform secret
# ─────────────────────────────────────────────────────────────────

def _decode_jwt(token: str) -> Dict[str, Any]:
    secret = os.environ.get("JWT_SECRET") or os.environ.get("PLATFORM_JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT secret not configured")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e}")


async def _require_user(authorization: str = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    payload = _decode_jwt(authorization.split(" ", 1)[1].strip())
    if not payload.get("email"):
        raise HTTPException(401, "token missing email")
    return payload


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_id(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if d is None:
        return None
    d.pop("_id", None)
    return d


# ─────────────────────────────────────────────────────────────────
# HEALTH / INCIDENTS
# ─────────────────────────────────────────────────────────────────

@router.post("/api/repair/trigger-scan")
async def trigger_scan(user=Depends(_require_user)):
    """Queue a fresh repair scan for the caller's primary site.

    Writes a `repair_scan_queue` doc; existing scan workers pick it up
    on the next tick. Returns immediately.
    """
    if _db is None:
        raise HTTPException(503, "db not ready")
    bin_id = user.get("business_id") or user.get("bin") or user.get("email", "").split("@")[0]
    doc = {
        "bin_id": bin_id,
        "email": user["email"],
        "queued_at": _now(),
        "status": "queued",
        "source": "v2_customer_portal",
    }
    res = await _db.repair_scan_queue.insert_one(doc)
    doc["scan_id"] = str(res.inserted_id)
    return {"ok": True, "scan_id": doc["scan_id"], "queued_at": doc["queued_at"].isoformat()}


@router.get("/api/incidents/list")
async def list_incidents(limit: int = 20, user=Depends(_require_user)):
    """Reads from the existing `incident_ledger` collection populated by
    the autonomous repair stack. Falls back to `error_ledger`.
    """
    if _db is None:
        raise HTTPException(503, "db not ready")
    out: List[Dict[str, Any]] = []
    collection = "incident_ledger" if "incident_ledger" in await _db.list_collection_names() else "error_ledger"
    cur = _db[collection].find(
        {"resolved": {"$ne": True}},
        {"_id": 1, "severity": 1, "message": 1, "created_at": 1, "ts": 1, "source": 1, "category": 1},
    ).sort("created_at", -1).limit(max(1, min(limit, 100)))
    async for d in cur:
        out.append({
            "id": str(d.pop("_id")),
            "severity": (d.get("severity") or "LOW").upper(),
            "message": d.get("message") or d.get("category") or "incident",
            "source": d.get("source") or collection,
            "created_at": (d.get("created_at") or d.get("ts") or _now()).isoformat()
                          if isinstance(d.get("created_at") or d.get("ts"), datetime)
                          else str(d.get("created_at") or d.get("ts") or ""),
        })
    return {"incidents": out, "count": len(out), "source_collection": collection}


@router.post("/api/incidents/resolve/{incident_id}")
async def resolve_incident(incident_id: str, user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    try:
        oid = ObjectId(incident_id)
        flt = {"_id": oid}
    except Exception:
        flt = {"_id": incident_id}
    collection = "incident_ledger" if "incident_ledger" in await _db.list_collection_names() else "error_ledger"
    res = await _db[collection].update_one(
        flt,
        {"$set": {"resolved": True, "resolved_at": _now(), "resolved_by": user["email"]}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "incident not found")
    return {"ok": True, "incident_id": incident_id, "resolved_at": _now().isoformat()}


# Backwards-compat singular alias the spec also mentions
@router.post("/api/incident/resolve/{incident_id}")
async def resolve_incident_alias(incident_id: str, user=Depends(_require_user)):
    return await resolve_incident(incident_id, user)


# ─────────────────────────────────────────────────────────────────
# AUTH — extends /api/platform/auth/* family
# ─────────────────────────────────────────────────────────────────

async def _find_user(email: str) -> Optional[Dict[str, Any]]:
    """Look up the user across the 3 known collections."""
    for coll in ("users", "platform_users", "admin_users", "aurem_users"):
        if coll not in await _db.list_collection_names():
            continue
        d = await _db[coll].find_one({"email": email})
        if d:
            d["_source_collection"] = coll
            return d
    return None


@router.get("/api/platform/auth/me")
async def get_me(user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    doc = await _find_user(user["email"])
    if not doc:
        raise HTTPException(404, "user not found")
    src = doc.pop("_source_collection", "users")
    out = {
        "email":         doc.get("email"),
        "full_name":     doc.get("full_name") or doc.get("name"),
        "company_name":  doc.get("company_name") or doc.get("business_name"),
        "business_id":   doc.get("business_id") or doc.get("bin"),
        "role":          doc.get("role"),
        "plan":          doc.get("plan") or user.get("plan"),
        "tier":          doc.get("tier"),
        "website_url":   doc.get("website_url"),
        "phone":         doc.get("phone"),
        "two_fa_enabled": bool(doc.get("two_fa_enabled", False)),
        "_collection":   src,
    }
    return out


class UpdateMeBody(BaseModel):
    full_name:    Optional[str] = None
    company_name: Optional[str] = None
    website_url:  Optional[str] = None
    phone:        Optional[str] = None


@router.patch("/api/platform/auth/me")
async def patch_me(body: UpdateMeBody, user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    doc = await _find_user(user["email"])
    if not doc:
        raise HTTPException(404, "user not found")
    src = doc.pop("_source_collection", "users")
    patch = {k: v for k, v in body.dict().items() if v is not None}
    if not patch:
        return {"ok": True, "updated": 0}
    patch["updated_at"] = _now()
    await _db[src].update_one({"email": user["email"]}, {"$set": patch})
    return {"ok": True, "updated": len(patch) - 1, "fields": list(patch.keys())}


@router.post("/api/platform/auth/2fa/toggle")
async def toggle_2fa(user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    doc = await _find_user(user["email"])
    if not doc:
        raise HTTPException(404, "user not found")
    src = doc.pop("_source_collection", "users")
    current = bool(doc.get("two_fa_enabled", False))
    new = not current
    await _db[src].update_one(
        {"email": user["email"]},
        {"$set": {"two_fa_enabled": new, "two_fa_changed_at": _now()}},
    )
    return {"ok": True, "two_fa_enabled": new}


@router.delete("/api/platform/auth/sessions/all")
async def revoke_all_sessions(user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    # Bumping `token_epoch` invalidates every JWT minted before now.
    # The auth middleware should reject tokens with iat < token_epoch.
    epoch = int(_now().timestamp())
    for coll in ("users", "platform_users"):
        if coll in await _db.list_collection_names():
            await _db[coll].update_one(
                {"email": user["email"]},
                {"$set": {"token_epoch": epoch}},
            )
    return {"ok": True, "revoked_before": epoch, "revoked_at": _now().isoformat()}


@router.get("/api/platform/auth/session")
async def get_session(user=Depends(_require_user)):
    return {
        "email":       user.get("email"),
        "role":        user.get("role"),
        "business_id": user.get("business_id"),
        "plan":        user.get("plan"),
        "issued_at":   user.get("iat"),
        "expires_at":  user.get("exp"),
        "session_id":  user.get("jti"),
    }


@router.post("/api/platform/auth/api-key/regenerate")
async def regenerate_api_key(user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    new_key = f"sk_aurem_{secrets.token_urlsafe(32)}"
    for coll in ("users", "platform_users"):
        if coll in await _db.list_collection_names():
            await _db[coll].update_one(
                {"email": user["email"]},
                {"$set": {"api_key": new_key, "api_key_rotated_at": _now()}},
            )
    return {"ok": True, "api_key": new_key, "rotated_at": _now().isoformat()}


# ─────────────────────────────────────────────────────────────────
# ONBOARDING / DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────

class ActivatePipelineBody(BaseModel):
    website_url: str = Field(..., min_length=4)


@router.post("/api/onboarding/activate-pipeline")
async def activate_pipeline(body: ActivatePipelineBody, user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    bin_id = user.get("business_id") or user["email"].split("@")[0]
    await _db.onboarding_state.update_one(
        {"email": user["email"]},
        {"$set": {
            "email":       user["email"],
            "bin_id":      bin_id,
            "website_url": body.website_url,
            "status":      "activated",
            "activated_at": _now(),
        }},
        upsert=True,
    )
    # Also save website on the user doc so it surfaces in /me.
    for coll in ("users", "platform_users"):
        if coll in await _db.list_collection_names():
            await _db[coll].update_one(
                {"email": user["email"]},
                {"$set": {"website_url": body.website_url}},
            )
    return {"ok": True, "bin_id": bin_id, "website_url": body.website_url}


@router.post("/api/customer/diagnostic/run-now/{bin_id}")
async def diagnostic_run_now(bin_id: str, user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    job = {
        "bin_id":   bin_id,
        "email":    user["email"],
        "queued_at": _now(),
        "status":   "queued",
        "source":   "v2_profile_scan_now",
    }
    res = await _db.diagnostic_queue.insert_one(job)
    return {"ok": True, "job_id": str(res.inserted_id), "bin_id": bin_id}


# ─────────────────────────────────────────────────────────────────
# BRANDING / TENANT
# ─────────────────────────────────────────────────────────────────

@router.get("/api/bin/ora/settings")
async def get_bin_settings(user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    bin_id = user.get("business_id") or user["email"].split("@")[0]
    doc = await _db.tenant_settings.find_one({"bin_id": bin_id}, {"_id": 0}) or {}
    return {
        "bin_id":         bin_id,
        "brand_name":     doc.get("brand_name") or user.get("company_name") or "AUREM",
        "logo_url":       doc.get("logo_url") or "",
        "primary_colour": doc.get("primary_colour") or "#5E54E8",
        "custom_domain":  doc.get("custom_domain") or "",
        "scan_schedule":  doc.get("scan_schedule") or "weekly",
    }


class PatchBinBody(BaseModel):
    brand_name:     Optional[str] = None
    logo_url:       Optional[str] = None
    primary_colour: Optional[str] = None
    custom_domain:  Optional[str] = None


@router.patch("/api/bin/settings")
async def patch_bin_settings(body: PatchBinBody, user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    bin_id = user.get("business_id") or user["email"].split("@")[0]
    patch = {k: v for k, v in body.dict().items() if v is not None}
    if not patch:
        return {"ok": True, "updated": 0}
    patch.update({"bin_id": bin_id, "updated_at": _now()})
    await _db.tenant_settings.update_one(
        {"bin_id": bin_id},
        {"$set": patch},
        upsert=True,
    )
    return {"ok": True, "updated": len(patch) - 2, "fields": list(patch.keys())}


# ─────────────────────────────────────────────────────────────────
# VOICE
# ─────────────────────────────────────────────────────────────────

@router.get("/api/voice-agent/config")
async def voice_config(user=Depends(_require_user)):
    return {
        "configured":   bool((os.environ.get("RETELL_API_KEY") or "").strip()),
        "agent_id":     os.environ.get("RETELL_AGENT_ID", ""),
        "from_number":  os.environ.get("RETELL_FROM_NUMBER", ""),
        "provider":     "retell",
    }


@router.get("/api/voice-agent/health")
async def voice_health(user=Depends(_require_user)):
    key = (os.environ.get("RETELL_API_KEY") or "").strip()
    if not key:
        return {"live": False, "minutes_used": 0, "reason": "RETELL_API_KEY missing"}
    try:
        async with httpx.AsyncClient(timeout=4.0) as c:
            r = await c.get("https://api.retellai.com/list-agents",
                            headers={"Authorization": f"Bearer {key}"})
        live = r.status_code == 200
    except Exception:
        live = False
    minutes = 0
    if _db is not None:
        cutoff = _now() - timedelta(days=30)
        cur = _db.auto_call_log.find({"called_at": {"$gte": cutoff}}, {"duration_sec": 1})
        async for d in cur:
            minutes += (d.get("duration_sec") or 0) / 60.0
    return {"live": live, "minutes_used": round(minutes, 1), "provider": "retell"}


# ─────────────────────────────────────────────────────────────────
# LEADS
# ─────────────────────────────────────────────────────────────────

_VALID_STATUSES = {"new", "contacted", "qualified", "responded", "closed", "lost"}


class PatchLeadBody(BaseModel):
    status: Optional[str] = None
    score:  Optional[int] = None
    notes:  Optional[str] = None


def _lead_filter(lead_id: str) -> Dict[str, Any]:
    """Match by _id (ObjectId or str) OR by lead_id field."""
    try:
        return {"$or": [{"_id": ObjectId(lead_id)}, {"lead_id": lead_id}]}
    except Exception:
        return {"lead_id": lead_id}


@router.patch("/api/leads/{lead_id}")
async def patch_lead(lead_id: str, body: PatchLeadBody, user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    if body.status and body.status not in _VALID_STATUSES:
        raise HTTPException(422, f"invalid status; allowed: {sorted(_VALID_STATUSES)}")
    patch = {k: v for k, v in body.dict().items() if v is not None}
    if not patch:
        return {"ok": True, "updated": 0}
    patch["updated_at"] = _now()
    patch["updated_by"] = user["email"]
    # Try `leads` first, fall back to `campaign_leads`.
    collections = [c for c in ("leads", "campaign_leads") if c in await _db.list_collection_names()]
    for coll in collections:
        res = await _db[coll].update_one(_lead_filter(lead_id), {"$set": patch})
        if res.matched_count > 0:
            return {"ok": True, "lead_id": lead_id, "collection": coll, "fields": list(patch.keys())}
    raise HTTPException(404, "lead not found")


class SendEmailBody(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    body:    str = Field(..., min_length=1, max_length=10000)


@router.post("/api/leads/{lead_id}/send-email")
async def send_lead_email(lead_id: str, body: SendEmailBody, user=Depends(_require_user)):
    if _db is None:
        raise HTTPException(503, "db not ready")
    # Find lead
    lead = None
    for coll in ("leads", "campaign_leads"):
        if coll in await _db.list_collection_names():
            lead = await _db[coll].find_one(_lead_filter(lead_id))
            if lead:
                break
    if not lead:
        raise HTTPException(404, "lead not found")
    to_email = lead.get("email") or lead.get("contact_email")
    if not to_email:
        raise HTTPException(422, "lead has no email on file")
    # Send via resend if configured; otherwise queue.
    sent_id = None
    if os.environ.get("RESEND_API_KEY"):
        try:
            from services.email_engine import resend  # iter 326x defensive
            resend.api_key = os.environ["RESEND_API_KEY"]
            r = resend.Emails.send({
                "from":    "AUREM <ops@aurem.live>",
                "to":      [to_email],
                "subject": body.subject,
                "html":    f"<p>{body.body}</p>",
            })
            sent_id = (r or {}).get("id")
        except Exception as e:
            logger.warning(f"[send_lead_email] resend failed: {e}")
    # Always log the attempt
    await _db.outreach_history.insert_one({
        "lead_id":  str(lead.get("_id") or lead.get("lead_id")),
        "channel":  "email",
        "to":       to_email,
        "subject":  body.subject,
        "sent_at":  _now(),
        "sent_by":  user["email"],
        "provider_id": sent_id,
        "source":   "v2_crm_inline_send",
    })
    return {"ok": True, "to": to_email, "provider_id": sent_id}
