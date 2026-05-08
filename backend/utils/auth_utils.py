"""
Auth Utilities Module
═══════════════════════════════════════════════════════════════════
Shared authentication and authorization utilities used across routes.
Extracted from server.py for better modularity.
═══════════════════════════════════════════════════════════════════
"""

from fastapi import HTTPException, Request
from typing import Optional
import jwt
import logging

# Module-level references - initialized by init_auth_utils()
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"
_default_permissions = None
_super_admin_permissions = None

logger = logging.getLogger(__name__)


def init_auth_utils(db, jwt_secret: str, jwt_algorithm: str = "HS256", 
                    default_permissions: dict = None, super_admin_permissions: dict = None):
    """Initialize auth utilities with shared dependencies."""
    global _db, _jwt_secret, _jwt_algorithm, _default_permissions, _super_admin_permissions
    _db = db
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm
    _default_permissions = default_permissions or {}
    _super_admin_permissions = super_admin_permissions or {}
    logger.info("✓ Auth utilities initialized")


async def get_current_user(request: Request) -> Optional[dict]:
    """
    Get the current authenticated user from the request.
    Returns None if not authenticated or token is invalid.
    """
    if _db is None or _jwt_secret is None:
        logger.warning("Auth utilities not initialized")
        return None
        
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        user_id = payload.get("user_id")
        is_team_member = payload.get("is_team_member", False)

        if is_team_member:
            # Fetch team member
            team_member = await _db.team_members.find_one(
                {"id": user_id}, {"_id": 0, "password_hash": 0}
            )
            if team_member and team_member.get("status") == "active":
                # Get role permissions
                role = await _db.roles.find_one(
                    {"id": team_member.get("role_id")}, {"_id": 0}
                )
                team_member["permissions"] = (
                    role.get("permissions", _default_permissions)
                    if role
                    else _default_permissions
                )
                team_member["role_name"] = (
                    role.get("name", "Unknown") if role else "Unknown"
                )
                team_member["is_team_member"] = True
                team_member["is_admin"] = True  # Grant admin panel access
                return team_member
            return None
        else:
            # Regular user or super admin
            user = await _db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
            if user and user.get("is_admin"):
                user["is_super_admin"] = True
                user["permissions"] = _super_admin_permissions
            return user
    except Exception:
        return None


async def require_auth(request: Request) -> dict:
    """Require any authenticated user."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin(request: Request) -> dict:
    """Require admin access."""
    user = await get_current_user(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(request: Request) -> dict:
    """Require super admin (main account) access."""
    user = await get_current_user(request)
    if not user or not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


def check_permission(user: dict, feature: str, action: str) -> bool:
    """Check if user has permission for a specific action on a feature."""
    if user.get("is_super_admin"):
        return True
    permissions = user.get("permissions", {})
    feature_perms = permissions.get(feature, {})
    return feature_perms.get(action, False)


async def require_permission(request: Request, feature: str, action: str) -> dict:
    """Require specific permission for an action."""
    user = await require_admin(request)
    if not check_permission(user, feature, action):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {action} access required for {feature}",
        )
    return user
