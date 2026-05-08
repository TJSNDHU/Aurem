"""
ORA Permanent Learning Brain — Phase 3
=======================================
3-Tier Memory:
  Tier 1 — Ephemeral (`ora_brain_thoughts`)        — every observed event
  Tier 2 — Pending  (`learnings_pending_review`)   — Council-gated candidates
  Tier 3 — Permanent (`ora_knowledge`)             — promoted, queryable

5 Learning Feeds (subscribed to A2A bus):
  1. CODE_FIX_APPLIED   → kind=code_fix
  2. COUNCIL_REJECTED   → kind=council_pattern
  3. WEDGE_HEALED       → kind=wedge_recipe
  4. HOT_REPLY          → kind=hot_signal
  5. DEPLOY_DETECTED    → kind=deploy_event

Nightly Learning Digest @ 03:00 UTC — summarises:
  - new pending count, new promoted count
  - top 5 patterns by times_seen
  - rejection rate

Weekly Self-Assessment @ Sunday 04:00 UTC — writes to `ora_self_assessments`:
  - active agents, silent agents, pause count
  - top failures, top wins
  - current confidence (avg of ora_knowledge.confidence)

Public query API:
  - `query_knowledge(db, *, kind=None, pattern=None, min_confidence=0.5, limit=20)`
  - `top_patterns(db, *, kind=None, limit=10)`
  - `summarize_period(db, *, hours=24)`
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


KNOWLEDGE = "ora_knowledge"
PENDING = "learnings_pending_review"
LIVE = "learnings"
DIGEST = "ora_learning_digests"
ASSESS = "ora_self_assessments"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return _now().isoformat()


# ─── Public query API ─────────────────────────────────────────────────

async def query_knowledge(
    db,
    *,
    kind: Optional[str] = None,
    pattern: Optional[str] = None,
    min_confidence: float = 0.5,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Tier-3 query. Returns active patterns ordered by (times_seen DESC, confidence DESC)."""
    if db is None:
        return []
    q: Dict[str, Any] = {
        "active": True,
        "confidence": {"$gte": float(min_confidence)},
    }
    if kind:
        q["kind"] = kind
    if pattern:
        q["pattern"] = {"$regex": pattern, "$options": "i"}
    cursor = (
        db[KNOWLEDGE]
        .find(q, {"_id": 0})
        .sort([("times_seen", -1), ("confidence", -1)])
        .limit(min(max(limit, 1), 200))
    )
    return [d async for d in cursor]


async def top_patterns(
    db, *, kind: Optional[str] = None, limit: int = 10,
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"active": True}
    if kind:
        q["kind"] = kind
    cursor = db[KNOWLEDGE].find(
        q, {"_id": 0, "pattern": 1, "kind": 1, "times_seen": 1, "confidence": 1},
    ).sort("times_seen", -1).limit(min(max(limit, 1), 100))
    return [d async for d in cursor]


async def summarize_period(db, *, hours: int = 24) -> Dict[str, Any]:
    """Snapshot of learning activity over the last N hours."""
    if db is None:
        return {"available": False}
    cutoff = (_now() - timedelta(hours=hours)).isoformat()
    new_pending, new_promoted, new_rejected, total_knowledge = await asyncio.gather(
        db[PENDING].count_documents({"submitted_at": {"$gte": cutoff}}),
        db[PENDING].count_documents({"status": "promoted", "promoted_at": {"$gte": cutoff}}),
        db[PENDING].count_documents({"status": "rejected", "rejected_at": {"$gte": cutoff}}),
        db[KNOWLEDGE].count_documents({"active": True}),
    )
    return {
        "available": True,
        "window_hours": hours,
        "new_pending": new_pending,
        "new_promoted": new_promoted,
        "new_rejected": new_rejected,
        "total_knowledge": total_knowledge,
        "rejection_rate": (
            round(new_rejected / max(new_promoted + new_rejected, 1), 3)
        ),
    }


# ─── 5 Learning Feeds (A2A bus subscriptions) ────────────────────────
# Each feed turns observed events into Tier-2 pending learnings via
# sovereign_memory.submit_learning so the Council can audit + promote.
# Feeds are throttled in-memory to avoid duplicate submissions per pattern.

_FEED_DEDUPE_WINDOW_S = 600  # 10 minutes
_recent_patterns: Dict[str, datetime] = {}


def _seen_recently(pattern: str) -> bool:
    now = _now()
    last = _recent_patterns.get(pattern)
    if last and (now - last).total_seconds() < _FEED_DEDUPE_WINDOW_S:
        return True
    _recent_patterns[pattern] = now
    # Trim old entries (cap memory)
    if len(_recent_patterns) > 500:
        cutoff = now - timedelta(seconds=_FEED_DEDUPE_WINDOW_S)
        for k in list(_recent_patterns.keys()):
            if _recent_patterns[k] < cutoff:
                del _recent_patterns[k]
    return False


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def _safe_submit(
    *, agent_role: str, kind: str, payload: Dict[str, Any],
    evidence: Dict[str, Any], confidence: float,
) -> None:
    db = _get_db()
    if db is None:
        return
    try:
        from services.sovereign_memory import submit_learning
        await submit_learning(
            db,
            agent_role=agent_role,
            kind=kind,
            payload=payload,
            evidence=evidence,
            confidence=confidence,
        )
    except ValueError:
        # Contract violation (unknown role / missing evidence) — drop silently
        return
    except Exception as e:
        logger.debug(f"[learning-feed] submit failed kind={kind}: {e}")


# Feed 1: CODE_FIX_APPLIED → submit kind=code_fix
async def _feed_code_fix(payload: Dict[str, Any]) -> None:
    fix = (payload.get("fix_description") or payload.get("fix") or "")[:120]
    err = (payload.get("error_type") or payload.get("error") or "")[:80]
    pattern = f"code_fix:{err}:{fix}"
    if _seen_recently(pattern):
        return
    await _safe_submit(
        agent_role="dev",
        kind="code_fix",
        payload={"pattern": pattern, "fix": fix, "error": err,
                 "files_changed": payload.get("files_changed", [])},
        evidence={"source": "auto_repair", "raw": payload, "ts": _iso()},
        confidence=0.7,
    )


# Feed 2: COUNCIL_REJECTED → submit kind=council_pattern
async def _feed_council_reject(payload: Dict[str, Any]) -> None:
    agent = payload.get("agent", "?")
    reason = (payload.get("reason") or payload.get("verdict_reason") or "")[:100]
    pattern = f"council_reject:{agent}:{reason}"
    if _seen_recently(pattern):
        return
    await _safe_submit(
        agent_role="qa",
        kind="council_pattern",
        payload={"pattern": pattern, "agent": agent, "reason": reason},
        evidence={"source": "council", "raw": payload, "ts": _iso()},
        confidence=0.6,
    )


# Feed 3: WEDGE_HEALED → submit kind=wedge_recipe
async def _feed_wedge_healed(payload: Dict[str, Any]) -> None:
    tier = payload.get("tier", "?")
    agent = payload.get("agent", "?")
    pattern = f"wedge_recipe:{tier}:{agent}"
    if _seen_recently(pattern):
        return
    await _safe_submit(
        agent_role="watchdog",
        kind="wedge_recipe",
        payload={"pattern": pattern, "tier": tier, "agent": agent,
                 "age_seconds": payload.get("age_seconds_before_heal")},
        evidence={"source": "wedge_detector", "raw": payload, "ts": _iso()},
        confidence=0.75,
    )


# Feed 4: HOT_REPLY → submit kind=hot_signal
async def _feed_hot(payload: Dict[str, Any]) -> None:
    channel = payload.get("channel", "?")
    text = (payload.get("text") or "")[:60]
    pattern = f"hot_signal:{channel}:{text[:24]}"
    if _seen_recently(pattern):
        return
    await _safe_submit(
        agent_role="closer",
        kind="hot_signal",
        payload={"pattern": pattern, "channel": channel, "snippet": text},
        evidence={"source": "blast_chain", "raw": payload, "ts": _iso()},
        confidence=0.65,
    )


# Feed 5: DEPLOY_DETECTED → submit kind=deploy_event
async def _feed_deploy(payload: Dict[str, Any]) -> None:
    old = payload.get("old", "?")[:24]
    new = payload.get("new", "?")[:24]
    pattern = f"deploy:{old}->{new}"
    if _seen_recently(pattern):
        return
    await _safe_submit(
        agent_role="dev",
        kind="deploy_event",
        payload={"pattern": pattern, "old": old, "new": new},
        evidence={"source": "deploy_monitor", "raw": payload, "ts": _iso()},
        confidence=0.9,
    )


_FEEDS = (
    ("CODE_FIX_APPLIED", _feed_code_fix),
    ("COUNCIL_REJECTED", _feed_council_reject),
    ("WEDGE_HEALED",     _feed_wedge_healed),
    ("HOT_REPLY",        _feed_hot),
    ("DEPLOY_DETECTED",  _feed_deploy),
)


def register_feeds() -> None:
    """Subscribe all 5 learning feeds to the A2A bus."""
    from services.a2a_bus import bus
    for event, handler in _FEEDS:
        bus.subscribe(event, handler)
    logger.info(f"[ora_knowledge] {len(_FEEDS)} learning feeds registered")


# ─── Nightly Learning Digest ─────────────────────────────────────────

async def write_nightly_digest() -> Dict[str, Any]:
    """Compute + persist a 24h learning summary. Idempotent per UTC day."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}
    day_key = _now().strftime("%Y-%m-%d")
    existing = await db[DIGEST].find_one({"day": day_key}, {"_id": 0})
    if existing:
        return existing

    summary, top = await asyncio.gather(
        summarize_period(db, hours=24),
        top_patterns(db, limit=5),
    )
    digest = {
        "day": day_key,
        "ts": _iso(),
        "summary": summary,
        "top_patterns": top,
    }
    await db[DIGEST].update_one({"day": day_key}, {"$set": digest}, upsert=True)
    logger.info(
        f"[ora_knowledge] nightly digest day={day_key} "
        f"new_promoted={summary.get('new_promoted')} "
        f"top={[p.get('pattern','')[:40] for p in top[:3]]}",
    )
    return digest


def nightly_digest_scheduler():
    async def _loop():
        # First run: 5 minutes after attach (debounce post-deploy bursts)
        await asyncio.sleep(300)
        while True:
            try:
                # Sleep until next 03:00 UTC
                now = _now()
                target = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if target <= now:
                    target = target + timedelta(days=1)
                await asyncio.sleep(max(60, (target - now).total_seconds()))
                await write_nightly_digest()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[ora_knowledge] nightly digest err: {e}")
                await asyncio.sleep(3600)
    return _loop


# ─── Weekly Self-Assessment ──────────────────────────────────────────

async def write_self_assessment() -> Dict[str, Any]:
    """Tier-3 confidence snapshot + agent health overview."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}
    week_key = _now().strftime("%G-W%V")
    existing = await db[ASSESS].find_one({"week": week_key}, {"_id": 0})
    if existing:
        return existing

    cutoff_24h = (_now() - timedelta(hours=24)).isoformat()
    cutoff_7d = (_now() - timedelta(days=7)).isoformat()

    # Average confidence + count of active knowledge
    pipeline = [
        {"$match": {"active": True}},
        {"$group": {
            "_id": None,
            "avg_conf": {"$avg": "$confidence"},
            "total": {"$sum": 1},
            "total_seen": {"$sum": "$times_seen"},
        }},
    ]
    confidence_doc: List[Dict[str, Any]] = await db[KNOWLEDGE].aggregate(pipeline).to_list(1)
    avg_conf = round(confidence_doc[0]["avg_conf"], 3) if confidence_doc else 0.0
    total_knowledge = confidence_doc[0]["total"] if confidence_doc else 0
    total_seen = confidence_doc[0]["total_seen"] if confidence_doc else 0

    # Agents heartbeat health
    active_agents, silent_agents, paused_agents = await asyncio.gather(
        db.agent_heartbeats.count_documents({"last_beat": {"$gte": cutoff_24h}}),
        db.agent_heartbeats.count_documents({"last_beat": {"$lt": cutoff_24h}}),
        db.agent_heartbeats.count_documents({"status": "paused"}),
    )

    # Top 7-day patterns
    top_7d = await top_patterns(db, limit=10)

    # 7-day promoted/rejected
    promoted_7d, rejected_7d = await asyncio.gather(
        db[PENDING].count_documents({"status": "promoted", "promoted_at": {"$gte": cutoff_7d}}),
        db[PENDING].count_documents({"status": "rejected", "rejected_at": {"$gte": cutoff_7d}}),
    )

    assessment = {
        "week": week_key,
        "ts": _iso(),
        "confidence": {
            "avg_confidence": avg_conf,
            "total_knowledge": total_knowledge,
            "total_seen": total_seen,
        },
        "agents": {
            "active_24h": active_agents,
            "silent_24h": silent_agents,
            "paused": paused_agents,
        },
        "learnings_7d": {
            "promoted": promoted_7d,
            "rejected": rejected_7d,
            "rejection_rate": round(rejected_7d / max(promoted_7d + rejected_7d, 1), 3),
        },
        "top_patterns": top_7d,
    }
    await db[ASSESS].update_one(
        {"week": week_key}, {"$set": assessment}, upsert=True,
    )
    logger.info(
        f"[ora_knowledge] self-assessment week={week_key} "
        f"avg_conf={avg_conf} promoted_7d={promoted_7d}",
    )
    return assessment


def weekly_self_assessment_scheduler():
    async def _loop():
        await asyncio.sleep(600)
        while True:
            try:
                now = _now()
                # Sunday = weekday() == 6
                days_until_sun = (6 - now.weekday()) % 7
                target = (now + timedelta(days=days_until_sun)).replace(
                    hour=4, minute=0, second=0, microsecond=0,
                )
                if target <= now:
                    target = target + timedelta(days=7)
                await asyncio.sleep(max(60, (target - now).total_seconds()))
                await write_self_assessment()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[ora_knowledge] self-assessment err: {e}")
                await asyncio.sleep(3600)
    return _loop


# ─────────────────────────────────────────────────────────────────────
# v4.0 spec compatibility: short alias used by agent decision callers
# (e.g. `await ora.query("lead_pattern", industry=...)`) — same signature
# as query_knowledge(). Keep both exported for clarity.
# ─────────────────────────────────────────────────────────────────────
query = query_knowledge
