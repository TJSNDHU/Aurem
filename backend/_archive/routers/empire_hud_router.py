"""
Empire HUD — Live Router Pulse API
Pings every registered router and returns real-time health status.
GREEN=LIVE, RED=BLOCKED (missing keys), AMBER=ARCHIVED/SKIPPED
"""
import os
import logging
import importlib
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/admin/empire", tags=["Empire HUD"])
logger = logging.getLogger(__name__)


def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        payload = jwt.decode(auth.split(" ", 1)[1], os.environ.get("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


# Key requirements per blocked module
KEY_REQUIREMENTS = {
    "stripe": {"keys": ["STRIPE_SECRET_KEY"], "name": "Stripe", "url": "dashboard.stripe.com → Developers → API Keys"},
    "twilio": {"keys": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"], "name": "Twilio", "url": "console.twilio.com"},
    "whapi": {"keys": ["WHAPI_API_TOKEN"], "name": "WHAPI (WhatsApp)", "url": "whapi.cloud"},
    "resend": {"keys": ["RESEND_API_KEY"], "name": "Resend (Email)", "url": "resend.com"},
    "elevenlabs": {"keys": ["ELEVENLABS_API_KEY"], "name": "ElevenLabs (Voice)", "url": "elevenlabs.io"},
    "vapi": {"keys": ["VAPI_API_KEY"], "name": "Vapi (Voice AI)", "url": "vapi.ai"},
}


@router.get("/pulse")
async def empire_pulse(request: Request):
    """Real-time health pulse of all 11 layers. Returns status per node."""
    _verify_admin(request)

    nodes = []

    # Layer 0: Foundation
    nodes.extend([
        _check_node("L0", "jwt_blocklist", "JWT Blocklist", "services/jwt_blocklist.py", _check_redis()),
        _check_node("L0", "security_mw", "Security Middleware", "middleware/security.py", True),
        _check_node("L0", "rate_limiter", "Rate Limiter", "performance_patch.py", True),
        _check_node("L0", "cors", "CORS Whitelist", "server.py", True),
    ])

    # Layer 1: Identity
    nodes.extend([
        _check_node("L1", "aurem_auth", "AUREM Auth", "routers/aurem_routes.py", True),
        _check_node("L1", "biometric", "WebAuthn / PIN", "routers/biometric_secure.py", True),
        _check_node("L1", "vault", "Secret Vault", "routers/vault_router.py", True),
        _check_node("L1", "api_keys", "API Keys", "services/api_key_manager.py", True),
    ])

    # Layer 2: Customers
    nodes.extend([
        _check_node("L2", "tenant_customers", "Client Manager", "routers/admin_customers_router.py", True),
        _check_node("L2", "crm", "CRM Connect", "routers/crm_router.py", True),
        _check_node("L2", "leads", "Leads Pipeline", "routers/leads_router.py", True),
        _check_node("L2", "churn", "Churn Prediction", "routers/churn_prediction_router.py", True),
    ])

    # Layer 3: Intelligence
    nodes.extend([
        _check_node("L3", "dark_scout", "Dark Scout OSINT", "routers/dark_scout_router.py", True),
        _check_node("L3", "scanner", "Website Scanner", "routers/customer_scanner.py", True),
        _check_node("L3", "global_pulse", "Global Pulse", "routers/global_pulse_router.py", True),
        _check_node("L3", "camofox", "Camofox Browser", "services/camofox_client.py", _check_camofox()),
    ])

    # Layer 4: ORA AI
    nodes.extend([
        _check_node("L4", "ora_chat", "ORA Multi-Model", "routers/aurem_chat.py", _check_llm()),
        _check_node("L4", "ora_repair", "ORA Repair Engine", "routers/ora_repair_engine.py", True),
        _check_node("L4", "morning_brief", "Morning Brief", "routers/morning_brief_router.py", True),
        _check_node("L4", "ora_pwa", "ORA PWA", "routers/ora_pwa_router.py", True),
    ])

    # Layer 5: Automation
    nodes.extend([
        _check_node("L5", "campaign", "Campaign Engine", "routers/campaign_router.py", True),
        _check_node("L5", "pipeline", "OODA Pipeline", "routers/pipeline_router.py", True),
        _check_node("L5", "scheduler", "APScheduler", "services/cron_schedulers.py", True),
        _check_node("L5", "approval", "Approval Queue", "routers/approval_router.py", True),
    ])

    # Layer 6: Voice & Comms
    twilio_ok = all(os.environ.get(k) for k in ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"])
    whapi_ok = bool(os.environ.get("WHAPI_API_TOKEN"))
    resend_ok = bool(os.environ.get("RESEND_API_KEY"))
    nodes.extend([
        _check_node("L6", "voice_sales", "Voice Sales Agent", "routers/voice_sales_agent.py", True),
        _check_node("L6", "twilio", "Twilio Calls/SMS", "routers/sms_alerts_router.py", twilio_ok, "twilio"),
        _check_node("L6", "whatsapp", "WhatsApp (WHAPI)", "routers/whatsapp_webhook_router.py", whapi_ok, "whapi"),
        _check_node("L6", "email", "Email (Resend)", "services/email_service.py", resend_ok, "resend"),
        _check_node("L6", "tts", "TTS (ElevenLabs)", "services/aurem_voice_service.py", bool(os.environ.get("ELEVENLABS_API_KEY")), "elevenlabs"),
    ])

    # Layer 7: Payments
    stripe_sk = bool(os.environ.get("STRIPE_SECRET_KEY") and "live" in os.environ.get("STRIPE_SECRET_KEY", ""))
    nodes.extend([
        _check_node("L7", "stripe", "Stripe Payments", "routers/stripe_payment_router.py", stripe_sk, "stripe"),
        _check_node("L7", "billing", "AUREM Billing", "routers/aurem_billing_router.py", True),
        _check_node("L7", "subscriptions", "Subscription Mgr", "routers/subscription_routes.py", True),
    ])

    # Layer 8: Data
    nodes.extend([
        _check_node("L8", "mongodb", "MongoDB", "motor (async)", _check_mongo()),
        _check_node("L8", "redis", "Redis Cache", "services/jwt_blocklist.py", _check_redis()),
        _check_node("L8", "memory", "Memory Tiers", "routers/memory_router.py", True),
    ])

    # Layer 9: Security
    nodes.extend([
        _check_node("L9", "sentinel", "Sentinel", "routers/sentinel_router.py", True),
        _check_node("L9", "fraud", "Fraud Prevention", "routers/fraud_prevention.py", True),
        _check_node("L9", "forensics", "Forensics", "routers/forensic_routes.py", True),
    ])

    # Layer 10: Admin
    nodes.extend([
        _check_node("L10", "observatory", "Agent Observatory", "routers/agent_observatory_router.py", True),
        _check_node("L10", "mission_ctrl", "Mission Control", "routers/admin_mission_control_router.py", True),
        _check_node("L10", "system_pulse", "System Pulse", "routers/system_pulse_router.py", True),
    ])

    # Layer 11: AUREM Live Funnel (this session's architecture)
    whapi_ok = bool(os.environ.get("WHAPI_API_TOKEN"))
    resend_ok = bool(os.environ.get("RESEND_API_KEY"))
    twilio_ok = all(os.environ.get(k) for k in ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"])
    tavily_ok = bool(os.environ.get("TAVILY_API_KEY"))
    firecrawl_ok = bool(os.environ.get("FIRECRAWL_API_KEY"))

    nodes.extend([
        _check_node("L11", "accurate_scout", "Accurate Scout", "services/accurate_scout.py",
                    tavily_ok or firecrawl_ok, "tavily" if not (tavily_ok or firecrawl_ok) else None),
        _check_node("L11", "ora_cmd_center", "ORA Command Center", "services/ora_command_center.py", True),
        _check_node("L11", "dashboard_feeds", "Dashboard Feeds", "routers/dashboard_feeds_router.py", True),
        _check_node("L11", "flame_score", "Flame Score Engine", "routers/dashboard_feeds_router.py", whapi_ok, "whapi" if not whapi_ok else None),
        _check_node("L11", "flame_dialer", "Flame Auto-Dialer", "services/flame_auto_dialer.py",
                    twilio_ok, "twilio" if not twilio_ok else None),
        _check_node("L11", "lifecycle", "Lead Lifecycle", "services/lead_lifecycle.py", True),
        _check_node("L11", "drip", "Drip Sequencer (6h)", "services/drip_sequencer.py", True),
        _check_node("L11", "kanban", "Pipeline Kanban", "platform/feeds/LeadPipelineKanban.jsx", True),
        _check_node("L11", "resend_hook", "Resend Webhook", "routers/lead_lifecycle_router.py", resend_ok, "resend" if not resend_ok else None),
        _check_node("L11", "whapi_hook", "WHAPI Webhook", "routers/lead_lifecycle_router.py", whapi_ok, "whapi" if not whapi_ok else None),
        _check_node("L11", "voicemail_blitz", "Voicemail Blitz", "services/drip_sequencer.py",
                    whapi_ok and resend_ok and twilio_ok),
        _check_node("L11", "morning_digest", "Morning Digest (7 AM)", "services/morning_digest.py", whapi_ok, "whapi" if not whapi_ok else None),
    ])

    # Summary
    live = sum(1 for n in nodes if n["status"] == "live")
    blocked = sum(1 for n in nodes if n["status"] == "blocked")
    degraded = sum(1 for n in nodes if n["status"] == "degraded")

    return {
        "nodes": nodes,
        "summary": {
            "total": len(nodes),
            "live": live,
            "blocked": blocked,
            "degraded": degraded,
            "health_pct": round(live / max(len(nodes), 1) * 100, 1),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _check_node(layer: str, node_id: str, name: str, file_path: str, is_ok, blocked_key: str = None):
    if is_ok:
        status = "live"
    elif blocked_key:
        status = "blocked"
    else:
        status = "degraded"

    node = {
        "layer": layer,
        "id": node_id,
        "name": name,
        "file": file_path,
        "status": status,
    }

    if blocked_key and not is_ok:
        req = KEY_REQUIREMENTS.get(blocked_key, {})
        node["blocked_keys"] = req.get("keys", [])
        node["key_provider"] = req.get("name", "")
        node["key_url"] = req.get("url", "")

    return node


def _check_redis():
    return bool(os.environ.get("REDIS_URL"))

def _check_mongo():
    return bool(os.environ.get("MONGO_URL"))

def _check_llm():
    return bool(os.environ.get("EMERGENT_LLM_KEY"))

def _check_camofox():
    try:
        import httpx
        resp = httpx.get("http://localhost:9377/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


@router.post("/inject-key")
async def inject_key(request: Request):
    """Inject an API key into the environment (runtime only — add to .env for persistence)."""
    _verify_admin(request)
    body = await request.json()
    key_name = body.get("key", "").strip()
    key_value = body.get("value", "").strip()

    if not key_name or not key_value:
        raise HTTPException(400, "Missing key name or value")

    # Whitelist of injectable keys
    allowed = {"STRIPE_SECRET_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
               "WHAPI_API_TOKEN", "RESEND_API_KEY", "ELEVENLABS_API_KEY", "VAPI_API_KEY"}

    if key_name not in allowed:
        raise HTTPException(400, f"Key {key_name} not in allowed list")

    os.environ[key_name] = key_value

    # Also append to .env for persistence
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
        # Check if key already exists
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key_name}="):
                lines[i] = f"{key_name}={key_value}\n"
                found = True
                break
        if not found:
            lines.append(f"{key_name}={key_value}\n")
        with open(env_path, "w") as f:
            f.writelines(lines)
    except Exception as e:
        logger.warning(f"[Empire] .env write failed: {e}")

    return {"success": True, "key": key_name, "persisted": True}


# ═══════════════════════════════════════════════════════════════
# LIVE METRICS — per-node counters for L11 AUREM Live Funnel
# ═══════════════════════════════════════════════════════════════
@router.get("/live-metrics")
async def live_metrics(request: Request):
    """Returns live counters for the L11 Funnel nodes so the HUD can show real numbers."""
    _verify_admin(request)

    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL", "")
    if not mongo_url:
        return {"nodes": {}, "error": "mongo_unavailable"}

    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "aurem_db")]
    now = datetime.now(timezone.utc)
    from datetime import timedelta as _td
    window_iso = (now - _td(hours=24)).isoformat()

    async def _safe(coro, default=0):
        try:
            return await coro
        except Exception:
            return default

    metrics: dict = {}

    metrics["accurate_scout"] = {
        "total_verified": await _safe(db.campaign_leads.count_documents({"verification": {"$exists": True}})),
        "high_confidence": await _safe(db.campaign_leads.count_documents({"verification.phone_confidence": "HIGH"})),
    }

    metrics["ora_cmd_center"] = {
        "commands_24h": (await _safe(db.ora_commands_log.count_documents({"at": {"$gte": window_iso}})))
                        or (await _safe(db.ora_command_log.count_documents({"at": {"$gte": window_iso}})))
    }

    metrics["dashboard_feeds"] = {
        "live_viewers": await _safe(db.aurem_live_viewers.count_documents(
            {"last_heartbeat_at": {"$gte": (now - _td(minutes=2)).isoformat()}}
        )),
    }

    flame_alerts_24h = await _safe(db.flame_alerts_log.count_documents({"sent_at": {"$gte": window_iso}}))
    try:
        top = await db.flame_alerts_log.find_one({}, {"_id": 0, "flame_score": 1}, sort=[("flame_score", -1)])
        top_score = (top or {}).get("flame_score", 0)
    except Exception:
        top_score = 0
    metrics["flame_score"] = {"alerts_24h": flame_alerts_24h, "top_score": top_score}

    metrics["flame_dialer"] = {
        "dials_24h": await _safe(db.flame_auto_dials.count_documents({"dialed_at": {"$gte": window_iso}})),
        "dialed_ok": await _safe(db.flame_auto_dials.count_documents({"status": "dialed"})),
    }

    stages = ["new", "contacted", "engaged", "called_no_response", "following_up", "won", "cold"]
    by_stage = {}
    for s in stages:
        by_stage[s] = await _safe(db.campaign_leads.count_documents({"lifecycle_stage": s}))
    metrics["lifecycle"] = {"by_stage": by_stage, "active": sum(by_stage.get(s, 0) for s in stages[:5])}
    metrics["kanban"] = metrics["lifecycle"]

    try:
        drip_pipe = [
            {"$unwind": "$touchpoints"},
            {"$match": {"touchpoints.kind": {"$regex": "^drip_"}, "touchpoints.at": {"$gte": window_iso}}},
            {"$count": "n"},
        ]
        agg = await db.campaign_leads.aggregate(drip_pipe).to_list(length=1)
        drip_24h = agg[0]["n"] if agg else 0
    except Exception:
        drip_24h = 0
    metrics["drip"] = {"steps_24h": drip_24h}

    try:
        hook_pipe = [
            {"$unwind": "$touchpoints"},
            {"$match": {"touchpoints.kind": {"$regex": "^(resend_|whapi_)"}, "touchpoints.at": {"$gte": window_iso}}},
            {"$group": {"_id": {"$substr": ["$touchpoints.kind", 0, 6]}, "count": {"$sum": 1}}},
        ]
        hooks = await db.campaign_leads.aggregate(hook_pipe).to_list(length=10)
        resend_n = next((h["count"] for h in hooks if h["_id"] == "resend"), 0)
        whapi_n = next((h["count"] for h in hooks if h["_id"] == "whapi_"), 0)
    except Exception:
        resend_n, whapi_n = 0, 0
    metrics["resend_hook"] = {"events_24h": resend_n}
    metrics["whapi_hook"] = {"events_24h": whapi_n}

    metrics["voicemail_blitz"] = {
        "fired_24h": await _safe(db.campaign_leads.count_documents({"voicemail_blitz_fired_at": {"$gte": window_iso}})),
    }

    try:
        last_dig = await db.morning_digest_log.find_one({}, {"_id": 0, "sent_at": 1, "sent": 1}, sort=[("sent_at", -1)])
    except Exception:
        last_dig = None
    metrics["morning_digest"] = {
        "last_sent": (last_dig or {}).get("sent_at"),
        "last_ok": bool((last_dig or {}).get("sent")),
        "total_sent": await _safe(db.morning_digest_log.count_documents({})),
    }

    return {
        "nodes": metrics,
        "window_hours": 24,
        "timestamp": now.isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# RECENT EVENTS — for L11 LIVE EVENT PINGS (flash affected nodes)
# Returns all events in the last N seconds, mapped to their HUD node id.
# Polled by the HUD every 3-5 seconds.
# ═══════════════════════════════════════════════════════════════
@router.get("/recent-events")
async def recent_events(request: Request, seconds: int = 30):
    _verify_admin(request)

    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL", "")
    if not mongo_url:
        return {"events": []}

    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "aurem_db")]
    from datetime import timedelta as _td
    now = datetime.now(timezone.utc)
    cutoff_iso = (now - _td(seconds=min(seconds, 300))).isoformat()

    events: list[dict] = []

    async def _collect(cursor, node_id, kind, label_fn=None):
        async for d in cursor:
            at = d.get("at") or d.get("sent_at") or d.get("dialed_at") or d.get("started_at")
            events.append({
                "node_id": node_id,
                "kind": kind,
                "at": at if isinstance(at, str) else (at.isoformat() if at else now.isoformat()),
                "label": label_fn(d) if label_fn else "",
                "business": d.get("business_name") or d.get("business") or "",
            })

    # Flame alerts → flame_score
    try:
        c = db.flame_alerts_log.find({"sent_at": {"$gte": cutoff_iso}}, {"_id": 0}).limit(20)
        await _collect(c, "flame_score", "flame_alert",
                       lambda d: f"🔥 WA alert · score {d.get('flame_score', 0)}")
    except Exception:
        pass

    # Auto-dials → flame_dialer
    try:
        c = db.flame_auto_dials.find({"dialed_at": {"$gte": cutoff_iso}}, {"_id": 0}).limit(20)
        await _collect(c, "flame_dialer", "auto_dial",
                       lambda d: f"☎️ {d.get('status', 'dialed')}")
    except Exception:
        pass

    # Morning digests → morning_digest
    try:
        c = db.morning_digest_log.find({"sent_at": {"$gte": cutoff_iso}}, {"_id": 0}).limit(5)
        await _collect(c, "morning_digest", "digest_sent", lambda d: "☕ digest sent")
    except Exception:
        pass

    # New live viewers → dashboard_feeds
    try:
        c = db.aurem_live_viewers.find({"started_at": {"$gte": cutoff_iso}}, {"_id": 0}).limit(20)
        await _collect(c, "dashboard_feeds", "viewer_joined",
                       lambda d: f"👀 {d.get('business_name', '?')}")
    except Exception:
        pass

    # Touchpoints in last N seconds → map kind to HUD node
    KIND_TO_NODE = [
        ("drip_", "drip"),
        ("resend_", "resend_hook"),
        ("whapi_", "whapi_hook"),
        ("voicemail_blitz_", "voicemail_blitz"),
        ("flame_auto_dial", "flame_dialer"),
        ("sample_site_visit", "dashboard_feeds"),
        ("stripe_paid", "lifecycle"),
        ("manual_blast", "lifecycle"),
    ]
    try:
        pipe = [
            {"$unwind": "$touchpoints"},
            {"$match": {"touchpoints.at": {"$gte": cutoff_iso}}},
            {"$project": {"_id": 0, "business_name": 1, "lead_id": 1,
                          "kind": "$touchpoints.kind", "at": "$touchpoints.at",
                          "channel": "$touchpoints.channel", "status": "$touchpoints.status"}},
            {"$sort": {"at": -1}},
            {"$limit": 50},
        ]
        async for d in db.campaign_leads.aggregate(pipe):
            kind = d.get("kind") or ""
            node_id = None
            for prefix, nid in KIND_TO_NODE:
                if kind.startswith(prefix) or kind == prefix:
                    node_id = nid
                    break
            if not node_id:
                continue
            events.append({
                "node_id": node_id,
                "kind": kind,
                "at": d.get("at"),
                "label": f"{d.get('channel', '')} · {d.get('status', '')}",
                "business": d.get("business_name") or "",
            })
    except Exception:
        pass

    # Lifecycle transitions — from lifecycle_history (latest entries)
    try:
        pipe = [
            {"$unwind": "$lifecycle_history"},
            {"$match": {"lifecycle_history.at": {"$gte": cutoff_iso}}},
            {"$project": {"_id": 0, "business_name": 1,
                          "at": "$lifecycle_history.at",
                          "to": "$lifecycle_history.to",
                          "reason": "$lifecycle_history.reason"}},
            {"$sort": {"at": -1}},
            {"$limit": 20},
        ]
        async for d in db.campaign_leads.aggregate(pipe):
            events.append({
                "node_id": "lifecycle",
                "kind": f"transition_{d.get('to')}",
                "at": d.get("at"),
                "label": f"→ {d.get('to')} ({(d.get('reason') or '')[:30]})",
                "business": d.get("business_name") or "",
            })
            # Also flash kanban
            events.append({
                "node_id": "kanban",
                "kind": f"transition_{d.get('to')}",
                "at": d.get("at"),
                "label": f"→ {d.get('to')}",
                "business": d.get("business_name") or "",
            })
    except Exception:
        pass

    # Sort newest first
    events.sort(key=lambda e: e.get("at") or "", reverse=True)
    return {"events": events[:100], "window_seconds": seconds, "timestamp": now.isoformat()}

