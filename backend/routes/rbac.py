# ============================================================
# REROOTS — ROLE-BASED ACCESS CONTROL (RBAC)
# Supports: Email/Password + Google Sign-In
# Roles: owner, manager, staff, wholesale
# ============================================================

import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from bson import ObjectId

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

JWT_SECRET = os.environ.get("JWT_SECRET", "reroots-secret-change-in-production")
JWT_EXPIRY_HOURS = 24
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "admin@reroots.ca")
SETUP_KEY = os.environ.get("SETUP_KEY", "reroots-setup-2026")

security = HTTPBearer(auto_error=False)

# ─── ROLE DEFINITIONS ────────────────────────────────────────

ROLE_PERMISSIONS = {
    "owner": {
        "label": "Owner",
        "sections": [
            "executive-intel", "inventory-batch", "crm-repurchase", "orders-fulfillment",
            "accounting-gst", "online-store", "products", "customers", "ai-intelligence",
            "settings", "marketing-lab", "reviews", "partners", "waitlist", "founders"
        ],
        "readOnly": [],
        "canManageUsers": True,
        "canViewAccounting": True,
        "canRefund": True,
        "canExport": True,
    },
    "manager": {
        "label": "Store Manager",
        "sections": [
            "inventory-batch", "crm-repurchase", "orders-fulfillment", "products",
            "customers", "online-store", "reviews"
        ],
        "readOnly": ["inventory-batch"],
        "canManageUsers": False,
        "canViewAccounting": False,
        "canRefund": True,
        "canExport": True,
    },
    "staff": {
        "label": "Staff / Fulfillment",
        "sections": ["orders-fulfillment", "inventory-batch"],
        "readOnly": ["inventory-batch"],
        "canManageUsers": False,
        "canViewAccounting": False,
        "canRefund": False,
        "canExport": False,
    },
    "wholesale": {
        "label": "Wholesale Partner",
        "sections": ["products", "orders-fulfillment"],
        "readOnly": ["products"],
        "canManageUsers": False,
        "canViewAccounting": False,
        "canRefund": False,
        "canExport": False,
    }
}


# ─── JWT HELPERS ─────────────────────────────────────────────

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


async def get_current_user_rbac(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """FastAPI dependency — use on any protected route"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return verify_token(credentials.credentials)


def require_role(*allowed_roles: str):
    """FastAPI dependency factory — restrict route to specific roles."""
    async def checker(user: dict = Depends(get_current_user_rbac)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
            )
        return user
    return checker


def require_owner():
    return require_role("owner")


# ─── AUTH ENDPOINTS ───────────────────────────────────────────

@router.post("/rbac/login")
async def rbac_login(data: dict = Body(...)):
    """Email + Password login with role-based permissions."""
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required.")
    
    user = await db["admin_users"].find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    if not user.get("passwordHash"):
        raise HTTPException(status_code=401, detail="Password not set. Use Google login or contact owner.")
    
    if not bcrypt.checkpw(password.encode(), user["passwordHash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    if not user.get("isActive", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact the owner.")
    
    await db["admin_users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"lastLogin": datetime.utcnow().isoformat()}}
    )
    
    role = user.get("role", "staff")
    token = create_token(str(user["_id"]), email, role)
    
    return {
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "email": email,
            "name": user.get("name", ""),
            "role": role,
            "permissions": ROLE_PERMISSIONS.get(role, {}),
            "avatar": user.get("avatar", email[0].upper())
        }
    }


@router.post("/rbac/google")
async def google_rbac_login(data: dict = Body(...)):
    """Google Sign-In with role-based permissions."""
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        
        GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
        google_token = data.get("googleToken")
        
        if not google_token:
            raise HTTPException(status_code=400, detail="Google token required.")
        
        id_info = id_token.verify_oauth2_token(
            google_token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        
        google_email = id_info.get("email", "").lower()
        google_name = id_info.get("name", "")
        google_pic = id_info.get("picture", "")
        
        user = await db["admin_users"].find_one({"email": google_email})
        
        if not user:
            if google_email == OWNER_EMAIL.lower():
                new_user = {
                    "email": google_email,
                    "name": google_name,
                    "role": "owner",
                    "authMethod": "google",
                    "avatar": google_pic,
                    "isActive": True,
                    "createdAt": datetime.utcnow().isoformat(),
                    "lastLogin": datetime.utcnow().isoformat()
                }
                result = await db["admin_users"].insert_one(new_user)
                new_user["_id"] = result.inserted_id
                user = new_user
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. Your Google account is not authorized."
                )
        
        if not user.get("isActive", True):
            raise HTTPException(status_code=403, detail="Account is inactive.")
        
        await db["admin_users"].update_one(
            {"email": google_email},
            {"$set": {"lastLogin": datetime.utcnow().isoformat(), "avatar": google_pic}}
        )
        
        role = user.get("role", "staff")
        token = create_token(str(user["_id"]), google_email, role)
        
        return {
            "token": token,
            "user": {
                "id": str(user["_id"]),
                "email": google_email,
                "name": google_name,
                "role": role,
                "permissions": ROLE_PERMISSIONS.get(role, {}),
                "avatar": google_pic or google_email[0].upper()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Google authentication failed: {str(e)}")


@router.get("/rbac/me")
async def get_rbac_me(user: dict = Depends(get_current_user_rbac)):
    """Get current user profile + permissions"""
    try:
        db_user = await db["admin_users"].find_one({"email": user["email"]})
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found.")
        
        role = db_user.get("role", "staff")
        return {
            "id": str(db_user["_id"]),
            "email": db_user["email"],
            "name": db_user.get("name", ""),
            "role": role,
            "permissions": ROLE_PERMISSIONS.get(role, {}),
            "avatar": db_user.get("avatar", ""),
            "lastLogin": db_user.get("lastLogin", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rbac/logout")
async def rbac_logout(user: dict = Depends(get_current_user_rbac)):
    """Logout — client should delete token."""
    await db["admin_users"].update_one(
        {"email": user["email"]},
        {"$set": {"lastLogout": datetime.utcnow().isoformat()}}
    )
    return {"success": True}


# ─── USER MANAGEMENT (Owner only) ────────────────────────────

@router.get("/users")
async def get_admin_users(user: dict = Depends(require_owner())):
    """Get all admin users"""
    try:
        users = await db["admin_users"].find().sort("name", 1).to_list(100)
        return [{
            "id": str(u["_id"]),
            "email": u["email"],
            "name": u.get("name", ""),
            "role": u.get("role", "staff"),
            "isActive": u.get("isActive", True),
            "lastLogin": u.get("lastLogin", ""),
            "authMethod": u.get("authMethod", "email"),
            "permissions": ROLE_PERMISSIONS.get(u.get("role", "staff"), {})
        } for u in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users")
async def create_admin_user(data: dict = Body(...), user: dict = Depends(require_owner())):
    """Create a new admin user. Body: { name, email, role, password }"""
    try:
        email = data.get("email", "").lower().strip()
        if not email:
            raise HTTPException(status_code=400, detail="Email required.")
        
        existing = await db["admin_users"].find_one({"email": email})
        if existing:
            raise HTTPException(status_code=409, detail="User with this email already exists.")
        
        new_user = {
            "email": email,
            "name": data.get("name", ""),
            "role": data.get("role", "staff"),
            "isActive": True,
            "authMethod": "email",
            "createdAt": datetime.utcnow().isoformat(),
            "createdBy": user["email"]
        }
        
        if data.get("password"):
            hashed = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt())
            new_user["passwordHash"] = hashed.decode()
        
        result = await db["admin_users"].insert_one(new_user)
        new_user["id"] = str(result.inserted_id)
        new_user.pop("passwordHash", None)
        new_user.pop("_id", None)
        return new_user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/role")
async def update_user_role(user_id: str, data: dict = Body(...), current_user: dict = Depends(require_owner())):
    """Change a user's role. Body: { role }"""
    try:
        new_role = data.get("role")
        if new_role not in ROLE_PERMISSIONS:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be: {list(ROLE_PERMISSIONS.keys())}")
        
        await db["admin_users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"role": new_role, "updatedAt": datetime.utcnow().isoformat()}}
        )
        return {"success": True, "userId": user_id, "newRole": new_role}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/deactivate")
async def deactivate_admin_user(user_id: str, current_user: dict = Depends(require_owner())):
    """Deactivate a user account"""
    try:
        await db["admin_users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"isActive": False, "deactivatedAt": datetime.utcnow().isoformat()}}
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/change-password")
async def change_user_password(data: dict = Body(...), current_user: dict = Depends(get_current_user_rbac)):
    """Change own password. Body: { currentPassword, newPassword }"""
    try:
        user = await db["admin_users"].find_one({"email": current_user["email"]})
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        
        if user.get("passwordHash"):
            if not bcrypt.checkpw(data["currentPassword"].encode(), user["passwordHash"].encode()):
                raise HTTPException(status_code=401, detail="Current password incorrect.")
        
        new_hash = bcrypt.hashpw(data["newPassword"].encode(), bcrypt.gensalt())
        await db["admin_users"].update_one(
            {"email": current_user["email"]},
            {"$set": {"passwordHash": new_hash.decode(), "passwordUpdatedAt": datetime.utcnow().isoformat()}}
        )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── OWNER SETUP (ONE-TIME) ──────────────────────────────────

@router.post("/setup-owner")
async def setup_owner_account(data: dict = Body(...)):
    """ONE-TIME SETUP: Create the owner account. DELETE after use."""
    if data.get("setupKey") != SETUP_KEY:
        raise HTTPException(status_code=403, detail="Invalid setup key.")
    
    existing = await db["admin_users"].find_one({"role": "owner"})
    if existing:
        raise HTTPException(status_code=409, detail="Owner account already exists.")
    
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")
    name = data.get("name", "Owner")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required.")
    
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    owner = {
        "email": email,
        "name": name,
        "role": "owner",
        "passwordHash": hashed.decode(),
        "isActive": True,
        "authMethod": "email",
        "createdAt": datetime.utcnow().isoformat()
    }
    result = await db["admin_users"].insert_one(owner)
    return {
        "success": True,
        "message": f"Owner account created for {email}.",
        "id": str(result.inserted_id)
    }


@router.get("/roles")
async def get_available_roles():
    """Get all available roles and their permissions"""
    return ROLE_PERMISSIONS
