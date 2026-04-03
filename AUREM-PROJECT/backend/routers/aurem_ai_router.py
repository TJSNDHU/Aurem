"""
AUREM AI Router — Completely Separate from ReRoots
Brand: AUREM by Polaris Built Inc.
Products: OROÉ only
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import AUREM-specific prompt (separate from any ReRoots prompts)
from utils.aurem_prompt import AUREM_SYSTEM_PROMPT, AUREM_WELCOME_MESSAGE, QUICK_OPTIONS

# Import Emergent LLM integration
from emergentintegrations.llm.chat import LlmChat, UserMessage

router = APIRouter(prefix="/api/aurem-ai", tags=["AUREM AI"])
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    response: str
    
class WelcomeResponse(BaseModel):
    welcome_message: str
    quick_options: list

# ══════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.get("/welcome")
async def get_welcome():
    """Get AUREM AI welcome message and quick options"""
    return WelcomeResponse(
        welcome_message=AUREM_WELCOME_MESSAGE,
        quick_options=QUICK_OPTIONS
    )

@router.post("/chat")
async def chat(request: ChatRequest):
    """AUREM AI Chat endpoint — uses Emergent LLM integration with Claude"""
    try:
        # Get Emergent LLM key
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        
        if not api_key:
            logger.error("[AUREM AI] No EMERGENT_LLM_KEY found")
            return ChatResponse(
                response="I'm currently in maintenance mode. Please try again shortly, or contact support@polarisbuilt.com for immediate assistance."
            )
        
        logger.info(f"[AUREM AI] Processing chat request with session: {request.session_id}")
        
        # Initialize chat with Emergent integration
        chat_instance = LlmChat(
            api_key=api_key,
            session_id=f"aurem-{request.session_id}",
            system_message=AUREM_SYSTEM_PROMPT
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        # Build the message with history context if needed
        message_text = request.message
        if request.history and len(request.history) > 0:
            # Add context from recent history
            context_parts = []
            for msg in request.history[-6:]:  # Last 6 messages for context
                role = "Customer" if msg.role == "user" else "AUREM"
                context_parts.append(f"{role}: {msg.content}")
            
            if context_parts:
                message_text = f"Previous conversation:\n{chr(10).join(context_parts)}\n\nCustomer's current message: {request.message}"
        
        # Create user message
        user_message = UserMessage(text=message_text)
        
        # Send message and get response
        response = await chat_instance.send_message(user_message)
        
        logger.info("[AUREM AI] Response generated successfully")
        return ChatResponse(response=response)
            
    except Exception as e:
        logger.error(f"[AUREM AI] Chat error: {str(e)}")
        return ChatResponse(
            response="I'm experiencing a momentary pause. Please try again, or reach out to support@polarisbuilt.com."
        )

@router.get("/health")
async def health():
    """Health check for AUREM AI"""
    return {
        "status": "operational",
        "brand": "AUREM",
        "company": "Polaris Built Inc.",
        "product_line": "OROÉ"
    }
