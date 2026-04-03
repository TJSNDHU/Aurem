"""
AUREM Commercial Platform - Billing Router
Stripe subscription management and webhook handling

Endpoints:
- POST /api/aurem-billing/customers - Create Stripe customer
- POST /api/aurem-billing/checkout - Create checkout session
- POST /api/aurem-billing/portal - Create billing portal session
- GET /api/aurem-billing/status/{business_id} - Get billing status
- POST /api/aurem-billing/webhook - Stripe webhook handler
"""

import os
import stripe
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

router = APIRouter(prefix="/api/aurem-billing", tags=["AUREM Billing"])

logger = logging.getLogger(__name__)

# Database reference
_db = None

# Stripe webhook secret
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def set_db(db):
    """Set database reference"""
    global _db
    _db = db


def get_db():
    """Get database reference"""
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


# ==================== MODELS ====================

class CreateCustomerRequest(BaseModel):
    business_id: str
    email: EmailStr
    business_name: str


class CreateCheckoutRequest(BaseModel):
    business_id: str
    plan: str  # starter, pro, enterprise
    success_url: str
    cancel_url: str


class CreatePortalRequest(BaseModel):
    business_id: str
    return_url: str


# ==================== ENDPOINTS ====================

@router.post("/customers")
async def create_customer(request: CreateCustomerRequest, req: Request):
    """
    Create a Stripe customer for a business.
    Called after workspace creation.
    """
    from services.aurem_commercial.billing_service import get_billing_service
    
    db = get_db()
    billing_service = get_billing_service(db)
    
    ip_address = req.client.host if req.client else None
    
    try:
        result = await billing_service.create_customer(
            business_id=request.business_id,
            email=request.email,
            business_name=request.business_name,
            ip_address=ip_address
        )
        
        return {
            "success": True,
            "customer_id": result["customer"].id,
            "existing": result.get("existing", False)
        }
        
    except Exception as e:
        logger.error(f"[Billing] Error creating customer: {e}")
        raise HTTPException(500, f"Failed to create customer: {str(e)}")


@router.post("/checkout")
async def create_checkout(request: CreateCheckoutRequest, req: Request):
    """
    Create a Stripe Checkout session for subscription upgrade.
    Returns a URL to redirect the customer to.
    """
    from services.aurem_commercial.billing_service import get_billing_service
    from services.aurem_commercial.workspace_service import SubscriptionPlan
    
    db = get_db()
    billing_service = get_billing_service(db)
    
    # Validate plan
    try:
        plan = SubscriptionPlan(request.plan)
    except ValueError:
        raise HTTPException(400, f"Invalid plan: {request.plan}")
    
    # Trial plan cannot be purchased
    if plan == SubscriptionPlan.TRIAL:
        raise HTTPException(400, "Trial plan is free and cannot be purchased")
    
    ip_address = req.client.host if req.client else None
    
    try:
        result = await billing_service.create_checkout_session(
            business_id=request.business_id,
            plan=plan,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            ip_address=ip_address
        )
        
        return {
            "success": True,
            "session_id": result["session_id"],
            "checkout_url": result["url"],
            "plan": result["plan"]
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"[Billing] Error creating checkout: {e}")
        raise HTTPException(500, f"Failed to create checkout: {str(e)}")


@router.post("/portal")
async def create_portal_session(request: CreatePortalRequest):
    """
    Create a Stripe Customer Portal session.
    Allows customers to manage subscription, update payment, view invoices.
    """
    from services.aurem_commercial.billing_service import get_billing_service
    
    db = get_db()
    billing_service = get_billing_service(db)
    
    try:
        result = await billing_service.create_billing_portal_session(
            business_id=request.business_id,
            return_url=request.return_url
        )
        
        return {
            "success": True,
            "portal_url": result["url"]
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"[Billing] Error creating portal: {e}")
        raise HTTPException(500, f"Failed to create portal: {str(e)}")


@router.get("/status/{business_id}")
async def get_billing_status(business_id: str):
    """
    Get billing status for a business.
    Returns subscription status, plan, period dates, etc.
    """
    from services.aurem_commercial.billing_service import get_billing_service
    
    db = get_db()
    billing_service = get_billing_service(db)
    
    status = await billing_service.get_billing_status(business_id)
    
    if not status:
        return {
            "business_id": business_id,
            "status": "no_billing_record",
            "plan": "trial",
            "message": "No billing record found. Business may be on free trial."
        }
    
    return {
        "business_id": business_id,
        "status": status.get("status"),
        "plan": status.get("plan"),
        "stripe_customer_id": status.get("stripe_customer_id"),
        "stripe_subscription_id": status.get("stripe_subscription_id"),
        "current_period_start": status.get("current_period_start"),
        "current_period_end": status.get("current_period_end"),
        "payment_failed_count": status.get("payment_failed_count", 0),
        "last_payment_error": status.get("last_payment_error")
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """
    Stripe webhook handler.
    Receives events for subscription changes, payments, etc.
    """
    from services.aurem_commercial.billing_service import get_billing_service
    
    # Get raw body
    payload = await request.body()
    
    # Verify webhook signature
    if STRIPE_WEBHOOK_SECRET and stripe_signature:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, STRIPE_WEBHOOK_SECRET
            )
        except stripe.error.SignatureVerificationError:
            logger.warning("[Billing] Invalid webhook signature")
            raise HTTPException(400, "Invalid signature")
    else:
        # No signature verification (development mode)
        import json
        event = stripe.Event.construct_from(
            json.loads(payload), stripe.api_key
        )
        logger.warning("[Billing] Webhook signature not verified (dev mode)")
    
    db = get_db()
    billing_service = get_billing_service(db)
    
    event_type = event.type
    logger.info(f"[Billing] Webhook received: {event_type}")
    
    try:
        # Handle subscription events
        if event_type == "customer.subscription.created":
            await billing_service.handle_subscription_created(event.data.object)
        
        elif event_type == "customer.subscription.updated":
            await billing_service.handle_subscription_updated(event.data.object)
        
        elif event_type == "customer.subscription.deleted":
            await billing_service.handle_subscription_deleted(event.data.object)
        
        # Handle invoice events
        elif event_type == "invoice.paid":
            await billing_service.handle_invoice_paid(event.data.object)
        
        elif event_type == "invoice.payment_failed":
            await billing_service.handle_invoice_payment_failed(event.data.object)
        
        # Handle checkout events
        elif event_type == "checkout.session.completed":
            # Checkout completed - subscription should be created automatically
            logger.info(f"[Billing] Checkout completed: {event.data.object.id}")
        
        else:
            logger.info(f"[Billing] Unhandled event type: {event_type}")
        
        return {"status": "success", "event_type": event_type}
        
    except Exception as e:
        logger.error(f"[Billing] Webhook processing error: {e}")
        # Return 200 to prevent Stripe retries for processing errors
        return {"status": "error", "message": str(e)}


@router.get("/plans")
async def get_available_plans():
    """
    Get available subscription plans with pricing.
    """
    from services.aurem_commercial.workspace_service import PLAN_LIMITS, SubscriptionPlan
    
    plans = []
    for plan_key, limits in PLAN_LIMITS.items():
        if plan_key == SubscriptionPlan.TRIAL.value:
            price = 0
        elif plan_key == SubscriptionPlan.STARTER.value:
            price = 49
        elif plan_key == SubscriptionPlan.PRO.value:
            price = 149
        elif plan_key == SubscriptionPlan.ENTERPRISE.value:
            price = 399
        else:
            price = 0
        
        plans.append({
            "plan": plan_key,
            "price_monthly": price,
            "currency": "CAD",
            "ai_messages_included": limits["ai_messages"],
            "users": limits["users"],
            "channels": limits["channels"],
            "features": limits["features"],
            "overage_rate": limits["overage_rate"]
        })
    
    return {"plans": plans}


@router.get("/health")
async def health_check():
    """Health check for billing service"""
    
    stripe_ok = bool(stripe.api_key)
    
    return {
        "status": "healthy" if stripe_ok else "degraded",
        "stripe_configured": stripe_ok,
        "webhook_secret_configured": bool(STRIPE_WEBHOOK_SECRET)
    }
