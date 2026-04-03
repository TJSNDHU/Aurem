"""
ReRoots — Production WebSocket Fix
File: routes/websocket_fix.py

THE PROBLEM:
  WebSocket connections work in development (localhost) but fail or
  drop in production on the Emergent platform. This is caused by:

  1. Missing WebSocket-specific CORS/headers
  2. Emergent's reverse proxy not forwarding Upgrade: websocket headers
  3. No reconnection logic on the frontend — a single drop kills the
     live updates permanently until page refresh
  4. No heartbeat / ping-pong — idle connections time out after ~60s
  5. Trying to push real-time updates when polling would be safer

SOLUTION STRATEGY:
  A) Fix the backend WebSocket handler (heartbeat + proper headers)
  B) Add automatic reconnection to the frontend
  C) Add a polling fallback for environments where WS is blocked
  D) Replace live dashboard updates with SSE (Server-Sent Events)
     as a more reliable alternative on Emergent

This file provides all four — use whichever fits your case.
"""

import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set

router = APIRouter()


# ════════════════════════════════════════════════════════════════
# OPTION A — FIXED WEBSOCKET BACKEND
# ════════════════════════════════════════════════════════════════

class ConnectionManager:
    """WebSocket connection manager with rooms and heartbeat."""
    
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}   # client_id → websocket
        self.rooms:  Dict[str, Set[str]]  = {}   # room → set of client_ids

    async def connect(self, websocket: WebSocket, client_id: str, room: str = "global"):
        await websocket.accept()
        self.active[client_id] = websocket
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(client_id)
        print(f"WS connected: {client_id} → room:{room} ({len(self.active)} total)")

    def disconnect(self, client_id: str, room: str = "global"):
        self.active.pop(client_id, None)
        if room in self.rooms:
            self.rooms[room].discard(client_id)
        print(f"WS disconnected: {client_id} ({len(self.active)} remaining)")

    async def broadcast_to_room(self, room: str, message: dict):
        if room not in self.rooms:
            return
        dead = []
        for client_id in list(self.rooms[room]):
            ws = self.active.get(client_id)
            if ws:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(client_id)
        for c in dead:
            self.disconnect(c, room)

    async def send_to_client(self, client_id: str, message: dict):
        ws = self.active.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(client_id)

    def stats(self):
        return {"connections": len(self.active), "rooms": {r: len(c) for r, c in self.rooms.items()}}


manager = ConnectionManager()
HEARTBEAT_INTERVAL = 25  # seconds — under the 30s proxy timeout


@router.websocket("/ws/{room}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, room: str, client_id: str):
    """
    WebSocket endpoint with heartbeat.
    URL: wss://reroots.ca/api/ws/{room}/{client_id}
    Rooms: "admin", "orders", "inventory", "global"
    """
    await manager.connect(websocket, client_id, room)
    heartbeat_task = asyncio.create_task(_heartbeat(websocket, client_id))

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "clientId": client_id,
            "room": room,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server": "reroots-api-v2",
        })

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                continue

            msg_type = data.get("type", "")

            if msg_type == "pong":
                continue
            elif msg_type == "subscribe":
                new_room = data.get("room", room)
                manager.rooms.setdefault(new_room, set()).add(client_id)
                await websocket.send_json({"type": "subscribed", "room": new_room})
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({
                    "type": "ack", "received": msg_type, "timestamp": datetime.now(timezone.utc).isoformat()
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS error ({client_id}): {e}")
    finally:
        heartbeat_task.cancel()
        manager.disconnect(client_id, room)


async def _heartbeat(websocket: WebSocket, client_id: str):
    """Sends ping every 25s to keep connection alive through proxies."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_json({"type": "ping", "ts": datetime.now(timezone.utc).isoformat()})
    except Exception:
        pass


# ── Broadcast helpers (call from other routes) ────────────────

async def broadcast_order_update(order: dict):
    """Call from order creation/update to push live update to admin."""
    await manager.broadcast_to_room("admin", {
        "type": "order_update",
        "order": {
            "id":     str(order.get("_id", "")),
            "status": order.get("status", ""),
            "total":  order.get("total", 0),
            "email":  order.get("email", ""),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def broadcast_inventory_update(product_id: str, new_stock: int, product_name: str):
    """Call from inventory update to push stock change to admin."""
    await manager.broadcast_to_room("admin", {
        "type": "inventory_update",
        "productId":  product_id,
        "productName":product_name,
        "stock":      new_stock,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    })


async def broadcast_new_lead(email: str, source: str, product: str = ""):
    """Call from quiz/bio-scan to push new lead notification."""
    await manager.broadcast_to_room("admin", {
        "type":    "new_lead",
        "email":   email[:3] + "***" + email[email.find("@"):] if "@" in email else "***",
        "source":  source,
        "product": product,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection stats."""
    return manager.stats()


# ════════════════════════════════════════════════════════════════
# OPTION C — SSE (Server-Sent Events) ALTERNATIVE
# More reliable than WebSockets on reverse-proxy platforms
# ════════════════════════════════════════════════════════════════

from fastapi.responses import StreamingResponse
from collections import deque

_sse_queues: Dict[str, asyncio.Queue] = {}
_recent_events: deque = deque(maxlen=50)


async def push_sse_event(event_type: str, data: dict):
    """Call this from anywhere to push a live event to all SSE clients."""
    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _recent_events.append(event)
    for q in list(_sse_queues.values()):
        await q.put(event)


async def _sse_stream(client_id: str):
    """Generate SSE events for a client."""
    q = asyncio.Queue()
    _sse_queues[client_id] = q

    try:
        yield f"data: {json.dumps({'type': 'connected', 'clientId': client_id})}\n\n"
        for old_event in list(_recent_events)[-10:]:
            yield f"data: {json.dumps(old_event)}\n\n"

        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=25.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield f": heartbeat {datetime.now(timezone.utc).isoformat()}\n\n"

    except asyncio.CancelledError:
        pass
    finally:
        _sse_queues.pop(client_id, None)


@router.get("/events/{client_id}")
async def sse_events(client_id: str):
    """
    Server-Sent Events endpoint — more reliable than WS on Emergent.
    Frontend: const es = new EventSource("/api/admin/events/my-client-id");
              es.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    return StreamingResponse(
        _sse_stream(client_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


# ════════════════════════════════════════════════════════════════
# FRONTEND HOOKS (save as separate files)
# ════════════════════════════════════════════════════════════════

FRONTEND_WEBSOCKET_HOOK = '''
// src/hooks/useWebSocket.js
// Auto-reconnecting WebSocket hook with polling fallback

import { useState, useEffect, useRef, useCallback } from "react";

const WS_BASE = process.env.REACT_APP_WS_URL
  || (window.location.protocol === "https:" ? "wss:" : "ws:")
  + "//" + window.location.host + "/api";

export function useWebSocket(room = "admin", options = {}) {
  const {
    onMessage,
    reconnectDelay = 2000,
    maxReconnectDelay = 30000,
    pollingFallback = true,
  } = options;

  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [error, setError] = useState(null);
  const [usingPolling, setUsingPolling] = useState(false);

  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const reconnectDelay_ = useRef(reconnectDelay);
  const clientId = useRef(`client-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const mounted = useRef(true);

  const connect = useCallback(() => {
    if (!mounted.current) return;

    const url = `${WS_BASE}/ws/${room}/${clientId.current}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mounted.current) return;
        setConnected(true);
        setError(null);
        setUsingPolling(false);
        reconnectDelay_.current = reconnectDelay;
      };

      ws.onmessage = (event) => {
        if (!mounted.current) return;
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "ping") {
            ws.send(JSON.stringify({ type: "pong" }));
            return;
          }
          if (msg.type === "connected" || msg.type === "pong") return;
          setLastMessage(msg);
          if (onMessage) onMessage(msg);
        } catch (e) {}
      };

      ws.onerror = () => setError("WebSocket error");

      ws.onclose = (event) => {
        if (!mounted.current) return;
        setConnected(false);
        wsRef.current = null;

        if (event.code === 1000) return;

        const delay = Math.min(reconnectDelay_.current, maxReconnectDelay);
        reconnectDelay_.current = delay * 1.5;
        reconnectTimer.current = setTimeout(() => {
          if (mounted.current) connect();
        }, delay);

        if (delay > reconnectDelay * 4 && pollingFallback) {
          setUsingPolling(true);
        }
      };

    } catch (e) {
      setError(e.message);
      if (pollingFallback) setUsingPolling(true);
    }
  }, [room, onMessage, reconnectDelay, maxReconnectDelay, pollingFallback]);

  const send = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    wsRef.current?.close(1000);
    setConnected(false);
  }, []);

  useEffect(() => {
    connect();
    return () => {
      mounted.current = false;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close(1000);
    };
  }, [connect]);

  return { connected, lastMessage, error, usingPolling, send, disconnect };
}
'''


FRONTEND_SSE_HOOK = '''
// src/hooks/useSSE.js
// Server-Sent Events hook — more reliable than WebSocket on Emergent

import { useState, useEffect, useRef, useCallback } from "react";

const API_URL = process.env.REACT_APP_BACKEND_URL || "";

export function useSSE(onMessage) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const eventSourceRef = useRef(null);
  const clientId = useRef(`sse-${Date.now()}-${Math.random().toString(36).slice(2)}`);

  const connect = useCallback(() => {
    const url = `${API_URL}/api/admin/events/${clientId.current}`;
    
    eventSourceRef.current = new EventSource(url);
    
    eventSourceRef.current.onopen = () => {
      setConnected(true);
      setError(null);
    };
    
    eventSourceRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
      } catch (e) {}
    };
    
    eventSourceRef.current.onerror = () => {
      setConnected(false);
      setError("Connection lost");
      eventSourceRef.current?.close();
      setTimeout(connect, 3000);
    };
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => eventSourceRef.current?.close();
  }, [connect]);

  return { connected, error };
}
'''


# ════════════════════════════════════════════════════════════════
# WIRING GUIDE
# ════════════════════════════════════════════════════════════════

WIRING_GUIDE = """
STEP 1 — Add to server.py:
  from routes.websocket_fix import router as ws_router
  from routes.websocket_fix import broadcast_order_update, broadcast_inventory_update
  app.include_router(ws_router, prefix="/api")

STEP 2 — Call broadcasts from existing routes:
  # In POST /api/orders, after insert:
  await broadcast_order_update(order_data)

  # In PUT /api/products/{id}, after stock update:
  await broadcast_inventory_update(str(product_id), new_stock, product_name)

STEP 3 — Add hooks to frontend:
  Save FRONTEND_WEBSOCKET_HOOK as src/hooks/useWebSocket.js
  Save FRONTEND_SSE_HOOK as src/hooks/useSSE.js

STEP 4 — Use in AdminDashboard:
  const { connected } = useWebSocket("admin", {
    onMessage: (msg) => {
      if (msg.type === "order_update") refetchOrders();
      if (msg.type === "inventory_update") refetchInventory();
    }
  });

RECOMMENDATION:
  Use SSE (Option C) on Emergent — it's more reliable because it
  doesn't require the WebSocket upgrade handshake.
"""
