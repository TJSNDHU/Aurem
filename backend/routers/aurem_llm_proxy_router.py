"""
AUREM LLM Proxy Router
OpenAI-compatible API that validates sk_aurem_ keys and proxies to Emergent

Endpoints:
- POST /api/aurem-llm/chat/completions - Chat completion (OpenAI-compatible)
- POST /api/aurem-llm/completions - Text completion
- GET /api/aurem-llm/models - List available models

Security:
- Client sends: Authorization: Bearer sk_aurem_live_xxx
- Backend validates AUREM key
- Backend attaches Emergent key (server-to-server only)
- Usage tracked for billing
"""

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

router = APIRouter(prefix="/api/aurem-llm", tags=["AUREM LLM Proxy"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


# OpenAI-compatible request models
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "gpt-4o-mini"
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class CompletionRequest(BaseModel):
    model: str = "gpt-4o-mini"
    prompt: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None


async def validate_aurem_key(authorization: str) -> Dict[str, Any]:
    """
    Extract and validate AUREM API key from Authorization header.
    
    Expected format: Bearer sk_aurem_live_xxx or Bearer sk_aurem_test_xxx
    """
    if not authorization:
        raise HTTPException(401, "Authorization header required")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization format. Use: Bearer sk_aurem_xxx")
    
    api_key = authorization[7:]  # Remove "Bearer " prefix
    
    if not (api_key.startswith("sk_aurem_live_") or api_key.startswith("sk_aurem_test_")):
        raise HTTPException(401, "Invalid API key format. Must start with sk_aurem_live_ or sk_aurem_test_")
    
    from services.aurem_commercial.key_service import get_aurem_key_service
    
    key_service = get_aurem_key_service(get_db())
    key_info = await key_service.validate_key(api_key)
    
    if not key_info:
        raise HTTPException(401, "Invalid or expired API key")
    
    return key_info


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: str = Header(..., alias="Authorization")
):
    """
    OpenAI-compatible chat completions endpoint.
    
    Usage:
    ```
    curl -X POST https://your-domain.com/api/aurem-llm/chat/completions \
      -H "Authorization: Bearer sk_aurem_live_xxx" \
      -H "Content-Type: application/json" \
      -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]}'
    ```
    """
    # Validate AUREM key
    key_info = await validate_aurem_key(authorization)
    
    from services.aurem_commercial.llm_proxy import get_llm_proxy
    
    proxy = get_llm_proxy(get_db())
    
    try:
        result = await proxy.chat_completion(
            aurem_key_info=key_info,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[LLMProxy] Chat completion failed: {e}")
        raise HTTPException(500, f"LLM request failed: {str(e)}")


@router.post("/completions")
async def completions(
    request: CompletionRequest,
    authorization: str = Header(..., alias="Authorization")
):
    """
    Text completion endpoint (converts to chat format internally).
    """
    # Validate AUREM key
    key_info = await validate_aurem_key(authorization)
    
    from services.aurem_commercial.llm_proxy import get_llm_proxy
    
    proxy = get_llm_proxy(get_db())
    
    try:
        result = await proxy.chat_completion(
            aurem_key_info=key_info,
            messages=[{"role": "user", "content": request.prompt}],
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # Convert to completion format
        return {
            "id": result["id"],
            "object": "text_completion",
            "created": result["created"],
            "model": result["model"],
            "choices": [{
                "text": result["choices"][0]["message"]["content"],
                "index": 0,
                "finish_reason": "stop"
            }],
            "usage": result["usage"]
        }
        
    except Exception as e:
        logger.error(f"[LLMProxy] Completion failed: {e}")
        raise HTTPException(500, f"LLM request failed: {str(e)}")


@router.get("/models")
async def list_models(authorization: str = Header(..., alias="Authorization")):
    """
    List available models.
    """
    # Validate AUREM key
    await validate_aurem_key(authorization)
    
    return {
        "object": "list",
        "data": [
            {"id": "gpt-4o", "object": "model", "owned_by": "aurem"},
            {"id": "gpt-4o-mini", "object": "model", "owned_by": "aurem"},
            {"id": "gpt-4-turbo", "object": "model", "owned_by": "aurem"},
            {"id": "claude-3-sonnet", "object": "model", "owned_by": "aurem"},
            {"id": "claude-3-haiku", "object": "model", "owned_by": "aurem"}
        ]
    }


@router.get("/health")
async def health():
    """Health check (no auth required)"""
    import os
    emergent_configured = bool(os.environ.get("EMERGENT_LLM_KEY"))
    
    return {
        "status": "healthy" if emergent_configured else "degraded",
        "service": "aurem-llm-proxy",
        "emergent_configured": emergent_configured
    }
