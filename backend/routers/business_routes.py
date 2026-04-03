"""
AUREM Business & Multi-Channel API Routes
Manages businesses, agents, and omnichannel communications
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/business", tags=["Business Management"])

# Database reference
db = None

def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class BusinessCreate(BaseModel):
    name: str
    type: str  # skincare, automotive, etc.
    description: str = ""
    industry_keywords: List[str] = []
    tone: str = "professional"
    target_audience: str = ""
    products_services: List[str] = []
    unique_selling_points: List[str] = []

class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tone: Optional[str] = None
    target_audience: Optional[str] = None
    products_services: Optional[List[str]] = None
    unique_selling_points: Optional[List[str]] = None

class ChannelMessageRequest(BaseModel):
    channel: str  # email, whatsapp, voice, sms, web_chat
    sender_id: str
    content: str
    metadata: Dict[str, Any] = {}

class OutboundMessageRequest(BaseModel):
    channel: str
    customer_id: str
    content: str
    metadata: Dict[str, Any] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Token validation would go here
    return {"_id": "admin", "email": "admin@aurem.ai", "role": "admin"}


# ═══════════════════════════════════════════════════════════════════════════════
# BUSINESS ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/list")
async def list_businesses(user = Depends(get_current_user)):
    """List all configured businesses"""
    from services.aurem_business_agents import get_agent_manager
    
    manager = get_agent_manager(db)
    businesses = manager.list_businesses()
    
    return {
        "businesses": [
            {
                "business_id": b.business_id,
                "name": b.name,
                "type": b.type.value,
                "description": b.description,
                "is_active": b.is_active
            }
            for b in businesses
        ],
        "total": len(businesses)
    }

@router.get("/{business_id}")
async def get_business(business_id: str, user = Depends(get_current_user)):
    """Get business details with agents"""
    from services.aurem_business_agents import get_business_ai
    
    business_ai = get_business_ai(db)
    summary = business_ai.get_business_summary(business_id)
    
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    
    return summary

@router.post("/create")
async def create_business(request: BusinessCreate, user = Depends(get_current_user)):
    """Create a new business with agents"""
    from services.aurem_business_agents import get_agent_manager, BusinessConfig, BusinessType
    import uuid
    
    manager = get_agent_manager(db)
    
    # Generate business ID
    business_id = f"ABC-{str(uuid.uuid4())[:4].upper()}"
    
    # Map type
    try:
        business_type = BusinessType(request.type.lower())
    except ValueError:
        business_type = BusinessType.CUSTOM
    
    config = BusinessConfig(
        business_id=business_id,
        name=request.name,
        type=business_type,
        description=request.description,
        industry_keywords=request.industry_keywords,
        tone=request.tone,
        target_audience=request.target_audience,
        products_services=request.products_services,
        unique_selling_points=request.unique_selling_points
    )
    
    manager.add_business(config)
    await manager.save_to_db()
    
    return {
        "business_id": business_id,
        "name": request.name,
        "agents_created": 5,
        "status": "created"
    }

@router.put("/{business_id}")
async def update_business(
    business_id: str, 
    request: BusinessUpdate, 
    user = Depends(get_current_user)
):
    """Update business configuration"""
    from services.aurem_business_agents import get_agent_manager
    
    manager = get_agent_manager(db)
    
    updates = {k: v for k, v in request.dict().items() if v is not None}
    result = manager.update_business(business_id, updates)
    
    if not result:
        raise HTTPException(status_code=404, detail="Business not found")
    
    await manager.save_to_db()
    
    return {
        "business_id": business_id,
        "updated": list(updates.keys()),
        "status": "updated"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{business_id}/agents")
async def list_business_agents(business_id: str, user = Depends(get_current_user)):
    """List all agents for a business"""
    from services.aurem_business_agents import get_agent_manager
    
    manager = get_agent_manager(db)
    agents = manager.get_agents_for_business(business_id)
    
    if not agents:
        raise HTTPException(status_code=404, detail="Business not found or no agents")
    
    return {
        "business_id": business_id,
        "agents": [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "role": a.role.value,
                "capabilities": a.capabilities,
                "model": a.model,
                "is_active": a.is_active
            }
            for a in agents
        ]
    }

@router.post("/{business_id}/chat")
async def chat_with_business(
    business_id: str,
    message: str,
    agent_role: str = None,
    user = Depends(get_current_user)
):
    """Chat with a business-specific AI agent"""
    from services.aurem_business_agents import get_business_ai, AgentRole
    
    business_ai = get_business_ai(db)
    
    # Parse agent role
    role = None
    if agent_role:
        try:
            role = AgentRole(agent_role.lower())
        except ValueError:
            pass
    
    result = await business_ai.chat_with_context(
        message=message,
        business_id=business_id,
        agent_role=role
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# OMNICHANNEL ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{business_id}/message/inbound")
async def process_inbound_message(
    business_id: str,
    request: ChannelMessageRequest,
    user = Depends(get_current_user)
):
    """Process an inbound message from any channel"""
    from services.omnidimension_service import get_omni_service, Channel
    
    omni = get_omni_service(db)
    
    try:
        channel = Channel(request.channel.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid channel: {request.channel}")
    
    result = await omni.process_inbound_message(
        channel=channel,
        business_id=business_id,
        sender_id=request.sender_id,
        content=request.content,
        metadata=request.metadata
    )
    
    return result

@router.post("/{business_id}/message/outbound")
async def send_outbound_message(
    business_id: str,
    request: OutboundMessageRequest,
    user = Depends(get_current_user)
):
    """Send an outbound message via any channel"""
    from services.omnidimension_service import get_omni_service, Channel
    
    omni = get_omni_service(db)
    
    try:
        channel = Channel(request.channel.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid channel: {request.channel}")
    
    result = await omni.send_outbound_message(
        channel=channel,
        business_id=business_id,
        customer_id=request.customer_id,
        content=request.content,
        metadata=request.metadata
    )
    
    return result

@router.get("/{business_id}/analytics/channels")
async def get_channel_analytics(business_id: str, user = Depends(get_current_user)):
    """Get analytics across all communication channels"""
    from services.omnidimension_service import get_omni_service
    
    omni = get_omni_service(db)
    analytics = await omni.get_channel_analytics(business_id)
    
    return analytics

@router.get("/{business_id}/customers/{customer_id}")
async def get_customer_360(
    business_id: str, 
    customer_id: str, 
    user = Depends(get_current_user)
):
    """Get 360-degree customer view"""
    from services.omnidimension_service import get_omni_service
    
    omni = get_omni_service(db)
    result = await omni.get_customer_360(customer_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


print("[STARTUP] Business & OmniChannel Routes loaded")
