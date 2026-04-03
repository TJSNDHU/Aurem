"""
AI Router - Unified routing for AI tasks
Routes to appropriate model based on task type:
- Claude (Anthropic) → skin_advisor, whatsapp_twin, formulation
- OpenRouter free   → admin_summary, email_draft, whatsapp_triage
"""
import os
import logging
import httpx
from typing import Optional, Dict, Any, Literal, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])

# API Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# OpenRouter Config
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://reroots.ca",
    "X-Title": "ReRoots"
}

# Model Routing Table
MODEL_ROUTING = {
    # Claude (Anthropic) - High quality, paid - Customer-facing
    "skin_advisor": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    "whatsapp_twin": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    "formulation": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    
    # OpenRouter Free Models - Internal/Admin tasks
    "admin_hub": {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "admin_summary": {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "cart_copy": {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "email_draft": {"provider": "openrouter", "model": "google/gemma-3-27b-it:free"},
    "whatsapp_triage": {"provider": "openrouter", "model": "mistralai/mistral-small-3.1-24b-instruct:free"},
    "product_copy": {"provider": "openrouter", "model": "google/gemma-3-27b-it:free"},
    "inventory_insight": {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "crm_segment": {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},
}

# Confidence threshold for escalation
TRIAGE_CONFIDENCE_THRESHOLD = 0.7


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class AIRequest(BaseModel):
    task_type: Literal["skin_advisor", "whatsapp_twin", "formulation", "admin_summary", 
                       "admin_hub", "cart_copy", "email_draft", "whatsapp_triage", 
                       "product_copy", "inventory_insight", "crm_segment"]
    prompt: str
    context: Optional[Dict[str, Any]] = None
    max_tokens: int = 1024
    temperature: float = 0.7


class AIResponse(BaseModel):
    response: str
    model_used: str
    provider: str
    confidence: Optional[float] = None
    escalated: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# ANTHROPIC (CLAUDE) CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

async def call_anthropic(prompt: str, model: str, max_tokens: int = 1024, temperature: float = 0.7, system: str = None) -> str:
    """Call Anthropic Claude API"""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="Anthropic API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            headers = {
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            if system:
                payload["system"] = system
            
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Anthropic error: {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Anthropic API error")
            
            data = response.json()
            if "content" in data and len(data["content"]) > 0:
                return data["content"][0].get("text", "")
            raise HTTPException(status_code=500, detail="Empty response from Anthropic")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Anthropic call failed: {e}")
        raise HTTPException(status_code=500, detail=f"Anthropic error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# OPENROUTER CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

async def call_openrouter(prompt: str, model: str, max_tokens: int = 1024, temperature: float = 0.7, system: str = None) -> str:
    """Call OpenRouter API (free models) with retry and fallback"""
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="OpenRouter API key not configured")
    
    # Fallback models to try if primary is rate-limited
    fallback_models = [
        model,
        "google/gemma-3-27b-it:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "openrouter/free"  # Random free model router
    ]
    
    last_error = None
    
    for try_model in fallback_models:
        async with httpx.AsyncClient(timeout=60) as client:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                **OPENROUTER_HEADERS
            }
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": try_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            try:
                response = await client.post(
                    OPENROUTER_BASE_URL,
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0].get("message", {}).get("content")
                        if content:
                            return content
                    logger.warning(f"OpenRouter empty response from {try_model}: {data}")
                    last_error = "Empty response"
                    continue
                elif response.status_code == 429:
                    logger.warning(f"OpenRouter rate limited on {try_model}, trying fallback...")
                    last_error = f"Rate limited on {try_model}"
                    continue
                else:
                    logger.error(f"OpenRouter error ({try_model}): {response.text}")
                    last_error = response.text
                    continue
            except Exception as e:
                logger.error(f"OpenRouter request failed ({try_model}): {e}")
                last_error = str(e)
                continue
    
    raise HTTPException(status_code=503, detail=f"OpenRouter API error: {last_error}")


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED AI ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/route", response_model=AIResponse)
async def route_ai_request(request: AIRequest):
    """
    Route AI request to appropriate model based on task type.
    Automatically escalates to Claude if triage confidence is low.
    """
    routing = MODEL_ROUTING.get(request.task_type)
    if not routing:
        raise HTTPException(status_code=400, detail=f"Unknown task type: {request.task_type}")
    
    provider = routing["provider"]
    model = routing["model"]
    
    # Build system prompt based on task type
    system_prompts = {
        "skin_advisor": "You are an expert skincare advisor for ReRoots, a Canadian biotech skincare brand specializing in PDRN technology. Provide personalized, science-backed skincare advice.",
        "whatsapp_twin": "You are the AI assistant for ReRoots skincare on WhatsApp. Be friendly, helpful, and knowledgeable about our PDRN-based products. Keep responses concise for mobile.",
        "formulation": "You are a skincare formulation expert. Analyze ingredients, suggest improvements, and explain the science behind skincare formulations.",
        "admin_summary": "You are a business analyst. Summarize data clearly and concisely, highlighting key insights and actionable recommendations.",
        "email_draft": "You are a marketing copywriter for ReRoots luxury skincare. Write elegant, persuasive email copy that matches our premium brand voice.",
        "whatsapp_triage": "You are a customer service triage agent. Analyze the customer message and determine: 1) Category (order, product, return, other), 2) Urgency (low/medium/high), 3) Confidence score (0-1). Respond in JSON format.",
        "inventory_insight": "You are an inventory analyst. Analyze stock levels, identify trends, and suggest reorder quantities based on sales velocity.",
        "crm_segment": "You are a CRM strategist. Analyze customer data and suggest segments for targeted marketing campaigns."
    }
    
    system = system_prompts.get(request.task_type, "You are a helpful assistant.")
    
    # Add context to prompt if provided
    full_prompt = request.prompt
    if request.context:
        context_str = "\n".join([f"{k}: {v}" for k, v in request.context.items()])
        full_prompt = f"Context:\n{context_str}\n\nRequest:\n{request.prompt}"
    
    try:
        if provider == "anthropic":
            response_text = await call_anthropic(full_prompt, model, request.max_tokens, request.temperature, system)
        else:
            response_text = await call_openrouter(full_prompt, model, request.max_tokens, request.temperature, system)
        
        # Special handling for triage - check confidence and escalate if needed
        confidence = None
        escalated = False
        
        if request.task_type == "whatsapp_triage":
            try:
                import json
                triage_result = json.loads(response_text)
                confidence = triage_result.get("confidence", 1.0)
                
                # Escalate to Claude if confidence is low
                if confidence < TRIAGE_CONFIDENCE_THRESHOLD:
                    logger.info(f"Triage confidence {confidence} < {TRIAGE_CONFIDENCE_THRESHOLD}, escalating to Claude")
                    response_text = await call_anthropic(
                        full_prompt, 
                        MODEL_ROUTING["whatsapp_twin"]["model"],
                        request.max_tokens,
                        request.temperature,
                        system_prompts["whatsapp_twin"]
                    )
                    escalated = True
                    model = MODEL_ROUTING["whatsapp_twin"]["model"]
                    provider = "anthropic"
            except json.JSONDecodeError:
                pass
        
        return AIResponse(
            response=response_text,
            model_used=model,
            provider=provider,
            confidence=confidence,
            escalated=escalated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI routing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE ENDPOINTS FOR ADMIN HUB
# ═══════════════════════════════════════════════════════════════════════════════

class SummaryRequest(BaseModel):
    data: Dict[str, Any]
    summary_type: Literal["sales", "inventory", "customers"]


@router.post("/admin/summary")
async def generate_admin_summary(request: SummaryRequest):
    """Generate AI summary for admin dashboard"""
    try:
        prompts = {
            "sales": f"Analyze this sales data and provide a brief summary with key insights:\n{request.data}",
            "inventory": f"Analyze this inventory data and provide recommendations:\n{request.data}",
            "customers": f"Analyze this customer data and suggest marketing segments:\n{request.data}"
        }
        
        ai_request = AIRequest(
            task_type="admin_summary" if request.summary_type == "sales" else 
                      "inventory_insight" if request.summary_type == "inventory" else "crm_segment",
            prompt=prompts[request.summary_type],
            max_tokens=512,
            temperature=0.5
        )
        
        return await route_ai_request(ai_request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class EmailDraftRequest(BaseModel):
    email_type: Literal["promo", "announcement", "followup"]
    context: Dict[str, Any]


@router.post("/admin/email-draft")
async def generate_email_draft(request: EmailDraftRequest):
    """Generate email draft for marketing"""
    try:
        prompts = {
            "promo": f"Write a promotional email for ReRoots skincare with these details:\n{request.context}",
            "announcement": f"Write an announcement email with these details:\n{request.context}",
            "followup": f"Write a customer follow-up email with these details:\n{request.context}"
        }
        
        ai_request = AIRequest(
            task_type="email_draft",
            prompt=prompts[request.email_type],
            max_tokens=1024,
            temperature=0.7
        )
        
        return await route_ai_request(ai_request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email draft error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class WhatsAppTriageRequest(BaseModel):
    message: str
    customer_id: Optional[str] = None
    order_history: Optional[list] = None


@router.post("/whatsapp/triage")
async def triage_whatsapp_message(request: WhatsAppTriageRequest):
    """
    Triage incoming WhatsApp message.
    Returns category, urgency, suggested response.
    Escalates to Claude if confidence < 0.7
    """
    try:
        context = {}
        if request.customer_id:
            context["customer_id"] = request.customer_id
        if request.order_history:
            context["recent_orders"] = request.order_history
        
        ai_request = AIRequest(
            task_type="whatsapp_triage",
            prompt=f"Triage this customer message:\n\n{request.message}",
            context=context if context else None,
            max_tokens=512,
            temperature=0.3
        )
        
        return await route_ai_request(ai_request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WhatsApp triage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN AI HUB - General query endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class AdminAIQueryRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None


@router.post("/admin/ai/query")
async def admin_ai_query(request: AdminAIQueryRequest):
    """
    General AI query endpoint for Admin AI Hub.
    Uses free OpenRouter models for cost efficiency.
    """
    try:
        ai_request = AIRequest(
            task_type="admin_hub",
            prompt=request.query,
            context=request.context,
            max_tokens=1024,
            temperature=0.5
        )
        
        return await route_ai_request(ai_request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin AI query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT COPY GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ProductCopyRequest(BaseModel):
    product_name: str
    ingredients: Optional[List[str]] = None
    benefits: Optional[List[str]] = None
    target_audience: Optional[str] = None


@router.post("/admin/product-copy")
async def generate_product_copy(request: ProductCopyRequest):
    """Generate product description copy using free model"""
    try:
        prompt = f"""Write a compelling product description for:
Product: {request.product_name}
Ingredients: {', '.join(request.ingredients) if request.ingredients else 'Not specified'}
Benefits: {', '.join(request.benefits) if request.benefits else 'Not specified'}
Target Audience: {request.target_audience or 'Skincare enthusiasts'}

Write in ReRoots brand voice - luxury, scientific, results-focused."""
        
        ai_request = AIRequest(
            task_type="product_copy",
            prompt=prompt,
            max_tokens=512,
            temperature=0.7
        )
        
        return await route_ai_request(ai_request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Product copy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# SKIN ADVISOR CHAT - PWA Customer-facing chatbot
# ═══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


@router.post("/chat")
async def skin_advisor_chat(request: ChatRequest):
    """
    Skin Advisor chat endpoint for PWA.
    Uses OpenRouter with fallback for reliability.
    """
    try:
        # Build user context
        user_name = request.context.get("user", "Guest") if request.context else "Guest"
        skin_type = request.context.get("skinType", "combination") if request.context else "combination"
        tier = request.context.get("tier", "Silver") if request.context else "Silver"
        
        system_prompt = f"""CRITICAL INSTRUCTION: You MUST always respond in English only, regardless of what language the user writes in. Never switch languages.

You are the ReRoots AI Skin Advisor - an expert cosmetic chemist specializing in the AURA-GEN Series with PDRN technology.

USER PROFILE:
- Name: {user_name}
- Skin Type: {skin_type}
- Membership: {tier}

PRODUCT KNOWLEDGE:
- AURA-GEN PDRN + TXA Serum ($99): 5% TXA, 2% PDRN, Argireline - brightening, anti-aging
- AURA-GEN Accelerator Cream ($74.99): Rich moisturizer with PDRN
- AURA-GEN Recovery Complex ($99.99): 17% active recovery complex

GUIDELINES:
1. Be knowledgeable, friendly, and professional
2. Provide science-backed skincare advice
3. Recommend products when relevant
4. Keep responses concise (2-3 sentences max)
5. Use proper skincare terminology
"""
        
        response_text = await call_openrouter(
            prompt=request.message,
            model="google/gemini-2.0-flash-lite-001",
            max_tokens=300,
            temperature=0.7,
            system=system_prompt
        )
        
        return {"response": response_text}
        
    except HTTPException as e:
        logger.error(f"Skin advisor chat error: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Skin advisor chat error: {e}")
        raise HTTPException(status_code=500, detail="Connection interrupted. Please retry.")
