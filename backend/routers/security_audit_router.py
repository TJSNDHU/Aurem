"""
Security Audit Router — OWASP Agentic AI + ASVS L1 + CI/CD Gate
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/security", tags=["Security"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.security_gate import set_db as set_sg_db
    set_sg_db(database)


async def _get_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if _db is not None and user_id:
            user = await _db.users.find_one({"id": user_id}, {"_id": 0})
            if user and (user.get("is_admin") or user.get("is_super_admin") or user.get("role") == "admin"):
                return user
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/scan/changed")
async def scan_changed(admin=Depends(_get_admin)):
    """Scan git-changed files for security issues (CI/CD gate)."""
    from services.security_gate import scan_changed_files
    result = scan_changed_files("/app")
    return {"status": "ok", **result}


@router.get("/scan/full")
async def scan_full(admin=Depends(_get_admin)):
    """Full codebase security scan."""
    from services.security_gate import scan_full_codebase
    result = scan_full_codebase("/app")
    return {"status": "ok", **result}


@router.get("/audit/asvs")
async def audit_asvs(admin=Depends(_get_admin)):
    """Run ASVS 5.0 Level 1 compliance audit."""
    from services.security_gate import run_asvs_l1_audit
    result = await run_asvs_l1_audit()
    return {"status": "ok", **result}


@router.get("/audit/agentic")
async def audit_agentic(admin=Depends(_get_admin)):
    """Run OWASP Agentic AI Top 10 security audit."""
    from services.security_gate import run_agentic_ai_audit
    result = await run_agentic_ai_audit()
    return {"status": "ok", **result}


@router.get("/audit/history")
async def audit_history(limit: int = 10, admin=Depends(_get_admin)):
    """Get security audit history."""
    if _db is None:
        return {"status": "ok", "audits": []}
    audits = await _db.security_audits.find(
        {}, {"_id": 0}
    ).sort("audited_at", -1).to_list(limit)
    asvs = await _db.asvs_audits.find(
        {}, {"_id": 0}
    ).sort("audited_at", -1).to_list(limit)
    return {"status": "ok", "agentic_audits": audits, "asvs_audits": asvs}


@router.get("/compliance/badge")
async def compliance_badge(admin=Depends(_get_admin)):
    """Get current compliance status badges."""
    asvs_latest = None
    agentic_latest = None
    if _db is not None:
        asvs_latest = await _db.asvs_audits.find_one({}, {"_id": 0}, sort=[("audited_at", -1)])
        agentic_latest = await _db.security_audits.find_one({"type": "agentic_ai"}, {"_id": 0}, sort=[("audited_at", -1)])

    return {
        "status": "ok",
        "asvs_l1": {
            "compliant": asvs_latest.get("compliant", False) if asvs_latest else False,
            "score": asvs_latest.get("score", 0) if asvs_latest else 0,
            "last_audit": asvs_latest.get("audited_at") if asvs_latest else None,
        },
        "agentic_ai": {
            "score": agentic_latest.get("score", 0) if agentic_latest else 0,
            "last_audit": agentic_latest.get("audited_at") if agentic_latest else None,
        },
    }
