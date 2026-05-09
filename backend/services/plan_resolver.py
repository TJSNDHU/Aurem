"""
plan_resolver.py — Single source of truth for "what plan + services does
this BIN currently have access to?"
═══════════════════════════════════════════════════════════════════════════
Replaces the 3 fragmented systems (plan_enforcement, subscription_manager,
usage_metering_service) with ONE function: `get_plan_state(business_id)`.

State sources (merged in order):
  1. platform_users.plan + lifetime_free flag → base plan
  2. customer_subscriptions where status=active → à-la-carte add-ons
  3. trial state (if active and not expired) overrides plan to "trial"

Computed `services_unlocked` = base plan bundle ∪ active add-ons.
Wildcard ["*"] short-circuits everything (lifetime_free / enterprise).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aurem_config.plans import PLANS, has_wildcard

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_trial_active(billing: Dict[str, Any]) -> bool:
    """Trial is active if status=trialing AND trial_ends_at > now."""
    if (billing or {}).get("status") != "trialing":
        return False
    ends = billing.get("trial_ends_at")
    if not ends:
        return False
    try:
        if isinstance(ends, str):
            ends_dt = datetime.fromisoformat(ends.replace("Z", "+00:00"))
        else:
            ends_dt = ends
        if ends_dt.tzinfo is None:
            ends_dt = ends_dt.replace(tzinfo=timezone.utc)
        return ends_dt > datetime.now(timezone.utc)
    except Exception:
        return False


async def get_plan_state(db, business_id: str) -> Dict[str, Any]:
    """Resolve the current plan + services_unlocked + limits + status for a BIN.

    Returns:
      {
        "business_id": str,
        "plan": "trial|starter|growth|pro|enterprise|lifetime_free",
        "services_unlocked": [str],          # merged bundle, may be ["*"]
        "addons": [str],                     # active à-la-carte add-on service_ids
        "limits": dict,                      # quota caps
        "subscription_status": str,          # trialing|active|past_due|cancelled|trial_expired|suspended
        "trial_ends_at": str | None,
        "current_period_end": str | None,
      }
    """
    if db is None or not business_id:
        return _default_state(business_id)

    plat = await db.platform_users.find_one(
        {"business_id": business_id},
        {"_id": 0, "plan": 1, "lifetime_free": 1, "lifetime": 1, "founder": 1, "tier": 1, "email": 1},
    )
    if not plat:
        # Try email fallback (in case BIN not yet propagated)
        return _default_state(business_id)

    # Lifetime-free shortcut (founder / dogfood)
    if plat.get("lifetime_free") or plat.get("founder"):
        lf = PLANS["lifetime_free"]
        return {
            "business_id": business_id,
            "plan": "lifetime_free",
            "services_unlocked": list(lf["services"]),
            "addons": [],
            "limits": dict(lf["limits"]),
            "subscription_status": "lifetime_active",
            "trial_ends_at": None,
            "current_period_end": None,
        }

    billing = await db.aurem_billing.find_one(
        {"business_id": business_id}, {"_id": 0}
    ) or {}

    # Determine effective plan id
    plan_id = plat.get("plan") or billing.get("plan") or "trial"
    if plan_id not in PLANS:
        plan_id = "trial"

    # Trial active gating
    if plan_id == "trial" and not _is_trial_active(billing):
        plan_id = "trial_expired"

    # Pull active add-ons
    addons: List[str] = []
    try:
        async for s in db.customer_subscriptions.find(
            {"$or": [{"tenant_bin": business_id}, {"business_id": business_id}],
             "status": "active"},
            {"_id": 0, "service_id": 1},
        ):
            sid = s.get("service_id")
            if sid:
                addons.append(sid)
    except Exception as e:
        logger.debug(f"[plan_resolver] addon fetch failed: {e}")

    # Compute services_unlocked
    if plan_id == "trial_expired":
        services_unlocked: List[str] = list(set(addons))  # only paid add-ons survive
        limits = {"leads_limit": 0, "email_limit": 0, "sms_limit": 0,
                  "voice_limit": 0, "campaigns_limit": 0, "agents_limit": 0,
                  "websites_limit": 0, "ai_calls_limit": 0}
        sub_status = "trial_expired"
    else:
        plan = PLANS[plan_id]
        if has_wildcard(plan["services"]):
            services_unlocked = ["*"]
        else:
            services_unlocked = sorted(set(list(plan["services"]) + addons))
        limits = dict(plan["limits"])
        sub_status = billing.get("status") or ("trialing" if plan_id == "trial" else "active")

    return {
        "business_id": business_id,
        "plan": plan_id,
        "services_unlocked": services_unlocked,
        "addons": addons,
        "limits": limits,
        "subscription_status": sub_status,
        "trial_ends_at": billing.get("trial_ends_at"),
        "current_period_end": billing.get("current_period_end"),
    }


def _default_state(business_id: str) -> Dict[str, Any]:
    return {
        "business_id": business_id or "",
        "plan": "none",
        "services_unlocked": [],
        "addons": [],
        "limits": {},
        "subscription_status": "no_account",
        "trial_ends_at": None,
        "current_period_end": None,
    }


async def recompute_services_unlocked(db, business_id: str) -> Dict[str, Any]:
    """Recompute and PERSIST services_unlocked + limits + plan onto platform_users.
    Called by Stripe webhooks and trial transitions so JWT-cached state stays
    fresh without a DB read on every request."""
    state = await get_plan_state(db, business_id)
    if db is not None and business_id:
        try:
            await db.platform_users.update_one(
                {"business_id": business_id},
                {"$set": {
                    "plan": state["plan"],
                    "services_unlocked": state["services_unlocked"],
                    "usage_limits": state["limits"],
                    "subscription_status": state["subscription_status"],
                    "plan_resolved_at": _now_iso(),
                }},
            )
        except Exception as e:
            logger.warning(f"[plan_resolver] persist failed for {business_id}: {e}")
    return state
