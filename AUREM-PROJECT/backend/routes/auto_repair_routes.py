"""
Auto-Repair API Routes
═══════════════════════════════════════════════════════════════════
Endpoints for the autonomous self-repair system.
═══════════════════════════════════════════════════════════════════
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/auto-repair", tags=["Auto-Repair"])

# Database reference
_db = None

def set_db(db):
    global _db
    _db = db
    # Also set db for the service
    from services.auto_repair import set_db as set_repair_db
    set_repair_db(db)


class ApprovalRequest(BaseModel):
    approval_id: str
    action: str  # 'approve' or 'reject'


@router.get("/status")
async def get_auto_repair_status():
    """Get current auto-repair system status."""
    from services.auto_repair import get_repair_stats, get_pending_approvals
    
    stats = await get_repair_stats()
    pending = await get_pending_approvals()
    
    return {
        "success": True,
        "status": "active",
        "stats": stats,
        "pending_approvals": len(pending)
    }


@router.get("/history")
async def get_repair_history(limit: int = 50):
    """Get auto-repair history."""
    from services.auto_repair import get_repair_history
    
    history = await get_repair_history(limit)
    
    return {
        "success": True,
        "repairs": history,
        "count": len(history)
    }


@router.get("/pending")
async def get_pending_approvals_endpoint():
    """Get pending approvals awaiting admin action."""
    from services.auto_repair import get_pending_approvals
    
    pending = await get_pending_approvals()
    
    return {
        "success": True,
        "pending": pending,
        "count": len(pending)
    }


@router.post("/run")
async def trigger_auto_repair():
    """Manually trigger an auto-repair cycle."""
    from services.auto_repair import run_autonomous_repair
    
    try:
        result = await run_autonomous_repair()
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Auto-repair trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve")
async def approve_or_reject_fix(request: ApprovalRequest):
    """Approve or reject a pending fix from the dashboard."""
    from services.auto_repair import process_whatsapp_approval
    
    message = f"{request.action.upper()} {request.approval_id}"
    result = await process_whatsapp_approval(message)
    
    if result:
        return {
            "success": True,
            "message": f"Fix {request.action}d successfully"
        }
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Approval {request.approval_id} not found or already processed"
        )


@router.get("/stats")
async def get_repair_stats_endpoint():
    """Get auto-repair statistics."""
    from services.auto_repair import get_repair_stats
    
    stats = await get_repair_stats()
    
    return {
        "success": True,
        "stats": stats
    }
