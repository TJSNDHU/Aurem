"""
ReRoots AI Subscription System
Manages subscription tiers, API key limits, and billing
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import secrets
import hashlib

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION TIERS CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SUBSCRIPTION_TIERS = {
    "starter": {
        "name": "Starter",
        "price_monthly": 29.0,
        "price_yearly": 290.0,
        "api_calls_limit": 1000,
        "rate_limit_per_min": 10,
        "features": [
            "ai_chat",
            "weather_skincare",
            "voice_commands",
            "toon_optimization"
        ],
        "support": "email",
        "description": "Perfect for small businesses getting started with AI"
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 99.0,
        "price_yearly": 990.0,
        "api_calls_limit": 10000,
        "rate_limit_per_min": 30,
        "features": [
            "ai_chat",
            "weather_skincare",
            "voice_commands",
            "toon_optimization",
            "skin_analysis",
            "sms_alerts",
            "sentiment_analysis",
            "translation"
        ],
        "support": "priority_email",
        "description": "For growing businesses needing advanced AI features"
    },
    "business": {
        "name": "Business",
        "price_monthly": 299.0,
        "price_yearly": 2990.0,
        "api_calls_limit": 50000,
        "rate_limit_per_min": 100,
        "features": [
            "ai_chat",
            "weather_skincare",
            "voice_commands",
            "toon_optimization",
            "skin_analysis",
            "sms_alerts",
            "sentiment_analysis",
            "translation",
            "whatsapp_alerts",
            "video_generation",
            "inventory_ai",
            "churn_prediction"
        ],
        "support": "chat_email",
        "description": "Full-featured AI suite for established businesses"
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 999.0,
        "price_yearly": 9990.0,
        "api_calls_limit": 500000,
        "rate_limit_per_min": 500,
        "features": [
            "ai_chat",
            "weather_skincare",
            "voice_commands",
            "toon_optimization",
            "skin_analysis",
            "sms_alerts",
            "sentiment_analysis",
            "translation",
            "whatsapp_alerts",
            "video_generation",
            "inventory_ai",
            "churn_prediction",
            "ai_email",
            "biometric_auth",
            "github_integration",
            "document_scanner",
            "appointment_scheduler",
            "product_description_ai",
            "custom_integrations"
        ],
        "support": "dedicated_phone",
        "description": "Unlimited access with dedicated support"
    },
    "custom": {
        "name": "Custom",
        "price_monthly": None,  # Negotiable
        "price_yearly": None,
        "api_calls_limit": -1,  # Unlimited
        "rate_limit_per_min": -1,  # No limit
        "features": ["all"],
        "support": "dedicated_team",
        "description": "Tailored solution for large enterprises"
    }
}

# All available AI features
ALL_FEATURES = {
    "ai_chat": {"name": "AI Chat Assistant", "icon": "MessageSquare", "description": "RAG-powered skincare advisor"},
    "weather_skincare": {"name": "Weather Skincare", "icon": "Cloud", "description": "Climate-based recommendations"},
    "voice_commands": {"name": "Voice Commands", "icon": "Mic", "description": "Multi-language voice I/O"},
    "toon_optimization": {"name": "TOON Optimization", "icon": "Zap", "description": "50% token savings"},
    "skin_analysis": {"name": "AI Skin Analysis", "icon": "Camera", "description": "Photo-based skin detection"},
    "sms_alerts": {"name": "SMS Alerts", "icon": "MessageCircle", "description": "Order & OTP notifications"},
    "sentiment_analysis": {"name": "Sentiment Analysis", "icon": "Heart", "description": "Review analysis & trends"},
    "translation": {"name": "Multi-Language", "icon": "Globe", "description": "Auto-translate content"},
    "whatsapp_alerts": {"name": "WhatsApp Alerts", "icon": "Phone", "description": "WhatsApp notifications"},
    "video_generation": {"name": "Video Generation", "icon": "Video", "description": "AI product videos"},
    "inventory_ai": {"name": "Inventory AI", "icon": "Package", "description": "Predictive stock management"},
    "churn_prediction": {"name": "Churn Prediction", "icon": "TrendingDown", "description": "Customer retention AI"},
    "ai_email": {"name": "AI Email", "icon": "Mail", "description": "Automated email campaigns"},
    "biometric_auth": {"name": "Biometric Auth", "icon": "Fingerprint", "description": "Face/Voice/Touch ID"},
    "github_integration": {"name": "GitHub Integration", "icon": "Github", "description": "Auto-build RAG from repos"},
    "document_scanner": {"name": "Document Scanner", "icon": "FileText", "description": "OCR & data extraction"},
    "appointment_scheduler": {"name": "Appointments", "icon": "Calendar", "description": "Google Calendar booking"},
    "product_description_ai": {"name": "Product AI", "icon": "Edit", "description": "Auto-generate descriptions"},
    "custom_integrations": {"name": "Custom APIs", "icon": "Code", "description": "Custom webhook integrations"}
}


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SubscriptionCreate(BaseModel):
    subscriber_email: str
    subscriber_name: str
    tier: str
    billing_cycle: str = "monthly"  # monthly or yearly
    payment_method: str = "stripe"  # stripe or razorpay
    custom_features: Optional[List[str]] = None
    custom_api_limit: Optional[int] = None

class SubscriptionUpdate(BaseModel):
    tier: Optional[str] = None
    billing_cycle: Optional[str] = None
    custom_features: Optional[List[str]] = None
    custom_api_limit: Optional[int] = None
    status: Optional[str] = None

class APIKeyCreate(BaseModel):
    subscription_id: str
    key_name: str = "Default Key"

class UsageRecord(BaseModel):
    api_key: str
    feature: str
    tokens_used: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# TIER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/tiers")
async def get_subscription_tiers():
    """Get all available subscription tiers with pricing"""
    return {
        "tiers": SUBSCRIPTION_TIERS,
        "features": ALL_FEATURES
    }

@router.get("/tiers/{tier_id}")
async def get_tier_details(tier_id: str):
    """Get details for a specific tier"""
    if tier_id not in SUBSCRIPTION_TIERS:
        raise HTTPException(status_code=404, detail="Tier not found")
    
    tier = SUBSCRIPTION_TIERS[tier_id]
    features_detail = []
    for feat_id in tier["features"]:
        if feat_id == "all":
            features_detail = list(ALL_FEATURES.values())
            break
        if feat_id in ALL_FEATURES:
            features_detail.append({**ALL_FEATURES[feat_id], "id": feat_id})
    
    return {
        "tier_id": tier_id,
        **tier,
        "features_detail": features_detail
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/create")
async def create_subscription(data: SubscriptionCreate):
    """Create a new subscription (called after payment success)"""
    if data.tier not in SUBSCRIPTION_TIERS and data.tier != "custom":
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    tier_config = SUBSCRIPTION_TIERS.get(data.tier, SUBSCRIPTION_TIERS["custom"])
    
    # Generate subscription ID
    subscription_id = f"sub_{secrets.token_hex(12)}"
    
    # Calculate pricing
    if data.tier == "custom":
        price = 0  # Custom pricing handled separately
    else:
        price = tier_config["price_yearly"] if data.billing_cycle == "yearly" else tier_config["price_monthly"]
    
    # Create subscription record
    subscription = {
        "subscription_id": subscription_id,
        "subscriber_email": data.subscriber_email,
        "subscriber_name": data.subscriber_name,
        "tier": data.tier,
        "billing_cycle": data.billing_cycle,
        "payment_method": data.payment_method,
        "status": "active",
        "price": price,
        "api_calls_limit": data.custom_api_limit or tier_config["api_calls_limit"],
        "rate_limit_per_min": tier_config["rate_limit_per_min"],
        "features": data.custom_features or tier_config["features"],
        "usage_this_month": 0,
        "current_period_start": datetime.now(timezone.utc),
        "current_period_end": datetime.now(timezone.utc) + timedelta(days=30 if data.billing_cycle == "monthly" else 365),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.subscriptions.insert_one(subscription)
    
    # Generate initial API key
    api_key = f"rr_live_{secrets.token_hex(24)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    await db.subscriber_api_keys.insert_one({
        "api_key_hash": api_key_hash,
        "api_key_prefix": api_key[:12],
        "subscription_id": subscription_id,
        "subscriber_email": data.subscriber_email,
        "key_name": "Default Key",
        "status": "active",
        "usage_count": 0,
        "created_at": datetime.now(timezone.utc),
        "last_used_at": None
    })
    
    # Return with unhashed key (only shown once)
    del subscription["_id"]
    return {
        "subscription": subscription,
        "api_key": api_key,
        "message": "Save this API key securely - it won't be shown again!"
    }

@router.get("/list")
async def list_subscriptions(status: Optional[str] = None, limit: int = 50, skip: int = 0):
    """List all subscriptions (Owner access)"""
    query = {}
    if status:
        query["status"] = status
    
    subscriptions = await db.subscriptions.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.subscriptions.count_documents(query)
    
    return {
        "subscriptions": subscriptions,
        "total": total,
        "limit": limit,
        "skip": skip
    }

@router.get("/{subscription_id}")
async def get_subscription(subscription_id: str):
    """Get subscription details"""
    subscription = await db.subscriptions.find_one(
        {"subscription_id": subscription_id},
        {"_id": 0}
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Get API keys for this subscription
    api_keys = await db.subscriber_api_keys.find(
        {"subscription_id": subscription_id},
        {"_id": 0, "api_key_hash": 0}
    ).to_list(100)
    
    # Get usage stats
    usage_stats = await db.api_usage_logs.aggregate([
        {"$match": {"subscription_id": subscription_id}},
        {"$group": {
            "_id": "$feature",
            "total_calls": {"$sum": 1},
            "total_tokens": {"$sum": "$tokens_used"}
        }}
    ]).to_list(100)
    
    return {
        "subscription": subscription,
        "api_keys": api_keys,
        "usage_by_feature": usage_stats
    }

@router.patch("/{subscription_id}")
async def update_subscription(subscription_id: str, data: SubscriptionUpdate):
    """Update subscription (upgrade/downgrade)"""
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = await db.subscriptions.update_one(
        {"subscription_id": subscription_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    return {"success": True, "message": "Subscription updated"}

@router.delete("/{subscription_id}")
async def cancel_subscription(subscription_id: str):
    """Cancel a subscription"""
    result = await db.subscriptions.update_one(
        {"subscription_id": subscription_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Deactivate all API keys
    await db.subscriber_api_keys.update_many(
        {"subscription_id": subscription_id},
        {"$set": {"status": "revoked"}}
    )
    
    return {"success": True, "message": "Subscription cancelled"}


# ═══════════════════════════════════════════════════════════════════════════════
# API KEY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{subscription_id}/api-keys")
async def create_api_key(subscription_id: str, data: APIKeyCreate):
    """Create a new API key for a subscription"""
    subscription = await db.subscriptions.find_one({"subscription_id": subscription_id})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    if subscription["status"] != "active":
        raise HTTPException(status_code=400, detail="Subscription is not active")
    
    # Generate new API key
    api_key = f"rr_live_{secrets.token_hex(24)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    await db.subscriber_api_keys.insert_one({
        "api_key_hash": api_key_hash,
        "api_key_prefix": api_key[:12],
        "subscription_id": subscription_id,
        "subscriber_email": subscription["subscriber_email"],
        "key_name": data.key_name,
        "status": "active",
        "usage_count": 0,
        "created_at": datetime.now(timezone.utc),
        "last_used_at": None
    })
    
    return {
        "api_key": api_key,
        "key_name": data.key_name,
        "message": "Save this API key securely - it won't be shown again!"
    }

@router.delete("/{subscription_id}/api-keys/{key_prefix}")
async def revoke_api_key(subscription_id: str, key_prefix: str):
    """Revoke an API key"""
    result = await db.subscriber_api_keys.update_one(
        {"subscription_id": subscription_id, "api_key_prefix": key_prefix},
        {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc)}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    
    return {"success": True, "message": "API key revoked"}


# ═══════════════════════════════════════════════════════════════════════════════
# USAGE TRACKING & ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{subscription_id}/usage")
async def get_usage_stats(subscription_id: str, days: int = 30):
    """Get usage statistics for a subscription"""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Daily usage
    daily_usage = await db.api_usage_logs.aggregate([
        {
            "$match": {
                "subscription_id": subscription_id,
                "timestamp": {"$gte": since}
            }
        },
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "calls": {"$sum": 1},
                "tokens": {"$sum": "$tokens_used"}
            }
        },
        {"$sort": {"_id": 1}}
    ]).to_list(100)
    
    # Usage by feature
    feature_usage = await db.api_usage_logs.aggregate([
        {
            "$match": {
                "subscription_id": subscription_id,
                "timestamp": {"$gte": since}
            }
        },
        {
            "$group": {
                "_id": "$feature",
                "calls": {"$sum": 1},
                "tokens": {"$sum": "$tokens_used"}
            }
        }
    ]).to_list(100)
    
    # Get subscription limits
    subscription = await db.subscriptions.find_one(
        {"subscription_id": subscription_id},
        {"_id": 0, "api_calls_limit": 1, "usage_this_month": 1}
    )
    
    return {
        "daily_usage": daily_usage,
        "feature_usage": feature_usage,
        "current_usage": subscription.get("usage_this_month", 0) if subscription else 0,
        "limit": subscription.get("api_calls_limit", 0) if subscription else 0,
        "period_days": days
    }


# ═══════════════════════════════════════════════════════════════════════════════
# OWNER ANALYTICS (Aggregate across all subscriptions)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/analytics/overview")
async def get_owner_analytics():
    """Get analytics overview for the owner"""
    
    # Total subscribers by tier
    tier_breakdown = await db.subscriptions.aggregate([
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$tier", "count": {"$sum": 1}}}
    ]).to_list(10)
    
    # Total revenue
    revenue = await db.subscriptions.aggregate([
        {"$match": {"status": "active"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}}
    ]).to_list(1)
    
    # Total API calls this month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)
    api_calls = await db.api_usage_logs.count_documents({"timestamp": {"$gte": month_start}})
    
    # Active subscribers
    active_subs = await db.subscriptions.count_documents({"status": "active"})
    
    # Total API keys
    total_keys = await db.subscriber_api_keys.count_documents({"status": "active"})
    
    return {
        "active_subscribers": active_subs,
        "total_api_keys": total_keys,
        "api_calls_this_month": api_calls,
        "monthly_revenue": revenue[0]["total"] if revenue else 0,
        "tier_breakdown": {t["_id"]: t["count"] for t in tier_breakdown}
    }
