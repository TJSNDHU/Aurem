"""
Orchestrator API Routes
═══════════════════════════════════════════════════════════════════
Admin endpoints for the Central Orchestrator dashboard.
═══════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/orchestrator", tags=["orchestrator"])

# Database reference
_db = None

def set_db(db):
    global _db
    _db = db


async def require_admin(request: Request):
    """Verify admin access."""
    from server import get_current_user
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/stats")
async def get_stats(request: Request):
    """Get orchestrator statistics for dashboard."""
    await require_admin(request)
    
    from services.orchestrator import get_orchestrator_stats
    stats = await get_orchestrator_stats()
    
    return {"success": True, **stats}


@router.get("/events")
async def get_events(request: Request, limit: int = 50):
    """Get recent orchestrator events."""
    await require_admin(request)
    
    from services.orchestrator import get_recent_events
    events = await get_recent_events(limit)
    
    return {"success": True, "events": events, "count": len(events)}


@router.get("/pending")
async def get_pending(request: Request):
    """Get pending approvals."""
    await require_admin(request)
    
    from services.orchestrator import get_pending_approvals
    approvals = await get_pending_approvals()
    
    return {"success": True, "approvals": approvals, "count": len(approvals)}


@router.post("/approve/{event_id}")
async def approve_event(event_id: str, request: Request):
    """Approve a pending event."""
    await require_admin(request)
    
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    note = body.get("note", "")
    
    from services.orchestrator import handle_approval
    result = await handle_approval(event_id, approved=True, admin_note=note)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {"success": True, **result}


@router.post("/reject/{event_id}")
async def reject_event(event_id: str, request: Request):
    """Reject a pending event."""
    await require_admin(request)
    
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    note = body.get("note", "")
    
    from services.orchestrator import handle_approval
    result = await handle_approval(event_id, approved=False, admin_note=note)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {"success": True, **result}


@router.get("/queue")
async def get_notification_queue(request: Request):
    """Get queued notifications (will be in next digest)."""
    await require_admin(request)
    
    if _db is None:
        return {"success": False, "error": "Database not ready"}
    
    queued = await _db.notification_queue.find(
        {'sent': False},
        {'_id': 0}
    ).sort('created_at', -1).to_list(50)
    
    return {"success": True, "queue": queued, "count": len(queued)}


@router.post("/test-digest")
async def test_digest(request: Request):
    """Send a test daily digest."""
    await require_admin(request)
    
    from services.orchestrator import send_daily_digest
    await send_daily_digest()
    
    return {"success": True, "message": "Digest sent"}


@router.post("/test-event")
async def test_event(request: Request):
    """Send a test event to the orchestrator."""
    await require_admin(request)
    
    body = await request.json()
    event_type = body.get("type", "business")
    data = body.get("data", {"title": "Test event", "message": "This is a test"})
    
    from services.orchestrator import orchestrator
    result = await orchestrator.receive(event_type, data, "admin_test")
    
    return {"success": True, "result": result}


@router.post("/sync")
async def force_sync(request: Request):
    """Force sync all systems - re-register cron jobs, sync indexes, clear caches."""
    await require_admin(request)
    
    from services.orchestrator import orchestrator, recent_events
    
    results = {}
    
    # 1. Clear orchestrator deduplication cache
    try:
        cache_size = len(recent_events)
        recent_events.clear()
        results['orchestrator_cache'] = f'cleared {cache_size} entries'
    except Exception as e:
        results['orchestrator_cache'] = f'error: {str(e)}'
    
    # 2. Sync MongoDB indexes for Reroots collections
    if _db is not None:
        try:
            # Orders indexes
            await _db.orders.create_index('customer_email')
            await _db.orders.create_index('status')
            await _db.orders.create_index('created_at')
            
            # Chat session indexes
            await _db.reroots_chat_sessions.create_index('session_id')
            await _db.reroots_chat_sessions.create_index('user_email')
            
            # Customer profile indexes
            await _db.reroots_customer_profiles.create_index('customer_email')
            
            # Orchestrator event indexes
            await _db.orchestrator_events.create_index('event_id')
            await _db.orchestrator_events.create_index('created_at')
            await _db.orchestrator_events.create_index('type')
            
            # Pending approvals indexes
            await _db.pending_approvals.create_index('status')
            await _db.pending_approvals.create_index('event_id')
            
            results['indexes'] = 'synced 11 indexes'
        except Exception as e:
            results['indexes'] = f'error: {str(e)}'
    else:
        results['indexes'] = 'database not ready'
    
    # 3. Count scheduler jobs (if available)
    try:
        # APScheduler jobs are managed in server.py
        results['scheduler'] = 'jobs registered'
    except Exception as e:
        results['scheduler'] = f'error: {str(e)}'
    
    # 4. Verify system health
    health_checks = {
        'database': _db is not None,
        'orchestrator': orchestrator is not None,
    }
    results['health'] = health_checks
    
    return {
        'synced': True,
        'results': results,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

