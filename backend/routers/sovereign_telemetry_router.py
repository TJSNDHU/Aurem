"""
AUREM Sovereign Telemetry router (iter 322m Day 5+)
====================================================
Single-pulse JSON for the Council Activity Feed and any external
monitoring dashboards. Aggregates state from all Sovereign Discipline
subsystems with a consistent shape:

  {
    "ts": "<ISO>",
    "memory_guard":     <stats>,
    "watchdog":         <status>,
    "latency_guardian": <status>,
    "council_rotation": <last_tick_summary>,
    "pillar_fulfiller": <last_tick_summary>,
    "council_sessions_24h": int,
    "boundary_lint": {"passed": bool, "checked_at": "<ISO>"},
  }

Admin-only. Cached for 10 seconds (TTL cache) to avoid stampede.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, HTTPException, Request


router = APIRouter(prefix="/api/sovereign", tags=["sovereign-telemetry"])

_db = None
_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
_CACHE_TTL_S = 10

# Path to the boundary lint script — run on every telemetry call so
# violations show up in the dashboard within 10s.
_LINT_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "lint_sovereign_boundary.py"


def set_db(database) -> None:
    global _db
    _db = database


def _require_admin(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(401, "Auth required")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT_SECRET not configured")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    if not (payload.get("is_admin") or payload.get("is_super_admin") or
            payload.get("role") in ("admin", "super_admin", "founder")):
        raise HTTPException(403, "Admin required")
    return payload


async def _last_doc(coll_name: str, query: Optional[Dict[str, Any]] = None,
                    sort_field: str = "ts") -> Optional[Dict[str, Any]]:
    if _db is None:
        return None
    try:
        return await _db[coll_name].find_one(
            query or {}, {"_id": 0}, sort=[(sort_field, -1)],
        )
    except Exception:
        return None


def _run_boundary_lint() -> Dict[str, Any]:
    """Run the boundary lint and return pass/fail snapshot."""
    if not _LINT_SCRIPT.exists():
        return {"passed": False, "reason": "lint_script_missing"}
    try:
        proc = subprocess.run(
            ["python3", str(_LINT_SCRIPT)],
            capture_output=True, text=True, timeout=10,
        )
        return {
            "passed": proc.returncode == 0,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "summary": proc.stdout.splitlines()[0] if proc.stdout else "",
        }
    except Exception as e:
        return {"passed": False, "reason": str(e)[:120]}


@router.get("/telemetry-status")
async def sovereign_health(request: Request) -> Dict[str, Any]:
    """Aggregated Sovereign telemetry. Cached 10s.

    Anyone with an admin token can poll this — perfect for the
    System Pulse Live dashboard's Council Activity Feed pill.
    """
    _require_admin(request)

    import time
    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL_S:
        return _cache["data"]

    # Run all reads concurrently for snappiness.
    async def _safe(coro, fallback):
        try:
            return await coro
        except Exception as e:
            return {**(fallback or {}), "error": str(e)[:120]}

    from services import (
        sovereign_memory as smg,
        sovereign_watchdog as sw,
        latency_guardian as lg,
    )

    memory_stats_t = _safe(
        smg.get_memory_guard_stats(_db),
        {"available": False},
    )
    watchdog_status_t = _safe(
        sw.get_watchdog_status(_db),
        {"state": "unknown"},
    )
    guardian_status_t = _safe(
        lg.get_guardian_status(_db),
        {"state": "unknown"},
    )

    last_rotation_t = _last_doc(
        "council_sessions",
        query={"agents_consulted": {"$ne": None}},
    )
    last_pillar_fulfill_t = _last_doc(
        "pillar_restart_requests",
        query={"fulfilled": True},
        sort_field="fulfilled_at",
    )

    # Council session count in last 24h
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    council_24h_t = _db.council_sessions.count_documents(
        {"ts": {"$gte": cutoff}},
    ) if _db is not None else None

    # Agent A2A self-heal stats — surfaced on the same single-pulse so
    # the dashboard can render "agents wedged · auto-healed · avg μs".
    from services.agent_wedge_detector import get_wedge_stats as _wedge_stats
    wedge_stats_t = _wedge_stats(_db, hours=24)

    (memory_stats, watchdog_status, guardian_status,
     last_rotation, last_pillar_fulfill, wedge_stats) = await asyncio.gather(
        memory_stats_t, watchdog_status_t, guardian_status_t,
        last_rotation_t, last_pillar_fulfill_t, wedge_stats_t,
    )
    council_24h = await council_24h_t if council_24h_t else 0

    boundary_lint = _run_boundary_lint()

    data = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "memory_guard": memory_stats,
        "watchdog": watchdog_status,
        "latency_guardian": guardian_status,
        "council_rotation": {
            "last_tick_at": last_rotation.get("ts") if last_rotation else None,
            "last_winner": last_rotation.get("winner") if last_rotation else None,
        },
        "pillar_fulfiller": {
            "last_fulfilled_at": (
                last_pillar_fulfill.get("fulfilled_at")
                if last_pillar_fulfill else None
            ),
            "last_pillar": (
                last_pillar_fulfill.get("pillar")
                if last_pillar_fulfill else None
            ),
            "last_attempt_ok": (
                bool(last_pillar_fulfill.get("attempt_result", {}).get("ok"))
                if last_pillar_fulfill else None
            ),
        },
        "agent_wedges": wedge_stats,
        "council_sessions_24h": council_24h,
        "boundary_lint": boundary_lint,
    }
    _cache.update({"data": data, "ts": now})
    return data
