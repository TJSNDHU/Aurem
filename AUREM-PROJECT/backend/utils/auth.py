"""
Authentication utilities: JWT, password hashing, token management.
"""
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import Request, HTTPException

from config import JWT_SECRET, JWT_ALGORITHM, get_database

# Super admin permissions (full access)
SUPER_ADMIN_PERMISSIONS = {
    "overview": {"view": True, "create": True, "edit": True, "delete": True},
    "products": {"view": True, "create": True, "edit": True, "delete": True},
    "categories": {"view": True, "create": True, "edit": True, "delete": True},
    "orders": {"view": True, "create": True, "edit": True, "delete": True},
    "financials": {"view": True, "create": True, "edit": True, "delete": True},
    "payroll": {"view": True, "create": True, "edit": True, "delete": True},
    "customers": {"view": True, "create": True, "edit": True, "delete": True},
    "offers": {"view": True, "create": True, "edit": True, "delete": True},
    "reviews": {"view": True, "create": True, "edit": True, "delete": True},
    "sections": {"view": True, "create": True, "edit": True, "delete": True},
    "website": {"view": True, "create": True, "edit": True, "delete": True},
    "ads": {"view": True, "create": True, "edit": True, "delete": True},
    "typography": {"view": True, "create": True, "edit": True, "delete": True},
    "subscriptions": {"view": True, "create": True, "edit": True, "delete": True},
    "settings": {"view": True, "create": True, "edit": True, "delete": True},
    "ai_chat": {"view": True, "create": True, "edit": True, "delete": True},
    "team": {"view": True, "create": True, "edit": True, "delete": True},
}


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, is_admin: bool = False) -> str:
    """Create a JWT token for a user"""
    payload = {
        "user_id": user_id,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> Optional[dict]:
    """Get current user from JWT token in Authorization header or cookie"""
    db = get_database()
    
    # Try Authorization header first
    auth_header = request.headers.get("Authorization", "")
    token = None
    
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        # Try cookie
        token = request.cookies.get("session_token")
    
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        is_team_member = payload.get("is_team_member", False)
        
        if is_team_member:
            # Get team member
            team_member = await db.team_members.find_one(
                {"id": user_id}, {"_id": 0, "password_hash": 0}
            )
            if team_member and team_member.get("status") == "active":
                role = await db.roles.find_one(
                    {"id": team_member.get("role_id")}, {"_id": 0}
                )
                team_member["permissions"] = (
                    role.get("permissions", {}) if role else {}
                )
                team_member["role_name"] = (
                    role.get("name", "Team Member") if role else "Team Member"
                )
                team_member["is_team_member"] = True
                team_member["is_admin"] = True
                return team_member
            return None
        else:
            # Regular user or super admin
            user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
            if user and user.get("is_admin"):
                user["is_super_admin"] = True
                user["permissions"] = SUPER_ADMIN_PERMISSIONS
            return user
    except Exception:
        return None


async def require_auth(request: Request) -> dict:
    """Require authentication - raises 401 if not authenticated"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin(request: Request) -> dict:
    """Require admin privileges - raises 403 if not admin"""
    user = await require_auth(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(request: Request) -> dict:
    """Require super admin privileges"""
    user = await require_admin(request)
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


async def require_permission(request: Request, feature: str, action: str) -> dict:
    """Require specific permission for a feature"""
    user = await require_admin(request)
    permissions = user.get("permissions", {})
    feature_perms = permissions.get(feature, {})
    
    if not feature_perms.get(action, False):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {feature}.{action}"
        )
    return user
