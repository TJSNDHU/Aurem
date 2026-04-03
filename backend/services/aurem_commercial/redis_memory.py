"""
AUREM Commercial Platform - Redis Memory Service
Hydrated Memory for Active Conversations (< 1ms retrieval)

Key Patterns:
- aurem:biz_{id}:conv:{conv_id} - Conversation context
- aurem:biz_{id}:profile - Business profile cache
- aurem:biz_{id}:state:{key} - UI state
- aurem:biz_{id}:activity - Live activity feed
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import os

logger = logging.getLogger(__name__)

CONVERSATION_TTL = 86400  # 24 hours
PROFILE_TTL = 3600  # 1 hour
STATE_TTL = 604800  # 7 days
MAX_CONTEXT_MESSAGES = 10


class AuremRedisMemory:
    """High-performance Redis memory for AUREM conversations."""
    
    PREFIX = "aurem"
    
    def __init__(self):
        self._redis = None
        self._connected = False
    
    async def connect(self):
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            logger.warning("[AuremMemory] REDIS_URL not set")
            return
        
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                redis_url, encoding="utf-8", decode_responses=True,
                socket_timeout=5, socket_connect_timeout=5
            )
            await self._redis.ping()
            self._connected = True
            logger.info("[AuremMemory] Connected to Redis")
        except Exception as e:
            logger.warning(f"[AuremMemory] Redis connection failed: {e}")
    
    async def disconnect(self):
        if self._redis:
            await self._redis.aclose()
    
    @property
    def available(self) -> bool:
        return self._connected and self._redis is not None
    
    def _key(self, business_id: str, *parts: str) -> str:
        return f"{self.PREFIX}:biz_{business_id}:{':'.join(parts)}"
    
    async def store_message(self, business_id: str, conversation_id: str, 
                           role: str, content: str, metadata: dict = None):
        if not self.available:
            return
        key = self._key(business_id, "conv", conversation_id)
        message = {"role": role, "content": content, 
                   "timestamp": datetime.now(timezone.utc).isoformat(),
                   "metadata": metadata or {}}
        try:
            await self._redis.rpush(key, json.dumps(message))
            await self._redis.ltrim(key, -MAX_CONTEXT_MESSAGES, -1)
            await self._redis.expire(key, CONVERSATION_TTL)
        except Exception as e:
            logger.error(f"[AuremMemory] store_message failed: {e}")
    
    async def get_context(self, business_id: str, conversation_id: str,
                         include_profile: bool = True) -> Dict[str, Any]:
        if not self.available:
            return {"messages": [], "profile": None}
        try:
            key = self._key(business_id, "conv", conversation_id)
            raw = await self._redis.lrange(key, 0, -1)
            messages = [json.loads(m) for m in raw]
            profile = await self.get_business_profile(business_id) if include_profile else None
            return {"messages": messages, "profile": profile}
        except Exception:
            return {"messages": [], "profile": None}
    
    async def set_business_profile(self, business_id: str, profile: Dict):
        if not self.available:
            return
        try:
            key = self._key(business_id, "profile")
            await self._redis.setex(key, PROFILE_TTL, json.dumps(profile))
        except Exception as e:
            logger.error(f"[AuremMemory] set_profile failed: {e}")
    
    async def get_business_profile(self, business_id: str) -> Optional[Dict]:
        if not self.available:
            return None
        try:
            key = self._key(business_id, "profile")
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None
    
    async def set_state(self, business_id: str, state_key: str, value: Any):
        if not self.available:
            return
        try:
            key = self._key(business_id, "state", state_key)
            await self._redis.setex(key, STATE_TTL, json.dumps(value))
        except Exception:
            pass
    
    async def get_state(self, business_id: str, state_key: str, default=None):
        if not self.available:
            return default
        try:
            key = self._key(business_id, "state", state_key)
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else default
        except Exception:
            return default
    
    async def log_activity(self, business_id: str, activity_type: str,
                          description: str, metadata: dict = None):
        if not self.available:
            return
        key = self._key(business_id, "activity")
        activity = {"type": activity_type, "description": description,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": metadata or {}}
        try:
            await self._redis.lpush(key, json.dumps(activity))
            await self._redis.ltrim(key, 0, 49)
            await self._redis.expire(key, 86400 * 7)
        except Exception:
            pass
    
    async def get_activities(self, business_id: str, limit: int = 20) -> List[Dict]:
        if not self.available:
            return []
        try:
            key = self._key(business_id, "activity")
            raw = await self._redis.lrange(key, 0, limit - 1)
            return [json.loads(a) for a in raw]
        except Exception:
            return []


_aurem_memory: Optional[AuremRedisMemory] = None

async def get_aurem_memory() -> AuremRedisMemory:
    global _aurem_memory
    if _aurem_memory is None:
        _aurem_memory = AuremRedisMemory()
        await _aurem_memory.connect()
    return _aurem_memory
