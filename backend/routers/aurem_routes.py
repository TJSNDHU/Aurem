"""
AUREM AI API Routes
Complete API for the AUREM platform
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
import jwt
import hashlib
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/aurem", tags=["AUREM AI"])

# Database reference (set by main app)
db = None

def set_db(database):
    global db
    db = database

# JWT Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "aurem-secure-jwt-secret-key-2026-production")
JWT_ALGORITHM = "HS256"

# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent: Optional[Dict[str, Any]] = None
    timestamp: str

class OnboardingRequest(BaseModel):
    company_name: str
    industry: str
    team_size: str
    goals: List[str] = []
    email: EmailStr
    password: str
    full_name: str

class AutomationRequest(BaseModel):
    name: str
    description: str = ""
    trigger: str
    actions: List[Dict[str, Any]]
    enabled: bool = True

class ImageGenerationRequest(BaseModel):
    prompt: str
    style: Optional[str] = "professional"

class OODARequest(BaseModel):
    query: Optional[str] = None
    message: Optional[str] = None
    automation: Optional[Dict[str, Any]] = None
    outreach: Optional[Dict[str, Any]] = None

# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def create_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc).timestamp() + 86400 * 30,  # 30 days
        "iat": datetime.now(timezone.utc).timestamp()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    
    if db:
        user = await db.aurem_users.find_one({"_id": payload["user_id"]})
        if user:
            return user
    
    # Return basic user info from token
    return {
        "_id": payload["user_id"],
        "email": payload["email"],
        "tier": "enterprise"
    }

# ═══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/auth/register")
async def register(request: OnboardingRequest):
    """Register a new AUREM user with onboarding data"""
    try:
        # Check if user exists
        if db:
            existing = await db.aurem_users.find_one({"email": request.email.lower()})
            if existing:
                raise HTTPException(status_code=400, detail="Email already registered")
        
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        
        user_data = {
            "_id": user_id,
            "email": request.email.lower(),
            "password_hash": password_hash,
            "full_name": request.full_name,
            "company_name": request.company_name,
            "industry": request.industry,
            "team_size": request.team_size,
            "goals": request.goals,
            "tier": "starter",
            "tier_status": "active",
            "created_at": datetime.now(timezone.utc),
            "onboarding_completed": True,
            "settings": {
                "notifications": True,
                "voice_enabled": False,
                "auto_respond": True
            }
        }
        
        if db:
            await db.aurem_users.insert_one(user_data)
        
        token = create_token(user_id, request.email.lower())
        
        return {
            "user_id": user_id,
            "email": request.email.lower(),
            "token": token,
            "company_name": request.company_name,
            "full_name": request.full_name,
            "tier": "starter"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/auth/login")
async def login(email: str = None, password: str = None, request: Request = None):
    """Login to AUREM platform"""
    try:
        # Handle both JSON body and form data
        if request:
            try:
                body = await request.json()
                email = body.get("email", email)
                password = body.get("password", password)
            except:
                pass
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")
        
        email = email.lower()
        
        # Check hardcoded admin credentials
        admin_creds = {
            "teji.ss1986@gmail.com": "Admin123",
            "admin@aurem.live": "AuremAdmin2024!",
            "admin@aurem.ai": "AuremAdmin2024!"
        }
        
        if email in admin_creds and password == admin_creds[email]:
            token = create_token("admin", email)
            return {
                "user_id": "admin",
                "email": email,
                "token": token,
                "company_name": "AUREM Platform",
                "full_name": "AUREM Admin",
                "tier": "enterprise",
                "tier_status": "active",
                "role": "admin"
            }
        
        # Check database
        if db:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            user = await db.aurem_users.find_one({
                "email": email,
                "password_hash": password_hash
            })
            
            if user:
                token = create_token(str(user["_id"]), email)
                return {
                    "user_id": str(user["_id"]),
                    "email": email,
                    "token": token,
                    "company_name": user.get("company_name", ""),
                    "full_name": user.get("full_name", ""),
                    "tier": user.get("tier", "starter"),
                    "tier_status": user.get("tier_status", "active"),
                    "role": user.get("role", "user")
                }
        
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@router.get("/auth/me")
async def get_me(user = Depends(get_current_user)):
    """Get current user profile"""
    return {
        "user_id": str(user.get("_id", "admin")),
        "email": user.get("email", "admin@aurem.live"),
        "company_name": user.get("company_name", "AUREM Platform"),
        "full_name": user.get("full_name", "AUREM Admin"),
        "tier": user.get("tier", "enterprise"),
        "tier_status": user.get("tier_status", "active"),
        "role": user.get("role", "admin"),
        "settings": user.get("settings", {})
    }

# ═══════════════════════════════════════════════════════════════════════════════
# AI CHAT ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user = Depends(get_current_user)):
    """Send a message to AUREM AI"""
    from services.aurem_ai_service import get_aurem_service
    
    aurem = get_aurem_service(db)
    session_id = request.session_id or str(uuid.uuid4())
    
    result = await aurem.chat(
        session_id=session_id,
        message=request.message,
        user_id=str(user.get("_id", "anonymous"))
    )
    
    return ChatResponse(
        response=result["response"],
        session_id=result["session_id"],
        intent=result.get("intent"),
        timestamp=result["timestamp"]
    )

@router.get("/chat/history")
async def get_chat_history(
    session_id: str = None,
    limit: int = 50,
    user = Depends(get_current_user)
):
    """Get chat history"""
    if not db:
        return {"messages": []}
    
    query = {"user_id": str(user.get("_id"))}
    if session_id:
        query["session_id"] = session_id
    
    messages = await db.aurem_conversations.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"messages": list(reversed(messages))}

# ═══════════════════════════════════════════════════════════════════════════════
# AGENT SWARM ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/agents/status")
async def get_agents_status(user = Depends(get_current_user)):
    """Get status of all AUREM agents"""
    from services.aurem_ai_service import get_aurem_service
    
    aurem = get_aurem_service(db)
    return {
        "agents": aurem.orchestrator.get_swarm_status(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.post("/agents/ooda")
async def run_ooda_cycle(request: OODARequest, user = Depends(get_current_user)):
    """Execute an OODA loop cycle"""
    from services.aurem_ai_service import get_aurem_service
    
    aurem = get_aurem_service(db)
    
    input_data = {}
    if request.query:
        input_data["query"] = request.query
    if request.message:
        input_data["message"] = request.message
    if request.automation:
        input_data["automation"] = request.automation
    if request.outreach:
        input_data["outreach"] = request.outreach
    
    result = await aurem.run_ooda_cycle(input_data)
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATION ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/automations")
async def create_automation(request: AutomationRequest, user = Depends(get_current_user)):
    """Create a new automation"""
    from services.aurem_ai_service import get_aurem_service
    
    aurem = get_aurem_service(db)
    
    automation = await aurem.create_automation({
        "name": request.name,
        "description": request.description,
        "trigger": request.trigger,
        "steps": request.actions,
        "enabled": request.enabled,
        "user_id": str(user.get("_id"))
    })
    
    if db:
        automation["user_id"] = str(user.get("_id"))
        await db.aurem_automations.insert_one(automation)
    
    return automation

@router.get("/automations")
async def list_automations(user = Depends(get_current_user)):
    """List user's automations"""
    if not db:
        return {"automations": []}
    
    automations = await db.aurem_automations.find(
        {"user_id": str(user.get("_id"))},
        {"_id": 0}
    ).to_list(100)
    
    return {"automations": automations}

@router.delete("/automations/{automation_id}")
async def delete_automation(automation_id: str, user = Depends(get_current_user)):
    """Delete an automation"""
    if db:
        result = await db.aurem_automations.delete_one({
            "automation_id": automation_id,
            "user_id": str(user.get("_id"))
        })
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Automation not found")
    
    return {"status": "deleted", "automation_id": automation_id}

# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE GENERATION ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/images/generate")
async def generate_image(request: ImageGenerationRequest, user = Depends(get_current_user)):
    """Generate an image using AI"""
    from services.aurem_ai_service import get_aurem_service
    
    aurem = get_aurem_service(db)
    
    # Enhance prompt with style
    enhanced_prompt = f"{request.prompt}. Style: {request.style}, high quality, professional"
    
    result = await aurem.generate_image(enhanced_prompt)
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# METRICS & ANALYTICS ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/metrics")
async def get_metrics(user = Depends(get_current_user)):
    """Get platform metrics"""
    from services.aurem_ai_service import get_aurem_service
    
    aurem = get_aurem_service(db)
    metrics = aurem.get_platform_metrics()
    
    # Add user-specific metrics
    if db:
        user_id = str(user.get("_id"))
        conversation_count = await db.aurem_conversations.count_documents({"user_id": user_id})
        automation_count = await db.aurem_automations.count_documents({"user_id": user_id})
        metrics["user_metrics"] = {
            "conversations": conversation_count,
            "automations": automation_count
        }
    
    return metrics

@router.get("/analytics/overview")
async def get_analytics_overview(user = Depends(get_current_user)):
    """Get analytics overview"""
    return {
        "period": "30d",
        "metrics": {
            "total_conversations": 2848,
            "avg_response_time": 1.5,
            "automation_runs": 1247,
            "leads_generated": 89,
            "meetings_booked": 23,
            "revenue_attributed": 48500
        },
        "trends": {
            "conversations": "+12%",
            "automation_efficiency": "+8%",
            "lead_quality": "+15%"
        }
    }

# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITY FEED ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/activity/feed")
async def get_activity_feed(limit: int = 20, user = Depends(get_current_user)):
    """Get recent activity feed"""
    activities = [
        {"type": "agent", "agent": "Scout", "action": "Completed market analysis for 3 brands", "time": "2 min ago"},
        {"type": "automation", "name": "WhatsApp Flow", "action": "Sent 847 messages", "time": "5 min ago"},
        {"type": "agent", "agent": "Architect", "action": "Built new automation pipeline", "time": "23 min ago"},
        {"type": "system", "action": "Circuit breaker reset — all systems clear", "time": "1 hr ago"},
        {"type": "agent", "agent": "Closer", "action": "Completed 12 outreach calls", "time": "2 hr ago"},
    ]
    
    return {"activities": activities[:limit]}

# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION & BILLING ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

SUBSCRIPTION_TIERS = {
    "starter": {
        "name": "Starter",
        "price": 49.00,
        "features": ["1,000 AI queries/mo", "Basic automations", "Email support"],
        "limits": {"queries": 1000, "automations": 5, "agents": 2}
    },
    "growth": {
        "name": "Growth",
        "price": 149.00,
        "features": ["10,000 AI queries/mo", "Advanced automations", "WhatsApp integration", "Priority support"],
        "limits": {"queries": 10000, "automations": 25, "agents": 4}
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 499.00,
        "features": ["Unlimited AI queries", "Full agent swarm", "All integrations", "Dedicated support", "Custom training"],
        "limits": {"queries": -1, "automations": -1, "agents": 5}
    }
}

@router.get("/subscriptions/tiers")
async def get_subscription_tiers():
    """Get available subscription tiers"""
    return {"tiers": SUBSCRIPTION_TIERS}

@router.post("/subscriptions/checkout")
async def create_checkout(tier: str, request: Request, user = Depends(get_current_user)):
    """Create a Stripe checkout session for subscription"""
    if tier not in SUBSCRIPTION_TIERS:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    tier_info = SUBSCRIPTION_TIERS[tier]
    
    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
        
        stripe_key = os.environ.get("STRIPE_API_KEY")
        if not stripe_key:
            raise HTTPException(status_code=500, detail="Payment not configured")
        
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        
        stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=webhook_url)
        
        checkout_request = CheckoutSessionRequest(
            amount=tier_info["price"],
            currency="usd",
            success_url=f"{host_url}/dashboard?session_id={{CHECKOUT_SESSION_ID}}&status=success",
            cancel_url=f"{host_url}/dashboard/billing?status=cancelled",
            metadata={
                "user_id": str(user.get("_id")),
                "tier": tier,
                "user_email": user.get("email", "")
            }
        )
        
        session = await stripe_checkout.create_checkout_session(checkout_request)
        
        # Store transaction
        if db:
            await db.payment_transactions.insert_one({
                "session_id": session.session_id,
                "user_id": str(user.get("_id")),
                "tier": tier,
                "amount": tier_info["price"],
                "currency": "usd",
                "status": "pending",
                "created_at": datetime.now(timezone.utc)
            })
        
        return {
            "checkout_url": session.url,
            "session_id": session.session_id
        }
    
    except ImportError:
        raise HTTPException(status_code=500, detail="Payment integration not available")
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

@router.get("/subscriptions/status/{session_id}")
async def get_subscription_status(session_id: str, user = Depends(get_current_user)):
    """Check subscription payment status"""
    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout
        
        stripe_key = os.environ.get("STRIPE_API_KEY")
        stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url="")
        
        status = await stripe_checkout.get_checkout_status(session_id)
        
        # Update database if paid
        if db and status.payment_status == "paid":
            transaction = await db.payment_transactions.find_one({"session_id": session_id})
            if transaction and transaction.get("status") != "completed":
                # Update transaction
                await db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}}
                )
                
                # Upgrade user tier
                await db.aurem_users.update_one(
                    {"_id": transaction["user_id"]},
                    {"$set": {"tier": transaction["tier"], "tier_status": "active"}}
                )
        
        return {
            "status": status.status,
            "payment_status": status.payment_status,
            "amount": status.amount_total / 100,  # Convert cents to dollars
            "currency": status.currency
        }
    
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail="Failed to check status")

# ═══════════════════════════════════════════════════════════════════════════════
# VOICE-TO-VOICE ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/voice/config")
async def get_voice_config(user = Depends(get_current_user)):
    """Get voice service configuration for client SDK"""
    from services.aurem_voice_service import get_voice_service
    
    voice_service = get_voice_service(db)
    return voice_service.get_client_sdk_config()

@router.post("/voice/web-call")
async def start_web_call(user = Depends(get_current_user)):
    """Start a web-based voice call session"""
    from services.aurem_voice_service import get_voice_service, VoiceCallConfig
    
    voice_service = get_voice_service(db)
    result = await voice_service.create_web_call(
        user_id=str(user.get("_id", "anonymous")),
        config=VoiceCallConfig()
    )
    
    return result

@router.post("/voice/phone-call")
async def start_phone_call(
    phone_number: str,
    user = Depends(get_current_user)
):
    """Initiate an outbound phone call"""
    from services.aurem_voice_service import get_voice_service
    
    voice_service = get_voice_service(db)
    result = await voice_service.create_phone_call(
        phone_number=phone_number,
        user_id=str(user.get("_id", "anonymous"))
    )
    
    return result

@router.post("/voice/end-call/{call_id}")
async def end_voice_call(call_id: str, user = Depends(get_current_user)):
    """End an active voice call"""
    from services.aurem_voice_service import get_voice_service
    
    voice_service = get_voice_service(db)
    return await voice_service.end_call(call_id)

@router.get("/voice/history")
async def get_voice_history(limit: int = 20, user = Depends(get_current_user)):
    """Get voice call history"""
    from services.aurem_voice_service import get_voice_service
    
    voice_service = get_voice_service(db)
    calls = await voice_service.get_call_history(
        user_id=str(user.get("_id", "anonymous")),
        limit=limit
    )
    
    return {"calls": calls}

@router.post("/voice/webhook")
async def voice_webhook(request: Request):
    """Handle Vapi webhook events"""
    from services.aurem_voice_service import get_voice_service
    
    try:
        event = await request.json()
        voice_service = get_voice_service(db)
        return await voice_service.handle_vapi_webhook(event)
    except Exception as e:
        logger.error(f"Voice webhook error: {e}")
        return {"status": "error", "message": str(e)}

print("[STARTUP] AUREM AI Routes loaded")
