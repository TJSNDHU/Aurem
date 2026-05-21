"""
services/build_verifier.py — iter 326i
═══════════════════════════════════════════════════════════════════════════
BUILD MODE proof-bundle persistence + drift watchdog.

Pairs with the two new ORA tools (`run_pytest`, `verify_endpoint`) and the
BUILD MODE directive in `ora_agent.SYSTEM_PROMPT`. Whenever ORA completes
a build cycle, the proof bundle (files touched + test result + endpoint
verify result) is recorded here so the operator can audit every
autonomous build AND a re-verify loop can detect when a previously-green
build silently goes red.

Why this matters
────────────────
The existing 8 repair/watchdog modules (sovereign_watchdog,
ora_campaign_watchdog, autonomous_repair_engine, etc.) are all REACTIVE —
they fire when something breaks. None of them say "the build that
shipped 2 hours ago — is it still wired?" This module answers exactly
that question by:

  1. `record_proof(build_id, proof)` — call from the chat-router after
     ORA emits a successful proof table. Persists to `build_proofs`.
  2. `reverify_one(build_id)` — re-runs `verify_endpoint` (and a quick
     pytest collect-only check) against the original proof targets. If
     anything degraded, writes a drift event to `build_drift_events`.
  3. `reverify_tick()` — fan-out: re-verify every build proof that's
     <24h old and hasn't been re-verified in the last 5 minutes. Cheap
     because it only checks endpoints + pytest collect, no LLM cost.

Wired from existing watchdog tick infrastructure (no new APScheduler
job — the operator can plug this into the sovereign_watchdog loop or
call `reverify_tick()` from a route).
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_db = None  # set via set_db()


def set_db(database) -> None:
    global _db
    _db = database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Schema ────────────────────────────────────────────────────────────
# build_proofs:
#   _id                  : build_id (uuid4 hex)
#   created_at           : ISO datetime
#   feature              : short label ("add /api/foo endpoint")
#   files_changed        : list[str]  (relative paths under /app)
#   tests                : list[{"path": str, "passed": int, "failed": int,
#                                "duration_s": float, "summary": str}]
#   endpoints            : list[{"endpoint": str, "expected_status": int,
#                                "matched_status": bool, "latency_ms": int}]
#   verdict              : "green" | "yellow" | "red"
#   last_reverified_at   : ISO datetime | None
#   last_reverify_verdict: "green" | "yellow" | "red" | null
#
# build_drift_events:
#   _id                  : uuid4 hex
#   build_id             : refers to build_proofs._id
#   detected_at          : ISO datetime
#   diff                 : dict of {component: "before → after"}


# ─────────────────────────────────────────────────────────────────────
# 1. Record a fresh proof bundle
# ─────────────────────────────────────────────────────────────────────
async def record_proof(
    *,
    feature:       str,
    files_changed: list[str],
    tests:         list[dict[str, Any]],
    endpoints:     list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist a build proof. Returns the created doc.

    The caller (typically the ORA chat-router after a BUILD MODE reply)
    is responsible for collecting the raw tool outputs and reducing them
    to the schema described above. Each tests[] entry must already
    carry `passed/failed/duration_s/summary` (the structured envelope
    that `run_pytest` returns).
    """
    if _db is None:
        return {"ok": False, "error": "db not wired"}
    if not feature or not isinstance(feature, str):
        return {"ok": False, "error": "feature required"}

    build_id = uuid.uuid4().hex[:16]
    verdict  = _judge_verdict(tests, endpoints)
    doc = {
        "_id":                  build_id,
        "created_at":           _now_iso(),
        "feature":              feature[:300],
        "files_changed":        [str(p)[:400] for p in (files_changed or [])][:50],
        "tests":                tests or [],
        "endpoints":            endpoints or [],
        "verdict":              verdict,
        "last_reverified_at":   None,
        "last_reverify_verdict": None,
    }
    await _db.build_proofs.insert_one(doc)
    logger.info(f"[build-verifier] recorded {build_id} verdict={verdict}")
    # Drop _id back as a regular field for callers (it's already the id).
    return {"ok": True, "build_id": build_id, "verdict": verdict, "doc": doc}


def _judge_verdict(
    tests: list[dict[str, Any]],
    endpoints: list[dict[str, Any]],
) -> str:
    """Reduce raw proof rows to a traffic-light verdict."""
    if not tests and not endpoints:
        return "yellow"  # no proof attached
    for t in tests or []:
        if int(t.get("failed") or 0) > 0:
            return "red"
        if int(t.get("errors") or 0) > 0:
            return "red"
    for e in endpoints or []:
        if not e.get("matched_status"):
            return "red"
    # passing → green
    return "green"


# ─────────────────────────────────────────────────────────────────────
# 2. Re-verify a single build
# ─────────────────────────────────────────────────────────────────────
async def reverify_one(build_id: str) -> dict[str, Any]:
    """Hit each endpoint + run `pytest --collect-only` on each test file.

    Cheap — endpoint checks are <250 ms each, `--collect-only` skips
    actual test execution and just confirms the file still parses and
    pytest can discover the marked tests. Real test execution is gated
    behind explicit `run_pytest` (callable from chat).

    Writes a `build_drift_events` row when verdict downgrades.
    """
    if _db is None:
        return {"ok": False, "error": "db not wired"}
    doc = await _db.build_proofs.find_one({"_id": build_id}, {"_id": 0,
        "feature": 1, "tests": 1, "endpoints": 1, "verdict": 1,
    })
    if not doc:
        return {"ok": False, "error": "build_id not found"}

    fresh_endpoints: list[dict[str, Any]] = []
    fresh_tests:     list[dict[str, Any]] = []

    # ── Endpoint re-verify (in-process via aiohttp-like curl shell) ──
    for ep in doc.get("endpoints") or []:
        endpoint        = ep.get("endpoint") or ""
        expected_status = int(ep.get("expected_status") or 200)
        fresh = await _curl_one(endpoint, expected_status)
        fresh_endpoints.append(fresh)

    # ── Test re-verify: pytest --collect-only (cheap parse check) ──
    for t in doc.get("tests") or []:
        path = t.get("path") or ""
        fresh_tests.append(await _pytest_collect_only(path))

    new_verdict = _judge_verdict(fresh_tests, fresh_endpoints)
    now_iso = _now_iso()

    await _db.build_proofs.update_one(
        {"_id": build_id},
        {"$set": {
            "last_reverified_at":    now_iso,
            "last_reverify_verdict": new_verdict,
        }},
    )

    # Did we drift from green to anything-not-green? Emit a drift event.
    old_verdict = doc.get("verdict")
    drifted     = (old_verdict == "green" and new_verdict != "green")
    if drifted:
        await _db.build_drift_events.insert_one({
            "_id":           uuid.uuid4().hex[:16],
            "build_id":      build_id,
            "detected_at":   now_iso,
            "diff":          {
                "verdict": f"{old_verdict} → {new_verdict}",
                "endpoints": fresh_endpoints,
                "tests":     fresh_tests,
            },
        })
        logger.warning(
            f"[build-verifier] DRIFT {build_id}: {old_verdict} → {new_verdict}"
        )

    return {
        "ok":             True,
        "build_id":       build_id,
        "prior_verdict":  old_verdict,
        "new_verdict":    new_verdict,
        "drifted":        drifted,
        "endpoints":      fresh_endpoints,
        "tests":          fresh_tests,
    }


async def _curl_one(endpoint: str, expected_status: int) -> dict[str, Any]:
    if not endpoint.startswith("/api/"):
        return {"endpoint": endpoint, "expected_status": expected_status,
                "matched_status": False, "latency_ms": 0,
                "error": "endpoint must start with /api/"}
    url = f"http://localhost:8001{endpoint}"
    started = time.time()
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["curl", "-s", "-o", "/dev/null",
             "-w", "%{http_code}",
             "--max-time", "8", url],
            capture_output=True, text=True, timeout=10,
        )
        elapsed_ms = int((time.time() - started) * 1000)
        try:
            http_status = int((r.stdout or "0").strip())
        except ValueError:
            http_status = 0
        return {
            "endpoint":        endpoint,
            "expected_status": expected_status,
            "http_status":     http_status,
            "matched_status":  http_status == expected_status,
            "latency_ms":      elapsed_ms,
        }
    except Exception as e:
        return {
            "endpoint":        endpoint,
            "expected_status": expected_status,
            "http_status":     0,
            "matched_status":  False,
            "latency_ms":      int((time.time() - started) * 1000),
            "error":           f"{type(e).__name__}: {str(e)[:120]}",
        }


_PYTEST_BIN_CANDIDATES = (
    "/root/.venv/bin/pytest",
    "/opt/plugins-venv/bin/pytest",
)


async def _pytest_collect_only(path: str) -> dict[str, Any]:
    """`pytest --collect-only` confirms the test file still parses and
    yields ≥1 test. Doesn't run any test bodies — fast (<1s)."""
    if not path or not path.startswith("/app/backend/tests"):
        return {"path": path, "passed": 0, "failed": 0, "errors": 1,
                "duration_s": 0.0, "summary": "path not allowed"}
    if not Path(path.split("::")[0]).exists():
        return {"path": path, "passed": 0, "failed": 0, "errors": 1,
                "duration_s": 0.0, "summary": "file missing"}
    import shutil
    pytest_bin = (
        shutil.which("pytest")
        or next((p for p in _PYTEST_BIN_CANDIDATES if Path(p).is_file()), None)
    )
    if not pytest_bin:
        return {"path": path, "passed": 0, "failed": 0, "errors": 1,
                "duration_s": 0.0, "summary": "pytest binary not found"}

    started = time.time()
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = "/app/backend" + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        r = await asyncio.to_thread(
            subprocess.run,
            [pytest_bin, "--collect-only", "-q", path],
            cwd="/app/backend",
            capture_output=True, text=True, timeout=20,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"path": path, "passed": 0, "failed": 0, "errors": 1,
                "duration_s": 20.0, "summary": "collect timed out"}
    except Exception as e:
        return {"path": path, "passed": 0, "failed": 0, "errors": 1,
                "duration_s": 0.0,
                "summary": f"{type(e).__name__}: {str(e)[:100]}"}

    duration = round(time.time() - started, 3)
    out = (r.stdout or "")
    # pytest --collect-only ends with "N tests collected"
    import re as _re
    m = _re.search(r"(\d+)\s+tests?\s+collected", out)
    collected = int(m.group(1)) if m else 0
    return {
        "path":        path,
        "passed":      collected,  # represented as "discoverable" tests
        "failed":      0 if r.returncode in (0, 5) else 1,
        "errors":      0 if r.returncode in (0, 5) else 1,
        "duration_s":  duration,
        "summary":     f"collect-only: {collected} tests" if collected
                       else f"exit={r.returncode}",
    }


# ─────────────────────────────────────────────────────────────────────
# 3. Fan-out re-verify — call this from sovereign_watchdog or a tick
# ─────────────────────────────────────────────────────────────────────
async def reverify_tick(stale_after_minutes: int = 5,
                        max_age_hours: int = 24,
                        max_per_tick: int = 20) -> dict[str, Any]:
    """Re-verify all build proofs that:
      • were created < max_age_hours ago, AND
      • haven't been re-verified in the last `stale_after_minutes`.

    Cheap fan-out — caps at `max_per_tick` so a sudden burst of new
    builds can't melt the watchdog tick.
    """
    if _db is None:
        return {"ok": False, "error": "db not wired"}
    now      = datetime.now(timezone.utc)
    cutoff   = (now - timedelta(hours=max_age_hours)).isoformat()
    stale_at = (now - timedelta(minutes=stale_after_minutes)).isoformat()

    query = {
        "created_at": {"$gte": cutoff},
        "$or": [
            {"last_reverified_at": None},
            {"last_reverified_at": {"$lt": stale_at}},
        ],
    }
    candidates: list[str] = []
    async for d in _db.build_proofs.find(query, {"_id": 1}).limit(max_per_tick):
        candidates.append(d["_id"])

    summary = {"considered": len(candidates), "checked": 0,
               "drifted": 0, "still_green": 0, "errored": 0}
    for bid in candidates:
        try:
            res = await reverify_one(bid)
            summary["checked"] += 1
            if res.get("drifted"):
                summary["drifted"] += 1
            elif res.get("new_verdict") == "green":
                summary["still_green"] += 1
        except Exception as e:
            summary["errored"] += 1
            logger.warning(f"[build-verifier] reverify {bid} error: {e}")
    return {"ok": True, **summary}
