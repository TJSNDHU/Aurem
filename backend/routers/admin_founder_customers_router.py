"""Founder Customer Management Router (iter 288.2)
====================================================
- GET  /api/admin/customers/list          — sidebar contacts feed (auto-updating)
- POST /api/admin/customers/cleanup       — wipe non-founder users + BINs
- POST /api/admin/customers/reonboard-bin — re-issue fresh BIN for an email
- POST /api/admin/customers/relink-pixel  — link existing pixel API key to a fresh account
"""
from __future__ import annotations
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/founder/customers", tags=["Founder Customers"])

# Founder allow-list — these accounts are NEVER deleted.
# Bug-fix #27 — pull from FOUNDER_EMAILS env (comma-separated) so we
# stop hard-coding personal emails in source. Falls back to the historic
# list so existing deploys don't lose protection.
import os as _os
_env_founders = (_os.environ.get("FOUNDER_EMAILS") or "").strip()
if _env_founders:
    FOUNDER_EMAILS = {e.strip().lower() for e in _env_founders.split(",") if e.strip()}
else:
    _f = (_os.environ.get("FOUNDER_EMAIL") or "teji.ss1986@gmail.com").strip().lower()
    FOUNDER_EMAILS = {_f, "admin@aurem.live"}

# Collections that hold customer/tenant data (cleanup scope)
CUSTOMER_COLLECTIONS = [
    "platform_users", "users", "aurem_onboarding", "tenant_customers",
    "business_profiles", "aurem_workspaces", "user_integrations",
    "scan_queue", "recovery_queue", "offer_sets",
    "agent_activations", "tenants",
]

_db = None


def set_db(db):
    global _db
    _db = db


def _require_founder(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    try:
        from middleware.tenant_guard import JWT_SECRET, JWT_ALGORITHM
        p = pyjwt.decode(auth.split(" ", 1)[1], JWT_SECRET,
                         algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")
    if not (p.get("is_admin") or p.get("is_super_admin")):
        raise HTTPException(403, "Founder only")
    return p


# ─────────────────────────────────────────────────────────────
# LIST CUSTOMERS — for sidebar auto-feed
# ─────────────────────────────────────────────────────────────
@router.get("/list")
async def list_customers(request: Request, limit: int = 50):
    _require_founder(request)
    if _db is None:
        return {"ok": False, "customers": []}
    rows: List[Dict[str, Any]] = []
    seen_emails = set()
    try:
        cur = _db.platform_users.find(
            {"email": {"$nin": list(FOUNDER_EMAILS)}},
            {"_id": 0, "email": 1, "business_id": 1, "full_name": 1,
             "company_name": 1, "city": 1, "industry": 1, "phone": 1,
             "smart_onboarded_at": 1, "created_at": 1, "role": 1,
             "onboarding_wizard_complete": 1, "google_oauth": 1,
             "business_id_active": 1, "plan": 1, "website": 1}
        ).sort("smart_onboarded_at", -1).limit(limit)
        async for d in cur:
            email = (d.get("email") or "").lower()
            if email in seen_emails or email in FOUNDER_EMAILS:
                continue
            seen_emails.add(email)
            rows.append({
                "email": email,
                "business_id": d.get("business_id") or "—",
                "full_name": d.get("full_name") or "",
                "company_name": d.get("company_name") or "",
                "city": d.get("city") or "",
                "industry": d.get("industry") or "",
                "phone": d.get("phone") or "",
                "website": d.get("website") or "",
                "plan": d.get("plan") or "free",
                "wizard_complete": bool(str(d.get("onboarding_wizard_complete")).lower() in ("true", "1")),
                "google_oauth": bool(d.get("google_oauth")),
                "active": str(d.get("business_id_active")).lower() in ("true", "1"),
                "joined_at": str(d.get("smart_onboarded_at") or d.get("created_at") or "—")[:19],
                "source": "platform_users",
            })
    except Exception as e:
        logger.warning(f"[CUST] list failed: {e}")
    return {"ok": True, "count": len(rows), "customers": rows}


# ─────────────────────────────────────────────────────────────
# CLEANUP — wipe everything except founder accounts
# ─────────────────────────────────────────────────────────────
class CleanupRequest(BaseModel):
    confirm: str  # must equal "WIPE"
    keep_pixel_keys: bool = True


@router.post("/cleanup")
async def cleanup_non_founder(request: Request, body: CleanupRequest):
    founder = _require_founder(request)
    if body.confirm != "WIPE":
        raise HTTPException(400, "confirm must be 'WIPE'")
    if _db is None:
        raise HTTPException(503, "DB unavailable")

    report: Dict[str, int] = {}
    keep = list(FOUNDER_EMAILS)
    for col in CUSTOMER_COLLECTIONS:
        try:
            res = await _db[col].delete_many({"email": {"$nin": keep}})
            if res.deleted_count:
                report[col] = res.deleted_count
        except Exception as e:
            logger.warning(f"[CUST] cleanup {col}: {e}")

    # Also remove orphan tenant_id-scoped data for non-founder tenants
    try:
        tenants_to_keep = ["aurem_platform", "system", "aurem_internal"]
        for col in ["bin_audit_log", "ora_command_log", "campaign_leads"]:
            try:
                res = await _db[col].delete_many(
                    {"tenant_id": {"$nin": tenants_to_keep},
                     "email": {"$nin": keep}})
                if res.deleted_count:
                    report[col] = report.get(col, 0) + res.deleted_count
            except Exception:
                pass
    except Exception:
        pass

    # API keys: keep them (so pixel re-link possible) unless user says no
    if not body.keep_pixel_keys:
        try:
            res = await _db.api_keys.delete_many({"owner_email": {"$nin": keep, "$regex": ".+"}})
            if res.deleted_count:
                report["api_keys"] = res.deleted_count
        except Exception:
            pass

    # Audit
    try:
        await _db.founder_audit.insert_one({
            "action": "cleanup_non_founder",
            "by": founder.get("email") or founder.get("user_id"),
            "at": datetime.now(timezone.utc).isoformat(),
            "report": report,
            "keep_pixel_keys": body.keep_pixel_keys,
        })
    except Exception:
        pass

    return {"ok": True, "deleted": report,
            "founders_preserved": list(FOUNDER_EMAILS),
            "total_deleted": sum(report.values())}


# ─────────────────────────────────────────────────────────────
# REONBOARD — fresh BIN for returning email
# ─────────────────────────────────────────────────────────────
class ReonboardRequest(BaseModel):
    email: EmailStr
    full_name: Optional[str] = ""
    company_name: Optional[str] = ""
    website: Optional[str] = ""
    city: Optional[str] = ""
    industry: Optional[str] = ""
    phone: Optional[str] = ""
    relink_existing_pixel: bool = True


@router.post("/reonboard-bin")
async def reonboard_bin(request: Request, body: ReonboardRequest):
    founder = _require_founder(request)
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    email = body.email.lower()
    if email in FOUNDER_EMAILS:
        raise HTTPException(400, "Cannot re-onboard a founder account")

    # Wipe any prior records for this email (clean slate)
    for col in CUSTOMER_COLLECTIONS:
        try:
            await _db[col].delete_many({"email": email})
        except Exception:
            pass

    # Generate fresh BIN
    from services.bin_generator import generate_bin
    new_bin = generate_bin(industry=body.industry, city=body.city)

    # Find any pre-existing pixel API key linked to this email/website
    existing_key = None
    if body.relink_existing_pixel:
        try:
            existing_key = await _db.api_keys.find_one(
                {"$or": [
                    {"owner_email": {"$regex": f"^{email}$", "$options": "i"}},
                    {"website": {"$regex": (body.website or "x").replace(".", r"\."), "$options": "i"}},
                ]},
                {"_id": 0},
            )
        except Exception:
            existing_key = None

    tenant_id = f"cust-{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc).isoformat()

    pu_doc = {
        "email": email,
        "business_id": new_bin,
        "business_id_active": True,
        "full_name": body.full_name or "",
        "company_name": body.company_name or "",
        "website": body.website or "",
        "city": body.city or "",
        "industry": body.industry or "",
        "phone": body.phone or "",
        "role": "user",
        "tenant_id": tenant_id,
        "must_set_password": True,
        "onboarding_wizard_complete": False,
        "smart_onboarded_at": now,
        "created_at": now,
        "reonboarded_by": founder.get("email") or "founder",
        "linked_pixel_key": existing_key.get("key") if existing_key else None,
    }
    await _db.platform_users.insert_one(pu_doc)

    # If there was an existing pixel key, re-link it to the new BIN/tenant
    if existing_key:
        try:
            await _db.api_keys.update_one(
                {"key": existing_key["key"]},
                {"$set": {
                    "business_id": new_bin,
                    "tenant_id": tenant_id,
                    "owner_email": email,
                    "relinked_at": now,
                    "is_active": True,
                }},
            )
        except Exception as e:
            logger.warning(f"[CUST] pixel relink failed: {e}")

    # Audit
    try:
        await _db.founder_audit.insert_one({
            "action": "reonboard_bin",
            "by": founder.get("email") or founder.get("user_id"),
            "at": now,
            "email": email,
            "new_bin": new_bin,
            "linked_pixel_key": existing_key.get("key") if existing_key else None,
        })
    except Exception:
        pass

    return {
        "ok": True,
        "email": email,
        "business_id": new_bin,
        "tenant_id": tenant_id,
        "linked_pixel_key": existing_key.get("key") if existing_key else None,
        "must_set_password": True,
    }


# ─────────────────────────────────────────────────────────────
# RELINK PIXEL — bind existing pixel API key to a fresh account
# ─────────────────────────────────────────────────────────────
class RelinkPixelRequest(BaseModel):
    pixel_key: str
    new_email: EmailStr
    new_business_id: Optional[str] = None
    website: Optional[str] = ""


@router.post("/relink-pixel")
async def relink_pixel(request: Request, body: RelinkPixelRequest):
    founder = _require_founder(request)
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    key_doc = await _db.api_keys.find_one({"key": body.pixel_key}, {"_id": 0})
    if not key_doc:
        raise HTTPException(404, f"Pixel API key not found: {body.pixel_key}")
    bid = body.new_business_id or key_doc.get("business_id") or ""
    upd = {
        "owner_email": body.new_email.lower(),
        "business_id": bid,
        "website": body.website or key_doc.get("website") or "",
        "is_active": True,
        "relinked_at": datetime.now(timezone.utc).isoformat(),
        "relinked_by": founder.get("email") or "founder",
    }
    await _db.api_keys.update_one({"key": body.pixel_key}, {"$set": upd})
    return {"ok": True, "key": body.pixel_key, "linked_to": upd}
