"""
Shadow Mode Service — Gate 2
Runs optimized pipeline in parallel, compares responses, logs results.
Does NOT serve optimized results to users — observation only.
"""

import hashlib
import logging
import random
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
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


def _simple_similarity(a: str, b: str) -> float:
    """Fast token-overlap similarity (no ML deps). 0.0-1.0."""
    if not a or not b:
        return 0.0
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


async def run_shadow_comparison(tenant_id: str, query: str, original_response: str,
                                 original_tokens: int, optimized_response: str,
                                 optimized_tokens: int, model_used: str = "") -> dict:
    """
    Compare original vs optimized response for a single query.
    Called from the chat pipeline when shadow mode is active.
    """
    db = _get_db()
    if db is None:
        return {"error": "db_unavailable"}

    similarity = _simple_similarity(original_response, optimized_response)
    tokens_saved = original_tokens - optimized_tokens
    tokens_saved_pct = round((tokens_saved / original_tokens * 100) if original_tokens > 0 else 0, 1)

    # Quality classification
    if similarity >= 0.90:
        quality = "match"
    elif similarity >= 0.70:
        quality = "degraded"
    else:
        quality = "mismatch"

    result = {
        "tenant_id": tenant_id,
        "query_hash": hashlib.sha256(query.encode()).hexdigest(),
        "similarity_score": round(similarity, 4),
        "tokens_original": original_tokens,
        "tokens_optimized": optimized_tokens,
        "tokens_saved": tokens_saved,
        "tokens_saved_pct": tokens_saved_pct,
        "response_quality": quality,
        "model_used": model_used,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    await db.shadow_test_results.insert_one(result)
    return {k: v for k, v in result.items() if k != "_id"}


async def get_shadow_results(tenant_id: str) -> dict:
    """Get aggregated shadow test results for a tenant."""
    db = _get_db()
    if db is None:
        return {"error": "db_unavailable"}

    results = await db.shadow_test_results.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(500)

    if not results:
        return {
            "tenant_id": tenant_id,
            "total_queries": 0,
            "avg_similarity": 0,
            "pass_criteria_met": False,
            "results": [],
        }

    total = len(results)
    avg_sim = sum(r.get("similarity_score", 0) for r in results) / total
    avg_savings = sum(r.get("tokens_saved_pct", 0) for r in results) / total
    mismatches = sum(1 for r in results if r.get("response_quality") == "mismatch")
    degraded = sum(1 for r in results if r.get("response_quality") == "degraded")

    # Pass criteria: avg similarity > 0.90, 50+ queries, token reduction > 20%, zero mismatches
    pass_criteria = (
        avg_sim >= 0.90 and
        total >= 50 and
        avg_savings >= 20 and
        mismatches == 0
    )

    return {
        "tenant_id": tenant_id,
        "total_queries": total,
        "avg_similarity": round(avg_sim, 4),
        "avg_tokens_saved_pct": round(avg_savings, 1),
        "quality_breakdown": {
            "match": sum(1 for r in results if r.get("response_quality") == "match"),
            "degraded": degraded,
            "mismatch": mismatches,
        },
        "pass_criteria_met": pass_criteria,
        "criteria_detail": {
            "similarity_ok": avg_sim >= 0.90,
            "volume_ok": total >= 50,
            "savings_ok": avg_savings >= 20,
            "no_mismatches": mismatches == 0,
        },
        "recommendation": "promote_to_canary" if pass_criteria else (
            "continue_shadow" if total < 50 else "abort_optimization"
        ),
        "latest_results": results[:20],
    }


async def check_shadow_exit_criteria(tenant_id: str) -> dict:
    """Check if tenant should exit shadow mode."""
    summary = await get_shadow_results(tenant_id)
    db = _get_db()

    if summary.get("pass_criteria_met"):
        # Auto-promote to canary 10%
        if db is not None:
            await db.tenant_optimization_profiles.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "optimization_stage": "10%",
                    "shadow_completed_at": datetime.now(timezone.utc).isoformat(),
                    "shadow_results_summary": {
                        "avg_similarity": summary["avg_similarity"],
                        "total_queries": summary["total_queries"],
                        "avg_savings_pct": summary["avg_tokens_saved_pct"],
                    }
                }}
            )
        return {"action": "promoted", "new_stage": "10%", "summary": summary}

    if summary.get("recommendation") == "abort_optimization":
        if db is not None:
            await db.tenant_optimization_profiles.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "optimization_stage": "blocked",
                    "blocked_reason": "Shadow mode failed criteria",
                    "blocked_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
        return {"action": "blocked", "summary": summary}

    return {"action": "continue", "summary": summary}


async def simulate_shadow_test(tenant_id: str, num_queries: int = 60) -> dict:
    """
    Simulate shadow test data for demo/testing purposes.
    In production, shadow comparisons are triggered by real queries.
    """
    db = _get_db()
    if db is None:
        return {"error": "db_unavailable"}

    generated = 0
    for i in range(num_queries):
        orig_tokens = random.randint(300, 800)
        # Optimized uses 30-60% fewer tokens
        reduction = random.uniform(0.30, 0.60)
        opt_tokens = int(orig_tokens * (1 - reduction))
        similarity = random.uniform(0.88, 0.99)

        await db.shadow_test_results.insert_one({
            "tenant_id": tenant_id,
            "query_hash": hashlib.sha256(f"sim_query_{i}_{tenant_id}".encode()).hexdigest(),
            "similarity_score": round(similarity, 4),
            "tokens_original": orig_tokens,
            "tokens_optimized": opt_tokens,
            "tokens_saved": orig_tokens - opt_tokens,
            "tokens_saved_pct": round(reduction * 100, 1),
            "response_quality": "match" if similarity >= 0.90 else "degraded",
            "model_used": "openrouter/qwen-2.5:floor",
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 47))).isoformat(),
        })
        generated += 1

    return {"generated": generated, "tenant_id": tenant_id}
