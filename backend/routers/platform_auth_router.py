"""
AUREM Platform Authentication Router
Admin-only JWT authentication for AUREM platform
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import jwt
import hashlib
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/platform/auth", tags=["Platform Auth"])

# JWT Secret - in production, use environment variable
JWT_SECRET = os.environ.get("JWT_SECRET", "aurem-platform-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7  # 1 week

# In-memory admin store (for simplicity - use MongoDB in production)
# Default admin credentials
ADMIN_USERS = {
    "admin@aurem.live": {
        "password_hash": hashlib.sha256("AuremAdmin2024!".encode()).hexdigest(),
        "full_name": "AUREM Admin",
        "company_name": "AUREM Platform",
        "role": "admin",
        "created_at": datetime.utcnow().isoformat()
    }
}

# MongoDB connection (will be set by server.py)
db = None

def set_db(database):
    global db
    db = database

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: str

class TokenResponse(BaseModel):
    token: str
    email: str
    full_name: str
    company_name: str
    role: str

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(email: str, role: str = "user") -> str:
    payload = {
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Login to AUREM Platform
    Default admin: admin@aurem.live / AuremAdmin2024!
    """
    email = request.email.lower()
    password_hash = hash_password(request.password)
    
    logger.info(f"[PLATFORM AUTH] Login attempt for: {email}")
    logger.info(f"[PLATFORM AUTH] Password hash: {password_hash}")
    logger.info(f"[PLATFORM AUTH] Admin users: {list(ADMIN_USERS.keys())}")
    
    # Check in-memory admin users first
    if email in ADMIN_USERS:
        user = ADMIN_USERS[email]
        logger.info(f"[PLATFORM AUTH] Found user, stored hash: {user['password_hash']}")
        logger.info(f"[PLATFORM AUTH] Hash match: {user['password_hash'] == password_hash}")
        if user["password_hash"] == password_hash:
            token = create_token(email, user.get("role", "admin"))
            return TokenResponse(
                token=token,
                email=email,
                full_name=user["full_name"],
                company_name=user["company_name"],
                role=user.get("role", "admin")
            )
    
    # Check MongoDB if available
    if db is not None:
        try:
            user = await db.platform_users.find_one({"email": email})
            if user and user.get("password_hash") == password_hash:
                token = create_token(email, user.get("role", "user"))
                return TokenResponse(
                    token=token,
                    email=email,
                    full_name=user.get("full_name", ""),
                    company_name=user.get("company_name", ""),
                    role=user.get("role", "user")
                )
        except Exception as e:
            print(f"[AUTH] DB error: {e}")
    
    raise HTTPException(status_code=401, detail="Invalid email or password")

@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """
    Register new AUREM Platform user
    Note: Registration is disabled for admin-only access
    """
    # For admin-only access, disable public registration
    raise HTTPException(
        status_code=403, 
        detail="Registration is currently disabled. Contact admin@aurem.live for access."
    )
    
    # Uncomment below to enable registration:
    """
    email = request.email.lower()
    
    # Check if user exists
    if email in ADMIN_USERS:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if db is not None:
        existing = await db.platform_users.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user
        user_data = {
            "email": email,
            "password_hash": hash_password(request.password),
            "full_name": request.full_name,
            "company_name": request.company_name,
            "role": "user",
            "created_at": datetime.utcnow()
        }
        await db.platform_users.insert_one(user_data)
        
        token = create_token(email, "user")
        return TokenResponse(
            token=token,
            email=email,
            full_name=request.full_name,
            company_name=request.company_name,
            role="user"
        )
    
    raise HTTPException(status_code=500, detail="Database not available")
    """

@router.get("/verify")
async def verify_auth(token: str):
    """Verify JWT token is valid"""
    payload = verify_token(token)
    return {"valid": True, "email": payload.get("email"), "role": payload.get("role")}

@router.post("/add-admin")
async def add_admin(email: str, password: str, full_name: str, master_key: str):
    """
    Add a new admin user (requires master key)
    Master key should be set as AUREM_MASTER_KEY environment variable
    """
    expected_key = os.environ.get("AUREM_MASTER_KEY", "aurem-master-2024")
    if master_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid master key")
    
    email = email.lower()
    if email in ADMIN_USERS:
        raise HTTPException(status_code=400, detail="Admin already exists")
    
    ADMIN_USERS[email] = {
        "password_hash": hash_password(password),
        "full_name": full_name,
        "company_name": "AUREM Platform",
        "role": "admin",
        "created_at": datetime.utcnow().isoformat()
    }
    
    return {"message": f"Admin {email} added successfully"}

@router.get("/health")
async def health():
    return {"status": "ok", "service": "platform-auth"}
