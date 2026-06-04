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

import asyncio
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


# Bug-fix #75 — Auth helper. Previously /customers, /checkout, /portal, /status
# had ZERO auth — anyone could submit any business_id to /portal and receive
# the victim tenant's authenticated Stripe Customer Portal URL (cancel sub,
# update payment, view invoices). Now require a valid JWT + business_id must
# match caller's tenant unless caller is admin.
def _verify_caller(request: Request, business_id: Optional[str] = None) -> dict:
    """Validate JWT, optionally enforce business_id matches caller's tenant."""
    import jwt as _jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(503, "Auth not configured")
    try:
        payload = _jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    is_admin = bool(
        payload.get("is_admin") or payload.get("is_super_admin")
        or payload.get("role") in ("admin", "super_admin")
    )
    if not is_admin:
        from utils.admin_guard import is_admin_email
        if is_admin_email(payload.get("email")):
            is_admin = True
    if business_id and not is_admin:
        caller_tenant = (
            payload.get("tenant_id") or payload.get("business_id")
            or payload.get("sub") or ""
        )
        if caller_tenant != business_id:
            raise HTTPException(403, "business_id does not belong to caller")
    return payload


@router.get("/stripe-status")
async def get_stripe_status():
    """Return whether Stripe is in test or live mode (normalized env resolver)."""
    from services.channel_config import stripe_status
    s = stripe_status()
    if not s["configured"]:
        return {"mode": "not_configured", "message": s["reason"]}
    if s["mode"] == "test":
        return {"mode": "test", "message": "Stripe running in test mode"}
    if s["mode"] == "live":
        return {"mode": "live", "message": "Stripe connected with live keys"}
    return {"mode": "unknown", "message": "Stripe key present but mode unknown"}



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
    _verify_caller(req, business_id=request.business_id)
    from shared.commercial.billing_service import get_billing_service
    
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
    _verify_caller(req, business_id=request.business_id)
    from shared.commercial.billing_service import get_billing_service
    from shared.commercial.workspace_service import SubscriptionPlan
    
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
async def create_portal_session(request: CreatePortalRequest, req: Request):
    """
    Create a Stripe Customer Portal session.
    Allows customers to manage subscription, update payment, view invoices.
    """
    # Bug-fix #75 — this endpoint previously had ZERO auth. An attacker
    # could POST {"business_id": "VICTIM", "return_url": "https://evil.com"}
    # and receive an authenticated billing portal URL for the victim
    # (cancel subscription, view invoices, change payment method). Now
    # requires JWT + business_id ownership check.
    _verify_caller(req, business_id=request.business_id)
    from shared.commercial.billing_service import get_billing_service
    
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
async def get_billing_status(business_id: str, req: Request):
    """
    Get billing status for a business.
    Returns subscription status, plan, period dates, etc.
    """
    _verify_caller(req, business_id=business_id)
    from shared.commercial.billing_service import get_billing_service
    
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
    from shared.commercial.billing_service import get_billing_service
    
    # Get raw body
    payload = await request.body()
    
    # Verify webhook signature
    # Bug-fix #76 — previously fell back to UNVERIFIED event parsing when
    # STRIPE_WEBHOOK_SECRET was empty (the default). An attacker could POST
    # a fake `customer.subscription.updated` event and activate enterprise
    # plans for free. Now we REQUIRE the secret in any non-explicitly-dev
    # environment. Set AUREM_ALLOW_UNVERIFIED_WEBHOOK=1 only for local dev.
    if STRIPE_WEBHOOK_SECRET and stripe_signature:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, STRIPE_WEBHOOK_SECRET
            )
        except stripe.error.SignatureVerificationError:
            logger.warning("[Billing] Invalid webhook signature")
            raise HTTPException(400, "Invalid signature")
    else:
        if os.environ.get("AUREM_ALLOW_UNVERIFIED_WEBHOOK", "").strip() != "1":
            logger.error(
                "[Billing] Webhook rejected: STRIPE_WEBHOOK_SECRET unset or "
                "Stripe-Signature header missing. Set the secret in .env or "
                "explicitly opt-in via AUREM_ALLOW_UNVERIFIED_WEBHOOK=1 for dev."
            )
            raise HTTPException(400, "Webhook signature verification required")
        # Explicit dev opt-in only
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
            # Phase 1 — emit SUBSCRIPTION_CREATED so Referral ORA arms Day 7
            # nudge + Trial Win-back auto-cancels for this email.
            try:
                from services.a2a_bus import bus
                from services.trial_winback import cancel_trial_winback
                sub = event.data.object
                customer_id = sub.get("customer")
                customer_email = ""
                customer_phone = ""
                business_name = ""
                if customer_id:
                    import stripe as _stripe
                    _stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
                    try:
                        # Bug-fix #81 — was synchronous, blocked event loop
                        cust = await asyncio.to_thread(_stripe.Customer.retrieve, customer_id)
                        customer_email = cust.get("email") or ""
                        customer_phone = cust.get("phone") or ""
                        business_name = (cust.get("metadata") or {}).get("business_name", "")
                    except Exception:
                        pass
                await asyncio.gather(
                    bus.emit("billing", "SUBSCRIPTION_CREATED", {
                        "customer_id": customer_id,
                        "email": customer_email,
                        "phone": customer_phone,
                        "business_name": business_name,
                        "subscription_id": sub.get("id", ""),
                    }),
                    cancel_trial_winback(db, customer_email, "subscribed")
                    if customer_email else asyncio.sleep(0),
                    return_exceptions=True,
                )
            except Exception as _e:
                logger.warning(f"[Billing] SUBSCRIPTION_CREATED emit failed (non-blocking): {_e}")
            # Referral reward: if this subscription came from a referred signup, flip + reward
            try:
                from services.referral_rewards import handle_new_subscription
                sub = event.data.object
                customer_id = sub.get("customer")
                customer_email = ""
                if customer_id:
                    import stripe as _stripe
                    _stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
                    # Bug-fix #81 — wrap sync stripe call to avoid blocking loop
                    cust = await asyncio.to_thread(_stripe.Customer.retrieve, customer_id)
                    customer_email = cust.get("email") or ""
                if customer_email:
                    await handle_new_subscription(db, customer_email, sub.get("id", ""))
            except Exception as _e:
                logger.warning(f"[Billing] Referral reward failed (non-blocking): {_e}")
        
        elif event_type == "customer.subscription.updated":
            await billing_service.handle_subscription_updated(event.data.object)
        
        elif event_type == "customer.subscription.deleted":
            await billing_service.handle_subscription_deleted(event.data.object)
        
        # Handle invoice events
        elif event_type == "invoice.paid":
            await billing_service.handle_invoice_paid(event.data.object)
        
        elif event_type == "invoice.payment_failed":
            await billing_service.handle_invoice_payment_failed(event.data.object)

        # Token pack purchase (one-off PaymentIntent)
        elif event_type == "payment_intent.succeeded":
            pi = event.data.object
            metadata = pi.get("metadata") or {}
            if metadata.get("purpose") == "aurem_token_pack":
                try:
                    from routers.customer_tokens_router import credit_tokens, set_db as _ctx_db
                    _ctx_db(db)
                    em = metadata.get("email", "")
                    tokens = int(metadata.get("tokens", "10"))
                    new_bal = await credit_tokens(em, tokens, pi.get("id", ""))
                    logger.info(f"[Billing] Credited {tokens} tokens to {em}; new balance: {new_bal}")
                except Exception as _e:
                    logger.error(f"[Billing] Token credit failed: {_e}")
        
        # Handle checkout events
        elif event_type == "checkout.session.completed":
            # Checkout completed - subscription should be created automatically
            logger.info(f"[Billing] Checkout completed: {event.data.object.id}")

            # ═══ Trigger full post-payment onboarding chain ═══
            # (welcome WhatsApp + Google scan + website draft + admin alert + tenant tasks)
            try:
                session = event.data.object
                from services.aurem_post_payment_onboarding import run_post_payment_flow
                customer_email = (session.get("customer_details") or {}).get("email") or session.get("customer_email") or ""
                if customer_email:
                    tenant_id = customer_email.replace("@", "-")
                    plan = ((session.get("metadata") or {}).get("plan")
                            or (session.get("metadata") or {}).get("package_id")
                            or "starter")
                    amount = float(session.get("amount_total") or 0) / 100.0
                    lead_ref = (session.get("metadata") or {}).get("ref") or ""
                    summary = await run_post_payment_flow(
                        db=db,
                        tenant_id=tenant_id,
                        customer_email=customer_email,
                        plan=plan,
                        amount=amount,
                        lead_ref=lead_ref,
                    )
                    logger.info(f"[Billing] Post-payment chain fired: {list(summary.get('steps', {}).keys())}")
            except Exception as _e:
                logger.warning(f"[Billing] Post-payment chain failed (non-blocking): {_e}")
        
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
    from shared.commercial.workspace_service import PLAN_LIMITS, SubscriptionPlan
    
    plans = []
    for plan_key, limits in PLAN_LIMITS.items():
        if plan_key == SubscriptionPlan.TRIAL.value:
            price = 0
        elif plan_key == SubscriptionPlan.STARTER.value:
            price = 97
        elif plan_key == SubscriptionPlan.GROWTH.value:
            price = 297
        elif plan_key == SubscriptionPlan.ENTERPRISE.value:
            price = 997
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
