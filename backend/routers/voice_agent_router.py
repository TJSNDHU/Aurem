"""
AUREM Voice Agent Router (Phase 6) — Consolidated
===================================================
Unified inbound AI call handler. Replaces fragmentation of 6+ voice routers.

Integration: Retell AI (primary) via RETELL_API_KEY. Graceful degradation to
stub mode if key not set (lets us ship UI + DB layer now, flip switch later).

Endpoints:
  ADMIN:
    GET    /api/admin/voice-agent/config/{bin}       Load per-customer agent config
    POST   /api/admin/voice-agent/config/{bin}       Save config (greeting, hours, voice, transfer)
    GET    /api/admin/voice-agent/calls/{bin}        List call log + analytics
    POST   /api/admin/voice-agent/test-call          Trigger a test call
    GET    /api/admin/voice-agent/overview           Platform-wide call stats

  CUSTOMER:
    GET    /api/customer/voice-agent/status          My config + minutes used
    POST   /api/customer/voice-agent/config          Update my greeting/hours
    GET    /api/customer/voice-agent/calls           My call log + transcripts

  WEBHOOKS:
    POST   /api/retell/webhook                       Retell fires on call_ended
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AUREM Voice Agent"])
_db = None

DEFAULT_MINUTES_INCLUDED = 400
DEFAULT_OVERAGE_RATE = 0.35  # $/min CAD


def set_db(database):
    global _db
    _db = database


def _retell_ready() -> bool:
    return bool(os.environ.get("RETELL_API_KEY", "").strip())


# ═════ Auth ═════
def _decode_jwt(request: Request) -> dict:
    import jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT_SECRET not configured")
    try:
        return jwt.decode(auth[7:], secret, algorithms=["HS256"])
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")


async def _verify_super_admin(request: Request) -> dict:
    user = _decode_jwt(request)
    email = (user.get("email") or "").lower()
    if not email or _db is None:
        raise HTTPException(401, "unauthorized")
    admin = await _db.users.find_one(
        {"email": email, "$or": [{"role": "super_admin"}, {"is_admin": True}]},
        {"_id": 0, "email": 1, "role": 1}
    )
    if not admin:
        raise HTTPException(403, "super admin required")
    return admin


async def _verify_platform_user(request: Request) -> dict:
    user = _decode_jwt(request)
    email = (user.get("email") or "").lower()
    if not email or _db is None:
        raise HTTPException(401, "unauthorized")
    doc = await _db.platform_users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not doc:
        raise HTTPException(404, "user not found")
    doc["bin"] = doc.get("bin") or doc.get("business_id") or doc.get("tenant_id")
    return doc


# ═════ Models ═════

class VoiceAgentConfig(BaseModel):
    greeting: str = Field(default="Hello, thank you for calling. How can I help you today?")
    business_hours: Dict[str, Any] = Field(default_factory=lambda: {
        "enabled": True,
        "timezone": "America/Toronto",
        "monday":    {"open": "09:00", "close": "18:00"},
        "tuesday":   {"open": "09:00", "close": "18:00"},
        "wednesday": {"open": "09:00", "close": "18:00"},
        "thursday":  {"open": "09:00", "close": "18:00"},
        "friday":    {"open": "09:00", "close": "18:00"},
        "saturday":  {"open": "10:00", "close": "16:00"},
        "sunday":    {"closed": True},
    })
    after_hours_message: str = Field(default="We're currently closed. Please call back during business hours.")
    transfer_number: Optional[str] = None
    transfer_on_keywords: List[str] = Field(default_factory=lambda: ["emergency", "speak to owner", "urgent"])
    qualification_questions: List[str] = Field(default_factory=lambda: [
        "What's your name?",
        "What brings you in today?",
        "What's the best number to reach you?",
    ])
    voice_id: str = Field(default="rachel")    # ElevenLabs voice
    llm_model: str = Field(default="gpt-4o")   # Retell-supported models
    language: str = Field(default="en")
    enabled: bool = Field(default=True)


# ═════ ADMIN ENDPOINTS ═════

@router.get("/api/admin/voice-agent/overview")
async def voice_overview(admin: dict = Depends(_verify_super_admin)):
    """Platform-wide voice agent stats for admin command hub."""
    total_configs = await _db.voice_agent_configs.count_documents({})
    enabled = await _db.voice_agent_configs.count_documents({"enabled": True})
    # Calls in last 7 days
    cutoff = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=7)).isoformat()
    total_calls_7d = await _db.voice_call_logs.count_documents({"at": {"$gte": cutoff}})
    # Total minutes logged
    pipeline = [{"$group": {"_id": None, "total_min": {"$sum": "$duration_minutes"}}}]
    min_agg = await _db.voice_call_logs.aggregate(pipeline).to_list(length=1)
    total_minutes = (min_agg[0]["total_min"] if min_agg else 0) or 0

    return {
        "retell_connected": _retell_ready(),
        "total_customers_configured": total_configs,
        "enabled_agents": enabled,
        "calls_7d": total_calls_7d,
        "total_minutes_all_time": round(total_minutes, 1),
        "estimated_cost_7d_usd": round(total_calls_7d * 3 * 0.07, 2),   # avg 3min × $0.07
    }


@router.get("/api/admin/voice-agent/config/{bin_id}")
async def admin_get_config(bin_id: str, admin: dict = Depends(_verify_super_admin)):
    cfg = await _db.voice_agent_configs.find_one({"tenant_bin": bin_id}, {"_id": 0})
    return {"config": cfg or {}, "retell_ready": _retell_ready()}


@router.post("/api/admin/voice-agent/config/{bin_id}")
async def admin_save_config(bin_id: str, config: VoiceAgentConfig, admin: dict = Depends(_verify_super_admin)):
    now = datetime.now(timezone.utc).isoformat()
    doc = config.dict()
    doc.update({
        "tenant_bin": bin_id,
        "updated_at": now,
        "updated_by": admin.get("email"),
    })
    # Attempt Retell agent create/update (lazy, non-blocking on stub mode)
    retell_agent_id = None
    if _retell_ready():
        try:
            retell_agent_id = await _upsert_retell_agent(bin_id, doc)
            doc["retell_agent_id"] = retell_agent_id
        except Exception as e:
            logger.warning(f"[voice-agent] Retell upsert failed (config saved locally): {e}")
    await _db.voice_agent_configs.update_one(
        {"tenant_bin": bin_id}, {"$set": doc}, upsert=True
    )
    return {"ok": True, "saved": True, "retell_agent_id": retell_agent_id}


@router.get("/api/admin/voice-agent/calls/{bin_id}")
async def admin_get_calls(bin_id: str, admin: dict = Depends(_verify_super_admin)):
    calls = await _db.voice_call_logs.find({"tenant_bin": bin_id}, {"_id": 0})\
        .sort("at", -1).limit(100).to_list(length=100)
    # Usage this month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0).isoformat()
    pipeline = [
        {"$match": {"tenant_bin": bin_id, "at": {"$gte": month_start}}},
        {"$group": {"_id": None, "minutes": {"$sum": "$duration_minutes"}, "count": {"$sum": 1}}},
    ]
    agg = await _db.voice_call_logs.aggregate(pipeline).to_list(length=1)
    month_minutes = (agg[0]["minutes"] if agg else 0) or 0
    month_count = (agg[0]["count"] if agg else 0) or 0

    return {
        "calls": calls,
        "month_usage": {
            "minutes_used": round(month_minutes, 1),
            "minutes_included": DEFAULT_MINUTES_INCLUDED,
            "minutes_remaining": max(0, DEFAULT_MINUTES_INCLUDED - month_minutes),
            "call_count": month_count,
            "overage_minutes": max(0, month_minutes - DEFAULT_MINUTES_INCLUDED),
            "overage_cost_cad": round(max(0, month_minutes - DEFAULT_MINUTES_INCLUDED) * DEFAULT_OVERAGE_RATE, 2),
        },
    }


class TestCallRequest(BaseModel):
    bin_id: str
    phone_number: str


@router.post("/api/admin/voice-agent/test-call")
async def admin_test_call(body: TestCallRequest, admin: dict = Depends(_verify_super_admin)):
    """Trigger a test outbound call to verify agent config."""
    if not _retell_ready():
        return {
            "ok": False,
            "reason": "Retell not connected. Set RETELL_API_KEY in .env to enable.",
            "stub_mode": True,
        }
    cfg = await _db.voice_agent_configs.find_one({"tenant_bin": body.bin_id}, {"_id": 0})
    if not cfg:
        raise HTTPException(404, "config not found for this customer")
    try:
        # iter 325h — _retell_create_phone_call now returns a dict
        # `{ok, call_id, error}`. Old call shape (string call_id) is
        # gone; we surface the error message back to the admin tester.
        result = await _retell_create_phone_call(cfg.get("retell_agent_id"), body.phone_number)
        if not result.get("ok"):
            raise HTTPException(500, f"test call failed: {result.get('error') or 'unknown'}")
        return {"ok": True, "call_id": result.get("call_id")}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[voice-agent] test call failed")
        raise HTTPException(500, f"test call failed: {e}")


# ═════ CUSTOMER ENDPOINTS ═════

@router.get("/api/customer/voice-agent/status")
async def customer_voice_status(user: dict = Depends(_verify_platform_user)):
    """Customer-facing: my config + minutes used + Retell readiness."""
    bin_id = user.get("bin", "")
    cfg = await _db.voice_agent_configs.find_one({"tenant_bin": bin_id}, {"_id": 0})
    # Usage this month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0).isoformat()
    pipeline = [
        {"$match": {"tenant_bin": bin_id, "at": {"$gte": month_start}}},
        {"$group": {"_id": None, "minutes": {"$sum": "$duration_minutes"}}},
    ]
    agg = await _db.voice_call_logs.aggregate(pipeline).to_list(length=1)
    month_min = (agg[0]["minutes"] if agg else 0) or 0

    # Is customer subscribed to voice_agent_ai service?
    sub = await _db.customer_subscriptions.find_one({
        "email": user.get("email", ""),
        "service_id": "voice_agent_ai",
        "status": "active",
    }, {"_id": 0})

    return {
        "provisioned": bool(sub),
        "config": cfg or {},
        "retell_ready": _retell_ready(),
        "month_usage": {
            "minutes_used": round(month_min, 1),
            "minutes_included": DEFAULT_MINUTES_INCLUDED,
            "minutes_remaining": max(0, DEFAULT_MINUTES_INCLUDED - month_min),
            "overage_cost_cad": round(max(0, month_min - DEFAULT_MINUTES_INCLUDED) * DEFAULT_OVERAGE_RATE, 2),
        },
    }


@router.post("/api/customer/voice-agent/config")
async def customer_save_config(config: VoiceAgentConfig, user: dict = Depends(_verify_platform_user)):
    """Customer updates own greeting/hours/transfer (subset of admin config)."""
    sub = await _db.customer_subscriptions.find_one({
        "email": user.get("email", ""),
        "service_id": "voice_agent_ai",
        "status": "active",
    })
    if not sub:
        raise HTTPException(403, "Voice Agent add-on required — subscribe at /my/website")

    bin_id = user.get("bin", "")
    now = datetime.now(timezone.utc).isoformat()
    doc = config.dict()
    doc.update({"tenant_bin": bin_id, "updated_at": now, "updated_by": user.get("email")})

    if _retell_ready():
        try:
            retell_id = await _upsert_retell_agent(bin_id, doc)
            doc["retell_agent_id"] = retell_id
        except Exception as e:
            logger.warning(f"[voice-agent] Retell upsert failed: {e}")

    await _db.voice_agent_configs.update_one(
        {"tenant_bin": bin_id}, {"$set": doc}, upsert=True
    )
    return {"ok": True}


@router.get("/api/customer/voice-agent/calls")
async def customer_my_calls(user: dict = Depends(_verify_platform_user)):
    """Customer's own call log + transcripts."""
    calls = await _db.voice_call_logs.find(
        {"tenant_bin": user.get("bin", "")}, {"_id": 0}
    ).sort("at", -1).limit(50).to_list(length=50)
    return {"calls": calls, "total": len(calls)}


# ═════ RETELL CATALOG (voices, agents, phone numbers) ═════

@router.get("/api/admin/voice-agent/retell/voices")
async def list_retell_voices(admin: dict = Depends(_verify_super_admin)):
    """List all available Retell voices (for voice picker UI)."""
    if not _retell_ready():
        return {"voices": [], "retell_ready": False}
    try:
        resp = await _retell_request("GET", "/list-voices")
        voices = resp if isinstance(resp, list) else resp.get("voices", [])
        return {"voices": voices, "retell_ready": True, "count": len(voices)}
    except Exception as e:
        logger.warning(f"[retell] list voices failed: {e}")
        return {"voices": [], "retell_ready": True, "error": str(e)}


@router.get("/api/admin/voice-agent/retell/agents")
async def list_retell_agents(admin: dict = Depends(_verify_super_admin)):
    """List all Retell agents in the account."""
    if not _retell_ready():
        return {"agents": [], "retell_ready": False}
    try:
        resp = await _retell_request("GET", "/list-agents")
        agents = resp if isinstance(resp, list) else resp.get("agents", [])
        return {"agents": agents, "retell_ready": True, "count": len(agents)}
    except Exception as e:
        return {"agents": [], "retell_ready": True, "error": str(e)}


@router.get("/api/admin/voice-agent/retell/phone-numbers")
async def list_retell_phone_numbers(admin: dict = Depends(_verify_super_admin)):
    """List phone numbers purchased/imported in Retell."""
    if not _retell_ready():
        return {"phone_numbers": [], "retell_ready": False}
    try:
        resp = await _retell_request("GET", "/list-phone-numbers")
        nums = resp if isinstance(resp, list) else resp.get("phone_numbers", [])
        return {"phone_numbers": nums, "retell_ready": True, "count": len(nums)}
    except Exception as e:
        return {"phone_numbers": [], "retell_ready": True, "error": str(e)}


@router.get("/api/admin/voice-agent/retell/status")
async def retell_connection_status(admin: dict = Depends(_verify_super_admin)):
    """Ping Retell to verify API key + account health."""
    if not _retell_ready():
        return {"connected": False, "reason": "RETELL_API_KEY not set"}
    try:
        voices = await _retell_request("GET", "/list-voices")
        agents = await _retell_request("GET", "/list-agents")
        nums = await _retell_request("GET", "/list-phone-numbers")
        v = voices if isinstance(voices, list) else voices.get("voices", [])
        a = agents if isinstance(agents, list) else agents.get("agents", [])
        n = nums if isinstance(nums, list) else nums.get("phone_numbers", [])
        return {
            "connected": True,
            "voices_available": len(v),
            "agents_in_account": len(a),
            "phone_numbers": len(n),
            "from_number_configured": bool(os.environ.get("RETELL_FROM_NUMBER", "").strip()),
        }
    except Exception as e:
        return {"connected": False, "reason": str(e)}


# ═════ RETELL WEBHOOK ═════

def _verify_retell_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Verify Retell webhook HMAC-SHA256 signature.
    Header format: v={timestamp_ms},d={hex_digest}
    where hex_digest = HMAC-SHA256(raw_body + timestamp, api_key)
    """
    import re, hmac, hashlib, time
    api_key = os.environ.get("RETELL_API_KEY", "")
    if not api_key or not signature_header:
        return False
    m = re.match(r'v=(\d+),d=(.+)', signature_header.strip())
    if not m:
        return False
    ts_str, received = m.group(1), m.group(2)
    try:
        # 5-minute replay window
        if abs(int(time.time() * 1000) - int(ts_str)) > 5 * 60 * 1000:
            return False
        msg = raw_body.decode("utf-8") + ts_str
        expected = hmac.new(api_key.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, received)
    except Exception:
        return False


@router.post("/api/retell/webhook")
async def retell_webhook(request: Request):
    """Retell fires on call_started, call_ended, call_analyzed events."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    # Read raw body first for signature verification
    raw = await request.body()
    sig = request.headers.get("x-retell-signature", "")
    # Bug-fix #58 — used to short-circuit when `sig` was missing, letting
    # attackers POST fake call events without any signature. Now: if the
    # webhook is configured (RETELL_API_KEY set), the signature header
    # MUST be present and valid.
    if os.environ.get("RETELL_API_KEY"):
        if not sig:
            logger.warning("[retell-webhook] missing signature header — rejecting")
            raise HTTPException(401, "missing signature")
        if not _verify_retell_signature(raw, sig):
            logger.warning("[retell-webhook] invalid signature — rejecting")
            raise HTTPException(401, "invalid signature")

    import json as _json
    try:
        body = _json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(400, "invalid JSON")
    event_type = body.get("event") or body.get("type", "unknown")
    call_data = body.get("call", body.get("data", {}))

    logger.info(f"[retell-webhook] event={event_type} call_id={call_data.get('call_id')}")

    if event_type in ("call_ended", "call_analyzed"):
        # Extract agent_id → lookup tenant_bin
        agent_id = call_data.get("agent_id")
        cfg = await _db.voice_agent_configs.find_one({"retell_agent_id": agent_id}, {"_id": 0})
        bin_id = cfg.get("tenant_bin") if cfg else call_data.get("metadata", {}).get("tenant_bin")

        duration_ms = call_data.get("duration_ms", 0) or 0
        duration_min = round(duration_ms / 60000.0, 2) if duration_ms else 0

        await _db.voice_call_logs.insert_one({
            "call_id": call_data.get("call_id") or f"call_{uuid.uuid4().hex[:12]}",
            "retell_call_id": call_data.get("call_id"),
            "tenant_bin": bin_id,
            "caller_number": call_data.get("from_number"),
            "called_number": call_data.get("to_number"),
            "direction": call_data.get("direction", "inbound"),
            "duration_ms": duration_ms,
            "duration_minutes": duration_min,
            "transcript": call_data.get("transcript", ""),
            "summary": call_data.get("call_analysis", {}).get("call_summary", ""),
            "sentiment": call_data.get("call_analysis", {}).get("user_sentiment", "neutral"),
            "outcome": call_data.get("call_analysis", {}).get("call_successful", None),
            "recording_url": call_data.get("recording_url"),
            "at": datetime.now(timezone.utc).isoformat(),
            "raw": call_data if len(str(call_data)) < 8000 else None,
        })

        # Bump usage meter
        if bin_id and duration_min:
            await _db.voice_agent_usage_meter.update_one(
                {"tenant_bin": bin_id, "month": datetime.now(timezone.utc).strftime("%Y-%m")},
                {"$inc": {"minutes_used": duration_min, "call_count": 1}},
                upsert=True,
            )

    return {"received": True, "event": event_type}


# ═════ RETELL SDK HELPERS (graceful degradation) ═════

RETELL_API_BASE = "https://api.retellai.com"


async def _retell_request(method: str, path: str, json_body: Optional[Dict] = None) -> Dict:
    """Thin Retell HTTP client with auth + timeout."""
    if not _retell_ready():
        raise Exception("RETELL_API_KEY missing")
    import httpx
    api_key = os.environ["RETELL_API_KEY"]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.request(method, f"{RETELL_API_BASE}{path}", json=json_body, headers=headers)
        if resp.status_code >= 400:
            raise Exception(f"Retell {method} {path} → {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content else {}


async def _upsert_retell_agent(tenant_bin: str, cfg: Dict) -> Optional[str]:
    """
    Create/update a Retell agent using the correct 2-step flow:
    1. Create/update LLM response engine (gets llm_id)
    2. Create/update agent referencing that llm_id
    Returns agent_id.
    """
    if not _retell_ready():
        return None

    greeting = cfg.get("greeting") or "Hello, how can I help you?"
    system_prompt = (
        f"You are a friendly AI receptionist for {tenant_bin}. "
        f"Greeting: {greeting}\n"
        f"Qualification questions: {', '.join(cfg.get('qualification_questions', []))}\n"
        f"Transfer to human on keywords: {', '.join(cfg.get('transfer_on_keywords', []))}\n"
        f"Keep responses brief, warm, professional."
    )

    # STEP 1 — create or update the LLM response engine
    existing_llm_id = cfg.get("retell_llm_id")
    llm_payload = {
        "model": "gpt-4o",
        "model_temperature": 0.7,
        "general_prompt": system_prompt,
        "begin_message": greeting,
    }
    if existing_llm_id:
        try:
            llm_resp = await _retell_request("PATCH", f"/update-retell-llm/{existing_llm_id}", llm_payload)
            llm_id = llm_resp.get("llm_id") or existing_llm_id
        except Exception:
            # LLM was deleted upstream → recreate
            llm_resp = await _retell_request("POST", "/create-retell-llm", llm_payload)
            llm_id = llm_resp.get("llm_id")
    else:
        llm_resp = await _retell_request("POST", "/create-retell-llm", llm_payload)
        llm_id = llm_resp.get("llm_id")

    cfg["retell_llm_id"] = llm_id

    # STEP 2 — create or update the agent referencing that LLM
    existing_agent_id = cfg.get("retell_agent_id")
    # Normalize voice_id → Retell format (prefix if raw name given)
    voice_id = cfg.get("voice_id", "11labs-Adrian")
    if not any(voice_id.startswith(p) for p in ("11labs-", "cartesia-", "minimax-", "openai-", "deepgram-", "elevenlabs-", "retell-")):
        voice_id = f"11labs-{voice_id.capitalize()}"

    agent_payload = {
        "agent_name": f"AUREM-{tenant_bin}",
        "voice_id": voice_id,
        "language": cfg.get("language", "en-US"),
        "response_engine": {"type": "retell-llm", "llm_id": llm_id},
        "webhook_url": (os.environ.get("PUBLIC_APP_URL", "") + "/api/retell/webhook").rstrip("/") or None,
    }
    # Strip None
    agent_payload = {k: v for k, v in agent_payload.items() if v is not None}

    if existing_agent_id:
        try:
            agent_resp = await _retell_request("PATCH", f"/update-agent/{existing_agent_id}", agent_payload)
            return agent_resp.get("agent_id") or existing_agent_id
        except Exception:
            # Agent deleted upstream → recreate
            agent_resp = await _retell_request("POST", "/create-agent", agent_payload)
            return agent_resp.get("agent_id")
    agent_resp = await _retell_request("POST", "/create-agent", agent_payload)
    return agent_resp.get("agent_id")


async def _retell_create_phone_call(
    agent_id: str,
    to_number: str,
    lead_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Trigger an outbound Retell call.

    Iter 325h — widened to accept ``lead_context`` so the closer agent
    can pass the lead's name + business name + plan + trigger context.
    Those are forwarded as ``retell_llm_dynamic_variables`` per Retell's
    create-phone-call docs so the AI prompt can address the prospect by
    name and reference their business.

    Backwards-compatible:
      - Old call sites that pass ``(agent_id, to_number)`` keep working.
      - Old call sites that only used the returned ``call_id`` string
        can use ``result["call_id"]`` from the dict.

    Returns
    -------
    dict
        ``{"ok": bool, "call_id": str, "error": Optional[str]}``.
    """
    from_number = os.environ.get("RETELL_FROM_NUMBER", "").strip()
    if not from_number:
        return {"ok": False, "call_id": "",
                "error": "RETELL_FROM_NUMBER not set — purchase or import a phone number first"}
    if not agent_id:
        return {"ok": False, "call_id": "",
                "error": "agent_id missing — set RETELL_AGENT_ID or tenant retell_agent_id"}

    payload: Dict[str, Any] = {
        "from_number": from_number,
        "to_number": to_number,
        "override_agent_id": agent_id,
    }
    if lead_context:
        # Stringify every value — Retell only accepts string variables.
        dyn = {k: ("" if v is None else str(v))
               for k, v in lead_context.items()}
        payload["retell_llm_dynamic_variables"] = dyn

    try:
        resp = await _retell_request("POST", "/v2/create-phone-call", payload)
    except Exception as e:
        return {"ok": False, "call_id": "", "error": f"{type(e).__name__}: {e}"}

    call_id = resp.get("call_id", "") if isinstance(resp, dict) else ""
    return {"ok": bool(call_id), "call_id": call_id,
            "error": None if call_id else "no_call_id_in_response"}
