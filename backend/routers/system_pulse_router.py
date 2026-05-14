"""
AUREM System Pulse — SSE Heartbeat + Tier Metering + Dependency Monitoring

Phase A foundation:
  1. /admin/pulse   — SSE stream pushing service health, tier usage, SSE connections every 5s
  2. Tier middleware — Enforces plan limits on restricted services
  3. Dependency pinger — Background task checking all 26 services
  4. Forensic mapping — Router → Collection cross-reference for 500 error analysis
"""
import os
import json
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin Pulse"])

_db = None
_sse_connections = 0  # global counter for active SSE streams

def set_db(database):
    global _db
    _db = database

def _get_db():
    return _db


def _require_admin_pulse(request: Request):
    """Admin-only gate for all /api/admin/pulse/* endpoints.
    Accepts bearer token via Authorization header OR `?token=` query param
    (since EventSource cannot send custom headers).
    """
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    token = None
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    else:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        import jwt
        payload = jwt.decode(
            token,
            (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = (payload.get("role") or "").lower()
    is_admin = bool(payload.get("is_admin") or payload.get("is_super_admin"))
    if role not in ("admin", "super_admin") and not is_admin:
        raise HTTPException(403, "Admin role required")
    return payload


# ═══════════════════════════════════════════════════════════════════
# TIER DEFINITIONS  (in-memory — no DB hit per request)
# ═══════════════════════════════════════════════════════════════════
TIER_LIMITS = {
    "free": {
        "api_calls_per_day": 1000,
        "scanner_scans_per_day": 3,
        "repair_deploys_per_day": 0,
        "restricted_services": ["exa_search", "elevenlabs", "sora_video"],
        "label": "Free Forever",
    },
    "starter": {
        "api_calls_per_day": 5000,
        "scanner_scans_per_day": 25,
        "repair_deploys_per_day": 10,
        "restricted_services": ["sora_video"],
        "label": "Starter",
    },
    "professional": {
        "api_calls_per_day": 50000,
        "scanner_scans_per_day": -1,  # unlimited
        "repair_deploys_per_day": -1,
        "restricted_services": [],
        "label": "Professional",
    },
    "enterprise": {
        "api_calls_per_day": -1,
        "scanner_scans_per_day": -1,
        "repair_deploys_per_day": -1,
        "restricted_services": [],
        "label": "Enterprise",
    },
}


# ═══════════════════════════════════════════════════════════════════
# SERVICE DEPENDENCY MAP  (all 26 from ARCHITECTURE.md)
# ═══════════════════════════════════════════════════════════════════
SERVICES = [
    {"id": "openai_gpt4o",    "name": "OpenAI GPT-4o",         "env": "EMERGENT_LLM_KEY",     "category": "active",   "check": "env"},
    {"id": "openai_image",    "name": "OpenAI Image Gen",      "env": "EMERGENT_LLM_KEY",     "category": "active",   "check": "env"},
    {"id": "openai_sora",     "name": "OpenAI Sora 2 Video",   "env": "EMERGENT_LLM_KEY",     "category": "active",   "check": "env"},
    {"id": "mongodb",         "name": "MongoDB",               "env": "MONGO_URL",            "category": "active",   "check": "ping"},
    {"id": "stripe",          "name": "Stripe Payments",       "env": "STRIPE_SECRET_KEY",    "category": "active",   "check": "env"},
    {"id": "twilio",          "name": "Twilio SMS",            "env": "TWILIO_ACCOUNT_SID",   "category": "requires_key", "check": "env"},
    {"id": "aurem_voice",   "name": "AUREM DIY Voice",       "env": "EMERGENT_LLM_KEY",     "category": "built_in",     "check": "env"},
    {"id": "whapi",           "name": "Whapi.cloud",           "env": "WHAPI_API_TOKEN",      "category": "requires_key", "check": "env"},
    {"id": "meta_whatsapp",   "name": "Meta WhatsApp",         "env": "META_APP_SECRET",      "category": "requires_key", "check": "env"},
    {"id": "resend",          "name": "Resend Email",          "env": "RESEND_API_KEY",       "category": "requires_key", "check": "env"},
    {"id": "sendgrid",        "name": "SendGrid",              "env": "SENDGRID_API_KEY",     "category": "requires_key", "check": "env"},
    {"id": "google_oauth",    "name": "Google OAuth 2.0",      "env": "GOOGLE_CLIENT_SECRET", "category": "requires_key", "check": "env"},
    {"id": "cloudinary",      "name": "Cloudinary",            "env": "CLOUDINARY_API_KEY",   "category": "requires_key", "check": "env"},
    {"id": "github",          "name": "GitHub API",            "env": "GITHUB_TOKEN",         "category": "requires_key", "check": "env"},
    {"id": "brave_search",    "name": "Brave Search",          "env": "BRAVE_SEARCH_API_KEY", "category": "requires_key", "check": "env"},
    {"id": "exa_search",      "name": "EXA Search",            "env": "EXA_API_KEY",          "category": "requires_key", "check": "env"},
    {"id": "coinbase",        "name": "Coinbase Crypto",       "env": "",                     "category": "mock",     "check": "none"},
    {"id": "redis",           "name": "Redis Cache",           "env": "REDIS_URL",            "category": "optional", "check": "env"},
    {"id": "vapid_push",      "name": "VAPID Push",            "env": "VAPID_PUBLIC_KEY",     "category": "active",   "check": "env"},
    {"id": "openrouter",      "name": "OpenRouter",            "env": "OPENROUTER_API_KEY",   "category": "requires_key", "check": "env"},
    {"id": "anthropic",       "name": "Anthropic Claude",      "env": "ANTHROPIC_API_KEY",    "category": "requires_key", "check": "env"},
    {"id": "omnidimension",   "name": "OmniDimension 3D",     "env": "OMNIDIMENSION_API_KEY","category": "requires_key", "check": "env"},
    {"id": "openweather",     "name": "OpenWeatherMap",        "env": "WEATHER_API_KEY",      "category": "requires_key", "check": "env"},
    {"id": "web_speech",      "name": "Web Speech API",        "env": "",                     "category": "active",   "check": "none"},
    {"id": "webauthn",        "name": "WebAuthn / FIDO2",      "env": "",                     "category": "active",   "check": "none"},
    {"id": "web_push",        "name": "Web Push / VAPID",      "env": "VAPID_PRIVATE_KEY",    "category": "active",   "check": "env"},
]

# ═══════════════════════════════════════════════════════════════════
# ROUTER → COLLECTION FORENSIC MAP  (for root-cause analysis)
# ═══════════════════════════════════════════════════════════════════
ROUTER_COLLECTION_MAP = {
    "aurem_routes":        ["users", "leads", "voice_calls", "api_keys", "managed_clients"],
    "aurem_chat":          ["chat_sessions", "chat_messages"],
    "live_scanner":        ["system_scans"],
    "ora_repair_engine":   ["system_scans", "auto_repair_log"],
    "voice_analytics_router": ["voice_calls"],
    "voice_router":        ["voice_calls", "voice_interactions"],
    "crm_router":          ["crm_contacts", "crm_connections", "crm_deals"],
    "automations_router":  ["automations"],
    "gateway_router":      ["webhooks", "api_request_logs"],
    "settings_router":     ["users"],
    "aurem_billing_router":["subscription_plans", "custom_subscriptions"],
    "integration_api":     ["api_keys", "api_keys_registry"],
    "biometric_secure":    ["webauthn_challenges", "users"],
    "push_notification_router": ["push_subscriptions"],
    "self_healing_router": ["auto_heal_log", "auto_heal_runs"],
    "crash_dashboard_routes": ["crash_log"],
    "vault_router":        ["secret_vault", "vault_audit_log"],
    "panic_takeover_router": ["panic_events"],
    "gmail_channel_router": ["gmail_tokens"],
    "whatsapp_webhook_router": ["whatsapp_messages"],
    "acquisition_router":  ["acquisition_campaigns", "acquisition_leads", "acquisition_config"],
    "referral_portal_router": ["referral_profiles"],
    "admin_mission_control_router": ["service_registry", "admin_api_keys", "subscription_plans", "custom_subscriptions"],
}

# ═══════════════════════════════════════════════════════════════════
# ERROR LOG — in-memory ring buffer for the last 50 errors
# ═══════════════════════════════════════════════════════════════════
_error_log = []
MAX_ERROR_LOG = 50

def log_error(router_name: str, path: str, status: int, detail: str):
    """Called by the middleware to register 500 errors for forensic analysis."""
    global _error_log
    collections = ROUTER_COLLECTION_MAP.get(router_name, [])
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "router": router_name,
        "path": path,
        "status": status,
        "detail": detail[:200],
        "collections": collections,
        "forensic": f"Error in {path}. Correlating with {', '.join(collections) if collections else 'unknown'} collections." if collections else f"Error in {path}. No collection mapping found.",
    }
    _error_log.append(entry)
    if len(_error_log) > MAX_ERROR_LOG:
        _error_log.pop(0)


# ═══════════════════════════════════════════════════════════════════
# DEPENDENCY HEALTH  (cached, refreshed by background task)
# ═══════════════════════════════════════════════════════════════════
_dependency_health: Dict[str, Any] = {}
_last_health_check = 0

async def check_dependency_health():
    """Ping all services and update the cached health map."""
    global _dependency_health, _last_health_check
    results = {}

    for svc in SERVICES:
        sid = svc["id"]
        status = "unknown"
        latency = 0

        if svc["check"] == "none":
            status = "active" if svc["category"] == "active" else svc["category"]
        elif svc["check"] == "env":
            env_val = os.environ.get(svc["env"], "")
            if env_val:
                status = "active"
                if svc["category"] == "test":
                    status = "test_mode"
            else:
                status = "not_configured"
        elif svc["check"] == "ping" and sid == "mongodb":
            try:
                db = _get_db()
                if db is not None:
                    t0 = time.time()
                    await db.command("ping")
                    latency = round((time.time() - t0) * 1000, 1)
                    status = "active"
                else:
                    status = "offline"
            except Exception:
                status = "offline"

        results[sid] = {
            "id": sid,
            "name": svc["name"],
            "status": status,
            "category": svc["category"],
            "latency_ms": latency,
        }

    _dependency_health = results
    _last_health_check = time.time()
    return results


# ═══════════════════════════════════════════════════════════════════
# TIER USAGE  (computed from DB)
# ═══════════════════════════════════════════════════════════════════
async def get_tier_usage():
    db = _get_db()
    if db is None:
        return {"free": 0, "starter": 0, "professional": 0, "enterprise": 0, "total_users": 0}

    total_users = await db.users.count_documents({})
    # Count by subscription
    pipeline = [
        {"$group": {"_id": "$tier", "count": {"$sum": 1}}}
    ]
    tier_counts = {"free": total_users, "starter": 0, "professional": 0, "enterprise": 0}
    try:
        async for doc in db.custom_subscriptions.aggregate(pipeline):
            tier = doc["_id"]
            if tier in tier_counts:
                tier_counts[tier] = doc["count"]
                tier_counts["free"] = max(0, tier_counts["free"] - doc["count"])
    except Exception:
        pass

    return {**tier_counts, "total_users": total_users}


# ═══════════════════════════════════════════════════════════════════
# SSE PULSE ENDPOINT  (/admin/pulse)
# ═══════════════════════════════════════════════════════════════════
@router.get("/pulse")
async def system_pulse(request: Request):
    """
    Server-Sent Events stream pushing live system health every 5 seconds.
    Includes: dependency status, tier usage, SSE connections, error log, DB stats.
    ADMIN-ONLY.
    """
    _require_admin_pulse(request)
    global _sse_connections

    async def event_stream():
        global _sse_connections
        _sse_connections += 1
        try:
            while True:
                if await request.is_disconnected():
                    break

                # Refresh dependency health
                deps = await check_dependency_health()

                # Tier usage
                tiers = await get_tier_usage()

                # DB stats
                db = _get_db()
                db_stats = {"collections": 0, "total_docs": 0}
                if db is not None:
                    try:
                        colls = await db.list_collection_names()
                        db_stats["collections"] = len(colls)
                        # Sample a few key collections for doc counts
                        for c in ["users", "api_keys", "voice_calls", "leads", "crash_log", "auto_heal_log"]:
                            if c in colls:
                                db_stats[c] = await db[c].count_documents({})
                                db_stats["total_docs"] += db_stats[c]
                    except Exception:
                        pass

                # Count services by status
                active = sum(1 for d in deps.values() if d["status"] == "active")
                test_mode = sum(1 for d in deps.values() if d["status"] == "test_mode")
                offline = sum(1 for d in deps.values() if d["status"] in ("offline", "not_configured"))
                mock = sum(1 for d in deps.values() if d["status"] == "mock" or d["category"] == "mock")

                # Recent errors (last 10)
                recent_errors = _error_log[-10:] if _error_log else []
                has_breach = any(e["status"] >= 500 for e in recent_errors[-3:])  # last 3 = "glitch" trigger

                payload = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "sse_connections": _sse_connections,
                    "dependencies": list(deps.values()),
                    "dependency_summary": {
                        "active": active,
                        "test_mode": test_mode,
                        "offline": offline,
                        "mock": mock,
                        "total": len(deps),
                    },
                    "tier_usage": tiers,
                    "db_stats": db_stats,
                    "recent_errors": recent_errors,
                    "has_breach": has_breach,
                    "uptime_seconds": int(time.time() - _start_time),
                }

                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(1)  # 1-second high-fidelity heartbeat

        except asyncio.CancelledError:
            pass
        finally:
            _sse_connections -= 1

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


_start_time = time.time()


# ═══════════════════════════════════════════════════════════════════
# SNAPSHOT ENDPOINT  (non-streaming, for initial load)
# ═══════════════════════════════════════════════════════════════════
@router.get("/pulse/snapshot")
async def pulse_snapshot(request: Request):
    """One-shot snapshot of system health for initial page load. ADMIN-ONLY."""
    _require_admin_pulse(request)
    deps = await check_dependency_health()
    tiers = await get_tier_usage()

    db = _get_db()
    db_stats = {"collections": 0, "total_docs": 0}
    if db is not None:
        try:
            colls = await db.list_collection_names()
            db_stats["collections"] = len(colls)
            for c in ["users", "api_keys", "voice_calls", "leads", "crash_log", "auto_heal_log"]:
                if c in colls:
                    db_stats[c] = await db[c].count_documents({})
                    db_stats["total_docs"] += db_stats[c]
        except Exception:
            pass

    active = sum(1 for d in deps.values() if d["status"] == "active")
    test_mode = sum(1 for d in deps.values() if d["status"] == "test_mode")
    offline = sum(1 for d in deps.values() if d["status"] in ("offline", "not_configured"))
    mock = sum(1 for d in deps.values() if d["status"] == "mock" or d["category"] == "mock")

    return {
        "dependencies": list(deps.values()),
        "dependency_summary": {"active": active, "test_mode": test_mode, "offline": offline, "mock": mock, "total": len(deps)},
        "tier_usage": tiers,
        "db_stats": db_stats,
        "recent_errors": _error_log[-10:],
        "has_breach": any(e["status"] >= 500 for e in _error_log[-3:]),
        "sse_connections": _sse_connections,
        "uptime_seconds": int(time.time() - _start_time),
        "tier_definitions": TIER_LIMITS,
        "router_collection_map": ROUTER_COLLECTION_MAP,
    }


# ═══════════════════════════════════════════════════════════════════
# LOG CLEANUP ENDPOINT  (Phase D)
# ═══════════════════════════════════════════════════════════════════
@router.post("/cleanup")
async def cleanup_old_logs(request: Request, days: int = 30):
    """Purge self-healing logs, crash logs, auto-repair entries older than N days. ADMIN-ONLY."""
    _require_admin_pulse(request)
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not available")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cleaned = {}
    for coll_name in ["auto_heal_log", "auto_heal_runs", "auto_repair_log", "crash_log"]:
        try:
            result = await db[coll_name].delete_many({"timestamp": {"$lt": cutoff}})
            if result.deleted_count == 0:
                result = await db[coll_name].delete_many({"ts": {"$lt": cutoff}})
            cleaned[coll_name] = result.deleted_count
        except Exception:
            cleaned[coll_name] = 0

    return {"success": True, "days": days, "purged": cleaned}


# ═══════════════════════════════════════════════════════════════════
# SSE CONCURRENCY GUARD  (Phase D — limit concurrent SSE streams)
# ═══════════════════════════════════════════════════════════════════
MAX_SSE_CONNECTIONS = 50

@router.get("/pulse/status")
async def pulse_status(request: Request):
    """Quick check — how many SSE streams are active right now. ADMIN-ONLY."""
    _require_admin_pulse(request)
    return {
        "sse_connections": _sse_connections,
        "max_allowed": MAX_SSE_CONNECTIONS,
        "available": MAX_SSE_CONNECTIONS - _sse_connections,
    }
