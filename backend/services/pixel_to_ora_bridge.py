"""
Pixel → ORA Bridge — iter 323g
═══════════════════════════════════════════════════════════════════════════
Monitors `pixel_events` collection, detects actionable issues, and enqueues
work for ORA (either as a fast pixel-patch task or as a GitHub code-push
task, depending on whether the tenant has a connected GitHub repo).

This module ONLY enqueues. A separate ORA worker (out of scope) dequeues
from `pixel_ora_tasks` and calls `/api/ora-chat/ask` or `/api/github/push-fix`.

Design constraints:
  • Cheap cron path — NO LLM calls during scan
  • Dedup within 60 minutes per (tenant_id, event_type)
  • Tenant-scoped writes only — never mutate other tenants' data
  • db is injected (no `from server import …`)
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Event types we consider actionable
TRIGGER_EVENTS = {"js_error", "patch_failed", "form_error"}

# Scan window — how far back to look on each cycle
SCAN_WINDOW_MIN = 10

# Dedup window — same tenant+event within this many minutes is ignored
DEDUP_WINDOW_MIN = 60

# Score threshold — performance events below this become tasks too
SCORE_THRESHOLD = 50


def _infer_patch_type(event_type: str) -> str:
    """Infer the patch surface from the event type."""
    if event_type == "form_error":
        return "html"
    if event_type == "js_error":
        return "js"
    if event_type == "patch_failed":
        return "html"
    return "css"


class PixelToOraBridge:
    """Bridge cron worker — scans pixel_events and enqueues ORA tasks."""

    last_run_at: Optional[datetime] = None
    last_event_count: int = 0
    last_summary: Dict[str, Any] = {}

    async def run_cycle(self, db) -> Dict[str, Any]:
        """Public entry — runs ONE scan cycle. Returns summary dict."""
        started = datetime.now(timezone.utc)
        events = await self._scan_recent_events(db, minutes=SCAN_WINDOW_MIN)
        enqueued = 0
        skipped_dedup = 0
        github_tasks = 0
        patch_tasks = 0
        errors = 0
        # In-cycle dedup: same (tenant, event_type) pair seen this scan
        in_cycle_seen: set = set()

        for event in events:
            tenant_id = event.get("tenant_id") or event.get("business_id")
            event_type = event.get("event") or "unknown"
            if not tenant_id:
                continue
            key = (tenant_id, event_type)
            try:
                if key in in_cycle_seen:
                    skipped_dedup += 1
                    continue
                if await self._is_duplicate(db, tenant_id, event_type):
                    skipped_dedup += 1
                    in_cycle_seen.add(key)
                    continue
                kind = await self._route_event(db, event)
                if kind == "github":
                    github_tasks += 1
                elif kind == "patch":
                    patch_tasks += 1
                enqueued += 1
                in_cycle_seen.add(key)
            except Exception as e:
                errors += 1
                logger.warning(f"[pixel-bridge] enqueue failed for {tenant_id}/{event_type}: {e}")

        summary = {
            "started_at": started.isoformat(),
            "scanned_events": len(events),
            "enqueued": enqueued,
            "skipped_dedup": skipped_dedup,
            "github_tasks": github_tasks,
            "patch_tasks": patch_tasks,
            "errors": errors,
        }
        PixelToOraBridge.last_run_at = started
        PixelToOraBridge.last_event_count = len(events)
        PixelToOraBridge.last_summary = summary
        logger.info(f"[pixel-bridge] cycle done: {summary}")
        return summary

    async def _scan_recent_events(self, db, minutes: int = SCAN_WINDOW_MIN) -> List[Dict[str, Any]]:
        """Return actionable events from the last `minutes` window."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        query: Dict[str, Any] = {
            "received_at": {"$gte": cutoff},
            "$or": [
                {"event": {"$in": list(TRIGGER_EVENTS)}},
                {"data.score": {"$lt": SCORE_THRESHOLD, "$ne": None}},
            ],
        }
        try:
            cursor = db.pixel_events.find(
                query,
                {
                    "_id": 0,
                    "tenant_id": 1,
                    "business_id": 1,
                    "event": 1,
                    "url": 1,
                    "session_id": 1,
                    "data": 1,
                    "received_at": 1,
                },
            ).sort("received_at", -1).limit(100)
            return [e async for e in cursor]
        except Exception as e:
            logger.warning(f"[pixel-bridge] scan failed: {e}")
            return []

    async def _is_duplicate(self, db, tenant_id: str, event_type: str) -> bool:
        """True if we already enqueued the same tenant+type in DEDUP_WINDOW_MIN."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_WINDOW_MIN)
        try:
            hit = await db.pixel_ora_tasks.find_one(
                {
                    "tenant_id": tenant_id,
                    "event_type": event_type,
                    "created_at": {"$gte": cutoff},
                },
                {"_id": 0, "task_id": 1},
            )
            return hit is not None
        except Exception as e:
            logger.debug(f"[pixel-bridge] dedup check failed: {e}")
            return False

    async def _route_event(self, db, event_doc: Dict[str, Any]) -> str:
        """Routes to github or pixel-patch path. Returns the kind str."""
        tenant_id = event_doc.get("tenant_id") or event_doc.get("business_id")
        github_conn = None
        try:
            github_conn = await db.github_connections.find_one(
                {"company_id": tenant_id},
                {"_id": 0, "repo": 1, "branch": 1},
            )
        except Exception as e:
            logger.debug(f"[pixel-bridge] github lookup failed: {e}")
            github_conn = None

        if github_conn:
            await self._create_github_task(db, tenant_id, event_doc)
            return "github"
        await self._create_pixel_patch_task(db, tenant_id, event_doc)
        return "patch"

    async def _create_pixel_patch_task(self, db, tenant_id: str, event_doc: Dict[str, Any]) -> str:
        """Insert a placeholder patch into pending_pixel_patches AND log the task."""
        now = datetime.now(timezone.utc)
        event_type = event_doc.get("event", "unknown")
        patch_id = str(uuid.uuid4())
        patch = {
            "id": patch_id,
            "tenant_id": tenant_id,
            "type": _infer_patch_type(event_type),
            "status": "queued",
            "source": "pixel_to_ora_bridge",
            "event_summary": {
                "event": event_type,
                "url": event_doc.get("url"),
                "data": event_doc.get("data"),
            },
            "created_at": now,
        }
        await db.pending_pixel_patches.insert_one(patch)
        await db.pixel_ora_tasks.insert_one({
            "task_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "kind": "patch",
            "patch_id": patch_id,
            "event_type": event_type,
            "url": event_doc.get("url"),
            "status": "queued",
            "created_at": now,
        })
        return patch_id

    async def _create_github_task(self, db, tenant_id: str, event_doc: Dict[str, Any]) -> str:
        """Enqueue a github-path ORA task. The cron does NOT call /push-fix
        directly — a separate ORA worker will pick this up and decide the fix."""
        now = datetime.now(timezone.utc)
        event_type = event_doc.get("event", "unknown")
        task_id = str(uuid.uuid4())
        await db.pixel_ora_tasks.insert_one({
            "task_id": task_id,
            "tenant_id": tenant_id,
            "kind": "github",
            "event_type": event_type,
            "url": event_doc.get("url"),
            "error": event_doc.get("data"),
            "status": "queued",
            "created_at": now,
        })
        return task_id


__all__ = ["PixelToOraBridge"]
