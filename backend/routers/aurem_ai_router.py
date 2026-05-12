"""
AUREM AI Router — Completely Separate from ReRoots
Brand: AUREM by Polaris Built Inc.
Products: OROÉ only
"""

import hashlib
import logging
import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Load environment variables
load_dotenv(override=False)

# Import AUREM-specific prompt (separate from any ReRoots prompts)
from utils.aurem_prompt import AUREM_SYSTEM_PROMPT, AUREM_WELCOME_MESSAGE, QUICK_OPTIONS

# Import Emergent LLM integration
from emergentintegrations.llm.chat import LlmChat, UserMessage

# iter 322eb — wire llm_response_cache into the customer-facing AUREM AI
# chat. Caches Claude responses keyed on the normalized user question so
# repeated FAQ-style asks ("what does AUREM do", "pricing", "how does
# ORA work") hit the cache instead of burning Emergent LLM key budget.
from services.llm_response_cache import cache_get, cache_put

router = APIRouter(prefix="/api/aurem-ai", tags=["AUREM AI"])
logger = logging.getLogger(__name__)

# Module-level db handle — wired from registry.set_db() at startup.
_db = None


def set_db(db):
    """Inject the live Motor handle so the cache layer can read/write."""
    global _db
    _db = db


_CACHE_SCOPE = "aurem_ai_chat"
# Bump this token if AUREM_SYSTEM_PROMPT changes substantively — forces a
# cache miss on the new prompt and re-learns fresh responses.
_PROMPT_SEED = "v1"


def _normalize_for_cache(text: str) -> str:
    """Lower, strip punctuation, collapse whitespace, cap length.
    Same question phrased slightly differently maps to the same key."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t[:500]


def _cache_signature(message: str) -> str:
    """Deterministic 16-char hex of the normalized message."""
    norm = _normalize_for_cache(message)
    if not norm:
        return ""
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]

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
    """AUREM AI Chat endpoint — uses Emergent LLM integration with Claude.
    Caches identical FAQ-style messages (no history) for 24h to cut LLM cost."""
    try:
        # Get Emergent LLM key
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        
        if not api_key:
            logger.error("[AUREM AI] No EMERGENT_LLM_KEY found")
            return ChatResponse(
                response="I'm currently in maintenance mode. Please try again shortly, or contact support@polarisbuilt.com for immediate assistance."
            )
        
        logger.info(f"[AUREM AI] Processing chat request with session: {request.session_id}")

        # ── Cache lookup (only for stateless asks — history makes replies context-bound) ──
        has_history = bool(request.history and len(request.history) > 0)
        sig = _cache_signature(request.message) if not has_history else ""
        if sig and _db is not None:
            try:
                cached = await cache_get(_db, scope=_CACHE_SCOPE, signature=sig, prompt_seed=_PROMPT_SEED)
                if cached and isinstance(cached, dict) and cached.get("response"):
                    logger.info(f"[AUREM AI] cache HIT sig={sig[:8]} — Claude call skipped")
                    return ChatResponse(response=cached["response"])
            except Exception as ce:
                # Cache must never break the chat — fall through to live call.
                logger.debug(f"[AUREM AI] cache_get failed: {ce}")
        
        # Initialize chat with Emergent integration
        chat_instance = LlmChat(
            api_key=api_key,
            session_id=f"aurem-{request.session_id}",
            system_message=AUREM_SYSTEM_PROMPT
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        # Build the message with history context if needed
        message_text = request.message
        if has_history:
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

        # ── Cache write (only on success + no history + non-empty reply) ──
        if sig and _db is not None and response:
            try:
                await cache_put(
                    _db,
                    scope=_CACHE_SCOPE,
                    signature=sig,
                    payload={"response": response},
                    prompt_seed=_PROMPT_SEED,
                    ttl_hours=24,
                )
                logger.debug(f"[AUREM AI] cache PUT sig={sig[:8]}")
            except Exception as ce:
                logger.debug(f"[AUREM AI] cache_put failed: {ce}")

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
