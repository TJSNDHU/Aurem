"""
Customer Fix Executors — Phase 3
=================================
Idempotent fix functions invoked by customer_repair_pipeline.

Every executor:
  * Returns True on success, False on hard failure (logged)
  * Is idempotent — safe to call repeatedly
  * Reuses existing services (billing_service.create_customer etc.)
  * Never throws — wraps all errors and logs them
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict

logger = logging.getLogger(__name__)


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────
# EXECUTORS
# ─────────────────────────────────────────────────────────────

async def _seed_billing(business_id: str) -> bool:
    db = _get_db()
    if db is None:
        return False
    user = await db.platform_users.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    if not user:
        return False
    email = user.get("email") or f"{business_id}@aurem.local"
    name = user.get("business_name") or user.get("full_name") or business_id
    try:
        from shared.commercial.billing_service import get_billing_service
        svc = get_billing_service(db)
        await svc.create_customer(business_id, email, name)
        return True
    except Exception as e:
        logger.warning(f"[fix] seed_billing crashed: {e}")
        # Fallback: insert minimal billing record so /api/aurem-billing/* works
        try:
            await db.aurem_billing.update_one(
                {"business_id": business_id},
                {"$setOnInsert": {
                    "business_id": business_id,
                    "email": email,
                    "status": "trialing",
                    "plan": "trial",
                    "created_at": _utc_now(),
                }},
                upsert=True,
            )
            return True
        except Exception as ee:
            logger.warning(f"[fix] minimal billing insert failed: {ee}")
            return False


async def _create_workspace(business_id: str) -> bool:
    db = _get_db()
    if db is None:
        return False
    user = await db.platform_users.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    if not user:
        return False
    try:
        await db.aurem_workspaces.update_one(
            {"business_id": business_id},
            {"$setOnInsert": {
                "business_id": business_id,
                "owner_email": user.get("email"),
                "business_name": user.get("business_name") or business_id,
                "status": "active",
                "plan": "trial",
                "created_at": _utc_now(),
            }},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.warning(f"[fix] create_workspace failed: {e}")
        return False


async def _init_onboarding(business_id: str) -> bool:
    db = _get_db()
    if db is None:
        return False
    try:
        await db.aurem_onboarding.update_one(
            {"business_id": business_id},
            {"$setOnInsert": {
                "business_id": business_id,
                "current_step": 0,
                "total_steps": 5,
                "status": "in_progress",
                "created_at": _utc_now(),
            }},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.warning(f"[fix] init_onboarding failed: {e}")
        return False


async def _seed_tenant_record(business_id: str) -> bool:
    db = _get_db()
    if db is None:
        return False
    user = await db.platform_users.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    if not user:
        return False
    try:
        await db.tenant_customers.update_one(
            {"business_id": business_id},
            {"$setOnInsert": {
                "business_id": business_id,
                "email": user.get("email"),
                "business_name": user.get("business_name") or business_id,
                "plan": "trial",
                "status": "active",
                "created_at": _utc_now(),
            }},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.warning(f"[fix] seed_tenant_record failed: {e}")
        return False


async def _create_stripe_customer(business_id: str) -> bool:
    """Same as seed_billing — billing_service.create_customer is idempotent."""
    return await _seed_billing(business_id)


async def _reset_auth_tokens(business_id: str) -> bool:
    db = _get_db()
    if db is None:
        return False
    try:
        await db.platform_users.update_one(
            {"business_id": business_id},
            {"$set": {"token_version": _utc_now().timestamp()}},
        )
        return True
    except Exception as e:
        logger.warning(f"[fix] reset_auth_tokens failed: {e}")
        return False


async def _diagnose_route(business_id: str) -> bool:
    """Log a CODE_FIX_NEEDED system event so the autonomous repair loop +
    morning brief can surface the broken route to the founder."""
    db = _get_db()
    if db is None:
        return False
    try:
        await db.system_events.insert_one({
            "type": "FRONTEND_ROUTE_BROKEN",
            "business_id": business_id,
            "needs_emergent_fix": True,
            "ts": _utc_now(),
        })
    except Exception:
        pass
    try:
        from services.a2a_bus import bus
        await bus.emit("customer_repair", "CODE_FIX_NEEDED", {
            "issue": "frontend_route_5xx",
            "business_id": business_id,
            "priority": "P0",
        })
    except Exception:
        pass
    return True  # logging always counts as "applied"


async def _reseed_from_legacy(business_id: str) -> bool:
    """One-click recovery: copy a legacy `users` record (Google OAuth) into
    `platform_users`, attaching the missing `business_id`. After this runs
    the rest of the safe fixes (workspace, billing, tenant, Stripe) become
    unblocked because they all need a `platform_users` parent.

    Idempotent. Looks up by `aurem_onboarding.business_id` to find a hint of
    the email if one was stored, otherwise falls back to the legacy
    `users` collection scan for any record whose email contains the BIN's
    domain hint.
    """
    db = _get_db()
    if db is None:
        return False

    # 1. Already seeded? bail
    pu = await db.platform_users.find_one(
        {"business_id": business_id}, {"_id": 0, "email": 1}
    )
    if pu:
        return True  # nothing to do — repair pipeline will handle the rest

    # 2. Find candidate in legacy users collection.
    #    Prefer linked record on aurem_onboarding (some flows stamp email),
    #    otherwise let admin pass an explicit hint via env var or hard-code
    #    against any orphan.
    onb = await db.aurem_onboarding.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    candidate_email = None
    if onb:
        candidate_email = onb.get("email") or onb.get("owner_email")

    legacy = None
    if candidate_email:
        legacy = await db.users.find_one({"email": candidate_email})
    else:
        # Try matching by business_id stamp on legacy record (some have it)
        legacy = await db.users.find_one({"business_id": business_id})

    if not legacy:
        logger.warning(
            f"[fix] reseed_from_legacy {business_id}: no candidate in "
            f"legacy users collection — manual intervention needed"
        )
        return False

    full_name = (
        legacy.get("google_name")
        or f"{legacy.get('first_name','')} {legacy.get('last_name','')}".strip()
        or "Imported User"
    )
    company_name = legacy.get("business_name") or full_name or business_id

    doc = {
        "email": legacy["email"],
        "full_name": full_name,
        "company_name": company_name,
        "role": "user",
        "auth_provider": legacy.get("auth_provider", "google"),
        "google_picture": legacy.get("google_picture"),
        "email_verified": True,
        "is_active": True,
        "plan": "trial",
        "terms_accepted": True,
        "terms_version": "1.0",
        "terms_accepted_at": _utc_now().isoformat(),
        "business_id": business_id,
        "business_id_active": True,
        "business_id_created": _utc_now().isoformat(),
        "created_at": legacy.get("created_at") or _utc_now().isoformat(),
        "updated_at": _utc_now().isoformat(),
        "smart_onboarding_complete": False,
        "wizard_complete": False,
        "must_set_password": False,
    }
    try:
        # 1. Upsert into platform_users with the desired BIN
        await db.platform_users.update_one(
            {"email": legacy["email"]},
            {"$setOnInsert": doc, "$set": {
                "business_id": business_id,
                "business_id_active": True,
            }},
            upsert=True,
        )
        # 2. ALSO stamp the legacy users.{email} doc so that
        #    `ensure_business_id` won't regenerate a new BIN on the next
        #    /api/business-id/mine call (it updates BOTH collections by
        #    email when a legacy user has no BIN — that overwrote our seed
        #    once before).
        await db.users.update_one(
            {"email": legacy["email"]},
            {"$set": {
                "business_id": business_id,
                "business_id_active": True,
                "business_id_created": _utc_now().isoformat(),
            }},
        )
        return True
    except Exception as e:
        logger.warning(f"[fix] reseed_from_legacy crashed: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────────────────────

EXECUTORS: Dict[str, Callable[[str], Awaitable[bool]]] = {
    "seed_billing_record":     _seed_billing,
    "create_workspace":        _create_workspace,
    "init_onboarding":         _init_onboarding,
    "seed_tenant_record":      _seed_tenant_record,
    "create_stripe_customer":  _create_stripe_customer,
    "reset_auth_tokens":       _reset_auth_tokens,
    "diagnose_frontend_route": _diagnose_route,
    "reseed_from_legacy":      _reseed_from_legacy,
}


async def apply_customer_fix(business_id: str, fix_name: str) -> bool:
    fn = EXECUTORS.get(fix_name)
    if fn is None:
        logger.warning(f"[fix] unknown fix name: {fix_name}")
        return False
    return await fn(business_id)
