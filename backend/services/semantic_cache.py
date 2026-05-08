"""
Semantic Cache — Eliminates repeated LLM calls.
================================================
1. Hash incoming query
2. Search MongoDB cache for exact/similar match
3. If match found AND fresh: return cached response
4. If miss: call LLM, store result in cache

Uses simple string hashing (no embedding model needed).
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

logger = logging.getLogger(__name__)

_db = None

# TTL in seconds per query type
TTL_FACTUAL = 14400    # 4 hours for factual queries
TTL_BUSINESS = 3600    # 1 hour for business data
TTL_REALTIME = 0       # Never cache real-time requests

REALTIME_KEYWORDS = {"right now", "current", "live", "today's weather", "just happened"}
BUSINESS_KEYWORDS = {"pipeline", "revenue", "leads", "mrr", "deals", "forecast"}


def set_db(database):
    global _db
    _db = database


def _hash_query(text: str) -> str:
    """Normalize and hash the query for exact matching."""
    normalized = text.strip().lower()
    # Remove common filler words for better matching
    for word in ["please", "can you", "could you", "hey", "hi", "ora"]:
        normalized = normalized.replace(word, "")
    normalized = " ".join(normalized.split())  # collapse whitespace
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def _get_ttl(query: str) -> int:
    """Determine TTL based on query content."""
    q = query.lower()
    if any(kw in q for kw in REALTIME_KEYWORDS):
        return TTL_REALTIME
    if any(kw in q for kw in BUSINESS_KEYWORDS):
        return TTL_BUSINESS
    return TTL_FACTUAL


async def get_cached_response(query: str, tenant_id: str = "aurem_platform") -> Optional[Dict]:
    """Check cache for a matching response. Returns None on miss."""
    if _db is None:
        return None

    ttl = _get_ttl(query)
    if ttl == 0:
        return None  # Never cache real-time queries

    query_hash = _hash_query(query)

    try:
        cutoff = datetime.now(timezone.utc).timestamp() - ttl
        cached = await _db.semantic_cache.find_one(
            {
                "query_hash": query_hash,
                "tenant_id": tenant_id,
                "created_ts": {"$gte": cutoff},
            },
            {"_id": 0, "response": 1, "model_used": 1, "autotune": 1, "hit_count": 1},
        )

        if cached:
            # Increment hit counter
            await _db.semantic_cache.update_one(
                {"query_hash": query_hash, "tenant_id": tenant_id},
                {"$inc": {"hit_count": 1}},
            )
            logger.info(f"[SemanticCache] HIT for hash={query_hash[:8]}... hits={cached.get('hit_count', 0) + 1}")
            return cached
    except Exception as e:
        logger.debug(f"[SemanticCache] Lookup error: {e}")

    return None

    return None


async def store_response(
    query: str,
    response: str,
    model_used: str,
    tenant_id: str = "aurem_platform",
    autotune: Optional[Dict] = None,
):
    """Store a response in cache."""
    if _db is None or not response:
        return

    ttl = _get_ttl(query)
    if ttl == 0:
        return

    query_hash = _hash_query(query)

    try:
        await _db.semantic_cache.update_one(
            {"query_hash": query_hash, "tenant_id": tenant_id},
            {"$set": {
                "query_hash": query_hash,
                "query_text": query[:200],
                "response": response,
                "model_used": model_used,
                "autotune": autotune,
                "tenant_id": tenant_id,
                "created_ts": datetime.now(timezone.utc).timestamp(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "hit_count": 0,
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[SemanticCache] Store error: {e}")


async def get_cache_stats(tenant_id: str = "aurem_platform") -> Dict:
    """Get cache statistics for monitoring."""
    if _db is None:
        return {"total_entries": 0, "total_hits": 0}

    try:
        total = await _db.semantic_cache.count_documents({"tenant_id": tenant_id})
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {"_id": None, "total_hits": {"$sum": "$hit_count"}}},
        ]
        result = await _db.semantic_cache.aggregate(pipeline).to_list(1)
        total_hits = result[0]["total_hits"] if result else 0
        return {"total_entries": total, "total_hits": total_hits}
    except Exception:
        return {"total_entries": 0, "total_hits": 0}
