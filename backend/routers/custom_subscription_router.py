"""
Custom Subscription Router - A-la-carte / Build-Your-Own Plans
Users can select specific services and get custom pricing
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import secrets
import logging

from models.custom_subscription_models import (
    CustomSubscriptionRequest,
    CustomSubscriptionPricing,
    CustomSubscriptionPlan
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscriptions/custom", tags=["Custom Subscriptions"])

# MongoDB reference
_db = None

def set_db(database):
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════════════════
# PRICING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Base platform fee (access to AUREM platform)
BASE_PLATFORM_FEE_MONTHLY = 49.0  # $49/month base fee

# Per-service pricing (monthly)
SERVICE_PRICING = {
    # LLM Services
    "gpt-4o": 20.0,
    "gpt-4o-mini": 5.0,
    "claude-sonnet-4": 25.0,
    "gemini-2.5-flash": 10.0,
    
    # Voice Services
    "openai-tts": 15.0,
    "voxtral-tts": 20.0,
    "elevenlabs-tts": 25.0,
    
    # Payment Processing
    "stripe-payments": 0.0,  # Free (Stripe takes their own fees)
    
    # Advanced Features
    "video-upscaling": 50.0,
    "competitive-intelligence": 75.0,
}

# Annual discount percentage
ANNUAL_DISCOUNT = 0.20  # 20% off if paying annually


# ═══════════════════════════════════════════════════════════════════════════════
# PRICING CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class CalculatePricingRequest(BaseModel):
    selected_services: List[str]
    billing_cycle: str = "monthly"  # "monthly" or "annual"


@router.post("/calculate-pricing")
async def calculate_custom_pricing(request: CalculatePricingRequest):
    """
    Calculate pricing for a custom service selection
    
    Returns:
    {
        "base_fee": 49.00,
        "service_fees": {"gpt-4o": 20.00, "voxtral-tts": 20.00},
        "total_monthly": 89.00,
        "total_annual": 854.40,
        "annual_savings": 213.60,
        "selected_services": ["gpt-4o", "voxtral-tts"]
    }
    """
    try:
        # Calculate service fees
        service_fees = {}
        total_services_cost = 0.0
        
        for service_id in request.selected_services:
            if service_id in SERVICE_PRICING:
                price = SERVICE_PRICING[service_id]
                service_fees[service_id] = price
                total_services_cost += price
            else:
                logger.warning(f"Unknown service: {service_id}")
        
        # Total monthly cost
        total_monthly = BASE_PLATFORM_FEE_MONTHLY + total_services_cost
        
        # Annual pricing (with discount)
        total_annual = total_monthly * 12 * (1 - ANNUAL_DISCOUNT)
        annual_savings = (total_monthly * 12) - total_annual
        
        pricing = CustomSubscriptionPricing(
            base_fee=BASE_PLATFORM_FEE_MONTHLY,
            service_fees=service_fees,
            total_monthly=total_monthly,
            total_annual=total_annual,
            annual_savings=annual_savings,
            selected_services=request.selected_services
        )
        
        return pricing
        
    except Exception as e:
        logger.error(f"[Custom Subscription] Pricing calculation error: {e}")
        raise HTTPException(500, f"Failed to calculate pricing: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION CREATION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/create")
async def create_custom_subscription(request: CustomSubscriptionRequest):
    """
    Create a custom subscription plan
    
    Request:
    {
        "user_id": "user_12345",
        "selected_services": ["gpt-4o", "voxtral-tts"],
        "billing_cycle": "monthly"
    }
    
    Returns:
    {
        "plan_id": "custom_xxxxx",
        "pricing": {...},
        "next_steps": "Proceed to payment with Stripe"
    }
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Validate services exist
        for service_id in request.selected_services:
            service = await _db.service_registry.find_one(
                {"service_id": service_id},
                {"_id": 0}
            )
            if not service:
                raise HTTPException(404, f"Service '{service_id}' not found")
        
        # Calculate pricing
        pricing_request = CalculatePricingRequest(
            selected_services=request.selected_services,
            billing_cycle=request.billing_cycle
        )
        pricing = await calculate_custom_pricing(pricing_request)
        
        # Generate plan ID
        plan_id = f"custom_{secrets.token_hex(12)}"
        
        # Calculate period end
        if request.billing_cycle == "monthly":
            period_end = datetime.now(timezone.utc) + timedelta(days=30)
        else:
            period_end = datetime.now(timezone.utc) + timedelta(days=365)
        
        # Create subscription plan
        subscription = {
            "plan_id": plan_id,
            "user_id": request.user_id,
            "plan_type": "custom",
            "selected_services": request.selected_services,
            "pricing": pricing.dict(),
            "billing_cycle": request.billing_cycle,
            "status": "pending_payment",  # Will be "active" after payment
            "created_at": datetime.now(timezone.utc),
            "current_period_end": period_end,
            "stripe_subscription_id": None,  # Will be set after Stripe payment
            "custom_limits": request.custom_limits or {}
        }
        
        # Save to database
        await _db.custom_subscriptions.insert_one(subscription)
        
        logger.info(f"[Custom Subscription] Created plan {plan_id} for user {request.user_id}")
        
        return {
            "success": True,
            "plan_id": plan_id,
            "pricing": pricing,
            "status": "pending_payment",
            "next_steps": "Proceed to payment with Stripe",
            "checkout_url": f"/checkout/{plan_id}"  # Frontend will handle this
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Custom Subscription] Creation error: {e}")
        raise HTTPException(500, f"Failed to create subscription: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/user/{user_id}")
async def get_user_custom_subscription(user_id: str):
    """Get user's custom subscription"""
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        subscription = await _db.custom_subscriptions.find_one(
            {"user_id": user_id, "status": {"$in": ["active", "pending_payment"]}},
            {"_id": 0}
        )
        
        if not subscription:
            raise HTTPException(404, "No custom subscription found for user")
        
        return subscription
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Custom Subscription] Get user subscription error: {e}")
        raise HTTPException(500, f"Failed to get subscription: {str(e)}")


@router.get("/available-services")
async def get_available_services():
    """
    Get all available services for custom subscription builder
    
    Returns list of services with pricing
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Get all services from registry
        services = await _db.service_registry.find(
            {},
            {"_id": 0}
        ).to_list(100)
        
        # Enrich with custom subscription pricing
        enriched_services = []
        for service in services:
            service_id = service.get("service_id")
            service["custom_price_monthly"] = SERVICE_PRICING.get(service_id, 0.0)
            service["available_for_custom"] = service_id in SERVICE_PRICING
            enriched_services.append(service)
        
        return {
            "services": enriched_services,
            "base_platform_fee": BASE_PLATFORM_FEE_MONTHLY,
            "annual_discount": ANNUAL_DISCOUNT * 100  # Return as percentage
        }
        
    except Exception as e:
        logger.error(f"[Custom Subscription] Get services error: {e}")
        raise HTTPException(500, f"Failed to get services: {str(e)}")


@router.delete("/{plan_id}")
async def cancel_custom_subscription(plan_id: str):
    """Cancel a custom subscription"""
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        result = await _db.custom_subscriptions.update_one(
            {"plan_id": plan_id},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, "Subscription not found")
        
        return {
            "success": True,
            "message": "Subscription cancelled successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Custom Subscription] Cancel error: {e}")
        raise HTTPException(500, f"Failed to cancel subscription: {str(e)}")
