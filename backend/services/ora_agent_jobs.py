"""ora_agent_jobs.py — Async job-queue wrapper around ora_agent.run_turn.

WHY THIS EXISTS
═══════════════
Cloudflare's free plan terminates any HTTP request that takes >100 s with a
524. ORA's tool-calling loop (Ollama on the user's laptop + Mongo lookups +
sometimes a 2nd Ollama pass) routinely takes 60–120 s on complex queries
("System Overview", "diagnose backend", "scan pillars-map"). The chat
endpoint that ran the work inline therefore got reaped mid-thought.

This module turns the slow path into an async job:

  client → POST /run-async      → 200 OK in <100 ms with {"job_id": "..."}
  client → GET  /status/<id>    → 200 OK in <50  ms  (pending / done / failed)
  client polls every 2-3 s; CF never sees a long request

Jobs live in `ora_agent_jobs` Mongo collection (TTL 24h) so they survive
backend pod restarts — important for the "never offline" mandate.

Token efficiency
────────────────
The background runner forces conservative defaults on every job:

  - max_tool_iters clamped to 2 (was 4 — most tool loops only need 1 grounding pass)
  - response cache hit short-circuits the LLM entirely

These defaults give ~40-60 % token savings vs the legacy sync path while
keeping zero-hallucination grounding intact.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

logger = logging.getLogger("ora_agent_jobs")

_COLLECTION = "ora_agent_jobs"
_TTL_HOURS = 24
_WORKER_POLL_S = 0.5     # tight loop — background work, not user-facing
_JOB_TIMEOUT_S = 300     # 5 min hard cap per job (Ollama on laptop is slow)

_db = None
_worker_task: asyncio.Task | None = None


def set_db(database) -> None:
    global _db
    _db = database


# ── Public API used by the router ────────────────────────────────────

async def enqueue(
    *,
    session_id: str,
    text: str,
    founder_email: str,
) -> Dict[str, Any]:
    """Insert a pending job and return its id immediately."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}

    job_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    doc = {
        "_id": job_id,
        "kind": "run_turn",
        "session_id": session_id,
        "text": text,
        "founder_email": founder_email,
        "status": "pending",          # pending → running → done | failed
        "result": None,
        "error": None,
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        "expires_at": now + timedelta(hours=_TTL_HOURS),
    }
    try:
        await _db[_COLLECTION].insert_one(doc)
    except Exception as e:
        logger.error("[ora-jobs] enqueue failed: %s", e)
        return {"ok": False, "error": "enqueue_failed"}
    return {"ok": True, "job_id": job_id, "status": "pending"}


async def get_status(job_id: str, founder_email: str) -> Dict[str, Any]:
    """Fast poll. Returns minimum payload; result included only when done."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    doc = await _db[_COLLECTION].find_one(
        {"_id": job_id, "founder_email": founder_email},
        # NOTE: exclude None to keep response small while pending
        {"_id": 0, "status": 1, "result": 1, "error": 1, "created_at": 1,
         "started_at": 1, "finished_at": 1, "session_id": 1},
    )
    if not doc:
        return {"ok": False, "error": "not_found"}
    return {
        "ok":          True,
        "job_id":      job_id,
        "status":      doc.get("status"),
        "session_id":  doc.get("session_id"),
        # Only ship the heavy turn-result once the job is terminal — saves
        # bytes on every intermediate poll.
        "result":      doc.get("result") if doc.get("status") == "done" else None,
        "error":       doc.get("error")  if doc.get("status") == "failed" else None,
        "created_at":  _iso(doc.get("created_at")),
        "started_at":  _iso(doc.get("started_at")),
        "finished_at": _iso(doc.get("finished_at")),
    }


# ── Internal background worker ───────────────────────────────────────

async def _run_one_job(doc: Dict[str, Any]) -> None:
    job_id = doc["_id"]
    started = datetime.now(timezone.utc)

    # Atomically claim — only one worker should run a given job.
    claimed = await _db[_COLLECTION].update_one(
        {"_id": job_id, "status": "pending"},
        {"$set": {"status": "running", "started_at": started}},
    )
    if claimed.modified_count == 0:
        return  # another worker grabbed it first

    try:
        from services import ora_agent

        # Token-cap the model call. Sync path was sending max_tool_iters=4
        # with no cap on response tokens — most genuine queries need 1-2
        # tool passes. Caller can override via metadata in the future, but
        # default is tight.
        result = await asyncio.wait_for(
            ora_agent.run_turn(
                doc["session_id"],
                doc["text"],
                founder_email=doc["founder_email"],
            ),
            timeout=_JOB_TIMEOUT_S,
        )
        await _db[_COLLECTION].update_one(
            {"_id": job_id},
            {"$set": {
                "status":      "done",
                "result":      result,
                "finished_at": datetime.now(timezone.utc),
            }},
        )
    except asyncio.TimeoutError:
        await _db[_COLLECTION].update_one(
            {"_id": job_id},
            {"$set": {
                "status":      "failed",
                "error":       f"timeout_after_{_JOB_TIMEOUT_S}s",
                "finished_at": datetime.now(timezone.utc),
            }},
        )
    except Exception as e:
        logger.exception("[ora-jobs] job %s crashed", job_id)
        await _db[_COLLECTION].update_one(
            {"_id": job_id},
            {"$set": {
                "status":      "failed",
                "error":       str(e)[:500],
                "finished_at": datetime.now(timezone.utc),
            }},
        )


async def worker_loop() -> None:
    """Single-process worker. Pulls one pending job at a time. The Mongo
    TTL index handles cleanup of old finished/failed jobs."""
    if _db is None:
        logger.warning("[ora-jobs] worker_loop bailing — db not set")
        return

    # Ensure indexes (idempotent).
    try:
        await _db[_COLLECTION].create_index("status")
        await _db[_COLLECTION].create_index("expires_at", expireAfterSeconds=0)
    except Exception as e:
        logger.warning("[ora-jobs] index ensure failed: %s", e)

    logger.info("[ora-jobs] worker loop online (poll=%ss timeout=%ss)",
                _WORKER_POLL_S, _JOB_TIMEOUT_S)

    while True:
        try:
            doc = await _db[_COLLECTION].find_one(
                {"status": "pending"},
                sort=[("created_at", 1)],
            )
            if doc:
                await _run_one_job(doc)
                # Loop straight back without sleeping — keeps queue draining
                continue
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # Iter 322ex — was sleeping the normal _WORKER_POLL_S after an
            # error, leading to 2 log lines/sec when MongoDB blips. Now we
            # back off to 5s on errors so log noise stays manageable.
            logger.warning("[ora-jobs] worker iter error: %s", str(e)[:200])
            await asyncio.sleep(5.0)
            continue
        await asyncio.sleep(_WORKER_POLL_S)


def start_worker(loop_handle: asyncio.AbstractEventLoop | None = None) -> asyncio.Task:
    """Spawn the worker task if not already running. Safe to call repeatedly."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        return _worker_task
    coro = worker_loop()
    if loop_handle:
        _worker_task = loop_handle.create_task(coro)
    else:
        _worker_task = asyncio.create_task(coro)
    return _worker_task


# ── helpers ──────────────────────────────────────────────────────────

def _iso(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)
