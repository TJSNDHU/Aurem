"""
billing_plan_router.py — Base plan subscribe / upgrade / cancel endpoints.
═══════════════════════════════════════════════════════════════════════════
  POST /api/billing/plan/subscribe {plan: "growth"}
       → Creates a Stripe Checkout session for the chosen base plan.
       → Caller must already have a BIN (signup flow guarantees this).
       → On payment success, the existing canonical Stripe webhook calls
         plan_resolver.recompute_services_unlocked(business_id).

  POST /api/billing/plan/upgrade   {new_plan: "pro"}
       → Updates the existing Stripe subscription with proration.

  POST /api/billing/plan/cancel
       → Schedules subscription cancellation at period end (NEVER immediate;
         keeps customer in good standing for the rest of their billing cycle).

  GET  /api/billing/plan/state
       → Live plan + services_unlocked + limits + status. Bypasses JWT
         cache and reads via plan_resolver.get_plan_state — useful after
         any plan change so the UI reloads fresh state.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from aurem_config.plans import PLANS
from middleware.bin_context import get_bin_ctx
from services.plan_resolver import get_plan_state, recompute_services_unlocked

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(db):
    global _db
    _db = db


class SubscribeReq(BaseModel):
    plan: str
    origin_url: Optional[str] = None


class UpgradeReq(BaseModel):
    new_plan: str


def _get_stripe_key() -> Optional[str]:
    return os.environ.get("STRIPE_SECRET_KEY")


@router.get("/api/billing/plan/state")
async def plan_state(request: Request):
    ctx = get_bin_ctx(request, required=True)
    if _db is None:
        raise HTTPException(503, "db not ready")
    return await get_plan_state(_db, ctx.business_id)


@router.post("/api/billing/plan/subscribe")
async def plan_subscribe(body: SubscribeReq, request: Request):
    ctx = get_bin_ctx(request, required=True)
    if body.plan not in PLANS or body.plan in ("trial", "lifetime_free"):
        raise HTTPException(400, "invalid plan")
    if _db is None:
        raise HTTPException(503, "db not ready")

    plan = PLANS[body.plan]
    api_key = _get_stripe_key()
    if not api_key:
        raise HTTPException(503, "Stripe not configured")

    # Resolve Stripe Price ID from env (set per plan in deployment)
    stripe_price_id = os.environ.get(plan["stripe_price_env"], "")
    if not stripe_price_id:
        raise HTTPException(503, f"Stripe price not configured for plan '{body.plan}'")

    try:
        import stripe as stripe_lib
        stripe_lib.api_key = api_key

        # Find or create Stripe customer
        billing = await _db.aurem_billing.find_one({"business_id": ctx.business_id}, {"_id": 0})
        cust_id = (billing or {}).get("stripe_customer_id")
        if not cust_id:
            cust = stripe_lib.Customer.create(email=ctx.email, metadata={"business_id": ctx.business_id})
            cust_id = cust.id
            await _db.aurem_billing.update_one(
                {"business_id": ctx.business_id},
                {"$set": {"stripe_customer_id": cust_id, "email": ctx.email}},
                upsert=True,
            )

        success_base = body.origin_url or "https://aurem.live"
        session = stripe_lib.checkout.Session.create(
            mode="subscription",
            customer=cust_id,
            line_items=[{"price": stripe_price_id, "quantity": 1}],
            metadata={
                "business_id": ctx.business_id,
                "plan": body.plan,
                "kind": "base_plan",
            },
            success_url=f"{success_base}/my/billing?status=ok&plan={body.plan}",
            cancel_url=f"{success_base}/my/billing?status=cancelled",
            allow_promotion_codes=True,
        )
        return {"ok": True, "checkout_url": session.url, "session_id": session.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[billing/plan/subscribe] failed: {e}")
        raise HTTPException(500, f"Stripe checkout failed: {e}")


@router.post("/api/billing/plan/upgrade")
async def plan_upgrade(body: UpgradeReq, request: Request):
    ctx = get_bin_ctx(request, required=True)
    if body.new_plan not in PLANS or body.new_plan in ("trial", "lifetime_free"):
        raise HTTPException(400, "invalid plan")
    if _db is None:
        raise HTTPException(503, "db not ready")
    api_key = _get_stripe_key()
    if not api_key:
        raise HTTPException(503, "Stripe not configured")

    billing = await _db.aurem_billing.find_one({"business_id": ctx.business_id}, {"_id": 0})
    sub_id = (billing or {}).get("stripe_subscription_id")
    if not sub_id:
        raise HTTPException(400, "no active subscription to upgrade — use /subscribe first")

    new_price = os.environ.get(PLANS[body.new_plan]["stripe_price_env"], "")
    if not new_price:
        raise HTTPException(503, f"Stripe price not configured for '{body.new_plan}'")

    try:
        import stripe as stripe_lib
        stripe_lib.api_key = api_key
        sub = stripe_lib.Subscription.retrieve(sub_id)
        item_id = sub["items"]["data"][0]["id"]
        stripe_lib.Subscription.modify(
            sub_id,
            items=[{"id": item_id, "price": new_price}],
            proration_behavior="create_prorations",
            metadata={"business_id": ctx.business_id, "plan": body.new_plan, "kind": "base_plan"},
        )
        await _db.aurem_billing.update_one(
            {"business_id": ctx.business_id},
            {"$set": {"plan": body.new_plan, "plan_changed_at": _iso_now()}},
        )
        await recompute_services_unlocked(_db, ctx.business_id)
        return {"ok": True, "plan": body.new_plan}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[billing/plan/upgrade] failed: {e}")
        raise HTTPException(500, f"Stripe upgrade failed: {e}")


@router.post("/api/billing/plan/cancel")
async def plan_cancel(request: Request):
    ctx = get_bin_ctx(request, required=True)
    if _db is None:
        raise HTTPException(503, "db not ready")
    api_key = _get_stripe_key()
    if not api_key:
        raise HTTPException(503, "Stripe not configured")

    billing = await _db.aurem_billing.find_one({"business_id": ctx.business_id}, {"_id": 0})
    sub_id = (billing or {}).get("stripe_subscription_id")
    if not sub_id:
        raise HTTPException(400, "no active subscription to cancel")

    try:
        import stripe as stripe_lib
        stripe_lib.api_key = api_key
        stripe_lib.Subscription.modify(sub_id, cancel_at_period_end=True)
        await _db.aurem_billing.update_one(
            {"business_id": ctx.business_id},
            {"$set": {"cancel_scheduled": True, "cancel_scheduled_at": _iso_now()}},
        )
        return {"ok": True, "cancel_at_period_end": True}
    except Exception as e:
        logger.exception(f"[billing/plan/cancel] failed: {e}")
        raise HTTPException(500, f"Stripe cancel failed: {e}")


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
