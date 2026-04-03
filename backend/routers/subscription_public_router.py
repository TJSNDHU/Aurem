"""
AUREM Subscription Router (Customer-facing)
Customers can view plans and subscribe

ALL responses in TOON format
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from services.toon_service import get_toon_service

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
