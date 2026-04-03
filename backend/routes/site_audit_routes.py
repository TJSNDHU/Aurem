"""
Site Audit Dashboard Routes
═══════════════════════════════════════════════════════════════════
Admin API endpoints for site health monitoring and audits.

Features:
- Run on-demand site audits
- Get latest audit results
- View audit history
- Manual trigger for daily audit

Daily automated audit runs at 7 AM EST.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/audit", tags=["Site Audit"])

# Database reference
_db = None


def set_db(database):
    """Set database reference from server.py startup."""
    global _db
    _db = database
    
    # Also set for audit service
    from services.site_audit import set_db as set_audit_db
    set_audit_db(database)
    
    logger.info("Site Audit routes: Database reference set")


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.get("/latest")
async def get_latest_audit():
    """
    Get the most recent site audit result.
    
    Returns full audit with all check results.
    """
    from services.site_audit import get_latest_audit
    
    result = await get_latest_audit()
    
    if not result:
        return {
            "message": "No audits found. Run an audit first.",
            "audit": None
        }
    
    return {
        "audit": result
    }


@router.get("/history")
async def get_audit_history(days: int = 7):
    """
    Get audit history for the specified number of days.
    
    Useful for trending and pattern analysis.
    """
    from services.site_audit import get_audit_history
    
    if days < 1 or days > 90:
        days = 7
    
    results = await get_audit_history(days)
    
    return {
        "days": days,
        "count": len(results),
        "audits": results
    }


@router.post("/run")
async def run_audit_now(background_tasks: BackgroundTasks):
    """
    Trigger an immediate site audit.
    
    Runs in background and returns immediately.
    Use /latest to get results after a few seconds.
    """
    from services.site_audit import run_full_audit
    
    # Always use production URL for audits
    base_url = "https://reroots.ca"
    
    # Run audit in background
    background_tasks.add_task(run_full_audit, base_url)
    
    logger.info(f"[AUDIT] Manual audit triggered for {base_url}")
    
    return {
        "message": "Audit started in background",
        "base_url": base_url,
        "status": "running",
        "note": "Check /latest in 10-15 seconds for results"
    }


@router.get("/status")
async def get_audit_status():
    """
    Get current audit system status.
    
    Returns scheduler status and last run time.
    """
    from services.site_audit import get_latest_audit, _audit_task
    
    latest = await get_latest_audit()
    
    return {
        "scheduler_active": _audit_task is not None and not _audit_task.done(),
        "next_run": "7:00 AM EST daily",
        "last_audit": {
            "timestamp": latest.get("timestamp") if latest else None,
            "overall_status": latest.get("overall_status") if latest else None,
            "summary": latest.get("summary") if latest else None
        } if latest else None,
        "whatsapp_alerts": bool(os.environ.get("ADMIN_WHATSAPP"))
    }


@router.get("/summary")
async def get_audit_summary():
    """
    Get a quick summary of site health.
    
    Returns overall status and key metrics.
    """
    from services.site_audit import get_latest_audit
    
    latest = await get_latest_audit()
    
    if not latest:
        return {
            "overall_status": "unknown",
            "message": "No audits available",
            "recommendation": "Run an audit to check site health"
        }
    
    # Build status indicators
    checks = latest.get("checks", [])
    
    status_icons = {
        "pass": "✅",
        "fail": "❌",
        "warn": "⚠️"
    }
    
    check_summary = []
    for check in checks:
        icon = status_icons.get(check.get("status"), "❓")
        check_summary.append({
            "name": check.get("name"),
            "status": check.get("status"),
            "icon": icon
        })
    
    return {
        "overall_status": latest.get("overall_status"),
        "timestamp": latest.get("timestamp"),
        "summary": latest.get("summary"),
        "checks": check_summary,
        "healthy": latest.get("overall_status") == "healthy"
    }


@router.get("/health")
async def audit_health():
    """Health check for audit service."""
    return {
        "status": "ok",
        "service": "site-audit"
    }
