"""
AUREM Commercial Platform - Stripe Billing Service
Subscription management, usage-based billing, and auto-pause

Features:
- Subscription plan management (Trial, Starter, Pro, Enterprise)
- Usage-based overage billing
- Automatic pause for failed payments
- Stripe webhook handling
"""

import os
import stripe
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

from .audit_service import AuditLogger, AuditAction, get_audit_logger
from .workspace_service import (
    CustomerWorkspace, 
    SubscriptionPlan, 
    WorkspaceStatus,
    PLAN_LIMITS,
    get_workspace_service
)

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.environ.get("STRIPE_API_KEY", "")

# Stripe Price IDs (create these in Stripe Dashboard)
# For now, we'll create them dynamically if they don't exist
STRIPE_PRICES = {
    SubscriptionPlan.STARTER.value: {
        "amount": 4900,  # $49.00 in cents
        "interval": "month",
        "product_name": "AUREM Starter",
        "price_id": os.environ.get("STRIPE_PRICE_STARTER"),
    },
    SubscriptionPlan.PRO.value: {
        "amount": 14900,  # $149.00
        "interval": "month",
        "product_name": "AUREM Pro",
        "price_id": os.environ.get("STRIPE_PRICE_PRO"),
    },
    SubscriptionPlan.ENTERPRISE.value: {
        "amount": 39900,  # $399.00
        "interval": "month",
        "product_name": "AUREM Enterprise",
        "price_id": os.environ.get("STRIPE_PRICE_ENTERPRISE"),
    }
}

# Overage pricing
OVERAGE_PRICE_PER_MESSAGE = {
    SubscriptionPlan.STARTER.value: 8,      # $0.08
    SubscriptionPlan.PRO.value: 5,          # $0.05
    SubscriptionPlan.ENTERPRISE.value: 3,   # $0.03
}


class PaymentStatus(str, Enum):
    """Payment status"""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class BillingService:
    """
    Stripe billing integration for AUREM platform.
    """
    
    COLLECTION_NAME = "aurem_billing"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION_NAME]
        self.audit = get_audit_logger(db)
        self.workspace_service = get_workspace_service(db)
        
        if not stripe.api_key:
            logger.warning("[Billing] STRIPE_API_KEY not set!")
    
    async def ensure_indexes(self):
        """Create indexes - handles existing indexes gracefully"""
        indexes = [
            {"keys": "business_id", "unique": True},
            {"keys": "stripe_customer_id"},
            {"keys": "stripe_subscription_id"},
            {"keys": "status"}
        ]
        for idx in indexes:
            try:
                if idx.get("unique"):
                    await self.collection.create_index(idx["keys"], unique=True)
                else:
                    await self.collection.create_index(idx["keys"])
            except Exception:
                pass  # Index exists or conflict
        logger.info("[Billing] Indexes verified")
    
    async def create_customer(
        self,
        business_id: str,
        email: str,
        business_name: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe customer for a business.
        
        Args:
            business_id: AUREM business ID
            email: Customer email
            business_name: Business name
            ip_address: For audit
            
        Returns:
            Stripe customer object
        """
        try:
            # Check if customer already exists
            existing = await self.collection.find_one({"business_id": business_id})
            if existing and existing.get("stripe_customer_id"):
                # Return existing customer
                customer = stripe.Customer.retrieve(existing["stripe_customer_id"])
                return {"customer": customer, "existing": True}
            
            # Create Stripe customer
            customer = stripe.Customer.create(
                email=email,
                name=business_name,
                metadata={
                    "business_id": business_id,
                    "platform": "aurem"
                }
            )
            
            # Store billing record
            billing_record = {
                "business_id": business_id,
                "stripe_customer_id": customer.id,
                "email": email,
                "status": PaymentStatus.TRIALING.value,
                "plan": SubscriptionPlan.TRIAL.value,
                "stripe_subscription_id": None,
                "current_period_start": None,
                "current_period_end": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await self.collection.update_one(
                {"business_id": business_id},
                {"$set": billing_record},
                upsert=True
            )
            
            # Update workspace with Stripe customer ID
            await self.db["aurem_workspaces"].update_one(
                {"business_id": business_id},
                {"$set": {"stripe_customer_id": customer.id}}
            )
            
            # Audit log
            await self.audit.log(
                action=AuditAction.ADMIN_ACTION,
                business_id=business_id,
                actor_id="system",
                actor_type="system",
                resource_type="billing",
                details={
                    "action": "customer_created",
                    "stripe_customer_id": customer.id
                },
                ip_address=ip_address,
                success=True
            )
            
            logger.info(f"[Billing] Created Stripe customer: {customer.id} for {business_id}")
            return {"customer": customer, "existing": False}
            
        except stripe.error.StripeError as e:
            logger.error(f"[Billing] Stripe error creating customer: {e}")
            raise
    
    async def create_checkout_session(
        self,
        business_id: str,
        plan: SubscriptionPlan,
        success_url: str,
        cancel_url: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout session for subscription.
        
        Args:
            business_id: AUREM business ID
            plan: Subscription plan to purchase
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            
        Returns:
            Checkout session with URL
        """
        try:
            # Get billing record
            billing = await self.collection.find_one({"business_id": business_id})
            if not billing:
                raise ValueError("Business not found in billing")
            
            customer_id = billing.get("stripe_customer_id")
            if not customer_id:
                raise ValueError("No Stripe customer for this business")
            
            # Get or create price
            plan_key = plan.value if isinstance(plan, SubscriptionPlan) else plan
            price_config = STRIPE_PRICES.get(plan_key)
            
            if not price_config:
                raise ValueError(f"Invalid plan: {plan_key}")
            
            price_id = price_config.get("price_id")
            
            # If no price ID configured, create price dynamically
            if not price_id:
                price_id = await self._get_or_create_price(plan_key, price_config)
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_id,
                    "quantity": 1
                }],
                mode="subscription",
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                metadata={
                    "business_id": business_id,
                    "plan": plan_key
                },
                subscription_data={
                    "metadata": {
                        "business_id": business_id,
                        "plan": plan_key
                    }
                }
            )
            
            # Audit log
            await self.audit.log(
                action=AuditAction.ADMIN_ACTION,
                business_id=business_id,
                actor_id=customer_id,
                actor_type="user",
                resource_type="billing",
                details={
                    "action": "checkout_created",
                    "plan": plan_key,
                    "session_id": session.id
                },
                ip_address=ip_address,
                success=True
            )
            
            logger.info(f"[Billing] Checkout session created: {session.id} for {business_id}")
            
            return {
                "session_id": session.id,
                "url": session.url,
                "plan": plan_key
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"[Billing] Stripe error creating checkout: {e}")
            raise
    
    async def _get_or_create_price(
        self,
        plan_key: str,
        price_config: Dict[str, Any]
    ) -> str:
        """Get existing price or create new one"""
        
        # Search for existing price
        prices = stripe.Price.list(
            lookup_keys=[f"aurem_{plan_key}"],
            limit=1
        )
        
        if prices.data:
            return prices.data[0].id
        
        # Create product first
        product = stripe.Product.create(
            name=price_config["product_name"],
            metadata={"platform": "aurem", "plan": plan_key}
        )
        
        # Create price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=price_config["amount"],
            currency="cad",
            recurring={"interval": price_config["interval"]},
            lookup_key=f"aurem_{plan_key}",
            metadata={"platform": "aurem", "plan": plan_key}
        )
        
        logger.info(f"[Billing] Created Stripe price: {price.id} for {plan_key}")
        return price.id
    
    async def handle_subscription_created(
        self,
        subscription: stripe.Subscription
    ):
        """Handle subscription.created webhook"""
        
        business_id = subscription.metadata.get("business_id")
        plan = subscription.metadata.get("plan", SubscriptionPlan.STARTER.value)
        
        if not business_id:
            logger.warning(f"[Billing] Subscription without business_id: {subscription.id}")
            return
        
        # Update billing record
        await self.collection.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "stripe_subscription_id": subscription.id,
                    "status": PaymentStatus.ACTIVE.value,
                    "plan": plan,
                    "current_period_start": datetime.fromtimestamp(
                        subscription.current_period_start, tz=timezone.utc
                    ),
                    "current_period_end": datetime.fromtimestamp(
                        subscription.current_period_end, tz=timezone.utc
                    ),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Update workspace plan
        await self.workspace_service.change_plan(business_id, SubscriptionPlan(plan))
        
        # Audit log
        await self.audit.log(
            action=AuditAction.PLAN_CHANGED,
            business_id=business_id,
            actor_id="stripe_webhook",
            actor_type="system",
            resource_type="subscription",
            resource_id=subscription.id,
            details={
                "action": "subscription_created",
                "plan": plan,
                "status": subscription.status
            },
            success=True
        )
        
        logger.info(f"[Billing] Subscription created: {subscription.id} for {business_id}")
    
    async def handle_subscription_updated(
        self,
        subscription: stripe.Subscription
    ):
        """Handle subscription.updated webhook"""
        
        business_id = subscription.metadata.get("business_id")
        if not business_id:
            # Try to find by subscription ID
            billing = await self.collection.find_one({
                "stripe_subscription_id": subscription.id
            })
            if billing:
                business_id = billing["business_id"]
            else:
                logger.warning(f"[Billing] Unknown subscription: {subscription.id}")
                return
        
        # Map Stripe status to our status
        status_map = {
            "active": PaymentStatus.ACTIVE,
            "past_due": PaymentStatus.PAST_DUE,
            "canceled": PaymentStatus.CANCELLED,
            "trialing": PaymentStatus.TRIALING,
            "unpaid": PaymentStatus.UNPAID
        }
        
        status = status_map.get(subscription.status, PaymentStatus.ACTIVE)
        
        # Update billing record
        await self.collection.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "status": status.value,
                    "current_period_start": datetime.fromtimestamp(
                        subscription.current_period_start, tz=timezone.utc
                    ),
                    "current_period_end": datetime.fromtimestamp(
                        subscription.current_period_end, tz=timezone.utc
                    ),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Handle status changes
        if status in [PaymentStatus.PAST_DUE, PaymentStatus.UNPAID]:
            # Pause workspace
            await self.workspace_service.pause_workspace(
                business_id, 
                reason=f"payment_{status.value}"
            )
            logger.warning(f"[Billing] Paused workspace {business_id} due to {status.value}")
        
        elif status == PaymentStatus.ACTIVE:
            # Reactivate workspace
            workspace = await self.workspace_service.get_workspace(business_id)
            if workspace and workspace.get("status") == WorkspaceStatus.PAUSED.value:
                await self.workspace_service.reactivate_workspace(business_id)
                logger.info(f"[Billing] Reactivated workspace {business_id}")
        
        # Audit log
        await self.audit.log(
            action=AuditAction.ADMIN_ACTION,
            business_id=business_id,
            actor_id="stripe_webhook",
            actor_type="system",
            resource_type="subscription",
            resource_id=subscription.id,
            details={
                "action": "subscription_updated",
                "stripe_status": subscription.status,
                "aurem_status": status.value
            },
            success=True
        )
    
    async def handle_subscription_deleted(
        self,
        subscription: stripe.Subscription
    ):
        """Handle subscription.deleted webhook"""
        
        business_id = subscription.metadata.get("business_id")
        if not business_id:
            billing = await self.collection.find_one({
                "stripe_subscription_id": subscription.id
            })
            if billing:
                business_id = billing["business_id"]
            else:
                return
        
        # Update billing record
        await self.collection.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "status": PaymentStatus.CANCELLED.value,
                    "cancelled_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Downgrade to trial
        await self.workspace_service.change_plan(business_id, SubscriptionPlan.TRIAL)
        
        # Pause workspace
        await self.workspace_service.pause_workspace(
            business_id, 
            reason="subscription_cancelled"
        )
        
        logger.info(f"[Billing] Subscription cancelled for {business_id}")
    
    async def handle_invoice_paid(
        self,
        invoice: stripe.Invoice
    ):
        """Handle invoice.paid webhook"""
        
        business_id = None
        if invoice.subscription:
            billing = await self.collection.find_one({
                "stripe_subscription_id": invoice.subscription
            })
            if billing:
                business_id = billing["business_id"]
        
        if not business_id:
            return
        
        # Record payment
        await self.db["aurem_payments"].insert_one({
            "business_id": business_id,
            "stripe_invoice_id": invoice.id,
            "amount": invoice.amount_paid,
            "currency": invoice.currency,
            "status": "paid",
            "paid_at": datetime.now(timezone.utc)
        })
        
        logger.info(f"[Billing] Invoice paid: {invoice.id} for {business_id}")
    
    async def handle_invoice_payment_failed(
        self,
        invoice: stripe.Invoice
    ):
        """Handle invoice.payment_failed webhook"""
        
        business_id = None
        if invoice.subscription:
            billing = await self.collection.find_one({
                "stripe_subscription_id": invoice.subscription
            })
            if billing:
                business_id = billing["business_id"]
        
        if not business_id:
            return
        
        # Pause workspace after 3rd failure
        billing = await self.collection.find_one({"business_id": business_id})
        failed_count = billing.get("payment_failed_count", 0) + 1
        
        await self.collection.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "payment_failed_count": failed_count,
                    "last_payment_error": invoice.last_payment_error.message if invoice.last_payment_error else "Unknown error",
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if failed_count >= 3:
            await self.workspace_service.pause_workspace(
                business_id, 
                reason="payment_failed_3x"
            )
        
        logger.warning(f"[Billing] Payment failed ({failed_count}x) for {business_id}")
    
    async def get_billing_status(
        self,
        business_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get billing status for a business"""
        
        billing = await self.collection.find_one({"business_id": business_id})
        if billing:
            billing["_id"] = str(billing["_id"])
        return billing
    
    async def create_billing_portal_session(
        self,
        business_id: str,
        return_url: str
    ) -> Dict[str, Any]:
        """
        Create a Stripe Customer Portal session.
        Allows customers to manage their subscription, update payment, etc.
        """
        
        billing = await self.collection.find_one({"business_id": business_id})
        if not billing or not billing.get("stripe_customer_id"):
            raise ValueError("No Stripe customer found")
        
        session = stripe.billing_portal.Session.create(
            customer=billing["stripe_customer_id"],
            return_url=return_url
        )
        
        return {
            "url": session.url
        }
    
    async def record_overage(
        self,
        business_id: str,
        messages: int
    ):
        """
        Record overage usage for billing.
        Called when a business exceeds their included messages.
        """
        
        billing = await self.collection.find_one({"business_id": business_id})
        if not billing:
            return
        
        plan = billing.get("plan", SubscriptionPlan.STARTER.value)
        rate_cents = OVERAGE_PRICE_PER_MESSAGE.get(plan, 8)
        
        # Update usage tracking
        period = datetime.utcnow().strftime("%Y-%m")
        await self.workspace_service.usage.update_one(
            {"business_id": business_id, "billing_period": period},
            {
                "$inc": {
                    "overage_messages": messages,
                    "overage_cost": (messages * rate_cents) / 100
                }
            }
        )
        
        # TODO: Create usage record in Stripe for metered billing
        # This would require setting up metered billing in Stripe


# Singleton
_billing_service: Optional[BillingService] = None


def get_billing_service(db: AsyncIOMotorDatabase) -> BillingService:
    """Get or create the billing service instance"""
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService(db)
    return _billing_service
