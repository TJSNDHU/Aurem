"""
Shannon Security Router — Red Team Pentest Integration API
===========================================================
Endpoints for receiving Shannon pentest reports from Legion,
viewing security posture, and managing audit history.
"""

import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/security/shannon", tags=["Shannon Security"])


class VulnerabilityReport(BaseModel):
    severity: str = "info"
    title: str = ""
    description: str = ""
    category: str = ""
    file: Optional[str] = None
    line: Optional[int] = None
    verified: bool = False
    exploitable: bool = False
    cwe: Optional[str] = None
    fix_suggestion: Optional[str] = None


class ShannonReport(BaseModel):
    target: str = ""
    url: Optional[str] = None
    timestamp: Optional[str] = None
    duration_seconds: Optional[float] = None
    duration: Optional[float] = None
    scanner: str = "shannon"
    version: Optional[str] = None
    vulnerabilities: Optional[List[Dict[str, Any]]] = None
    findings: Optional[List[Dict[str, Any]]] = None


async def _verify_auth(authorization: str = Header(None)):
    """Verify admin/system auth for sensitive security endpoints."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    try:
        import jwt
        import os
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/report")
async def receive_shannon_report(report: ShannonReport):
    """
    Receive a pentest report from Shannon running on Legion.
    This is the bridge endpoint — Legion pushes results here after each scan.
    
    Usage from Legion:
        npx shannon audit http://localhost:8001 --source ./backend
        curl -X POST https://aurem.live/api/security/shannon/report \
             -H "Content-Type: application/json" \
             -d @shannon-report.json
    """
    from services.shannon_security import ingest_report
    result = await ingest_report(report.model_dump())
    return {
        "status": "ingested",
        "security_score": result["security_score"],
        "total_vulnerabilities": result["total_vulnerabilities"],
        "severity_counts": result["severity_counts"],
        "exploits_verified": result["exploits_verified"],
    }


@router.get("/posture")
async def get_security_posture(authorization: str = Header(None)):
    """Get current security posture summary for dashboards."""
    await _verify_auth(authorization)
    from services.shannon_security import get_security_posture
    return get_security_posture()


@router.get("/report/latest")
async def get_latest_report(authorization: str = Header(None)):
    """Get the full latest Shannon pentest report with vulnerability details."""
    await _verify_auth(authorization)
    from services.shannon_security import get_full_report
    report = await get_full_report()
    if not report:
        return {"status": "no_reports", "message": "No Shannon audits completed yet. Run Shannon on Legion to generate the first report."}
    return report


@router.get("/history")
async def get_audit_history(authorization: str = Header(None)):
    """Get history of Shannon audits for trend visualization."""
    await _verify_auth(authorization)
    from services.shannon_security import get_report_history
    history = await get_report_history()
    return {"audits": history, "total": len(history)}


@router.post("/mock-audit")
async def trigger_mock_audit(authorization: str = Header(None)):
    """
    Trigger a simulated security audit for testing the dashboard UI.
    Use this from your phone to see the Shannon card come to life
    without needing the Legion connected.
    """
    await _verify_auth(authorization)
    from services.shannon_security import generate_mock_audit
    result = await generate_mock_audit()
    return {
        "status": "mock_audit_complete",
        "security_score": result["security_score"],
        "total_vulnerabilities": result["total_vulnerabilities"],
        "severity_counts": result["severity_counts"],
        "note": "This is a simulated audit for UI testing",
    }


@router.post("/run-now")
async def trigger_real_audit(authorization: str = Header(None), target: Optional[str] = None):
    """
    Trigger a REAL in-process Shannon audit NOW.
    Non-destructive probes (TLS, headers, CORS, sensitive paths, HTTP→HTTPS redirect).
    Fire-and-forget: returns immediately, poll /posture for `last_audit`.
    """
    await _verify_auth(authorization)
    import os
    import asyncio
    from services.shannon_runner import run_real_audit

    url = target or os.environ.get("SHANNON_AUDIT_TARGET", "https://aurem.live")

    async def _runner():
        try:
            result = await asyncio.wait_for(run_real_audit(url), timeout=120.0)
            logger.info(f"[shannon/run-now] done: score={result.get('security_score')} vulns={result.get('total_vulnerabilities')}")
        except asyncio.TimeoutError:
            logger.warning("[shannon/run-now] audit exceeded 120s cap")
        except Exception as e:
            logger.error(f"[shannon/run-now] failed: {e}")

    asyncio.create_task(_runner())
    return {
        "status": "started",
        "target": url,
        "scanner": "shannon_runner_v1",
        "message": "Real audit running in background — poll /api/security/shannon/posture for results",
    }


# ═══════════════════════════════════════════════════════════
# Red Team Findings API — Unified endpoint for all consumers
# ═══════════════════════════════════════════════════════════
red_team_router = APIRouter(prefix="/api/security/red-team", tags=["Red Team"])


@red_team_router.get("/findings")
async def get_red_team_findings():
    """
    Public-facing Red Team findings endpoint.
    Returns the latest Shannon pentest findings + a real-time
    code audit of the backend source for common vulnerability patterns.
    No auth required — findings are non-sensitive metadata.
    """
    from services.shannon_security import get_full_report, get_security_posture
    from services.shannon_code_audit import run_code_audit

    # 1. Get latest Shannon report (from Legion or mock)
    shannon_report = await get_full_report()

    # 2. Run live code audit against the backend source
    code_audit = run_code_audit()

    # 3. Merge findings
    all_findings = []

    if shannon_report and shannon_report.get("vulnerabilities"):
        for vuln in shannon_report["vulnerabilities"]:
            all_findings.append({
                "source": "shannon_pentest",
                "severity": vuln.get("severity", "info"),
                "title": vuln.get("title", ""),
                "description": vuln.get("description", ""),
                "file": vuln.get("file"),
                "cwe": vuln.get("cwe"),
                "verified": vuln.get("verified", False),
                "exploitable": vuln.get("exploitable", False),
                "fix_suggestion": vuln.get("fix_suggestion"),
            })

    for finding in code_audit.get("findings", []):
        all_findings.append({
            "source": "code_audit",
            **finding,
        })

    # Calculate combined score
    posture = get_security_posture()
    code_score = code_audit.get("score", 100)
    shannon_score = posture.get("score")

    if shannon_score is not None:
        combined_score = int((shannon_score + code_score) / 2)
    else:
        combined_score = code_score

    return {
        "findings": all_findings,
        "total": len(all_findings),
        "combined_score": combined_score,
        "shannon_score": shannon_score,
        "code_audit_score": code_score,
        "status": _classify_status(all_findings),
    }


def _classify_status(findings: list) -> str:
    """Classify security status based on finding severities."""
    if not findings:
        return "clean"
    severities = {f.get("severity", "info") for f in findings}
    if severities & {"critical", "high"}:
        return "vulnerable"
    if "medium" in severities:
        return "warning"
    return "healthy"


# ═══════════════════════════════════════════════════════════
# PentAGI Full Pentest — Enterprise Only
# ═══════════════════════════════════════════════════════════
pentagi_router = APIRouter(prefix="/api/security/pentest", tags=["PentAGI Pentest"])


class PentestRequest(BaseModel):
    target: str
    scan_type: str = "full"
    description: str = ""


@pentagi_router.post("/run")
async def run_pentest(req: PentestRequest, authorization: str = Header(None)):
    """Start a PentAGI autonomous penetration test. Enterprise only."""
    payload = await _verify_auth(authorization)
    tenant_id = payload.get("tenant_id") or payload.get("business_id") or "aurem_platform"

    # Enterprise tier gate
    from services.plan_enforcement import PLAN_TIERS
    tier = "starter"
    try:
        import server
        if hasattr(server, "db") and server.db:
            ws = await server.db.workspaces.find_one({"tenant_id": tenant_id}, {"_id": 0, "tier": 1, "plan": 1})
            tier = (ws or {}).get("tier") or (ws or {}).get("plan") or "starter"
    except Exception:
        pass

    plan = PLAN_TIERS.get(tier, PLAN_TIERS.get("starter", {}))
    if not plan.get("limits", {}).get("video_generation", False):
        # Enterprise check — reuse video_generation flag as Enterprise indicator
        raise HTTPException(status_code=403, detail=f"Full pentest requires Enterprise plan. Current: {tier.capitalize()}")

    from services.pentagi_service import run_pentest as _run
    result = await _run(req.target, req.scan_type, req.description, tenant_id)

    # Track usage
    try:
        import server
        if hasattr(server, "db") and server.db:
            from datetime import datetime, timezone
            month_key = datetime.now(timezone.utc).strftime("%Y-%m")
            await server.db.content_engine_usage.update_one(
                {"tenant_id": tenant_id, "month": month_key},
                {"$inc": {"pentests_run": 1}},
                upsert=True,
            )
    except Exception:
        pass

    return result


@pentagi_router.get("/status/{pentest_id}")
async def pentest_status(pentest_id: str, authorization: str = Header(None)):
    """Get status and results of a running/completed pentest."""
    payload = await _verify_auth(authorization)
    tenant_id = payload.get("tenant_id") or payload.get("business_id") or "aurem_platform"
    from services.pentagi_service import get_pentest_results
    return await get_pentest_results(pentest_id, tenant_id)


@pentagi_router.get("/history")
async def pentest_history(limit: int = 20, authorization: str = Header(None)):
    """Get pentest history."""
    payload = await _verify_auth(authorization)
    tenant_id = payload.get("tenant_id") or payload.get("business_id") or "aurem_platform"
    from services.pentagi_service import get_pentest_history
    items = await get_pentest_history(tenant_id, limit)
    return {"pentests": items, "count": len(items)}


@pentagi_router.get("/health")
async def pentagi_health(authorization: str = Header(None)):
    """Check if PentAGI is online on Legion."""
    await _verify_auth(authorization)
    from services.pentagi_service import check_pentagi_health
    return await check_pentagi_health()

