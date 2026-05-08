"""
Shopify Billing API Router — Subscription Management via GraphQL
================================================================
Uses Shopify's `appSubscriptionCreate` GraphQL mutation for merchant billing.
This is REQUIRED if charging merchants inside the Shopify ecosystem.

ACTIVATES when: SHOPIFY_API_KEY + shop access_token are available.
SCAFFOLD MODE when: No credentials configured.
"""

import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shopify-billing", tags=["Shopify Billing"])

SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY", "")

_db = None


def set_db(database):
    global _db
    _db = database


# ═══════════════════════════════════════════════════
# PLAN DEFINITIONS (server-side truth)
# ═══════════════════════════════════════════════════

SHOPIFY_PLANS = {
    "starter": {
        "name": "AUREM Starter",
        "price": 49.00,
        "interval": "EVERY_30_DAYS",
        "trial_days": 7,
        "features": ["5 AI Agents", "1,000 ORA Messages/mo", "Basic Analytics", "Email Support"],
        "test": True,  # Use test charges during development
    },
    "professional": {
        "name": "AUREM Professional",
        "price": 149.00,
        "interval": "EVERY_30_DAYS",
        "trial_days": 7,
        "features": ["Unlimited AI Agents", "10,000 ORA Messages/mo", "Advanced Analytics", "Priority Support", "API Access"],
        "test": True,
    },
    "enterprise": {
        "name": "AUREM Enterprise",
        "price": 499.00,
        "interval": "EVERY_30_DAYS",
        "trial_days": 14,
        "features": ["Unlimited Everything", "Dedicated Infrastructure", "Custom Integrations", "24/7 Phone Support", "SLA Guarantee"],
        "test": True,
    },
}


class SubscribeRequest(BaseModel):
    plan_id: str
    shop: str
    return_url: Optional[str] = None


class ConfirmRequest(BaseModel):
    charge_id: str
    shop: str


# ═══════════════════════════════════════════════════
# PLAN LISTING
# ═══════════════════════════════════════════════════

@router.get("/plans")
async def list_shopify_plans():
    """List available Shopify subscription plans."""
    return {
        "plans": [
            {"id": k, **{kk: vv for kk, vv in v.items() if kk != "test"}}
            for k, v in SHOPIFY_PLANS.items()
        ]
    }


# ═══════════════════════════════════════════════════
# CREATE SUBSCRIPTION (appSubscriptionCreate)
# ═══════════════════════════════════════════════════

@router.post("/subscribe")
async def create_subscription(body: SubscribeRequest, request: Request):
    """
    Create a Shopify app subscription using GraphQL appSubscriptionCreate.
    Returns a confirmation_url that the merchant must visit to approve.
    """
    if body.plan_id not in SHOPIFY_PLANS:
        raise HTTPException(400, f"Invalid plan: {body.plan_id}")

    plan = SHOPIFY_PLANS[body.plan_id]
    shop = body.shop

    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"

    # Get access token for this shop
    if _db is None:
        raise HTTPException(500, "Database not available")

    install = await _db.shopify_app_installs.find_one(
        {"shop_domain": shop, "status": "active"}, {"_id": 0}
    )

    if not install or not install.get("access_token") or install["access_token"] == "mock_token":
        # Scaffold mode — return mock confirmation URL
        logger.info(f"[SHOPIFY-BILLING] Scaffold mode — no real access token for {shop}")
        return {
            "mode": "scaffold",
            "message": "Shopify billing requires a real access token. Connect your Shopify Partner app first.",
            "plan": body.plan_id,
            "shop": shop,
            "confirmation_url": None,
            "setup_required": ["SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "Complete OAuth install flow"],
        }

    access_token = install["access_token"]
    return_url = body.return_url or f"https://{shop}/admin/apps"

    # Build GraphQL mutation
    mutation = """
    mutation appSubscriptionCreate($name: String!, $lineItems: [AppSubscriptionLineItemInput!]!, $returnUrl: URL!, $test: Boolean) {
      appSubscriptionCreate(name: $name, lineItems: $lineItems, returnUrl: $returnUrl, test: $test) {
        userErrors {
          field
          message
        }
        confirmationUrl
        appSubscription {
          id
          status
        }
      }
    }
    """

    variables = {
        "name": plan["name"],
        "returnUrl": return_url,
        "test": plan.get("test", True),
        "lineItems": [{
            "plan": {
                "appRecurringPricingDetails": {
                    "price": {"amount": plan["price"], "currencyCode": "USD"},
                    "interval": plan["interval"],
                }
            }
        }],
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://{shop}/admin/api/2026-04/graphql.json",
                json={"query": mutation, "variables": variables},
                headers={
                    "X-Shopify-Access-Token": access_token,
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code != 200:
            logger.error(f"[SHOPIFY-BILLING] GraphQL error: {resp.status_code} {resp.text}")
            raise HTTPException(502, "Shopify API error")

        data = resp.json()
        result = data.get("data", {}).get("appSubscriptionCreate", {})

        if result.get("userErrors"):
            errors = result["userErrors"]
            logger.error(f"[SHOPIFY-BILLING] User errors: {errors}")
            raise HTTPException(400, f"Shopify billing error: {errors[0]['message']}")

        confirmation_url = result.get("confirmationUrl")
        subscription_id = result.get("appSubscription", {}).get("id")

        # Store the pending subscription
        await _db.shopify_subscriptions.insert_one({
            "shop": shop,
            "plan_id": body.plan_id,
            "plan_name": plan["name"],
            "price": plan["price"],
            "subscription_id": subscription_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"[SHOPIFY-BILLING] Subscription created for {shop}: {body.plan_id}")

        return {
            "confirmation_url": confirmation_url,
            "subscription_id": subscription_id,
            "plan": body.plan_id,
            "shop": shop,
        }

    except httpx.HTTPError as e:
        logger.error(f"[SHOPIFY-BILLING] HTTP error: {e}")
        raise HTTPException(502, "Failed to contact Shopify")


# ═══════════════════════════════════════════════════
# CONFIRM / CHECK SUBSCRIPTION STATUS
# ═══════════════════════════════════════════════════

@router.get("/status/{shop}")
async def subscription_status(shop: str, request: Request):
    """Check current subscription status for a shop."""
    if _db is None:
        return {"status": "unknown", "plan": None}

    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"

    sub = await _db.shopify_subscriptions.find_one(
        {"shop": shop}, {"_id": 0}, sort=[("created_at", -1)]
    )

    if not sub:
        return {"status": "free", "plan": None, "shop": shop}

    return {
        "status": sub.get("status", "unknown"),
        "plan": sub.get("plan_id"),
        "plan_name": sub.get("plan_name"),
        "price": sub.get("price"),
        "subscription_id": sub.get("subscription_id"),
        "created_at": sub.get("created_at"),
        "shop": shop,
    }


@router.get("/history/{shop}")
async def subscription_history(shop: str):
    """Get full subscription history for a shop."""
    if _db is None:
        return {"subscriptions": []}

    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"

    cursor = _db.shopify_subscriptions.find(
        {"shop": shop}, {"_id": 0}
    ).sort("created_at", -1).limit(20)

    subs = await cursor.to_list(length=20)
    return {"subscriptions": subs, "shop": shop}
