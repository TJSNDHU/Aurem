"""
AUREM Public API v1
Client-facing endpoints for external website integrations
Validates sk_aurem_ API keys
"""

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

router = APIRouter(tags=["Public API v1"])  # NO PREFIX - FastAPI will handle it
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    context: Optional[dict] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str

class LeadRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = "widget"

class LeadResponse(BaseModel):
    success: bool
    lead_id: str
    message: str

# ═══════════════════════════════════════════════════════════════════════════════
# API KEY VALIDATION MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════════════

async def validate_api_key(authorization: str = Header(None)):
    """
    Validate client API key (sk_aurem_live_xxx or sk_aurem_test_xxx)
    Returns business_id and key info
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    # Extract key from "Bearer sk_aurem_..."
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    api_key = authorization.replace("Bearer ", "").strip()
    
    # Validate key format
    if not (api_key.startswith("sk_aurem_live_") or api_key.startswith("sk_aurem_test_")):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    
    try:
        from server import db
        from services.aurem_commercial.key_service import get_aurem_key_service
        
        key_service = get_aurem_key_service(db)
        validation = await key_service.validate_key(api_key)
        
        if not validation["valid"]:
            raise HTTPException(status_code=401, detail=validation.get("reason", "Invalid API key"))
        
        # Check rate limit
        if validation.get("rate_limited"):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        return {
            "business_id": validation["business_id"],
            "key_id": validation["key_id"],
            "scopes": validation.get("scopes", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Public API] Key validation error: {e}")
        raise HTTPException(status_code=500, detail="Authentication service error")

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC CHAT ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/chat", response_model=ChatResponse)
async def public_chat(
    request: ChatRequest,
    authorization: str = Header(None)
):
    """
    Public chat endpoint for client websites
    
    Usage:
    ```javascript
    const response = await fetch('https://aurem.live/api/v1/chat', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer sk_aurem_live_xxxxx',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: 'Hello, how can I increase sales?',
        conversation_id: 'conv_123'
      })
    });
    ```
    """
    
    # Validate API key
    key_info = await validate_api_key(authorization)
    
    # Check chat:read scope
    if "chat:read" not in key_info["scopes"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions (requires chat:read scope)")
    
    try:
        # Use existing AUREM chat service
        from services.aurem_commercial.key_service import get_aurem_key_service
        from server import db
        
        # Get business info
        business_id = key_info["business_id"]
        
        # Call AUREM AI (using existing GPT-4o integration)
        try:
            from emergentintegrations.openai_integration import OpenAI
            import os
            
            EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
            client = OpenAI(api_key=EMERGENT_LLM_KEY)
            
            # Build system prompt
            system_prompt = """You are AUREM AI, an intelligent business assistant.
            
You help with:
- Business strategy and growth
- Customer engagement and sales
- Process automation
- Data-driven insights
- Lead qualification

Be concise, professional, and actionable."""

            # Generate conversation ID if not provided
            conversation_id = request.conversation_id or f"conv_{datetime.utcnow().timestamp()}"
            
            # Call GPT-4o
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.message}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            
            # Track usage
            key_service = get_aurem_key_service(db)
            await key_service.track_usage(
                key_id=key_info["key_id"],
                business_id=business_id,
                endpoint="/api/v1/chat",
                tokens_used=response.usage.total_tokens
            )
            
            # Store conversation (optional)
            await db.aurem_conversations.insert_one({
                "conversation_id": conversation_id,
                "business_id": business_id,
                "messages": [
                    {"role": "user", "content": request.message, "timestamp": datetime.utcnow().isoformat()},
                    {"role": "assistant", "content": ai_response, "timestamp": datetime.utcnow().isoformat()}
                ],
                "created_at": datetime.utcnow().isoformat()
            })
            
            return ChatResponse(
                response=ai_response,
                conversation_id=conversation_id,
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as llm_error:
            logger.error(f"[Public API] LLM error: {llm_error}")
            # Fallback response
            return ChatResponse(
                response="I'm here to help with your business needs. Could you provide more details about what you're looking for?",
                conversation_id=request.conversation_id or "conv_fallback",
                timestamp=datetime.utcnow().isoformat()
            )
        
    except Exception as e:
        logger.error(f"[Public API] Chat error: {e}")
        raise HTTPException(status_code=500, detail="Chat service error")


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC LEAD CAPTURE ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/leads", response_model=LeadResponse)
async def capture_lead(
    request: LeadRequest,
    authorization: str = Header(None)
):
    """
    Capture leads from client websites
    
    Usage:
    ```javascript
    await fetch('https://aurem.live/api/v1/leads', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer sk_aurem_live_xxxxx',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name: 'John Doe',
        email: 'john@example.com',
        message: 'Interested in your product'
      })
    });
    ```
    """
    
    # Validate API key
    key_info = await validate_api_key(authorization)
    
    try:
        from server import db
        import uuid
        
        lead_id = str(uuid.uuid4())
        business_id = key_info["business_id"]
        
        # Store lead
        lead_doc = {
            "lead_id": lead_id,
            "business_id": business_id,
            "name": request.name,
            "email": request.email,
            "phone": request.phone,
            "message": request.message,
            "source": request.source,
            "created_at": datetime.utcnow().isoformat(),
            "status": "new"
        }
        
        await db.aurem_leads.insert_one(lead_doc)
        
        # Track usage
        from services.aurem_commercial.key_service import get_aurem_key_service
        key_service = get_aurem_key_service(db)
        await key_service.track_usage(
            key_id=key_info["key_id"],
            business_id=business_id,
            endpoint="/api/v1/leads"
        )
        
        return LeadResponse(
            success=True,
            lead_id=lead_id,
            message="Lead captured successfully"
        )
        
    except Exception as e:
        logger.error(f"[Public API] Lead capture error: {e}")
        raise HTTPException(status_code=500, detail="Lead capture failed")


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def health_check():
    """Public API health check (no auth required)"""
    return {
        "status": "healthy",
        "version": "1.0",
        "timestamp": datetime.utcnow().isoformat()
    }
