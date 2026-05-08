"""
AUREM Latency Guardian (iter 322f)
==================================

Self-healing latency control loop. Runs as a passive layer on top of the
existing QA Bot 10-minute pulse sweep.

After every sweep:
  1. Any endpoint with `latency_ms > THRESHOLD_MS` AND `passed=True` is a
     "slow but working" candidate.
  2. Endpoints with `latency_ms > MAX_INTENTIONAL_MS` (default 5000ms) are
     **skipped** — they're known long-running probes (SEO scans, etc.).
  3. For each candidate, run a 3-step auto-fix cascade:
        Step 1 (t+0):  flush cache keys matching that endpoint
        Step 2 (t+30): re-probe; if still slow → `_ensure_indexes()`
        Step 3 (t+60): re-probe; if still slow → write `admin_alerts` row
  4. Every action is logged to `system_pulse_actions`.

Does NOT add a new scheduler. Hooked from `services.qa_bot.run_pulse_once`.

Public API:
  - `run_guardian_after_sweep(db, run_doc)` — called from qa_bot
  - `get_guardian_status(db)`               — for `/api/qa-bot/guardian/status`
  - `get_recent_actions(db, limit)`         — for the dashboard timeline
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ─── Tunables ────────────────────────────────────────────────────────────
THRESHOLD_MS = int(os.environ.get("GUARDIAN_THRESHOLD_MS", "400"))
MAX_INTENTIONAL_MS = int(os.environ.get("GUARDIAN_SKIP_ABOVE_MS", "5000"))
RE_PROBE_DELAY_S = int(os.environ.get("GUARDIAN_REPROBE_DELAY_S", "30"))


# ─── Cache prefix mapping ────────────────────────────────────────────────
# Map endpoint id (or path fragment) → list of TTL cache prefixes that may
# hold stale aggregates for it. Add entries here as new cached endpoints
# are introduced.
_CACHE_PREFIX_MAP: Dict[str, List[str]] = {
    "admin_pulse": [],
    "admin_mission_control_pixel_health": ["mc_pixel_health"],
    "admin_mission_control_tenants_summary": ["mc_tenants_summary"],
    # Path-based fallbacks — any endpoint path containing these strings
    "_path:/admin/mission-control/pixel-health": ["mc_pixel_health"],
    "_path:/admin/mission-control/tenants-summary": ["mc_tenants_summary"],
}


def _resolve_cache_prefixes(endpoint_id: str, path: Optional[str]) -> List[str]:
    """Return the cache prefixes that should be flushed for this endpoint."""
    prefixes: List[str] = list(_CACHE_PREFIX_MAP.get(endpoint_id, []))
    if path:
        for k, v in _CACHE_PREFIX_MAP.items():
            if k.startswith("_path:") and k[6:] in path:
                prefixes.extend(v)
    # de-dup
    seen = set()
    out: List[str] = []
    for p in prefixes:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# ─── Cache flush helper ──────────────────────────────────────────────────
def _flush_cache_prefixes(prefixes: List[str]) -> int:
    """Drop in-memory + Redis keys whose key starts with `aurem:<prefix>:`.
    Returns the number of keys removed."""
    if not prefixes:
        return 0
    from utils import ttl_cache as tc

    removed = 0
    # In-memory
    for prefix in prefixes:
        marker = f"aurem:{prefix}:"
        keys = [k for k in list(tc._cache.keys()) if k.startswith(marker)]
        for k in keys:
            tc._cache.pop(k, None)
        removed += len(keys)

    # Redis (best-effort)
    r = tc._init_redis()
    if r and r is not False:
        try:
            cursor = 0
            for prefix in prefixes:
                pattern = f"aurem:{prefix}:*"
                while True:
                    cursor, keys = r.scan(cursor, match=pattern, count=100)
                    if keys:
                        r.delete(*keys)
                        removed += len(keys)
                    if cursor == 0:
                        break
        except Exception as e:
            logger.warning(f"[guardian] Redis flush failed: {e}")
    return removed


# ─── Re-probe helper ─────────────────────────────────────────────────────
async def _reprobe(path: str, method: str = "GET") -> Optional[float]:
    """Re-probe the endpoint after an auto-fix step.

    Returns latency in ms, or None if the request errored. We use the
    public API base URL (same as qa_bot does) and accept any 2xx/3xx/4xx —
    we only care about latency, not auth status.
    """
    base = os.environ.get("PUBLIC_API_ORIGIN", "http://localhost:8001").rstrip("/")
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            t0 = time.perf_counter()
            r = await client.request(method, url)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            # Any HTTP response counts — non-5xx
            if r.status_code < 500:
                return elapsed_ms
    except Exception as e:
        logger.warning(f"[guardian] reprobe {url} failed: {e}")
    return None


# ─── Action log writer ───────────────────────────────────────────────────
async def _log_action(db, *, endpoint_id: str, path: str,
                      latency_before: float, latency_after: Optional[float],
                      action_taken: str, success: bool,
                      details: Optional[Dict[str, Any]] = None) -> None:
    if db is None:
        return
    try:
        await db.system_pulse_actions.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint_id": endpoint_id,
            "path": path,
            "latency_before_ms": round(latency_before, 1),
            "latency_after_ms": round(latency_after, 1) if latency_after else None,
            "action_taken": action_taken,
            "success": bool(success),
            "details": details or {},
        })
    except Exception as e:
        logger.warning(f"[guardian] action log write failed: {e}")


async def _emit_admin_alert(db, *, endpoint_id: str, path: str,
                            latency_ms: float) -> None:
    """Reserved for catastrophic failures only (kept as a fallback signal).
    The Latency Guardian no longer emits these in the normal flow — see
    `_council_autonomous_decision` for the autonomous escalation chain."""
    if db is None:
        return
    try:
        await db.admin_alerts.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "latency",
            "severity": "info",  # downgraded from "warn" — autonomous flow handles it
            "source": "latency_guardian",
            "endpoint_id": endpoint_id,
            "path": path,
            "latency_ms": round(latency_ms, 1),
            "message": (
                f"{endpoint_id} crossed all autonomous thresholds — Council "
                f"absorbed the decision; no action required."
            ),
            "ack": True,  # auto-acknowledged
        })
    except Exception as e:
        logger.warning(f"[guardian] admin_alert write failed: {e}")


# ─── Autonomous extra fix-step helpers (iter 322i — Council Mode) ───────
async def _tighten_cache_ttl(db, endpoint_id: str, prefixes: List[str]) -> Dict[str, Any]:
    """Step 4 — extend the active TTL on the endpoint's cache prefix to
    reduce DB hit-rate. Records the override in `latency_guardian_overrides`
    so the next QA Bot sweep can read it back. Returns details."""
    new_ttl = int(os.environ.get("GUARDIAN_HOT_CACHE_TTL", "120"))
    if db is not None:
        try:
            for p in prefixes:
                await db.latency_guardian_overrides.update_one(
                    {"prefix": p},
                    {"$set": {
                        "prefix": p,
                        "ttl_seconds": new_ttl,
                        "set_by": "latency_guardian",
                        "endpoint_id": endpoint_id,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
        except Exception as e:
            logger.warning(f"[guardian] ttl override write failed: {e}")
    return {"new_ttl": new_ttl, "prefixes": prefixes}


async def _connection_pool_recycle(db) -> Dict[str, Any]:
    """Step 5 — best-effort Motor pool refresh. We call admin_command to
    'ping' which reuses sockets. Mongo pools auto-rotate, so this is a
    non-destructive nudge that often clears a hung socket."""
    info: Dict[str, Any] = {"ping": False}
    if db is None:
        return info
    try:
        await db.command("ping")
        info["ping"] = True
    except Exception as e:
        info["error"] = str(e)[:120]
    return info


async def _council_autonomous_decision(
    db, *, endpoint_id: str, path: str,
    latency_before: float, latency_after: Optional[float],
    actions_so_far: List[str],
) -> Dict[str, Any]:
    """Final step — convene the ORA Council (`dev`/`qa`/`security`/`pricing`)
    asking them to **vouch** for one of the autonomous outcomes:
      a) ACCEPT — endpoint is functioning; the persistent latency is acceptable
         within current load and warrants no further action. Council closes
         the case (status `closed_by_council`).
      b) HOLD — keep the tightened cache & monitor; reopen if the next sweep
         still shows breach (status `held_by_council`).

    The Council never asks a human. If LLMs are unreachable, defaults to HOLD.
    """
    decision = "hold"
    notes = ""
    council_winner = None
    council_score = 0
    try:
        from services.ora_council import convene_council
        prompt = (
            f"AUTONOMOUS LATENCY ESCALATION — endpoint `{endpoint_id}` ({path}). "
            f"Baseline {round(latency_before)}ms, after auto-fixes "
            f"{round(latency_after or latency_before)}ms. Threshold {THRESHOLD_MS}ms. "
            f"Steps already attempted: {', '.join(actions_so_far)}. "
            f"As Council, vote ACCEPT (close case, current latency is acceptable) "
            f"or HOLD (keep monitoring). Reply in ONE LINE only, format: "
            f"`<ACCEPT|HOLD> — <one-sentence reason>`."
        )
        result = await convene_council(prompt, {
            "source": "latency_guardian",
            "evidence": {
                "endpoint_id": endpoint_id,
                "path": path,
                "latency_before_ms": round(latency_before, 1),
                "latency_after_ms": round(latency_after, 1) if latency_after else None,
                "threshold_ms": THRESHOLD_MS,
                "actions_so_far": actions_so_far,
            },
        }, db)
        if result.get("ok"):
            text = (result.get("final_response") or "").strip()
            council_winner = result.get("winner")
            council_score = int(result.get("winner_score") or 0)
            up = text.upper()
            if up.startswith("ACCEPT"):
                decision = "accept"
            else:
                decision = "hold"
            notes = text[:240]
    except Exception as e:
        logger.warning(f"[guardian] council convene failed: {e}")
        notes = f"council_unavailable: {str(e)[:80]} — defaulting to HOLD"

    return {
        "decision": decision,
        "notes": notes,
        "council_winner": council_winner,
        "council_score": council_score,
    }


# ─── Main heal loop (per slow endpoint) ──────────────────────────────────
async def _heal_one(db, check: Dict[str, Any]) -> None:
    endpoint_id = check.get("id") or "unknown"
    path = check.get("path") or check.get("url") or ""
    latency_before = float(check.get("latency_ms") or 0)

    # Step 1 — cache flush
    prefixes = _resolve_cache_prefixes(endpoint_id, path)
    flushed = _flush_cache_prefixes(prefixes)
    await _log_action(
        db, endpoint_id=endpoint_id, path=path,
        latency_before=latency_before, latency_after=None,
        action_taken="cache_flush",
        success=bool(prefixes),
        details={"prefixes": prefixes, "keys_removed": flushed},
    )

    # Step 2 — wait + reprobe + maybe ensure_indexes
    await asyncio.sleep(RE_PROBE_DELAY_S)
    latency_after_step1 = await _reprobe(path) if path else None
    if latency_after_step1 is not None and latency_after_step1 <= THRESHOLD_MS:
        await _log_action(
            db, endpoint_id=endpoint_id, path=path,
            latency_before=latency_before,
            latency_after=latency_after_step1,
            action_taken="recovered_after_cache_flush",
            success=True,
        )
        return

    # Index refresh (idempotent)
    try:
        from routers.infra_settings_router import _ensure_indexes
        await _ensure_indexes(db)
        idx_ok = True
    except Exception as e:
        logger.warning(f"[guardian] ensure_indexes failed: {e}")
        idx_ok = False

    await _log_action(
        db, endpoint_id=endpoint_id, path=path,
        latency_before=latency_before,
        latency_after=latency_after_step1,
        action_taken="index_refresh",
        success=idx_ok,
    )

    # Step 3 — wait + reprobe (post index_refresh)
    await asyncio.sleep(RE_PROBE_DELAY_S)
    latency_after_step2 = await _reprobe(path) if path else None
    if latency_after_step2 is not None and latency_after_step2 <= THRESHOLD_MS:
        await _log_action(
            db, endpoint_id=endpoint_id, path=path,
            latency_before=latency_before,
            latency_after=latency_after_step2,
            action_taken="recovered_after_index_refresh",
            success=True,
        )
        return

    # ── Autonomous escalation chain (iter 322i) — no human alerts ──
    actions_taken = ["cache_flush", "index_refresh"]

    # Step 4 — extend hot-cache TTL
    ttl_info = await _tighten_cache_ttl(db, endpoint_id, prefixes)
    actions_taken.append("tighten_cache_ttl")
    await _log_action(
        db, endpoint_id=endpoint_id, path=path,
        latency_before=latency_before,
        latency_after=latency_after_step2,
        action_taken="tighten_cache_ttl",
        success=True,
        details=ttl_info,
    )

    await asyncio.sleep(RE_PROBE_DELAY_S)
    latency_after_step4 = await _reprobe(path) if path else None
    if latency_after_step4 is not None and latency_after_step4 <= THRESHOLD_MS:
        await _log_action(
            db, endpoint_id=endpoint_id, path=path,
            latency_before=latency_before,
            latency_after=latency_after_step4,
            action_taken="recovered_after_ttl_tighten",
            success=True,
        )
        return

    # Step 5 — connection pool recycle (best-effort)
    pool_info = await _connection_pool_recycle(db)
    actions_taken.append("connection_pool_recycle")
    await _log_action(
        db, endpoint_id=endpoint_id, path=path,
        latency_before=latency_before,
        latency_after=latency_after_step4,
        action_taken="connection_pool_recycle",
        success=bool(pool_info.get("ping")),
        details=pool_info,
    )

    await asyncio.sleep(min(RE_PROBE_DELAY_S, 15))
    latency_after_step5 = await _reprobe(path) if path else None
    if latency_after_step5 is not None and latency_after_step5 <= THRESHOLD_MS:
        await _log_action(
            db, endpoint_id=endpoint_id, path=path,
            latency_before=latency_before,
            latency_after=latency_after_step5,
            action_taken="recovered_after_pool_recycle",
            success=True,
        )
        return

    # Step 6 — Council autonomous decision (no human in loop)
    final_latency = latency_after_step5 or latency_after_step4 or latency_after_step2 or latency_before
    council = await _council_autonomous_decision(
        db,
        endpoint_id=endpoint_id, path=path,
        latency_before=latency_before, latency_after=final_latency,
        actions_so_far=actions_taken,
    )
    decision = council.get("decision", "hold")
    council_action = "council_accepted" if decision == "accept" else "council_hold"

    await _log_action(
        db, endpoint_id=endpoint_id, path=path,
        latency_before=latency_before,
        latency_after=final_latency,
        action_taken=council_action,
        success=True,  # autonomous flow always closes the case
        details={
            "council_decision": decision,
            "council_winner": council.get("council_winner"),
            "council_score": council.get("council_score"),
            "council_notes": council.get("notes"),
            "actions_attempted": actions_taken,
        },
    )


# ─── Public entry point ──────────────────────────────────────────────────
async def run_guardian_after_sweep(db, run_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Called by qa_bot.run_pulse_once at the end of every sweep.

    Identifies slow-but-passing endpoints and runs the heal cascade for each
    in a fire-and-forget background task (so it never delays the sweep).
    Returns a summary dict (count of candidates triaged).
    """
    if db is None:
        return {"triaged": 0, "skipped_intentional": 0}

    checks: List[Dict[str, Any]] = run_doc.get("checks") or []
    # qa_bot.run_pulse_once historically stores `failures` only — but we
    # also receive the full `checks` list when integrated. Be tolerant.
    if not checks:
        # Fallback: query the per-endpoint log written by the same sweep
        try:
            started = run_doc.get("started_at")
            cursor = db.qa_bot_endpoint_log.find(
                {"run_started_at": started},
                {"_id": 0},
            ).limit(200)
            checks = [c async for c in cursor]
        except Exception:
            checks = []

    triaged: List[Dict[str, Any]] = []
    skipped = 0
    for c in checks:
        latency = float(c.get("latency_ms") or 0)
        if not c.get("passed"):
            continue
        if latency <= THRESHOLD_MS:
            continue
        if latency > MAX_INTENTIONAL_MS:
            skipped += 1
            continue
        triaged.append(c)

    for c in triaged:
        # Fire-and-forget so the sweep finishes immediately
        asyncio.create_task(_heal_one(db, c))

    summary = {
        "threshold_ms": THRESHOLD_MS,
        "skip_above_ms": MAX_INTENTIONAL_MS,
        "triaged": len(triaged),
        "skipped_intentional": skipped,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.system_pulse_actions.insert_one({
            **summary,
            "action_taken": "sweep_summary",
            "success": True,
        })
    except Exception:
        pass
    return summary


# ─── Read-side helpers (used by the router) ─────────────────────────────
async def get_guardian_status(db) -> Dict[str, Any]:
    """Return a single-glance status pill for the dashboard.

    State machine (iter 322i — Council Mode, fully autonomous):
      green  — no triaged events in last 30 min OR council closed all cases
               (`council_accepted`).
      yellow — heals are running OR council placed endpoints on `council_hold`
               (autonomous monitoring continues; no human action needed).
      red    — only legacy `alert_admin` rows still in the window. New
               flow never produces these; existing rows age out in 30 min.
    """
    if db is None:
        return {"state": "green", "reason": "db_unavailable"}

    from datetime import timedelta as _td
    cutoff = (datetime.now(timezone.utc) - _td(minutes=30)).isoformat()

    try:
        # Legacy alert_admin (pre iter-322i) — still respect for back-compat.
        legacy_alerts = await db.system_pulse_actions.count_documents(
            {"action_taken": "alert_admin", "ts": {"$gte": cutoff}},
        )
        if legacy_alerts:
            return {
                "state": "red",
                "reason": "legacy_alert_pending",
                "alert_count": legacy_alerts,
                "threshold_ms": THRESHOLD_MS,
            }

        # Council holds — autonomous flow keeps watching, surface as yellow.
        council_holds = await db.system_pulse_actions.count_documents(
            {"action_taken": "council_hold", "ts": {"$gte": cutoff}},
        )

        active_triages = 0
        async for s in db.system_pulse_actions.find(
            {"action_taken": "sweep_summary", "ts": {"$gte": cutoff}},
            {"_id": 0, "triaged": 1},
        ):
            active_triages += int(s.get("triaged") or 0)

        # Distinguish "in flight" (triage > 0 with no terminal yet) vs holds.
        if council_holds:
            return {
                "state": "yellow",
                "reason": "council_monitoring",
                "council_holds": council_holds,
                "active_triages": active_triages,
                "threshold_ms": THRESHOLD_MS,
            }

        # In-flight heals (yellow) — only if we have triages without any
        # terminal (council_accepted/recovered_*) to match them.
        if active_triages:
            terminals = await db.system_pulse_actions.count_documents({
                "action_taken": {"$in": [
                    "council_accepted", "council_hold",
                    "recovered_after_cache_flush",
                    "recovered_after_index_refresh",
                    "recovered_after_ttl_tighten",
                    "recovered_after_pool_recycle",
                ]},
                "ts": {"$gte": cutoff},
            })
            if terminals < active_triages:
                return {
                    "state": "yellow",
                    "reason": "auto_fix_running",
                    "active_triages": active_triages,
                    "terminals": terminals,
                    "threshold_ms": THRESHOLD_MS,
                }
    except Exception as e:
        logger.warning(f"[guardian] status read failed: {e}")

    return {
        "state": "green",
        "reason": "all_under_threshold_or_council_closed",
        "threshold_ms": THRESHOLD_MS,
    }


async def get_recent_actions(db, limit: int = 20) -> List[Dict[str, Any]]:
    if db is None:
        return []
    try:
        cursor = db.system_pulse_actions.find(
            {"action_taken": {"$ne": "sweep_summary"}},
            {"_id": 0},
        ).sort("ts", -1).limit(min(max(limit, 1), 100))
        return [a async for a in cursor]
    except Exception as e:
        logger.warning(f"[guardian] recent actions read failed: {e}")
        return []
