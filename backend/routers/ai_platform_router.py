"""
ReRoots AI Platform - Commercial AI Crews Service
The all-in-one AI platform with Voice, WhatsApp, Email, Chat + AI Crews
"""

from fastapi import APIRouter, HTTPException, Depends, Header, BackgroundTasks
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

JWT_SECRET = os.environ.get("JWT_SECRET", "reroots-ai-platform-secret-key")
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
    email: EmailStr
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
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_platform_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.platform_users.find_one({"_id": payload["user_id"]})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

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


@router.post("/auth/login")
async def login_platform_user(data: PlatformUserLogin):
    """Login platform customer"""
    # Check default admin credentials first (hardcoded for development)
    if data.email.lower() == "teji.ss1986@gmail.com" and data.password == "Admin123":
        import hashlib
        token = create_token("admin", data.email.lower())
        return {
            "user_id": "admin",
            "email": data.email.lower(),
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
    
    tier_config = PLATFORM_TIERS.get(user["tier"], PLATFORM_TIERS["starter"])
    usage = user.get("usage", {})
    
    return {
        "user_id": user["_id"],
        "email": user["email"],
        "company_name": user["company_name"],
        "full_name": user["full_name"],
        "tier": user["tier"],
        "tier_status": user["tier_status"],
        "trial_ends_at": user.get("trial_ends_at"),
        "api_key": user["api_key"][:12] + "..." + user["api_key"][-4:],
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
        "features": tier_config["features"]
    }


@router.get("/api-key")
async def get_api_key(authorization: str = Header(None)):
    """Get full API key (one-time reveal)"""
    user = await get_current_platform_user(authorization)
    return {"api_key": user["api_key"]}


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
    
    # Store encrypted credentials (in production, use proper encryption)
    await db.platform_users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            f"tool_connections.{data.tool_type}": {
                "connected_at": datetime.now(timezone.utc),
                "status": "active",
                "config": data.credentials
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
    usage = user.get("usage", {})
    
    # Check usage limits
    if usage.get("crew_executions", 0) >= tier_config["crew_executions"]:
        raise HTTPException(
            status_code=429, 
            detail="Crew execution limit reached. Upgrade your plan for more executions."
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
    
    # Increment usage
    await db.platform_users.update_one(
        {"_id": user["_id"]},
        {"$inc": {"usage.crew_executions": 1}}
    )
    
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
        load_dotenv()
        
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
        
        # Trigger webhooks
        user = await db.platform_users.find_one({"_id": user_id})
        for webhook in user.get("webhooks", []):
            if "crew_completed" in webhook.get("events", []):
                # In production, make HTTP call to webhook URL
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
    usage = user.get("usage", {})
    
    if usage.get("crew_executions", 0) >= tier_config["crew_executions"]:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    if data.template_id and data.template_id not in CREW_TEMPLATES:
        raise HTTPException(status_code=400, detail="Invalid template")
    
    crew_config = CREW_TEMPLATES.get(data.template_id, data.custom_crew)
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
    
    await db.platform_users.update_one(
        {"_id": user["_id"]},
        {"$inc": {"usage.crew_executions": 1}}
    )
    
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
