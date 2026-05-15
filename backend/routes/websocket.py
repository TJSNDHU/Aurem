"""
WebSocket Routes: Real-time connection management for admin dashboard and live updates.
"""
import logging
import asyncio
import uuid
import jwt
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException

from config import get_database, JWT_SECRET, JWT_ALGORITHM
from utils.auth import require_admin

# Initialize router
router = APIRouter(tags=["WebSocket"])


class WebSocketConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, dict] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str, user_id: str = None, is_admin: bool = False):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            self.active_connections[client_id] = {
                "websocket": websocket,
                "user_id": user_id,
                "is_admin": is_admin,
                "connected_at": datetime.now(timezone.utc).isoformat()
            }
        logging.info(f"WebSocket connected: {client_id} (admin: {is_admin})")
    
    async def disconnect(self, client_id: str):
        """Remove a WebSocket connection"""
        async with self._lock:
            if client_id in self.active_connections:
                del self.active_connections[client_id]
        logging.info(f"WebSocket disconnected: {client_id}")
    
    async def send_personal_message(self, message: dict, client_id: str):
        """Send a message to a specific client"""
        async with self._lock:
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id]["websocket"].send_json(message)
                except Exception as e:
                    logging.error(f"Failed to send message to {client_id}: {e}")
    
    async def broadcast_to_admins(self, message: dict):
        """Broadcast a message to all admin connections"""
        async with self._lock:
            disconnected = []
            for client_id, conn in self.active_connections.items():
                if conn.get("is_admin"):
                    try:
                        await conn["websocket"].send_json(message)
                    except Exception as e:
                        logging.error(f"Failed to broadcast to admin {client_id}: {e}")
                        disconnected.append(client_id)
            for client_id in disconnected:
                del self.active_connections[client_id]
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast a message to all connections"""
        async with self._lock:
            disconnected = []
            for client_id, conn in self.active_connections.items():
                try:
                    await conn["websocket"].send_json(message)
                except Exception as e:
                    logging.error(f"Failed to broadcast to {client_id}: {e}")
                    disconnected.append(client_id)
            for client_id in disconnected:
                del self.active_connections[client_id]
    
    def get_connection_count(self) -> dict:
        """Get count of active connections"""
        admin_count = sum(1 for c in self.active_connections.values() if c.get("is_admin"))
        return {
            "total": len(self.active_connections),
            "admin": admin_count,
            "user": len(self.active_connections) - admin_count
        }


# Global WebSocket manager instance
ws_manager = WebSocketConnectionManager()


async def broadcast_admin_event(event_type: str, data: dict):
    """Broadcast an event to all admin WebSocket connections"""
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await ws_manager.broadcast_to_admins(message)


async def broadcast_inventory_update(product_id: str, new_stock: int, product_name: str = None):
    """Broadcast inventory update to all connections"""
    await ws_manager.broadcast_to_all({
        "type": "inventory_update",
        "data": {
            "product_id": product_id,
            "stock": new_stock,
            "product_name": product_name
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# WebSocket endpoint (will be mounted on app, not router)
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time updates.

    Bug-fix #52 — JWT used to be transmitted strictly via ?token= URL
    query param, which got logged to Nginx access logs. We now accept
    the token via either:
      1) The first WebSocket message: {"type": "auth", "token": "..."}
         (preferred — keeps the JWT out of access logs); OR
      2) The legacy `?token=` query param (kept for backwards compat
         until all PWA clients migrate; will be removed in a future
         release once PWA coordination completes).
    """
    db = get_database()
    client_id = str(uuid.uuid4())
    user_id = None
    is_admin = False

    async def _decode_and_apply(tok: str) -> None:
        nonlocal user_id, is_admin
        try:
            payload = jwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("user_id") or payload.get("sub")
            user = await db.users.find_one({"id": user_id}, {"_id": 0})
            if user:
                is_admin = user.get("is_admin", False) or user.get("is_super_admin", False)
            else:
                is_admin = bool(payload.get("is_admin") or payload.get("is_super_admin")
                                or payload.get("role") in ("admin", "super_admin"))
        except jwt.InvalidTokenError:
            pass

    try:
        # Legacy query-string fallback (deprecated — see Bug-fix #52)
        legacy_token = websocket.query_params.get("token")
        if legacy_token:
            await _decode_and_apply(legacy_token)

        await ws_manager.connect(websocket, client_id, user_id, is_admin)

        await websocket.send_json({
            "type": "connection_established",
            "client_id": client_id,
            "is_admin": is_admin,
            "auth_required": user_id is None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        while True:
            try:
                data = await websocket.receive_json()

                # Bug-fix #52 — preferred auth path: first-message JWT
                if data.get("type") == "auth" and data.get("token"):
                    await _decode_and_apply(data["token"])
                    async with ws_manager._lock:
                        if client_id in ws_manager.active_connections:
                            ws_manager.active_connections[client_id]["user_id"] = user_id
                            ws_manager.active_connections[client_id]["is_admin"] = is_admin
                    await websocket.send_json({
                        "type": "auth_result",
                        "authenticated": user_id is not None,
                        "is_admin": is_admin,
                    })
                    continue

                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})

                elif data.get("type") == "subscribe":
                    channel = data.get("channel")
                    await websocket.send_json({
                        "type": "subscribed",
                        "channel": channel,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

            except Exception as e:
                logging.debug(f"WebSocket receive error: {e}")
                break

    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        await ws_manager.disconnect(client_id)


# Admin status endpoint
@router.get("/admin/websocket/status")
async def get_websocket_status(request: Request):
    """Get WebSocket connection statistics"""
    await require_admin(request)
    return {
        "connections": ws_manager.get_connection_count(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
