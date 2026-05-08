"""
Truth Ledger — AUREM's Honesty DNA (iter 283)
═══════════════════════════════════════════════════════════════════════

Zabaan ka pakka system. Append-only WORM (Write-Once-Read-Many) ledger
that records every agent's REAL performance — failures first, glitches,
hallucinations caught, insufficient recoveries, plus genuine successes.

Collection: `db.truth_logs`

Core contract:
  • Nothing is ever UPDATED or DELETED (after TTL).
  • Every entry carries evidence (raw payload, counts, error traces).
  • Severity is honest: if it's red, it's red.
  • Induction briefing is auto-generated from last 30 days so new agents
    start with hard-earned humility, not a sanitized brochure.

Event types (keep it tight — expand only when strictly needed):
  failure                — operation attempted and failed
  success                — operation completed AND verified
  glitch                 — unexpected state (timeout, race, partial data)
  self_correction        — agent caught its own mistake mid-flight
  hallucination_caught   — LLM output rejected by validator
  insufficient_recovery  — auto-heal ran but didn't actually heal
  persistent_red         — pillar stuck red beyond threshold
  manual_override        — human intervened over autonomous decision
  learning_no_signal     — learning cycle produced zero actionable insight
"""
from __future__ import annotations

import logging
import uuid
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COLLECTION = "truth_logs"
INDUCTION_WINDOW_DAYS = int(os.environ.get("TRUTH_LEDGER_INDUCTION_DAYS", "30"))
RETENTION_DAYS = int(os.environ.get("TRUTH_LEDGER_RETENTION_DAYS", "365"))

VALID_EVENT_TYPES = {
    "failure",
    "success",
    "glitch",
    "self_correction",
    "hallucination_caught",
    "insufficient_recovery",
    "persistent_red",
    "manual_override",
    "learning_no_signal",
}

VALID_SEVERITIES = {"info", "warn", "critical"}

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def record(
    actor: str,
    event_type: str,
    description: str,
    *,
    severity: str = "info",
    evidence: Optional[Dict[str, Any]] = None,
    outcome: Optional[str] = None,
) -> Dict[str, Any]:
    """Append an entry. NEVER updates existing; if validation fails, logs
    to stderr but does not raise — truth should never block real work."""
    if event_type not in VALID_EVENT_TYPES:
        logger.warning("[truth-ledger] unknown event_type=%s — stored as 'glitch'", event_type)
        event_type = "glitch"
    if severity not in VALID_SEVERITIES:
        severity = "info"
    doc = {
        "log_id": uuid.uuid4().hex[:14],
        "ts": _now(),
        "ts_iso": _now().isoformat(),
        "actor": actor or "unknown",
        "event_type": event_type,
        "severity": severity,
        "description": (description or "")[:1000],
        "evidence": evidence or {},
        "outcome": outcome,
        "immutable": True,
    }
    if _db is None:
        logger.debug("[truth-ledger] db unset — entry dropped (expected in unit tests): %s", doc["log_id"])
        return doc
    try:
        await _db[COLLECTION].insert_one(dict(doc))
    except Exception as e:
        logger.warning("[truth-ledger] persist failed: %s (entry=%s)", e, doc["log_id"])
    return doc


async def record_failure(actor: str, description: str, **kw) -> Dict[str, Any]:
    kw.setdefault("severity", "warn")
    return await record(actor, "failure", description, **kw)


async def record_success(actor: str, description: str, **kw) -> Dict[str, Any]:
    kw.setdefault("severity", "info")
    return await record(actor, "success", description, **kw)


async def record_insufficient_recovery(actor: str, description: str, **kw) -> Dict[str, Any]:
    kw.setdefault("severity", "critical")
    return await record(actor, "insufficient_recovery", description, **kw)


async def record_persistent_red(actor: str, description: str, **kw) -> Dict[str, Any]:
    kw.setdefault("severity", "critical")
    return await record(actor, "persistent_red", description, **kw)


async def record_hallucination(actor: str, description: str, **kw) -> Dict[str, Any]:
    kw.setdefault("severity", "warn")
    return await record(actor, "hallucination_caught", description, **kw)


# ── Readers ───────────────────────────────────────────────────────────

async def get_recent(
    limit: int = 50,
    severity: Optional[str] = None,
    actor: Optional[str] = None,
    event_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    limit = max(1, min(int(limit or 50), 500))
    query: Dict[str, Any] = {}
    if severity:
        query["severity"] = severity
    if actor:
        query["actor"] = actor
    if event_type:
        query["event_type"] = event_type
    docs = []
    try:
        async for d in _db[COLLECTION].find(
            query, {"_id": 0, "ts": 0, "immutable": 0}
        ).sort("ts_iso", -1).limit(limit):
            docs.append(d)
    except Exception as e:
        logger.debug("[truth-ledger] get_recent failed: %s", e)
    return docs


async def get_stats() -> Dict[str, Any]:
    if _db is None:
        return {"total": 0, "by_type": {}, "by_severity": {}, "by_actor": {}}
    cutoff = _now() - timedelta(days=INDUCTION_WINDOW_DAYS)
    total = 0
    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    by_actor: Dict[str, int] = {}
    try:
        async for doc in _db[COLLECTION].aggregate([
            {"$match": {"ts": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"t": "$event_type", "s": "$severity", "a": "$actor"},
                "n": {"$sum": 1},
            }},
        ]):
            n = doc["n"]
            total += n
            by_type[doc["_id"]["t"]] = by_type.get(doc["_id"]["t"], 0) + n
            by_severity[doc["_id"]["s"]] = by_severity.get(doc["_id"]["s"], 0) + n
            by_actor[doc["_id"]["a"]] = by_actor.get(doc["_id"]["a"], 0) + n
    except Exception:
        pass
    return {
        "window_days": INDUCTION_WINDOW_DAYS,
        "total": total,
        "by_type": by_type,
        "by_severity": by_severity,
        "by_actor": by_actor,
    }


async def get_induction_briefing() -> Dict[str, Any]:
    """
    Returned to every new agent on first init. Contains the last
    INDUCTION_WINDOW_DAYS of *failures, glitches, insufficient recoveries*
    — not a sanitized highlight reel. Teaches: "here's what went wrong,
    don't repeat it, and if you see it happening, flag it."
    """
    if _db is None:
        return {
            "preamble": PREAMBLE,
            "window_days": INDUCTION_WINDOW_DAYS,
            "failures": [],
            "glitches": [],
            "insufficient_recoveries": [],
            "persistent_reds": [],
            "stats": {"total": 0},
        }
    cutoff = _now() - timedelta(days=INDUCTION_WINDOW_DAYS)
    base = {"ts": {"$gte": cutoff}}
    failures = await _list(base | {"event_type": "failure"}, 20)
    glitches = await _list(base | {"event_type": "glitch"}, 20)
    insufficient = await _list(base | {"event_type": "insufficient_recovery"}, 20)
    persistent = await _list(base | {"event_type": "persistent_red"}, 20)
    halluc = await _list(base | {"event_type": "hallucination_caught"}, 20)
    stats = await get_stats()
    return {
        "preamble": PREAMBLE,
        "window_days": INDUCTION_WINDOW_DAYS,
        "failures": failures,
        "glitches": glitches,
        "insufficient_recoveries": insufficient,
        "persistent_reds": persistent,
        "hallucinations_caught": halluc,
        "stats": stats,
    }


async def _list(query: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    docs = []
    try:
        async for d in _db[COLLECTION].find(
            query, {"_id": 0, "ts": 0, "immutable": 0}
        ).sort("ts_iso", -1).limit(limit):
            docs.append(d)
    except Exception:
        pass
    return docs


# ── Health check (truthful) ───────────────────────────────────────────

async def current_truthful_health() -> Dict[str, Any]:
    """Used by ORA's Truth-Sync system prompt. Returns the REAL state,
    not a sanitized summary. If something is red, it says red.
    """
    payload: Dict[str, Any] = {
        "ts_iso": _now().isoformat(),
        "pillars_verdict": None,
        "sentinel": None,
        "autonomous_repair": None,
        "open_criticals_24h": 0,
        "recent_failures": [],
    }
    # Pull pillar overview cached snapshot (no DB round-trip)
    try:
        from routers.pillars_map_router import get_cached_snapshot, _fetch_sentinel_overlay
        snap = get_cached_snapshot() or {}
        payload["pillars_verdict"] = snap.get("overall_status")
        payload["sentinel"] = snap.get("sentinel_overlay") or await _fetch_sentinel_overlay()
    except Exception as e:
        payload["pillars_verdict_error"] = str(e)[:200]
    # Pull autonomous repair status
    try:
        from services.autonomous_repair_engine import status_snapshot
        payload["autonomous_repair"] = await status_snapshot()
    except Exception:
        pass
    # Pull open criticals from truth_logs (last 24h)
    if _db is not None:
        try:
            cutoff = _now() - timedelta(hours=24)
            payload["open_criticals_24h"] = await _db[COLLECTION].count_documents({
                "ts": {"$gte": cutoff},
                "severity": "critical",
            })
            payload["recent_failures"] = await _list(
                {"ts": {"$gte": cutoff},
                 "event_type": {"$in": ["failure", "insufficient_recovery", "persistent_red"]}},
                5,
            )
        except Exception:
            pass
    return payload


PREAMBLE = (
    "You are joining AUREM — a B2B AI automation platform that operates under "
    "a strict Truth-Sync mandate. The following ledger shows real failures, "
    "glitches and insufficient recoveries from the last 30 days.\n\n"
    "Operating principles you MUST respect:\n"
    "  1. Never sanitize state. If pillar is red, report it red.\n"
    "  2. Never hide partial data. If you couldn't verify something, say so.\n"
    "  3. Never pretend recovery succeeded if errors persist above warm threshold.\n"
    "  4. If you catch yourself about to hallucinate or fill a gap with guesswork, "
    "     STOP, return 'insufficient_signal', and call record_hallucination().\n"
    "  5. Read the failures below. Do not repeat them.\n"
    "  6. Every action taken must carry evidence — counts, IDs, timestamps. "
    "     Claims without evidence get rejected.\n\n"
    "Jhooth nahi chalega. Zabaan ka pakka.\n"
)
