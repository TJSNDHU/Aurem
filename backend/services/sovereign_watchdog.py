"""
AUREM Sovereign Watchdog (iter 322j)
====================================
Continuously scans the live system (logs, supervisor status, scheduler
heartbeats, Redis health, MongoDB ping, router registrations) and
auto-heals anything that breaks — no human review, no manual ops.

Design
------
- Lightweight: one process-global async loop, sleeps `WATCHDOG_INTERVAL_S`
  (default 60s) between scans. Fires the Council only when a finding has
  no deterministic recipe.
- Pluggable: `_PATTERNS` is a list of (regex, recipe_name, severity).
  `_RECIPES` maps recipe names to async fix functions. Add new entries
  here as new failure modes are discovered.
- Idempotent: each finding is keyed by hash(pattern+source+lineno) so
  the same warning doesn't trigger a fix on every iteration.
- Self-learning: every finding+fix outcome is persisted to
  `sovereign_watchdog_log` so the dashboard can show what was healed and
  the Council has historical context for similar future anomalies.

Public API
----------
- `start_watchdog(db)`        — launch the background loop (called once)
- `scan_once(db)`             — run a single iteration (used by tests +
                                manual /api/qa/watchdog/run-now)
- `get_watchdog_status(db)`   — pill state for the dashboard
- `get_recent_findings(db, limit)` — timeline rows
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Tunables ────────────────────────────────────────────────────────────
WATCHDOG_INTERVAL_S = int(os.environ.get("WATCHDOG_INTERVAL_S", "60"))
LOG_TAIL_LINES = int(os.environ.get("WATCHDOG_LOG_TAIL", "300"))
MAX_FINDINGS_PER_SCAN = int(os.environ.get("WATCHDOG_MAX_PER_SCAN", "20"))
LOG_PATHS = [
    "/var/log/supervisor/backend.err.log",
    "/var/log/supervisor/backend.out.log",
]
DEDUP_WINDOW = timedelta(minutes=int(os.environ.get("WATCHDOG_DEDUP_MIN", "30")))


# ─── Recipe registry ─────────────────────────────────────────────────────
async def _recipe_redis_pool_kick(db, *_args, **_kwargs) -> Dict[str, Any]:
    """Force-recycle the shared Redis pool. Best-effort — uses the official
    `close_pools()` helper from utils.redis_pool which closes both the async
    pool and the sync ConnectionPool atomically."""
    info: Dict[str, Any] = {}
    try:
        from utils import redis_pool as rp
        try:
            await rp.close_pools()
            info["pools_closed"] = True
        except Exception as e:
            info["close_err"] = str(e)[:120]
        # Force a fresh sync client on next call
        try:
            sync = rp.get_sync_redis()
            if sync:
                sync.connection_pool.disconnect()
                info["sync_disconnected"] = True
        except Exception as e:
            info["sync_disconnect_err"] = str(e)[:120]
    except Exception as e:
        info["err"] = str(e)[:200]
    return info


async def _recipe_pillar_restart(db, match: re.Match, *_args) -> Dict[str, Any]:
    """A pillar's start_pillar*_worker raised. We can't restart it inline
    (it owns its own task group), but we can write a `pillar_restart_request`
    document that the next supervisor heartbeat will pick up."""
    pillar_no = "?"
    try:
        if match and match.groups():
            pillar_no = match.group(1)
    except Exception:
        pass
    if db is not None:
        try:
            await db.pillar_restart_requests.insert_one({
                "pillar": pillar_no,
                "ts": datetime.now(timezone.utc).isoformat(),
                "fulfilled": False,
                "source": "sovereign_watchdog",
            })
        except Exception as e:
            return {"err": str(e)[:200]}
    return {"pillar": pillar_no, "request_filed": True}


async def _recipe_db_ping(db, *_args) -> Dict[str, Any]:
    """A DB-related anomaly was seen — verify connectivity."""
    if db is None:
        return {"ping": False, "err": "db_unavailable"}
    try:
        await db.command("ping")
        return {"ping": True}
    except Exception as e:
        return {"ping": False, "err": str(e)[:200]}


async def _recipe_noop_log_only(db, *_args) -> Dict[str, Any]:
    """For boot-race artifacts (e.g. nginx 111 before port bind) we just
    record but take no action — they self-resolve once the port binds."""
    return {"action": "boot_artifact_noted"}


_RECIPES: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
    "redis_pool_kick":  _recipe_redis_pool_kick,
    "pillar_restart":   _recipe_pillar_restart,
    "db_ping":          _recipe_db_ping,
    "noop_log_only":    _recipe_noop_log_only,
}


# ─── Pattern catalog ─────────────────────────────────────────────────────
# Each tuple: (compiled_regex, recipe_name, severity, kind)
_PATTERNS: List[Tuple[re.Pattern, str, str, str]] = [
    (re.compile(r"max number of clients reached", re.I),
        "redis_pool_kick",   "warn",  "redis_exhausted"),
    (re.compile(r"Pillar\s+(\d+)\s+worker NOT started", re.I),
        "pillar_restart",    "high",  "pillar_failed"),
    (re.compile(r"\[STARTUP\]\s*✗\s*Pillar", re.I),
        "pillar_restart",    "high",  "pillar_failed"),
    (re.compile(r"connect\(\)\s+failed\s+\(111[^)]*\)\s+while connecting to upstream.*?/health", re.I | re.S),
        "noop_log_only",     "info",  "boot_race"),
    (re.compile(r"PymongoServerSelectionTimeout|ServerSelectionTimeoutError", re.I),
        "db_ping",           "high",  "mongo_timeout"),
    (re.compile(r"motor\..*ConnectionFailure|motor\..*OperationFailure", re.I),
        "db_ping",           "high",  "mongo_op_failure"),
]


# ─── Helpers ─────────────────────────────────────────────────────────────
def _tail_file(path: str, n: int) -> List[str]:
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return []
        with p.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = 4096
            data = b""
            while size > 0 and data.count(b"\n") <= n + 5:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
            return data.decode(errors="replace").splitlines()[-n:]
    except Exception as e:
        logger.debug(f"[watchdog] tail failed {path}: {e}")
        return []


def _finding_key(source: str, kind: str, line: str) -> str:
    h = hashlib.sha1(f"{source}|{kind}|{line[:200]}".encode("utf-8")).hexdigest()
    return h[:16]


# ─── Single scan iteration ──────────────────────────────────────────────
async def scan_once(db) -> Dict[str, Any]:
    """Run one full scan pass. Returns a summary dict."""
    findings: List[Dict[str, Any]] = []
    fixed: List[Dict[str, Any]] = []
    skipped_dup = 0
    council_consults = 0

    cutoff_iso = (datetime.now(timezone.utc) - DEDUP_WINDOW).isoformat()

    for src in LOG_PATHS:
        lines = _tail_file(src, LOG_TAIL_LINES)
        if not lines:
            continue
        for line in lines:
            if len(findings) >= MAX_FINDINGS_PER_SCAN:
                break
            for pat, recipe, severity, kind in _PATTERNS:
                m = pat.search(line)
                if not m:
                    continue
                key = _finding_key(src, kind, line)
                # Dedup by (key, ts >= cutoff)
                if db is not None:
                    try:
                        already = await db.sovereign_watchdog_log.find_one(
                            {"finding_key": key, "ts": {"$gte": cutoff_iso}},
                            {"_id": 0, "finding_key": 1},
                        )
                    except Exception:
                        already = None
                    if already:
                        skipped_dup += 1
                        break

                # Run the recipe
                try:
                    fn = _RECIPES.get(recipe)
                    out = await fn(db, m) if fn else {"err": "no_recipe"}
                    success = "err" not in out
                except Exception as e:
                    out = {"err": str(e)[:200]}
                    success = False

                # If recipe failed AND severity >= high, escalate to Council
                council_decision = None
                if not success and severity == "high":
                    council_decision = await _consult_council(
                        kind=kind, line=line[:400], recipe_attempted=recipe,
                        recipe_result=out, db=db,
                    )
                    council_consults += 1

                doc = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "finding_key": key,
                    "source": src,
                    "kind": kind,
                    "severity": severity,
                    "line_excerpt": line[:400],
                    "recipe": recipe,
                    "recipe_result": out,
                    "success": bool(success),
                    "council": council_decision,
                }
                findings.append(doc)
                if success:
                    fixed.append(doc)
                if db is not None:
                    try:
                        await db.sovereign_watchdog_log.insert_one(dict(doc))
                    except Exception as e:
                        logger.debug(f"[watchdog] log write failed: {e}")

                # Memory-Guard: every successful auto-fix is submitted as a
                # learning candidate (status pending) — a different Council
                # agent must approve it before it's promoted to canonical
                # `learnings`. Two stamps from distinct roles required.
                if success and severity in ("warn", "high"):
                    try:
                        from services import sovereign_memory as smg
                        await smg.submit_learning(
                            db,
                            agent_role="watchdog",
                            kind=f"watchdog_fix:{kind}",
                            payload={"recipe": recipe, "result": out},
                            evidence={
                                "source": src,
                                "line_excerpt": line[:400],
                                "finding_key": key,
                            },
                            confidence=0.6,
                        )
                    except Exception as e:
                        logger.debug(f"[watchdog] learning submit skipped: {e}")
                break  # one pattern per line is enough

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "findings": len(findings),
        "fixed": len(fixed),
        "skipped_duplicates": skipped_dup,
        "council_consults": council_consults,
        "interval_s": WATCHDOG_INTERVAL_S,
    }
    if db is not None:
        try:
            await db.sovereign_watchdog_log.insert_one({
                **summary,
                "kind": "scan_summary",
                "severity": "info",
                "success": True,
            })
        except Exception:
            pass
    return summary


async def _consult_council(
    *, kind: str, line: str, recipe_attempted: str,
    recipe_result: Dict[str, Any], db,
) -> Optional[Dict[str, Any]]:
    """Convene the ORA Council when a recipe fails. The Council's role is
    advisory only — it picks one of:
      a) RETRY — try the same recipe next iteration (no-op)
      b) ESCALATE — write a `sovereign_council_escalation` row that AUREM's
         on-call ORA agent picks up (no human page)
    The Council is NEVER allowed to ask a human."""
    decision = "retry"
    notes = ""
    winner = None
    score = 0
    try:
        from services.ora_council import convene_council
        prompt = (
            f"AUTONOMOUS WATCHDOG ESCALATION — kind={kind}. "
            f"Recipe `{recipe_attempted}` failed: {recipe_result}. "
            f"Log line: {line}. "
            f"As Council, vote RETRY (defer to next sweep) or ESCALATE "
            f"(write a sovereign_council_escalation row for the on-call "
            f"ORA agent). Reply ONE LINE: `<RETRY|ESCALATE> — <reason>`."
        )
        result = await convene_council(prompt, {
            "source": "sovereign_watchdog",
            "evidence": {
                "kind": kind,
                "recipe": recipe_attempted,
                "recipe_result": recipe_result,
                "line_excerpt": line[:300],
            },
        }, db)
        if result.get("ok"):
            text = (result.get("final_response") or "").strip()
            winner = result.get("winner")
            score = int(result.get("winner_score") or 0)
            if text.upper().startswith("ESCALATE"):
                decision = "escalate"
            notes = text[:240]
    except Exception as e:
        notes = f"council_unavailable: {str(e)[:80]} — defaulting to RETRY"

    if decision == "escalate" and db is not None:
        try:
            await db.sovereign_council_escalations.insert_one({
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": kind, "line": line[:400],
                "recipe": recipe_attempted, "recipe_result": recipe_result,
                "council_winner": winner, "council_score": score,
                "council_notes": notes,
                "ack_by_ora_agent": False,
            })
        except Exception as e:
            logger.debug(f"[watchdog] escalation write failed: {e}")

    return {
        "decision": decision, "notes": notes,
        "winner": winner, "score": score,
    }


# ─── Background loop ────────────────────────────────────────────────────
_started = False


async def _watchdog_loop(db) -> None:
    logger.info(
        f"[watchdog] sovereign loop online — interval={WATCHDOG_INTERVAL_S}s "
        f"patterns={len(_PATTERNS)}",
    )
    # Stagger first run 20s after boot so we don't trip on boot artifacts.
    await asyncio.sleep(20)
    while True:
        try:
            await scan_once(db)
        except Exception as e:
            logger.warning(f"[watchdog] scan iteration error: {e}")
        await asyncio.sleep(WATCHDOG_INTERVAL_S)


def start_watchdog(db) -> bool:
    """Launch the background loop (idempotent)."""
    global _started
    if _started:
        return False
    if os.environ.get("WATCHDOG_DISABLED", "").lower() in ("1", "true", "yes"):
        logger.info("[watchdog] disabled via WATCHDOG_DISABLED env")
        return False
    try:
        asyncio.create_task(_watchdog_loop(db))
        _started = True
        return True
    except RuntimeError:
        # No running loop (boot path); caller can call us again later
        return False


# ─── Read helpers ───────────────────────────────────────────────────────
async def get_watchdog_status(db) -> Dict[str, Any]:
    """Pill state:
      green  — no findings in last 30 min, OR all findings auto-fixed
      yellow — there are findings; some still pending fix or in retry
      red    — active sovereign_council_escalations row that hasn't been
               acked by an on-call ORA agent (ack_by_ora_agent=False)
    """
    if db is None:
        return {"state": "green", "reason": "db_unavailable"}
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    try:
        unacked = await db.sovereign_council_escalations.count_documents(
            {"ts": {"$gte": cutoff}, "ack_by_ora_agent": False},
        )
        if unacked:
            return {
                "state": "red", "reason": "council_escalation_pending",
                "unacked": unacked, "interval_s": WATCHDOG_INTERVAL_S,
            }
        unfixed = await db.sovereign_watchdog_log.count_documents({
            "ts": {"$gte": cutoff},
            "success": False,
            "kind": {"$ne": "scan_summary"},
        })
        if unfixed:
            return {
                "state": "yellow", "reason": "findings_pending",
                "unfixed": unfixed, "interval_s": WATCHDOG_INTERVAL_S,
            }
    except Exception as e:
        logger.warning(f"[watchdog] status read failed: {e}")
    return {
        "state": "green", "reason": "all_clear",
        "interval_s": WATCHDOG_INTERVAL_S,
    }


async def get_recent_findings(db, limit: int = 20) -> List[Dict[str, Any]]:
    if db is None:
        return []
    try:
        cursor = db.sovereign_watchdog_log.find(
            {"kind": {"$ne": "scan_summary"}},
            {"_id": 0},
        ).sort("ts", -1).limit(min(max(limit, 1), 100))
        return [a async for a in cursor]
    except Exception as e:
        logger.warning(f"[watchdog] recent findings read failed: {e}")
        return []
