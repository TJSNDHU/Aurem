"""
ORA Fix Learning Pipeline — iter 322ar
========================================
Every applied fix teaches ORA. After Tier-1 auto-execute, Tier-2 founder
approval, OR Emergent-driven fix is applied, this pipeline:

  1. Builds a fingerprint of the issue (sha256 over agent + evidence
     type + metric_name + gap-bucket).
  2. Upserts a row in `db.fix_patterns` — increments `times_seen`,
     `times_fixed_successfully`, recomputes `confidence`.
  3. Writes a `fix_learned` thought into `db.ora_brain_thoughts` so the
     ORA brain corpus grows.
  4. Emits an A2A bus event so live learners (evolver, council voters)
     can react.

Read side: `services.ora_pattern_matcher.check_ora_knows(issue)` consults
this collection BEFORE escalating to paid LLMs.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _gap_bucket(gap: Any) -> str:
    """Bucket numeric gaps so fingerprints group similar-magnitude issues."""
    try:
        g = float(gap)
    except Exception:
        return "na"
    if g <= 0:
        return "0"
    if g <= 1:
        return "1"
    if g <= 10:
        return "1-10"
    if g <= 100:
        return "10-100"
    if g <= 1000:
        return "100-1k"
    return "1k+"


def fingerprint_issue(issue: Dict[str, Any]) -> str:
    """Stable hash for an issue signature. Same fingerprint = same kind
    of bug across runs / agents."""
    parts = "|".join([
        str(issue.get("agent") or issue.get("subject_agent") or ""),
        str(issue.get("evidence_type") or ""),
        str(issue.get("metric_name") or ""),
        _gap_bucket(issue.get("gap") or issue.get("metric_value") or 0),
    ])
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:24]


def _recalc_confidence(seen: int, success: int) -> float:
    if seen <= 0:
        return 0.0
    # Bayesian smoothing — first few samples shouldn't shoot to 100%.
    # weight prior of 0.5 with seen samples
    prior_weight = 3
    return round((success + prior_weight * 0.5) / (seen + prior_weight), 3)


async def learn_from_fix(fix_event: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a fix-learning row + ORA thought. Returns the updated
    pattern document so callers can show updated confidence."""
    if _db is None:
        logger.warning("[fix-learn] db not ready, skipping")
        return {"ok": False, "reason": "db_unavailable"}

    issue = fix_event.get("issue") or {}
    fix = fix_event.get("fix") or {}
    outcome = fix_event.get("outcome") or {}
    source = fix_event.get("source", "unknown")
    fp = fingerprint_issue(issue)
    passed = bool(outcome.get("verification_passed"))

    update = {
        "$inc": {
            "times_seen": 1,
            "times_fixed_successfully": 1 if passed else 0,
        },
        "$setOnInsert": {
            "fingerprint": fp,
            "first_seen": _utc_now(),
            "issue_signature": {
                "agent": issue.get("agent") or issue.get("subject_agent"),
                "evidence_type": issue.get("evidence_type"),
                "metric_name": issue.get("metric_name"),
            },
        },
        "$set": {
            "last_fix_applied": {
                "fix_type": fix.get("fix_type"),
                "files_changed": fix.get("files_changed", []),
                "config_changed": fix.get("config_changed"),
                "action_taken": fix.get("action_taken"),
            },
            "last_outcome": outcome,
            "last_source": source,
            "last_seen": _utc_now(),
        },
    }

    try:
        await _db.fix_patterns.update_one(
            {"fingerprint": fp}, update, upsert=True,
        )
        row = await _db.fix_patterns.find_one({"fingerprint": fp}, {"_id": 0})
        if row:
            row["confidence"] = _recalc_confidence(
                row.get("times_seen", 0),
                row.get("times_fixed_successfully", 0),
            )
            await _db.fix_patterns.update_one(
                {"fingerprint": fp},
                {"$set": {"confidence": row["confidence"]}},
            )
    except Exception as e:
        logger.warning(f"[fix-learn] upsert failed: {e}")
        return {"ok": False, "reason": str(e)[:120]}

    # Brain thought
    try:
        await _db.ora_brain_thoughts.insert_one({
            "ts": _utc_now(),
            "source": "fix_learning_pipeline",
            "kind": "fix_learned",
            "agent": issue.get("agent") or issue.get("subject_agent"),
            "fingerprint": fp,
            "confidence": row.get("confidence", 0.5) if row else 0.5,
            "summary": (
                f"Fix learned: agent={issue.get('agent') or issue.get('subject_agent')} "
                f"evidence={issue.get('evidence_type')} "
                f"fix_type={fix.get('fix_type','?')} "
                f"passed={passed} via {source}"
            ),
            "issue": issue,
            "fix": fix,
            "outcome": outcome,
        })
    except Exception as e:
        logger.debug(f"[fix-learn] brain-thought write skipped: {e}")

    # A2A
    try:
        from services.a2a_bus import bus
        await bus.emit("fix_learning", "fix_pattern_learned",
                       {"fingerprint": fp, "agent": issue.get("agent"),
                        "confidence": row.get("confidence", 0) if row else 0})
    except Exception:
        pass

    # API-usage cost ledger (for /admin/brain "ORA self-sufficiency" tile)
    try:
        await _db.api_usage_log.insert_one({
            "ts": _utc_now(),
            "issue_type": issue.get("evidence_type"),
            "agent": issue.get("agent"),
            "source_used": source,        # ora_learned | sovereign | groq | openrouter_free | emergent
            "cost": float(fix_event.get("cost_usd", 0.0)),
            "success": passed,
            "fingerprint": fp,
        })
    except Exception:
        pass

    return {"ok": True, "fingerprint": fp, "pattern": row}


async def fix_patterns_summary() -> Dict[str, Any]:
    """For /admin/brain: counts + top-confidence patterns."""
    if _db is None:
        return {"total": 0, "patterns": []}
    try:
        total = await _db.fix_patterns.estimated_document_count()
        top = await _db.fix_patterns.find(
            {}, {"_id": 0}
        ).sort("confidence", -1).limit(8).to_list(8)
        return {"total": total, "top": top}
    except Exception as e:
        return {"total": 0, "patterns": [], "error": str(e)[:120]}


async def ora_self_sufficiency(days: int = 30) -> Dict[str, Any]:
    """Returns the ORA-vs-paid-API split over the last N days plus a
    rough cost-saved estimate (assumes $0.003 / fix avg Emergent cost)."""
    if _db is None:
        return {"ora_ratio": 0, "total": 0}
    try:
        from datetime import timedelta
        since = _utc_now() - timedelta(days=int(days))
        cur = _db.api_usage_log.aggregate([
            {"$match": {"ts": {"$gte": since}}},
            {"$group": {
                "_id": "$source_used",
                "count": {"$sum": 1},
                "cost": {"$sum": "$cost"},
            }},
        ])
        rows: List[Dict[str, Any]] = await cur.to_list(50)
    except Exception:
        rows = []

    counts: Dict[str, int] = {}
    cost_paid = 0.0
    for r in rows:
        src = r.get("_id") or "unknown"
        counts[src] = int(r.get("count", 0))
        if src in ("emergent",):
            cost_paid += float(r.get("cost", 0))
    total = sum(counts.values())
    free_sources = (
        counts.get("ora_learned", 0)
        + counts.get("sovereign", 0)
        + counts.get("groq", 0)
        + counts.get("openrouter_free", 0)
        + counts.get("tier1_auto", 0)
    )
    ratio = round((free_sources / total * 100), 1) if total > 0 else 0.0
    # Rough $ saved assuming every free fix would have cost $0.003 via Emergent
    saved = round(free_sources * 0.003, 2)
    return {
        "ora_ratio": ratio,
        "total": total,
        "free_count": free_sources,
        "paid_count": counts.get("emergent", 0),
        "cost_paid_usd": round(cost_paid, 4),
        "estimated_savings_usd": saved,
        "by_source": counts,
        "window_days": int(days),
    }
