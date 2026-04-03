"""
AUREM Brain Orchestrator API Router
Exposes the AI Brain via validated AUREM API Keys

Endpoints:
- POST /api/brain/think - Process a message through OODA loop
- GET /api/brain/thought/{thought_id} - Get thought details
- GET /api/brain/thoughts/{business_id} - Get thought history
- GET /api/brain/health - Health check
"""

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

router = APIRouter(prefix="/api/brain", tags=["AUREM Brain"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ThinkRequest(BaseModel):
    """Request to the Brain Orchestrator"""
    message: str
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ThinkResponse(BaseModel):
    """Response from the Brain Orchestrator"""
    thought_id: str
    response: str
    intent: str
    confidence: float
    actions_taken: List[str]
    duration_ms: int
    status: str


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/think", response_model=ThinkResponse)
async def think(
    request: ThinkRequest,
    req: Request,
    authorization: str = Header(None, alias="Authorization")
):
    """
    Process a message through the AUREM Brain OODA Loop.
    
    Requires a valid AUREM API key in the Authorization header:
    `Authorization: Bearer sk_aurem_live_xxxx`
    
    The Brain will:
    1. OBSERVE - Gather context (conversation history, business data)
    2. ORIENT - Analyze intent using LLM
    3. DECIDE - Select appropriate action
    4. ACT - Execute via Action Engine and push to WebSocket
    
    Returns the AI response and any actions taken.
    """
    # Extract API key
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header. Use: Bearer sk_aurem_xxx")
    
    api_key = authorization.replace("Bearer ", "").strip()
    
    # Validate API key
    from services.aurem_commercial.key_service import get_aurem_key_service
    key_service = get_aurem_key_service(get_db())
    key_info = await key_service.validate_key(api_key)
    
    if not key_info:
        raise HTTPException(401, "Invalid or expired API key")
    
    # Check for chat:read scope at minimum
    scopes = key_info.get("scopes", [])
    if "chat:read" not in scopes and "admin:keys" not in scopes:
        raise HTTPException(403, "API key does not have 'chat:read' scope")
    
    # Get client IP
    client_ip = req.client.host if req.client else None
    
    # Process through Brain
    from services.aurem_commercial.brain_orchestrator import get_brain_orchestrator, BrainInput
    brain = get_brain_orchestrator(get_db())
    
    result = await brain.think(
        business_id=key_info["business_id"],
        input_data=BrainInput(
            message=request.message,
            conversation_id=request.conversation_id,
            context=request.context
        ),
        api_key_info=key_info,
        ip_address=client_ip
    )
    
    # Record usage
    await key_service.record_usage(
        key_id=key_info["key_id"],
        business_id=key_info["business_id"],
        operation="brain.think",
        tokens_in=len(request.message.split()),
        tokens_out=len(result.final_response.split()),
        model="gpt-4o-mini",
        latency_ms=result.duration_ms,
        success=result.status.value == "complete"
    )
    
    return ThinkResponse(
        thought_id=result.thought_id,
        response=result.final_response,
        intent=result.phases.get("orient", {}).get("intent", "unknown"),
        confidence=result.phases.get("orient", {}).get("confidence", 0.0),
        actions_taken=result.actions_taken,
        duration_ms=result.duration_ms,
        status=result.status.value
    )


@router.get("/thought/{thought_id}")
async def get_thought(
    thought_id: str,
    authorization: str = Header(None, alias="Authorization")
):
    """
    Get details of a specific thought/processing record.
    
    Requires valid AUREM API key.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    
    api_key = authorization.replace("Bearer ", "").strip()
    
    from services.aurem_commercial.key_service import get_aurem_key_service
    key_service = get_aurem_key_service(get_db())
    key_info = await key_service.validate_key(api_key)
    
    if not key_info:
        raise HTTPException(401, "Invalid API key")
    
    from services.aurem_commercial.brain_orchestrator import get_brain_orchestrator
    brain = get_brain_orchestrator(get_db())
    
    thought = await brain.get_thought(thought_id)
    
    if not thought:
        raise HTTPException(404, "Thought not found")
    
    # Verify business ownership
    if thought.get("business_id") != key_info["business_id"]:
        raise HTTPException(403, "Access denied")
    
    return {"thought": thought}


@router.get("/thoughts/{business_id}")
async def get_thoughts(
    business_id: str,
    limit: int = 20,
    authorization: str = Header(None, alias="Authorization")
):
    """
    Get recent thought history for a business.
    
    Requires valid AUREM API key with matching business_id.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    
    api_key = authorization.replace("Bearer ", "").strip()
    
    from services.aurem_commercial.key_service import get_aurem_key_service
    key_service = get_aurem_key_service(get_db())
    key_info = await key_service.validate_key(api_key)
    
    if not key_info:
        raise HTTPException(401, "Invalid API key")
    
    # Use the key's business_id, ignore the path parameter for security
    actual_business_id = key_info["business_id"]
    
    from services.aurem_commercial.brain_orchestrator import get_brain_orchestrator
    brain = get_brain_orchestrator(get_db())
    
    thoughts = await brain.get_thoughts_for_business(actual_business_id, limit)
    
    return {"thoughts": thoughts, "count": len(thoughts), "business_id": actual_business_id}


@router.get("/my-thoughts")
async def get_my_thoughts(
    limit: int = 20,
    authorization: str = Header(None, alias="Authorization")
):
    """
    Get recent thought history for the API key's business.
    
    Simpler endpoint that uses the key's business_id automatically.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    
    api_key = authorization.replace("Bearer ", "").strip()
    
    from services.aurem_commercial.key_service import get_aurem_key_service
    key_service = get_aurem_key_service(get_db())
    key_info = await key_service.validate_key(api_key)
    
    if not key_info:
        raise HTTPException(401, "Invalid API key")
    
    from services.aurem_commercial.brain_orchestrator import get_brain_orchestrator
    brain = get_brain_orchestrator(get_db())
    
    thoughts = await brain.get_thoughts_for_business(key_info["business_id"], limit)
    
    return {"thoughts": thoughts, "count": len(thoughts), "business_id": key_info["business_id"]}


@router.get("/intents")
async def get_available_intents():
    """
    Get list of available intents the Brain can process.
    
    Public endpoint - no auth required.
    """
    from services.aurem_commercial.brain_orchestrator import IntentType, INTENT_TO_TOOL
    
    intents = []
    for intent in IntentType:
        tool = INTENT_TO_TOOL.get(intent)
        intents.append({
            "intent": intent.value,
            "maps_to_tool": tool,
            "requires_action": tool is not None,
            "description": {
                "chat": "General conversation and questions",
                "book_appointment": "Schedule meetings with calendar integration",
                "check_availability": "Check available time slots",
                "send_email": "Send emails via Gmail",
                "send_whatsapp": "Send WhatsApp messages",
                "create_invoice": "Generate Stripe invoices",
                "create_payment": "Create payment links",
                "query_data": "Business intelligence queries",
                "unknown": "Intent could not be determined"
            }.get(intent.value, "")
        })
    
    return {"intents": intents}


@router.get("/health")
async def health():
    """Health check for Brain Orchestrator"""
    try:
        # Check if we can import the brain
        from services.aurem_commercial.brain_orchestrator import get_brain_orchestrator
        
        # Check LLM key
        import os
        has_llm_key = bool(os.environ.get("EMERGENT_LLM_KEY"))
        
        return {
            "status": "healthy",
            "service": "aurem-brain",
            "llm_configured": has_llm_key,
            "capabilities": [
                "intent_classification",
                "entity_extraction",
                "action_execution",
                "websocket_push"
            ]
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "aurem-brain",
            "error": str(e)
        }
