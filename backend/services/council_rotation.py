"""
AUREM Council Rotation Worker (iter 322l — Day 2.2)
====================================================
Self-driving 2-stamp learning reviewer.

Every `ROTATION_INTERVAL_S` seconds:
  1. Pick a Council agent role at random (excluding the role that
     submitted any pending learnings the last cycle).
  2. Ask `sovereign_memory.next_pending_for_review(role)` for the oldest
     pending candidate this agent hasn't already stamped.
  3. Build a deterministic LLM prompt with kind / payload / evidence and
     have the agent vote `approve` / `reject`.
  4. Call `sovereign_memory.review_learning(...)` to persist the stamp.
  5. The 2nd distinct-role approve auto-promotes to canonical
     `learnings` — without any manual API call.

Boundaries
----------
- Defaults to `RUN_LIMIT` reviews per cycle so a flood of submissions
  never starves the loop.
- LLM unreachable → defaults to `reject` with reason `llm_unavailable`
  (rejection is final; the agent can resubmit a higher-quality candidate
  later — this prevents low-quality learnings from drifting in).
- Idempotent: every call goes through `review_learning` which already
  blocks `self_stamp`, `duplicate_stamp`, and post-terminal stamps.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from typing import Any, Dict, List, Optional

from services import sovereign_memory as smg

logger = logging.getLogger(__name__)


# ─── Config ──────────────────────────────────────────────────────────────
ROTATION_INTERVAL_S = int(os.environ.get("COUNCIL_ROTATION_INTERVAL_S", "300"))
RUN_LIMIT = int(os.environ.get("COUNCIL_ROTATION_RUN_LIMIT", "5"))

# Roles eligible to stamp via the rotation loop. System-only roles
# (watchdog, latency_guardian) are excluded — their stamp authority is
# limited to their own subsystem fixes, not arbitrary peer review.
ROTATION_ROLES = ["dev", "qa", "security", "pricing", "casl", "seo"]

_started = False


# ─── Decision logic ─────────────────────────────────────────────────────
async def _agent_decide(
    *, agent_role: str, candidate: Dict[str, Any], db,
) -> Dict[str, str]:
    """Ask the Council agent to vote. Returns {"vote": ..., "notes": ...}."""
    try:
        from services.ora_council import convene_council
        prompt = (
            f"AUTONOMOUS LEARNING REVIEW — you are the {agent_role} agent.\n"
            f"A peer agent ({candidate.get('submitted_by')}) submitted a "
            f"learning candidate of kind `{candidate.get('kind')}`.\n"
            f"Payload: {candidate.get('payload')}\n"
            f"Evidence: {candidate.get('evidence')}\n"
            f"As the {agent_role} agent applying the Sovereign Truth standard, "
            f"reply ONE LINE in this format: "
            f"`<APPROVE|REJECT> — <one-sentence reason>`. "
            f"Approve only if the evidence aligns with the claimed payload. "
            f"Reject when evidence is missing, contradictory, or thin."
        )
        out = await convene_council(
            prompt,
            {
                "source": "council_rotation_worker",
                "review_role": agent_role,
                "evidence": {
                    "kind": candidate.get("kind"),
                    "submitted_by": candidate.get("submitted_by"),
                    "payload": candidate.get("payload"),
                    "candidate_evidence": candidate.get("evidence"),
                },
            },
            db,
        )
        text = (out.get("final_response") or "").strip()
        if not text:
            return {"vote": "reject", "notes": "council_empty_response"}
        # Tolerant parsing — accept ACCEPT/APPROVE both.
        head = text.upper().lstrip()
        if re.match(r"^(APPROVE|ACCEPT)\b", head):
            return {"vote": "approve", "notes": text[:240]}
        return {"vote": "reject", "notes": text[:240]}
    except Exception as e:
        return {
            "vote": "reject",
            "notes": f"llm_unavailable:{str(e)[:120]}",
        }


# ─── Single rotation tick ───────────────────────────────────────────────
async def rotate_once(db) -> Dict[str, Any]:
    """Run up to RUN_LIMIT review cycles. Returns a summary."""
    if db is None:
        return {"reviews": 0, "promoted": 0, "skipped": 0, "error": "db_unavailable"}

    reviews = 0
    promoted = 0
    skipped = 0
    by_role: Dict[str, int] = {}

    roles = list(ROTATION_ROLES)
    random.shuffle(roles)

    for role in roles:
        if reviews >= RUN_LIMIT:
            break
        candidate = await smg.next_pending_for_review(db, exclude_role=role)
        if not candidate:
            continue

        decision = await _agent_decide(
            agent_role=role, candidate=candidate, db=db,
        )
        try:
            # Defensive: candidate might come from a row inserted without
            # an `id` field (e.g., wedge observations) — fall back to the
            # Mongo `_id` so council rotation doesn't KeyError.
            learning_id = candidate.get("id") or str(candidate.get("_id") or "")
            if not learning_id:
                logger.debug("[council-rotation] candidate has no id — skipping")
                skipped += 1
                continue
            res = await smg.review_learning(
                db,
                learning_id=learning_id,
                reviewer_role=role,
                vote=decision["vote"],
                notes=decision["notes"],
            )
        except Exception as e:
            logger.warning(f"[council-rotation] review error: {e}")
            skipped += 1
            continue

        if not res.get("ok"):
            skipped += 1
            continue
        reviews += 1
        by_role[role] = by_role.get(role, 0) + 1
        if res.get("promoted"):
            promoted += 1

    return {
        "reviews": reviews,
        "promoted": promoted,
        "skipped": skipped,
        "by_role": by_role,
        "interval_s": ROTATION_INTERVAL_S,
    }


# ─── Background loop ───────────────────────────────────────────────────
async def _rotation_loop(db) -> None:
    logger.info(
        f"[council-rotation] online — interval={ROTATION_INTERVAL_S}s "
        f"roles={ROTATION_ROLES}",
    )
    # Stagger 30s so we don't pile on top of the watchdog's first scan.
    await asyncio.sleep(30)
    while True:
        try:
            summary = await rotate_once(db)
            if summary.get("reviews"):
                logger.info(f"[council-rotation] tick: {summary}")
        except Exception as e:
            logger.warning(f"[council-rotation] tick failed: {e}")
        await asyncio.sleep(ROTATION_INTERVAL_S)


def start_council_rotation(db) -> bool:
    """Idempotent launcher — called from server.py startup."""
    global _started
    if _started:
        return False
    if os.environ.get("COUNCIL_ROTATION_DISABLED", "").lower() in ("1", "true", "yes"):
        logger.info("[council-rotation] disabled via env")
        return False
    try:
        asyncio.create_task(_rotation_loop(db))
        _started = True
        return True
    except RuntimeError:
        return False
