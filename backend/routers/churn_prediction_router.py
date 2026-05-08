"""
AUREM Churn Prediction Router — Layer 9 Intelligence
Predicts client churn risk based on usage patterns, plan activity, and engagement.
Wired to Sentinel Dashboard for real-time risk monitoring.
Adapted from legacy e-commerce churn → now uses tenant_customers + usage data.
"""
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/churn", tags=["Churn Prediction"])
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


def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET")
        payload = jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


def _get_retention_action(risk_level: str, plan: str) -> str:
    """AUREM-specific retention recommendations."""
    actions = {
        "critical": {
            "enterprise": "CEO personal call + 3-month price lock + dedicated onboarding session",
            "growth": "Send personalized win-back email with 1 month free + demo of new features",
            "starter": "ORA outbound call with free Growth upgrade trial (30 days)",
        },
        "high": {
            "enterprise": "Schedule executive review meeting + share ROI report",
            "growth": "Send feature adoption email + ORA check-in call",
            "starter": "Send website scan report showing improvements since signup",
        },
        "medium": {
            "default": "Schedule ORA engagement email with usage tips + case studies",
        },
        "low": {
            "default": "Add to monthly newsletter + feature announcement list",
        },
    }
    level_actions = actions.get(risk_level, actions["low"])
    return level_actions.get(plan, level_actions.get("default", "Monitor — no action needed"))


# ══════════════════════════════════════════════
# At-Risk Clients
# ══════════════════════════════════════════════

@router.get("/at-risk")
async def get_at_risk_clients(request: Request):
    """Get AUREM clients at risk of churning based on usage and activity patterns."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    now = datetime.now(timezone.utc)
    at_risk = []

    # Get all active clients
    clients = await _get_db().tenant_customers.find(
        {"is_active": True, "is_self_client": {"$ne": True}},
        {"_id": 0}
    ).to_list(500)

    for client in clients:
        # Calculate risk signals
        last_active_str = client.get("last_active", "")
        joined_str = client.get("joined_date", "")

        try:
            last_active = datetime.fromisoformat(last_active_str.replace("Z", "+00:00")) if last_active_str else now - timedelta(days=999)
        except Exception:
            last_active = now - timedelta(days=999)

        days_inactive = (now - last_active).days
        usage = client.get("usage", {})
        actions_used = usage.get("actions_used", 0)
        actions_limit = usage.get("actions_limit", 500)
        usage_pct = round(actions_used / max(actions_limit, 1) * 100, 1)
        plan = client.get("plan", "starter")
        perf = client.get("performance", {})
        automations = perf.get("automations_run", 0)

        # Risk scoring
        risk_score = 0.0
        factors = []

        # Inactivity
        if days_inactive > 14:
            risk_score += min(0.4, days_inactive / 60)
            factors.append(f"Inactive for {days_inactive} days")
        if days_inactive > 30:
            factors.append("No login in 30+ days")

        # Low usage
        if usage_pct < 10 and actions_limit > 0:
            risk_score += 0.25
            factors.append(f"Only {usage_pct}% of plan used")
        elif usage_pct < 25:
            risk_score += 0.1

        # No automations
        if automations == 0:
            risk_score += 0.15
            factors.append("Zero automations run")

        # No website scanned
        if perf.get("total_scans", 0) == 0:
            risk_score += 0.1
            factors.append("Never scanned website")

        risk_score = min(1.0, risk_score)

        if risk_score >= 0.2:
            risk_level = "critical" if risk_score >= 0.7 else "high" if risk_score >= 0.5 else "medium" if risk_score >= 0.3 else "low"
            at_risk.append({
                "tenant_id": client.get("tenant_id", ""),
                "company_name": client.get("company_name", "Unknown"),
                "email": client.get("email", ""),
                "plan": plan,
                "plan_price_cad": client.get("plan_price_cad", 0),
                "days_inactive": days_inactive,
                "usage_percent": usage_pct,
                "risk_score": round(risk_score, 2),
                "risk_level": risk_level,
                "risk_factors": factors,
                "recommended_action": _get_retention_action(risk_level, plan),
                "last_active": last_active_str,
                "revenue_at_risk_cad": client.get("plan_price_cad", 0),
            })

    # Sort by risk score descending
    at_risk.sort(key=lambda x: x["risk_score"], reverse=True)

    total_revenue_at_risk = sum(c["revenue_at_risk_cad"] for c in at_risk if c["risk_level"] in ("critical", "high"))

    return {
        "at_risk_clients": at_risk,
        "total_at_risk": len(at_risk),
        "critical_count": sum(1 for c in at_risk if c["risk_level"] == "critical"),
        "high_count": sum(1 for c in at_risk if c["risk_level"] == "high"),
        "medium_count": sum(1 for c in at_risk if c["risk_level"] == "medium"),
        "revenue_at_risk_cad": total_revenue_at_risk,
    }


# ══════════════════════════════════════════════
# Predict Single Client
# ══════════════════════════════════════════════

@router.get("/predict/{tenant_id}")
async def predict_churn(tenant_id: str, request: Request):
    """AI-powered churn prediction for a specific client."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    client = await _get_db().tenant_customers.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not client:
        raise HTTPException(404, "Client not found")

    usage = client.get("usage", {})
    perf = client.get("performance", {})
    plan = client.get("plan", "starter")

    now = datetime.now(timezone.utc)
    last_active_str = client.get("last_active", "")
    try:
        last_active = datetime.fromisoformat(last_active_str.replace("Z", "+00:00")) if last_active_str else now - timedelta(days=999)
    except Exception:
        last_active = now - timedelta(days=999)
    days_inactive = (now - last_active).days

    metrics = {
        "days_inactive": days_inactive,
        "plan": plan,
        "plan_price_cad": client.get("plan_price_cad", 0),
        "actions_used": usage.get("actions_used", 0),
        "actions_limit": usage.get("actions_limit", 500),
        "automations_run": perf.get("automations_run", 0),
        "total_scans": perf.get("total_scans", 0),
        "leads_found": perf.get("leads_found", 0),
        "issues_fixed": perf.get("issues_fixed", 0),
    }

    # Try LLM prediction
    try:
        from emergentintegrations.llm.chat import ChatLLM, UserMessage
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if api_key:
            chat = ChatLLM(
                api_key=api_key, model="gpt-4o-mini",
                system_message=(
                    "You are AUREM's churn prediction AI for a B2B SaaS platform. "
                    "Analyze client usage data and predict churn probability. "
                    "Respond ONLY in JSON: "
                    '{"churn_probability": 0.0-1.0, "risk_level": "low|medium|high|critical", '
                    '"key_factors": ["factor1"], "retention_suggestions": ["action1"], '
                    '"customer_segment": "power_user|engaged|passive|churning"}'
                ),
            )
            resp = await chat.send_message(UserMessage(text=f"Client: {client.get('company_name')}\nMetrics: {json.dumps(metrics)}"))
            text = resp.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            prediction = json.loads(text.strip())
            prediction["tenant_id"] = tenant_id
            prediction["company_name"] = client.get("company_name", "")
            prediction["metrics"] = metrics
            prediction["recommended_action"] = _get_retention_action(prediction.get("risk_level", "medium"), plan)
            return prediction
    except Exception as e:
        logger.debug(f"[Churn] LLM prediction failed: {e}")

    # Fallback heuristic
    risk_score = min(1.0, days_inactive / 90 * 0.4 + (1 - metrics["actions_used"] / max(metrics["actions_limit"], 1)) * 0.3 + (0.3 if metrics["automations_run"] == 0 else 0))
    risk_level = "critical" if risk_score >= 0.7 else "high" if risk_score >= 0.5 else "medium" if risk_score >= 0.3 else "low"

    return {
        "tenant_id": tenant_id,
        "company_name": client.get("company_name", ""),
        "churn_probability": round(risk_score, 2),
        "risk_level": risk_level,
        "metrics": metrics,
        "key_factors": [f"Inactive {days_inactive} days", f"Usage: {metrics['actions_used']}/{metrics['actions_limit']}"],
        "retention_suggestions": [_get_retention_action(risk_level, plan)],
        "customer_segment": "churning" if risk_score > 0.6 else "passive" if risk_score > 0.3 else "engaged",
    }


# ══════════════════════════════════════════════
# Analytics
# ══════════════════════════════════════════════

@router.get("/analytics")
async def churn_analytics(request: Request):
    """Overall churn analytics for the AUREM platform."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not initialized")

    total = await _get_db().tenant_customers.count_documents({"is_self_client": {"$ne": True}})
    active = await _get_db().tenant_customers.count_documents({"is_active": True, "plan_status": "active", "is_self_client": {"$ne": True}})
    inactive = total - active

    # Revenue
    pipeline = [
        {"$match": {"is_active": True, "plan_status": "active", "is_self_client": {"$ne": True}}},
        {"$group": {"_id": None, "mrr": {"$sum": "$plan_price_cad"}}},
    ]
    agg = await _get_db().tenant_customers.aggregate(pipeline).to_list(1)
    mrr = agg[0]["mrr"] if agg else 0

    return {
        "total_clients": total,
        "active_clients": active,
        "inactive_clients": inactive,
        "churn_rate": round(inactive / max(total, 1) * 100, 1),
        "retention_rate": round(active / max(total, 1) * 100, 1),
        "mrr_cad": mrr,
        "arr_cad": mrr * 12,
    }
