"""
Authentication utilities: JWT, password hashing, token management.
"""
import asyncio
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
    """Hash a plaintext password using bcrypt with a work factor of 10 rounds.

    Uses bcrypt's adaptive hash with ``rounds=10`` (down from the default
    12). Per OWASP 2024 guidance, 10 rounds is the minimum recommended
    for web logins and takes ~50-100ms, while 12 rounds is overkill at
    ~200-400ms per call. Existing passwords hashed at 12 rounds still
    verify correctly because bcrypt stores the rounds value in the hash
    string itself.

    Args:
        password: The plaintext password to hash.

    Returns:
        A bcrypt hash string suitable for persistent storage.

    Raises:
        TypeError: If ``password`` is not a string.
        ValueError: If ``password`` cannot be encoded as UTF-8 or
            exceeds bcrypt's 72-byte input limit.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


async def averify_password(password: str, hashed: str) -> bool:
    """Async wrapper around verify_password. iter 325e — fixes the
    "first login click is slow" bug. bcrypt.checkpw runs in a thread so
    the event loop can keep responding to other inbound requests while
    we burn ~50–100ms on the rounds=10 hash comparison."""
    if not hashed:
        return False
    return await asyncio.to_thread(verify_password, password, hashed)


async def ahash_password(password: str) -> str:
    """Async wrapper around hash_password. Same reason as averify_password
    — keeps the event loop responsive during signup / migration."""
    return await asyncio.to_thread(hash_password, password)


def create_token(user_id: str, is_admin: bool = False, email: str = None) -> str:
    """Create a JWT token for a user"""
    payload = {
        "user_id": user_id,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    if email:
        payload["email"] = email
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> Optional[dict]:
    """Resolve and return the currently authenticated user from the request.

    The caller's identity is established from a JWT, which may be supplied
    either as a ``Bearer`` token in the ``Authorization`` header or as the
    ``session_token`` cookie. The token is decoded and validated using the
    application's configured JWT secret and algorithm.

    Args:
        request: The incoming FastAPI ``Request`` containing the headers
            and cookies used to locate the authentication token.

    Returns:
        A dictionary describing the authenticated user when a valid token
        is present. For team members this includes their role name and
        permissions; for super admins it includes the full
        ``SUPER_ADMIN_PERMISSIONS`` mapping. Returns ``None`` when no
        token is supplied, the token is invalid/expired, or the referenced
        user or active team member cannot be found.

    Raises:
        This function does not raise exceptions on authentication failure;
        invalid or expired tokens result in a return value of ``None``.
        Any unexpected errors during token decoding or database lookup are
        caught and also result in ``None``.
    """
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