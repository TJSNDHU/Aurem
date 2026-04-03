"""
Compliance Monitor API Routes
═══════════════════════════════════════════════════════════════════
Health Canada compliance scanning endpoints.
═══════════════════════════════════════════════════════════════════
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compliance", tags=["Compliance"])

# Database reference (set by server.py)
_db = None

def set_db(db):
    global _db
    _db = db


class ScanRequest(BaseModel):
    content: str
    content_type: str = "general"
    content_id: Optional[str] = None
    deep_scan: bool = False


class ScanResponse(BaseModel):
    compliant: bool
    severity: str
    blocked: bool
    issue_count: int
    critical_count: int
    warning_count: int
    issues: list
    message: Optional[str] = None


@router.post("/scan", response_model=ScanResponse)
async def scan_content(request: ScanRequest):
    """
    Scan content for Health Canada compliance issues.
    
    Returns:
    - compliant: True if content can be published
    - severity: CRITICAL (blocked), WARNING (allowed with issues), PASS
    - blocked: True if content must not be published
    - issues: List of compliance issues found
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    from services.compliance_monitor import get_compliance_monitor
    
    monitor = get_compliance_monitor(_db)
    
    if request.deep_scan:
        result = await monitor.deep_scan_with_ai(
            content=request.content,
            content_type=request.content_type
        )
    else:
        result = await monitor.scan_content(
            content=request.content,
            content_type=request.content_type,
            content_id=request.content_id
        )
    
    # Convert severity enum to string
    severity = result.get("severity")
    if hasattr(severity, "value"):
        severity = severity.value
    
    return {
        "compliant": result.get("compliant", True),
        "severity": str(severity),
        "blocked": result.get("blocked", False),
        "issue_count": result.get("issue_count", 0),
        "critical_count": result.get("critical_count", 0),
        "warning_count": result.get("warning_count", 0),
        "issues": [
            {
                "type": i.get("type"),
                "severity": str(i.get("severity").value if hasattr(i.get("severity"), "value") else i.get("severity")),
                "phrase": i.get("phrase"),
                "reason": i.get("reason"),
                "suggested": i.get("suggested"),
                "context": i.get("context")
            }
            for i in result.get("issues", [])
        ],
        "message": result.get("ai_assessment") if request.deep_scan else None
    }


@router.get("/history")
async def get_scan_history(
    limit: int = 50,
    severity: Optional[str] = None
):
    """Get compliance scan history."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    from services.compliance_monitor import get_compliance_monitor
    
    monitor = get_compliance_monitor(_db)
    history = await monitor.get_scan_history(limit=limit, severity_filter=severity)
    
    return {
        "success": True,
        "scans": history,
        "count": len(history)
    }


@router.get("/stats")
async def get_compliance_stats():
    """Get compliance scanning statistics."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    from services.compliance_monitor import get_compliance_monitor
    
    monitor = get_compliance_monitor(_db)
    stats = await monitor.get_compliance_stats()
    
    return {
        "success": True,
        "stats": stats
    }
