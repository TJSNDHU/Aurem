"""
Customer 360 View — Iteration 208
==================================
Single admin endpoint that aggregates every surface of a customer's data
into one response. Powers the `/dashboard` → Customer 360 screen.

GET /api/admin/customer-360/{identifier}
  identifier = email OR business_id (BIN in either 3+3+4 or 4+4 format)

Returns:
    {
      identity:          { platform_user, users_legacy, tenant_customer },
      workspace:         aurem_workspaces doc,
      pricing_plan:      from tenant_customer,
      pixel:             { key_info, connected, last_ping, events_24h, total_hits },
      scan_history:      [recent scans],
      referrals:         { referred_count, rewards },
      bin_history:       { current, previous, synced_at },
      login_history:     [recent audit_chain login events],
      onboarding_state:  { smart, first_login },
      subscription:      stripe metadata if present
    }
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/customer-360", tags=["Customer 360"])

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

_db = None


def set_db(db):
    global _db
    _db = db


async def _require_admin(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = payload.get("role", "")
    if role in ("admin", "super_admin") or payload.get("is_admin") or payload.get("is_super_admin"):
        return payload
    raise HTTPException(403, "Admin only")


def _get_db():
    if _db is None:
        raise HTTPException(503, "DB not available")
    return _db


def _scrub(doc: Optional[dict]) -> Optional[dict]:
    """Remove sensitive + binary fields before returning to admin."""
    if not doc:
        return None
    d = dict(doc)
    d.pop("_id", None)
    d.pop("password_hash", None)
    d.pop("password", None)
    d.pop("api_key_hash", None)
    return d


async def _resolve_identity(db, identifier: str) -> Dict[str, Any]:
    """Locate the customer by email OR BIN across collections."""
    ident = (identifier or "").strip()
    if not ident:
        return {}

    from services.bin_generator import is_bin, normalize_bin

    lookup_email: Optional[str] = None

    if is_bin(ident):
        bid = normalize_bin(ident)
        # Try platform_users first
        u = await db.platform_users.find_one({"business_id": bid}) \
            or await db.users.find_one({"business_id": bid}) \
            or await db.tenant_customers.find_one({"business_id": bid})
        if u:
            lookup_email = (u.get("email") or "").lower()
    else:
        lookup_email = ident.lower()

    if not lookup_email:
        return {}

    pu = await db.platform_users.find_one({"email": {"$regex": f"^{lookup_email}$", "$options": "i"}})
    ul = await db.users.find_one({"email": {"$regex": f"^{lookup_email}$", "$options": "i"}})
    tc = await db.tenant_customers.find_one({"email": {"$regex": f"^{lookup_email}$", "$options": "i"}})

    return {
        "email":          lookup_email,
        "platform_user":  _scrub(pu),
        "users_legacy":   _scrub(ul),
        "tenant_customer":_scrub(tc),
    }


async def _workspace(db, email: str, business_id: Optional[str]) -> Optional[dict]:
    q: Dict[str, Any] = {}
    if email:
        q = {"$or": [
            {"owner_email": {"$regex": f"^{email}$", "$options": "i"}},
            {"email": {"$regex": f"^{email}$", "$options": "i"}},
        ]}
    ws = await db.aurem_workspaces.find_one(q, {"_id": 0}) if q else None
    if not ws and business_id:
        ws = await db.aurem_workspaces.find_one(
            {"$or": [{"business_id": business_id}, {"owner_id": business_id}]},
            {"_id": 0},
        )
    return ws


async def _pixel_info(db, email: str) -> Dict[str, Any]:
    """Find the customer's API key + live pixel stats."""
    # Keys can use either `email` or `owner_email` field. Also support case-insensitive match.
    key_doc = await db.api_keys.find_one(
        {"$or": [
            {"email": {"$regex": f"^{email}$", "$options": "i"}},
            {"owner_email": {"$regex": f"^{email}$", "$options": "i"}},
        ]},
        {"_id": 0, "api_key_hash": 0, "key": 0},   # never leak raw key
    )
    if not key_doc:
        return {"has_key": False}

    tenant_id = key_doc.get("tenant_id") or ""
    d24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    events_24h = await db.pixel_events.count_documents(
        {"tenant_id": tenant_id, "received_at": {"$gte": d24}}
    ) if tenant_id else 0
    total_hits = int(key_doc.get("hit_count") or key_doc.get("usage_count") or 0)
    last_ping = key_doc.get("last_ping") or key_doc.get("last_used") or key_doc.get("last_seen") or ""

    last_event = await db.pixel_events.find(
        {"tenant_id": tenant_id}, {"_id": 0, "received_at": 1, "url": 1, "event": 1},
    ).sort("received_at", -1).limit(1).to_list(1) if tenant_id else []

    return {
        "has_key": True,
        "key_preview": key_doc.get("key_preview") or "",
        "tenant_id": tenant_id,
        "active": bool(key_doc.get("active", key_doc.get("is_active", True))),
        "connected": bool(last_event) or total_hits > 0,
        "last_ping": last_ping,
        "events_24h": events_24h,
        "total_hits": total_hits,
    }


async def _scan_history(db, tenant_id: str, email: str, limit: int = 5) -> List[dict]:
    q: Dict[str, Any] = {}
    if tenant_id:
        q = {"tenant_id": tenant_id}
    elif email:
        q = {"email": {"$regex": f"^{email}$", "$options": "i"}}
    if not q:
        return []
    try:
        cursor = db.scan_history.find(q, {"_id": 0}).sort("scanned_at", -1).limit(limit)
        return await cursor.to_list(limit)
    except Exception:
        return []


async def _referrals(db, email: str) -> Dict[str, Any]:
    try:
        referred_count = await db.customer_referrals.count_documents(
            {"referrer_email": {"$regex": f"^{email}$", "$options": "i"}}
        )
        rewards = await db.customer_referrals.aggregate([
            {"$match": {"referrer_email": {"$regex": f"^{email}$", "$options": "i"}}},
            {"$group": {"_id": None, "total_rewards": {"$sum": "$reward_months"}}},
        ]).to_list(1)
        total_rewards = (rewards[0]["total_rewards"] if rewards else 0)
        return {"referred_count": referred_count, "reward_months": total_rewards}
    except Exception:
        return {"referred_count": 0, "reward_months": 0}


async def _login_history(db, email: str, limit: int = 10) -> List[dict]:
    try:
        cursor = db.audit_chain.find(
            {
                "email": {"$regex": f"^{email}$", "$options": "i"},
                "event_type": {"$regex": "login|auth", "$options": "i"},
            },
            {"_id": 0, "event_type": 1, "timestamp": 1, "ip": 1, "success": 1},
        ).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(limit)
    except Exception:
        return []


@router.get("/health")
async def health():
    return {"status": "ok", "service": "customer-360"}


@router.get("/{identifier}")
async def customer_360(identifier: str, request: Request):
    """
    Single aggregator endpoint for the 360° customer screen.
    `identifier` = email address OR BIN in either format.
    """
    await _require_admin(request)
    db = _get_db()

    identity = await _resolve_identity(db, identifier)
    if not identity or not identity.get("email"):
        raise HTTPException(404, f"Customer not found: {identifier}")

    email = identity["email"]
    pu = identity.get("platform_user") or {}
    tc = identity.get("tenant_customer") or {}

    business_id = pu.get("business_id") or tc.get("business_id") or ""
    workspace = await _workspace(db, email, business_id) or {}
    pixel = await _pixel_info(db, email)
    tenant_id = pixel.get("tenant_id") or workspace.get("owner_id") or ""

    scans = await _scan_history(db, tenant_id, email)
    referrals = await _referrals(db, email)
    logins = await _login_history(db, email)

    # Onboarding state
    onboarding_state = {
        "smart_complete":   bool(pu.get("smart_onboarding_complete")),
        "smart_onboarded_at": pu.get("smart_onboarded_at") or "",
        "wizard_complete":  bool(pu.get("onboarding_wizard_complete")),
        "wizard_step":      int(pu.get("onboarding_wizard_step") or 0),
        "platform_detected":pu.get("onboarded_platform") or "",
    }

    # Subscription / plan
    pricing_plan = {
        "plan":          tc.get("plan") or pu.get("plan_status") or "",
        "plan_started_at": tc.get("plan_started_at") or workspace.get("plan_started_at") or "",
        "mrr":           tc.get("mrr") or tc.get("monthly_revenue") or 0,
        "joined_date":   tc.get("joined_date") or "",
        "status":        tc.get("status") or workspace.get("status") or "",
        "stripe_customer_id": workspace.get("stripe_customer_id") or tc.get("stripe_customer_id") or "",
        "stripe_subscription_id": workspace.get("stripe_subscription_id") or "",
    }

    # BIN history
    bin_history = {
        "current": business_id,
        "previous": pu.get("bin_previous") or "",
        "synced_at": pu.get("bin_synced_at") or "",
    }

    return {
        "identifier_requested": identifier,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity": identity,
        "workspace": workspace,
        "pricing_plan": pricing_plan,
        "pixel": pixel,
        "scan_history": scans,
        "referrals": referrals,
        "onboarding_state": onboarding_state,
        "bin_history": bin_history,
        "login_history": logins,
    }
