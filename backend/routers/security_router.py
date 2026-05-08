"""
AUREM Security Router
Administrative endpoints for security monitoring

Endpoints:
- GET /api/security/rate-limits - Check rate limit status
- GET /api/security/lockouts - Check auth lockouts
- GET /api/security/audit-log - Get secrets access audit
- POST /api/security/unlock - Manually unlock an IP/user
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query, Request

from services.security_service import (
    rate_limiter,
    auth_tracker,
    secrets_audit,
    set_security_db
)

router = APIRouter(prefix="/api/security", tags=["Security"])

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    """Set database dependency."""
    global _db
    _db = db
    set_security_db(db)


async def verify_admin_key(x_admin_key: str = Header(None, alias="X-Admin-Key")):
    """Verify admin key for security endpoints."""
    import os
    expected_key = os.environ.get("ADMIN_API_KEY") or os.environ.get("JWT_SECRET", "")[:32]
    
    if not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin key"
        )


@router.get("/rate-limits")
async def get_rate_limit_status(
    request: Request,
    ip: Optional[str] = Query(None, description="Specific IP to check")
):
    """
    Get rate limit status.
    
    If no IP specified, returns stats for the requesting IP.
    """
    check_ip = ip or (request.client.host if request.client else "unknown")
    stats = rate_limiter.get_stats(check_ip)
    
    return {
        "status": "ok",
        "rate_limits": stats,
        "config": {
            "requests_per_minute": rate_limiter.requests_per_minute,
            "block_duration_seconds": rate_limiter.block_duration
        }
    }


@router.get("/lockouts")
async def get_lockout_status(
    request: Request,
    ip: Optional[str] = Query(None),
    username: Optional[str] = Query(None)
):
    """Check if an IP/username is locked out."""
    check_ip = ip or (request.client.host if request.client else "unknown")
    
    is_locked, remaining = await auth_tracker.is_locked(check_ip, username or "")
    
    return {
        "ip": check_ip,
        "username": username or "(any)",
        "is_locked": is_locked,
        "remaining_seconds": remaining,
        "config": {
            "max_attempts": auth_tracker.MAX_ATTEMPTS,
            "lockout_duration_minutes": auth_tracker.LOCKOUT_DURATION // 60
        }
    }


@router.post("/unlock")
async def unlock_ip_user(
    ip: str = Query(..., description="IP address to unlock"),
    username: Optional[str] = Query(None),
    x_admin_key: str = Header(None, alias="X-Admin-Key")
):
    """
    Manually unlock an IP/username.
    
    Requires admin key.
    """
    await verify_admin_key(x_admin_key)
    
    key = auth_tracker._get_key(ip, username or "")
    
    if key in auth_tracker._lockouts:
        del auth_tracker._lockouts[key]
        auth_tracker._attempts[key] = []
        
        logger.info(f"[Security] Manual unlock: IP={ip}, username={username}")
        
        return {
            "success": True,
            "message": f"Unlocked IP {ip}" + (f" for user {username}" if username else "")
        }
    
    return {
        "success": True,
        "message": "IP/user was not locked"
    }


@router.get("/audit-log")
async def get_secrets_audit_log(
    limit: int = Query(100, ge=1, le=500),
    x_admin_key: str = Header(None, alias="X-Admin-Key")
):
    """
    Get secrets access audit log.
    
    Requires admin key.
    """
    await verify_admin_key(x_admin_key)
    
    logs = await secrets_audit.get_recent_access(limit)
    
    return {
        "count": len(logs),
        "logs": logs,
        "retrieved_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/status")
async def get_security_status():
    """Get overall security status summary."""
    return {
        "status": "ok",
        "services": {
            "rate_limiter": "active",
            "auth_tracker": "active",
            "secrets_audit": "active",
            "path_protection": "active"
        },
        "config": {
            "rate_limit": f"{rate_limiter.requests_per_minute} req/min",
            "auth_lockout": f"{auth_tracker.MAX_ATTEMPTS} attempts / {auth_tracker.LOCKOUT_DURATION // 60} min",
            "protected_paths": [
                "/memory/",
                "/.env",
                "/AUDIT_REPORT",
                "/PRD.md",
                "/SECRETS_POLICY"
            ]
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/health")
async def security_health_check():
    """Simple health check for security service."""
    return {"status": "healthy"}


# ═══════════════════════════════════════════════════
# SECURITY REVIEWER (Code Audit)
# ═══════════════════════════════════════════════════

from pydantic import BaseModel
from typing import List


class CodeAuditRequest(BaseModel):
    targets: List[str] = []
    scan_workspace: bool = True
    scan_services: bool = True


class ParseltongueTestRequest(BaseModel):
    text: str
    technique: str = "random"
    intensity: str = "medium"


@router.post("/code-audit")
async def run_code_audit(request: Request, body: CodeAuditRequest):
    """Run the Security Reviewer against codebase targets."""
    import os
    import jwt
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        secret = os.environ.get("JWT_SECRET", "")
        try:
            jwt.decode(token, secret, algorithms=["HS256"])
        except Exception:
            raise HTTPException(401, "Invalid token")
    else:
        await verify_admin_key(request.headers.get("X-Admin-Key"))

    # Lazy db fetch - handles case where db is set after module import
    db_to_use = _db
    if db_to_use is None:
        try:
            import server
            db_to_use = getattr(server, 'db', None)
        except Exception:
            pass

    from services.security_reviewer import scan_directory, run_phase_c_audit
    from pathlib import Path

    results = {"workspace": None, "services": None, "phase_c": None, "summary": {}}

    if body.scan_workspace:
        results["workspace"] = scan_directory(Path("/app/backend/workspace"), extensions=(".md", ".py", ".txt"))

    if body.scan_services or body.targets:
        targets = body.targets or ["/app/backend/services/"]
        for target in targets:
            scan = scan_directory(Path(target))
            if results["services"] is None:
                results["services"] = scan
            else:
                results["services"]["critical_count"] = results["services"].get("critical_count", 0) + scan.get("critical_count", 0)
                results["services"]["major_count"] = results["services"].get("major_count", 0) + scan.get("major_count", 0)

    # Run Phase C audit
    results["phase_c"] = await run_phase_c_audit(db_to_use)

    total_critical = sum(
        r.get("critical_count", 0) for r in [results["workspace"], results["services"]] if r
    )
    total_major = sum(
        r.get("major_count", 0) for r in [results["workspace"], results["services"]] if r
    )

    results["summary"] = {
        "status": "CLEAN" if total_critical == 0 and total_major == 0 else "ALERT",
        "critical_findings": total_critical,
        "major_findings": total_major,
    }

    if db_to_use is not None:
        try:
            from routers.agent_execution_router import create_audit_entry
            await create_audit_entry(db_to_use, action="security_code_audit", agent_id="security_reviewer", data=results["summary"])
        except Exception:
            pass

    return results


# ═══════════════════════════════════════════════════
# PRECOMPACT HOOK (Context Memory Optimization)
# ═══════════════════════════════════════════════════

@router.post("/precompact")
async def run_precompact(request: Request):
    """Run PreCompact Hook — save ORA state and optimize workspace memory."""
    import os
    import jwt
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        secret = os.environ.get("JWT_SECRET", "")
        try:
            jwt.decode(token, secret, algorithms=["HS256"])
        except Exception:
            raise HTTPException(401, "Invalid token")
    else:
        await verify_admin_key(request.headers.get("X-Admin-Key"))

    # Lazy db fetch - handles case where db is set after module import
    db_to_use = _db
    if db_to_use is None:
        try:
            import server
            db_to_use = getattr(server, 'db', None)
        except Exception:
            pass

    from services.precompact_hook import precompact_state, set_db as set_pc_db
    set_pc_db(db_to_use)

    result = await precompact_state(reason="manual_trigger")

    if db_to_use is not None:
        try:
            from routers.agent_execution_router import create_audit_entry
            await create_audit_entry(
                db_to_use, action="precompact_sweep", agent_id="precompact",
                data={"reason": "manual_trigger", "hash": result.get("hash", "")},
            )
        except Exception:
            pass

    return result


@router.get("/precompact/status")
async def precompact_status(request: Request):
    """Get workspace memory status and token estimation."""
    import os
    import jwt
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        secret = os.environ.get("JWT_SECRET", "")
        try:
            jwt.decode(token, secret, algorithms=["HS256"])
        except Exception:
            raise HTTPException(401, "Invalid token")
    else:
        await verify_admin_key(request.headers.get("X-Admin-Key"))

    from services.precompact_hook import _session_msg_counts, COMPACT_THRESHOLD
    from pathlib import Path

    # Estimate workspace tokens by counting chars in workspace files
    workspace_dir = Path("/app/backend/workspace")
    total_chars = 0
    file_count = 0
    if workspace_dir.exists():
        for f in workspace_dir.rglob("*.md"):
            try:
                total_chars += len(f.read_text(encoding="utf-8", errors="ignore"))
                file_count += 1
            except Exception:
                pass

    est_tokens = total_chars // 4  # ~4 chars per token

    return {
        "workspace_tokens": est_tokens,
        "workspace_chars": total_chars,
        "workspace_files": file_count,
        "compact_threshold_msgs": COMPACT_THRESHOLD,
        "active_sessions": len(_session_msg_counts),
        "needs_compaction": est_tokens > 4000,
    }


# ═══════════════════════════════════════════════════
# PARSELTONGUE ADVERSARIAL TESTING
# ═══════════════════════════════════════════════════

@router.post("/parseltongue/test")
async def parseltongue_test(request: Request, body: ParseltongueTestRequest):
    """Run Parseltongue adversarial transformation on input text."""
    import os
    import jwt
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        secret = os.environ.get("JWT_SECRET", "")
        try:
            jwt.decode(token, secret, algorithms=["HS256"])
        except Exception:
            raise HTTPException(401, "Invalid token")
    else:
        await verify_admin_key(request.headers.get("X-Admin-Key"))

    from services.parseltongue import transform
    return transform(body.text, body.technique, body.intensity)


@router.post("/parseltongue/suite")
async def parseltongue_suite(request: Request, body: ParseltongueTestRequest):
    """Run full Parseltongue adversarial suite (all 6 techniques x 3 intensities)."""
    import os
    import jwt
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        secret = os.environ.get("JWT_SECRET", "")
        try:
            jwt.decode(token, secret, algorithms=["HS256"])
        except Exception:
            raise HTTPException(401, "Invalid token")
    else:
        await verify_admin_key(request.headers.get("X-Admin-Key"))

    from services.parseltongue import run_adversarial_suite
    return run_adversarial_suite(body.text)


@router.get("/parseltongue/triggers")
async def parseltongue_triggers(request: Request):
    """List all trigger word categories and counts."""
    import os
    import jwt
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        secret = os.environ.get("JWT_SECRET", "")
        try:
            jwt.decode(token, secret, algorithms=["HS256"])
        except Exception:
            raise HTTPException(401, "Invalid token")
    else:
        await verify_admin_key(request.headers.get("X-Admin-Key"))

    from services.parseltongue import TRIGGERS, ALL_TRIGGERS
    return {
        "total_triggers": len(ALL_TRIGGERS),
        "categories": {k: len(v) for k, v in TRIGGERS.items()},
        "techniques": ["leetspeak", "unicode", "zwj", "mixedcase", "phonetic", "random"],
        "intensities": ["light", "medium", "heavy"],
    }
