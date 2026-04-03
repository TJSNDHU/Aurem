"""
AUREM Subscription API Routes
Revenue Layer - Tiered Access Control
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscription", tags=["Subscription & Billing"])

# Database reference
db = None

def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # TODO: Decode JWT and get real user_id
    return {"user_id": "admin", "email": "admin@aurem.ai", "role": "admin"}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class CreateSubscriptionRequest(BaseModel):
    tier: str  # free, basic, pro, enterprise
    duration_days: int = 30


class UpgradeRequest(BaseModel):
    new_tier: str


class GrantFreeAccessRequest(BaseModel):
    user_id: str
    admin_notes: str = ""


class CheckFeatureRequest(BaseModel):
    feature: str


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/my-plan")
async def get_my_plan(user = Depends(get_current_user)):
    """Get current user's subscription plan"""
    from services.subscription_manager import get_subscription_manager
    
    manager = get_subscription_manager(db)
    subscription = await manager.get_subscription(user["user_id"])
    
    if not subscription:
        return {
            "has_subscription": False,
            "message": "No active subscription"
        }
    
    return {
        "has_subscription": True,
        "subscription": subscription.dict(),
        "features": [f.value for f in subscription.features],
        "limits": subscription.limits.dict(),
        "usage": subscription.current_usage
    }


@router.post("/create")
async def create_subscription(
    request: CreateSubscriptionRequest,
    user = Depends(get_current_user)
):
    """Create new subscription"""
    from services.subscription_manager import get_subscription_manager, SubscriptionTier
    
    manager = get_subscription_manager(db)
    
    try:
        tier = SubscriptionTier(request.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")
    
    subscription = await manager.create_subscription(
        user_id=user["user_id"],
        tier=tier,
        duration_days=request.duration_days
    )
    
    return {
        "success": True,
        "subscription": subscription.dict()
    }


@router.post("/upgrade")
async def upgrade_subscription(
    request: UpgradeRequest,
    user = Depends(get_current_user)
):
    """Upgrade subscription tier"""
    from services.subscription_manager import get_subscription_manager, SubscriptionTier
    
    manager = get_subscription_manager(db)
    
    try:
        new_tier = SubscriptionTier(request.new_tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.new_tier}")
    
    result = await manager.upgrade_subscription(user["user_id"], new_tier)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/check-feature")
async def check_feature_access(
    request: CheckFeatureRequest,
    user = Depends(get_current_user)
):
    """Check if user has access to a feature"""
    from services.subscription_manager import get_subscription_manager, FeatureAccess
    
    manager = get_subscription_manager(db)
    
    try:
        feature = FeatureAccess(request.feature)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feature: {request.feature}")
    
    access = await manager.check_feature_access(user["user_id"], feature)
    
    return access


@router.post("/check-limit/{resource}")
async def check_usage_limit(
    resource: str,
    user = Depends(get_current_user)
):
    """Check usage limit for a resource"""
    from services.subscription_manager import get_subscription_manager
    
    manager = get_subscription_manager(db)
    limit_check = await manager.check_usage_limit(user["user_id"], resource)
    
    return limit_check


@router.get("/usage")
async def get_usage_stats(user = Depends(get_current_user)):
    """Get current usage statistics"""
    from services.subscription_manager import get_subscription_manager
    
    manager = get_subscription_manager(db)
    subscription = await manager.get_subscription(user["user_id"])
    
    if not subscription:
        return {
            "has_subscription": False,
            "usage": {}
        }
    
    # Calculate percentages
    usage_percentages = {}
    for key, current in subscription.current_usage.items():
        limit_key = f"max_{key}_per_month" if key in ["messages", "voice_minutes"] else f"max_{key}"
        limit = getattr(subscription.limits, limit_key, 0)
        
        if limit > 0:
            usage_percentages[key] = {
                "current": current,
                "limit": limit,
                "percentage": round((current / limit) * 100, 1)
            }
    
    return {
        "has_subscription": True,
        "tier": subscription.tier.value,
        "usage": usage_percentages,
        "period": {
            "start": subscription.start_date.isoformat(),
            "end": subscription.end_date.isoformat() if subscription.end_date else None
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/admin/grant-free-access")
async def grant_free_access(
    request: GrantFreeAccessRequest,
    user = Depends(get_current_user)
):
    """Admin: Grant free unlimited access to a user"""
    # Check if admin
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from services.subscription_manager import get_subscription_manager
    
    manager = get_subscription_manager(db)
    result = await manager.grant_free_access(
        user_id=request.user_id,
        admin_notes=request.admin_notes
    )
    
    return result


@router.get("/admin/expiring")
async def get_expiring_subscriptions(
    days: int = 7,
    user = Depends(get_current_user)
):
    """Admin: Get subscriptions expiring soon"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from services.subscription_manager import get_subscription_manager
    
    manager = get_subscription_manager(db)
    expiring = await manager.check_expiry_soon(days)
    
    return {
        "threshold_days": days,
        "count": len(expiring),
        "subscriptions": expiring
    }


@router.post("/admin/send-expiry-notifications")
async def send_expiry_notifications(user = Depends(get_current_user)):
    """Admin: Send notifications for expiring subscriptions"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from services.subscription_manager import get_subscription_manager
    
    manager = get_subscription_manager(db)
    count = await manager.send_expiry_notifications()
    
    return {
        "notifications_sent": count
    }


@router.get("/tiers")
async def get_available_tiers():
    """Get all available subscription tiers and their features"""
    from services.subscription_manager import SubscriptionTier, FeatureAccess
    
    manager = get_subscription_manager(db)
    
    tiers = {}
    for tier in SubscriptionTier:
        if tier == SubscriptionTier.CUSTOM:
            continue  # Skip custom tier
        
        tiers[tier.value] = {
            "name": tier.value.title(),
            "features": [f.value for f in manager.tier_features.get(tier, [])],
            "limits": manager.tier_limits.get(tier).dict() if tier in manager.tier_limits else {}
        }
    
    return {
        "tiers": tiers,
        "available_features": [f.value for f in FeatureAccess]
    }


print("[STARTUP] Subscription & Billing Routes loaded")
