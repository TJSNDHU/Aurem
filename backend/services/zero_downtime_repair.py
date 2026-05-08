"""
Zero-Downtime Self-Repair (iter 303)
====================================
Wraps every repair execution with:

  1. Health gate     — wait if blast/autopilot mid-cycle (max 60s)
  2. State snapshot  — dump scheduler/queue state to Redis
  3. Sandboxed apply — run repair fn as a shielded async task so a
                       crash inside the fix CANNOT kill the main loop
  4. Status doc      — exposed at /api/admin/repair/status for UI banner
  5. State restore   — replay snapshot after repair (best-effort)

Design notes
------------
- Single-process FastAPI cannot truly "blue-green" containers. K8s does
  that via rolling deploys. What we CAN do in-process: isolate the
  repair so the main event loop keeps serving HTTP, and persist state
  in Redis so any forced restart restores the queue.
- A real out-of-process watchdog is provided via supervisord
  (see /etc/supervisor/conf.d/watchdog.conf). This module covers the
  in-process side.

Public API
----------
  await acquire_repair_lock(reason: str) -> bool
  await release_repair_lock()
  await health_gate(max_wait_s: int = 60) -> dict
  await pre_repair_snapshot(db) -> dict
  await post_repair_restore(db) -> dict
  await run_with_zdr(coro_fn, *, label: str, db) -> dict
  await repair_status() -> dict
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

REDIS_KEY_LOCK = "aurem:repair:lock"
REDIS_KEY_STATUS = "aurem:repair:status"
REDIS_KEY_SNAPSHOT = "aurem:repair:snapshot"
LOCK_TTL_S = 600
SNAPSHOT_TTL_S = 3600


# ─── redis client shim ──────────────────────────────────────────────────────
_redis = None


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis as _r
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis = _r.Redis.from_url(url, decode_responses=True,
                                   socket_timeout=2, socket_connect_timeout=2)
        # ping
        _redis.ping()
    except Exception as e:
        logger.warning(f"[zdr] redis unavailable, falling back to in-mem: {e}")
        _redis = _MemRedis()
    return _redis


class _MemRedis:
    """Tiny fallback when Redis isn't reachable. Single-process only."""
    def __init__(self):
        self._d: Dict[str, str] = {}

    def get(self, k):
        return self._d.get(k)

    def set(self, k, v, ex=None, nx=False):
        if nx and k in self._d:
            return False
        self._d[k] = v
        return True

    def delete(self, k):
        self._d.pop(k, None)
        return 1

    def ping(self):
        return True


# ─── lock ───────────────────────────────────────────────────────────────────
async def acquire_repair_lock(reason: str = "manual",
                              actor: str = "system") -> bool:
    r = _get_redis()
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps({"reason": reason, "actor": actor, "ts": now})
    ok = r.set(REDIS_KEY_LOCK, payload, ex=LOCK_TTL_S, nx=True)
    return bool(ok)


async def release_repair_lock() -> None:
    r = _get_redis()
    r.delete(REDIS_KEY_LOCK)


def _set_status(stage: str, **fields):
    r = _get_redis()
    doc = {"stage": stage, "ts": datetime.now(timezone.utc).isoformat(), **fields}
    r.set(REDIS_KEY_STATUS, json.dumps(doc), ex=900)


async def repair_status() -> Dict[str, Any]:
    r = _get_redis()
    raw = r.get(REDIS_KEY_STATUS)
    lock = r.get(REDIS_KEY_LOCK)
    return {
        "in_progress": bool(lock),
        "lock": json.loads(lock) if lock else None,
        "status": json.loads(raw) if raw else {"stage": "idle"},
        "system_online": True,
    }


# ─── health gate ────────────────────────────────────────────────────────────
async def _is_blast_active(db) -> bool:
    """True if auto_blast or autopilot is mid-cycle (within 30s)."""
    try:
        ab = await db.auto_blast_config.find_one(
            {"tenant_id": "global"}, {"_id": 0, "last_run_at": 1}
        ) or {}
        last = ab.get("last_run_at")
        if last:
            from datetime import timedelta
            t = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - t).total_seconds() < 30:
                return True
    except Exception:
        pass
    try:
        ap = await db.platform_config.find_one(
            {"config_key": "master_autopilot"}, {"_id": 0}
        ) or {}
        last_runs = ap.get("last_runs") or []
        if last_runs and last_runs[0].get("started_at") and not last_runs[0].get("finished_at"):
            return True
    except Exception:
        pass
    return False


async def health_gate(db, max_wait_s: int = 60) -> Dict[str, Any]:
    """Wait for in-flight blasts to finish; force-proceed after max_wait."""
    waited = 0
    while waited < max_wait_s:
        if not await _is_blast_active(db):
            return {"ok": True, "waited_s": waited}
        await asyncio.sleep(2)
        waited += 2
    return {"ok": False, "waited_s": waited, "forced": True}


# ─── snapshot / restore ─────────────────────────────────────────────────────
async def pre_repair_snapshot(db) -> Dict[str, Any]:
    """Dump scheduler-critical state to Redis so a forced restart restores it."""
    snap: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        snap["awb_autopilot_state"] = await db.awb_autopilot_state.find_one(
            {"_id": "singleton"}, {"_id": 0}
        ) or {}
    except Exception as e:
        snap["awb_autopilot_state_err"] = str(e)[:120]
    try:
        snap["master_autopilot"] = await db.platform_config.find_one(
            {"config_key": "master_autopilot"}, {"_id": 0}
        ) or {}
    except Exception as e:
        snap["master_autopilot_err"] = str(e)[:120]
    try:
        snap["auto_blast_config"] = await db.auto_blast_config.find_one(
            {"tenant_id": "global"}, {"_id": 0}
        ) or {}
    except Exception as e:
        snap["auto_blast_config_err"] = str(e)[:120]

    r = _get_redis()
    r.set(REDIS_KEY_SNAPSHOT, json.dumps(snap, default=str), ex=SNAPSHOT_TTL_S)
    return snap


async def post_repair_restore(db) -> Dict[str, Any]:
    """If schedulers came back disabled after a restart, re-arm from snapshot."""
    r = _get_redis()
    raw = r.get(REDIS_KEY_SNAPSHOT)
    if not raw:
        return {"ok": False, "reason": "no_snapshot"}
    snap = json.loads(raw)
    restored: Dict[str, Any] = {}
    # AWB autopilot
    try:
        prev = snap.get("awb_autopilot_state") or {}
        if prev.get("enabled"):
            cur = await db.awb_autopilot_state.find_one(
                {"_id": "singleton"}, {"_id": 0, "enabled": 1}
            ) or {}
            if not cur.get("enabled"):
                await db.awb_autopilot_state.update_one(
                    {"_id": "singleton"},
                    {"$set": {"enabled": True,
                              "restored_at": datetime.now(timezone.utc).isoformat(),
                              "restored_by": "zdr_post_repair"}},
                    upsert=True,
                )
                restored["awb_autopilot"] = "re-enabled"
    except Exception as e:
        restored["awb_autopilot_err"] = str(e)[:200]
    # Auto-blast
    try:
        prev = snap.get("auto_blast_config") or {}
        if prev.get("enabled"):
            cur = await db.auto_blast_config.find_one(
                {"tenant_id": "global"}, {"_id": 0, "enabled": 1}
            ) or {}
            if not cur.get("enabled"):
                await db.auto_blast_config.update_one(
                    {"tenant_id": "global"},
                    {"$set": {"enabled": True,
                              "restored_at": datetime.now(timezone.utc).isoformat(),
                              "restored_by": "zdr_post_repair"}},
                    upsert=True,
                )
                restored["auto_blast"] = "re-enabled"
    except Exception as e:
        restored["auto_blast_err"] = str(e)[:200]
    return {"ok": True, "restored": restored, "snapshot_ts": snap.get("ts")}


# ─── sandboxed apply ────────────────────────────────────────────────────────
async def run_with_zdr(coro_fn: Callable[[], Awaitable[Any]], *,
                       label: str, db,
                       max_wait_s: int = 60,
                       timeout_s: int = 120) -> Dict[str, Any]:
    """Wrap any repair coroutine with the full ZDR safety pipeline."""
    started = time.monotonic()
    if not await acquire_repair_lock(reason=label):
        return {"ok": False, "reason": "another_repair_in_progress",
                "status": await repair_status()}

    try:
        _set_status("health_gate", label=label)
        gate = await health_gate(db, max_wait_s=max_wait_s)

        _set_status("snapshot", label=label, gate=gate)
        snap = await pre_repair_snapshot(db)

        _set_status("applying", label=label, gate=gate, snapshot_ts=snap.get("ts"))

        # Shielded apply — exception inside coro_fn cannot tear down caller.
        result: Dict[str, Any] = {"ok": False}
        try:
            result = await asyncio.wait_for(
                asyncio.shield(coro_fn()),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            result = {"ok": False, "reason": f"timeout_{timeout_s}s"}
        except Exception as e:
            logger.exception(f"[zdr] repair '{label}' raised")
            result = {"ok": False, "reason": f"exception: {type(e).__name__}: {str(e)[:200]}"}

        _set_status("restoring", label=label, repair_result=result)
        restore = await post_repair_restore(db)

        elapsed = round(time.monotonic() - started, 2)
        _set_status("done", label=label, elapsed_s=elapsed,
                    repair_result=result, restore=restore)
        try:
            await db.repair_runs.insert_one({
                "label": label,
                "started_at": datetime.fromtimestamp(time.time() - elapsed, tz=timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "elapsed_s": elapsed,
                "gate": gate,
                "result": result,
                "restore": restore,
            })
        except Exception:
            pass
        return {
            "ok": bool(result.get("ok")),
            "label": label,
            "elapsed_s": elapsed,
            "gate": gate,
            "result": result,
            "restore": restore,
        }
    finally:
        await release_repair_lock()
