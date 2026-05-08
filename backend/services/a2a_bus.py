"""
AUREM Agent-to-Agent (A2A) Communication Bus
=============================================
Simple publish/subscribe bus for the 4 autonomous AUREM agents
(Hunter / Follow-up / Closer / Referral).

Backed by:
  • In-process asyncio.Queue (fast path, per-process subscribers)
  • MongoDB collection `a2a_events` (durable audit trail + admin UI feed)
  • SSE broadcast (so the Admin Command Center UI sees every event live)

Usage:
    from services.a2a_bus import bus

    # Publishing
    await bus.emit("hunter", "new_lead", {"lead_id": "abc", "business": "Mike's Auto"})

    # Subscribing (inside an agent)
    async for event in bus.subscribe("followup_ora"):
        ...
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class A2ABus:
    """
    Agent-to-Agent message bus.
    All events are persisted to MongoDB and pushed to SSE for admin visibility.
    """
    def __init__(self):
        self._db = None
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        # event_name → list of async handler callables (Phase 1 wiring)
        self._handlers: Dict[str, List[Any]] = {}
        # In-memory tail for the Admin Command Center live feed (no-DB fallback)
        self._tail: deque = deque(maxlen=100)

    def set_db(self, db):
        self._db = db

    async def emit(
        self,
        from_agent: str,
        event: str,
        payload: Optional[Dict[str, Any]] = None,
        to_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Publish an event onto the bus.
        Returns the persisted event doc (safe to JSON-serialize).
        """
        doc = {
            "a2a_id": uuid.uuid4().hex[:12],
            "from_agent": from_agent,
            "to_agent": to_agent or "broadcast",
            "event": event,
            "payload": payload or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 1. In-memory tail for the UI
        self._tail.append(doc)

        # 2. Persist to MongoDB (best-effort, never block the bus on DB errors)
        if self._db is not None:
            try:
                await self._db.a2a_events.insert_one({**doc})
            except Exception as e:
                logger.debug(f"[A2A] persist failed: {e}")

        # 3. Fan-out to in-process subscribers
        #    (agent queues matching to_agent or "broadcast")
        targets = {"broadcast"}
        if to_agent:
            targets.add(to_agent)
        else:
            targets.update(self._subscribers.keys())

        for agent_name in list(targets):
            for q in self._subscribers.get(agent_name, []):
                try:
                    q.put_nowait(doc)
                except Exception:
                    pass

        # 4. SSE broadcast for the Admin Command Center
        try:
            from routers.server_misc_routes import push_sse_event
            await push_sse_event("a2a_event", doc)
        except Exception:
            pass

        # 5. Phase 1 — fire registered handlers in PARALLEL.
        #    Each handler is independent; exceptions are logged but never
        #    crash the bus or block siblings.
        handlers = self._handlers.get(event, [])
        if handlers:
            async def _run(h):
                try:
                    await asyncio.wait_for(h(payload or {}), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning(f"[A2A] handler timeout: {event} → {getattr(h, '__name__', h)}")
                except Exception as e:
                    logger.warning(f"[A2A] handler error: {event} → "
                                   f"{getattr(h, '__name__', h)}: {e}")
                    # Persist to a2a_error_log for ORA Brain to learn from
                    if self._db is not None:
                        try:
                            await self._db.a2a_error_log.insert_one({
                                "event": event,
                                "handler": getattr(h, "__name__", str(h)),
                                "error": f"{type(e).__name__}: {e}",
                                "ts": datetime.now(timezone.utc),
                            })
                        except Exception:
                            pass

            async def _run_all():
                await asyncio.gather(
                    *[_run(h) for h in handlers],
                    return_exceptions=True,
                )
            # Fire-and-forget so emit() never blocks the publisher
            asyncio.create_task(_run_all())

        return doc

    def subscribe_queue(self, agent_name: str) -> asyncio.Queue:
        """Register a new asyncio.Queue subscription for an agent."""
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.setdefault(agent_name, []).append(q)
        return q

    def subscribe(self, event: str, handler) -> None:
        """Phase 1 — register an async handler for a specific event.

        Handlers are invoked in PARALLEL via asyncio.gather inside emit().
        Each handler is called as ``await handler(payload)`` with a 10s
        timeout. Exceptions are logged but never crash the bus.
        """
        self._handlers.setdefault(event, []).append(handler)

    def unsubscribe_queue(self, agent_name: str, q: asyncio.Queue):
        try:
            self._subscribers.get(agent_name, []).remove(q)
        except ValueError:
            pass

    def recent(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Return the last N events (newest first) for the admin UI."""
        return list(reversed(list(self._tail)))[:limit]


# Module-level singleton
bus = A2ABus()
