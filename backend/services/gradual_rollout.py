"""
Gradual Rollout Service — Gate 3
Canary deployment: 10% → 25% → 50% → 100% with auto-rollback.
"""
import os

import logging
import random
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_db = None

ROLLOUT_STAGES = ["10%", "25%", "50%", "100%"]
STAGE_PCTS = {"10%": 10, "25%": 25, "50%": 50, "100%": 100}
ERROR_THRESHOLD = 0.5  # Rollback if error rate > 0.5%
MIN_DAYS_PER_STAGE = 7


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


def should_use_optimized(tenant_id: str, stage: str) -> bool:
    """
    Determine if THIS specific query should use the optimized pipeline.
    Based on the rollout percentage for the tenant's current stage.
    """
    if stage not in STAGE_PCTS:
        return False
    pct = STAGE_PCTS[stage]
    if pct >= 100:
        return True
    return random.randint(1, 100) <= pct


async def record_query_result(tenant_id: str, used_optimized: bool,
                               success: bool, tokens_used: int = 0,
                               response_time_ms: int = 0) -> None:
    """Record each query result for rollout monitoring."""
    db = _get_db()
    if db is None:
        return

    await db.rollout_metrics.insert_one({
        "tenant_id": tenant_id,
        "used_optimized": used_optimized,
        "success": success,
        "tokens_used": tokens_used,
        "response_time_ms": response_time_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def get_rollout_metrics(tenant_id: str, days: int = 7) -> dict:
    """Get rollout metrics for the current stage window."""
    db = _get_db()
    if db is None:
        return {"error": "db_unavailable"}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    pipeline = [
        {"$match": {"tenant_id": tenant_id, "timestamp": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$used_optimized",
            "total": {"$sum": 1},
            "errors": {"$sum": {"$cond": [{"$eq": ["$success", False]}, 1, 0]}},
            "avg_tokens": {"$avg": "$tokens_used"},
            "avg_response_ms": {"$avg": "$response_time_ms"},
        }}
    ]
    results = await db.rollout_metrics.aggregate(pipeline).to_list(2)

    optimized = next((r for r in results if r["_id"] is True), {})
    original = next((r for r in results if r["_id"] is False), {})

    opt_total = optimized.get("total", 0)
    opt_errors = optimized.get("errors", 0)
    orig_total = original.get("total", 0)
    orig_errors = original.get("errors", 0)

    opt_error_rate = round((opt_errors / opt_total * 100) if opt_total > 0 else 0, 2)
    orig_error_rate = round((orig_errors / orig_total * 100) if orig_total > 0 else 0, 2)

    return {
        "tenant_id": tenant_id,
        "period_days": days,
        "optimized": {
            "total_queries": opt_total,
            "errors": opt_errors,
            "error_rate": opt_error_rate,
            "avg_tokens": round(optimized.get("avg_tokens", 0), 1),
            "avg_response_ms": round(optimized.get("avg_response_ms", 0), 1),
        },
        "original": {
            "total_queries": orig_total,
            "errors": orig_errors,
            "error_rate": orig_error_rate,
            "avg_tokens": round(original.get("avg_tokens", 0), 1),
            "avg_response_ms": round(original.get("avg_response_ms", 0), 1),
        },
        "should_rollback": opt_error_rate > ERROR_THRESHOLD,
        "can_advance": opt_error_rate < 0.1 and opt_total >= 20,
    }


async def check_stage_advancement(tenant_id: str) -> dict:
    """
    Check if tenant should advance to the next rollout stage.
    Called by Sentinel or manually.
    """
    db = _get_db()
    if db is None:
        return {"action": "skip", "reason": "db_unavailable"}

    profile = await db.tenant_optimization_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    if not profile:
        return {"action": "skip", "reason": "no_profile"}

    stage = profile.get("optimization_stage", "")
    if stage not in ROLLOUT_STAGES:
        return {"action": "skip", "reason": f"not_in_rollout (stage={stage})"}

    # Check minimum time in stage
    advanced_at = profile.get("stage_advanced_at") or profile.get("shadow_completed_at")
    if advanced_at:
        days_in_stage = (datetime.now(timezone.utc) - datetime.fromisoformat(advanced_at)).days
        if days_in_stage < MIN_DAYS_PER_STAGE:
            return {
                "action": "wait",
                "reason": f"Only {days_in_stage}/{MIN_DAYS_PER_STAGE} days in {stage} stage",
                "days_remaining": MIN_DAYS_PER_STAGE - days_in_stage,
            }

    metrics = await get_rollout_metrics(tenant_id)

    # Rollback check
    if metrics.get("should_rollback"):
        await db.tenant_optimization_profiles.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "optimization_enabled": False,
                "optimization_stage": "rolled_back",
                "rollback_at": datetime.now(timezone.utc).isoformat(),
                "rollback_reasons": [f"Error rate {metrics['optimized']['error_rate']}% exceeded {ERROR_THRESHOLD}% at {stage}"],
            }}
        )
        # WhatsApp alert
        try:
            from services.twilio_service import send_whatsapp_message
            import asyncio
            asyncio.create_task(send_whatsapp_message(
                os.environ.get("ADMIN_ALERT_PHONE", os.environ.get("FOUNDER_PHONE", "")),
                f"*AUREM Rollback*\nTenant `{tenant_id}` rolled back from {stage}.\nError rate: {metrics['optimized']['error_rate']}%"
            ))
        except Exception:
            pass

        logger.warning(f"[GATE3] Rollback for {tenant_id} at {stage}: error_rate={metrics['optimized']['error_rate']}%")
        return {"action": "rollback", "stage": stage, "metrics": metrics}

    # Advancement check
    if metrics.get("can_advance"):
        current_idx = ROLLOUT_STAGES.index(stage)
        if current_idx < len(ROLLOUT_STAGES) - 1:
            next_stage = ROLLOUT_STAGES[current_idx + 1]
            await db.tenant_optimization_profiles.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "optimization_stage": next_stage,
                    "stage_advanced_at": datetime.now(timezone.utc).isoformat(),
                    "optimization_enabled": True,
                    f"rollout_{stage}_metrics": {
                        "error_rate": metrics["optimized"]["error_rate"],
                        "queries": metrics["optimized"]["total_queries"],
                    }
                }}
            )
            logger.info(f"[GATE3] Advanced {tenant_id}: {stage} -> {next_stage}")
            return {"action": "advanced", "from": stage, "to": next_stage, "metrics": metrics}
        else:
            # Already at 100%, promote to monitoring
            await db.tenant_optimization_profiles.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "optimization_stage": "monitoring",
                    "fully_deployed_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            logger.info(f"[GATE3] {tenant_id} fully deployed -> monitoring")
            return {"action": "fully_deployed", "metrics": metrics}

    return {"action": "hold", "stage": stage, "metrics": metrics, "reason": "Insufficient data or error rate not low enough"}


async def get_rollout_timeline(tenant_id: str) -> dict:
    """Get full rollout timeline for a tenant."""
    db = _get_db()
    if db is None:
        return {"error": "db_unavailable"}

    profile = await db.tenant_optimization_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    if not profile:
        return {"error": "no_profile"}

    timeline = []
    if profile.get("profiled_at"):
        timeline.append({"stage": "profiled", "at": profile["profiled_at"], "status": "completed"})
    if profile.get("shadow_completed_at"):
        timeline.append({"stage": "shadow", "at": profile["shadow_completed_at"], "status": "completed"})
    for pct in ["10%", "25%", "50%", "100%"]:
        metrics_key = f"rollout_{pct}_metrics"
        if profile.get(metrics_key):
            timeline.append({"stage": pct, "status": "completed", "metrics": profile[metrics_key]})
    if profile.get("fully_deployed_at"):
        timeline.append({"stage": "monitoring", "at": profile["fully_deployed_at"], "status": "active"})
    if profile.get("rollback_at"):
        timeline.append({"stage": "rolled_back", "at": profile["rollback_at"], "reasons": profile.get("rollback_reasons", [])})

    current = profile.get("optimization_stage", "not_started")
    current_metrics = await get_rollout_metrics(tenant_id) if current in ROLLOUT_STAGES else {}

    return {
        "tenant_id": tenant_id,
        "current_stage": current,
        "timeline": timeline,
        "current_metrics": current_metrics,
        "optimization_enabled": profile.get("optimization_enabled", False),
    }
