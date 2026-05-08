"""
WebSocket Connection Manager — Extracted from server.py
"""
import asyncio
import logging
import json
from typing import Dict, Set, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Store active connections: {client_id: {"websocket": ws, "user_id": str, "is_admin": bool}}
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
            # Clean up disconnected clients
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
            # Clean up disconnected clients
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

# Initialize global WebSocket manager
ws_manager = WebSocketConnectionManager()


# Helper function to broadcast events
async def broadcast_admin_event(event_type: str, data: dict):
    """Broadcast an event to all admin WebSocket connections"""
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await ws_manager.broadcast_to_admins(message)

