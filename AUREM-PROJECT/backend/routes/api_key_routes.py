"""
API Key Routes for Reroots AI
Admin endpoints for managing API keys
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import logging

from services.api_key_manager import (
    create_api_key,
    revoke_api_key,
    list_api_keys,
    get_key_usage,
    reset_monthly_counters,
    TIER_LIMITS,
    set_db as set_api_key_db
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/api-keys", tags=["api-keys"])

# Database reference
_db = None


def set_db(database):
    """Set database reference"""
    global _db
    _db = database
    set_api_key_db(database)


class CreateKeyRequest(BaseModel):
    client_name: str
    brand: str = "reroots"
    tier: str = "starter"
    monthly_limit: Optional[int] = None
    expires_in_days: int = 365


async def get_current_user(request: Request):
    """Get current user from request"""
    from server import get_current_user as server_get_user
    return await server_get_user(request)


@router.get("/tiers")
async def get_tier_info():
    """Get available tiers and their limits"""
    return {
        "tiers": {
            tier: {
                "limit": limit,
                "description": f"{limit} conversations/month" if limit > 0 else "Unlimited"
            }
            for tier, limit in TIER_LIMITS.items()
        }
    }


@router.post("/create")
async def create_key(request: Request, body: CreateKeyRequest):
    """Create a new API key for a client"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if body.tier not in TIER_LIMITS:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Choose from: {list(TIER_LIMITS.keys())}")
    
    result = await create_api_key(
        client_name=body.client_name,
        brand=body.brand,
        tier=body.tier,
        monthly_limit=body.monthly_limit,
        expires_in_days=body.expires_in_days
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create key"))
    
    return result


@router.get("")
async def list_keys(request: Request, include_inactive: bool = False):
    """List all API keys with usage stats"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    keys = await list_api_keys(include_inactive=include_inactive)
    
    return {
        "success": True,
        "keys": keys,
        "count": len(keys)
    }


@router.get("/{key_preview}/usage")
async def get_usage(request: Request, key_preview: str):
    """Get detailed usage for a specific key"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    usage = await get_key_usage(key_preview)
    
    if "error" in usage:
        raise HTTPException(status_code=404, detail=usage["error"])
    
    return {
        "success": True,
        "usage": usage
    }


@router.delete("/{key_preview}")
async def revoke_key(request: Request, key_preview: str):
    """Revoke an API key"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await revoke_api_key(key_preview)
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Failed to revoke key"))
    
    return result


@router.post("/reset-monthly")
async def reset_monthly(request: Request):
    """Manually reset monthly counters (also runs automatically on 1st of month)"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await reset_monthly_counters()
    
    return result
