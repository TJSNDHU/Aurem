"""
Approval Router — Smart Approval Queue API
Endpoints for managing the hybrid auto/manual approval system.
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header, Body

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approvals", tags=["Approvals"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.smart_approval import set_db as set_sa_db
    set_sa_db(database)


async def _get_user(authorization: str = Header(None)):
    """Get authenticated user from JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if _db is not None and user_id:
            user = await _db.users.find_one({"id": user_id}, {"_id": 0})
            if user:
                return user
    except Exception:
        pass
    raise HTTPException(status_code=401, detail="Invalid token")


# ═══════════════════════════════════════
# PENDING APPROVALS
# ═══════════════════════════════════════

@router.get("/pending")
async def get_pending(user=Depends(_get_user)):
    """Get all pending manual approvals."""
    from services.smart_approval import get_pending_approvals
    is_admin = user.get("is_admin") or user.get("is_super_admin") or user.get("role") == "admin"
    tenant_id = None if is_admin else user.get("tenant_id", user.get("id"))
    approvals = await get_pending_approvals(tenant_id)
    return {"approvals": approvals, "count": len(approvals)}


# ═══════════════════════════════════════
# APPROVE / REJECT
# ═══════════════════════════════════════

@router.post("/{approval_id}/approve")
async def approve_action(approval_id: str, user=Depends(_get_user)):
    """Approve a pending action."""
    from services.smart_approval import process_approval
    result = await process_approval(approval_id, "approve", decided_by=user.get("email", "admin"))
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{approval_id}/reject")
async def reject_action(approval_id: str, body: dict = Body(default={}), user=Depends(_get_user)):
    """Reject a pending action with reason."""
    reason = body.get("reason", "")
    from services.smart_approval import process_approval
    result = await process_approval(approval_id, "reject", reason=reason, decided_by=user.get("email", "admin"))
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ═══════════════════════════════════════
# BULK ACTIONS
# ═══════════════════════════════════════

@router.post("/bulk")
async def bulk_process(body: dict = Body(...), user=Depends(_get_user)):
    """Bulk approve or reject multiple approvals."""
    ids = body.get("ids", [])
    decision = body.get("decision", "approve")
    reason = body.get("reason", "")

    if not ids:
        raise HTTPException(status_code=400, detail="No approval IDs provided")
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")

    from services.smart_approval import process_approval
    results = []
    for aid in ids:
        result = await process_approval(aid, decision, reason=reason, decided_by=user.get("email", "admin"))
        results.append(result)

    success = sum(1 for r in results if not r.get("error"))
    return {"processed": len(ids), "success": success, "results": results}


# ═══════════════════════════════════════
# HISTORY
# ═══════════════════════════════════════

@router.get("/history")
async def get_history(limit: int = 50, user=Depends(_get_user)):
    """Get approval decision history with pattern learning progress."""
    from services.smart_approval import get_approval_history, get_approval_stats
    is_admin = user.get("is_admin") or user.get("is_super_admin") or user.get("role") == "admin"
    tenant_id = None if is_admin else user.get("tenant_id", user.get("id"))
    history = await get_approval_history(tenant_id, limit)
    stats = await get_approval_stats(tenant_id)
    return {"history": history, "stats": stats}


# ═══════════════════════════════════════
# STATS
# ═══════════════════════════════════════

@router.get("/stats")
async def get_stats(user=Depends(_get_user)):
    """Get approval statistics and automation rate."""
    from services.smart_approval import get_approval_stats
    is_admin = user.get("is_admin") or user.get("is_super_admin") or user.get("role") == "admin"
    tenant_id = None if is_admin else user.get("tenant_id", user.get("id"))
    return await get_approval_stats(tenant_id)


# ═══════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════

@router.get("/settings")
async def get_settings(user=Depends(_get_user)):
    """Get current approval settings."""
    from services.smart_approval import get_tenant_settings
    tenant_id = user.get("tenant_id", user.get("id"))
    return await get_tenant_settings(tenant_id)


@router.put("/settings")
async def update_settings(body: dict = Body(...), user=Depends(_get_user)):
    """Update approval settings for the tenant."""
    from services.smart_approval import update_tenant_settings
    tenant_id = user.get("tenant_id", user.get("id"))
    result = await update_tenant_settings(tenant_id, body)
    return result


# ═══════════════════════════════════════
# PATTERN LEARNING
# ═══════════════════════════════════════

@router.get("/patterns")
async def get_patterns(user=Depends(_get_user)):
    """Get pattern learning statistics."""
    from services.smart_approval import get_pattern_stats
    tenant_id = user.get("tenant_id", user.get("id"))
    return await get_pattern_stats(tenant_id)


# ═══════════════════════════════════════
# WHATSAPP WEBHOOK
# ═══════════════════════════════════════

@router.post("/whatsapp/reply")
async def whatsapp_reply(body: dict = Body(...)):
    """Process incoming WhatsApp approval replies (from Twilio webhook)."""
    message = body.get("Body", body.get("message", ""))
    if not message:
        raise HTTPException(status_code=400, detail="No message body")

    from services.smart_approval import parse_whatsapp_reply, process_approval, get_pending_approvals

    parsed = parse_whatsapp_reply(message)

    if parsed["command"] == "approve":
        result = await process_approval(parsed["action_id"], "approve", decided_by="whatsapp")
        return {"status": "processed", "result": result}

    elif parsed["command"] == "reject":
        result = await process_approval(parsed["action_id"], "reject", reason="Rejected via WhatsApp", decided_by="whatsapp")
        return {"status": "processed", "result": result}

    elif parsed["command"] == "cancel":
        result = await process_approval(parsed["action_id"], "reject", reason="Cancelled via STOP", decided_by="whatsapp")
        return {"status": "cancelled", "result": result}

    elif parsed["command"] == "stop_all":
        pending = await get_pending_approvals()
        results = []
        for p in pending:
            r = await process_approval(p["approval_id"], "reject", reason="STOP ALL via WhatsApp", decided_by="whatsapp")
            results.append(r)
        return {"status": "all_stopped", "count": len(results)}

    return {"status": "unrecognized", "parsed": parsed}
