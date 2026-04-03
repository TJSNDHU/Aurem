"""
AUREM Commercial Platform - Redis Router
API endpoints for Redis memory, caching, and WebSocket

Endpoints:
- WS /api/aurem-ws/{business_id} - WebSocket for real-time updates
- GET /api/aurem-redis/memory/{business_id} - Memory stats
- GET /api/aurem-redis/cache/{business_id} - Cache stats
- GET /api/aurem-redis/rate-limit/{business_id} - Rate limit status
- GET /api/aurem-redis/activities/{business_id} - Get recent activities
- POST /api/aurem-redis/activity/{business_id} - Log activity
"""

import logging
from typing import Optional, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/aurem-redis", tags=["AUREM Redis"])

logger = logging.getLogger(__name__)


class ActivityRequest(BaseModel):
    activity_type: str
    description: str
    metadata: Optional[dict] = None


class StateRequest(BaseModel):
    key: str
    value: Any


# ==================== WEBSOCKET ====================

@router.websocket("/ws/{business_id}")
async def websocket_endpoint(websocket: WebSocket, business_id: str):
    """WebSocket endpoint for real-time dashboard updates"""
    from services.aurem_commercial.websocket_hub import get_websocket_hub
    
    hub = await get_websocket_hub()
    await hub.register(websocket, business_id)
    
    try:
        while True:
            # Keep connection alive, receive any client messages
            data = await websocket.receive_json()
            
            # Handle ping/pong
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
            # Handle state sync requests
            elif data.get("type") == "sync_state":
                from services.aurem_commercial.redis_memory import get_aurem_memory
                memory = await get_aurem_memory()
                state_key = data.get("key")
                if state_key:
                    value = await memory.get_state(business_id, state_key)
                    await websocket.send_json({
                        "type": "state_sync",
                        "key": state_key,
                        "value": value
                    })
    
    except WebSocketDisconnect:
        await hub.unregister(websocket, business_id)
    except Exception as e:
        logger.error(f"[WebSocket] Error: {e}")
        await hub.unregister(websocket, business_id)


# ==================== MEMORY ENDPOINTS ====================

@router.get("/memory/{business_id}")
async def get_memory_stats(business_id: str):
    """Get Redis memory stats for a business"""
    from services.aurem_commercial.redis_memory import get_aurem_memory
    
    memory = await get_aurem_memory()
    if not memory.available:
        return {"status": "unavailable", "message": "Redis not connected"}
    
    # Get conversation context count
    try:
        pattern = f"aurem:biz_{business_id}:conv:*"
        keys = await memory._redis.keys(pattern)
        conv_count = len(keys)
    except Exception:
        conv_count = 0
    
    profile = await memory.get_business_profile(business_id)
    
    return {
        "status": "connected",
        "business_id": business_id,
        "active_conversations": conv_count,
        "profile_cached": profile is not None
    }


@router.get("/context/{business_id}/{conversation_id}")
async def get_conversation_context(business_id: str, conversation_id: str):
    """Get conversation context from Redis"""
    from services.aurem_commercial.redis_memory import get_aurem_memory
    
    memory = await get_aurem_memory()
    context = await memory.get_context(business_id, conversation_id)
    return context


# ==================== CACHE ENDPOINTS ====================

@router.get("/cache/{business_id}")
async def get_cache_stats(business_id: str):
    """Get semantic cache stats"""
    from services.aurem_commercial.semantic_cache import get_semantic_cache
    
    cache = await get_semantic_cache()
    return await cache.get_stats(business_id)


@router.post("/cache/{business_id}/invalidate")
async def invalidate_cache(business_id: str, query: Optional[str] = None):
    """Invalidate cache entries"""
    from services.aurem_commercial.semantic_cache import get_semantic_cache
    
    cache = await get_semantic_cache()
    await cache.invalidate(business_id, query)
    return {"success": True, "invalidated": "all" if not query else "single"}


# ==================== RATE LIMIT ENDPOINTS ====================

@router.get("/rate-limit/{business_id}")
async def get_rate_limit_status(
    business_id: str,
    channel: str = Query("messages"),
    plan: str = Query("trial")
):
    """Check rate limit status"""
    from services.aurem_commercial.rate_limiter import get_rate_limiter
    
    limiter = await get_rate_limiter()
    return await limiter.check_limit(business_id, channel, plan)


@router.get("/rate-limit/{business_id}/usage")
async def get_rate_limit_usage(business_id: str):
    """Get current usage across all channels"""
    from services.aurem_commercial.rate_limiter import get_rate_limiter
    
    limiter = await get_rate_limiter()
    return await limiter.get_usage(business_id)


# ==================== ACTIVITY ENDPOINTS ====================

@router.get("/activities/{business_id}")
async def get_activities(business_id: str, limit: int = Query(20, le=50)):
    """Get recent activities for dashboard"""
    from services.aurem_commercial.redis_memory import get_aurem_memory
    
    memory = await get_aurem_memory()
    activities = await memory.get_activities(business_id, limit)
    return {"activities": activities, "count": len(activities)}


@router.post("/activity/{business_id}")
async def log_activity(business_id: str, activity: ActivityRequest):
    """Log an activity (for testing/manual triggers)"""
    from services.aurem_commercial.redis_memory import get_aurem_memory
    from services.aurem_commercial.websocket_hub import get_websocket_hub
    
    memory = await get_aurem_memory()
    await memory.log_activity(
        business_id,
        activity.activity_type,
        activity.description,
        activity.metadata
    )
    
    # Also push to WebSocket
    hub = await get_websocket_hub()
    await hub.push_activity(
        business_id,
        activity.activity_type,
        activity.description,
        metadata=activity.metadata
    )
    
    return {"success": True}


# ==================== STATE ENDPOINTS ====================

@router.get("/state/{business_id}/{key}")
async def get_state(business_id: str, key: str):
    """Get UI state value"""
    from services.aurem_commercial.redis_memory import get_aurem_memory
    
    memory = await get_aurem_memory()
    value = await memory.get_state(business_id, key)
    return {"key": key, "value": value}


@router.post("/state/{business_id}")
async def set_state(business_id: str, state: StateRequest):
    """Set UI state value"""
    from services.aurem_commercial.redis_memory import get_aurem_memory
    
    memory = await get_aurem_memory()
    await memory.set_state(business_id, state.key, state.value)
    return {"success": True, "key": state.key}


# ==================== HEALTH ====================

@router.get("/health")
async def health_check():
    """Health check for all Redis services"""
    from services.aurem_commercial.redis_memory import get_aurem_memory
    from services.aurem_commercial.semantic_cache import get_semantic_cache
    from services.aurem_commercial.rate_limiter import get_rate_limiter
    from services.aurem_commercial.websocket_hub import get_websocket_hub
    
    memory = await get_aurem_memory()
    cache = await get_semantic_cache()
    limiter = await get_rate_limiter()
    hub = await get_websocket_hub()
    
    return {
        "status": "healthy" if memory.available else "degraded",
        "services": {
            "redis_memory": "ok" if memory.available else "unavailable",
            "semantic_cache": "ok" if cache.available else "unavailable",
            "rate_limiter": "ok" if limiter.available else "unavailable",
            "websocket_hub": "ok",
            "websocket_connections": hub.get_connection_count()
        }
    }
