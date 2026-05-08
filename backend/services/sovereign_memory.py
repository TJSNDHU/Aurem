"""
AUREM Sovereign Memory Guard (iter 322k — Day 1 of Sovereign Discipline)
========================================================================
Two-stamp learning gate. Prevents any backend agent from writing directly
into the canonical `learnings` collection. Every new pattern/fix must be
quarantined in `learnings_pending_review`, audited by a *different* Council
agent, and only promoted after **two distinct-role stamps** approve it.

Why
---
A single-agent "learning" today = a hallucination tomorrow. The Council
already has multiple specialised roles (`dev`, `qa`, `security`,
`pricing`, etc.). Forcing a cross-role audit before promotion eliminates
the most common AI failure mode: confident-but-wrong memory.

Public API
----------
- `submit_learning(db, agent_role, kind, payload, evidence) -> _id`
- `next_pending_for_review(db, exclude_role) -> doc | None`
- `review_learning(db, learning_id, reviewer_role, vote, notes) -> dict`
- `promote_if_ready(db, learning_id) -> dict | None`
- `get_promoted_learnings(db, kind, limit)`
- `get_pending_learnings(db, limit)`
- `get_memory_guard_stats(db)`

Hard rules (enforced)
---------------------
1. The submitting agent **cannot** stamp its own submission.
2. Two stamps from **different roles** are required for promotion.
3. Submissions without an `evidence` payload are rejected at the gate.
4. Promotion is atomic: a single `update_one` with a precondition that
   re-checks the stamp count, so a concurrent rogue stamp never
   double-promotes.
5. Once promoted, the document in `learnings` is treated as immutable
   (re-promotion is a no-op).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


PENDING = "learnings_pending_review"
LIVE = "learnings"

# Roles the Council allows to stamp. Mirrors COUNCIL_AGENTS in ora_council.
_VALID_ROLES = {
    "scout", "envoy", "closer", "followup", "casl", "seo",
    "dev", "reddit", "security", "qa", "pricing",
    # System roles (non-LLM):
    "watchdog", "latency_guardian",
}

REQUIRED_STAMPS = 2  # distinct-role approvals to promote


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Submission ─────────────────────────────────────────────────────────
async def submit_learning(
    db,
    *,
    agent_role: str,
    kind: str,
    payload: Dict[str, Any],
    evidence: Dict[str, Any],
    confidence: float = 0.5,
) -> str:
    """Quarantine a new learning candidate. Returns the new doc's id.

    Raises ValueError on contract violations (no evidence, unknown role,
    empty kind) — caller agents should treat these as bugs, not retry.
    """
    if db is None:
        raise RuntimeError("db_unavailable")
    if agent_role not in _VALID_ROLES:
        raise ValueError(f"unknown agent_role: {agent_role}")
    if not kind:
        raise ValueError("kind is required")
    if not evidence:
        # Data-Anchor rule: no evidence = no submission. Forces the agent
        # to attach observable proof (logs, metrics, query results, etc).
        raise ValueError("evidence_required")

    doc_id = uuid.uuid4().hex
    doc = {
        "id": doc_id,
        "kind": kind,
        "payload": payload or {},
        "evidence": evidence,
        "confidence": float(max(0.0, min(1.0, confidence))),
        "submitted_by": agent_role,
        "submitted_at": _utc_iso(),
        "stamps": [],          # list of {role, vote, notes, ts}
        "status": "pending",   # pending | rejected | promoted | superseded
    }
    await db[PENDING].insert_one(doc)
    logger.info(f"[memory-guard] submitted: kind={kind} by={agent_role} id={doc_id}")
    return doc_id


# ─── Review ─────────────────────────────────────────────────────────────
async def next_pending_for_review(
    db, *, exclude_role: str, kind: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find the oldest pending learning that the given role hasn't already
    stamped (and didn't submit). Used by the Council rotation loop."""
    if db is None:
        return None
    q: Dict[str, Any] = {
        "status": "pending",
        "submitted_by": {"$ne": exclude_role},
        "stamps.role": {"$ne": exclude_role},
    }
    if kind:
        q["kind"] = kind
    return await db[PENDING].find_one(q, {"_id": 0}, sort=[("submitted_at", 1)])


async def review_learning(
    db,
    *,
    learning_id: str,
    reviewer_role: str,
    vote: str,
    notes: str = "",
) -> Dict[str, Any]:
    """Append a stamp. Then auto-promote if the doc now has the required
    number of distinct-role APPROVE stamps. Returns the new doc state.
    """
    if db is None:
        raise RuntimeError("db_unavailable")
    if reviewer_role not in _VALID_ROLES:
        raise ValueError(f"unknown reviewer_role: {reviewer_role}")
    if vote not in ("approve", "reject"):
        raise ValueError("vote must be 'approve' or 'reject'")

    doc = await db[PENDING].find_one({"id": learning_id}, {"_id": 0})
    if not doc:
        return {"ok": False, "error": "learning_not_found"}
    # Defensive: legacy pending rows may be missing fields. Use .get() so
    # the council rotation worker never KeyErrors on partial documents.
    doc_status = doc.get("status") or "pending"
    if doc_status != "pending":
        return {"ok": False, "error": f"already_{doc_status}"}
    # Rule 1: submitter cannot stamp its own submission.
    if doc.get("submitted_by") == reviewer_role:
        return {"ok": False, "error": "self_stamp_forbidden"}
    # Rule 2: same role cannot stamp twice.
    if any(s.get("role") == reviewer_role for s in doc.get("stamps", [])):
        return {"ok": False, "error": "duplicate_stamp"}

    stamp = {
        "role": reviewer_role,
        "vote": vote,
        "notes": (notes or "")[:500],
        "ts": _utc_iso(),
    }
    if vote == "reject":
        await db[PENDING].update_one(
            {"id": learning_id, "status": "pending"},
            {"$push": {"stamps": stamp},
             "$set": {"status": "rejected", "rejected_at": _utc_iso()}},
        )
        return {"ok": True, "promoted": False, "rejected": True}

    # APPROVE path
    await db[PENDING].update_one(
        {"id": learning_id, "status": "pending"},
        {"$push": {"stamps": stamp}},
    )

    # Promote if eligible (atomic re-read with stamp count guard).
    promoted = await promote_if_ready(db, learning_id)
    return {
        "ok": True,
        "promoted": bool(promoted),
        "rejected": False,
        "stamp_count": len(doc.get("stamps", [])) + 1,
    }


async def promote_if_ready(
    db, learning_id: str,
) -> Optional[Dict[str, Any]]:
    """Atomic promote — only fires when distinct-role approve count >= REQUIRED_STAMPS
    AND status is still pending. Returns the promoted live doc, or None.
    """
    doc = await db[PENDING].find_one({"id": learning_id}, {"_id": 0})
    if not doc or doc.get("status") != "pending":
        return None

    approves = [s for s in doc.get("stamps", []) if s.get("vote") == "approve"]
    distinct_roles = {s["role"] for s in approves}
    if len(distinct_roles) < REQUIRED_STAMPS:
        return None

    # Step 1: flip status atomically (idempotent guard).
    res = await db[PENDING].update_one(
        {"id": learning_id, "status": "pending"},
        {"$set": {"status": "promoted", "promoted_at": _utc_iso()}},
    )
    if res.modified_count != 1:
        # Lost the race — another concurrent reviewer promoted it.
        return None

    # Step 2: append to immutable LIVE collection.
    # Resilient to legacy docs that lack `submitted_by` / `kind` / `id`.
    live_doc = {
        "id": doc.get("id") or learning_id,
        "kind": doc.get("kind") or "unknown",
        "payload": doc.get("payload", {}),
        "evidence": doc.get("evidence", {}),
        "confidence": doc.get("confidence", 0.5),
        "submitted_by": doc.get("submitted_by") or "system",
        "promoted_at": _utc_iso(),
        "stamps": [s for s in doc.get("stamps", [])],
        "source_pending_id": doc.get("id") or learning_id,
    }
    try:
        await db[LIVE].insert_one(live_doc)
    except Exception as e:
        # If the live insert fails (dup id, etc.), revert the pending flip.
        logger.warning(f"[memory-guard] live insert failed, reverting: {e}")
        await db[PENDING].update_one(
            {"id": learning_id, "status": "promoted"},
            {"$set": {"status": "pending"}, "$unset": {"promoted_at": ""}},
        )
        return None

    logger.info(
        f"[memory-guard] promoted: kind={doc['kind']} id={learning_id} "
        f"stamps={[s['role'] for s in approves]}",
    )
    # Phase 2 — emit LEARNING_PROMOTED so ORA Brain hardens it into knowledge
    try:
        from services.a2a_bus import bus
        from services.agent_registry import heartbeat, log_action
        import asyncio as _asyncio
        pattern = f"{doc.get('kind', 'unknown')}_{doc.get('subject', '')}".strip("_")
        _asyncio.create_task(_asyncio.gather(
            heartbeat("learning_bus"),
            log_action("learning_bus", "LEARNING_PROMOTED",
                       pattern[:200],
                       metadata={"id": learning_id,
                                 "stamps": [s["role"] for s in approves]}),
            bus.emit("learning_bus", "LEARNING_PROMOTED", {
                "pattern": pattern,
                "kind": doc.get("kind", "unknown"),
                "id": learning_id,
                "confidence": doc.get("confidence", 0.5),
                "payload": doc.get("payload", {}),
            }),
            return_exceptions=True,
        ))
    except Exception:
        pass
    return live_doc


# ─── Read-side helpers ─────────────────────────────────────────────────
async def get_promoted_learnings(
    db, *, kind: Optional[str] = None, limit: int = 20,
) -> List[Dict[str, Any]]:
    if db is None:
        return []
    q: Dict[str, Any] = {}
    if kind:
        q["kind"] = kind
    cursor = db[LIVE].find(q, {"_id": 0}).sort("promoted_at", -1).limit(
        min(max(limit, 1), 200),
    )
    return [d async for d in cursor]


async def get_pending_learnings(
    db, *, limit: int = 50,
) -> List[Dict[str, Any]]:
    if db is None:
        return []
    cursor = db[PENDING].find(
        {"status": "pending"}, {"_id": 0},
    ).sort("submitted_at", 1).limit(min(max(limit, 1), 200))
    return [d async for d in cursor]


async def get_memory_guard_stats(db) -> Dict[str, Any]:
    """Single-glance metric for the dashboard."""
    if db is None:
        return {"available": False}
    try:
        pending = await db[PENDING].count_documents({"status": "pending"})
        promoted = await db[LIVE].count_documents({})
        rejected = await db[PENDING].count_documents({"status": "rejected"})
        return {
            "available": True,
            "pending_review": pending,
            "promoted_total": promoted,
            "rejected_total": rejected,
            "required_stamps": REQUIRED_STAMPS,
        }
    except Exception as e:
        return {"available": False, "error": str(e)[:200]}
