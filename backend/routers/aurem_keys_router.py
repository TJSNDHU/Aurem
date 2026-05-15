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


# Bug-fix #94 — list/revoke/usage previously had ZERO auth. An attacker
# who knew any business_id (visible in many API responses) could revoke
# all API keys for that business, breaking every integration. Now all
# three endpoints require JWT + business_id ownership (admins exempted).
def _verify_business_caller(authorization: str, business_id: str) -> dict:
    import os, jwt as _jwt
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(503, "Auth not configured")
    try:
        payload = _jwt.decode(authorization.split(" ", 1)[1], secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    is_admin = bool(
        payload.get("is_admin") or payload.get("is_super_admin")
        or payload.get("role") in ("admin", "super_admin")
    )
    if not is_admin:
        from utils.admin_guard import is_admin_email
        if is_admin_email(payload.get("email")):
            is_admin = True
    if is_admin:
        return payload
    caller_biz = payload.get("business_id") or payload.get("tenant_id") or payload.get("sub")
    if not caller_biz or caller_biz != business_id:
        raise HTTPException(403, "business_id does not belong to caller")
    return payload


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
async def create_api_key(
    request: CreateKeyRequest,
    admin_key: str = Header(None, alias="X-Admin-Key"),
    authorization: str = Header(None),
):
    """
    Create a new AUREM API key.

    Returns the full API key ONLY ONCE - store it securely!

    Auth: either
      - X-Admin-Key header matching AUREM_ADMIN_KEY env, OR
      - Bearer JWT with role in {admin, super_admin}, OR
      - Bearer JWT from a platform user whose business_id matches the
        `business_id` in the request (owner self-service).
    """
    import os

    _admin_env = os.environ.get("AUREM_ADMIN_KEY", "").strip()
    is_admin_key_valid = bool(_admin_env) and admin_key == _admin_env
    is_privileged = False
    caller_business_id = None

    if not is_admin_key_valid:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Authentication required to create API keys")
        try:
            from routers.platform_auth_router import verify_token
            payload = verify_token(authorization.split(" ", 1)[1])
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(401, "Invalid token")

        role = payload.get("role", "")
        caller_business_id = payload.get("business_id")
        is_privileged = role in ("admin", "super_admin")

        if not is_privileged:
            # Owner self-service: the caller can only mint keys for their OWN business_id.
            if not caller_business_id or caller_business_id != request.business_id:
                raise HTTPException(
                    403,
                    "You can only create keys for your own business_id.",
                )

    from services.aurem_commercial.key_service import get_aurem_key_service

    key_service = get_aurem_key_service(get_db())

    result = await key_service.create_key(
        business_id=request.business_id,
        name=request.name,
        is_test=request.is_test,
        rate_limit=request.rate_limit_daily,
        scope_bundle=request.scope_bundle,
        custom_scopes=request.custom_scopes,
    )

    # Audit trail — every key mint writes a record the founder can review.
    try:
        db = get_db()
        await db.api_key_audit.insert_one({
            "business_id": request.business_id,
            "name": request.name,
            "scope_bundle": request.scope_bundle,
            "via": "admin_key" if is_admin_key_valid else ("privileged_jwt" if is_privileged else "owner_jwt"),
            "caller_business_id": caller_business_id,
            "is_test": request.is_test,
            "key_id": (result or {}).get("key_id"),
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        })
    except Exception as _e:
        logger.warning(f"[aurem-keys] audit write failed: {_e}")

    return result


@router.get("/list/{business_id}")
async def list_api_keys(business_id: str, authorization: str = Header(None)):
    """List all API keys for a business (without revealing full keys)"""
    _verify_business_caller(authorization, business_id)
    from services.aurem_commercial.key_service import get_aurem_key_service
    
    key_service = get_aurem_key_service(get_db())
    keys = await key_service.list_keys(business_id)
    
    return {"keys": keys, "count": len(keys)}


@router.post("/revoke")
async def revoke_api_key(request: RevokeKeyRequest, authorization: str = Header(None)):
    """Revoke an API key"""
    _verify_business_caller(authorization, request.business_id)
    from services.aurem_commercial.key_service import get_aurem_key_service
    
    key_service = get_aurem_key_service(get_db())
    success = await key_service.revoke_key(request.key_id, request.business_id)
    
    if not success:
        raise HTTPException(404, "Key not found or already revoked")
    
    return {"success": True, "message": "API key revoked"}


@router.get("/usage/{business_id}")
async def get_usage_stats(business_id: str, billing_period: Optional[str] = None, authorization: str = Header(None)):
    """Get usage statistics for billing"""
    _verify_business_caller(authorization, business_id)
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
