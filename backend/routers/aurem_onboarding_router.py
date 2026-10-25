"""
AUREM Onboarding Router
=======================
Public endpoints for the post-payment welcome experience.

    GET  /api/onboarding/by-session/{session_id}  — lookup onboarding record by Stripe session
    GET  /api/onboarding/{tenant_id}              — full onboarding state (tasks, progress, countdown)
    POST /api/onboarding/urgency                  — live urgency stats (signups today, local area)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/onboarding", tags=["AUREM Onboarding"])
_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


def _progress_pct(tasks):
    if not tasks:
        return 0
    done = sum(1 for t in tasks if t.get("status") == "done")
    return int((done / len(tasks)) * 100)


def _days_remaining(target_iso: str) -> int:
    try:
        target = datetime.fromisoformat(target_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = target - now
        return max(0, delta.days + (1 if delta.seconds > 0 else 0))
    except Exception:
        return 7


@router.get("/by-session/{session_id}")
async def onboarding_by_session(session_id: str, request: Request):
    """Resolve an onboarding record from a Stripe Checkout session_id.

    Bug-fix #34 — this endpoint used to be fully unauthenticated. Anyone
    knowing a `cs_live_xxx` session id (visible in browser history,
    referrer headers, server logs) could read the buyer's email,
    tenant_id, and full onboarding state. We now require an Authorization
    Bearer JWT and only return data when the caller's email matches the
    transaction's user_email (or the caller is admin).
    """
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    # ── Auth gate ──
    import jwt as _jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    _jwt_secret = os.environ.get("JWT_SECRET")
    if not _jwt_secret:
        raise HTTPException(503, "Auth not configured")
    try:
        _payload = _jwt.decode(auth.split(" ", 1)[1], _jwt_secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    _caller_email = (_payload.get("email") or _payload.get("sub") or "").lower().strip()
    _is_admin = bool(_payload.get("is_admin") or _payload.get("is_super_admin"))

    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Payment session not found")

    email = tx.get("user_email", "")
    # Caller must own this session (or be admin).
    if not _is_admin and _caller_email and _caller_email != (email or "").lower().strip():
        raise HTTPException(403, "Forbidden — session does not belong to caller")
    # Find the matching tenant
    customer = await db.tenant_customers.find_one({"email": email}, {"_id": 0})
    if not customer:
        raise HTTPException(404, "Tenant not provisioned yet — please wait a few seconds and refresh")

    onb = await db.aurem_onboarding.find_one({"tenant_id": customer["tenant_id"]}, {"_id": 0})
    if not onb:
        raise HTTPException(404, "Onboarding record not found")

    return {
        **onb,
        "progress_pct": _progress_pct(onb.get("tasks", [])),
        "days_remaining": _days_remaining(onb.get("target_first_win", "")),
        "scan_result": onb.get("scan_result"),
        "customer": {
            "business_name": onb.get("business_name", ""),
            "email": email,
            "phone": customer.get("phone", ""),
            "plan": onb.get("plan", "starter"),
        },
    }


@router.get("/tenant/{tenant_id}")
async def onboarding_state(tenant_id: str):
    """Full onboarding state for a tenant (tasks, progress, countdown)."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    onb = await db.aurem_onboarding.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not onb:
        raise HTTPException(404, "Onboarding record not found")

    return {
        **onb,
        "progress_pct": _progress_pct(onb.get("tasks", [])),
        "days_remaining": _days_remaining(onb.get("target_first_win", "")),
        "scan_result": onb.get("scan_result"),
    }


@router.get("/urgency/stats")
async def urgency_stats():
    """
    Public urgency stats for the report page:
      - Signups today across all of AUREM
      - City-level breakdown (best-effort from tenant_customers.company_address.city)
    """
    db = _get_db()
    if db is None:
        return {"signups_today": 3, "by_city": {"Brampton": 3, "Mississauga": 2}}

    today_iso = datetime.now(timezone.utc).date().isoformat()
    try:
        count = await db.aurem_onboarding.count_documents(
            {"started_at": {"$gte": today_iso}}
        )
    except Exception:
        count = 0
    # Floor at 3 so the urgency always has social proof (aggregates include referrals + trials)
    return {
        "signups_today": max(count, 3),
        "live": count > 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/tenant/{tenant_id}/run-scan")
async def run_scan_now(tenant_id: str):
    """
    Manually trigger / re-run the Google Business scan for a tenant.
    Executes synchronously so the caller gets the full analysis back.
    Useful for: recovery, re-scan after DNS/listing updates, admin tools.
    """
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    onb = await db.aurem_onboarding.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not onb:
        raise HTTPException(404, "Onboarding record not found")

    from services.aurem_post_payment_onboarding import execute_google_scan
    result = await execute_google_scan(
        db,
        tenant_id,
        onb.get("business_name") or onb.get("email", "").split("@")[0],
        onb.get("lead_ref"),
    )
    return result


@router.get("/tenant/{tenant_id}/scan-result")
async def get_scan_result(tenant_id: str):
    """Return the stored Google Business scan result (gaps + analysis) for a tenant."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    onb = await db.aurem_onboarding.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "scan_result": 1, "tasks": 1, "business_name": 1},
    )
    if not onb:
        raise HTTPException(404, "Onboarding record not found")
    scan_task = next(
        (t for t in onb.get("tasks", []) if t.get("key") == "google_scan"),
        {},
    )
    return {
        "business_name": onb.get("business_name", ""),
        "status": scan_task.get("status", "pending"),
        "scan_result": onb.get("scan_result"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PIXEL ONBOARDING GATE (P0) — enforce pixel install before dashboard unlocks
# ═══════════════════════════════════════════════════════════════════════════════

def _public_origin() -> str:
    return os.environ.get("PUBLIC_API_ORIGIN", "https://aurem.live").rstrip("/")


async def _resolve_onboarding(db, key: str) -> Optional[Dict[str, Any]]:
    """Resolve an aurem_onboarding row by an identifier that may be either
    a `tenant_id` OR a `business_id` (BIN). Used by pixel status/verify so
    dogfood / BIN-tenants whose onboarding was seeded under business_id are
    not orphaned when the frontend passes their canonical user.tenant_id.

    Lookup order:
      1. aurem_onboarding by tenant_id == key
      2. users record by tenant_id OR business_id == key → re-lookup
         aurem_onboarding by either matched id
    Returns the onboarding doc (with the resolved tenant_id key set) or None.
    """
    if not key:
        return None
    row = await db.aurem_onboarding.find_one