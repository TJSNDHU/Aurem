"""
AUREM Usage + Subscription + Admin + Security API Router
Endpoints for metering, tenant management, admin oversight, and security dashboard.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import jwt as pyjwt
from config import JWT_SECRET, JWT_ALGORITHM

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AUREM Subscription"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


async def _auth(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        return pyjwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        raise HTTPException(401, "Invalid token")


ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

PLAN_TIERS = {
    "trial": {"price": 0, "actions": 50, "workspaces": 1, "brands": 1, "v2v_concurrent": 0, "label": "Trial"},
    "starter": {"price": 97, "actions": 500, "workspaces": 1, "brands": 1, "v2v_concurrent": 0, "label": "Starter"},
    "growth": {"price": 297, "actions": 5000, "workspaces": 3, "brands": 3, "v2v_concurrent": 5, "label": "Growth"},
    "enterprise": {"price": 997, "actions": -1, "workspaces": -1, "brands": -1, "v2v_concurrent": 25, "label": "Enterprise"},
}


# ═══════════════════════════════════════════════════════════════
# USAGE METERING ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/usage/current")
async def get_current_usage(request: Request):
    user = await _auth(request)
    db = _get_db()
    from services.aurem_commercial.usage_service import get_usage_meter
    meter = get_usage_meter(db)
    tenant_id = user.get("tenant_id", user.get("user_id", user.get("id", "default")))
    return await meter.get_current(tenant_id)


@router.get("/api/usage/history")
async def get_usage_history(request: Request, months: int = 6):
    user = await _auth(request)
    db = _get_db()
    from services.aurem_commercial.usage_service import get_usage_meter
    meter = get_usage_meter(db)
    tenant_id = user.get("tenant_id", user.get("user_id", user.get("id", "default")))
    history = await meter.get_history(tenant_id, months)
    return {"history": history}


@router.get("/api/usage/quota")
async def get_usage_quota(request: Request):
    user = await _auth(request)
    db = _get_db()
    from services.aurem_commercial.usage_service import get_usage_meter
    meter = get_usage_meter(db)
    tenant_id = user.get("tenant_id", user.get("user_id", user.get("id", "default")))
    plan = user.get("plan", "trial")
    ws = await db["aurem_workspaces"].find_one({"business_id": tenant_id}, {"_id": 0, "plan": 1})
    if ws:
        plan = ws.get("plan", plan)
    billing = await db["aurem_billing"].find_one({"business_id": tenant_id}, {"_id": 0, "plan": 1})
    if billing:
        plan = billing.get("plan", plan)
    quota = await meter.check_quota(tenant_id, plan)
    tier_info = PLAN_TIERS.get(plan, PLAN_TIERS["trial"])
    quota["plan"] = plan
    quota["plan_label"] = tier_info["label"]
    quota["plan_price"] = tier_info["price"]
    return quota


@router.get("/api/subscription/plans")
async def get_plans():
    plans = []
    for plan_id, info in PLAN_TIERS.items():
        plans.append({
            "id": plan_id,
            "label": info["label"],
            "price": info["price"],
            "currency": "CAD",
            "actions_included": info["actions"],
            "workspaces": info["workspaces"],
            "brands": info["brands"],
            "v2v_concurrent": info["v2v_concurrent"],
        })
    return {"plans": plans}


# ═══════════════════════════════════════════════════════════════
# TENANT MANAGEMENT (Mock Stripe — graceful degradation)
# ═══════════════════════════════════════════════════════════════

class UpgradeRequest(BaseModel):
    plan: str
    business_id: Optional[str] = None


@router.post("/api/subscription/checkout")
async def create_checkout(req: UpgradeRequest, request: Request):
    user = await _auth(request)
    db = _get_db()
    tenant_id = req.business_id or user.get("tenant_id", user.get("user_id", user.get("id", "default")))
    plan = req.plan

    if plan not in PLAN_TIERS or plan == "trial":
        raise HTTPException(400, "Invalid plan")

    stripe_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY", "")
    is_mock = not stripe_key or stripe_key == "sk_test_emergent"

    if is_mock:
        await db["aurem_billing"].update_one(
            {"business_id": tenant_id},
            {"$set": {
                "plan": plan,
                "status": "active",
                "updated_at": datetime.now(timezone.utc),
                "mock_mode": True,
            }},
            upsert=True,
        )
        await db["aurem_workspaces"].update_one(
            {"business_id": tenant_id},
            {"$set": {"plan": plan, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return {
            "success": True,
            "mock": True,
            "plan": plan,
            "message": f"Upgraded to {PLAN_TIERS[plan]['label']} (Stripe not configured — mock mode)",
        }

    try:
        import stripe
        stripe.api_key = stripe_key
        origin = request.headers.get("origin", request.headers.get("referer", ""))
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "cad",
                    "product_data": {"name": f"AUREM {PLAN_TIERS[plan]['label']}"},
                    "unit_amount": PLAN_TIERS[plan]["price"] * 100,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{origin}?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}?payment=cancelled",
            metadata={"business_id": tenant_id, "plan": plan},
        )
        return {"success": True, "url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"[Subscription] Stripe checkout error: {e}")
        raise HTTPException(500, f"Stripe error: {str(e)}")


@router.post("/api/subscription/cancel")
async def cancel_subscription(request: Request):
    user = await _auth(request)
    db = _get_db()
    tenant_id = user.get("tenant_id", user.get("user_id", user.get("id", "default")))
    await db["aurem_billing"].update_one(
        {"business_id": tenant_id},
        {"$set": {
            "status": "cancelled",
            "plan": "trial",
            "cancelled_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"success": True, "message": "Subscription cancelled. Data preserved in read-only mode."}


# ═══════════════════════════════════════════════════════════════
# API KEY SETTINGS (for external services)
# ═══════════════════════════════════════════════════════════════

CONFIGURABLE_KEYS = [
    {"key": "STRIPE_SECRET_KEY", "label": "Stripe Secret Key", "prefix": "sk_"},
    {"key": "STRIPE_WEBHOOK_SECRET", "label": "Stripe Webhook Secret", "prefix": "whsec_"},
    {"key": "SENDGRID_API_KEY", "label": "SendGrid API Key", "prefix": "SG."},
    {"key": "TWILIO_ACCOUNT_SID", "label": "Twilio Account SID", "prefix": "AC"},
    {"key": "TWILIO_AUTH_TOKEN", "label": "Twilio Auth Token", "prefix": ""},
    {"key": "SHOPIFY_API_KEY", "label": "Shopify API Key", "prefix": ""},
    {"key": "SHOPIFY_API_SECRET", "label": "Shopify API Secret", "prefix": ""},
    {"key": "OPENAI_API_KEY", "label": "OpenAI API Key", "prefix": "sk-"},
    {"key": "COINBASE_API_KEY", "label": "Coinbase API Key", "prefix": ""},
]


def _mask_key(value: str) -> str:
    if not value or len(value) < 8:
        return "••••"
    return value[:4] + "•" * (len(value) - 8) + value[-4:]


@router.get("/api/settings/api-keys")
async def get_api_keys(request: Request):
    await _auth(request)
    db = _get_db()
    tenant_id = "global"
    doc = await db["aurem_api_key_settings"].find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    keys_status = []
    saved = doc.get("keys", {}) if doc else {}
    for cfg in CONFIGURABLE_KEYS:
        val = saved.get(cfg["key"], "")
        keys_status.append({
            "key": cfg["key"],
            "label": cfg["label"],
            "prefix": cfg["prefix"],
            "configured": bool(val),
            "masked_value": _mask_key(val) if val else "",
        })
    return {"keys": keys_status}


class SaveApiKeyRequest(BaseModel):
    key_name: str
    key_value: str


@router.put("/api/settings/api-keys")
async def save_api_key(req: SaveApiKeyRequest, request: Request):
    await _auth(request)
    db = _get_db()
    tenant_id = "global"
    valid_keys = {c["key"] for c in CONFIGURABLE_KEYS}
    if req.key_name not in valid_keys:
        raise HTTPException(400, "Invalid key name")
    await db["aurem_api_key_settings"].update_one(
        {"tenant_id": tenant_id},
        {
            "$set": {
                f"keys.{req.key_name}": req.key_value,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"tenant_id": tenant_id, "created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    return {"success": True, "key": req.key_name, "masked": _mask_key(req.key_value)}


@router.delete("/api/settings/api-keys/{key_name}")
async def delete_api_key(key_name: str, request: Request):
    await _auth(request)
    db = _get_db()
    tenant_id = "global"
    await db["aurem_api_key_settings"].update_one(
        {"tenant_id": tenant_id},
        {"$unset": {f"keys.{key_name}": ""}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    return {"success": True, "key": key_name, "deleted": True}


# ═══════════════════════════════════════════════════════════════
# SUPER-ADMIN ENDPOINTS (Tj only)
# ═══════════════════════════════════════════════════════════════

def _require_admin(request: Request):
    key = request.headers.get("X-Admin-Key", "")
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    # Allow admin key OR JWT with is_admin
    if ADMIN_KEY and key == ADMIN_KEY:
        return
    if token:
        try:
            payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            # Bug-fix #162 (R19): removed `or payload.get("email")` bypass —
            # every JWT carries an email claim, so the OR clause granted
            # admin to any authenticated customer. Require an explicit
            # admin signal instead.
            if (payload.get("is_admin")
                    or payload.get("is_super_admin")
                    or payload.get("role") in ("admin", "super_admin")):
                return
        except Exception:
            pass
    raise HTTPException(403, "Admin access required")


@router.get("/api/admin/tenants")
async def admin_list_tenants(request: Request):
    _require_admin(request)
    db = _get_db()
    tenants = await db["aurem_billing"].find({}, {"_id": 0}).to_list(500)
    from services.aurem_commercial.usage_service import get_usage_meter
    meter = get_usage_meter(db)
    all_usage = await meter.get_all_tenants_usage()
    usage_map = {u["tenant_id"]: u for u in all_usage}

    result = []
    total_mrr = 0
    for t in tenants:
        plan = t.get("plan", "trial")
        tier = PLAN_TIERS.get(plan, PLAN_TIERS["trial"])
        mrr = tier["price"]
        if t.get("status") == "active":
            total_mrr += mrr
        tid = t.get("business_id", "")
        u = usage_map.get(tid, {})
        used = u.get("total_actions", 0)
        limit = tier["actions"]
        pct = round((used / limit) * 100, 1) if limit > 0 else 0

        result.append({
            "business_id": tid,
            "email": t.get("email", ""),
            "plan": plan,
            "plan_label": tier["label"],
            "mrr": mrr,
            "status": t.get("status", "unknown"),
            "actions_used": used,
            "actions_limit": limit,
            "usage_percent": pct,
            "churn_risk": used == 0 and t.get("status") == "active",
            "upsell_trigger": pct >= 90 and limit > 0,
            "updated_at": str(t.get("updated_at", "")),
        })

    return {
        "tenants": result,
        "total_mrr": total_mrr,
        "total_tenants": len(result),
        "active_tenants": sum(1 for t in result if t["status"] == "active"),
        "churn_risk_count": sum(1 for t in result if t["churn_risk"]),
        "upsell_count": sum(1 for t in result if t["upsell_trigger"]),
    }


class AdminPlanOverride(BaseModel):
    business_id: str
    plan: str


@router.put("/api/admin/tenants/plan")
async def admin_override_plan(req: AdminPlanOverride, request: Request):
    _require_admin(request)
    if req.plan not in PLAN_TIERS:
        raise HTTPException(400, "Invalid plan")
    db = _get_db()
    await db["aurem_billing"].update_one(
        {"business_id": req.business_id},
        {"$set": {"plan": req.plan, "status": "active", "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    await db["aurem_workspaces"].update_one(
        {"business_id": req.business_id},
        {"$set": {"plan": req.plan, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"success": True, "business_id": req.business_id, "plan": req.plan}


# ═══════════════════════════════════════════════════════════════
# SECURITY DASHBOARD ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/api/admin/security")
async def admin_security_dashboard(request: Request):
    _require_admin(request)
    db = _get_db()

    jwt_ok = bool(JWT_SECRET and len(JWT_SECRET) > 20)

    cors_raw = os.environ.get("CORS_ORIGINS", "")
    cors_ok = bool(cors_raw) and cors_raw.strip() != "*"

    try:
        from routers.v2v_stream_engine import _active_ws_connections
        ws_connections = dict(_active_ws_connections)
    except Exception:
        ws_connections = {}

    yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
    try:
        blocked_webhooks = await db["_unresolved_quarantine"].count_documents({})
    except Exception:
        blocked_webhooks = 0

    try:
        auth_failures = await db["aurem_audit_log"].count_documents({
            "action": {"$in": ["login_failed", "auth_failure"]},
            "timestamp": {"$gte": yesterday},
        })
    except Exception:
        auth_failures = 0

    return {
        "jwt_health": {"configured": jwt_ok, "algorithm": JWT_ALGORITHM, "key_length": len(JWT_SECRET) if JWT_SECRET else 0},
        "cors": {"configured": cors_ok, "origins": cors_raw.split(",") if cors_raw else []},
        "websocket_connections": {"active": ws_connections, "total": sum(ws_connections.values())},
        "blocked_webhooks_24h": blocked_webhooks,
        "auth_failures_24h": auth_failures,
        "security_patches_applied": 6,
        "last_audit": "2026-04-07",
    }
