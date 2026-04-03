"""
API Key Manager for Reroots AI
Proprietary API key system for controlling access to Reroots AI endpoints.

Features:
- Create/revoke API keys for external clients
- Tiered access (starter/growth/enterprise)
- Monthly usage limits with auto-reset
- Usage tracking and analytics
- Internal frontend whitelisting

MongoDB Collection: reroots_api_keys
"""

import os
import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from functools import wraps

logger = logging.getLogger(__name__)

# MongoDB reference
_db = None

# Master key for internal frontend (whitelisted)
INTERNAL_MASTER_KEY = os.environ.get("REROOTS_INTERNAL_KEY", "reroots-internal-2024")

# Tier configurations
TIER_LIMITS = {
    "starter": 500,       # 500 conversations/month
    "growth": 2000,       # 2000 conversations/month
    "enterprise": 10000,  # 10000 conversations/month
    "unlimited": -1       # No limit (internal use)
}


def set_db(database):
    """Set database reference"""
    global _db
    _db = database


def hash_key(key: str) -> str:
    """Hash an API key for secure storage"""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple:
    """Generate a new API key. Returns (display_key, hashed_key)"""
    # Format: rr_live_xxxxxxxxxxxxxxxxxxxx
    raw_key = f"rr_live_{secrets.token_hex(20)}"
    hashed = hash_key(raw_key)
    return raw_key, hashed


async def create_api_key(
    client_name: str,
    brand: str = "reroots",
    tier: str = "starter",
    monthly_limit: Optional[int] = None,
    expires_in_days: int = 365
) -> Dict[str, Any]:
    """Create a new API key for a client"""
    
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    # Generate key
    display_key, hashed_key = generate_api_key()
    
    # Set limit based on tier if not specified
    if monthly_limit is None:
        monthly_limit = TIER_LIMITS.get(tier, TIER_LIMITS["starter"])
    
    # Create key document
    key_doc = {
        "key_hash": hashed_key,
        "key_preview": display_key[:12] + "..." + display_key[-4:],  # rr_live_xxxx...xxxx
        "client_name": client_name,
        "brand": brand,
        "tier": tier,
        "monthly_limit": monthly_limit,
        "used_this_month": 0,
        "total_used": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat(),
        "active": True,
        "last_used_at": None,
        "usage_history": []
    }
    
    try:
        result = await _db.reroots_api_keys.insert_one(key_doc)
        
        return {
            "success": True,
            "api_key": display_key,  # Only returned once!
            "key_id": str(result.inserted_id),
            "client_name": client_name,
            "tier": tier,
            "monthly_limit": monthly_limit,
            "expires_at": key_doc["expires_at"],
            "warning": "Save this key now! It will not be shown again."
        }
    except Exception as e:
        logger.error(f"[API_KEY] Failed to create key: {e}")
        return {"success": False, "error": str(e)}


async def validate_api_key(api_key: str) -> Dict[str, Any]:
    """
    Validate an API key and check usage limits.
    Returns validation result with key info or error.
    """
    
    if _db is None:
        return {"valid": False, "error": "Database not available"}
    
    # Check for internal master key (frontend whitelist)
    if api_key == INTERNAL_MASTER_KEY:
        return {
            "valid": True,
            "internal": True,
            "client_name": "Reroots Internal",
            "tier": "unlimited",
            "remaining": -1
        }
    
    # Hash the provided key and look it up
    hashed = hash_key(api_key)
    
    try:
        key_doc = await _db.reroots_api_keys.find_one(
            {"key_hash": hashed},
            {"_id": 0, "key_hash": 0}  # Don't return sensitive data
        )
        
        if not key_doc:
            return {"valid": False, "error": "Invalid API key"}
        
        # Check if active
        if not key_doc.get("active", False):
            return {"valid": False, "error": "API key has been revoked"}
        
        # Check expiration
        expires_at = datetime.fromisoformat(key_doc["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at:
            return {"valid": False, "error": "API key has expired"}
        
        # Check monthly limit
        monthly_limit = key_doc.get("monthly_limit", 0)
        used_this_month = key_doc.get("used_this_month", 0)
        
        if monthly_limit > 0 and used_this_month >= monthly_limit:
            return {
                "valid": False,
                "error": f"Monthly limit reached ({used_this_month}/{monthly_limit}). Upgrade your plan or wait for reset.",
                "tier": key_doc.get("tier"),
                "limit_reached": True
            }
        
        # Calculate remaining
        remaining = monthly_limit - used_this_month if monthly_limit > 0 else -1
        
        return {
            "valid": True,
            "internal": False,
            "client_name": key_doc.get("client_name"),
            "brand": key_doc.get("brand"),
            "tier": key_doc.get("tier"),
            "used_this_month": used_this_month,
            "monthly_limit": monthly_limit,
            "remaining": remaining
        }
        
    except Exception as e:
        logger.error(f"[API_KEY] Validation error: {e}")
        return {"valid": False, "error": "Validation failed"}


async def increment_usage(api_key: str) -> bool:
    """Increment usage counter for an API key after successful call"""
    
    if _db is None:
        return False
    
    # Don't track internal key
    if api_key == INTERNAL_MASTER_KEY:
        return True
    
    hashed = hash_key(api_key)
    
    try:
        result = await _db.reroots_api_keys.update_one(
            {"key_hash": hashed},
            {
                "$inc": {"used_this_month": 1, "total_used": 1},
                "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"[API_KEY] Failed to increment usage: {e}")
        return False


async def revoke_api_key(key_preview: str) -> Dict[str, Any]:
    """Revoke an API key by its preview string"""
    
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    try:
        result = await _db.reroots_api_keys.update_one(
            {"key_preview": key_preview},
            {"$set": {"active": False, "revoked_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        if result.modified_count > 0:
            return {"success": True, "message": "API key revoked"}
        else:
            return {"success": False, "error": "Key not found"}
            
    except Exception as e:
        logger.error(f"[API_KEY] Failed to revoke key: {e}")
        return {"success": False, "error": str(e)}


async def list_api_keys(include_inactive: bool = False) -> List[Dict]:
    """List all API keys with usage stats"""
    
    if _db is None:
        return []
    
    try:
        query = {} if include_inactive else {"active": True}
        
        keys = await _db.reroots_api_keys.find(
            query,
            {"_id": 0, "key_hash": 0, "usage_history": 0}  # Don't return sensitive data
        ).sort("created_at", -1).to_list(100)
        
        return keys
        
    except Exception as e:
        logger.error(f"[API_KEY] Failed to list keys: {e}")
        return []


async def get_key_usage(key_preview: str) -> Dict[str, Any]:
    """Get detailed usage for a specific key"""
    
    if _db is None:
        return {"error": "Database not available"}
    
    try:
        key_doc = await _db.reroots_api_keys.find_one(
            {"key_preview": key_preview},
            {"_id": 0, "key_hash": 0}
        )
        
        if not key_doc:
            return {"error": "Key not found"}
        
        return {
            "client_name": key_doc.get("client_name"),
            "tier": key_doc.get("tier"),
            "used_this_month": key_doc.get("used_this_month", 0),
            "monthly_limit": key_doc.get("monthly_limit", 0),
            "total_used": key_doc.get("total_used", 0),
            "last_used_at": key_doc.get("last_used_at"),
            "created_at": key_doc.get("created_at"),
            "expires_at": key_doc.get("expires_at"),
            "active": key_doc.get("active", False)
        }
        
    except Exception as e:
        logger.error(f"[API_KEY] Failed to get usage: {e}")
        return {"error": str(e)}


async def reset_monthly_counters():
    """Reset all monthly usage counters (called by cron on 1st of month)"""
    
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Archive current month's usage before resetting
        now = datetime.now(timezone.utc)
        month_key = now.strftime("%Y-%m")
        
        # Get all keys with usage
        keys_with_usage = await _db.reroots_api_keys.find(
            {"used_this_month": {"$gt": 0}}
        ).to_list(1000)
        
        # Archive and reset each
        for key in keys_with_usage:
            await _db.reroots_api_keys.update_one(
                {"key_hash": key["key_hash"]},
                {
                    "$push": {
                        "usage_history": {
                            "month": month_key,
                            "used": key["used_this_month"]
                        }
                    },
                    "$set": {"used_this_month": 0}
                }
            )
        
        logger.info(f"[API_KEY] Reset monthly counters for {len(keys_with_usage)} keys")
        return {"success": True, "keys_reset": len(keys_with_usage)}
        
    except Exception as e:
        logger.error(f"[API_KEY] Failed to reset counters: {e}")
        return {"success": False, "error": str(e)}


# Decorator for protecting AI endpoints
def require_api_key(func):
    """Decorator to require valid API key for AI endpoints"""
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        from fastapi import HTTPException
        
        # Get API key from header
        api_key = request.headers.get("X-Reroots-API-Key")
        
        # Check for internal request (from reroots.ca frontend)
        origin = request.headers.get("Origin", "")
        referer = request.headers.get("Referer", "")
        
        # Whitelist internal origins
        internal_origins = [
            "https://reroots.ca",
            "https://www.reroots.ca",
            "http://localhost:3000",
            "https://live-support-test.preview.emergentagent.com"
        ]
        
        is_internal = any(
            origin.startswith(o) or referer.startswith(o) 
            for o in internal_origins
        )
        
        # If internal request without API key, use master key
        if is_internal and not api_key:
            api_key = INTERNAL_MASTER_KEY
        
        # Require API key for external requests
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Missing X-Reroots-API-Key header. Contact reroots.ca for access."
            )
        
        # Validate the key
        validation = await validate_api_key(api_key)
        
        if not validation.get("valid"):
            raise HTTPException(
                status_code=401,
                detail=validation.get("error", "Invalid or expired Reroots AI API key. Contact reroots.ca for access.")
            )
        
        # Add key info to request state for tracking
        request.state.api_key_info = validation
        
        # Call the actual function
        result = await func(request, *args, **kwargs)
        
        # Increment usage after successful call
        await increment_usage(api_key)
        
        return result
    
    return wrapper
