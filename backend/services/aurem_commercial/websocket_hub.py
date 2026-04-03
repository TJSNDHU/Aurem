"""
AUREM Commercial Platform - WebSocket Hub
Real-time dashboard updates via Redis Pub/Sub

Features:
- Push live activity updates to dashboard
- Agent status changes
- Notification broadcasts
- Multi-tenant isolation
"""

import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
import os

logger = logging.getLogger(__name__)


class AuremWebSocketHub:
    """
    WebSocket connection manager with Redis Pub/Sub backend.
    Pushes real-time updates to connected dashboards.
    """
    
    CHANNEL_PREFIX = "aurem:ws"
    
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}  # business_id -> connections
        self._redis = None
        self._pubsub = None
        self._listener_task = None
    
    async def connect_redis(self):
        """Connect to Redis for Pub/Sub"""
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            logger.warning("[WebSocketHub] REDIS_URL not set, using local broadcast only")
            return
        
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                redis_url, encoding="utf-8", decode_responses=True
            )
            self._pubsub = self._redis.pubsub()
            logger.info("[WebSocketHub] Connected to Redis Pub/Sub")
        except Exception as e:
            logger.warning(f"[WebSocketHub] Redis Pub/Sub failed: {e}")
    
    async def register(self, websocket: WebSocket, business_id: str):
        """Register a WebSocket connection for a business"""
        await websocket.accept()
        
        if business_id not in self._connections:
            self._connections[business_id] = set()
            # Subscribe to business channel
            if self._pubsub:
                channel = f"{self.CHANNEL_PREFIX}:{business_id}"
                await self._pubsub.subscribe(channel)
        
        self._connections[business_id].add(websocket)
        logger.info(f"[WebSocketHub] Client connected: {business_id} ({len(self._connections[business_id])} total)")
        
        # Send welcome message
        await self._send_to_socket(websocket, {
            "type": "connected",
            "business_id": business_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def unregister(self, websocket: WebSocket, business_id: str):
        """Unregister a WebSocket connection"""
        if business_id in self._connections:
            self._connections[business_id].discard(websocket)
            
            if not self._connections[business_id]:
                del self._connections[business_id]
                # Unsubscribe from channel
                if self._pubsub:
                    channel = f"{self.CHANNEL_PREFIX}:{business_id}"
                    await self._pubsub.unsubscribe(channel)
        
        logger.info(f"[WebSocketHub] Client disconnected: {business_id}")
    
    async def _send_to_socket(self, websocket: WebSocket, data: dict):
        """Send data to a single WebSocket"""
        try:
            await websocket.send_json(data)
        except Exception:
            pass  # Connection may be closed
    
    async def broadcast_to_business(self, business_id: str, message: dict):
        """Broadcast message to all connections for a business"""
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Publish to Redis for cross-instance broadcast
        if self._redis:
            channel = f"{self.CHANNEL_PREFIX}:{business_id}"
            await self._redis.publish(channel, json.dumps(message))
        
        # Also broadcast locally
        await self._local_broadcast(business_id, message)
    
    async def _local_broadcast(self, business_id: str, message: dict):
        """Broadcast to locally connected clients"""
        if business_id not in self._connections:
            return
        
        dead_connections = set()
        
        for websocket in self._connections[business_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_connections.add(websocket)
        
        # Clean up dead connections
        for ws in dead_connections:
            self._connections[business_id].discard(ws)
    
    async def push_activity(
        self,
        business_id: str,
        activity_type: str,
        description: str,
        icon: str = "default",
        metadata: dict = None
    ):
        """Push a live activity update to dashboard"""
        await self.broadcast_to_business(business_id, {
            "type": "activity",
            "activity_type": activity_type,
            "description": description,
            "icon": icon,
            "metadata": metadata or {}
        })
    
    async def push_agent_status(
        self,
        business_id: str,
        agent_name: str,
        status: str,
        task_count: int = 0
    ):
        """Push agent status update"""
        await self.broadcast_to_business(business_id, {
            "type": "agent_status",
            "agent": agent_name,
            "status": status,
            "task_count": task_count
        })
    
    async def push_notification(
        self,
        business_id: str,
        title: str,
        message: str,
        level: str = "info"
    ):
        """Push a notification"""
        await self.broadcast_to_business(business_id, {
            "type": "notification",
            "title": title,
            "message": message,
            "level": level
        })
    
    async def push_metrics_update(
        self,
        business_id: str,
        metrics: dict
    ):
        """Push metrics update"""
        await self.broadcast_to_business(business_id, {
            "type": "metrics",
            "metrics": metrics
        })
    
    def get_connection_count(self, business_id: str = None) -> int:
        """Get number of connected clients"""
        if business_id:
            return len(self._connections.get(business_id, set()))
        return sum(len(conns) for conns in self._connections.values())
    
    async def start_listener(self):
        """Start Redis Pub/Sub listener"""
        if not self._pubsub:
            return
        
        async def listener():
            try:
                async for message in self._pubsub.listen():
                    if message["type"] == "message":
                        channel = message["channel"]
                        business_id = channel.split(":")[-1]
                        data = json.loads(message["data"])
                        await self._local_broadcast(business_id, data)
            except Exception as e:
                logger.error(f"[WebSocketHub] Listener error: {e}")
        
        self._listener_task = asyncio.create_task(listener())
        logger.info("[WebSocketHub] Pub/Sub listener started")


# Singleton
_ws_hub: Optional[AuremWebSocketHub] = None

async def get_websocket_hub() -> AuremWebSocketHub:
    global _ws_hub
    if _ws_hub is None:
        _ws_hub = AuremWebSocketHub()
        await _ws_hub.connect_redis()
        await _ws_hub.start_listener()
    return _ws_hub
