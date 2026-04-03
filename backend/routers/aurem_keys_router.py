"""
AUREM API Key Management Router
Endpoints for creating, listing, and managing sk_aurem_ API keys

Endpoints:
- POST /api/aurem-keys/create - Create new API key
- GET /api/aurem-keys/list/{business_id} - List keys for business
- POST /api/aurem-keys/revoke - Revoke an API key
- GET /api/aurem-keys/usage/{business_id} - Get usage stats
- POST /api/aurem-keys/validate - Validate an API key
"""

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional, List
import logging

router = APIRouter(prefix="/api/aurem-keys", tags=["AUREM API Keys"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


class CreateKeyRequest(BaseModel):
    business_id: str
    name: str = "Default API Key"
    is_test: bool = False
    rate_limit_daily: int = 1000
    scope_bundle: str = "standard"  # read_only, standard, full_access, admin
    custom_scopes: Optional[List[str]] = None  # Override bundle with specific scopes


class RevokeKeyRequest(BaseModel):
    key_id: str
    business_id: str


class ValidateKeyRequest(BaseModel):
    api_key: str


@router.post("/create")
async def create_api_key(request: CreateKeyRequest, admin_key: str = Header(None, alias="X-Admin-Key")):
    """
    Create a new AUREM API key.
    
    Returns the full API key ONLY ONCE - store it securely!
    """
    # In production, verify admin authorization
    # For now, we'll allow creation with any request
    
    from services.aurem_commercial.key_service import get_aurem_key_service
    
    key_service = get_aurem_key_service(get_db())
    
    result = await key_service.create_key(
        business_id=request.business_id,
        name=request.name,
        is_test=request.is_test,
        rate_limit=request.rate_limit_daily,
        scope_bundle=request.scope_bundle,
        custom_scopes=request.custom_scopes
    )
    
    return result


@router.get("/list/{business_id}")
async def list_api_keys(business_id: str):
    """List all API keys for a business (without revealing full keys)"""
    from services.aurem_commercial.key_service import get_aurem_key_service
    
    key_service = get_aurem_key_service(get_db())
    keys = await key_service.list_keys(business_id)
    
    return {"keys": keys, "count": len(keys)}


@router.post("/revoke")
async def revoke_api_key(request: RevokeKeyRequest):
    """Revoke an API key"""
    from services.aurem_commercial.key_service import get_aurem_key_service
    
    key_service = get_aurem_key_service(get_db())
    success = await key_service.revoke_key(request.key_id, request.business_id)
    
    if not success:
        raise HTTPException(404, "Key not found or already revoked")
    
    return {"success": True, "message": "API key revoked"}


@router.get("/usage/{business_id}")
async def get_usage_stats(business_id: str, billing_period: Optional[str] = None):
    """Get usage statistics for billing"""
    from services.aurem_commercial.key_service import get_aurem_key_service
    
    key_service = get_aurem_key_service(get_db())
    stats = await key_service.get_usage_stats(business_id, billing_period)
    
    return stats


@router.post("/validate")
async def validate_api_key(request: ValidateKeyRequest):
    """
    Validate an API key.
    
    Returns key info if valid (without sensitive data).
    """
    from services.aurem_commercial.key_service import get_aurem_key_service
    
    key_service = get_aurem_key_service(get_db())
    key_info = await key_service.validate_key(request.api_key)
    
    if not key_info:
        raise HTTPException(401, "Invalid or expired API key")
    
    return {
        "valid": True,
        "key_id": key_info["key_id"],
        "business_id": key_info["business_id"],
        "name": key_info["name"],
        "is_test": key_info["is_test"],
        "usage_today": key_info["usage_today"],
        "rate_limit_daily": key_info["rate_limit_daily"]
    }


@router.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "service": "aurem-api-keys"}


@router.get("/scope-bundles")
async def get_scope_bundles():
    """Get available scope bundles and their permissions"""
    from services.aurem_commercial.key_service import SCOPE_BUNDLES, KeyScope
    
    return {
        "bundles": {
            name: {
                "scopes": scopes,
                "description": {
                    "read_only": "Read-only access to AI chat features",
                    "standard": "Standard access including chat and email actions",
                    "full_access": "Full access to all action capabilities",
                    "admin": "Full access plus key and billing management"
                }.get(name, "Custom scope bundle")
            }
            for name, scopes in SCOPE_BUNDLES.items()
        },
        "all_scopes": [s.value for s in KeyScope]
    }
