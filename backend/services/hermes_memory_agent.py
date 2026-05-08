"""
Hermes Memory Agent — Self-Improving OODA Memory Loop
=====================================================
Three memory layers per tenant:
  working_memory  — current session context (24h TTL)
  episodic_memory — every interaction stored (90d TTL)
  knowledge_base  — successful patterns promoted when confidence > 0.85

After EVERY agent response: store_interaction() fires automatically.
Before EVERY agent action: recall() retrieves relevant past successes.

This closes the OODA loop and makes AUREM self-improving.
"""
import os
import time
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database
    from services.memory_tiers import set_db as set_mt_db
    set_mt_db(database)


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


async def ensure_indexes():
    """Create all Hermes memory indexes (idempotent)."""
    from services.memory_tiers import ensure_indexes as mt_indexes
    await mt_indexes()
    db = _get_db()
    if db is None:
        return
    try:
        await db.hermes_interactions.create_index([("tenant_id", 1), ("timestamp", -1)])
        await db.hermes_interactions.create_index([("tenant_id", 1), ("agent_id", 1)])
        await db.hermes_interactions.create_index([("session_id", 1)])
        await db.hermes_interactions.create_index("expires_at", expireAfterSeconds=0)
        logger.info("[HERMES] Memory indexes ensured")
    except Exception as e:
        logger.warning(f"[HERMES] Index creation: {e}")


# ═══════════════════════════════════════
# RECALL — Pre-action memory retrieval
# ═══════════════════════════════════════

async def recall(tenant_id: str, query: str, agent_id: str = "ora") -> Dict[str, Any]:
    """
    Before any agent action, retrieve relevant memories.
    Returns: prior successes, known patterns, working context, semantic matches.
    """
    from services.memory_tiers import (
        scout_read_memory, get_working_memory, classify_query
    )
    from services.memobase import semantic_recall
    query_type = classify_query(query)

    # Parallel reads from all 3 tiers + semantic search
    scout_mem, working_mem, kb_patterns, sem_memories = await asyncio.gather(
        scout_read_memory(query_type, tenant_id),
        get_working_memory(tenant_id),
        _get_knowledge_patterns(tenant_id, query_type),
        semantic_recall(tenant_id, query, limit=3, agent_id=agent_id),
        return_exceptions=True,
    )

    if isinstance(scout_mem, Exception):
        scout_mem = {"prior_success": False}
    if isinstance(working_mem, Exception):
        working_mem = {}
    if isinstance(kb_patterns, Exception):
        kb_patterns = []
    if isinstance(sem_memories, Exception):
        sem_memories = []

    return {
        "query_type": query_type,
        "prior_success": scout_mem.get("prior_success", False),
        "last_approach": scout_mem.get("last_approach", ""),
        "confidence_boost": scout_mem.get("confidence_boost", 0),
        "known_patterns": kb_patterns,
        "semantic_memories": sem_memories,
        "working_context": {
            "last_action": working_mem.get("last_action", ""),
            "last_outcome": working_mem.get("last_outcome", ""),
            "active_goals": working_mem.get("active_goals", []),
        },
    }


async def _get_knowledge_patterns(tenant_id: str, query_type: str, limit: int = 3) -> List[Dict]:
    db = _get_db()
    if db is None:
        return []
    try:
        cursor = db.knowledge_base.find(
            {"tenant_id": tenant_id, "pattern_type": query_type},
            {"_id": 0, "pattern": 1, "action_taken": 1, "confidence": 1, "success_count": 1},
        ).sort("confidence", -1).limit(limit)
        return await cursor.to_list(length=limit)
    except Exception:
        return []


# ═══════════════════════════════════════
# AFTER RESPONSE HOOK — Auto-store
# ═══════════════════════════════════════

async def after_response_hook(
    tenant_id: str,
    session_id: str,
    agent_id: str,
    input_text: str,
    output_text: str,
    outcome: str = "success",
    action_type: str = None,
    execution_time_s: float = None,
    metadata: Dict = None,
):
    """
    Fire-and-forget hook called after EVERY agent response.
    Stores to episodic_memory, updates working_memory, auto-promotes to knowledge_base.
    """
    try:
        from services.memory_tiers import store_interaction, classify_query
        from services.memobase import store_memory

        action_type = action_type or classify_query(input_text)
        action_taken = f"{agent_id}: {input_text[:200]}"
        finding_type = (metadata or {}).get("finding_type", action_type)

        result = await store_interaction(
            tenant_id=tenant_id,
            run_id=session_id,
            action_type=action_type,
            action_taken=action_taken,
            outcome=outcome,
            finding_type=finding_type,
            has_known_fix=(metadata or {}).get("has_known_fix", False),
            execution_time_s=execution_time_s,
            error=(metadata or {}).get("error"),
        )

        # Store to Memobase with embedding for semantic recall
        await store_memory(
            tenant_id=tenant_id,
            content=f"{input_text[:300]} → {output_text[:200]}",
            memory_type="episodic",
            agent_id=agent_id,
            session_id=session_id,
            outcome=outcome,
            context={"action_type": action_type, "confidence": result.get("confidence", 0)},
        )

        # Also store full interaction record for auditing
        db = _get_db()
        if db is not None:
            await db.hermes_interactions.insert_one({
                "tenant_id": tenant_id,
                "session_id": session_id,
                "agent_id": agent_id,
                "input_text": input_text[:500],
                "output_text": output_text[:500],
                "outcome": outcome,
                "action_type": action_type,
                "confidence": result.get("confidence", 0),
                "promoted": result.get("promoted", False),
                "execution_time_s": execution_time_s,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=90),
            })

        if result.get("promoted"):
            logger.info(f"[HERMES] Pattern promoted: {action_type} (conf={result['confidence']})")

    except Exception as e:
        logger.warning(f"[HERMES] after_response_hook error: {e}")


def fire_and_forget_store(
    tenant_id: str,
    session_id: str,
    agent_id: str,
    input_text: str,
    output_text: str,
    outcome: str = "success",
    action_type: str = None,
    execution_time_s: float = None,
    metadata: Dict = None,
):
    """Non-blocking wrapper — schedules after_response_hook without awaiting."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(after_response_hook(
                tenant_id=tenant_id,
                session_id=session_id,
                agent_id=agent_id,
                input_text=input_text,
                output_text=output_text,
                outcome=outcome,
                action_type=action_type,
                execution_time_s=execution_time_s,
                metadata=metadata,
            ))
    except Exception as e:
        logger.debug(f"[HERMES] fire_and_forget scheduling: {e}")


# ═══════════════════════════════════════
# KNOWLEDGE BASE QUERIES
# ═══════════════════════════════════════

async def get_knowledge_entries(tenant_id: str = None, limit: int = 20) -> List[Dict]:
    db = _get_db()
    if db is None:
        return []
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    cursor = db.knowledge_base.find(query, {"_id": 0}).sort("confidence", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_recent_interactions(tenant_id: str = None, limit: int = 20) -> List[Dict]:
    db = _get_db()
    if db is None:
        return []
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    cursor = db.hermes_interactions.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_hermes_dashboard(tenant_id: str = None) -> Dict:
    """Aggregated stats for the Hermes Memory Agent dashboard."""
    from services.memory_tiers import get_memory_stats, get_memory_loop_stats, get_learning_velocity

    stats, loop_stats, velocity = await asyncio.gather(
        get_memory_stats(tenant_id),
        get_memory_loop_stats(tenant_id),
        get_learning_velocity(tenant_id),
        return_exceptions=True,
    )
    if isinstance(stats, Exception):
        stats = {}
    if isinstance(loop_stats, Exception):
        loop_stats = {}
    if isinstance(velocity, Exception):
        velocity = {}

    db = _get_db()
    interaction_count = 0
    if db is not None:
        try:
            q = {"tenant_id": tenant_id} if tenant_id else {}
            interaction_count = await db.hermes_interactions.count_documents(q)
        except Exception:
            pass

    return {
        "memory_tiers": stats,
        "loop_stats": loop_stats,
        "learning_velocity": velocity,
        "total_hermes_interactions": interaction_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def manually_promote_pattern(
    tenant_id: str, pattern_type: str, pattern: str, action_taken: str
) -> Dict:
    """Admin-triggered promotion to knowledge_base."""
    db = _get_db()
    if db is None:
        return {"promoted": False, "reason": "no_db"}
    now = datetime.now(timezone.utc)
    await db.knowledge_base.update_one(
        {"tenant_id": tenant_id, "pattern_type": pattern_type},
        {
            "$inc": {"success_count": 1, "hit_count": 1},
            "$set": {
                "tenant_id": tenant_id,
                "pattern_type": pattern_type,
                "pattern": pattern,
                "action_taken": action_taken,
                "confidence": 0.90,
                "source": "manual_promote",
                "last_success": now.isoformat(),
                "promoted_at": now.isoformat(),
            },
        },
        upsert=True,
    )
    return {"promoted": True, "pattern_type": pattern_type}
