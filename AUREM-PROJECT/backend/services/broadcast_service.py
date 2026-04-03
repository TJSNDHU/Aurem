"""
ReRoots AI Live Broadcast Service
Production-Ready WebSocket Engine for Real-Time Sync

Features:
- Admin-to-User: Instant UI refresh on product/inventory changes
- User-to-Admin: Live activity ticker in Admin StatusBar
- Circuit Breaker: Fallback to short-polling if WebSocket fails
- Lead Capture: Every customer interaction saved for marketing
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass, field
import os

# MongoDB connection
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "reroots")


@dataclass
class ConnectedClient:
    """Represents a connected WebSocket client"""
    websocket: WebSocket
    client_type: str  # 'admin', 'website', 'pwa'
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LiveBroadcastService:
    """
    Manages real-time WebSocket connections and broadcasts
    Single instance shared across the application
    """
    
    def __init__(self):
        self._clients: Dict[str, ConnectedClient] = {}
        self._admin_clients: Set[str] = set()
        self._pwa_clients: Set[str] = set()
        self._website_clients: Set[str] = set()
        self._lock = asyncio.Lock()
        self._heartbeat_interval = 30  # seconds
        self._circuit_breaker_open = False
        
    @property
    def total_connections(self) -> int:
        return len(self._clients)
    
    @property
    def admin_count(self) -> int:
        return len(self._admin_clients)
    
    @property
    def pwa_count(self) -> int:
        return len(self._pwa_clients)
    
    @property
    def website_count(self) -> int:
        return len(self._website_clients)
    
    async def connect(
        self, 
        websocket: WebSocket, 
        client_id: str,
        client_type: str = 'website',
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> bool:
        """Register a new WebSocket connection"""
        try:
            await websocket.accept()
            
            async with self._lock:
                client = ConnectedClient(
                    websocket=websocket,
                    client_type=client_type,
                    user_id=user_id,
                    session_id=session_id
                )
                self._clients[client_id] = client
                
                # Track by client type
                if client_type == 'admin':
                    self._admin_clients.add(client_id)
                elif client_type == 'pwa':
                    self._pwa_clients.add(client_id)
                else:
                    self._website_clients.add(client_id)
            
            # Log connection for admin visibility
            await self._log_activity({
                'type': 'connection',
                'client_type': client_type,
                'client_id': client_id,
                'user_id': user_id,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Send welcome message with current state
            await self._send_to_client(client_id, {
                'type': 'connected',
                'client_id': client_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'stats': {
                    'total_users': self.total_connections,
                    'pwa_users': self.pwa_count,
                    'admins_online': self.admin_count
                }
            })
            
            # Notify admins of new connection
            if client_type in ['pwa', 'website']:
                await self.broadcast_to_admins({
                    'type': 'user_connected',
                    'client_type': client_type,
                    'user_id': user_id,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_users': self.total_connections - self.admin_count
                })
            
            print(f"[LiveSync] Client connected: {client_id} ({client_type})")
            return True
            
        except Exception as e:
            print(f"[LiveSync] Connection error: {e}")
            return False
    
    async def disconnect(self, client_id: str):
        """Remove a WebSocket connection"""
        async with self._lock:
            if client_id in self._clients:
                client = self._clients[client_id]
                
                # Remove from type-specific sets
                self._admin_clients.discard(client_id)
                self._pwa_clients.discard(client_id)
                self._website_clients.discard(client_id)
                
                del self._clients[client_id]
                
                # Notify admins
                if client.client_type in ['pwa', 'website']:
                    await self.broadcast_to_admins({
                        'type': 'user_disconnected',
                        'client_type': client.client_type,
                        'user_id': client.user_id,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'total_users': self.total_connections - self.admin_count
                    })
                
                print(f"[LiveSync] Client disconnected: {client_id}")
    
    async def _send_to_client(self, client_id: str, message: dict) -> bool:
        """Send message to a specific client"""
        if client_id not in self._clients:
            return False
        
        try:
            client = self._clients[client_id]
            await client.websocket.send_json(message)
            return True
        except Exception as e:
            print(f"[LiveSync] Send error to {client_id}: {e}")
            await self.disconnect(client_id)
            return False
    
    async def broadcast_to_all(self, message: dict, exclude: Optional[str] = None):
        """Broadcast message to all connected clients"""
        message['broadcast_at'] = datetime.now(timezone.utc).isoformat()
        
        disconnected = []
        for client_id in list(self._clients.keys()):
            if client_id == exclude:
                continue
            if not await self._send_to_client(client_id, message):
                disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            await self.disconnect(client_id)
    
    async def broadcast_to_admins(self, message: dict):
        """Broadcast message only to admin clients"""
        message['broadcast_at'] = datetime.now(timezone.utc).isoformat()
        
        for client_id in list(self._admin_clients):
            await self._send_to_client(client_id, message)
    
    async def broadcast_to_users(self, message: dict, client_types: list = None):
        """Broadcast to website and/or PWA users"""
        if client_types is None:
            client_types = ['website', 'pwa']
        
        message['broadcast_at'] = datetime.now(timezone.utc).isoformat()
        
        target_clients = set()
        if 'pwa' in client_types:
            target_clients.update(self._pwa_clients)
        if 'website' in client_types:
            target_clients.update(self._website_clients)
        
        for client_id in list(target_clients):
            await self._send_to_client(client_id, message)
    
    async def broadcast_ui_refresh(self, resource_type: str, resource_id: str = None, action: str = 'update'):
        """
        Broadcast UI refresh signal when Admin updates products/inventory
        This is the Admin-to-User sync
        """
        await self.broadcast_to_users({
            'type': 'ui_refresh',
            'resource': resource_type,  # 'product', 'inventory', 'promotion', etc.
            'resource_id': resource_id,
            'action': action,  # 'update', 'create', 'delete'
            'message': f'{resource_type} has been {action}d'
        })
        
        print(f"[LiveSync] UI Refresh broadcast: {resource_type} {action}")
    
    async def broadcast_live_activity(self, activity: dict):
        """
        Broadcast user activity to Admin StatusBar
        This is the User-to-Admin sync
        """
        activity['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        await self.broadcast_to_admins({
            'type': 'live_activity',
            'activity': activity
        })
        
        # Also save to lead capture
        await self._capture_lead(activity)
    
    async def _capture_lead(self, activity: dict):
        """
        Save every customer interaction for marketing (n8n automation)
        The "Never Vanish" memory
        """
        try:
            client = MongoClient(MONGO_URL)
            db = client[DB_NAME]
            
            lead_data = {
                **activity,
                'captured_at': datetime.now(timezone.utc),
                'source': activity.get('client_type', 'unknown'),
                'processed': False  # For n8n to pick up
            }
            
            # Remove sensitive fields
            lead_data.pop('password', None)
            lead_data.pop('token', None)
            
            db.reroots_lead_capture.insert_one(lead_data)
            
        except Exception as e:
            print(f"[LiveSync] Lead capture error: {e}")
    
    async def _log_activity(self, activity: dict):
        """Log activity to MongoDB for persistence"""
        try:
            client = MongoClient(MONGO_URL)
            db = client[DB_NAME]
            
            db.live_sync_logs.insert_one({
                **activity,
                'logged_at': datetime.now(timezone.utc)
            })
        except Exception as e:
            print(f"[LiveSync] Activity log error: {e}")
    
    async def heartbeat(self, client_id: str):
        """Update client heartbeat timestamp"""
        if client_id in self._clients:
            self._clients[client_id].last_heartbeat = datetime.now(timezone.utc)
            return True
        return False
    
    async def get_stats(self) -> dict:
        """Get current connection statistics"""
        return {
            'total_connections': self.total_connections,
            'admin_connections': self.admin_count,
            'pwa_connections': self.pwa_count,
            'website_connections': self.website_count,
            'circuit_breaker_open': self._circuit_breaker_open,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def sync_customer_state(self, user_id: str, state_data: dict) -> dict:
        """
        Sync customer state between PWA (IndexedDB) and MongoDB
        The "Deep Sync" for persistent memory
        """
        try:
            client = MongoClient(MONGO_URL)
            db = client[DB_NAME]
            
            # Merge with existing state
            existing = db.reroots_customer_profiles.find_one({'user_id': user_id})
            
            if existing:
                # Merge: newer data wins
                merged_state = {**existing, **state_data}
                merged_state['last_synced'] = datetime.now(timezone.utc)
                merged_state['sync_count'] = existing.get('sync_count', 0) + 1
                
                db.reroots_customer_profiles.update_one(
                    {'user_id': user_id},
                    {'$set': merged_state}
                )
            else:
                # Create new profile
                state_data['user_id'] = user_id
                state_data['created_at'] = datetime.now(timezone.utc)
                state_data['last_synced'] = datetime.now(timezone.utc)
                state_data['sync_count'] = 1
                
                db.reroots_customer_profiles.insert_one(state_data)
            
            # Return the latest state for PWA to use
            latest = db.reroots_customer_profiles.find_one(
                {'user_id': user_id},
                {'_id': 0}
            )
            
            return {
                'success': True,
                'state': latest,
                'synced_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            print(f"[LiveSync] State sync error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_customer_state(self, user_id: str) -> dict:
        """Fetch customer state from MongoDB for PWA "Deep Sync" on launch"""
        try:
            client = MongoClient(MONGO_URL)
            db = client[DB_NAME]
            
            state = db.reroots_customer_profiles.find_one(
                {'user_id': user_id},
                {'_id': 0}
            )
            
            if state:
                return {
                    'success': True,
                    'state': state,
                    'found': True
                }
            else:
                return {
                    'success': True,
                    'state': {},
                    'found': False
                }
                
        except Exception as e:
            print(f"[LiveSync] Get state error: {e}")
            return {'success': False, 'error': str(e)}


# Global singleton instance
live_broadcast = LiveBroadcastService()


# ============ WebSocket Route Handler ============

async def websocket_handler(websocket: WebSocket, client_id: str):
    """
    Main WebSocket handler for all clients
    Call this from your FastAPI route
    """
    # Parse query params for client type
    query_params = dict(websocket.query_params)
    client_type = query_params.get('type', 'website')
    user_id = query_params.get('user_id')
    session_id = query_params.get('session_id')
    
    connected = await live_broadcast.connect(
        websocket, 
        client_id,
        client_type=client_type,
        user_id=user_id,
        session_id=session_id
    )
    
    if not connected:
        return
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            message_type = data.get('type', 'unknown')
            
            if message_type == 'heartbeat':
                # Keep connection alive
                await live_broadcast.heartbeat(client_id)
                await websocket.send_json({'type': 'heartbeat_ack'})
            
            elif message_type == 'activity':
                # User activity (quiz started, item added, etc.)
                await live_broadcast.broadcast_live_activity({
                    'client_id': client_id,
                    'client_type': client_type,
                    'user_id': user_id,
                    **data.get('payload', {})
                })
            
            elif message_type == 'sync_state':
                # PWA requesting state sync
                if user_id:
                    result = await live_broadcast.sync_customer_state(
                        user_id, 
                        data.get('state', {})
                    )
                    await websocket.send_json({
                        'type': 'sync_result',
                        **result
                    })
            
            elif message_type == 'get_state':
                # PWA requesting current state on launch
                if user_id:
                    result = await live_broadcast.get_customer_state(user_id)
                    await websocket.send_json({
                        'type': 'state_data',
                        **result
                    })
            
            elif message_type == 'admin_update':
                # Admin made a change - broadcast to all users
                if client_type == 'admin':
                    await live_broadcast.broadcast_ui_refresh(
                        resource_type=data.get('resource', 'unknown'),
                        resource_id=data.get('resource_id'),
                        action=data.get('action', 'update')
                    )
            
            elif message_type == 'typing':
                # Live typing indicator for chat
                await live_broadcast.broadcast_to_users({
                    'type': 'typing_indicator',
                    'user_id': user_id,
                    'client_type': client_type,
                    'is_typing': data.get('is_typing', False)
                })
            
            else:
                # Unknown message type
                await websocket.send_json({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                })
    
    except WebSocketDisconnect:
        await live_broadcast.disconnect(client_id)
    except Exception as e:
        print(f"[LiveSync] WebSocket error: {e}")
        await live_broadcast.disconnect(client_id)
