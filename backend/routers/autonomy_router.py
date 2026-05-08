"""
AUREM Autonomous Operations Router
POST /api/self-audit/run       — Run full 5-agent audit
GET  /api/self-audit/status    — Latest audit status
GET  /api/self-audit/findings  — All issues found (latest audit)
GET  /api/self-audit/log       — Audit history
GET  /api/self-audit/stats     — Agent performance stats
GET  /api/self-audit/queue     — Problems needing human review
GET  /api/self-audit/tier      — Current survival tier
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/self-audit", tags=["Autonomous Operations"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database
    from services.autonomy_engine import set_db as _set
    _set(database)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        return jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _tenant(p: dict) -> str:
    return p.get("tenant_id") or p.get("business_id") or "aurem_platform"


def _init():
    from services.autonomy_engine import set_db as _set
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _set(server.db)
    except Exception:
        pass


class RunAuditRequest(BaseModel):
    auto_fix: bool = True


@router.post("/run")
async def run_audit(req: RunAuditRequest = RunAuditRequest(), authorization: str = Header(None)):
    """Run full 5-agent self-audit with A2A problem resolution."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import run_full_audit
    report = await run_full_audit(_tenant(p), req.auto_fix)
    return report


@router.get("/status")
async def audit_status(authorization: str = Header(None)):
    """Get latest audit status."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import get_audit_history
    history = await get_audit_history(_tenant(p), limit=1)
    if not history:
        return {"status": "no_audits", "message": "No audits have been run yet"}
    latest = history[0]
    return {
        "audit_id": latest.get("audit_id"),
        "status": latest.get("status"),
        "timestamp": latest.get("timestamp"),
        "total_issues": latest.get("total_issues", 0),
        "auto_fixed": latest.get("auto_fixed", 0),
        "needs_review": latest.get("needs_review", 0),
        "tier": latest.get("tier", {}),
    }


@router.get("/findings")
async def audit_findings(authorization: str = Header(None)):
    """Get all findings from latest audit."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import get_audit_history
    history = await get_audit_history(_tenant(p), limit=1)
    if not history:
        return {"findings": [], "count": 0}
    latest = history[0]
    return {
        "audit_id": latest.get("audit_id"),
        "findings": latest.get("assignments", []),
        "fixes_applied": latest.get("fixes_applied", []),
        "needs_review": latest.get("needs_human_review", []),
        "suggestions": latest.get("suggestions", []),
        "count": latest.get("total_issues", 0),
    }


@router.get("/log")
async def audit_log(limit: int = 10, authorization: str = Header(None)):
    """Get audit history."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import get_audit_history
    audits = await get_audit_history(_tenant(p), limit)
    return {"audits": audits, "count": len(audits)}


@router.get("/stats")
async def agent_stats(authorization: str = Header(None)):
    """Get agent performance statistics."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import get_agent_stats
    stats = await get_agent_stats(_tenant(p))
    return {"agents": stats, "count": len(stats)}


@router.get("/queue")
async def problem_queue(authorization: str = Header(None)):
    """Get problems needing human review."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import get_problem_queue
    problems = await get_problem_queue(_tenant(p))
    return {"problems": problems, "count": len(problems)}


@router.get("/tier")
async def survival_tier(authorization: str = Header(None)):
    """Get current survival tier for tenant."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import get_survival_tier
    tier = await get_survival_tier(_tenant(p))
    return tier


@router.get("/usage")
async def fix_usage(authorization: str = Header(None)):
    """Get monthly auto-fix usage (plan-based limits)."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import get_monthly_fix_usage
    return await get_monthly_fix_usage(_tenant(p))



# ═══════════════════════════════════════
# ITEM 3: APPROVE / REJECT FIX
# ═══════════════════════════════════════

class ApproveRequest(BaseModel):
    audit_id: str
    issue_type: str
    action: str = "approve"


@router.post("/approve")
async def approve_fix(req: ApproveRequest, authorization: str = Header(None)):
    """Approve or reject a suggested fix from the review queue."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import approve_fix as _approve
    result = await _approve(req.audit_id, req.issue_type, req.action, _tenant(p))
    return result


# ═══════════════════════════════════════
# ITEM 4: SCHEDULE MANAGEMENT
# ═══════════════════════════════════════

class ScheduleRequest(BaseModel):
    frequency: str = "daily"
    hour: int = 2
    minute: int = 0
    enabled: bool = True


@router.post("/schedule")
async def set_schedule(req: ScheduleRequest, authorization: str = Header(None)):
    """Set custom auto-audit schedule (daily/weekly/disabled)."""
    await _auth(authorization)
    from services.autonomy_engine import set_audit_schedule
    return set_audit_schedule(req.frequency, req.hour, req.minute, req.enabled)


@router.get("/schedule")
async def get_schedule(authorization: str = Header(None)):
    """Get current audit schedule."""
    await _auth(authorization)
    from services.autonomy_engine import get_audit_schedule
    return get_audit_schedule()


@router.get("/cron-status")
async def cron_status(authorization: str = Header(None)):
    """Get full cron monitoring status — schedule, last/next run, execution history."""
    await _auth(authorization)
    _init()
    from services.autonomy_engine import get_cron_status
    return await get_cron_status()


@router.post("/cron-trigger")
async def cron_trigger(authorization: str = Header(None)):
    """Manually trigger a one-off audit run (bypasses schedule, for testing/monitoring)."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import run_full_audit, _log_cron_execution, _persist_cron_state, _get_db
    t0 = datetime.now(timezone.utc)
    db = _get_db()
    tenant_id = _tenant(p)
    try:
        report = await run_full_audit(tenant_id, auto_fix=True)
        report.pop("_id", None)
        t1 = datetime.now(timezone.utc)
        run_record = {
            "cron_id": "autonomy_nightly",
            "status": "success", "trigger": "manual",
            "started_at": t0.isoformat(), "finished_at": t1.isoformat(),
            "duration_ms": int((t1 - t0).total_seconds() * 1000),
            "tenants_audited": 1, "total_issues": report.get("total_issues", 0),
            "total_fixed": report.get("auto_fixed", 0), "errors": [],
        }
        await _log_cron_execution(db, run_record)
        await _persist_cron_state(db, {"last_run": run_record})
        return {"triggered": True, "report": report, "run_record": run_record}
    except Exception as e:
        return {"triggered": False, "error": str(e)}


# ═══════════════════════════════════════
# ITEM 5: DATA REPLACEMENT / VERIFICATION
# ═══════════════════════════════════════

class VerifyDataRequest(BaseModel):
    record_id: str
    field: str
    current_value: str


@router.post("/verify-data")
async def verify_data(req: VerifyDataRequest, authorization: str = Header(None)):
    """Verify and optionally replace customer data via free APIs (Tomba/Numverify/IPstack)."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import verify_and_replace_data
    result = await verify_and_replace_data(_tenant(p), req.record_id, req.field, req.current_value)
    return result


# ═══════════════════════════════════════
# SAFETY: ROLLBACK + BACKUP
# ═══════════════════════════════════════

@router.post("/rollback/{backup_id}")
async def rollback(backup_id: str, authorization: str = Header(None)):
    """Rollback an auto-fix using its backup. Available for 7 days."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import rollback_fix
    result = await rollback_fix(backup_id, _tenant(p))
    return result


@router.get("/backups")
async def list_backups(limit: int = 20, authorization: str = Header(None)):
    """List available backups (undoable fixes)."""
    p = await _auth(authorization)
    _init()
    from services.autonomy_engine import get_backups
    backups = await get_backups(_tenant(p), limit)
    return {"backups": backups, "count": len(backups)}
