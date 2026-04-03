"""
ReRoots AI Live Sync Router
WebSocket endpoints for real-time bi-directional sync

Routes:
- /api/live/ws/{client_id} - Main WebSocket connection
- /api/live/stats - Get connection statistics
- /api/live/broadcast - Admin broadcast endpoint
- /api/live/sync - State sync endpoint (REST fallback)
"""

from fastapi import APIRouter, WebSocket, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
from datetime import datetime, timezone

from services.broadcast_service import live_broadcast, websocket_handler

router = APIRouter(prefix="/api/live", tags=["Live Sync"])


# ============ Pydantic Models ============

class BroadcastRequest(BaseModel):
    resource: str  # 'product', 'inventory', 'promotion'
    resource_id: Optional[str] = None
    action: str = 'update'  # 'update', 'create', 'delete'
    message: Optional[str] = None


class StateSyncRequest(BaseModel):
    user_id: str
    state: Dict[str, Any]


class ActivityRequest(BaseModel):
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    activity_type: str  # 'quiz_started', 'cart_add', 'page_view', etc.
    data: Optional[Dict[str, Any]] = None


# ============ WebSocket Endpoint ============

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    Main WebSocket connection for live sync
    
    Query params:
    - type: 'admin' | 'pwa' | 'website'
    - user_id: Optional user ID
    - session_id: Optional session ID
    """
    await websocket_handler(websocket, client_id)


@router.websocket("/ws")
async def websocket_endpoint_auto_id(websocket: WebSocket):
    """WebSocket with auto-generated client ID"""
    client_id = f"client_{uuid.uuid4().hex[:12]}"
    await websocket_handler(websocket, client_id)


# ============ REST Endpoints (Fallback + Admin) ============

@router.get("/stats")
async def get_live_stats():
    """Get current WebSocket connection statistics"""
    stats = await live_broadcast.get_stats()
    return stats


@router.post("/broadcast")
async def admin_broadcast(request: BroadcastRequest):
    """
    Admin endpoint to broadcast UI refresh
    Called when Admin updates products, inventory, promotions
    """
    await live_broadcast.broadcast_ui_refresh(
        resource_type=request.resource,
        resource_id=request.resource_id,
        action=request.action
    )
    
    return {
        "success": True,
        "message": f"Broadcast sent: {request.resource} {request.action}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/sync")
async def sync_state(request: StateSyncRequest):
    """
    REST fallback for state sync when WebSocket unavailable
    Circuit Breaker fallback - short polling every 30 seconds
    """
    result = await live_broadcast.sync_customer_state(
        request.user_id,
        request.state
    )
    return result


@router.get("/state/{user_id}")
async def get_state(user_id: str):
    """
    Get customer state for PWA "Deep Sync" on launch
    """
    result = await live_broadcast.get_customer_state(user_id)
    return result


@router.post("/activity")
async def log_activity(request: ActivityRequest):
    """
    Log user activity for Admin visibility and lead capture
    REST fallback when WebSocket not available
    """
    await live_broadcast.broadcast_live_activity({
        'user_id': request.user_id,
        'session_id': request.session_id,
        'activity_type': request.activity_type,
        'data': request.data or {},
        'source': 'rest_fallback'
    })
    
    return {
        "success": True,
        "captured": True,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/health")
async def live_sync_health():
    """Health check for Circuit Breaker monitoring"""
    stats = await live_broadcast.get_stats()
    
    return {
        "status": "healthy",
        "websocket_active": stats['total_connections'] > 0,
        "connections": stats,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/leads")
async def get_unprocessed_leads(limit: int = 50):
    """
    Get unprocessed leads for n8n automation
    Mark as processed after retrieval
    """
    try:
        from pymongo import MongoClient
        import os
        
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        # Get unprocessed leads
        leads = list(db.reroots_lead_capture.find(
            {'processed': False},
            {'_id': 0}
        ).sort('captured_at', -1).limit(limit))
        
        # Mark as processed
        if leads:
            db.reroots_lead_capture.update_many(
                {'processed': False},
                {'$set': {'processed': True, 'processed_at': datetime.now(timezone.utc)}}
            )
        
        return {
            "success": True,
            "leads": leads,
            "count": len(leads)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
