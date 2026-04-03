"""
AUREM Commercial Platform - Semantic Cache Service
AI Response Caching with Vector Similarity (95% match threshold)

Uses simple string matching + hash-based caching.
For production RedisVL with embeddings, install sentence-transformers.

Key Pattern: aurem:cache:biz_{id}:{query_hash}
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
import os
import re

logger = logging.getLogger(__name__)

CACHE_TTL = 86400  # 24 hours
SIMILARITY_THRESHOLD = 0.85


class AuremSemanticCache:
    """
    Semantic caching for AI responses.
    Reduces AI costs by serving cached answers for similar questions.
    """
    
    PREFIX = "aurem:cache"
    
    def __init__(self):
        self._redis = None
        self._connected = False
    
    async def connect(self):
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            return
        
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                redis_url, encoding="utf-8", decode_responses=True,
                socket_timeout=5, socket_connect_timeout=5
            )
            await self._redis.ping()
            self._connected = True
            logger.info("[SemanticCache] Connected to Redis")
        except Exception as e:
            logger.warning(f"[SemanticCache] Redis connection failed: {e}")
    
    @property
    def available(self) -> bool:
        return self._connected and self._redis is not None
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for better matching"""
        q = query.lower().strip()
        q = re.sub(r'[^\w\s]', '', q)
        q = re.sub(r'\s+', ' ', q)
        stop_words = {'what', 'is', 'are', 'the', 'a', 'an', 'your', 'my', 'do', 'does', 'how', 'when', 'where'}
        words = [w for w in q.split() if w not in stop_words]
        return ' '.join(sorted(words))
    
    def _query_hash(self, query: str) -> str:
        """Generate hash for normalized query"""
        normalized = self._normalize_query(query)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _key(self, business_id: str, query_hash: str) -> str:
        return f"{self.PREFIX}:biz_{business_id}:{query_hash}"
    
    async def check(
        self,
        business_id: str,
        query: str
    ) -> Tuple[Optional[str], str]:
        """
        Check cache for similar query.
        Returns (cached_response, status) where status is 'HIT' or 'MISS'
        """
        if not self.available:
            return None, "DISABLED"
        
        query_hash = self._query_hash(query)
        key = self._key(business_id, query_hash)
        
        try:
            raw = await self._redis.get(key)
            if raw:
                data = json.loads(raw)
                logger.info(f"[SemanticCache] HIT for {business_id}: {query[:50]}...")
                return data.get("response"), "HIT"
        except Exception as e:
            logger.error(f"[SemanticCache] check failed: {e}")
        
        return None, "MISS"
    
    async def store(
        self,
        business_id: str,
        query: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store AI response in cache"""
        if not self.available:
            return
        
        query_hash = self._query_hash(query)
        key = self._key(business_id, query_hash)
        
        cache_entry = {
            "query": query,
            "query_normalized": self._normalize_query(query),
            "response": response,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        
        try:
            await self._redis.setex(key, CACHE_TTL, json.dumps(cache_entry))
            logger.debug(f"[SemanticCache] Stored for {business_id}: {query[:50]}...")
        except Exception as e:
            logger.error(f"[SemanticCache] store failed: {e}")
    
    async def invalidate(self, business_id: str, query: str = None):
        """Invalidate cache entry or all entries for business"""
        if not self.available:
            return
        
        try:
            if query:
                key = self._key(business_id, self._query_hash(query))
                await self._redis.delete(key)
            else:
                pattern = f"{self.PREFIX}:biz_{business_id}:*"
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"[SemanticCache] invalidate failed: {e}")
    
    async def get_stats(self, business_id: str) -> Dict[str, Any]:
        """Get cache stats for a business"""
        if not self.available:
            return {"status": "unavailable"}
        
        try:
            pattern = f"{self.PREFIX}:biz_{business_id}:*"
            keys = await self._redis.keys(pattern)
            return {
                "status": "connected",
                "cached_queries": len(keys),
                "ttl_hours": CACHE_TTL // 3600
            }
        except Exception:
            return {"status": "error"}


_semantic_cache: Optional[AuremSemanticCache] = None

async def get_semantic_cache() -> AuremSemanticCache:
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = AuremSemanticCache()
        await _semantic_cache.connect()
    return _semantic_cache
