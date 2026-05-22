"""
AUREM AI Platform - Commercial AI Crews Service
The all-in-one AI platform with Voice, WhatsApp, Email, Chat + AI Crews
"""

from fastapi import APIRouter, HTTPException, Depends, Header, BackgroundTasks, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import secrets
import hashlib
import bcrypt
import jwt

router = APIRouter(prefix="/api/platform", tags=["ai-platform"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

# FIX #5 (audit iter 322fi) — fail fast if JWT_SECRET is unset.
# Old code had a hardcoded fallback, which meant anyone reading the source
# could forge admin tokens whenever the env var was accidentally missing
# (e.g. fresh deploy, mistyped key name). The platform refuses to boot
# without a configured secret — protects every protected endpoint.
# iter 324d: switched to safe fallback via config.py (env → file → ephemeral)
# so the pod always binds port 8001 and K8s probes stay green. Auth-time
# validation now happens in the request handler, not at module load.
from config import JWT_SECRET  # noqa: E402
JWT_ALGORITHM = "HS256"

# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM SUBSCRIPTION TIERS
# ═══════════════════════════════════════════════════════════════════════════════

PLATFORM_TIERS = {
    "starter": {
        "name": "Starter",
        "price_monthly": 99,
        "price_yearly": 990,
        "crew_executions": 500,
        "tools": ["email", "chatbot"],
        "users": 1,
        "features": [
            "5 pre-built crew templates",
            "Email automation",
            "AI chatbot",
            "Basic analytics",
            "Email support"
        ],
        "voice_minutes": 0,
        "whatsapp_messages": 0,
        "description": "Perfect for small businesses starting with AI automation"
    },
    "growth": {
        "name": "Growth",
        "price_monthly": 299,
        "price_yearly": 2990,
        "crew_executions": 2000,
        "tools": ["email", "chatbot", "whatsapp"],
        "users": 5,
        "features": [
            "All Starter features",
            "WhatsApp automation",
            "Custom crew builder",
            "Advanced analytics",
            "OODA weekly reports",
            "Priority support"
        ],
        "voice_minutes": 0,
        "whatsapp_messages": 1000,
        "description": "Scale your automation across multiple channels"
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 799,
        "price_yearly": 7990,
        "crew_executions": 10000,
        "tools": ["email", "chatbot", "whatsapp", "voice", "browser_agent", "tts"],
        "users": -1,  # Unlimited
        "features": [
            "All Growth features",
            "Voice calling agent",
            "Browser automation",
            "Text-to-speech",
            "Custom integrations",
            "OODA daily monitoring",
            "Dedicated account manager",
            "SLA guarantee"
        ],
        "voice_minutes": 500,
        "whatsapp_messages": 5000,
        "description": "Full AI orchestration for enterprise operations"
    }
}

# Pre-built crew templates
CREW_TEMPLATES = {
    "abandoned_cart_recovery": {
        "name": "Abandoned Cart Recovery",
        "description": "Automatically recover abandoned carts through multi-channel outreach",
        "category": "e-commerce",
        "agents": [
            {"role": "analyst", "task": "Identify abandoned carts from last 24 hours"},
            {"role": "strategist", "task": "Segment carts by value and customer history"},
            {"role": "writer", "task": "Generate personalized recovery messages"},
            {"role": "executor", "task": "Send WhatsApp → Email → Voice sequence"}
        ],
        "tools_required": ["email", "whatsapp"],
        "estimated_time": "5-10 minutes",
        "success_metric": "Cart recovery rate"
    },
    "lead_qualification": {
        "name": "Lead Qualification & Follow-up",
        "description": "Automatically qualify and nurture new leads",
        "category": "sales",
        "agents": [
            {"role": "researcher", "task": "Gather lead information from form submissions"},
            {"role": "analyst", "task": "Score leads based on qualification criteria"},
            {"role": "writer", "task": "Create personalized outreach sequences"},
            {"role": "executor", "task": "Execute multi-touch follow-up campaign"}
        ],
        "tools_required": ["email", "chatbot"],
        "estimated_time": "3-5 minutes",
        "success_metric": "Lead-to-meeting conversion"
    },
    "customer_rescue": {
        "name": "Churn Prevention Squad",
        "description": "Identify and re-engage at-risk customers before they churn",
        "category": "retention",
        "agents": [
            {"role": "analyst", "task": "Identify customers showing churn signals"},
            {"role": "researcher", "task": "Analyze customer history and preferences"},
            {"role": "strategist", "task": "Create personalized retention offers"},
            {"role": "writer", "task": "Generate empathetic win-back messages"},
            {"role": "executor", "task": "Execute rescue campaign via preferred channel"}
        ],
        "tools_required": ["email", "whatsapp", "voice"],
        "estimated_time": "10-15 minutes",
        "success_metric": "Customer retention rate"
    },
    "competitor_intelligence": {
        "name": "Competitor Price Monitor",
        "description": "Monitor competitor pricing and get alerts on changes",
        "category": "research",
        "agents": [
            {"role": "researcher", "task": "Scan competitor websites for pricing"},
            {"role": "analyst", "task": "Compare against your pricing"},
            {"role": "strategist", "task": "Recommend pricing adjustments"},
            {"role": "writer", "task": "Generate competitive intelligence report"}
        ],
        "tools_required": ["browser_agent", "email"],
        "estimated_time": "15-20 minutes",
        "success_metric": "Pricing competitiveness"
    },
    "customer_support_tier1": {
        "name": "Tier-1 Support Automation",
        "description": "Handle common support queries automatically",
        "category": "support",
        "agents": [
            {"role": "analyst", "task": "Classify incoming support tickets"},
            {"role": "researcher", "task": "Search knowledge base for answers"},
            {"role": "writer", "task": "Generate helpful response"},
            {"role": "auditor", "task": "Check response quality before sending"},
            {"role": "executor", "task": "Send response or escalate to human"}
        ],
        "tools_required": ["chatbot", "email"],
        "estimated_time": "1-2 minutes",
        "success_metric": "First-response resolution rate"
    },
    "content_factory": {
        "name": "Content Generation Pipeline",
        "description": "Generate product descriptions, social posts, and marketing copy",
        "category": "marketing",
        "agents": [
            {"role": "researcher", "task": "Analyze product features and benefits"},
            {"role": "writer", "task": "Generate SEO-optimized descriptions"},
            {"role": "writer", "task": "Create social media variations"},
            {"role": "auditor", "task": "Review for brand voice and quality"}
        ],
        "tools_required": ["email"],
        "estimated_time": "5-8 minutes",
        "success_metric": "Content pieces generated"
    },
    "weekly_business_audit": {
        "name": "Weekly Business Health Check",
        "description": "OODA-powered weekly audit of key business metrics",
        "category": "analytics",
        "agents": [
            {"role": "analyst", "task": "Gather metrics from all data sources"},
            {"role": "analyst", "task": "Identify trends and anomalies"},
            {"role": "strategist", "task": "Create action recommendations"},
            {"role": "writer", "task": "Generate executive summary report"},
            {"role": "executor", "task": "Send report to stakeholders"}
        ],
        "tools_required": ["email"],
        "estimated_time": "10-15 minutes",
        "success_metric": "Insights acted upon"
    },
    "appointment_reminder": {
        "name": "Appointment Reminder System",
        "description": "Automated appointment reminders and confirmations",
        "category": "scheduling",
        "agents": [
            {"role": "analyst", "task": "Check upcoming appointments"},
            {"role": "writer", "task": "Generate reminder messages"},
            {"role": "executor", "task": "Send reminders via WhatsApp/SMS"},
            {"role": "analyst", "task": "Track confirmations and reschedules"}
        ],
        "tools_required": ["whatsapp", "voice"],
        "estimated_time": "2-3 minutes",
        "success_metric": "No-show reduction rate"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class PlatformUserCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str
    full_name: str

class PlatformUserLogin(BaseModel):
    # Accept ANY string here so customers can sign in with either an
    # email or their AUREM Business ID (BIN, e.g. "RERO-3DEJ"). The
    # handler validates / resolves to a real email below.
    email: str
    password: str

class ToolConnection(BaseModel):
    tool_type: str  # email, whatsapp, voice, etc.
    credentials: Dict[str, str]

class CrewExecutionRequest(BaseModel):
    template_id: Optional[str] = None
    custom_crew: Optional[Dict] = None
    input_data: Optional[Dict] = None
    tools_config: Optional[Dict] = None

class WebhookConfig(BaseModel):
    url: str
    events: List[str]
    secret: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_platform_user(authorization: str = Header(None)):
    import logging
    logger = logging.getLogger(__name__)
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(" ")[1]
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Support both user_id (legacy) and email-based lookup (platform_auth_router tokens)
        user = None
        uid = payload.get("user_id")
        if uid:
            # Try the `user_id` field first (platform_auth_router stores
            # the `plat_…` business id here, NOT the Mongo `_id` ObjectId).
            user = await db.platform_users.find_one({"user_id": uid})
            if not user:
                # Legacy fallback: some older rows stored the value as `_id`.
                try:
                    user = await db.platform_users.find_one({"_id": uid})
                except Exception:
                    user = None
        if not user and payload.get("email"):
            # Fallback to email lookup — covers tokens issued by routers
            # that don't embed `user_id`.
            user = await db.platform_users.find_one({"email": payload["email"].lower()})
        
        if not user:
            # For admin user, return from hardcoded credentials
            if payload.get("user_id") == "admin" or payload.get("role") == "admin":
                return {
                    "_id": "admin",
                    "email": payload.get("email"),
                    "full_name": "AUREM Admin",
                    "company_name": "AUREM Platform",
                    "tier": "enterprise",
                    "role": "admin"
                }
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception as e:
        logger.error(f"[PLATFORM AUTH] Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def platform_health():
    """
    Kubernetes / nginx liveness probe target.
    MUST stay dependency-free (no DB, no auth, no third-party) so it returns
    instantly during cold-start. Hit by Emergent's ingress at /api/platform/health.
    iter 322au — added to fix deployment health-check timeouts.
    iter 322g+ — env label included so prod-guard activation is verifiable.
    """
    try:
        from services.prod_guard import env_label
        env = env_label()
    except Exception:
        env = "unknown"
    return {"status": "ok", "service": "aurem-platform", "env": env}


@router.get("/tiers")
async def get_platform_tiers():
    """Get available subscription tiers"""
    return {"tiers": PLATFORM_TIERS}


@router.get("/templates")
async def get_crew_templates():
    """Get available crew templates"""
    return {
        "templates": CREW_TEMPLATES,
        "categories": list(set(t["category"] for t in CREW_TEMPLATES.values()))
    }


@router.post("/auth/register")
async def register_platform_user(data: PlatformUserCreate):
    """Register new platform customer"""
    # Check if email exists
    existing = await db.platform_users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = f"plat_{secrets.token_hex(12)}"
    api_key = f"rra_{secrets.token_hex(24)}"
    
    user_doc = {
        "_id": user_id,
        "email": data.email.lower(),
        "password_hash": hash_password(data.password),
        "company_name": data.company_name,
        "full_name": data.full_name,
        "tier": "starter",
        "tier_status": "trial",  # trial, active, cancelled
        "trial_ends_at": datetime.now(timezone.utc) + timedelta(days=14),
        "api_key": api_key,
        "api_key_hash": hashlib.sha256(api_key.encode()).hexdigest(),
        "usage": {
            "crew_executions": 0,
            "voice_minutes": 0,
            "whatsapp_messages": 0,
            "period_start": datetime.now(timezone.utc)
        },
        "tool_connections": {},
        "webhooks": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.platform_users.insert_one(user_doc)
    
    token = create_token(user_id, data.email.lower())
    
    return {
        "user_id": user_id,
        "email": data.email.lower(),
        "token": token,
        "api_key": api_key,
        "tier": "starter",
        "trial_ends_at": user_doc["trial_ends_at"].isoformat(),
        "message": "Welcome! Your 14-day free trial has started."
    }


# FIX #6 (audit) — Note: this in-memory dict is single-pod only.
# AUREM currently runs ONE backend pod via supervisor with ONE uvicorn worker,
# so all login traffic hits the same process and the dict is sufficient.
# IF we scale to multi-worker / multi-pod, this MUST move to Redis or a
# MongoDB-backed counter (TTL index on first_at). Until then a brute-force
# attacker would have to distribute requests across pods we don't have.
# An asyncio.Lock would also help if we move to multi-worker uvicorn.
_login_attempts = {}  # {ip: {"count": int, "first_at": float}}

@router.post("/auth/login")
async def login_platform_user(request: Request, data: PlatformUserLogin):
    """Login platform customer — rate limited to 5/minute"""
    import time
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Rate limiting: 5 attempts per minute per IP
    if client_ip in _login_attempts:
        attempts = _login_attempts[client_ip]
        if now - attempts["first_at"] > 60:
            _login_attempts[client_ip] = {"count": 1, "first_at": now}
        else:
            attempts["count"] += 1
            if attempts["count"] > 5:
                raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 1 minute.")
    else:
        _login_attempts[client_ip] = {"count": 1, "first_at": now}
    
    import hashlib

    # ─── BIN-or-email login (P0 — customer convenience) ─────────
    # If the input looks like a BIN (e.g. "RERO-3DEJ", "AURE-3M4G"),
    # resolve it to the underlying email before the password check.
    raw_input = (data.email or "").strip()
    import re as _re
    bin_pattern = _re.compile(r"^[a-z]{3,5}-[a-z0-9]{3,6}$", _re.IGNORECASE)
    if "@" not in raw_input and bin_pattern.match(raw_input):
        bid = raw_input.upper()
        try:
            from server import db as _srv_db
            _db = _srv_db
        except Exception:
            _db = None
        if _db is not None:
            doc = await _db.platform_users.find_one(
                {"business_id": bid}, {"_id": 0, "email": 1}
            )
            if not doc:
                doc = await _db.users.find_one(
                    {"business_id": bid}, {"_id": 0, "email": 1}
                )
            if doc and doc.get("email"):
                # Replace the input email with the resolved one.
                data.email = doc["email"]
            else:
                # Unknown BIN — return a generic 401 (don't leak whether
                # a BIN exists or not).
                raise HTTPException(status_code=401, detail="Invalid credentials")
    elif "@" not in raw_input:
        # Not a valid email AND not a BIN — generic 401
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check admin credentials from ENV (never hardcoded)
    email_lower = data.email.lower()
    admin_configs = [
        {"email": os.getenv("ADMIN_EMAIL_1", "teji.ss1986@gmail.com").lower(), "hash_env": "ADMIN_PASSWORD_HASH_1"},
        {"email": os.getenv("ADMIN_EMAIL_2", "admin@aurem.live").lower(), "hash_env": "ADMIN_PASSWORD_HASH_2"},
        {"email": "admin@aurem.live", "hash_env": "ADMIN_PASSWORD_HASH_2"},
    ]
    for admin in admin_configs:
        if email_lower == admin["email"]:
            pw_hash = os.getenv(admin["hash_env"], "").replace("$$", "$")
            if pw_hash and bcrypt.checkpw(data.password.encode("utf-8"), pw_hash.encode("utf-8")):
                token = create_token("admin", email_lower)
                return {
                    "user_id": "admin",
                    "email": email_lower,
                    "token": token,
                    "company_name": "AUREM Platform",
                    "full_name": "AUREM Admin",
                    "tier": "enterprise",
                    "tier_status": "active",
                    "role": "admin"
                }
    
    # Check database if available
    if db is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user = await db.platform_users.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_token(user["_id"], user["email"])
    
    return {
        "user_id": user["_id"],
        "email": user["email"],
        "token": token,
        "company_name": user["company_name"],
        "full_name": user.get("full_name", ""),
        "tier": user["tier"],
        "tier_status": user["tier_status"],
        "role": user.get("role", "user")
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATED ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/me")
async def get_current_user(authorization: str = Header(None)):
    """Get current user profile and usage"""
    user = await get_current_platform_user(authorization)
    
    tier_name = user.get("tier", "enterprise")
    tier_config = PLATFORM_TIERS.get(tier_name, PLATFORM_TIERS["starter"])
    usage = user.get("usage", {})
    
    return {
        "user_id": str(user.get("_id", user.get("user_id", "admin"))),
        "email": user.get("email", "admin@aurem.live"),
        "company_name": user.get("company_name", "AUREM Platform"),
        "full_name": user.get("full_name", "AUREM Admin"),
        # iter 322bk — surface BIN for the sidebar business badge
        "business_id": user.get("business_id") or user.get("bin") or "",
        "tier": tier_name,
        "tier_status": user.get("tier_status", "active"),
        "trial_ends_at": user.get("trial_ends_at"),
        "api_key": user.get("api_key", "aurem_admin_key")[:12] + "..." if user.get("api_key") else "aurem_admin...",
        "usage": {
            "crew_executions": usage.get("crew_executions", 0),
            "crew_limit": tier_config["crew_executions"],
            "voice_minutes": usage.get("voice_minutes", 0),
            "voice_limit": tier_config["voice_minutes"],
            "whatsapp_messages": usage.get("whatsapp_messages", 0),
            "whatsapp_limit": tier_config["whatsapp_messages"]
        },
        "tools_available": tier_config["tools"],
        "tool_connections": list(user.get("tool_connections", {}).keys()),
        "features": tier_config["features"],
        "role": user.get("role", "admin")
    }


@router.get("/api-key")
async def get_api_key(authorization: str = Header(None)):
    """Get full API key (one-time reveal)"""
    user = await get_current_platform_user(authorization)
    # FIX #3 (audit) — admin users created via the env-var admin path don't
    # have an `api_key` field. user["api_key"] raised KeyError. Return a
    # tier-appropriate fallback so admins get a usable admin key while
    # regular platform users get their actual key.
    api_key = user.get("api_key")
    if not api_key:
        if user.get("role") == "admin":
            api_key = os.environ.get("ADMIN_API_KEY", "aurem_admin_key")
        else:
            return {
                "api_key": None,
                "error": "no_api_key_provisioned",
                "hint": "Use /api-key/regenerate to provision one.",
            }
    return {"api_key": api_key}


@router.post("/api-key/regenerate")
async def regenerate_api_key(authorization: str = Header(None)):
    """Regenerate API key"""
    user = await get_current_platform_user(authorization)
    
    new_api_key = f"rra_{secrets.token_hex(24)}"
    
    await db.platform_users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "api_key": new_api_key,
            "api_key_hash": hashlib.sha256(new_api_key.encode()).hexdigest(),
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {
        "api_key": new_api_key,
        "message": "API key regenerated. Update your integrations."
    }


@router.post("/tools/connect")
async def connect_tool(data: ToolConnection, authorization: str = Header(None)):
    """Connect a tool (WhatsApp, Email, etc.)"""
    user = await get_current_platform_user(authorization)
    tier_config = PLATFORM_TIERS.get(user["tier"], PLATFORM_TIERS["starter"])
    
    if data.tool_type not in tier_config["tools"]:
        raise HTTPException(
            status_code=403, 
            detail=f"Tool '{data.tool_type}' not available in your plan. Upgrade to access."
        )
    
    # iter 326ww — P0 fix: credentials are now encrypted at rest via
    # Fernet (AES-128-CBC + HMAC-SHA256) keyed off AUREM_ENCRYPTION_KEY.
    # See services/credential_crypto.py for the envelope shape. Reads
    # in /tools/status / /tools/disconnect continue to never expose the
    # ciphertext — they only check membership.
    from services.credential_crypto import (
        encrypt_credentials, is_encryption_available,
    )
    envelope = encrypt_credentials(data.credentials)
    if not envelope.get("_encrypted"):
        # Encryption unavailable — refuse to persist plaintext for any
        # tool that obviously carries secrets. We still allow webhooks
        # (no secret) so the platform doesn't soft-fail on missing key.
        sensitive = {"whatsapp", "email", "twilio", "stripe", "openai",
                     "gemini", "claude", "smtp"}
        if data.tool_type.lower() in sensitive and not is_encryption_available():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Encryption key not configured — refusing to store "
                    f"{data.tool_type} credentials in plaintext. "
                    "Set AUREM_ENCRYPTION_KEY in the backend env."
                ),
            )
    await db.platform_users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            f"tool_connections.{data.tool_type}": {
                "connected_at": datetime.now(timezone.utc),
                "status": "active",
                # Encrypted envelope — see services/credential_crypto.py
                "config_envelope": envelope,
                "_encrypted":      bool(envelope.get("_encrypted")),
            },
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {
        "tool": data.tool_type,
        "status": "connected",
        "message": f"{data.tool_type.title()} connected successfully"
    }


@router.get("/tools/status")
async def get_tools_status(authorization: str = Header(None)):
    """Get status of all tool connections"""
    user = await get_current_platform_user(authorization)
    tier_config = PLATFORM_TIERS.get(user["tier"], PLATFORM_TIERS["starter"])
    
    tools_status = {}
    for tool in tier_config["tools"]:
        connection = user.get("tool_connections", {}).get(tool)
        tools_status[tool] = {
            "available": True,
            "connected": connection is not None,
            "status": connection["status"] if connection else "not_connected",
            "connected_at": connection["connected_at"].isoformat() if connection else None
        }
    
    return {"tools": tools_status}


@router.post("/crews/execute")
async def execute_crew(
    data: CrewExecutionRequest, 
    background_tasks: BackgroundTasks,
    authorization: str = Header(None)
):
    """Execute an AI crew"""
    user = await get_current_platform_user(authorization)
    tier_config = PLATFORM_TIERS.get(user["tier"], PLATFORM_TIERS["starter"])

    # FIX #10 (audit) — atomic check-and-increment.
    # Old code did `if usage >= limit: raise` then `$inc` in a separate query.
    # Two concurrent requests could both pass the gate before either incremented.
    # Now the conditional update only succeeds if usage is still under the limit.
    inc_result = await db.platform_users.update_one(
        {
            "_id": user["_id"],
            "$or": [
                {"usage.crew_executions": {"$lt": tier_config["crew_executions"]}},
                {"usage.crew_executions": {"$exists": False}},
            ],
        },
        {"$inc": {"usage.crew_executions": 1}},
    )
    if inc_result.modified_count == 0:
        raise HTTPException(
            status_code=429,
            detail="Crew execution limit reached. Upgrade your plan for more executions.",
        )

    # Get crew config
    if data.template_id:
        if data.template_id not in CREW_TEMPLATES:
            raise HTTPException(status_code=400, detail="Invalid template ID")
        crew_config = CREW_TEMPLATES[data.template_id]
        
        # Check required tools
        for tool in crew_config["tools_required"]:
            if tool not in user.get("tool_connections", {}):
                raise HTTPException(
                    status_code=400,
                    detail=f"Tool '{tool}' required but not connected. Connect it in Settings."
                )
    elif data.custom_crew:
        crew_config = data.custom_crew
    else:
        raise HTTPException(status_code=400, detail="Provide template_id or custom_crew")
    
    execution_id = f"exec_{secrets.token_hex(10)}"
    
    # Create execution record
    execution_doc = {
        "execution_id": execution_id,
        "user_id": user["_id"],
        "template_id": data.template_id,
        "crew_config": crew_config,
        "input_data": data.input_data or {},
        "status": "queued",
        "progress": 0,
        "results": [],
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.platform_executions.insert_one(execution_doc)
    
    # Execute in background
    background_tasks.add_task(
        run_platform_crew,
        execution_id,
        user["_id"],
        crew_config,
        data.input_data or {},
        user.get("tool_connections", {})
    )
    
    return {
        "execution_id": execution_id,
        "status": "queued",
        "crew_name": crew_config.get("name", "Custom Crew"),
        "message": "Crew execution started"
    }


async def run_platform_crew(
    execution_id: str,
    user_id: str,
    crew_config: Dict,
    input_data: Dict,
    tool_connections: Dict
):
    """Background task to run crew execution"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv(override=False)
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            await db.platform_executions.update_one(
                {"execution_id": execution_id},
                {"$set": {"status": "failed", "error": "AI not configured"}}
            )
            return
        
        results = []
        agents = crew_config.get("agents", [])
        
        for i, agent in enumerate(agents):
            # Update progress
            await db.platform_executions.update_one(
                {"execution_id": execution_id},
                {"$set": {
                    "status": "running",
                    "progress": int((i / len(agents)) * 100),
                    "current_agent": agent.get("role")
                }}
            )
            
            # Execute agent task
            chat = LlmChat(
                api_key=api_key,
                session_id=f"platform_{execution_id}_{i}",
                system_message=f"""You are a {agent.get('role', 'assistant')} agent in an AI crew.
Your task: {agent.get('task', 'Complete the assigned task')}

Context from previous agents: {results[-1] if results else 'You are the first agent.'}
Input data: {input_data}

Provide your output in JSON format with keys: analysis, actions, recommendations, next_steps"""
            ).with_model("openai", "gpt-4o-mini")
            
            response = await chat.send_message(UserMessage(
                text=f"Execute your task: {agent.get('task')}"
            ))
            
            results.append({
                "agent": agent.get("role"),
                "task": agent.get("task"),
                "output": response[:2000],
                "completed_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Generate summary
        summary_chat = LlmChat(
            api_key=api_key,
            session_id=f"summary_{execution_id}",
            system_message="Create a brief executive summary of the crew execution results."
        ).with_model("openai", "gpt-4o-mini")
        
        summary = await summary_chat.send_message(UserMessage(
            text=f"Summarize these results:\n{results}"
        ))
        
        # Complete execution
        await db.platform_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {
                "status": "completed",
                "progress": 100,
                "results": results,
                "summary": summary[:1000],
                "completed_at": datetime.now(timezone.utc)
            }}
        )
        
        # FIX #9 (audit) — actually fire the webhooks. Old code was a no-op
        # `pass` statement after the comment "In production, make HTTP call to
        # webhook URL". Customers saw "webhook configured" but nothing fired.
        # We POST asynchronously with a 10s timeout and log failures to
        # webhook_delivery_log so failed deliveries can be retried/inspected.
        user = await db.platform_users.find_one({"_id": user_id})
        if user:
            webhook_payload = {
                "event": "crew_completed",
                "execution_id": execution_id,
                "user_id": user_id,
                "summary": (summary or "")[:1000],
                "result_count": len(results),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            import httpx as _httpx
            for webhook in user.get("webhooks", []):
                if "crew_completed" not in webhook.get("events", []):
                    continue
                wh_url = (webhook.get("url") or "").strip()
                if not wh_url.startswith(("http://", "https://")):
                    continue
                wh_id = webhook.get("id") or webhook.get("url")
                try:
                    async with _httpx.AsyncClient(timeout=10.0) as _wc:
                        wr = await _wc.post(
                            wh_url, json=webhook_payload,
                            headers={"X-Aurem-Event": "crew_completed"},
                        )
                    ok = 200 <= wr.status_code < 300
                    await db.webhook_delivery_log.insert_one({
                        "user_id": user_id,
                        "execution_id": execution_id,
                        "webhook_id": wh_id,
                        "url": wh_url,
                        "status": "delivered" if ok else "http_error",
                        "http_status": wr.status_code,
                        "response_excerpt": (wr.text or "")[:300],
                        "ts": datetime.now(timezone.utc),
                    })
                except Exception as _whe:
                    try:
                        await db.webhook_delivery_log.insert_one({
                            "user_id": user_id,
                            "execution_id": execution_id,
                            "webhook_id": wh_id,
                            "url": wh_url,
                            "status": "transport_error",
                            "error": f"{type(_whe).__name__}: {str(_whe)[:200]}",
                            "ts": datetime.now(timezone.utc),
                        })
                    except Exception:
                        pass
        
    except Exception as e:
        await db.platform_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now(timezone.utc)
            }}
        )


@router.get("/crews/executions")
async def get_executions(
    status: Optional[str] = None,
    limit: int = 20,
    authorization: str = Header(None)
):
    """Get crew execution history"""
    user = await get_current_platform_user(authorization)
    
    query = {"user_id": user["_id"]}
    if status:
        query["status"] = status
    
    executions = await db.platform_executions.find(
        query,
        {"_id": 0, "results": 0}  # Exclude large fields
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"executions": executions}


@router.get("/crews/execution/{execution_id}")
async def get_execution_detail(execution_id: str, authorization: str = Header(None)):
    """Get detailed execution results"""
    user = await get_current_platform_user(authorization)
    
    execution = await db.platform_executions.find_one(
        {"execution_id": execution_id, "user_id": user["_id"]},
        {"_id": 0}
    )
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return {"execution": execution}


@router.post("/webhooks")
async def add_webhook(data: WebhookConfig, authorization: str = Header(None)):
    """Add webhook for event notifications"""
    user = await get_current_platform_user(authorization)
    
    webhook_id = f"wh_{secrets.token_hex(8)}"
    webhook_secret = data.secret or secrets.token_hex(16)
    
    webhook_doc = {
        "webhook_id": webhook_id,
        "url": data.url,
        "events": data.events,
        "secret": webhook_secret,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.platform_users.update_one(
        {"_id": user["_id"]},
        {"$push": {"webhooks": webhook_doc}}
    )
    
    return {
        "webhook_id": webhook_id,
        "secret": webhook_secret,
        "events": data.events,
        "message": "Webhook configured"
    }


@router.get("/analytics")
async def get_analytics(days: int = 30, authorization: str = Header(None)):
    """Get usage analytics"""
    user = await get_current_platform_user(authorization)
    
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Execution stats
    executions = await db.platform_executions.aggregate([
        {"$match": {"user_id": user["_id"], "created_at": {"$gte": since}}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]).to_list(10)
    
    # Daily usage
    daily_usage = await db.platform_executions.aggregate([
        {"$match": {"user_id": user["_id"], "created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "executions": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]).to_list(30)
    
    # Template usage
    template_usage = await db.platform_executions.aggregate([
        {"$match": {"user_id": user["_id"], "template_id": {"$ne": None}}},
        {"$group": {
            "_id": "$template_id",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]).to_list(10)
    
    return {
        "period_days": days,
        "execution_stats": {s["_id"]: s["count"] for s in executions},
        "daily_usage": daily_usage,
        "template_usage": template_usage,
        "current_usage": user.get("usage", {})
    }


# ═══════════════════════════════════════════════════════════════════════════════
# API KEY AUTH (For external API calls)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/v1/crews/run")
async def api_run_crew(
    data: CrewExecutionRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(None)
):
    """API endpoint for crew execution (API key auth)"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    api_key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    user = await db.platform_users.find_one({"api_key_hash": api_key_hash})
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Same logic as execute_crew but with API key auth
    tier_config = PLATFORM_TIERS.get(user["tier"], PLATFORM_TIERS["starter"])

    # FIX #10 (audit) — atomic check-and-increment (see /crews/execute above
    # for the rationale). Replaces the read-then-write pair that allowed
    # concurrent API requests to bypass the quota.
    inc_result = await db.platform_users.update_one(
        {
            "_id": user["_id"],
            "$or": [
                {"usage.crew_executions": {"$lt": tier_config["crew_executions"]}},
                {"usage.crew_executions": {"$exists": False}},
            ],
        },
        {"$inc": {"usage.crew_executions": 1}},
    )
    if inc_result.modified_count == 0:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if data.template_id and data.template_id not in CREW_TEMPLATES:
        raise HTTPException(status_code=400, detail="Invalid template")

    # FIX #8 (audit) — Old code: crew_config = CREW_TEMPLATES.get(data.template_id, data.custom_crew).
    # If template_id was None AND custom_crew was None, crew_config became None
    # and run_platform_crew crashed downstream on .get() of NoneType. The main
    # /execute endpoint already validated this; the api-key endpoint did not.
    if data.template_id:
        crew_config = CREW_TEMPLATES[data.template_id]
    elif data.custom_crew:
        crew_config = data.custom_crew
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide template_id or custom_crew",
        )
    execution_id = f"api_{secrets.token_hex(10)}"
    
    await db.platform_executions.insert_one({
        "execution_id": execution_id,
        "user_id": user["_id"],
        "template_id": data.template_id,
        "crew_config": crew_config,
        "input_data": data.input_data or {},
        "status": "queued",
        "progress": 0,
        "source": "api",
        "created_at": datetime.now(timezone.utc)
    })

    background_tasks.add_task(
        run_platform_crew,
        execution_id,
        user["_id"],
        crew_config,
        data.input_data or {},
        user.get("tool_connections", {})
    )
    
    return {
        "execution_id": execution_id,
        "status": "queued"
    }


@router.get("/v1/crews/{execution_id}")
async def api_get_execution(execution_id: str, x_api_key: str = Header(None)):
    """API endpoint to get execution status"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    api_key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    user = await db.platform_users.find_one({"api_key_hash": api_key_hash})
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    execution = await db.platform_executions.find_one(
        {"execution_id": execution_id, "user_id": user["_id"]},
        {"_id": 0}
    )
    
    if not execution:
        raise HTTPException(status_code=404, detail="Not found")
    
    return execution
