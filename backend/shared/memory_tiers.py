"""
Three-Tier Memory System — working_memory + episodic_memory + knowledge_base
=============================================================================
Tier 1: Long-term (knowledge_base) — existing, never expires
Tier 2: Working memory — current session context, 24h TTL
Tier 3: Episodic memory — action history + outcomes, 90-day rolling

Wired into OODA pipeline:
  Scout → reads episodic (what worked before?)
  Architect → reads long-term knowledge_base
  Envoy → reads working_memory (today's goals)
  Closer → writes episodic (what we tried)
  Verifier → updates all 3 tiers with results
"""

import os
import logging
from datetime import datetime, timezone, timedelta

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
    """Create TTL indexes for working_memory (24h) and episodic_memory (90d)."""
    db = _get_db()
    if db is None:
        return
    try:
        await db.working_memory.create_index("expires_at", expireAfterSeconds=0)
        await db.working_memory.create_index([("tenant_id", 1), ("session_id", 1)])
        await db.episodic_memory.create_index("expires_at", expireAfterSeconds=0)
        await db.episodic_memory.create_index([("tenant_id", 1), ("action_type", 1)])
        await db.episodic_memory.create_index([("tenant_id", 1), ("outcome", 1)])
        await db.episodic_memory.create_index([("tenant_id", 1), ("query_type", 1)])
        await db.execution_plans.create_index([("pipeline_run_id", 1)])
        await db.execution_plans.create_index([("tenant_id", 1), ("status", 1)])
        await db.knowledge_base.create_index([("tenant_id", 1), ("pattern_type", 1)])
        await db.memory_loop_log.create_index([("tenant_id", 1), ("timestamp", -1)])
        logger.info("[MEMORY] TTL + memory-loop indexes created")
    except Exception as e:
        logger.warning(f"[MEMORY] Index creation: {e}")


# ═══════════════════════════════════════
# QUERY HELPERS (classify, summarize, extract)
# ═══════════════════════════════════════

def classify_query(query: str) -> str:
    """Classify the query type for episodic pattern matching."""
    q = (query or "").lower()
    if any(w in q for w in ["lead", "outreach", "prospect", "contact"]):
        return "lead_management"
    if any(w in q for w in ["invoice", "payment", "billing", "overdue"]):
        return "billing"
    if any(w in q for w in ["site", "health", "css", "pixel", "seo"]):
        return "site_optimization"
    if any(w in q for w in ["message", "reply", "response", "chat"]):
        return "communication"
    if any(w in q for w in ["fix", "repair", "heal", "bug"]):
        return "auto_repair"
    if any(w in q for w in ["scan", "audit", "check"]):
        return "diagnostic"
    return "general"


def summarize_context(query: str, response: dict) -> str:
    """Create a compact context string for working memory."""
    action = response.get("action") or response.get("strategy") or "unknown"
    outcome = response.get("outcome") or response.get("status") or "unknown"
    finding = response.get("finding_type") or response.get("type") or ""
    return f"{action} → {outcome}" + (f" ({finding})" if finding else "")


def extract_pattern(query: str, response: dict) -> str:
    """Extract a reusable pattern from a successful interaction."""
    action = response.get("action") or response.get("strategy") or "unknown"
    finding = response.get("finding_type") or response.get("type") or "unknown"
    return f"{action} effective for {finding}"


# ═══════════════════════════════════════
# SCOUT READ-BACK (episodic recall before acting)
# ═══════════════════════════════════════

async def scout_read_memory(query_type: str, tenant_id: str) -> dict:
    """Before any Scout search, check episodic memory for prior success."""
    db = _get_db()
    if db is None:
        return {"prior_success": False}
    recent = await db.episodic_memory.find_one(
        {
            "tenant_id": tenant_id,
            "query_type": query_type,
            "outcome": "success",
        },
        {"_id": 0},
        sort=[("timestamp", -1)],
    )
    if recent:
        return {
            "prior_success": True,
            "last_approach": recent.get("action_taken", ""),
            "confidence_boost": 0.1,
            "last_pattern": recent.get("learned_pattern", ""),
        }
    return {"prior_success": False}


# ═══════════════════════════════════════
# TIER 2: WORKING MEMORY (24h context)
# ═══════════════════════════════════════

async def set_working_memory(tenant_id: str, session_id: str, data: dict):
    """Write/update working memory for current session."""
    db = _get_db()
    if db is None:
        return
    now = datetime.now(timezone.utc)
    doc = {
        "tenant_id": tenant_id,
        "session_id": session_id,
        "active_goals": data.get("active_goals", []),
        "current_pipeline_stage": data.get("current_pipeline_stage", ""),
        "pending_decisions": data.get("pending_decisions", []),
        "context_summary": data.get("context_summary", ""),
        "last_action": data.get("last_action", ""),
        "last_outcome": data.get("last_outcome", ""),
        "last_confidence": data.get("last_confidence"),
        "session_context": data.get("session_context", data.get("context_summary", "")),
        "last_updated": now.isoformat(),
        "expires_at": now + timedelta(hours=24),
    }
    await db.working_memory.update_one(
        {"tenant_id": tenant_id, "session_id": session_id},
        {"$set": doc},
        upsert=True,
    )


async def get_working_memory(tenant_id: str = None) -> dict:
    """Read latest working memory. If tenant_id is None, return the most recent across all tenants (admin view)."""
    db = _get_db()
    if db is None:
        return {}
    q = {"tenant_id": tenant_id} if tenant_id else {}
    doc = await db.working_memory.find_one(
        q,
        {"_id": 0},
        sort=[("last_updated", -1)],
    )
    return doc or {}


# ═══════════════════════════════════════
# TIER 3: EPISODIC MEMORY (90-day rolling)
# ═══════════════════════════════════════

async def write_episode(tenant_id: str, action_type: str, action_taken: str,
                        outcome: str, lead_id: str = None,
                        response_time_hours: float = None,
                        learned_pattern: str = None):
    """Record an action and its outcome."""
    db = _get_db()
    if db is None:
        return
    now = datetime.now(timezone.utc)
    await db.episodic_memory.insert_one({
        "tenant_id": tenant_id,
        "action_type": action_type,
        "action_taken": action_taken,
        "outcome": outcome,
        "lead_id": lead_id,
        "response_time_hours": response_time_hours,
        "learned_pattern": learned_pattern,
        "timestamp": now.isoformat(),
        "expires_at": now + timedelta(days=90),
    })


async def query_episodes(tenant_id: str = None, action_type: str = None,
                         outcome: str = None, limit: int = 10) -> list:
    """Query episodic memory. tenant_id=None → cross-tenant admin view."""
    db = _get_db()
    if db is None:
        return []
    query = {"tenant_id": tenant_id} if tenant_id else {}
    if action_type:
        query["action_type"] = action_type
    if outcome:
        query["outcome"] = outcome
    cursor = db.episodic_memory.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_success_patterns(tenant_id: str = None, action_type: str = None) -> dict:
    """Analyze episodic memory for success patterns. tenant_id=None → all tenants."""
    db = _get_db()
    if db is None:
        return {"total": 0, "success_rate": 0}
    query = {"tenant_id": tenant_id} if tenant_id else {}
    if action_type:
        query["action_type"] = action_type
    total = await db.episodic_memory.count_documents(query)
    successes = await db.episodic_memory.count_documents({**query, "outcome": "success"})
    return {
        "total": total,
        "successes": successes,
        "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
    }


# ═══════════════════════════════════════
# PLAN PERSISTENCE (execution_plans)
# ═══════════════════════════════════════

async def write_execution_plan(pipeline_run_id: str, tenant_id: str, steps: list) -> dict:
    """Architect writes plan before Closer executes."""
    db = _get_db()
    if db is None:
        return {"status": "no_db"}
    now = datetime.now(timezone.utc)
    plan = {
        "pipeline_run_id": pipeline_run_id,
        "tenant_id": tenant_id,
        "plan": steps,
        "created_by": "architect_agent",
        "status": "pending",
        "created_at": now.isoformat(),
        "completed_at": None,
    }
    await db.execution_plans.update_one(
        {"pipeline_run_id": pipeline_run_id},
        {"$set": plan},
        upsert=True,
    )
    return plan


async def update_plan_step(pipeline_run_id: str, step_index: int,
                           status: str, error: str = None):
    """Closer updates each step as it executes."""
    db = _get_db()
    if db is None:
        return
    update = {f"plan.{step_index}.status": status}
    if error:
        update[f"plan.{step_index}.error"] = error
    if status == "failed":
        update["status"] = "failed"
    await db.execution_plans.update_one(
        {"pipeline_run_id": pipeline_run_id},
        {"$set": update},
    )


async def complete_plan(pipeline_run_id: str, status: str = "complete"):
    """Mark plan as complete/failed."""
    db = _get_db()
    if db is None:
        return
    await db.execution_plans.update_one(
        {"pipeline_run_id": pipeline_run_id},
        {"$set": {
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )


async def get_execution_plan(pipeline_run_id: str) -> dict:
    """Read execution plan for a pipeline run."""
    db = _get_db()
    if db is None:
        return {}
    doc = await db.execution_plans.find_one(
        {"pipeline_run_id": pipeline_run_id}, {"_id": 0}
    )
    return doc or {}


async def get_recent_plans(tenant_id: str = None, limit: int = 10) -> list:
    """Get recent execution plans. tenant_id=None → all tenants (admin view)."""
    db = _get_db()
    if db is None:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    cursor = db.execution_plans.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


# ═══════════════════════════════════════
# STAGE 3: STORE_INTERACTION + AUTO-PROMOTE
# ═══════════════════════════════════════

def _calculate_confidence(outcome: str, has_known_fix: bool,
                          execution_time_s: float = None,
                          pattern_matches: int = 0) -> float:
    """Score interaction confidence 0.0–1.0."""
    score = 0.0
    if outcome == "success":
        score += 0.55
    elif outcome == "partial":
        score += 0.30
    if has_known_fix:
        score += 0.20
    if pattern_matches and pattern_matches > 0:
        score += min(0.15, pattern_matches * 0.05)
    if execution_time_s is not None and execution_time_s < 5.0:
        score += 0.10
    return round(min(score, 1.0), 3)


async def _promote_to_knowledge(tenant_id: str, episode: dict, confidence: float):
    """Promote a high-confidence episode to the long-term knowledge_base."""
    db = _get_db()
    if db is None:
        return
    now = datetime.now(timezone.utc)
    pattern_text = extract_pattern("", episode)
    await db.knowledge_base.update_one(
        {
            "tenant_id": tenant_id,
            "pattern_type": episode.get("action_type", ""),
        },
        {
            "$inc": {"success_count": 1, "hit_count": 1},
            "$set": {
                "tenant_id": tenant_id,
                "pattern_type": episode.get("action_type", ""),
                "pattern": pattern_text,
                "action_taken": episode.get("action_taken", ""),
                "confidence": confidence,
                "source": "auto_promote",
                "last_success": now.isoformat(),
                "promoted_at": now.isoformat(),
            },
        },
        upsert=True,
    )
    logger.info(f"[MEMORY] Promoted to knowledge_base: {episode.get('action_type')} (confidence={confidence})")


async def store_interaction(tenant_id: str, run_id: str, action_type: str,
                            action_taken: str, outcome: str,
                            finding_type: str = None,
                            has_known_fix: bool = False,
                            execution_time_s: float = None,
                            error: str = None) -> dict:
    """
    Stage 3 AI Memory Loop — the unified write-after-every-action function.
    1. Write to episodic_memory
    2. Update working_memory context
    3. Auto-promote to knowledge_base if confidence > 0.85
    """
    db = _get_db()
    if db is None:
        return {"stored": False, "reason": "no_db"}

    # Check how many times this pattern succeeded before
    pattern_matches = await db.episodic_memory.count_documents({
        "tenant_id": tenant_id,
        "action_type": action_type,
        "outcome": "success",
    })

    learned_pattern = (
        f"{action_type} effective for {finding_type}"
        if outcome == "success"
        else f"{action_type} failed on {finding_type}: {error or 'unknown'}"
    )

    # 1. EPISODIC MEMORY
    await write_episode(
        tenant_id=tenant_id,
        action_type=action_type,
        action_taken=action_taken,
        outcome=outcome,
        learned_pattern=learned_pattern,
    )
    # Also store query_type for scout read-back
    query_type = classify_query(action_taken)
    db = _get_db()
    if db is not None:
        await db.episodic_memory.update_one(
            {"tenant_id": tenant_id, "action_taken": action_taken,
             "timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()}},
            {"$set": {"query_type": query_type}},
        )

    # 2. WORKING MEMORY
    ctx_summary = summarize_context(action_taken, {
        "action": action_type, "outcome": outcome, "finding_type": finding_type
    })
    await set_working_memory(tenant_id, run_id, {
        "current_pipeline_stage": "store_interaction",
        "context_summary": ctx_summary,
        "last_action": action_type,
        "last_outcome": outcome,
        "last_confidence": None,  # will be set below
        "active_goals": [f"pipeline_{run_id}"],
        "pending_decisions": [] if outcome == "success" else [f"retry_{action_type}"],
    })

    # 3. CONFIDENCE → AUTO-PROMOTE
    confidence = _calculate_confidence(
        outcome=outcome,
        has_known_fix=has_known_fix,
        execution_time_s=execution_time_s,
        pattern_matches=pattern_matches,
    )

    # Write confidence back to working memory
    if db is not None:
        await db.working_memory.update_one(
            {"tenant_id": tenant_id, "session_id": run_id},
            {"$set": {"last_confidence": confidence}},
        )

    promoted = False
    if confidence > 0.85:
        await _promote_to_knowledge(tenant_id, {
            "action_type": action_type,
            "action_taken": action_taken,
            "learned_pattern": learned_pattern,
        }, confidence)
        promoted = True

    # Log the interaction loop
    await db.memory_loop_log.insert_one({
        "tenant_id": tenant_id,
        "run_id": run_id,
        "action_type": action_type,
        "outcome": outcome,
        "confidence": confidence,
        "promoted": promoted,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "stored": True,
        "confidence": confidence,
        "promoted": promoted,
        "pattern_matches": pattern_matches,
    }


async def get_promotions(tenant_id: str = None, limit: int = 20) -> list:
    """Get recent auto-promoted knowledge entries."""
    db = _get_db()
    if db is None:
        return []
    query = {"source": "auto_promote"}
    if tenant_id:
        query["tenant_id"] = tenant_id
    cursor = db.knowledge_base.find(query, {"_id": 0}).sort("promoted_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_memory_loop_stats(tenant_id: str = None) -> dict:
    """Aggregate stats for the store_interaction memory loop."""
    db = _get_db()
    if db is None:
        return {"total_interactions": 0, "promotions": 0, "promotion_rate": 0}
    query = {"tenant_id": tenant_id} if tenant_id else {}
    total = await db.memory_loop_log.count_documents(query)
    promoted = await db.memory_loop_log.count_documents({**query, "promoted": True})
    avg_pipeline = []
    try:
        pipeline = [{"$match": query}] if query else []
        pipeline.append({"$group": {"_id": None, "avg_conf": {"$avg": "$confidence"}}})
        async for doc in db.memory_loop_log.aggregate(pipeline):
            avg_pipeline.append(doc)
    except Exception:
        pass
    avg_confidence = round(avg_pipeline[0]["avg_conf"], 3) if avg_pipeline else 0
    return {
        "total_interactions": total,
        "promotions": promoted,
        "promotion_rate": round((promoted / total * 100) if total > 0 else 0, 1),
        "avg_confidence": avg_confidence,
    }


# ═══════════════════════════════════════
# MEMORY STATS
# ═══════════════════════════════════════

async def get_memory_stats(tenant_id: str = None) -> dict:
    """Dashboard stats for the 3-tier memory system."""
    db = _get_db()
    if db is None:
        return {"tier1": 0, "tier2": 0, "tier3": 0, "plans": 0}
    query = {"tenant_id": tenant_id} if tenant_id else {}
    loop_stats = await get_memory_loop_stats(tenant_id)
    return {
        "tier1_knowledge": await db.known_fixes.count_documents(query) if tenant_id else await db.known_fixes.estimated_document_count(),
        "tier2_working": await db.working_memory.count_documents(query) if tenant_id else await db.working_memory.estimated_document_count(),
        "tier3_episodic": await db.episodic_memory.count_documents(query) if tenant_id else await db.episodic_memory.estimated_document_count(),
        "execution_plans": await db.execution_plans.count_documents(query) if tenant_id else await db.execution_plans.estimated_document_count(),
        "auto_promotions": loop_stats.get("promotions", 0),
        "avg_confidence": loop_stats.get("avg_confidence", 0),
        "total_interactions": loop_stats.get("total_interactions", 0),
        "promotion_rate": loop_stats.get("promotion_rate", 0),
    }


# ═══════════════════════════════════════
# LEARNING VELOCITY
# ═══════════════════════════════════════

async def get_learning_velocity(tenant_id: str = None) -> dict:
    """
    Learning Velocity metrics:
    1. Promotions Today — episodic → knowledge_base in last 24h
    2. Pattern Reuse Rate — % of pipeline runs where Scout found prior success
    3. Compound Score — 7-day rolling (promotions_per_day × reuse_rate) / 100
    Plus 7-day trend arrays for sparklines.
    """
    db = _get_db()
    if db is None:
        return {
            "promotions_today": 0, "reuse_rate": 0, "compound_score": 0,
            "trend_promotions": [], "trend_reuse": [], "trend_compound": [],
        }

    now = datetime.now(timezone.utc)
    trends_promo = []
    trends_reuse = []
    trends_compound = []

    for day_offset in range(6, -1, -1):
        day_start = (now - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_start_iso = day_start.isoformat()
        day_end_iso = day_end.isoformat()

        q_base = {"timestamp": {"$gte": day_start_iso, "$lt": day_end_iso}}
        if tenant_id:
            q_base["tenant_id"] = tenant_id

        # Promotions this day
        day_promos = await db.memory_loop_log.count_documents({**q_base, "promoted": True})
        trends_promo.append(day_promos)

        # Pipeline runs this day (proxy: distinct run_ids in memory_loop_log)
        pipeline_q = {"started_at": {"$gte": day_start_iso, "$lt": day_end_iso}}
        if tenant_id:
            pipeline_q["tenant_id"] = tenant_id
        total_runs = await db.pipeline_runs.count_documents(pipeline_q)

        # Scout memory hits: pipeline runs where scout_memory_recall was non-empty
        # We track this via the scout stage data in pipeline_runs
        scout_hits = 0
        if total_runs > 0:
            try:
                async for run in db.pipeline_runs.find(
                    pipeline_q, {"_id": 0, "stages": 1}
                ).limit(100):
                    stages = run.get("stages", [])
                    for s in stages:
                        if s.get("stage") == "scout" and s.get("data", {}).get("scout_memory_recall"):
                            scout_hits += 1
                            break
            except Exception:
                pass

        day_reuse = round((scout_hits / total_runs * 100) if total_runs > 0 else 0, 1)
        trends_reuse.append(day_reuse)

        day_compound = round((day_promos * day_reuse) / 100, 1) if day_reuse > 0 else 0
        trends_compound.append(day_compound)

    promotions_today = trends_promo[-1] if trends_promo else 0
    reuse_rate = trends_reuse[-1] if trends_reuse else 0
    compound_score = round(sum(trends_compound) / len(trends_compound), 1) if trends_compound else 0

    # Lifetime fallback so the dashboard never looks empty when the 7-day window
    # happens to have no activity but historical data exists.
    lifetime_q = {"tenant_id": tenant_id} if tenant_id else {}
    lifetime_promoted = await db.memory_loop_log.count_documents({**lifetime_q, "promoted": True})
    lifetime_runs = await db.pipeline_runs.count_documents(lifetime_q)
    lifetime_scout_hits = 0
    try:
        async for run in db.pipeline_runs.find(lifetime_q, {"_id": 0, "stages": 1}).limit(500):
            for s in run.get("stages", []):
                if s.get("stage") == "scout" and s.get("data", {}).get("scout_memory_recall"):
                    lifetime_scout_hits += 1
                    break
    except Exception:
        pass
    lifetime_reuse = round((lifetime_scout_hits / lifetime_runs * 100) if lifetime_runs > 0 else 0, 1)

    return {
        "promotions_today": promotions_today,
        "reuse_rate": reuse_rate,
        "compound_score": compound_score,
        "trend_promotions": trends_promo,
        "trend_reuse": trends_reuse,
        "trend_compound": trends_compound,
        "period_days": 7,
        "lifetime_promotions": lifetime_promoted,
        "lifetime_runs": lifetime_runs,
        "lifetime_scout_hits": lifetime_scout_hits,
        "lifetime_reuse_rate": lifetime_reuse,
    }
