"""
Pixel Event Batch Buffer — Iteration 205 (Safe-Mode DB Optimization)
=====================================================================
In-memory buffer that batches pixel events and flushes them to MongoDB
every 60 seconds (or when buffer reaches 100 events).

Safety:
  • If buffer/flush fails → caller can fall back to direct DB insert_one.
  • On shutdown / hot-reload → flush_all() is called to drain the buffer.
  • No data loss: failed flush returns events to the buffer for retry.

Metrics:
  buffered / flushed / flush_failures / direct_writes / bypass_count
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Configuration (overridable via env in future)
BATCH_SIZE_THRESHOLD = 100
FLUSH_INTERVAL_SEC = 60
MAX_BUFFER_SIZE = 1000          # hard cap — above this we force direct-write

_buffer: List[Dict[str, Any]] = []
_lock = asyncio.Lock()
_db = None
_metrics = {
    "buffered": 0,
    "flushed": 0,
    "flush_failures": 0,
    "direct_writes": 0,   # events that bypassed the buffer (fallback)
    "bypass_count": 0,    # count of bypass events due to cap/error
}


def set_db(db):
    global _db
    _db = db


async def enqueue_event(event: Dict[str, Any]) -> str:
    """
    Add an event to the in-memory buffer. If the buffer is full or DB is
    unavailable, falls back to direct DB write.

    Returns one of: 'buffered', 'direct', 'dropped'.
    'dropped' only happens if BOTH buffer AND direct-write fail — extremely rare.
    """
    if _db is None:
        # No DB yet — can't persist
        _metrics["bypass_count"] += 1
        return "dropped"

    try:
        async with _lock:
            if len(_buffer) >= MAX_BUFFER_SIZE:
                # Buffer overfull — bypass to direct write
                _metrics["bypass_count"] += 1
                raise RuntimeError("buffer_full")
            _buffer.append(event)
            _metrics["buffered"] += 1
            # Trigger flush if threshold reached (fire-and-forget)
            should_flush = len(_buffer) >= BATCH_SIZE_THRESHOLD
        if should_flush:
            asyncio.create_task(flush())
        return "buffered"
    except Exception:
        # Fallback: direct write
        try:
            await _db.pixel_events.insert_one(event)
            _metrics["direct_writes"] += 1
            return "direct"
        except Exception as e:
            logger.warning(f"[PixelBuffer] direct write failed: {e}")
            _metrics["bypass_count"] += 1
            return "dropped"


async def flush() -> Dict[str, Any]:
    """Flush all buffered events to MongoDB in one insert_many()."""
    if _db is None:
        return {"flushed": 0, "skipped": "no_db"}

    async with _lock:
        if not _buffer:
            return {"flushed": 0}
        batch = _buffer[:]
        _buffer.clear()

    try:
        if batch:
            await _db.pixel_events.insert_many(batch, ordered=False)
            _metrics["flushed"] += len(batch)
            return {"flushed": len(batch)}
        return {"flushed": 0}
    except Exception as e:
        logger.warning(f"[PixelBuffer] flush failed: {e} — returning {len(batch)} events to buffer")
        _metrics["flush_failures"] += 1
        # Return events to buffer for retry
        async with _lock:
            _buffer[:0] = batch
        return {"flushed": 0, "failed": len(batch), "error": str(e)[:200]}


async def periodic_flush() -> Dict[str, Any]:
    """Scheduler entrypoint — call every FLUSH_INTERVAL_SEC."""
    return await flush()


def get_stats() -> dict:
    return {**_metrics, "buffer_size": len(_buffer), "batch_size": BATCH_SIZE_THRESHOLD, "max_buffer": MAX_BUFFER_SIZE}


async def flush_all_on_shutdown() -> int:
    """Drain buffer on shutdown. Returns number of events flushed."""
    r = await flush()
    return r.get("flushed", 0)
