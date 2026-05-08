"""
Tenant Profiling Service — Gate 1
Profiles tenants for optimization risk scoring before applying token reduction.
Zero-risk observation only.
"""
import os

import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional

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


# PII patterns that must NEVER be compressed
PII_KEYWORDS = [
    "email", "phone", "address", "credit card", "ssn", "sin",
    "password", "social insurance", "social security", "date of birth",
    "bank account", "routing number", "health card", "medical",
    "prescription", "diagnosis", "legal", "lawsuit", "contract",
    "payment", "invoice", "order #", "tracking number",
]


def detect_pii_content(text: str) -> bool:
    """Check if text contains PII that must NOT be compressed."""
    lower = text.lower()
    return any(kw in lower for kw in PII_KEYWORDS)


async def measure_avg_tokens(tenant_id: str, window_days: int = 7) -> dict:
    """Measure average tokens per call from usage_tracking over last N days."""
    db = _get_db()
    if db is None:
        return {"avg_tokens": 0, "total_calls": 0, "total_tokens": 0}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

    pipeline = [
        {"$match": {"tenant_id": tenant_id, "timestamp": {"$gte": cutoff}}},
        {"$group": {
            "_id": None,
            "total_calls": {"$sum": 1},
            "total_tokens": {"$sum": {"$ifNull": ["$tokens_used", 0]}},
            "total_input": {"$sum": {"$ifNull": ["$input_tokens", 0]}},
            "total_output": {"$sum": {"$ifNull": ["$output_tokens", 0]}},
        }}
    ]
    result = await db.usage_tracking.aggregate(pipeline).to_list(1)
    if not result:
        return {"avg_tokens": 0, "total_calls": 0, "total_tokens": 0}

    r = result[0]
    total_calls = r.get("total_calls", 0)
    total_tokens = r.get("total_tokens", 0) or (r.get("total_input", 0) + r.get("total_output", 0))
    avg = total_tokens / total_calls if total_calls > 0 else 0

    return {
        "avg_tokens": round(avg, 1),
        "total_calls": total_calls,
        "total_tokens": total_tokens,
    }


async def classify_query_patterns(tenant_id: str) -> dict:
    """Classify common query types from audit_trail."""
    db = _get_db()
    if db is None:
        return {"patterns": {}, "cacheable_rate": 0}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    queries = await db.audit_trail.find(
        {"tenant_id": tenant_id, "timestamp": {"$gte": cutoff}},
        {"_id": 0, "action": 1, "query_type": 1, "intent": 1}
    ).to_list(500)

    patterns = {}
    for q in queries:
        action = q.get("action") or q.get("query_type") or q.get("intent", "unknown")
        patterns[action] = patterns.get(action, 0) + 1

    # Estimate cacheable rate: repeated identical queries
    query_hashes = []
    raw_queries = await db.audit_trail.find(
        {"tenant_id": tenant_id, "timestamp": {"$gte": cutoff}},
        {"_id": 0, "input": 1, "query": 1, "message": 1}
    ).to_list(500)

    for q in raw_queries:
        text = q.get("input") or q.get("query") or q.get("message", "")
        if text:
            query_hashes.append(hashlib.sha256(text.encode()).hexdigest())

    total = len(query_hashes)
    unique = len(set(query_hashes))
    cacheable_rate = round(((total - unique) / total * 100) if total > 0 else 0, 1)

    return {"patterns": patterns, "cacheable_rate": cacheable_rate}


async def find_peak_hours(tenant_id: str) -> dict:
    """Find peak usage hours for deployment window planning."""
    db = _get_db()
    if db is None:
        return {"peak_hours": [], "quiet_hours": [2, 3, 4], "timezone_guess": "America/Toronto"}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    pipeline = [
        {"$match": {"tenant_id": tenant_id, "timestamp": {"$gte": cutoff}}},
        {"$addFields": {
            "ts_date": {"$dateFromString": {"dateString": "$timestamp", "onError": None}}
        }},
        {"$match": {"ts_date": {"$ne": None}}},
        {"$group": {
            "_id": {"$hour": "$ts_date"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]
    result = await db.usage_tracking.aggregate(pipeline).to_list(24)

    hour_counts = {r["_id"]: r["count"] for r in result}
    peak_hours = sorted(hour_counts, key=hour_counts.get, reverse=True)[:6]
    all_hours = set(range(24))
    quiet_hours = sorted(all_hours - set(peak_hours))[:6]

    return {
        "peak_hours": peak_hours,
        "quiet_hours": quiet_hours if quiet_hours else [2, 3, 4],
        "hourly_distribution": hour_counts,
    }


async def check_site_sensitivity(tenant_id: str) -> dict:
    """Check if tenant has live e-commerce, orders, or sensitive data."""
    db = _get_db()
    if db is None:
        return {"has_live_orders": False, "has_custom_integrations": False, "sensitivity": "low"}

    # Check for live orders in last 7 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    live_orders = await db.orders.count_documents({
        "tenant_id": tenant_id,
        "created_at": {"$gte": cutoff},
        "status": {"$in": ["pending", "processing", "shipped"]}
    })

    # Check for custom integrations
    integrations = await db.api_keys.count_documents({"tenant_id": tenant_id})

    # Check for connected external services
    ext_services = await db.tenant_integrations.count_documents({"tenant_id": tenant_id}) if "tenant_integrations" in await db.list_collection_names() else 0

    has_live = live_orders > 0
    has_custom = integrations > 2 or ext_services > 0

    sensitivity = "low"
    if has_live and has_custom:
        sensitivity = "high"
    elif has_live or has_custom:
        sensitivity = "medium"

    return {
        "has_live_orders": has_live,
        "live_order_count": live_orders,
        "has_custom_integrations": has_custom,
        "integration_count": integrations,
        "sensitivity": sensitivity,
    }


def calculate_risk_score(token_data: dict, patterns: dict, sensitivity: dict) -> dict:
    """
    Calculate optimization risk score 0-10.
    GREEN (0-3): auto-deploy allowed
    YELLOW (4-6): deploy with monitoring
    RED (7-10): human approval required
    """
    score = 0
    factors = []

    # Active e-commerce (live orders): +3
    if sensitivity.get("has_live_orders"):
        score += 3
        factors.append("Active e-commerce (+3)")

    # High query volume (>500/day): +2
    daily_calls = token_data.get("total_calls", 0) / 7
    if daily_calls > 500:
        score += 2
        factors.append(f"High volume: {daily_calls:.0f}/day (+2)")
    elif daily_calls > 200:
        score += 1
        factors.append(f"Moderate volume: {daily_calls:.0f}/day (+1)")

    # Custom integrations: +2
    if sensitivity.get("has_custom_integrations"):
        score += 2
        factors.append("Custom integrations (+2)")

    # Low cacheable rate means optimization harder: +1
    if patterns.get("cacheable_rate", 0) < 10:
        score += 1
        factors.append(f"Low cache potential: {patterns.get('cacheable_rate', 0)}% (+1)")

    # Simple blog/info site: -2
    if not sensitivity.get("has_live_orders") and not sensitivity.get("has_custom_integrations"):
        score -= 2
        factors.append("Simple site (-2)")

    score = max(0, min(10, score))

    if score <= 3:
        classification = "GREEN"
    elif score <= 6:
        classification = "YELLOW"
    else:
        classification = "RED"

    return {
        "score": score,
        "classification": classification,
        "factors": factors,
        "auto_deploy_allowed": classification == "GREEN",
        "needs_human_approval": classification == "RED",
    }


async def profile_tenant(tenant_id: str) -> dict:
    """
    Full tenant profiling for optimization readiness.
    GATE 1: Observe only, zero risk.
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available", "tenant_id": tenant_id}

    token_data = await measure_avg_tokens(tenant_id)
    patterns = await classify_query_patterns(tenant_id)
    peak_data = await find_peak_hours(tenant_id)
    sensitivity = await check_site_sensitivity(tenant_id)
    risk = calculate_risk_score(token_data, patterns, sensitivity)

    profile = {
        "tenant_id": tenant_id,
        "profiled_at": datetime.now(timezone.utc).isoformat(),
        "avg_tokens_per_call": token_data["avg_tokens"],
        "total_calls_7d": token_data["total_calls"],
        "total_tokens_7d": token_data["total_tokens"],
        "query_patterns": patterns["patterns"],
        "cache_candidate_rate": patterns["cacheable_rate"],
        "peak_usage_hours": peak_data["peak_hours"],
        "quiet_hours": peak_data["quiet_hours"],
        "site_sensitivity": sensitivity["sensitivity"],
        "has_live_orders": sensitivity["has_live_orders"],
        "has_custom_integrations": sensitivity["has_custom_integrations"],
        "risk_score": risk["score"],
        "risk_classification": risk["classification"],
        "risk_factors": risk["factors"],
        "auto_deploy_allowed": risk["auto_deploy_allowed"],
        "needs_human_approval": risk["needs_human_approval"],
        "optimization_stage": "profiled",
        "optimization_enabled": False,
    }

    # Upsert into MongoDB
    await db.tenant_optimization_profiles.update_one(
        {"tenant_id": tenant_id},
        {"$set": profile},
        upsert=True
    )

    # RED risk: send WhatsApp alert
    if risk["classification"] == "RED":
        try:
            from services.twilio_service import send_whatsapp_message
            msg = (
                f"*AUREM Optimization Alert*\n\n"
                f"Tenant `{tenant_id}` scored RED (risk: {risk['score']}/10)\n"
                f"Factors: {', '.join(risk['factors'])}\n"
                f"Human approval required before optimization."
            )
            await send_whatsapp_message(
                os.environ.get("ADMIN_ALERT_PHONE", os.environ.get("FOUNDER_PHONE", "")), msg)
        except Exception as e:
            logger.warning(f"WhatsApp alert failed for RED tenant {tenant_id}: {e}")

    logger.info(f"[GATE1] Profiled tenant {tenant_id}: risk={risk['score']} ({risk['classification']})")
    return profile


async def profile_all_tenants() -> dict:
    """Profile all active tenants. Safe batch operation."""
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}

    # Get unique tenant IDs from usage_tracking
    tenant_ids = await db.usage_tracking.distinct("tenant_id")
    if not tenant_ids:
        # Fallback: check users for tenant_id
        users = await db.users.find({}, {"_id": 0, "tenant_id": 1}).to_list(100)
        tenant_ids = list(set(u.get("tenant_id") for u in users if u.get("tenant_id")))

    results = {"profiled": 0, "green": 0, "yellow": 0, "red": 0, "errors": 0}

    for tid in tenant_ids:
        if not tid:
            continue
        try:
            profile = await profile_tenant(tid)
            results["profiled"] += 1
            cls = profile.get("risk_classification", "").lower()
            if cls in results:
                results[cls] += 1
        except Exception as e:
            logger.error(f"[GATE1] Failed to profile {tid}: {e}")
            results["errors"] += 1

    return results
