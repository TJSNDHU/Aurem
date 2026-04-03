"""
ReRoots AI OpenRouter - Unified LLM Routing with Fallback
Multi-model access with automatic failover and cost optimization
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import asyncio
import httpx
import json

router = APIRouter(prefix="/api/llm-router", tags=["llm-router"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# LLM MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

LLM_MODELS = {
    # OpenAI Models
    "gpt-5.2": {
        "provider": "openai",
        "model_id": "gpt-5.2",
        "name": "GPT-5.2",
        "cost_per_1k_input": 0.01,
        "cost_per_1k_output": 0.03,
        "max_tokens": 128000,
        "speed": "medium",
        "capabilities": ["text", "code", "reasoning", "vision"]
    },
    "gpt-4o": {
        "provider": "openai",
        "model_id": "gpt-4o",
        "name": "GPT-4o",
        "cost_per_1k_input": 0.005,
        "cost_per_1k_output": 0.015,
        "max_tokens": 128000,
        "speed": "fast",
        "capabilities": ["text", "code", "vision", "audio"]
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "model_id": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "cost_per_1k_input": 0.00015,
        "cost_per_1k_output": 0.0006,
        "max_tokens": 128000,
        "speed": "very_fast",
        "capabilities": ["text", "code"]
    },
    # Anthropic Models
    "claude-sonnet-4.5": {
        "provider": "anthropic",
        "model_id": "claude-sonnet-4.5",
        "name": "Claude Sonnet 4.5",
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
        "max_tokens": 200000,
        "speed": "medium",
        "capabilities": ["text", "code", "reasoning", "vision"]
    },
    "claude-haiku-4.5": {
        "provider": "anthropic",
        "model_id": "claude-haiku-4.5",
        "name": "Claude Haiku 4.5",
        "cost_per_1k_input": 0.0008,
        "cost_per_1k_output": 0.004,
        "max_tokens": 200000,
        "speed": "very_fast",
        "capabilities": ["text", "code"]
    },
    # Google Models
    "gemini-3-flash": {
        "provider": "google",
        "model_id": "gemini-3-flash",
        "name": "Gemini 3 Flash",
        "cost_per_1k_input": 0.0001,
        "cost_per_1k_output": 0.0004,
        "max_tokens": 1000000,
        "speed": "very_fast",
        "capabilities": ["text", "code", "vision"]
    },
    "gemini-3-pro": {
        "provider": "google",
        "model_id": "gemini-3-pro",
        "name": "Gemini 3 Pro",
        "cost_per_1k_input": 0.00125,
        "cost_per_1k_output": 0.005,
        "max_tokens": 2000000,
        "speed": "medium",
        "capabilities": ["text", "code", "reasoning", "vision"]
    },
    # Mistral Models
    "mistral-large": {
        "provider": "mistral",
        "model_id": "mistral-large-latest",
        "name": "Mistral Large",
        "cost_per_1k_input": 0.002,
        "cost_per_1k_output": 0.006,
        "max_tokens": 128000,
        "speed": "fast",
        "capabilities": ["text", "code", "reasoning"]
    }
}

# Routing strategies
ROUTING_STRATEGIES = {
    "cost": "Select cheapest model that meets requirements",
    "speed": "Select fastest model",
    "quality": "Select highest quality model",
    "balanced": "Balance cost, speed, and quality",
    "fallback": "Try primary, fallback to secondary on failure"
}

# Model fallback chains
FALLBACK_CHAINS = {
    "default": ["gpt-5.2", "claude-sonnet-4.5", "gemini-3-pro"],
    "fast": ["gpt-4o-mini", "gemini-3-flash", "claude-haiku-4.5"],
    "reasoning": ["claude-sonnet-4.5", "gpt-5.2", "gemini-3-pro"],
    "vision": ["gpt-4o", "claude-sonnet-4.5", "gemini-3-flash"],
    "budget": ["gemini-3-flash", "gpt-4o-mini", "claude-haiku-4.5"]
}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class LLMRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = None  # Specific model or None for auto-routing
    strategy: str = "balanced"  # cost, speed, quality, balanced, fallback
    fallback_chain: Optional[str] = None  # default, fast, reasoning, vision, budget
    max_tokens: int = 4096
    temperature: float = 0.7
    required_capabilities: Optional[List[str]] = None
    max_cost: Optional[float] = None  # Max cost in dollars

class LLMResponse(BaseModel):
    response: str
    model_used: str
    provider: str
    tokens_input: int
    tokens_output: int
    cost: float
    latency_ms: int
    fallbacks_tried: List[str]


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

def select_model_by_strategy(strategy: str, required_capabilities: List[str] = None, max_cost: float = None) -> str:
    """Select best model based on routing strategy"""
    candidates = list(LLM_MODELS.keys())
    
    # Filter by required capabilities
    if required_capabilities:
        candidates = [
            m for m in candidates 
            if all(cap in LLM_MODELS[m]["capabilities"] for cap in required_capabilities)
        ]
    
    # Filter by max cost
    if max_cost:
        candidates = [
            m for m in candidates 
            if LLM_MODELS[m]["cost_per_1k_output"] * 4 <= max_cost  # Rough estimate
        ]
    
    if not candidates:
        return "gpt-4o-mini"  # Fallback to cheapest
    
    if strategy == "cost":
        return min(candidates, key=lambda m: LLM_MODELS[m]["cost_per_1k_output"])
    elif strategy == "speed":
        speed_order = {"very_fast": 0, "fast": 1, "medium": 2, "slow": 3}
        return min(candidates, key=lambda m: speed_order.get(LLM_MODELS[m]["speed"], 2))
    elif strategy == "quality":
        # Prefer models with more capabilities and higher cost (proxy for quality)
        return max(candidates, key=lambda m: (len(LLM_MODELS[m]["capabilities"]), LLM_MODELS[m]["cost_per_1k_output"]))
    else:  # balanced
        # Score based on capabilities, inverse cost, and speed
        def score(m):
            caps = len(LLM_MODELS[m]["capabilities"])
            cost = 1 / (LLM_MODELS[m]["cost_per_1k_output"] + 0.001)
            speed_score = {"very_fast": 4, "fast": 3, "medium": 2, "slow": 1}.get(LLM_MODELS[m]["speed"], 2)
            return caps * 2 + cost * 0.1 + speed_score
        return max(candidates, key=score)


async def call_llm(model_id: str, messages: List[Dict], max_tokens: int, temperature: float) -> Dict:
    """Call specific LLM model"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise Exception("LLM API key not configured")
    
    model_info = LLM_MODELS.get(model_id, LLM_MODELS["gpt-4o-mini"])
    provider = model_info["provider"]
    
    import secrets
    import time
    
    start_time = time.time()
    
    chat = LlmChat(
        api_key=api_key,
        session_id=f"router_{secrets.token_hex(6)}",
        system_message=messages[0]["content"] if messages and messages[0].get("role") == "system" else None
    ).with_model(provider, model_info["model_id"])
    
    # Get user messages
    user_messages = [m for m in messages if m.get("role") == "user"]
    if user_messages:
        response = await chat.send_message(UserMessage(text=user_messages[-1]["content"]))
    else:
        response = "No user message provided"
    
    latency = int((time.time() - start_time) * 1000)
    
    # Estimate tokens (rough)
    input_tokens = sum(len(m.get("content", "").split()) * 1.3 for m in messages)
    output_tokens = len(response.split()) * 1.3
    
    cost = (input_tokens / 1000 * model_info["cost_per_1k_input"] + 
            output_tokens / 1000 * model_info["cost_per_1k_output"])
    
    return {
        "response": response,
        "model_used": model_id,
        "provider": provider,
        "tokens_input": int(input_tokens),
        "tokens_output": int(output_tokens),
        "cost": round(cost, 6),
        "latency_ms": latency
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/models")
async def get_available_models():
    """Get all available LLM models"""
    return {
        "models": LLM_MODELS,
        "strategies": ROUTING_STRATEGIES,
        "fallback_chains": FALLBACK_CHAINS
    }


@router.post("/chat")
async def routed_chat(data: LLMRequest):
    """Send message with intelligent model routing and fallback"""
    fallbacks_tried = []
    
    # Determine model(s) to try
    if data.model:
        models_to_try = [data.model]
    elif data.fallback_chain:
        models_to_try = FALLBACK_CHAINS.get(data.fallback_chain, FALLBACK_CHAINS["default"])
    else:
        primary_model = select_model_by_strategy(
            data.strategy,
            data.required_capabilities,
            data.max_cost
        )
        models_to_try = [primary_model] + [m for m in FALLBACK_CHAINS["default"] if m != primary_model]
    
    last_error = None
    
    for model_id in models_to_try:
        try:
            result = await call_llm(
                model_id,
                data.messages,
                data.max_tokens,
                data.temperature
            )
            result["fallbacks_tried"] = fallbacks_tried
            
            # Log successful call
            await db.llm_router_logs.insert_one({
                "model_used": model_id,
                "strategy": data.strategy,
                "fallbacks_tried": fallbacks_tried,
                "tokens_input": result["tokens_input"],
                "tokens_output": result["tokens_output"],
                "cost": result["cost"],
                "latency_ms": result["latency_ms"],
                "success": True,
                "timestamp": datetime.now(timezone.utc)
            })
            
            return result
            
        except Exception as e:
            last_error = str(e)
            fallbacks_tried.append(model_id)
            continue
    
    # All models failed
    raise HTTPException(
        status_code=500,
        detail=f"All models failed. Last error: {last_error}. Tried: {fallbacks_tried}"
    )


@router.post("/chat/stream")
async def routed_chat_stream(data: LLMRequest):
    """Streaming chat with model routing (returns generator info)"""
    # For now, return non-streaming response
    # In production, implement SSE streaming
    return await routed_chat(data)


@router.get("/recommend")
async def recommend_model(
    task_type: str,  # reasoning, coding, vision, fast_response, budget
    input_length: int = 1000,
    output_length: int = 500
):
    """Get model recommendation based on task requirements"""
    recommendations = {
        "reasoning": {
            "primary": "claude-sonnet-4.5",
            "fallback": "gpt-5.2",
            "reason": "Best for complex reasoning and analysis"
        },
        "coding": {
            "primary": "claude-sonnet-4.5",
            "fallback": "gpt-5.2",
            "reason": "Best for code generation and debugging"
        },
        "vision": {
            "primary": "gpt-4o",
            "fallback": "claude-sonnet-4.5",
            "reason": "Best multimodal performance"
        },
        "fast_response": {
            "primary": "gemini-3-flash",
            "fallback": "gpt-4o-mini",
            "reason": "Lowest latency for quick responses"
        },
        "budget": {
            "primary": "gemini-3-flash",
            "fallback": "gpt-4o-mini",
            "reason": "Lowest cost per token"
        }
    }
    
    rec = recommendations.get(task_type, recommendations["reasoning"])
    
    # Calculate estimated cost
    primary = LLM_MODELS[rec["primary"]]
    estimated_cost = (
        input_length / 1000 * primary["cost_per_1k_input"] +
        output_length / 1000 * primary["cost_per_1k_output"]
    )
    
    return {
        "recommendation": rec,
        "estimated_cost": round(estimated_cost, 6),
        "model_details": primary
    }


@router.get("/analytics")
async def get_routing_analytics(days: int = 7):
    """Get LLM routing analytics"""
    from datetime import timedelta
    
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Usage by model
    model_usage = await db.llm_router_logs.aggregate([
        {"$match": {"timestamp": {"$gte": since}}},
        {"$group": {
            "_id": "$model_used",
            "calls": {"$sum": 1},
            "total_cost": {"$sum": "$cost"},
            "avg_latency": {"$avg": "$latency_ms"},
            "total_tokens": {"$sum": {"$add": ["$tokens_input", "$tokens_output"]}}
        }},
        {"$sort": {"calls": -1}}
    ]).to_list(20)
    
    # Total stats
    total_calls = await db.llm_router_logs.count_documents({"timestamp": {"$gte": since}})
    total_cost = await db.llm_router_logs.aggregate([
        {"$match": {"timestamp": {"$gte": since}}},
        {"$group": {"_id": None, "total": {"$sum": "$cost"}}}
    ]).to_list(1)
    
    # Fallback rate
    with_fallbacks = await db.llm_router_logs.count_documents({
        "timestamp": {"$gte": since},
        "fallbacks_tried": {"$ne": []}
    })
    
    return {
        "period_days": days,
        "total_calls": total_calls,
        "total_cost": total_cost[0]["total"] if total_cost else 0,
        "fallback_rate": round(with_fallbacks / max(total_calls, 1) * 100, 2),
        "usage_by_model": {m["_id"]: m for m in model_usage}
    }
