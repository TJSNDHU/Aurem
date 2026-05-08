"""
ORA Action Router — Multi-Agent Pipeline Bridge
=================================================
Voice commands flow through the OODA pipeline:
  SCOUT → ARCHITECT → ENVOY → CLOSER → VERIFIER

Replaces the old keyword-matching logic with a staged multi-agent system.
Guardrail Proxy applied on input/output.
"""
import os
import time
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ora", tags=["ORA Action Router"])

from config import JWT_SECRET

_db = None

def set_db(db):
    global _db
    _db = db
    # Wire DB to pipeline and guardrail
    from services.agent_pipeline import set_db as pipe_set_db
    from services.guardrail_proxy import set_db as guard_set_db
    pipe_set_db(db)
    guard_set_db(db)

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db

async def _get_user(request: Request):
    import jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        return jwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


# ═══════════════════════════════════════════════════════════════
# ACTION RESOLUTION (Voice → Pipeline)
# ═══════════════════════════════════════════════════════════════

class ActionRequest(BaseModel):
    text: str = Field(..., description="Voice transcription or chat message")
    context: Optional[dict] = None
    current_url: Optional[str] = None

@router.post("/resolve-action")
async def resolve_action(body: ActionRequest, request: Request):
    """
    Resolve a voice command through the multi-agent OODA pipeline.
    Input is guardrail-checked before entering the pipeline.
    """
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id", "unknown"))
    start_time = time.time()

    # ── INPUT GUARDRAIL ──
    from services.guardrail_proxy import guard_input, check_rate_limit

    rate = await check_rate_limit(tenant_id, "llm_call")
    if not rate["allowed"]:
        raise HTTPException(429, "Rate limit exceeded. Upgrade your plan for higher limits.")

    guard = await guard_input(body.text, tenant_id)
    if not guard["allowed"]:
        return {
            "resolved": False,
            "action_id": None,
            "voice_response": guard.get("voice_response", "I can't process that request."),
            "guardrail": guard["action"],
            "resolution_time_ms": round((time.time() - start_time) * 1000, 1),
        }

    # ── RUN OODA PIPELINE ──
    from services.agent_pipeline import run_pipeline

    result = await run_pipeline(
        text=body.text,
        tenant_id=tenant_id,
        context=body.context,
    )

    # ── OUTPUT GUARDRAIL ──
    from services.guardrail_proxy import guard_output

    if result.get("voice_response"):
        out_guard = guard_output(result["voice_response"], tenant_id)
        if not out_guard["allowed"]:
            result["voice_response"] = out_guard["text"]
            result["output_guardrail"] = out_guard["reason"]

    result["resolution_time_ms"] = round((time.time() - start_time) * 1000, 1)
    return result


# ═══════════════════════════════════════════════════════════════
# ACTION EXECUTION (Direct execution via pipeline)
# ═══════════════════════════════════════════════════════════════

class ExecuteActionRequest(BaseModel):
    action_id: str
    params: Optional[dict] = {}

@router.post("/execute-action")
async def execute_action(body: ExecuteActionRequest, request: Request):
    """Execute a resolved action through the pipeline CLOSER agent."""
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id", "unknown"))
    start_time = time.time()

    from services.guardrail_proxy import check_rate_limit
    rate = await check_rate_limit(tenant_id, "llm_call")
    if not rate["allowed"]:
        raise HTTPException(429, "Rate limit exceeded.")

    from services.agent_pipeline import run_pipeline, ACTION_REGISTRY

    if body.action_id not in ACTION_REGISTRY:
        raise HTTPException(404, f"Unknown action: {body.action_id}")

    action = ACTION_REGISTRY[body.action_id]

    result = await run_pipeline(
        text=action["triggers"][0],
        tenant_id=tenant_id,
        params=body.params,
    )

    # Log execution
    db = get_db()
    await db.ora_action_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "action_id": body.action_id,
        "params": body.params,
        "result_status": result.get("status", "unknown"),
        "pipeline_id": result.get("pipeline_id"),
        "execution_time_ms": round((time.time() - start_time) * 1000, 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    from services.guardrail_proxy import guard_output
    if result.get("voice_response"):
        out_guard = guard_output(result["voice_response"], tenant_id)
        if not out_guard["allowed"]:
            result["voice_response"] = out_guard["text"]

    result["execution_time_ms"] = round((time.time() - start_time) * 1000, 1)
    return result


# ═══════════════════════════════════════════════════════════════
# ACTION CATALOG
# ═══════════════════════════════════════════════════════════════

@router.get("/actions")
async def list_actions():
    """List all available actions ORA can execute."""
    from services.agent_pipeline import ACTION_REGISTRY
    actions = []
    for action_id, action in ACTION_REGISTRY.items():
        actions.append({
            "id": action_id,
            "name": action["name"],
            "engine": action["engine"],
            "voice_triggers": action["triggers"],
            "params": action["params"],
        })
    return {"actions": actions, "total": len(actions)}


# ═══════════════════════════════════════════════════════════════
# PIPELINE STATUS (for ClawChief monitoring)
# ═══════════════════════════════════════════════════════════════

@router.get("/pipeline/status")
async def pipeline_status(request: Request):
    """Get pipeline health for ClawChief monitoring."""
    from services.agent_pipeline import check_pipeline_deadlocks
    deadlocks = await check_pipeline_deadlocks()
    return {
        "deadlocked_pipelines": len(deadlocks),
        "deadlocks": deadlocks[:10],
        "agents": ["SCOUT", "ARCHITECT", "ENVOY", "CLOSER", "VERIFIER"],
        "status": "degraded" if deadlocks else "healthy",
    }


# ═══════════════════════════════════════════════════════════════
# TTFA LATENCY MONITOR (Pulse Dashboard)
# ═══════════════════════════════════════════════════════════════

class LatencyReport(BaseModel):
    session_id: str
    ttfa_ms: float = Field(..., description="Time to First Audio in milliseconds")
    stt_ms: Optional[float] = None
    llm_ms: Optional[float] = None
    tts_ms: Optional[float] = None
    transport: str = "websocket"
    client_vad_ms: Optional[float] = None

@router.post("/pulse/report")
async def report_latency(body: LatencyReport, request: Request):
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": str(uuid.uuid4()),
        "session_id": body.session_id,
        "ttfa_ms": body.ttfa_ms,
        "stt_ms": body.stt_ms,
        "llm_ms": body.llm_ms,
        "tts_ms": body.tts_ms,
        "transport": body.transport,
        "client_vad_ms": body.client_vad_ms,
        "created_at": now,
    }
    await db.latency_pulse.insert_one(entry)
    entry.pop("_id", None)
    return {"recorded": True, "entry": entry}


@router.get("/pulse/stats")
async def latency_stats(request: Request, window: int = 100):
    db = get_db()
    entries = await db.latency_pulse.find({}, {"_id": 0}).sort("created_at", -1).limit(window).to_list(window)
    if not entries:
        return {"avg_ttfa_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0, "samples": 0, "target_ms": 400}
    ttfa_values = sorted([e["ttfa_ms"] for e in entries])
    n = len(ttfa_values)
    return {
        "avg_ttfa_ms": round(sum(ttfa_values) / n, 1),
        "p50_ms": round(ttfa_values[n // 2], 1),
        "p95_ms": round(ttfa_values[int(n * 0.95)], 1) if n > 1 else ttfa_values[0],
        "p99_ms": round(ttfa_values[int(n * 0.99)], 1) if n > 1 else ttfa_values[0],
        "min_ms": round(ttfa_values[0], 1),
        "max_ms": round(ttfa_values[-1], 1),
        "samples": n,
        "target_ms": 400,
        "below_target_pct": round(len([t for t in ttfa_values if t < 400]) / n * 100, 1),
        "recent": entries[:10],
    }


print("[STARTUP] ORA Action Router — Multi-Agent Pipeline + Guardrail loaded", flush=True)
