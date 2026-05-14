"""
Agent Observatory Router — Production monitoring & trace explorer.
Provides uptime stats, task counts, trace history, and real-time agent status.
"""
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/admin/agent", tags=["Agent Observatory"])
logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            raise HTTPException(500, "JWT not configured")
        payload = jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
        # Bug-fix #39 — require an admin claim, not just a valid JWT.
        from utils.admin_guard import is_admin_email
        if not (payload.get("is_admin") or payload.get("is_super_admin")
                or payload.get("role") in ("admin", "super_admin")
                or is_admin_email(payload.get("email"))):
            raise HTTPException(403, "Admin access required")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")


# ══════════════════════════════════════════════
# Trace Logger — call from pipeline/services
# ══════════════════════════════════════════════

async def log_trace(
    tenant_id: str,
    session_id: str,
    agent: str,
    action: str,
    steps: list,
    total_duration_ms: int,
    status: str = "completed",
    tools_used: list = None,
    llm_calls: int = 0,
    tokens_used: int = 0,
    error: str = "",
):
    """Log a complete agent trace to agent_traces collection."""
    if _db is None:
        return None
    trace_id = f"trace-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "trace_id": trace_id,
        "tenant_id": tenant_id,
        "session_id": session_id,
        "agent": agent,
        "action": action,
        "started_at": (datetime.now(timezone.utc) - timedelta(milliseconds=total_duration_ms)).isoformat(),
        "completed_at": now,
        "status": status,
        "steps": steps,
        "total_duration_ms": total_duration_ms,
        "tools_used": tools_used or [],
        "llm_calls": llm_calls,
        "tokens_used": tokens_used,
        "error": error,
        "error_rate": 1.0 if status == "failed" else 0.0,
    }
    try:
        await _db.agent_traces.insert_one(doc)
    except Exception as e:
        logger.warning(f"[Observatory] Trace log failed: {e}")
    return trace_id


async def log_pipeline_trace(run_id: str, tenant_id: str, stage_timings: dict, stages: dict, final_status: str):
    """Convert a pipeline run into an agent trace with steps."""
    if _db is None:
        return
    steps = []
    tools_used = set()
    total_ms = 0
    for i, (stage_name, elapsed_ms) in enumerate(stage_timings.items(), 1):
        stage_data = stages.get(stage_name, {})
        step_status = "success"
        if final_status in ("failed", "error") and i == len(stage_timings):
            step_status = "failed"
        steps.append({
            "step_number": i,
            "agent": stage_name.replace("_", " ").title(),
            "action": stage_name,
            "tool_called": stage_name,
            "input_summary": f"Pipeline stage {stage_name}",
            "output_summary": str(stage_data)[:200] if stage_data else "No output",
            "duration_ms": elapsed_ms,
            "status": step_status,
            "error": "",
        })
        tools_used.add(stage_name)
        total_ms += elapsed_ms

    await log_trace(
        tenant_id=tenant_id,
        session_id=run_id,
        agent="OODA Pipeline",
        action=f"pipeline_{final_status}",
        steps=steps,
        total_duration_ms=total_ms,
        status="completed" if "completed" in final_status else ("failed" if "failed" in final_status or "error" in final_status else "completed"),
        tools_used=list(tools_used),
    )


# ══════════════════════════════════════════════
# Stats Endpoint
# ══════════════════════════════════════════════

@router.get("/status")
async def agent_status(request: Request):
    """Live agent status — uptime, tasks, error rate, active sessions."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    # Task counts
    tasks_total = await _db.agent_traces.count_documents({})
    tasks_today = await _db.agent_traces.count_documents({"completed_at": {"$gte": today_start}})

    # Error rate (last 100 traces)
    recent = await _db.agent_traces.find({}, {"_id": 0, "status": 1}).sort("completed_at", -1).limit(100).to_list(100)
    failed = sum(1 for t in recent if t.get("status") == "failed")
    error_rate = round(failed / max(len(recent), 1) * 100, 2)

    # Average response time (last 50 traces)
    recent_times = await _db.agent_traces.find({}, {"_id": 0, "total_duration_ms": 1}).sort("completed_at", -1).limit(50).to_list(50)
    durations = [t.get("total_duration_ms", 0) for t in recent_times if t.get("total_duration_ms")]
    avg_response_ms = round(sum(durations) / max(len(durations), 1))

    # Pipeline runs today
    pipeline_runs_today = await _db.pipeline_runs.count_documents({"started_at": {"$gte": today_start}})

    # Active sessions (traces in last 5 min)
    five_min_ago = (now - timedelta(minutes=5)).isoformat()
    active_sessions = await _db.agent_traces.count_documents({"completed_at": {"$gte": five_min_ago}})

    # LLM calls today
    llm_traces = await _db.agent_traces.find(
        {"completed_at": {"$gte": today_start}}, {"_id": 0, "llm_calls": 1}
    ).to_list(500)
    llm_calls_today = sum(t.get("llm_calls", 0) for t in llm_traces)

    # Last active
    last_trace = await _db.agent_traces.find_one({}, {"_id": 0, "completed_at": 1}, sort=[("completed_at", -1)])
    last_active = last_trace.get("completed_at") if last_trace else now.isoformat()

    # Uptime — based on error rate (simple heuristic)
    uptime_percent = round(100.0 - error_rate, 1)

    return {
        "uptime_percent": uptime_percent,
        "tasks_today": tasks_today,
        "tasks_total": tasks_total,
        "error_rate": error_rate,
        "active_sessions": active_sessions,
        "pipeline_runs_today": pipeline_runs_today,
        "avg_response_ms": avg_response_ms,
        "llm_calls_today": llm_calls_today,
        "last_active": last_active,
    }


# ══════════════════════════════════════════════
# Activity Chart Data (24h)
# ══════════════════════════════════════════════

@router.get("/activity")
async def agent_activity(request: Request):
    """Hourly activity for last 24 hours — for chart."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    now = datetime.now(timezone.utc)
    hours = []
    for i in range(24, 0, -1):
        hour_start = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        count = await _db.agent_traces.count_documents({
            "completed_at": {"$gte": hour_start.isoformat(), "$lt": hour_end.isoformat()}
        })
        hours.append({
            "hour": hour_start.strftime("%H:%M"),
            "count": count,
            "time": hour_start.isoformat(),
        })

    return {"activity": hours}


# ══════════════════════════════════════════════
# Trace Explorer
# ══════════════════════════════════════════════

@router.get("/traces")
async def list_traces(
    request: Request,
    page: int = 1,
    limit: int = 25,
    status: Optional[str] = None,
    tenant_id: Optional[str] = None,
):
    """Paginated trace list with filters."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    query = {}
    if status:
        query["status"] = status
    if tenant_id:
        query["tenant_id"] = tenant_id

    total = await _db.agent_traces.count_documents(query)
    skip = (page - 1) * limit
    traces = await _db.agent_traces.find(query, {"_id": 0}).sort("completed_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"traces": traces, "total": total, "page": page, "limit": limit}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, request: Request):
    """Full trace with all steps."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    trace = await _db.agent_traces.find_one({"trace_id": trace_id}, {"_id": 0})
    if not trace:
        raise HTTPException(404, "Trace not found")
    return trace


# ══════════════════════════════════════════════
# Seed Demo Traces (for demo/first-run)
# ══════════════════════════════════════════════

@router.post("/seed-traces")
async def seed_demo_traces(request: Request):
    """Seed realistic demo trace data for the observatory dashboard."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    existing = await _db.agent_traces.count_documents({})
    if existing > 10:
        return {"success": True, "message": f"Already have {existing} traces", "seeded": 0}

    import random
    now = datetime.now(timezone.utc)
    agents = ["OODA Pipeline", "ORA Repair Engine", "Scout Agent", "Morning Brief", "Customer Scanner", "Campaign Engine"]
    actions = ["pipeline_completed", "repair_scan", "lead_scrape", "brief_generate", "website_scan", "email_sequence"]
    tools_pool = ["scout", "architect", "envoy", "closer", "verifier", "llm", "repair_engine", "camofox", "resend", "scanner"]
    tenants = ["polaris-built-001", "reroots-75ea63e28540", "system"]

    seeded = 0
    for i in range(80):
        hours_ago = random.uniform(0, 72)
        completed = now - timedelta(hours=hours_ago)
        duration = random.randint(200, 4500)
        started = completed - timedelta(milliseconds=duration)
        agent = random.choice(agents)
        status = random.choices(["completed", "completed", "completed", "completed", "failed"], weights=[4, 4, 4, 4, 1])[0]
        num_steps = random.randint(2, 7)
        steps = []
        step_agents = ["Scout", "Architect", "Risk Gate", "Envoy", "Human Loop", "Closer", "Verifier"]
        step_actions_pool = ["scrape_google_maps", "analyze_leads", "risk_check", "send_email", "approve_action", "deploy_fix", "verify_deployment", "generate_report", "scan_website"]
        remaining_ms = duration
        for s in range(num_steps):
            step_dur = random.randint(50, remaining_ms // max(num_steps - s, 1) + 50)
            remaining_ms -= step_dur
            steps.append({
                "step_number": s + 1,
                "agent": step_agents[s % len(step_agents)],
                "action": random.choice(step_actions_pool),
                "tool_called": random.choice(tools_pool),
                "input_summary": f"Step {s+1} input",
                "output_summary": f"Processed successfully" if status != "failed" or s < num_steps - 1 else "Error occurred",
                "duration_ms": max(step_dur, 20),
                "status": "success" if status != "failed" or s < num_steps - 1 else "failed",
                "error": "" if status != "failed" or s < num_steps - 1 else "Timeout after 3000ms",
            })

        llm_calls = random.randint(1, 8)
        used_tools = random.sample(tools_pool, min(random.randint(2, 5), len(tools_pool)))

        doc = {
            "trace_id": f"trace-{uuid.uuid4().hex[:10]}",
            "tenant_id": random.choice(tenants),
            "session_id": f"sess-{uuid.uuid4().hex[:8]}",
            "agent": agent,
            "action": random.choice(actions),
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "status": status,
            "steps": steps,
            "total_duration_ms": duration,
            "tools_used": used_tools,
            "llm_calls": llm_calls,
            "tokens_used": llm_calls * random.randint(200, 1200),
            "error": "" if status != "failed" else "Pipeline execution error",
            "error_rate": 1.0 if status == "failed" else 0.0,
        }
        await _db.agent_traces.insert_one(doc)
        seeded += 1

    return {"success": True, "seeded": seeded}
