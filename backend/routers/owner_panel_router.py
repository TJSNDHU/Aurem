"""
ReRoots AI Owner Panel
Master control panel for managing API credentials, subscribers, and platform settings
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import secrets
import hashlib

router = APIRouter(prefix="/api/owner", tags=["owner-panel"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

# ═══════════════════════════════════════════════════════════════════════════════
# OWNER AUTHENTICATION (Simple token-based for now)
# ═══════════════════════════════════════════════════════════════════════════════

OWNER_TOKEN = os.environ.get("OWNER_PANEL_TOKEN", "owner_secret_token_change_me")

async def verify_owner_token(x_owner_token: str = Header(None)):
    """Verify owner access token"""
    if not x_owner_token or x_owner_token != OWNER_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid owner token")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class APICredential(BaseModel):
    service: str  # stripe, razorpay, twilio, openai, resend, whapi, etc.
    name: str
    api_key: str
    api_secret: Optional[str] = None
    additional_config: Optional[Dict[str, str]] = None
    is_active: bool = True

class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    additional_config: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None

class PlatformSettings(BaseModel):
    setting_key: str
    setting_value: Any
    category: str = "general"


# ═══════════════════════════════════════════════════════════════════════════════
# API CREDENTIALS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

# Supported services and their required fields
SUPPORTED_SERVICES = {
    "stripe": {
        "name": "Stripe",
        "fields": ["api_key"],
        "description": "Payment processing for subscriptions"
    },
    "razorpay": {
        "name": "Razorpay",
        "fields": ["api_key", "api_secret"],
        "description": "Payment processing for India"
    },
    "twilio": {
        "name": "Twilio",
        "fields": ["api_key", "api_secret"],
        "additional": ["phone_number", "verify_service_sid"],
        "description": "SMS, WhatsApp, and Voice calls"
    },
    "openai": {
        "name": "OpenAI",
        "fields": ["api_key"],
        "description": "GPT models for AI features"
    },
    "anthropic": {
        "name": "Anthropic",
        "fields": ["api_key"],
        "description": "Claude models for AI features"
    },
    "resend": {
        "name": "Resend",
        "fields": ["api_key"],
        "description": "Email sending service"
    },
    "whapi": {
        "name": "WHAPI",
        "fields": ["api_key"],
        "description": "WhatsApp Business API"
    },
    "google_calendar": {
        "name": "Google Calendar",
        "fields": ["api_key", "api_secret"],
        "description": "Appointment scheduling"
    },
    "github": {
        "name": "GitHub",
        "fields": ["api_key"],
        "additional": ["client_id", "client_secret"],
        "description": "Repository integration for RAG"
    },
    "emergent_llm": {
        "name": "Emergent LLM",
        "fields": ["api_key"],
        "description": "Universal LLM key for multiple providers"
    }
}

@router.get("/services")
async def get_supported_services():
    """Get list of supported API services"""
    return {"services": SUPPORTED_SERVICES}

@router.post("/credentials")
async def add_credential(data: APICredential, _: bool = Depends(verify_owner_token)):
    """Add new API credential"""
    if data.service not in SUPPORTED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unsupported service: {data.service}")
    
    # Check if already exists
    existing = await db.owner_credentials.find_one({"service": data.service})
    if existing:
        raise HTTPException(status_code=400, detail=f"Credential for {data.service} already exists. Use PATCH to update.")
    
    credential = {
        "service": data.service,
        "name": data.name,
        "api_key_encrypted": data.api_key,  # In production, encrypt this!
        "api_secret_encrypted": data.api_secret if data.api_secret else None,
        "additional_config": data.additional_config or {},
        "is_active": data.is_active,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.owner_credentials.insert_one(credential)
    
    return {
        "success": True,
        "service": data.service,
        "message": f"Credential for {data.service} added successfully"
    }

@router.get("/credentials")
async def list_credentials(_: bool = Depends(verify_owner_token)):
    """List all API credentials (keys masked)"""
    credentials = await db.owner_credentials.find({}, {"_id": 0}).to_list(100)
    
    # Mask sensitive data
    for cred in credentials:
        if cred.get("api_key_encrypted"):
            key = cred["api_key_encrypted"]
            cred["api_key_masked"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
            del cred["api_key_encrypted"]
        if cred.get("api_secret_encrypted"):
            cred["api_secret_masked"] = "***"
            del cred["api_secret_encrypted"]
    
    return {"credentials": credentials}

@router.get("/credentials/{service}")
async def get_credential(service: str, _: bool = Depends(verify_owner_token)):
    """Get credential for a specific service (key masked)"""
    credential = await db.owner_credentials.find_one({"service": service}, {"_id": 0})
    if not credential:
        raise HTTPException(status_code=404, detail=f"No credential found for {service}")
    
    # Mask sensitive data
    if credential.get("api_key_encrypted"):
        key = credential["api_key_encrypted"]
        credential["api_key_masked"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
        del credential["api_key_encrypted"]
    if credential.get("api_secret_encrypted"):
        credential["api_secret_masked"] = "***"
        del credential["api_secret_encrypted"]
    
    return {"credential": credential}

@router.patch("/credentials/{service}")
async def update_credential(service: str, data: CredentialUpdate, _: bool = Depends(verify_owner_token)):
    """Update API credential"""
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.api_key is not None:
        update_data["api_key_encrypted"] = data.api_key
    if data.api_secret is not None:
        update_data["api_secret_encrypted"] = data.api_secret
    if data.additional_config is not None:
        update_data["additional_config"] = data.additional_config
    if data.is_active is not None:
        update_data["is_active"] = data.is_active
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = await db.owner_credentials.update_one(
        {"service": service},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail=f"No credential found for {service}")
    
    return {"success": True, "message": f"Credential for {service} updated"}

@router.delete("/credentials/{service}")
async def delete_credential(service: str, _: bool = Depends(verify_owner_token)):
    """Delete API credential"""
    result = await db.owner_credentials.delete_one({"service": service})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"No credential found for {service}")
    
    return {"success": True, "message": f"Credential for {service} deleted"}


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIBER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/subscribers")
async def list_subscribers(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    _: bool = Depends(verify_owner_token)
):
    """List all subscribers with filtering"""
    query = {}
    if status:
        query["status"] = status
    if tier:
        query["tier"] = tier
    
    subscribers = await db.subscriptions.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.subscriptions.count_documents(query)
    
    return {
        "subscribers": subscribers,
        "total": total,
        "limit": limit,
        "skip": skip
    }

@router.get("/subscribers/{subscription_id}")
async def get_subscriber_detail(subscription_id: str, _: bool = Depends(verify_owner_token)):
    """Get detailed subscriber information"""
    subscription = await db.subscriptions.find_one(
        {"subscription_id": subscription_id},
        {"_id": 0}
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    # Get API keys
    api_keys = await db.subscriber_api_keys.find(
        {"subscription_id": subscription_id},
        {"_id": 0, "api_key_hash": 0}
    ).to_list(100)
    
    # Get usage history
    usage = await db.api_usage_logs.find(
        {"subscription_id": subscription_id}
    ).sort("timestamp", -1).limit(100).to_list(100)
    
    # Get payment history
    payments = await db.payment_transactions.find(
        {"subscription_id": subscription_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return {
        "subscription": subscription,
        "api_keys": api_keys,
        "recent_usage": usage,
        "payment_history": payments
    }

@router.post("/subscribers/{subscription_id}/suspend")
async def suspend_subscriber(subscription_id: str, _: bool = Depends(verify_owner_token)):
    """Suspend a subscriber"""
    result = await db.subscriptions.update_one(
        {"subscription_id": subscription_id},
        {"$set": {
            "status": "suspended",
            "suspended_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    # Suspend all API keys
    await db.subscriber_api_keys.update_many(
        {"subscription_id": subscription_id},
        {"$set": {"status": "suspended"}}
    )
    
    return {"success": True, "message": "Subscriber suspended"}

@router.post("/subscribers/{subscription_id}/activate")
async def activate_subscriber(subscription_id: str, _: bool = Depends(verify_owner_token)):
    """Reactivate a suspended subscriber"""
    result = await db.subscriptions.update_one(
        {"subscription_id": subscription_id},
        {"$set": {
            "status": "active",
            "updated_at": datetime.now(timezone.utc)
        },
        "$unset": {"suspended_at": ""}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    # Reactivate all API keys
    await db.subscriber_api_keys.update_many(
        {"subscription_id": subscription_id},
        {"$set": {"status": "active"}}
    )
    
    return {"success": True, "message": "Subscriber reactivated"}


# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/analytics/dashboard")
async def get_dashboard_analytics(_: bool = Depends(verify_owner_token)):
    """Get comprehensive platform analytics"""
    
    # Time ranges
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    
    # Subscriber stats
    total_subscribers = await db.subscriptions.count_documents({})
    active_subscribers = await db.subscriptions.count_documents({"status": "active"})
    new_this_month = await db.subscriptions.count_documents({"created_at": {"$gte": month_start}})
    
    # Revenue
    current_mrr = await db.subscriptions.aggregate([
        {"$match": {"status": "active", "billing_cycle": "monthly"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}}
    ]).to_list(1)
    
    current_arr = await db.subscriptions.aggregate([
        {"$match": {"status": "active", "billing_cycle": "yearly"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}}
    ]).to_list(1)
    
    # API usage
    total_api_calls = await db.api_usage_logs.count_documents({"timestamp": {"$gte": month_start}})
    
    # Usage by feature
    feature_usage = await db.api_usage_logs.aggregate([
        {"$match": {"timestamp": {"$gte": month_start}}},
        {"$group": {"_id": "$feature", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]).to_list(20)
    
    # Tier breakdown
    tier_breakdown = await db.subscriptions.aggregate([
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$tier", "count": {"$sum": 1}, "revenue": {"$sum": "$price"}}}
    ]).to_list(10)
    
    # Daily signups (last 30 days)
    daily_signups = await db.subscriptions.aggregate([
        {"$match": {"created_at": {"$gte": now - timedelta(days=30)}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]).to_list(30)
    
    return {
        "subscribers": {
            "total": total_subscribers,
            "active": active_subscribers,
            "new_this_month": new_this_month,
            "churn_rate": round((total_subscribers - active_subscribers) / max(total_subscribers, 1) * 100, 2)
        },
        "revenue": {
            "mrr": current_mrr[0]["total"] if current_mrr else 0,
            "arr": current_arr[0]["total"] if current_arr else 0,
            "total_monthly": (current_mrr[0]["total"] if current_mrr else 0) + ((current_arr[0]["total"] if current_arr else 0) / 12)
        },
        "api_usage": {
            "total_calls_this_month": total_api_calls,
            "by_feature": {f["_id"]: f["count"] for f in feature_usage}
        },
        "tier_breakdown": {t["_id"]: {"count": t["count"], "revenue": t["revenue"]} for t in tier_breakdown},
        "daily_signups": daily_signups
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/settings")
async def get_settings(category: Optional[str] = None, _: bool = Depends(verify_owner_token)):
    """Get platform settings"""
    query = {}
    if category:
        query["category"] = category
    
    settings = await db.owner_settings.find(query, {"_id": 0}).to_list(100)
    return {"settings": {s["setting_key"]: s["setting_value"] for s in settings}}

@router.post("/settings")
async def update_setting(data: PlatformSettings, _: bool = Depends(verify_owner_token)):
    """Update or create a platform setting"""
    await db.owner_settings.update_one(
        {"setting_key": data.setting_key},
        {"$set": {
            "setting_value": data.setting_value,
            "category": data.category,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    
    return {"success": True, "message": f"Setting '{data.setting_key}' updated"}


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE TOGGLES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/features/status")
async def get_feature_status(_: bool = Depends(verify_owner_token)):
    """Get status of all AI features"""
    feature_status = await db.owner_settings.find_one(
        {"setting_key": "feature_toggles"},
        {"_id": 0}
    )
    
    if not feature_status:
        # Default all features to enabled
        return {"features": {
            "ai_chat": True,
            "weather_skincare": True,
            "voice_commands": True,
            "toon_optimization": True,
            "skin_analysis": True,
            "sms_alerts": True,
            "sentiment_analysis": True,
            "translation": True,
            "whatsapp_alerts": True,
            "video_generation": True,
            "inventory_ai": True,
            "churn_prediction": True,
            "ai_email": True,
            "biometric_auth": True,
            "github_integration": True,
            "document_scanner": True,
            "appointment_scheduler": True,
            "product_description_ai": True
        }}
    
    return {"features": feature_status.get("setting_value", {})}

@router.post("/features/toggle/{feature_id}")
async def toggle_feature(feature_id: str, enabled: bool, _: bool = Depends(verify_owner_token)):
    """Enable or disable a specific feature globally"""
    await db.owner_settings.update_one(
        {"setting_key": "feature_toggles"},
        {"$set": {f"setting_value.{feature_id}": enabled, "updated_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    
    return {"success": True, "feature": feature_id, "enabled": enabled}
