"""
AUREM Subscription Router (Customer-facing)
Customers can view plans and subscribe

ALL responses in TOON format
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
import logging

from services.toon_service import get_toon_service
from services.toon_stripe_service import get_toon_stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/saas/plans", tags=["SaaS Plans"])

# MongoDB reference
_db = None

def set_db(database):
    global _db
    _db = database
    get_toon_service().set_db(database)
    logger.info(f"[SaaS Plans] Database set: {_db is not None}")


@router.get("")
async def get_subscription_plans():
    """
    Get all available subscription plans in TOON format
    
    Returns:
    Plan[4]{id, name, price_m, price_y, limits, features}:
      free, Free Forever, 0, 0, {tokens:5k,formulas:3}, {ai_chat:T}
      starter, Starter, 99, 950, {tokens:50k,formulas:20}, {ai_chat:T,voice:openai}
      professional, Professional, 399, 3830, {tokens:200k}, {multi_agent:T}
      enterprise, Enterprise, 999, 9590, {unlimited}, {all:T}
    """
    toon_service = get_toon_service()
    
    try:
        plans_toon = await toon_service.get_subscription_plans_toon()
        
        return {
            "format": "TOON",
            "data": plans_toon
        }
    except Exception as e:
        logger.error(f"[SaaS Plans] Plans error: {e}")
        raise HTTPException(500, f"Failed to load plans: {str(e)}")


@router.get("/{tier}")
async def get_plan_by_tier(tier: str):
    """
    Get specific plan details by tier
    
    Args:
        tier: free, starter, professional, enterprise
    """
    logger.info(f"[SaaS Plans] Getting plan for tier: {tier}, _db is None: {_db is None}")
    
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        plan = await _db.subscription_plans.find_one(
            {"tier": tier, "active": True},
            {"_id": 0}
        )
        
        logger.info(f"[SaaS Plans] Plan found: {plan is not None}")
        
        if not plan:
            raise HTTPException(404, f"Plan '{tier}' not found")
        
        # Return TOON format
        plan_toon = f"""Plan[{plan['plan_id']}]:
  name: {plan['name']}
  tagline: {plan['tagline']}
  price_monthly: ${plan['price_monthly']}
  price_annual: ${plan['price_annual']}
  limits: {plan['limits']}
  features: {plan['features']}
  features_list: {plan['features_list']}
  popular: {plan.get('is_popular', False)}"""
        
        return {
            "format": "TOON",
            "data": plan_toon,
            "json": plan  # Also return JSON for frontend
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SaaS Plans] Plan detail error: {e}")
        raise HTTPException(500, f"Failed to load plan: {str(e)}")


# Request Models
class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., description="TOON plan ID (e.g., 'plan_starter')")
    billing_cycle: str = Field(..., description="'monthly' or 'annual'")
    success_url: str = Field(..., description="Redirect URL on successful payment")
    cancel_url: str = Field(..., description="Redirect URL if user cancels")
    customer_email: Optional[EmailStr] = None
    user_id: Optional[str] = None


@router.post("/checkout")
async def create_checkout_session(request: CheckoutRequest):
    """
    Create Stripe Checkout session for subscription
    
    Example:
    {
        "plan_id": "plan_starter",
        "billing_cycle": "monthly",
        "success_url": "https://aurem.ai/success",
        "cancel_url": "https://aurem.ai/pricing",
        "customer_email": "user@example.com"
    }
    
    Returns:
        Checkout session with redirect URL
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        stripe_service = get_toon_stripe_service(_db)
        
        result = await stripe_service.create_checkout_session(
            plan_id=request.plan_id,
            billing_cycle=request.billing_cycle,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_email=request.customer_email,
            user_id=request.user_id
        )
        
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "Checkout session creation failed"))
        
        return {
            "success": True,
            "checkout_url": result["checkout_url"],
            "session_id": result["session_id"],
            "plan_id": result["plan_id"],
            "billing_cycle": result["billing_cycle"],
            "mock_mode": result.get("mock_mode", False)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SaaS Plans] Checkout error: {e}")
        raise HTTPException(500, str(e))


@router.post("/sync-stripe")
async def sync_plans_to_stripe():
    """
    Sync all TOON plans to Stripe (create products + prices)
    
    Admin endpoint - syncs subscription plans to Stripe
    Creates Stripe products and prices for all active plans
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        stripe_service = get_toon_stripe_service(_db)
        result = await stripe_service.sync_all_plans()
        
        return {
            "success": True,
            "result": result
        }
    
    except Exception as e:
        logger.error(f"[SaaS Plans] Stripe sync error: {e}")
        raise HTTPException(500, str(e))

        logger.error(f"[SaaS Plans] Plan detail error: {e}")
        raise HTTPException(500, f"Failed to load plan: {str(e)}")
