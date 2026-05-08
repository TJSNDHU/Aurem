"""
AUREM Memobase — Semantic Memory Layer for Hermes
===================================================
MongoDB-based vector memory using local embeddings (all-MiniLM-L6-v2).
No external services — fully self-contained.

Two memory types:
  Episodic: per-tenant interactions with timestamps + embeddings
  Semantic: embedding similarity search on past interactions

Wired into Hermes OODA:
  recall() → semantic search for similar past interactions
  store()  → embed + persist interaction with vector
  consolidate() → merge similar memories, prune duplicates
"""
import os
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def ensure_indexes():
    """Create indexes for memobase collections."""
    db = _get_db()
    if not db:
        return
    try:
        await db.memobase_memories.create_index([("tenant_id", 1), ("created_at", -1)])
        await db.memobase_memories.create_index([("tenant_id", 1), ("memory_type", 1)])
        await db.memobase_memories.create_index([("tenant_id", 1), ("agent_id", 1)])
        await db.memobase_memories.create_index("expires_at", expireAfterSeconds=0)
        logger.info("[MEMOBASE] Indexes ensured")
    except Exception as e:
        logger.warning(f"[MEMOBASE] Index error: {e}")


async def store_memory(
    tenant_id: str,
    content: str,
    memory_type: str = "episodic",
    agent_id: str = "ora",
    session_id: str = "",
    outcome: str = "success",
    context: Dict = None,
    ttl_days: int = 180,
) -> Dict:
    """
    Store a memory with its embedding vector.
    Memory types: episodic (interactions), semantic (facts), procedural (skills)
    """
    db = _get_db()
    if not db or not content:
        return {"stored": False}

    from services.embeddings import embed_text
    embedding = embed_text(content[:500])

    # Check if embedding is valid (not all zeros)
    is_valid_embedding = any(v != 0.0 for v in embedding)

    now = datetime.now(timezone.utc)
    doc = {
        "tenant_id": tenant_id,
        "content": content[:1000],
        "memory_type": memory_type,
        "agent_id": agent_id,
        "session_id": session_id,
        "outcome": outcome,
        "context": context or {},
        "embedding": embedding,
        "has_embedding": is_valid_embedding,
        "access_count": 0,
        "last_accessed": None,
        "created_at": now.isoformat(),
        "expires_at": now + timedelta(days=ttl_days),
    }
    await db.memobase_memories.insert_one(doc)
    return {"stored": True, "has_embedding": is_valid_embedding, "memory_type": memory_type}


async def semantic_recall(
    tenant_id: str,
    query: str,
    limit: int = 5,
    threshold: float = 0.45,
    memory_type: str = None,
    agent_id: str = None,
) -> List[Dict]:
    """
    Semantic search: embed the query, compare against stored memories.
    Returns top-k similar memories above threshold.
    Uses in-application cosine similarity (no Atlas Search needed).
    """
    db = _get_db()
    if not db or not query:
        return []

    from services.embeddings import embed_text
    query_embedding = embed_text(query[:500])

    # Check if embeddings are available
    if all(v == 0.0 for v in query_embedding):
        # Fallback to text search if embeddings unavailable
        return await _text_recall(tenant_id, query, limit, memory_type, agent_id)

    # Fetch recent memories with embeddings for this tenant
    match_filter = {"tenant_id": tenant_id, "has_embedding": True}
    if memory_type:
        match_filter["memory_type"] = memory_type
    if agent_id:
        match_filter["agent_id"] = agent_id

    # Fetch candidates (capped at 200 for performance)
    cursor = db.memobase_memories.find(
        match_filter,
        {"_id": 0, "content": 1, "embedding": 1, "memory_type": 1,
         "outcome": 1, "agent_id": 1, "context": 1, "created_at": 1,
         "session_id": 1, "access_count": 1},
    ).sort("created_at", -1).limit(200)
    candidates = await cursor.to_list(200)

    if not candidates:
        return []

    # Compute similarities
    scored = []
    for mem in candidates:
        sim = _cosine_similarity(query_embedding, mem.get("embedding", []))
        if sim >= threshold:
            # Pattern: Evaluator scoring (inspired by context-engineering-workflow)
            # Each result gets a relevance_grade combining similarity + recency + outcome
            recency_boost = 0.0
            created = mem.get("created_at", "")
            if created:
                try:
                    from datetime import datetime as dt
                    age_days = (datetime.now(timezone.utc) - dt.fromisoformat(created.replace("Z", "+00:00"))).days
                    recency_boost = max(0, 0.1 - (age_days * 0.001))  # Recent = higher boost
                except Exception:
                    pass
            outcome_boost = 0.05 if mem.get("outcome") == "success" else 0.0
            relevance_score = round(min(1.0, sim + recency_boost + outcome_boost), 4)

            scored.append({
                "content": mem["content"],
                "memory_type": mem.get("memory_type", ""),
                "outcome": mem.get("outcome", ""),
                "agent_id": mem.get("agent_id", ""),
                "session_id": mem.get("session_id", ""),
                "context": mem.get("context", {}),
                "similarity": round(sim, 4),
                "relevance_score": relevance_score,
                "created_at": mem.get("created_at", ""),
                "access_count": mem.get("access_count", 0),
            })

    # Sort by relevance_score descending (not raw similarity), take top-k
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    results = scored[:limit]

    # Update access counts for retrieved memories
    for r in results:
        await db.memobase_memories.update_one(
            {"tenant_id": tenant_id, "content": r["content"], "created_at": r["created_at"]},
            {"$inc": {"access_count": 1}, "$set": {"last_accessed": datetime.now(timezone.utc).isoformat()}},
        )

    return results


async def _text_recall(
    tenant_id: str,
    query: str,
    limit: int = 5,
    memory_type: str = None,
    agent_id: str = None,
) -> List[Dict]:
    """Fallback: keyword-based recall when embeddings unavailable."""
    db = _get_db()
    if not db:
        return []
    words = query.lower().split()[:5]
    match_filter = {"tenant_id": tenant_id}
    if memory_type:
        match_filter["memory_type"] = memory_type
    if agent_id:
        match_filter["agent_id"] = agent_id

    # Simple regex match on any keyword
    if words:
        match_filter["content"] = {"$regex": "|".join(words[:3]), "$options": "i"}

    cursor = db.memobase_memories.find(
        match_filter,
        {"_id": 0, "content": 1, "memory_type": 1, "outcome": 1,
         "agent_id": 1, "context": 1, "created_at": 1, "access_count": 1,
         "session_id": 1},
    ).sort("created_at", -1).limit(limit)
    results = await cursor.to_list(limit)
    for r in results:
        r["similarity"] = 0.5  # Fixed score for text matches
        # Pattern: Evaluator scoring for text fallback (consistent with semantic_recall)
        outcome_boost = 0.05 if r.get("outcome") == "success" else 0.0
        r["relevance_score"] = round(0.5 + outcome_boost, 4)  # Base 0.5 + outcome boost
    return results


async def consolidate_memories(tenant_id: str, similarity_threshold: float = 0.92) -> Dict:
    """
    Memory consolidation: merge highly similar memories to reduce noise.
    Keeps the most recent version, increments access_count.
    """
    db = _get_db()
    if not db:
        return {"consolidated": 0}

    cursor = db.memobase_memories.find(
        {"tenant_id": tenant_id, "has_embedding": True},
        {"_id": 1, "content": 1, "embedding": 1, "created_at": 1, "access_count": 1},
    ).sort("created_at", -1).limit(100)
    memories = await cursor.to_list(100)

    if len(memories) < 2:
        return {"consolidated": 0, "total": len(memories)}

    # Find duplicate clusters
    merged_ids = set()
    consolidated = 0
    for i, m1 in enumerate(memories):
        if str(m1["_id"]) in merged_ids:
            continue
        for j, m2 in enumerate(memories[i + 1:], i + 1):
            if str(m2["_id"]) in merged_ids:
                continue
            sim = _cosine_similarity(m1.get("embedding", []), m2.get("embedding", []))
            if sim >= similarity_threshold:
                # Keep m1 (newer), remove m2
                merged_ids.add(str(m2["_id"]))
                await db.memobase_memories.update_one(
                    {"_id": m1["_id"]},
                    {"$inc": {"access_count": m2.get("access_count", 0) + 1}},
                )
                await db.memobase_memories.delete_one({"_id": m2["_id"]})
                consolidated += 1

    return {"consolidated": consolidated, "total_before": len(memories), "total_after": len(memories) - consolidated}


async def get_memory_stats(tenant_id: str = None) -> Dict:
    """Get Memobase statistics for dashboard."""
    db = _get_db()
    if not db:
        return {"total": 0}
    q = {"tenant_id": tenant_id} if tenant_id else {}
    total = await db.memobase_memories.count_documents(q)
    with_emb = await db.memobase_memories.count_documents({**q, "has_embedding": True})

    type_counts = {}
    for mt in ["episodic", "semantic", "procedural"]:
        type_counts[mt] = await db.memobase_memories.count_documents({**q, "memory_type": mt})

    return {
        "total_memories": total,
        "with_embeddings": with_emb,
        "by_type": type_counts,
        "embedding_coverage": round(with_emb / max(1, total) * 100, 1),
    }


# ═══════════════════════════════════════════════════════════════
# AUDIO RAG PATTERN — Voice Transcript → Memobase Memory
# (Inspired by chat-with-audios: transcribe → chunk → embed → RAG)
# ═══════════════════════════════════════════════════════════════

async def store_voice_transcript(
    tenant_id: str,
    transcript: str,
    agent_id: str = "ora_voice",
    session_id: str = "",
    caller_info: Dict = None,
    sentiment: str = "",
) -> Dict:
    """
    Audio RAG pattern: store voice call transcript as Memobase memory.
    Chunks long transcripts and stores each chunk with embeddings for
    future semantic recall during voice interactions.
    """
    if not transcript or len(transcript.strip()) < 10:
        return {"stored": False, "reason": "transcript_too_short"}

    chunks = _chunk_transcript(transcript)
    stored_count = 0
    for i, chunk in enumerate(chunks):
        context = {
            "source": "voice_transcript",
            "chunk_index": i,
            "total_chunks": len(chunks),
            "sentiment": sentiment,
            **(caller_info or {}),
        }
        result = await store_memory(
            tenant_id=tenant_id,
            content=chunk,
            memory_type="episodic",
            agent_id=agent_id,
            session_id=session_id,
            outcome="success",
            context=context,
        )
        if result.get("stored"):
            stored_count += 1

    return {"stored": True, "chunks": stored_count, "total_length": len(transcript)}


def _chunk_transcript(text: str, max_chars: int = 400, overlap: int = 50) -> List[str]:
    """Split transcript into overlapping chunks for better embedding recall."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        # Try to break at sentence boundary
        if end < len(text):
            for sep in ['. ', '? ', '! ', '\n']:
                last_sep = text[start:end].rfind(sep)
                if last_sep > max_chars // 2:
                    end = start + last_sep + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if len(c) > 10]


async def voice_context_recall(
    tenant_id: str,
    current_query: str,
    caller_phone: str = "",
    limit: int = 3,
) -> List[Dict]:
    """
    Before ORA responds to a voice call, recall relevant past voice interactions.
    Combines semantic search with caller-specific filtering.
    """
    results = await semantic_recall(
        tenant_id=tenant_id,
        query=current_query,
        limit=limit,
        threshold=0.35,
        agent_id="ora_voice" if not caller_phone else None,
    )
    # If caller phone provided, boost results from same caller
    if caller_phone:
        for r in results:
            if r.get("context", {}).get("caller_phone") == caller_phone:
                r["relevance_score"] = min(1.0, r.get("relevance_score", 0.5) + 0.15)
        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return results
