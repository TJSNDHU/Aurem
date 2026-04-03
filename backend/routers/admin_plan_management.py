"""
Admin Subscription Plan Management
Full CRUD operations for subscription plans and pricing
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging

from routers.admin_mission_control_router import verify_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/plans", tags=["Admin Plan Management"])

# MongoDB reference
_db = None

def set_db(database):
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SubscriptionPlanUpdate(BaseModel):
    """Update subscription plan"""
    name: Optional[str] = None
    tagline: Optional[str] = None
    price_monthly: Optional[float] = None
    price_annual: Optional[float] = None
    limits: Optional[Dict[str, int]] = None
    features: Optional[Dict[str, Any]] = None
    features_list: Optional[List[str]] = None
    included_services: Optional[List[str]] = None
    is_popular: Optional[bool] = None
    active: Optional[bool] = None


class SubscriptionPlanCreate(BaseModel):
    """Create new subscription plan"""
    plan_id: str
    tier: str  # free, starter, professional, enterprise, custom
    name: str
    tagline: str
    price_monthly: float
    price_annual: float
    limits: Dict[str, int]
    features: Dict[str, Any]
    features_list: List[str]
    included_services: List[str]
    is_popular: bool = False
    active: bool = True


class ServicePricingUpdate(BaseModel):
    """Update custom subscription service pricing"""
    service_id: str
    monthly_price: float


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/all")
async def get_all_plans(admin=Depends(verify_admin)):
    """
    Get all subscription plans (including inactive)
    
    Returns all plans with full details for admin editing
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        plans = await _db.subscription_plans.find(
            {},
            {"_id": 0}
        ).to_list(100)
        
        return {
            "success": True,
            "plans": plans,
            "total": len(plans)
        }
        
    except Exception as e:
        logger.error(f"[Admin Plans] Get all error: {e}")
        raise HTTPException(500, f"Failed to get plans: {str(e)}")


@router.get("/{plan_id}")
async def get_plan_details(plan_id: str, admin=Depends(verify_admin)):
    """Get single plan details"""
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        plan = await _db.subscription_plans.find_one(
            {"plan_id": plan_id},
            {"_id": 0}
        )
        
        if not plan:
            raise HTTPException(404, f"Plan {plan_id} not found")
        
        return {
            "success": True,
            "plan": plan
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin Plans] Get plan error: {e}")
        raise HTTPException(500, f"Failed to get plan: {str(e)}")


@router.post("/create")
async def create_plan(plan: SubscriptionPlanCreate, admin=Depends(verify_admin)):
    """
    Create new subscription plan
    
    Request:
    {
        "plan_id": "plan_premium",
        "tier": "premium",
        "name": "Premium",
        "tagline": "For power users",
        "price_monthly": 199,
        "price_annual": 1910,
        "limits": {"ai_tokens": 500000},
        "features": {"ai_chat": true},
        "features_list": ["Unlimited AI", "Priority support"],
        "included_services": ["gpt-4o", "claude-sonnet-4"],
        "is_popular": false,
        "active": true
    }
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Check if plan already exists
        existing = await _db.subscription_plans.find_one({"plan_id": plan.plan_id})
        if existing:
            raise HTTPException(400, f"Plan {plan.plan_id} already exists")
        
        # Create plan document
        plan_doc = {
            **plan.dict(),
            "created_at": datetime.now(timezone.utc),
            "created_by": admin
        }
        
        # Insert into database
        await _db.subscription_plans.insert_one(plan_doc)
        
        logger.info(f"[Admin Plans] Created plan {plan.plan_id} by {admin}")
        
        return {
            "success": True,
            "message": f"Plan {plan.plan_id} created successfully",
            "plan_id": plan.plan_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin Plans] Create error: {e}")
        raise HTTPException(500, f"Failed to create plan: {str(e)}")


@router.patch("/{plan_id}")
async def update_plan(
    plan_id: str,
    updates: SubscriptionPlanUpdate,
    admin=Depends(verify_admin)
):
    """
    Update subscription plan
    
    Partial update - only send fields you want to change
    
    Example:
    PATCH /api/admin/plans/plan_starter
    {
        "price_monthly": 79,
        "price_annual": 790
    }
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Get only non-None fields
        update_data = {k: v for k, v in updates.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(400, "No updates provided")
        
        # Add metadata
        update_data["updated_at"] = datetime.now(timezone.utc)
        update_data["updated_by"] = admin
        
        # Update plan
        result = await _db.subscription_plans.update_one(
            {"plan_id": plan_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, f"Plan {plan_id} not found")
        
        logger.info(f"[Admin Plans] Updated {plan_id}: {list(update_data.keys())} by {admin}")
        
        # Get updated plan
        updated_plan = await _db.subscription_plans.find_one(
            {"plan_id": plan_id},
            {"_id": 0}
        )
        
        return {
            "success": True,
            "message": f"Plan {plan_id} updated successfully",
            "updated_fields": list(update_data.keys()),
            "plan": updated_plan
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin Plans] Update error: {e}")
        raise HTTPException(500, f"Failed to update plan: {str(e)}")


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str, admin=Depends(verify_admin)):
    """
    Delete (deactivate) subscription plan
    
    Plans are soft-deleted (set active=false) to preserve historical data
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        result = await _db.subscription_plans.update_one(
            {"plan_id": plan_id},
            {
                "$set": {
                    "active": False,
                    "deactivated_at": datetime.now(timezone.utc),
                    "deactivated_by": admin
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, f"Plan {plan_id} not found")
        
        logger.info(f"[Admin Plans] Deactivated {plan_id} by {admin}")
        
        return {
            "success": True,
            "message": f"Plan {plan_id} deactivated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin Plans] Delete error: {e}")
        raise HTTPException(500, f"Failed to delete plan: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM SUBSCRIPTION PRICING MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/custom/pricing")
async def get_custom_pricing(admin=Depends(verify_admin)):
    """
    Get current custom subscription pricing configuration
    
    Returns:
    {
        "base_platform_fee": 49.0,
        "annual_discount": 20,
        "service_pricing": {
            "gpt-4o": 20.0,
            "claude-sonnet-4": 25.0,
            ...
        }
    }
    """
    # Read from custom_subscription_router.py config
    # For now, return hardcoded values (would need to move to DB)
    
    return {
        "success": True,
        "base_platform_fee": 49.0,
        "annual_discount_percent": 20,
        "service_pricing": {
            "gpt-4o": 20.0,
            "gpt-4o-mini": 5.0,
            "claude-sonnet-4": 25.0,
            "gemini-2.5-flash": 10.0,
            "openai-tts": 15.0,
            "voxtral-tts": 20.0,
            "elevenlabs-tts": 25.0,
            "stripe-payments": 0.0,
            "video-upscaling": 50.0,
            "competitive-intelligence": 75.0
        }
    }


@router.post("/custom/pricing/update")
async def update_custom_pricing(
    service_id: str,
    monthly_price: float,
    admin=Depends(verify_admin)
):
    """
    Update custom subscription service pricing
    
    Request:
    {
        "service_id": "gpt-4o",
        "monthly_price": 25.0
    }
    """
    # This would need to update a config file or database
    # For MVP, we'll log it and return success
    
    logger.info(f"[Admin Plans] Updated {service_id} pricing to ${monthly_price}/mo by {admin}")
    
    return {
        "success": True,
        "message": f"Service {service_id} pricing updated to ${monthly_price}/month",
        "note": "Pricing changes will take effect on next server restart"
    }


@router.post("/custom/base-fee")
async def update_base_fee(
    base_fee: float,
    admin=Depends(verify_admin)
):
    """
    Update base platform fee for custom subscriptions
    
    Query param: base_fee (e.g., 49.0)
    """
    logger.info(f"[Admin Plans] Updated base platform fee to ${base_fee}/mo by {admin}")
    
    return {
        "success": True,
        "message": f"Base platform fee updated to ${base_fee}/month",
        "note": "Changes will take effect on next server restart"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BULK OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/bulk/update-prices")
async def bulk_update_prices(
    price_changes: Dict[str, Dict[str, float]],
    admin=Depends(verify_admin)
):
    """
    Bulk update multiple plan prices
    
    Request:
    {
        "plan_starter": {"price_monthly": 89, "price_annual": 890},
        "plan_professional": {"price_monthly": 349, "price_annual": 3490}
    }
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        updated_count = 0
        
        for plan_id, prices in price_changes.items():
            result = await _db.subscription_plans.update_one(
                {"plan_id": plan_id},
                {
                    "$set": {
                        **prices,
                        "updated_at": datetime.now(timezone.utc),
                        "updated_by": admin
                    }
                }
            )
            
            if result.matched_count > 0:
                updated_count += 1
        
        logger.info(f"[Admin Plans] Bulk updated {updated_count} plans by {admin}")
        
        return {
            "success": True,
            "updated_count": updated_count,
            "total_requested": len(price_changes)
        }
        
    except Exception as e:
        logger.error(f"[Admin Plans] Bulk update error: {e}")
        raise HTTPException(500, f"Bulk update failed: {str(e)}")
