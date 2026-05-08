"""
Optimization Monitor — Gate 4
Continuous per-tenant monitoring after optimization deployment.
Tracks cache hits, token savings, response quality, error rates.
"""

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
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


async def get_tenant_optimization_metrics(tenant_id: str, window_days: int = 30) -> dict:
    """Get optimization metrics for a tenant over the last N days."""
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

    # Cache hit rate from semantic_cache
    cache_pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {"$group": {
            "_id": None,
            "total_entries": {"$sum": 1},
            "total_hits": {"$sum": "$hit_count"},
        }}
    ]
    cache_result = await db.semantic_cache.aggregate(cache_pipeline).to_list(1)
    cache_data = cache_result[0] if cache_result else {}
    total_hits = cache_data.get("total_hits", 0)
    total_entries = cache_data.get("total_entries", 0)

    # Token usage from usage_tracking
    usage_pipeline = [
        {"$match": {"tenant_id": tenant_id, "timestamp": {"$gte": cutoff}}},
        {"$group": {
            "_id": None,
            "total_calls": {"$sum": 1},
            "total_tokens": {"$sum": {"$ifNull": ["$tokens_used", 0]}},
            "cached_calls": {"$sum": {"$cond": [{"$eq": ["$from_cache", True]}, 1, 0]}},
            "errors": {"$sum": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}},
        }}
    ]
    usage_result = await db.usage_tracking.aggregate(usage_pipeline).to_list(1)
    usage_data = usage_result[0] if usage_result else {}

    total_calls = usage_data.get("total_calls", 0)
    cached_calls = usage_data.get("cached_calls", 0)
    errors = usage_data.get("errors", 0)
    total_tokens = usage_data.get("total_tokens", 0)

    # Get baseline (pre-optimization tokens if available)
    profile = await db.tenant_optimization_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    baseline_avg = profile.get("avg_tokens_per_call", 0) if profile else 0
    current_avg = total_tokens / total_calls if total_calls > 0 else 0

    tokens_saved_pct = round(((baseline_avg - current_avg) / baseline_avg * 100) if baseline_avg > 0 else 0, 1)
    cache_hit_rate = round((cached_calls / total_calls * 100) if total_calls > 0 else 0, 1)
    error_rate = round((errors / total_calls * 100) if total_calls > 0 else 0, 2)

    # Estimated cost saved (assuming $0.002 per 1K tokens for GPT-4o-mini)
    tokens_saved = max(0, (baseline_avg - current_avg) * total_calls)
    cost_saved = round(tokens_saved / 1000 * 0.002, 2)

    return {
        "tenant_id": tenant_id,
        "period_days": window_days,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "cache_hit_rate": cache_hit_rate,
        "cache_entries": total_entries,
        "cache_total_hits": total_hits,
        "total_calls": total_calls,
        "cached_calls": cached_calls,
        "total_tokens": total_tokens,
        "avg_tokens_per_call": round(current_avg, 1),
        "baseline_avg_tokens": baseline_avg,
        "tokens_saved_pct": tokens_saved_pct,
        "tokens_saved_total": round(tokens_saved),
        "estimated_cost_saved": cost_saved,
        "error_rate": error_rate,
        "error_count": errors,
        "health": "healthy" if error_rate < 0.5 else ("degraded" if error_rate < 2 else "critical"),
    }


async def check_rollback_needed(tenant_id: str) -> dict:
    """Check if optimization should be rolled back for this tenant."""
    metrics = await get_tenant_optimization_metrics(tenant_id, window_days=1)

    should_rollback = False
    reasons = []

    # Error rate > 0.5% triggers rollback
    if metrics.get("error_rate", 0) > 0.5:
        should_rollback = True
        reasons.append(f"Error rate {metrics['error_rate']}% exceeds 0.5% threshold")

    # Token usage INCREASED (negative savings)
    if metrics.get("tokens_saved_pct", 0) < -10:
        should_rollback = True
        reasons.append(f"Token usage increased by {abs(metrics['tokens_saved_pct'])}%")

    # Cache hit rate too low after 7+ days of optimization
    profile = await _get_db().tenant_optimization_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "optimization_stage": 1, "optimization_started_at": 1}
    ) if _get_db() else None

    if profile and profile.get("optimization_started_at"):
        started = datetime.fromisoformat(profile["optimization_started_at"])
        days_active = (datetime.now(timezone.utc) - started).days
        if days_active > 7 and metrics.get("cache_hit_rate", 0) < 5:
            reasons.append(f"Cache hit rate only {metrics['cache_hit_rate']}% after {days_active} days")

    return {
        "tenant_id": tenant_id,
        "should_rollback": should_rollback,
        "reasons": reasons,
        "current_metrics": metrics,
    }


async def generate_monthly_report(tenant_id: str) -> dict:
    """Generate monthly optimization report for a tenant."""
    metrics = await get_tenant_optimization_metrics(tenant_id, window_days=30)
    db = _get_db()

    profile = await db.tenant_optimization_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    ) if db is not None else None

    stage = profile.get("optimization_stage", "not_started") if profile else "not_started"
    risk = profile.get("risk_classification", "N/A") if profile else "N/A"

    quality_score = 10
    if metrics.get("error_rate", 0) > 0:
        quality_score -= min(3, int(metrics["error_rate"] * 10))
    if metrics.get("tokens_saved_pct", 0) < 0:
        quality_score -= 2
    if metrics.get("cache_hit_rate", 0) < 15:
        quality_score -= 1
    quality_score = max(1, quality_score)

    report = {
        "tenant_id": tenant_id,
        "report_month": datetime.now(timezone.utc).strftime("%B %Y"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "risk_classification": risk,
        "tokens_saved_total": metrics.get("tokens_saved_total", 0),
        "tokens_saved_pct": metrics.get("tokens_saved_pct", 0),
        "cache_hit_rate": metrics.get("cache_hit_rate", 0),
        "response_quality_score": quality_score,
        "estimated_cost_saved": metrics.get("estimated_cost_saved", 0),
        "total_calls": metrics.get("total_calls", 0),
        "status": "Healthy" if metrics.get("health") == "healthy" else "Needs Review",
    }

    # Store report
    if db is not None:
        await db.tenant_optimization_reports.insert_one({
            **report,
            "type": "monthly_report",
        })

    return report


async def get_optimization_dashboard_summary() -> dict:
    """Get aggregate summary for the admin optimization dashboard."""
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}

    profiles = await db.tenant_optimization_profiles.find(
        {}, {"_id": 0}
    ).to_list(500)

    stages = {}
    risk_counts = {"GREEN": 0, "YELLOW": 0, "RED": 0}
    total_savings = 0
    total_tokens_saved = 0

    for p in profiles:
        stage = p.get("optimization_stage", "not_started")
        stages[stage] = stages.get(stage, 0) + 1
        risk = p.get("risk_classification", "GREEN")
        if risk in risk_counts:
            risk_counts[risk] += 1

    # Get aggregate token savings
    pipeline = [
        {"$group": {
            "_id": None,
            "total_hits": {"$sum": "$hit_count"},
            "total_entries": {"$sum": 1},
        }}
    ]
    cache_agg = await db.semantic_cache.aggregate(pipeline).to_list(1)
    if cache_agg:
        total_tokens_saved = cache_agg[0].get("total_hits", 0) * 200  # est. 200 tokens per cache hit

    # Estimate cost saved
    total_savings = round(total_tokens_saved / 1000 * 0.002, 2)

    return {
        "total_tenants_profiled": len(profiles),
        "stage_counts": stages,
        "risk_distribution": risk_counts,
        "total_tokens_saved_estimate": total_tokens_saved,
        "total_cost_saved_estimate": total_savings,
        "tenants_fully_optimized": stages.get("monitoring", 0) + stages.get("100%", 0),
        "tenants_in_shadow": stages.get("shadow", 0),
        "tenants_blocked": sum(1 for p in profiles if p.get("optimization_stage") == "blocked"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def run_sentinel_optimization_check():
    """
    Called from Sentinel cycle — checks all optimized tenants for issues.
    Returns list of tenants needing attention.
    """
    db = _get_db()
    if db is None:
        return []

    optimized = await db.tenant_optimization_profiles.find(
        {"optimization_enabled": True}, {"_id": 0, "tenant_id": 1}
    ).to_list(100)

    alerts = []
    for p in optimized:
        tid = p.get("tenant_id")
        if not tid:
            continue
        check = await check_rollback_needed(tid)
        if check.get("should_rollback"):
            alerts.append({
                "tenant_id": tid,
                "action": "rollback_recommended",
                "reasons": check["reasons"],
            })
            # Auto-disable optimization
            await db.tenant_optimization_profiles.update_one(
                {"tenant_id": tid},
                {"$set": {
                    "optimization_enabled": False,
                    "optimization_stage": "rolled_back",
                    "rollback_at": datetime.now(timezone.utc).isoformat(),
                    "rollback_reasons": check["reasons"],
                }}
            )
            logger.warning(f"[GATE4] Auto-rollback for tenant {tid}: {check['reasons']}")

    return alerts
