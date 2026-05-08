"""
AUREM Council Deliberate Engine — Phase 0
==========================================
Parallel-vote consensus across required + advisory voters.

Required voters' REJECT halts the action.
Advisory voters annotate but never block.
Voter exceptions → fail-safe APPROVE (with reason logged).

Public:
  await deliberate(action, agent, payload,
                   required=["casl","qa"],
                   advisory=["security","pricing"])
  → {"verdict": "APPROVED|REJECTED",
     "votes": {voter: {"vote": "...", "reason": "..."}},
     "confidence": 0.0..1.0}
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# voter_name → (module_path, attr_name)
VOTER_MODULES: Dict[str, Tuple[str, str]] = {
    "casl":     ("services.casl_compliance",      "vote"),
    "qa":       ("services.qa_agent_deep",        "vote"),
    "security": ("services.aurem_skills.security_review", "vote"),
    "pricing":  ("services.agents.pricing_agent", "vote"),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def _get_vote(voter: str, action: str, payload: Dict[str, Any]) -> Tuple[str, str]:
    """Resolve voter's vote() function and call it. Tuple (vote, reason)."""
    if voter not in VOTER_MODULES:
        return "APPROVE", f"voter {voter} not registered (failsafe)"
    mod_path, attr = VOTER_MODULES[voter]
    try:
        mod = importlib.import_module(mod_path)
        fn = getattr(mod, attr, None)
        if fn is None:
            return "APPROVE", f"voter {voter} missing vote()"
        result = await fn(action, payload)
        if isinstance(result, tuple) and len(result) >= 2:
            return str(result[0]).upper(), str(result[1])
        return "APPROVE", str(result)
    except Exception as e:
        logger.warning(f"[council] voter {voter} crashed: {e}")
        return "APPROVE", f"voter_error_failsafe:{type(e).__name__}"


async def deliberate(
    action: str,
    agent: str,
    payload: Dict[str, Any],
    *,
    required: List[str] = None,
    advisory: List[str] = None,
) -> Dict[str, Any]:
    """Run parallel votes; required REJECT halts; advisory annotates."""
    required = required or ["casl", "qa"]
    advisory = advisory or ["security", "pricing"]

    # Required votes — parallel
    required_results = await asyncio.gather(
        *[_get_vote(v, action, payload) for v in required],
        return_exceptions=True,
    )

    votes: Dict[str, Dict[str, str]] = {}
    rejected_by = None
    rejection_reason = ""
    for voter, result in zip(required, required_results):
        if isinstance(result, Exception):
            votes[voter] = {"vote": "APPROVE",
                            "reason": f"voter_error_failsafe:{type(result).__name__}"}
            continue
        vote, reason = result
        votes[voter] = {"vote": vote, "reason": reason}
        if vote == "REJECT":
            rejected_by = voter
            rejection_reason = reason
            break

    db = _get_db()

    if rejected_by:
        # Advisory still runs but only logged for ORA learning
        verdict = "REJECTED"
        # Try imports lazily to avoid circular deps
        try:
            from services.a2a_bus import bus
            await bus.emit("council", "COUNCIL_REJECTED",
                           {"action": action, "agent": agent,
                            "voter": rejected_by, "reason": rejection_reason})
        except Exception:
            pass
        if db is not None:
            try:
                await db.council_decisions_detailed.insert_one({
                    "action": action, "requesting_agent": agent,
                    "votes": votes, "verdict": verdict,
                    "rejected_by": rejected_by,
                    "confidence": 0.0,
                    "ts": _utc_now(),
                })
            except Exception as e:
                logger.debug(f"[council] persist reject skipped: {e}")
        return {"verdict": verdict, "votes": votes, "confidence": 0.0}

    # Advisory — parallel, never blocks
    advisory_results = await asyncio.gather(
        *[_get_vote(v, action, payload) for v in advisory],
        return_exceptions=True,
    )
    for voter, result in zip(advisory, advisory_results):
        if isinstance(result, Exception):
            votes[voter] = {"vote": "APPROVE",
                            "reason": f"voter_error_failsafe:{type(result).__name__}"}
            continue
        vote, reason = result
        votes[voter] = {"vote": vote, "reason": reason}

    confidence = (
        sum(1 for v in votes.values() if v["vote"] == "APPROVE")
        / max(len(votes), 1)
    )
    verdict = "APPROVED"

    # Parallel persist + emit
    persist_tasks = []
    if db is not None:
        persist_tasks.append(db.council_decisions_detailed.insert_one({
            "action": action, "requesting_agent": agent,
            "votes": votes, "verdict": verdict,
            "confidence": confidence,
            "ts": _utc_now(),
        }))
        persist_tasks.append(db.learnings_pending_review.insert_one({
            "id": f"council_{action}_{int(_utc_now().timestamp())}",
            "kind": "council_pattern",
            "pattern": f"{agent}_{action}",
            "payload": {"votes": votes},
            "evidence": [],
            "confidence": confidence,
            "submitted_by": "council_deliberate",
            "submitted_at": _utc_now().isoformat(),
            "stamps": [],
            "status": "pending",
        }))
    try:
        from services.a2a_bus import bus
        persist_tasks.append(bus.emit("council", "COUNCIL_APPROVED",
                                      {"action": action, "agent": agent,
                                       "confidence": confidence}))
    except Exception:
        pass
    if persist_tasks:
        await asyncio.gather(*persist_tasks, return_exceptions=True)

    return {"verdict": verdict, "votes": votes, "confidence": confidence}
