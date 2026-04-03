"""
AUREM ADMIN MISSION CONTROL
Central control panel for managing ALL services, APIs, subscriptions, and tokens

ALL responses are in TOON format for maximum efficiency

Endpoints:
- GET /api/admin/mission-control/dashboard - Complete dashboard in TOON
- GET /api/admin/mission-control/services - Service registry
- POST /api/admin/mission-control/services/add-key - Add API key for service
- POST /api/admin/mission-control/services/remove-key - Remove API key
- GET /api/admin/mission-control/subscriptions - All subscriptions
- GET /api/admin/mission-control/usage - Usage analytics
- POST /api/admin/mission-control/recharge - Recharge tokens/credits
- POST /api/admin/mission-control/service/toggle - Start/stop service
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import secrets
import logging

from services.toon_service import get_toon_service
from utils.aurem_encryption import encrypt_api_key, decrypt_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/mission-control", tags=["Admin Mission Control"])

# MongoDB reference
_db = None

def set_db(database):
    global _db
    _db = database
    get_toon_service().set_db(database)


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class AddAPIKeyRequest(BaseModel):
    service_id: str  # gpt-4o, voxtral-tts, stripe-payments, etc.
    api_key: str  # The actual API key (will be encrypted)
    notes: Optional[str] = None
    monthly_spend_limit: Optional[float] = None  # Optional spending limit


class RemoveAPIKeyRequest(BaseModel):
    key_id: str
    service_id: str


class RechargeRequest(BaseModel):
    service_id: str
    amount_usd: float
    tokens_added: Optional[int] = None
    credits_added: Optional[float] = None
    payment_method: str = "manual"  # stripe, paypal, manual
    notes: Optional[str] = None


class ToggleServiceRequest(BaseModel):
    service_id: str
    action: str  # "start", "stop", "pause"


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN AUTHENTICATION (Simple - enhance later)
# ═══════════════════════════════════════════════════════════════════════════════

async def verify_admin(x_admin_key: Optional[str] = Header(None)):
    """
    Verify admin authentication
    For now, simple key check. In production, use JWT with admin role.
    """
    # TODO: Implement proper admin auth
    # For now, allow if X-Admin-Key header is present
    if not x_admin_key:
        raise HTTPException(401, "Admin authentication required")
    return x_admin_key


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD & OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def get_mission_control_dashboard(admin=Depends(verify_admin)):
    """
    Complete admin dashboard in TOON format
    
    Returns:
    AdminDashboard:
      metrics:
        total_active_subscriptions: 150
        mrr: $35000.00
        arr: $420000.00
      tiers:
        free: 50
        starter: 60
        professional: 30
        enterprise: 10
      services: Service[15]{id, status, spend}: gpt-4o, active, 1234.56; voxtral, active, 234.50; ...
      top_users: User[5]{id, tokens, cost}: user_abc, 150000, 45.67; ...
    """
    toon_service = get_toon_service()
    
    try:
        dashboard_toon = await toon_service.get_admin_dashboard_toon()
        
        return {
            "format": "TOON",
            "data": dashboard_toon,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"[Mission Control] Dashboard error: {e}")
        raise HTTPException(500, f"Failed to load dashboard: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE REGISTRY & API KEY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/services")
async def get_service_registry(admin=Depends(verify_admin)):
    """
    Get all available services in TOON format
    
    Returns:
    Service[15]{id, cat, provider, cost, status, tiers}:
      gpt-4o, llm, OpenAI, 0.005/1k, active, [sta|pro|ent]
      gpt-4o-mini, llm, OpenAI, 0.00015/1k, active, [free|sta|pro|ent]
      voxtral-tts, voice, Mistral, 0.002/min, no_keys, [pro|ent]
      ...
    """
    toon_service = get_toon_service()
    
    try:
        services_toon = await toon_service.get_service_registry_toon()
        
        return {
            "format": "TOON",
            "data": services_toon,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"[Mission Control] Services error: {e}")
        raise HTTPException(500, f"Failed to load services: {str(e)}")


@router.get("/api-keys")
async def get_api_keys(admin=Depends(verify_admin)):
    """
    Get all API keys in TOON format (encrypted keys not shown)
    
    Returns:
    APIKey[5]{service, preview, status, calls, spend, last_used}:
      gpt-4o, sk-proj-...ABC, active, 15000, 45.67, 2026-01-15T10:30
      voxtral-tts, sk-mist-...XYZ, active, 500, 12.34, 2026-01-14T15:20
      ...
    """
    toon_service = get_toon_service()
    
    try:
        keys_toon = await toon_service.get_api_keys_toon(admin)
        
        return {
            "format": "TOON",
            "data": keys_toon,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"[Mission Control] API keys error: {e}")
        raise HTTPException(500, f"Failed to load API keys: {str(e)}")


@router.post("/services/add-key")
async def add_api_key(request: AddAPIKeyRequest, admin=Depends(verify_admin)):
    """
    Add API key for a service
    This enables the service for all subscriptions that include it
    
    Request:
    {
      "service_id": "gpt-4o",
      "api_key": "sk-proj-...",
      "notes": "Production key - purchased 2026-01-15",
      "monthly_spend_limit": 1000.00
    }
    
    Response (TOON):
    APIKey[key_xxxxx]:
      service_id: gpt-4o
      preview: sk-proj-...ABC
      status: active
      added_at: 2026-01-15T10:30:00Z
    """
    if not _db:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Generate key ID
        key_id = f"key_{secrets.token_hex(12)}"
        
        # Encrypt API key
        encrypted_key = encrypt_api_key(request.api_key)
        
        # Create preview (first 8 + last 4 chars)
        preview = f"{request.api_key[:8]}...{request.api_key[-4:]}"
        
        # Store in database
        key_record = {
            "key_id": key_id,
            "service_id": request.service_id,
            "encrypted_key": encrypted_key,
            "key_preview": preview,
            "added_by": admin,  # Admin ID from header
            "added_at": datetime.now(timezone.utc),
            "status": "active",
            "total_calls": 0,
            "total_spend_usd": 0.0,
            "last_used": None,
            "monthly_spend_limit": request.monthly_spend_limit,
            "notes": request.notes
        }
        
        await _db.api_keys_registry.insert_one(key_record)
        
        # Update service status to 'active'
        await _db.service_registry.update_one(
            {"service_id": request.service_id},
            {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        
        logger.info(f"[Mission Control] Added API key for {request.service_id}")
        
        # Return TOON format
        response_toon = f"""APIKey[{key_id}]:
  service_id: {request.service_id}
  preview: {preview}
  status: active
  added_at: {key_record['added_at'].isoformat()}
  monthly_spend_limit: {request.monthly_spend_limit or 'unlimited'}"""
        
        return {
            "success": True,
            "format": "TOON",
            "data": response_toon,
            "key_id": key_id
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] Add API key error: {e}")
        raise HTTPException(500, f"Failed to add API key: {str(e)}")


@router.post("/services/remove-key")
async def remove_api_key(request: RemoveAPIKeyRequest, admin=Depends(verify_admin)):
    """
    Remove/revoke an API key
    
    Response:
    {
      "success": true,
      "message": "API key revoked for gpt-4o"
    }
    """
    if not _db:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Update key status to 'revoked'
        result = await _db.api_keys_registry.update_one(
            {"key_id": request.key_id, "service_id": request.service_id},
            {
                "$set": {
                    "status": "revoked",
                    "revoked_by": admin,
                    "revoked_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, "API key not found")
        
        # Check if service has other active keys
        active_keys = await _db.api_keys_registry.count_documents({
            "service_id": request.service_id,
            "status": "active"
        })
        
        # If no active keys, update service status
        if active_keys == 0:
            await _db.service_registry.update_one(
                {"service_id": request.service_id},
                {"$set": {"status": "no_keys"}}
            )
        
        logger.info(f"[Mission Control] Removed API key {request.key_id} for {request.service_id}")
        
        return {
            "success": True,
            "message": f"API key revoked for {request.service_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Mission Control] Remove API key error: {e}")
        raise HTTPException(500, f"Failed to remove API key: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTIONS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/subscriptions")
async def get_all_subscriptions(
    tier: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    admin=Depends(verify_admin)
):
    """
    Get all subscriptions in TOON format
    
    Query params:
    - tier: Filter by tier (free, starter, professional, enterprise)
    - status: Filter by status (active, cancelled, past_due)
    - limit: Max results (default 100)
    
    Returns:
    Subscription[150]{id, user, tier, status, amount, period_end, usage}:
      sub_001, user_abc, professional, active, 399, 2026-02-01, {tokens:15k/200k}
      sub_002, user_def, starter, active, 99, 2026-02-05, {tokens:8k/50k}
      ...
    """
    if not _db:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Build query
        query = {}
        if tier:
            query['tier'] = tier
        if status:
            query['status'] = status
        
        # Fetch subscriptions
        subs = await _db.subscriptions.find(
            query,
            {"_id": 0}
        ).limit(limit).to_list(limit)
        
        if not subs:
            return {
                "format": "TOON",
                "data": "Subscription[0]:",
                "count": 0
            }
        
        # Convert to TOON tabular format
        header = f"Subscription[{len(subs)}]{{id, user, tier, status, amount, period_end, usage}}"
        
        rows = []
        for sub in subs:
            sub_id = sub.get('id', sub.get('subscription_id', 'unknown'))[:12]
            user_id = sub.get('user_id', 'unknown')[:12]
            tier_val = sub.get('tier', 'free')
            status_val = sub.get('status', 'active')
            amount = sub.get('amount', 0)
            period_end = sub.get('current_period_end', 'N/A')
            if isinstance(period_end, datetime):
                period_end = period_end.strftime('%Y-%m-%d')
            
            # Compress usage
            usage = sub.get('usage', {})
            tokens_used = usage.get('ai_tokens_used', 0)
            tokens_limit = usage.get('ai_tokens_limit', 0)
            usage_str = f"{{tokens:{tokens_used}/{tokens_limit}}}"
            
            rows.append(f"{sub_id}, {user_id}, {tier_val}, {status_val}, {amount}, {period_end}, {usage_str}")
        
        toon_data = f"{header}:\n  " + "\n  ".join(rows)
        
        return {
            "format": "TOON",
            "data": toon_data,
            "count": len(subs)
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] Subscriptions error: {e}")
        raise HTTPException(500, f"Failed to load subscriptions: {str(e)}")


@router.get("/subscriptions/{user_id}")
async def get_user_subscription(user_id: str, admin=Depends(verify_admin)):
    """
    Get specific user's subscription in TOON format
    
    Returns:
    Subscription[sub_xxxxx]:
      user_id: user_12345
      tier: professional
      status: active
      amount: 399
      usage: {tokens:15k/200k, formulas:5/50}
      services: Service[3]{id, status, tokens}: gpt-4o, active, 15000; ...
    """
    toon_service = get_toon_service()
    
    try:
        sub_toon = await toon_service.get_user_subscription_toon(user_id)
        
        return {
            "format": "TOON",
            "data": sub_toon
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] User subscription error: {e}")
        raise HTTPException(500, f"Failed to load user subscription: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# USAGE ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/usage")
async def get_usage_analytics(
    user_id: Optional[str] = None,
    service_id: Optional[str] = None,
    limit: int = 100,
    admin=Depends(verify_admin)
):
    """
    Get usage logs in TOON format
    
    Query params:
    - user_id: Filter by user
    - service_id: Filter by service
    - limit: Max results
    
    Returns:
    UsageLog[150]{user, service, tokens, cost, endpoint, time}:
      user_123, gpt-4o, 1500, 0.0075, /api/aurem/chat, 2026-01-15T10:30
      user_123, voxtral-tts, 0, 0.0020, /api/voice/tts, 2026-01-15T10:31
      ...
    """
    toon_service = get_toon_service()
    
    try:
        usage_toon = await toon_service.get_usage_analytics_toon(user_id, service_id, limit)
        
        return {
            "format": "TOON",
            "data": usage_toon,
            "filters": {
                "user_id": user_id,
                "service_id": service_id,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] Usage analytics error: {e}")
        raise HTTPException(500, f"Failed to load usage analytics: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN/CREDIT RECHARGE
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/recharge")
async def recharge_service(request: RechargeRequest, admin=Depends(verify_admin)):
    """
    Recharge tokens/credits for a service
    
    Request:
    {
      "service_id": "openai-credits",
      "amount_usd": 100.00,
      "tokens_added": 20000000,
      "payment_method": "stripe",
      "notes": "Monthly recharge - Jan 2026"
    }
    
    Response (TOON):
    Recharge[rech_xxxxx]:
      service_id: openai-credits
      amount_usd: 100.00
      tokens_added: 20000000
      purchased_by: admin_123
      purchase_date: 2026-01-15T10:30:00Z
    """
    if not _db:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Generate recharge ID
        recharge_id = f"rech_{secrets.token_hex(12)}"
        
        # Store recharge record
        recharge_record = {
            "recharge_id": recharge_id,
            "service_id": request.service_id,
            "amount_usd": request.amount_usd,
            "tokens_added": request.tokens_added,
            "credits_added": request.credits_added,
            "purchased_by": admin,
            "purchase_date": datetime.now(timezone.utc),
            "payment_method": request.payment_method,
            "notes": request.notes
        }
        
        await _db.token_recharges.insert_one(recharge_record)
        
        logger.info(f"[Mission Control] Recharged {request.service_id}: ${request.amount_usd}")
        
        # Return TOON format
        response_toon = f"""Recharge[{recharge_id}]:
  service_id: {request.service_id}
  amount_usd: {request.amount_usd}
  tokens_added: {request.tokens_added or 'N/A'}
  credits_added: {request.credits_added or 'N/A'}
  purchased_by: {admin}
  purchase_date: {recharge_record['purchase_date'].isoformat()}"""
        
        return {
            "success": True,
            "format": "TOON",
            "data": response_toon,
            "recharge_id": recharge_id
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] Recharge error: {e}")
        raise HTTPException(500, f"Failed to process recharge: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE CONTROL (START/STOP)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/service/toggle")
async def toggle_service(request: ToggleServiceRequest, admin=Depends(verify_admin)):
    """
    Start, stop, or pause a service
    
    Request:
    {
      "service_id": "gpt-4o",
      "action": "pause"  # start, stop, pause
    }
    
    Response:
    {
      "success": true,
      "service_id": "gpt-4o",
      "new_status": "paused",
      "message": "Service gpt-4o paused"
    }
    """
    if not _db:
        raise HTTPException(500, "Database not initialized")
    
    if request.action not in ["start", "stop", "pause"]:
        raise HTTPException(400, "Invalid action. Must be: start, stop, or pause")
    
    try:
        # Map action to status
        status_map = {
            "start": "active",
            "stop": "suspended",
            "pause": "paused"
        }
        new_status = status_map[request.action]
        
        # Update service status
        result = await _db.service_registry.update_one(
            {"service_id": request.service_id},
            {
                "$set": {
                    "status": new_status,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": admin
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, f"Service {request.service_id} not found")
        
        logger.info(f"[Mission Control] Service {request.service_id} {request.action}ed by {admin}")
        
        return {
            "success": True,
            "service_id": request.service_id,
            "new_status": new_status,
            "message": f"Service {request.service_id} {request.action}ed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Mission Control] Toggle service error: {e}")
        raise HTTPException(500, f"Failed to toggle service: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "admin-mission-control",
        "format": "TOON",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
