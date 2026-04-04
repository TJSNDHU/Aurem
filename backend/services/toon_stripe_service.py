"""
TOON Stripe Integration Service
Connects TOON subscription plans to Stripe payment processing
"""

import os
import stripe
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.environ.get("STRIPE_API_KEY", "")


class TOONStripeService:
    """
    Stripe integration for TOON subscription plans
    
    Dynamically creates Stripe products/prices based on TOON plans
    """
    
    def __init__(self, db):
        self.db = db
        
        stripe_key = os.environ.get("STRIPE_API_KEY", "")
        
        # Check if key is valid (not the placeholder test key)
        if not stripe_key or stripe_key == "" or stripe_key == "sk_test_emergent":
            logger.warning("[TOONStripe] STRIPE_API_KEY not set or invalid - running in mock mode")
            self.mock_mode = True
        else:
            stripe.api_key = stripe_key
            self.mock_mode = False
            logger.info("[TOONStripe] Stripe initialized")
    
    async def get_or_create_stripe_product(
        self,
        plan_id: str,
        plan_name: str,
        plan_description: str
    ) -> Optional[str]:
        """
        Get or create Stripe product for a TOON plan
        
        Returns:
            Stripe product ID
        """
        if self.mock_mode:
            return f"mock_prod_{plan_id}"
        
        try:
            # Check if product already exists
            plan_doc = await self.db.subscription_plans.find_one(
                {"plan_id": plan_id},
                {"_id": 0}
            )
            
            if plan_doc and plan_doc.get("stripe_product_id"):
                # Verify it exists in Stripe
                try:
                    stripe.Product.retrieve(plan_doc["stripe_product_id"])
                    return plan_doc["stripe_product_id"]
                except stripe.error.InvalidRequestError:
                    # Product deleted, create new
                    pass
            
            # Create new product
            product = stripe.Product.create(
                name=plan_name,
                description=plan_description,
                metadata={
                    "toon_plan_id": plan_id,
                    "platform": "aurem"
                }
            )
            
            # Store product ID in database
            await self.db.subscription_plans.update_one(
                {"plan_id": plan_id},
                {"$set": {
                    "stripe_product_id": product.id,
                    "stripe_updated_at": datetime.now(timezone.utc)
                }}
            )
            
            logger.info(f"[TOONStripe] Created Stripe product: {product.id} for {plan_name}")
            
            return product.id
        
        except Exception as e:
            logger.error(f"[TOONStripe] Error creating product: {e}")
            return None
    
    async def get_or_create_stripe_price(
        self,
        product_id: str,
        amount_cents: int,
        currency: str,
        interval: str,
        plan_id: str
    ) -> Optional[str]:
        """
        Get or create Stripe price for a product
        
        Args:
            product_id: Stripe product ID
            amount_cents: Price in cents (e.g., 9900 for $99.00)
            currency: Currency code (e.g., 'usd')
            interval: 'month' or 'year'
            plan_id: TOON plan ID
        
        Returns:
            Stripe price ID
        """
        if self.mock_mode:
            return f"mock_price_{plan_id}_{interval}"
        
        try:
            # Check if price already exists
            price_field = f"stripe_price_id_{interval}ly"
            
            plan_doc = await self.db.subscription_plans.find_one(
                {"plan_id": plan_id},
                {"_id": 0}
            )
            
            if plan_doc and plan_doc.get(price_field):
                # Verify it exists in Stripe
                try:
                    stripe.Price.retrieve(plan_doc[price_field])
                    return plan_doc[price_field]
                except stripe.error.InvalidRequestError:
                    # Price deleted, create new
                    pass
            
            # Create new price
            price = stripe.Price.create(
                product=product_id,
                unit_amount=amount_cents,
                currency=currency,
                recurring={"interval": interval},
                metadata={
                    "toon_plan_id": plan_id,
                    "interval": interval
                }
            )
            
            # Store price ID in database
            await self.db.subscription_plans.update_one(
                {"plan_id": plan_id},
                {"$set": {
                    price_field: price.id,
                    "stripe_updated_at": datetime.now(timezone.utc)
                }}
            )
            
            logger.info(
                f"[TOONStripe] Created Stripe price: {price.id} "
                f"(${amount_cents/100:.2f}/{interval})"
            )
            
            return price.id
        
        except Exception as e:
            logger.error(f"[TOONStripe] Error creating price: {e}")
            return None
    
    async def sync_plan_to_stripe(self, plan_id: str) -> Dict[str, Any]:
        """
        Sync a TOON plan to Stripe (create product + prices)
        
        Args:
            plan_id: TOON plan ID (e.g., 'plan_starter')
        
        Returns:
            Sync result with product/price IDs
        """
        try:
            # Get plan from database
            plan = await self.db.subscription_plans.find_one(
                {"plan_id": plan_id},
                {"_id": 0}
            )
            
            if not plan:
                return {
                    "success": False,
                    "error": f"Plan not found: {plan_id}"
                }
            
            # Skip free plan (no Stripe needed)
            if plan["price_monthly"] == 0 and plan["price_annual"] == 0:
                return {
                    "success": True,
                    "plan_id": plan_id,
                    "message": "Free plan - no Stripe sync needed",
                    "skipped": True
                }
            
            # Create product
            product_id = await self.get_or_create_stripe_product(
                plan_id=plan_id,
                plan_name=plan["name"],
                plan_description=plan.get("tagline", "")
            )
            
            if not product_id:
                return {
                    "success": False,
                    "error": "Failed to create Stripe product"
                }
            
            # Create monthly price
            monthly_price_id = None
            if plan["price_monthly"] > 0:
                monthly_price_id = await self.get_or_create_stripe_price(
                    product_id=product_id,
                    amount_cents=int(plan["price_monthly"] * 100),
                    currency=plan.get("currency", "usd"),
                    interval="month",
                    plan_id=plan_id
                )
            
            # Create annual price
            annual_price_id = None
            if plan["price_annual"] > 0:
                annual_price_id = await self.get_or_create_stripe_price(
                    product_id=product_id,
                    amount_cents=int(plan["price_annual"] * 100),
                    currency=plan.get("currency", "usd"),
                    interval="year",
                    plan_id=plan_id
                )
            
            return {
                "success": True,
                "plan_id": plan_id,
                "stripe_product_id": product_id,
                "stripe_price_monthly": monthly_price_id,
                "stripe_price_annual": annual_price_id,
                "mock_mode": self.mock_mode
            }
        
        except Exception as e:
            logger.error(f"[TOONStripe] Error syncing plan: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def sync_all_plans(self) -> Dict[str, Any]:
        """
        Sync all TOON plans to Stripe
        """
        try:
            # Get all active plans
            plans_cursor = self.db.subscription_plans.find(
                {"active": True},
                {"_id": 0, "plan_id": 1, "name": 1}
            )
            
            plans = await plans_cursor.to_list(100)
            
            results = []
            for plan in plans:
                result = await self.sync_plan_to_stripe(plan["plan_id"])
                results.append({
                    "plan_id": plan["plan_id"],
                    "name": plan["name"],
                    "result": result
                })
            
            success_count = sum(1 for r in results if r["result"].get("success"))
            
            return {
                "success": True,
                "total_plans": len(plans),
                "synced": success_count,
                "results": results,
                "mock_mode": self.mock_mode
            }
        
        except Exception as e:
            logger.error(f"[TOONStripe] Error syncing all plans: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_checkout_session(
        self,
        plan_id: str,
        billing_cycle: str,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create Stripe Checkout session for subscription
        
        Args:
            plan_id: TOON plan ID
            billing_cycle: 'monthly' or 'annual'
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            customer_email: Customer email
            user_id: User ID for metadata
        
        Returns:
            Checkout session with URL
        """
        try:
            # Get plan
            plan = await self.db.subscription_plans.find_one(
                {"plan_id": plan_id},
                {"_id": 0}
            )
            
            if not plan:
                return {
                    "success": False,
                    "error": f"Plan not found: {plan_id}"
                }
            
            # Get price ID
            price_field = f"stripe_price_id_{billing_cycle}ly"
            price_id = plan.get(price_field)
            
            if not price_id:
                # Sync plan first
                sync_result = await self.sync_plan_to_stripe(plan_id)
                if not sync_result.get("success"):
                    return sync_result
                
                price_id = sync_result.get(f"stripe_price_{billing_cycle}")
            
            if self.mock_mode:
                # Mock checkout session
                return {
                    "success": True,
                    "checkout_url": f"{success_url}?mock_session=true",
                    "session_id": f"mock_cs_{plan_id}_{billing_cycle}",
                    "mock_mode": True,
                    "plan_id": plan_id,
                    "billing_cycle": billing_cycle
                }
            
            # Create Stripe Checkout Session
            session_params = {
                "mode": "subscription",
                "line_items": [{
                    "price": price_id,
                    "quantity": 1
                }],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "toon_plan_id": plan_id,
                    "billing_cycle": billing_cycle
                }
            }
            
            if customer_email:
                session_params["customer_email"] = customer_email
            
            if user_id:
                session_params["metadata"]["user_id"] = user_id
            
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(
                f"[TOONStripe] Created checkout session: {session.id} "
                f"for {plan['name']} ({billing_cycle})"
            )
            
            return {
                "success": True,
                "checkout_url": session.url,
                "session_id": session.id,
                "plan_id": plan_id,
                "billing_cycle": billing_cycle,
                "mock_mode": False
            }
        
        except Exception as e:
            logger.error(f"[TOONStripe] Error creating checkout session: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
_toon_stripe_service = None


def get_toon_stripe_service(db) -> TOONStripeService:
    """Get singleton TOON Stripe service instance"""
    global _toon_stripe_service
    
    if _toon_stripe_service is None:
        _toon_stripe_service = TOONStripeService(db)
    
    return _toon_stripe_service
