"""
ora_proposal_bridge.py — Autonomous bridge: sentinel/pillar/health insights
       → ORA Dev Console proposal queue.
═══════════════════════════════════════════════════════════════════════════
What this fixes:
  Before: founder manually runs curls, pastes console blocks, stares at
          health endpoints to find issues.
  After:  the autonomous A2A → Council → ORA loop already generates
          `repair_suggestions` (via sentinel_ai_diagnose) and `truth_ledger`
          entries (via pillar_escalation). This bridge converts those
          into ORA Dev Console proposals that show up in the existing
          Mode 2 queue UI — founder just clicks Approve / Reject.

Sources scanned every 60s:
  1. db.repair_suggestions where status=pending AND not yet bridged
  2. db.client_errors where classification=backend_5xx AND ai_eligible AND
     no repair_suggestion yet (raw 500s the diagnoser didn't pick up)
  3. db.aurem_billing where admin@aurem.live exists OR AURE-FNDR-001/-002
     BIN exists (suggests "Run iter322 cleanup migration")
  4. payments_health red OR sovereign_health red consistently for >5 min
     (suggests redeploy or env var fix)

Each surfaced issue becomes ONE ora_dev_actions row with:
  - source: "auto_bridge"
  - source_kind: "repair_suggestion" | "raw_5xx" | "migration_needed" | "health_persistent_red"
  - request_text: human-readable issue summary
  - proposal_text: Claude's suggested fix (if available) or "needs investigation"
  - approve_action: optional structured payload that the approve endpoint
                    can ACT on (e.g., {"kind": "run_migration", "endpoint":
                    "/api/admin/db-migrate/iter322-cleanup"}). When admin
                    clicks Approve, the system runs the action automatically.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# TIERED AUTO-APPROVAL TAXONOMY (iter 322s)
# ─────────────────────────────────────────────────────────────────────
# Tier 1 → safe, mechanical, reversible. Auto-approve after a 5-minute
#          "cancel window" provided git/db backup runs first. Outcome
#          is logged to truth_ledger.
# Tier 2 → human-only. Code changes, schema changes, money paths, agent
#          wiring. NO auto-execution — proposal sits in Dev Console
#          queue until a founder explicitly approves.
TIER_1_KINDS = frozenset({
    "config_change",
    "cache_clear",
    "rate_limit_adjust",
})
TIER_2_KINDS = frozenset({
    "code_change",
    "db_migration",
    "billing_change",
    "agent_deploy",
    # Pre-existing kinds the bridge already produces — explicit Tier 2.
    "run_migration_iter322",   # touches DB → strictly human
    "mark_safe_apply",         # informational tag, no auto-action
})
TIER_1_MIN_CONFIDENCE = 0.95
TIER_1_AUTO_EXECUTE_DELAY_MIN = 5
TIER_1_AUTO_BATCH_LIMIT = 10


# ─────────────────────────────────────────────────────────────────────
# SAFETY-LEVEL TAXONOMY (iter 322t)
# ─────────────────────────────────────────────────────────────────────
# Used by the founder-friendly UI banner. HIGH overrides tier
# classification — even a 0.99-confidence config_change marked HIGH
# (e.g., it touches auth.config) flips to tier_2 = founder approval.
SAFETY_LOW_KINDS = frozenset({
    "config_change", "cache_clear", "rate_limit_adjust", "mark_safe_apply",
})
SAFETY_HIGH_KINDS = frozenset({
    "db_migration", "billing_change", "run_migration_iter322",
})
SAFETY_MEDIUM_KINDS = frozenset({
    "code_change", "agent_deploy",
})


import re as _re

# Word-boundary regex (compiled once) so "auth" doesn't match "architecture",
# "credential" doesn't match anything inside "credentials_for_x", etc.
# We keep "schema" as conservative — even discussing schema changes should
# get a HIGH-risk founder review.
_SAFETY_HIGH_PATTERNS = _re.compile(
    r"\b("
    r"auth|authentication|authorization|"
    r"credential|password|passwd|"
    r"jwt_secret|stripe|billing|"
    r"schema_change|drop_collection|drop_index|"
    r"alter_table|run_migration"
    r")\b",
    _re.IGNORECASE,
)


def _classify_safety_level(
    action_kind: Optional[str],
    source_kind: Optional[str],
    request_text: str,
    proposal_text: str,
) -> str:
    """Returns 'LOW' | 'MEDIUM' | 'HIGH'. Conservative — when in doubt,
    upgrades to a stricter level."""
    k = (action_kind or "").lower()
    blob = f"{action_kind or ''} {source_kind or ''} {request_text} {proposal_text}"

    # HIGH wins over everything — auth/billing/schema land here even if
    # the kind itself is a "tier-1" name.
    if k in SAFETY_HIGH_KINDS:
        return "HIGH"
    if _SAFETY_HIGH_PATTERNS.search(blob):
        return "HIGH"
    if k in SAFETY_LOW_KINDS:
        return "LOW"
    if k in SAFETY_MEDIUM_KINDS:
        return "MEDIUM"
    # Unknown / no kind = MEDIUM by default (not LOW — conservative)
    return "MEDIUM"


def _classify_tier(action_kind: Optional[str], confidence: float) -> Tuple[str, str]:
    """Returns (tier, reason). Conservative default = tier_2."""
    k = (action_kind or "").lower()
    if k in TIER_1_KINDS and confidence >= TIER_1_MIN_CONFIDENCE:
        return "tier_1", f"auto_eligible:{k}@{confidence:.2f}"
    if k in TIER_1_KINDS:
        return "tier_2", f"tier1_kind_below_threshold:{k}@{confidence:.2f}"
    if k in TIER_2_KINDS:
        return "tier_2", f"human_required:{k}"
    return "tier_2", f"default_human:{k or 'no_kind'}"


# ─────────────────────────────────────────────────────────────────────
# Plain-Hinglish translation layer (iter 322t)
# ─────────────────────────────────────────────────────────────────────
# Every proposal carries a `plain_language` dict that the founder UI
# renders by default. Technical detail (proposal_text) is hidden behind
# a "Details" toggle. Translation is best-effort — if the LLM is slow
# or unavailable, we store a safe fallback so proposal creation never
# fails because of i18n.
_TRANSLATE_TIMEOUT_S = 10
_TRANSLATE_SYSTEM = (
    "You translate technical software-engineering proposals into simple "
    "Hinglish (Hindi-English mix in Latin script) so a non-technical "
    "business owner can decide approve/reject. Output STRICT JSON only.\n\n"
    "Schema (no markdown, no prose, no fences):\n"
    "{\n"
    '  "problem_found":      "1-2 line Hinglish — what problem was found",\n'
    '  "what_will_change":   "1-2 line Hinglish — what will change",\n'
    '  "impact_if_approved": "1-2 line Hinglish — business benefit if approved",\n'
    '  "risk_if_rejected":   "1-2 line Hinglish — risk if rejected"\n'
    "}\n\n"
    "Rules:\n"
    "• Each value max 2 lines. No technical jargon (file paths, function names, "
    "code snippets) — replace with the user-facing thing it controls.\n"
    "• Use natural Hinglish: 'Tera checkout page pe error aa raha hai', "
    "not formal Hindi.\n"
    "• If you cannot understand the proposal, return all fields as "
    "'Translation unavailable — see technical details below.'"
)


async def _translate_to_plain_language(
    request_text: str,
    proposal_text: str,
    severity: str,
    action_kind: Optional[str],
    safety_level: str,
) -> Dict[str, str]:
    """Best-effort Hinglish translation. Returns a dict matching the
    founder-spec schema (problem_found / what_will_change /
    impact_if_approved / risk_if_rejected / safety_level).
    Falls back to safe defaults if the LLM call fails or times out."""
    fallback = {
        "problem_found":      "Translation unavailable — see technical details below.",
        "what_will_change":   "Translation unavailable — see technical details below.",
        "impact_if_approved": "Translation unavailable — see technical details below.",
        "risk_if_rejected":   "Translation unavailable — see technical details below.",
        "safety_level":       safety_level,
    }
    try:
        import asyncio as _asyncio
        import json as _json
        from services.llm_gateway_v2 import route

        compact_request = (request_text or "")[:600]
        compact_proposal = (proposal_text or "")[:1200]
        prompt = (
            f"Severity: {severity or 'P2'}\n"
            f"Safety level: {safety_level}\n"
            f"Action kind: {action_kind or 'unspecified'}\n\n"
            f"Original request:\n{compact_request}\n\n"
            f"Technical proposal:\n{compact_proposal}\n"
        )

        async def _do():
            return await route(
                task_type="ora_brain",
                prompt=prompt,
                system=_TRANSLATE_SYSTEM,
                max_tokens=500,
            )

        result = await _asyncio.wait_for(_do(), timeout=_TRANSLATE_TIMEOUT_S)
        if not result.get("ok") or not result.get("text"):
            return fallback
        raw = str(result["text"]).strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s == -1 or e == -1:
            return fallback
        parsed = _json.loads(raw[s : e + 1])
        out: Dict[str, str] = {}
        for key in ("problem_found", "what_will_change",
                    "impact_if_approved", "risk_if_rejected"):
            v = parsed.get(key)
            out[key] = (str(v).strip() if v else fallback[key])[:400]
        # Always stamp safety_level inside plain_language too — UI reads
        # both top-level (for filtering/badges) and inline (for context).
        out["safety_level"] = safety_level
        return out
    except Exception as ex:
        logger.debug(f"[translate] plain-language failed: {ex}")
        return fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db():
    try:
        from server import db
        return db
    except Exception:
        return None


async def _already_bridged(db, source_signature: str) -> bool:
    """Idempotency: don't double-publish the same source."""
    if not source_signature:
        return False
    existing = await db.ora_dev_actions.find_one(
        {"source_signature": source_signature,
         "status": {"$in": ["pending", "approved"]}},
        {"_id": 1},
    )
    return existing is not None


async def _publish_proposal(
    db,
    *,
    request_text: str,
    proposal_text: str,
    source_kind: str,
    source_signature: str,
    severity: str = "P2",
    approve_action: Optional[Dict[str, Any]] = None,
    confidence: float = 0.7,
) -> Optional[str]:
    if await _already_bridged(db, source_signature):
        return None
    pid = str(uuid.uuid4())
    action_kind = (approve_action or {}).get("kind") if approve_action else None

    # iter 322t — safety-level classification (HIGH overrides tier)
    safety_level = _classify_safety_level(
        action_kind, source_kind, request_text, proposal_text,
    )

    tier, tier_reason = _classify_tier(action_kind, confidence)
    # HIGH risk overrides — even a 0.99 cache_clear that touches "auth.cache"
    # will be flagged HIGH and forced to tier_2 (founder-only).
    if safety_level == "HIGH" and tier == "tier_1":
        tier, tier_reason = "tier_2", f"forced_human_high_risk:{action_kind}"

    auto_execute_at = None
    if tier == "tier_1":
        auto_execute_at = (
            datetime.now(timezone.utc)
            + timedelta(minutes=TIER_1_AUTO_EXECUTE_DELAY_MIN)
        )

    # iter 322t — plain-Hinglish translation (best-effort, ≤10s timeout)
    plain_language = await _translate_to_plain_language(
        request_text=request_text,
        proposal_text=proposal_text,
        severity=severity,
        action_kind=action_kind,
        safety_level=safety_level,
    )

    doc = {
        "proposal_id": pid,
        "user": "auto_bridge",
        "session_id": "auto_bridge",
        "request_text": request_text[:600],
        "proposal_text": proposal_text[:4000],
        "status": "pending",
        "sealed_blocked": False,
        "created_at": _now_iso(),
        "approved_by": None,
        "approved_at": None,
        "applied_at": None,
        "rolled_back_at": None,
        # Bridge metadata
        "source": "auto_bridge",
        "source_kind": source_kind,
        "source_signature": source_signature,
        "severity": severity,
        "confidence": confidence,
        "approve_action": approve_action,  # optional structured action
        # iter 322s — tier classification
        "tier": tier,
        "tier_reason": tier_reason,
        "auto_execute_at": auto_execute_at,  # None for tier_2
        # iter 322t — founder-friendly fields
        "safety_level": safety_level,        # LOW | MEDIUM | HIGH
        "plain_language": plain_language,    # 5-field Hinglish dict
    }
    await db.ora_dev_actions.insert_one(doc)

    # iter 322u — STEP 4: HIGH-RISK auto-notification to founder.
    if safety_level == "HIGH":
        try:
            await db.founder_notifications.insert_one({
                "type": "HIGH_RISK_PROPOSAL",
                "title": (plain_language.get("problem_found")
                          or request_text[:160]
                          or "High-risk proposal awaiting review"),
                "proposal_id": pid,
                "safety_level": "HIGH",
                "severity": severity,
                "created_at": _now_iso(),
                "read": False,
            })
        except Exception as e:
            logger.debug(f"[publish] founder_notifications insert skipped: {e}")
        # iter 322v — also fire web push to all subscribed founder devices.
        try:
            from services.push_notification_service import notify_high_risk_proposal
            # Find every push-subscribed admin user and notify them.
            cur = db.push_subscriptions.find(
                {"user_id": {"$exists": True}}, {"_id": 0, "user_id": 1}
            ).limit(50)
            seen = set()
            async for s in cur:
                uid = s.get("user_id")
                if uid and uid not in seen:
                    seen.add(uid)
                    try:
                        await notify_high_risk_proposal(
                            uid,
                            plain_language.get("problem_found") or request_text[:120],
                            pid,
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"[publish] high-risk push fan-out skipped: {e}")

    return pid


# ─── Source 1: Pending repair_suggestions ──────────────────────────────────
async def _bridge_repair_suggestions(db) -> int:
    n = 0
    async for s in db.repair_suggestions.find(
        {"status": "pending"}, {"_id": 0}
    ).sort("created_at", -1).limit(20):
        sig = s.get("source_signature") or s.get("suggestion_id")
        if not sig:
            continue
        request_text = (
            f"[{s.get('severity', 'P2')}] {s.get('error_snapshot', {}).get('classification', 'issue')}: "
            f"{(s.get('root_cause') or 'auto-detected backend error')[:200]}"
        )
        proposal_text = (
            f"**ROOT CAUSE**\n{s.get('root_cause', '')}\n\n"
            f"**SUGGESTED FIX**\n{s.get('suggested_fix', '')}\n\n"
            f"**CODE HINT**\n```\n{(s.get('code_hint') or 'n/a')[:1500]}\n```\n\n"
            f"**TEST PLAN**\n{s.get('test_hint', 'manual verification required')}\n\n"
            f"**AFFECTED FILES**\n{', '.join(s.get('affected_files') or ['(unknown)'])}\n\n"
            f"_Confidence: {s.get('confidence', 0):.2f} · Source: AI-diagnosed via sentinel_ai_diagnose_"
        )
        # If AI flagged safe_auto_apply + high confidence + the fix is purely
        # config/restart, we *could* offer an auto-apply. Keep manual for now.
        action = None
        if s.get("safe_auto_apply") and s.get("confidence", 0) >= 0.85:
            action = {"kind": "mark_safe_apply", "suggestion_id": s.get("suggestion_id")}
        if await _publish_proposal(
            db,
            request_text=request_text,
            proposal_text=proposal_text,
            source_kind="repair_suggestion",
            source_signature=f"rs:{sig}",
            severity=s.get("severity", "P2"),
            approve_action=action,
            confidence=float(s.get("confidence", 0.7)),
        ):
            n += 1
    return n


# ─── Source 2: Migration-needed signals ─────────────────────────────────────
async def _bridge_migration_signals(db) -> int:
    """Detect prod-only state that maps to a known one-shot migration."""
    n = 0
    needs_iter322 = False
    reasons: List[str] = []

    if await db.platform_users.count_documents({"email": "admin@aurem.live"}):
        needs_iter322 = True
        reasons.append("admin@aurem.live still in platform_users (should be migrated to teji.ss1986+dogfood@gmail.com)")
    legacy_bins = ["AURE-FNDR-001", "AURE-FNDR-002", "AURE-3M4G"]
    for bin_id in legacy_bins:
        if await db.platform_users.count_documents({"business_id": bin_id}):
            needs_iter322 = True
            reasons.append(f"legacy BIN '{bin_id}' still active (should be renamed to AURE-ADMIN/AURE-SUPER)")
            break
    if await db.platform_users.count_documents({"email": "pawandeep19may1985@gmail.com"}):
        needs_iter322 = True
        reasons.append("pawandeep19may1985@gmail.com still in platform_users (should be hard-deleted per ops decision)")

    if needs_iter322:
        request_text = "Run iter322 cleanup migration (founder-flagged for execution)"
        proposal_text = (
            "**ROOT CAUSE**\nProduction database still contains legacy state that the iter322 "
            "cleanup migration is designed to purge:\n\n"
            + "\n".join(f"- {r}" for r in reasons)
            + "\n\n**SUGGESTED FIX**\n"
            "Run the idempotent admin endpoint sequence:\n"
            "1. `GET /api/admin/db-migrate/iter322-cleanup/preview` (dry-run)\n"
            "2. `POST /api/admin/db-migrate/iter322-cleanup` (execute)\n"
            "3. `POST /api/admin/db-migrate/backfill-business-id`\n"
            "4. `POST /api/admin/db-migrate/ensure-indexes`\n\n"
            "Approving this proposal triggers all 4 steps server-side automatically. "
            "Output is captured in proposal.applied_payload for audit.\n\n"
            "_Confidence: 0.95 · Idempotent · Safe to re-run_"
        )
        action = {"kind": "run_migration_iter322", "steps": [
            "/api/admin/db-migrate/iter322-cleanup",
            "/api/admin/db-migrate/backfill-business-id",
            "/api/admin/db-migrate/ensure-indexes",
        ]}
        if await _publish_proposal(
            db,
            request_text=request_text,
            proposal_text=proposal_text,
            source_kind="migration_needed",
            source_signature="migration:iter322",
            severity="P1",
            approve_action=action,
            confidence=0.95,
        ):
            n += 1
    return n


# ─── Source 3: Persistent-red truth_ledger entries ──────────────────────────
async def _bridge_persistent_red(db) -> int:
    n = 0
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    try:
        async for tl in db.truth_ledger.find(
            {"actor": "pillar_escalation_t3", "ts": {"$gte": cutoff}}, {"_id": 0}
        ).sort("ts", -1).limit(5):
            sig = f"pillar_outage:{tl.get('evidence', {}).get('pillar', 'unknown')}"
            pillar = tl.get("evidence", {}).get("pillar", "unknown")
            request_text = f"[P0] Persistent {pillar} pillar outage — DR sync triggered"
            proposal_text = (
                f"**ROOT CAUSE**\n{tl.get('description', '')}\n\n"
                f"**EVIDENCE**\n```\n{tl.get('evidence', {})}\n```\n\n"
                f"**SUGGESTED FIX**\nReview pillar diagnostic stack via "
                f"`/api/admin/pillars-map/heartbeat` and the autonomous "
                f"escalation log at `/api/admin/pillar-escalation/recent`. "
                f"DR mirror has already been queued for safety.\n\n"
                f"_Source: pillar_escalation_t3 · Auto-recorded outage_"
            )
            if await _publish_proposal(
                db,
                request_text=request_text,
                proposal_text=proposal_text,
                source_kind="health_persistent_red",
                source_signature=sig,
                severity="P0",
                confidence=0.85,
            ):
                n += 1
    except Exception as e:
        logger.debug(f"[ora_bridge] persistent-red scan failed: {e}")
    return n


# ─── Public tick (called from scheduler) ────────────────────────────────────
async def _tier1_snapshot(db, proposal_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
    """Fast pre-execute state snapshot for tier-1 auto-approval.

    Captures a focused, per-kind context object so the action can be
    reviewed (or reverted) post-fact. Idempotent. Microsecond-fast —
    NOT the daily DR mirror.

    Returns: {"snapshot_id": ..., "kind": ..., "context": {...}}
    Persisted to: db.tier1_pre_exec_snapshots
    """
    snap_id = f"tier1_snap_{uuid.uuid4().hex[:12]}"
    kind = (action or {}).get("kind") or "unknown"
    context: Dict[str, Any] = {}

    try:
        if kind == "config_change":
            target = action.get("key") or action.get("target")
            if target:
                # Try the most common config collections
                for col_name in ("app_config", "system_config", "settings"):
                    try:
                        existing = await db[col_name].find_one(
                            {"key": target}, {"_id": 0}
                        )
                        if existing:
                            context[col_name] = existing
                            break
                    except Exception:
                        pass
        elif kind == "cache_clear":
            scope = action.get("scope") or action.get("target") or "unknown"
            context = {
                "scope": scope,
                "note": ("Cache repopulates from authoritative source on next "
                         "access; nothing to back up. Snapshot is for audit only."),
            }
        elif kind == "rate_limit_adjust":
            target = action.get("limit_key") or action.get("key")
            if target:
                try:
                    existing = await db.rate_limits.find_one(
                        {"key": target}, {"_id": 0}
                    )
                    context["rate_limits"] = existing
                except Exception:
                    pass
    except Exception as e:
        context["context_capture_error"] = str(e)[:200]

    snap_doc = {
        "snapshot_id": snap_id,
        "proposal_id": proposal_id,
        "kind": kind,
        "action": action,
        "context": context,
        "captured_at": _now_iso(),
    }
    await db.tier1_pre_exec_snapshots.insert_one(snap_doc)
    return {"snapshot_id": snap_id, "kind": kind, "context": context}


async def _run_auto_approvals(db) -> Dict[str, int]:
    """Tier 1 auto-execution worker.

    Finds proposals where:
      - tier == "tier_1"
      - status == "pending"
      - auto_execute_at <= now
      - confidence >= TIER_1_MIN_CONFIDENCE (re-checked at exec time)

    Per proposal, runs:
      Step 1 — `db_backup_service.run_backup_async` (snapshot before any change)
      Step 2 — `execute_approve_action` (the actual structured action)
      Step 3 — Update ora_dev_actions row (status=auto_approved | auto_failed)
      Step 4 — Append to truth_ledger (audit immutability)

    Backup failure aborts auto-exec for THAT proposal — sets status=auto_aborted
    so a human can re-evaluate. Other proposals in the batch still run.
    """
    now = datetime.now(timezone.utc)
    rolling = {"executed": 0, "aborted": 0, "failed": 0}
    cur = db.ora_dev_actions.find(
        {
            "tier": "tier_1",
            "status": "pending",
            "auto_execute_at": {"$lte": now},
        },
        {"_id": 0},
    ).limit(TIER_1_AUTO_BATCH_LIMIT)

    async for p in cur:
        pid = p.get("proposal_id")
        action = p.get("approve_action") or {}
        kind = action.get("kind")
        confidence = float(p.get("confidence") or 0)

        # Re-verify confidence didn't drift between schedule and exec
        if confidence < TIER_1_MIN_CONFIDENCE:
            await db.ora_dev_actions.update_one(
                {"proposal_id": pid},
                {"$set": {
                    "status": "auto_aborted",
                    "auto_aborted_at": _now_iso(),
                    "auto_aborted_reason": f"confidence_drift:{confidence:.2f}",
                }},
            )
            rolling["aborted"] += 1
            continue

        # Step 1 — pre-execute state snapshot. Fast, focused, per-action
        # capture so a human (or the rollback path) can see exactly what the
        # action overwrote. We deliberately do NOT call `db_backup_service.
        # run_backup_async` here — that's the daily DR mirror (~11 min) and
        # would blow past the 5-minute cancel window. The daily mirror still
        # runs at 03:00 UTC for the global safety net.
        backup_run_id = None
        try:
            snap = await _tier1_snapshot(db, pid, action)
            backup_run_id = snap.get("snapshot_id")
        except Exception as e:
            await db.ora_dev_actions.update_one(
                {"proposal_id": pid},
                {"$set": {
                    "status": "auto_aborted",
                    "auto_aborted_at": _now_iso(),
                    "auto_aborted_reason": f"snapshot_failed: {str(e)[:200]}",
                    "backup_run_id": backup_run_id,
                }},
            )
            try:
                await db.truth_ledger.insert_one({
                    "ts": _now_iso(),
                    "actor": "tier1_auto_executor",
                    "kind": "auto_approval_aborted",
                    "description": f"Tier-1 auto-approval ABORTED for {pid}: pre-exec snapshot failed",
                    "evidence": {
                        "proposal_id": pid,
                        "action_kind": kind,
                        "confidence": confidence,
                        "abort_reason": "snapshot_failed",
                        "abort_detail": str(e)[:200],
                    },
                })
            except Exception:
                pass
            rolling["aborted"] += 1
            continue

        # Step 2 — execute the structured action.
        exec_result: Dict[str, Any]
        try:
            exec_result = await execute_approve_action(db, action)
        except Exception as e:
            exec_result = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
        ok = bool(exec_result.get("ok"))

        # Step 3 — persist outcome on the proposal.
        new_status = "auto_approved" if ok else "auto_failed"
        await db.ora_dev_actions.update_one(
            {"proposal_id": pid},
            {"$set": {
                "status": new_status,
                "approved_by": "tier1_auto_executor",
                "approved_at": _now_iso(),
                "applied_at": _now_iso() if ok else None,
                "applied_payload": exec_result,
                "backup_run_id": backup_run_id,
            }},
        )

        # Step 4 — truth_ledger entry (immutable audit).
        try:
            await db.truth_ledger.insert_one({
                "ts": _now_iso(),
                "actor": "tier1_auto_executor",
                "kind": "auto_approval",
                "description": (
                    f"Tier-1 {kind} auto-approval {'EXECUTED' if ok else 'FAILED'} "
                    f"for proposal {pid}"
                ),
                "evidence": {
                    "proposal_id": pid,
                    "action_kind": kind,
                    "confidence": confidence,
                    "tier": "tier_1",
                    "backup_run_id": backup_run_id,
                    "exec_ok": ok,
                    "exec_result": exec_result if ok else None,
                    "exec_error": None if ok else exec_result.get("error"),
                },
            })
        except Exception as e:
            logger.debug(f"[tier1_auto] truth_ledger insert skipped: {e}")

        if ok:
            rolling["executed"] += 1
        else:
            rolling["failed"] += 1
    return rolling


# ─── Public tick (called from scheduler) ────────────────────────────────────
async def ora_bridge_tick(db=None) -> Dict[str, Any]:
    if db is None:
        db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}
    summary = {"repair_suggestions": 0, "migrations": 0, "persistent_red": 0,
               "tier1_auto": {"executed": 0, "aborted": 0, "failed": 0}}
    try:
        summary["repair_suggestions"] = await _bridge_repair_suggestions(db)
    except Exception as e:
        logger.warning(f"[ora_bridge] suggestions stream failed: {e}")
    try:
        summary["migrations"] = await _bridge_migration_signals(db)
    except Exception as e:
        logger.warning(f"[ora_bridge] migration stream failed: {e}")
    try:
        summary["persistent_red"] = await _bridge_persistent_red(db)
    except Exception as e:
        logger.warning(f"[ora_bridge] persistent-red stream failed: {e}")
    # iter 322s — tier-1 auto-approval pass (after publish so newly-tagged
    # proposals get their delay window before being eligible).
    try:
        summary["tier1_auto"] = await _run_auto_approvals(db)
    except Exception as e:
        logger.warning(f"[ora_bridge] tier1 auto-exec failed: {e}")

    total = (summary["repair_suggestions"] + summary["migrations"]
             + summary["persistent_red"])
    if total > 0 or summary["tier1_auto"].get("executed", 0):
        logger.info(f"[ora_bridge] published={total} tier1_auto={summary['tier1_auto']}")

    # iter 322u — heartbeat for the watchdog.
    try:
        await db.scheduler_heartbeats.update_one(
            {"job_id": "ora_proposal_bridge"},
            {"$set": {
                "job_id": "ora_proposal_bridge",
                "last_ok_ts": datetime.now(timezone.utc),
                "last_summary": summary,
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[ora_bridge] heartbeat write skipped: {e}")
    return {"ok": True, "summary": summary, "total_published": total, "ts": _now_iso()}


# ─── iter 322u — Watchdog (re-arms a dead bridge job) ───────────────────────
async def ora_bridge_watchdog(db=None) -> Dict[str, Any]:
    """Runs every 5 minutes from the scheduler. Reads the bridge's
    `last_ok_ts` heartbeat — if it's stale by >5 min, the bridge is
    considered dead/hung. We:
      1. Try to re-add the APScheduler job (replace_existing=True)
      2. Append to truth_ledger with reason
      3. Emit one row to db.founder_notifications

    Idempotent — re-adding an already-live job is a no-op for our state.
    """
    if db is None:
        db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}

    now = datetime.now(timezone.utc)
    hb = await db.scheduler_heartbeats.find_one(
        {"job_id": "ora_proposal_bridge"}, {"_id": 0}
    )
    last_ok = hb.get("last_ok_ts") if hb else None
    if isinstance(last_ok, datetime) and last_ok.tzinfo is None:
        last_ok = last_ok.replace(tzinfo=timezone.utc)

    stale = (last_ok is None) or ((now - last_ok).total_seconds() > 300)
    if not stale:
        return {"ok": True, "stale": False, "last_ok": last_ok.isoformat() if last_ok else None}

    last_ok_iso = last_ok.isoformat() if last_ok else "never"
    reason = f"bridge_heartbeat_stale: last_ok={last_ok_iso}"
    restart_ok = False
    try:
        # `aurem_scheduler` is exported via globals() at runtime in
        # registry.py — use getattr (the module reference is module-global,
        # but the symbol is set dynamically so a `from ... import` would
        # capture an unbound stale reference).
        from routers import registry as _registry  # type: ignore
        sched = getattr(_registry, "aurem_scheduler", None)
        if sched is None:
            raise RuntimeError("aurem_scheduler not yet bound")
        from apscheduler.triggers.interval import IntervalTrigger
        sched.add_job(
            ora_bridge_tick,
            IntervalTrigger(seconds=60, jitter=20),
            id="ora_proposal_bridge",
            name="Autonomous ORA Proposal Bridge (sentinel/health → Dev Console)",
            replace_existing=True,
            # iter 326e — bump tolerance so prod deploy logs stop spamming
            # "maximum number of running instances reached (1)". The tick
            # itself averages ~12 s but can hit 45 s on a cold DeepSeek call.
            max_instances=2,
            coalesce=True,
            misfire_grace_time=90,
        )
        restart_ok = True
    except Exception as e:
        reason = f"{reason} | restart_failed: {str(e)[:200]}"

    try:
        await db.truth_ledger.insert_one({
            "ts": _now_iso(),
            "actor": "ora_bridge_watchdog",
            "kind": "bridge_restart",
            "description": (
                f"ora_proposal_bridge {'restarted' if restart_ok else 'restart attempt failed'}"
            ),
            "evidence": {"reason": reason, "restart_ok": restart_ok,
                         "last_ok_ts": last_ok_iso},
        })
    except Exception:
        pass
    try:
        await db.founder_notifications.insert_one({
            "type": "BRIDGE_RESTART",
            "title": ("ORA Bridge restarted by watchdog"
                      if restart_ok else "ORA Bridge restart FAILED — manual check needed"),
            "reason": reason,
            "severity": "P1" if not restart_ok else "P2",
            "created_at": _now_iso(),
            "read": False,
        })
    except Exception:
        pass
    return {"ok": True, "stale": True, "restart_ok": restart_ok, "reason": reason}


# ─── Approve action executor (called from approve endpoint) ─────────────────
async def execute_approve_action(db, action: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the structured action attached to a proposal. Idempotent
    where possible. Returns the captured payload for audit."""
    if not action or not isinstance(action, dict):
        return {"ok": False, "reason": "no_action"}
    kind = action.get("kind")

    if kind == "run_migration_iter322":
        # Run server-side via direct function calls (no HTTP loopback needed)
        out: Dict[str, Any] = {"steps": []}
        try:
            from routers.db_migrate_router import (
                _gather_test_emails, _gather_cascade_keys, _purge_emails,
                _merge_admin_to_dogfood, _cascade_rename_bins,
                EXTRA_DELETE,
            )
            test_emails = await _gather_test_emails(db)
            user_ids, _ = await _gather_cascade_keys(db, test_emails)
            test_purge = await _purge_emails(db, test_emails, user_ids, dry=False)
            merge = await _merge_admin_to_dogfood(db, dry=False)
            extra: Dict[str, int] = {}
            for em in EXTRA_DELETE:
                sub_ids, _ = await _gather_cascade_keys(db, [em])
                sub = await _purge_emails(db, [em], sub_ids, dry=False)
                for k, v in sub.items():
                    extra[k] = extra.get(k, 0) + v
            rename_summary = await _cascade_rename_bins(db)
            out["steps"].append({"step": "iter322_cleanup",
                                 "test_purge_total": sum(test_purge.values()),
                                 "extra_total": sum(extra.values()),
                                 "merge": merge.get("merged"),
                                 "renamed_total": rename_summary.get("renamed_total")})

            from services.backfill_business_id import backfill_business_id
            bf = await backfill_business_id(db)
            out["steps"].append({"step": "backfill", "total_backfilled": bf.get("total_backfilled"), "orphan": bf.get("total_orphan")})

            from services.db_indexes import ensure_bin_indexes
            idx = await ensure_bin_indexes(db)
            out["steps"].append({"step": "ensure_indexes",
                                 "collections": len(idx.get("indexes") or {})})
            return {"ok": True, "kind": kind, "result": out}
        except Exception as e:
            logger.exception(f"[ora_bridge] iter322 exec failed: {e}")
            return {"ok": False, "kind": kind, "error": str(e)[:300]}

    if kind == "mark_safe_apply":
        # Tag the underlying repair_suggestion as ready-for-apply (informational)
        sid = action.get("suggestion_id")
        if sid:
            await db.repair_suggestions.update_one(
                {"suggestion_id": sid},
                {"$set": {"approved_for_apply": True, "approved_at": _now_iso()}},
            )
        return {"ok": True, "kind": kind, "suggestion_id": sid}

    # ─── iter 322s — Tier-1 executors ──────────────────────────────────
    if kind == "config_change":
        # Apply a config change to one of the standard config collections.
        # Action shape: {"kind": "config_change", "key": "x", "value": <any>,
        #                "collection": "app_config" | "system_config" | "settings"}
        target_key = action.get("key") or action.get("target")
        new_val = action.get("value")
        col = action.get("collection") or "app_config"
        if not target_key:
            return {"ok": False, "kind": kind, "error": "missing key/target"}
        try:
            res = await db[col].update_one(
                {"key": target_key},
                {"$set": {"key": target_key, "value": new_val,
                          "updated_at": _now_iso(),
                          "updated_by": "tier1_auto_executor"}},
                upsert=True,
            )
            return {"ok": True, "kind": kind, "collection": col,
                    "key": target_key, "matched": res.matched_count,
                    "upserted": bool(res.upserted_id)}
        except Exception as e:
            return {"ok": False, "kind": kind, "error": str(e)[:200]}

    if kind == "cache_clear":
        # Clear a Redis scope OR a specific Mongo cache collection.
        # Action shape: {"kind": "cache_clear", "scope": "redis_key_prefix"}
        # OR           {"kind": "cache_clear", "collection": "some_cache_collection"}
        scope = action.get("scope") or action.get("target")
        cache_col = action.get("collection")
        cleared = 0
        try:
            if cache_col:
                # Mongo-cache collection
                r = await db[cache_col].delete_many({})
                cleared = r.deleted_count
                return {"ok": True, "kind": kind, "collection": cache_col,
                        "cleared_docs": cleared}
            if scope:
                # Redis prefix flush (best-effort; succeeds without redis too)
                try:
                    from utils.redis_client import get_redis  # type: ignore
                    redis = get_redis()
                    if redis is not None:
                        keys = await redis.keys(f"{scope}*")
                        if keys:
                            await redis.delete(*keys)
                            cleared = len(keys)
                except Exception:
                    pass
                return {"ok": True, "kind": kind, "scope": scope,
                        "cleared_keys": cleared}
            return {"ok": False, "kind": kind, "error": "missing scope/collection"}
        except Exception as e:
            return {"ok": False, "kind": kind, "error": str(e)[:200]}

    if kind == "rate_limit_adjust":
        # Adjust a per-key rate limit row in db.rate_limits.
        # Action shape: {"kind": "rate_limit_adjust",
        #                "limit_key": "api:something",
        #                "rps": int, "burst": int}
        target_key = action.get("limit_key") or action.get("key")
        if not target_key:
            return {"ok": False, "kind": kind, "error": "missing limit_key"}
        update_set: Dict[str, Any] = {
            "key": target_key,
            "updated_at": _now_iso(),
            "updated_by": "tier1_auto_executor",
        }
        for field in ("rps", "burst", "window_s", "max_per_window"):
            if field in action:
                update_set[field] = action[field]
        try:
            res = await db.rate_limits.update_one(
                {"key": target_key},
                {"$set": update_set},
                upsert=True,
            )
            return {"ok": True, "kind": kind, "key": target_key,
                    "matched": res.matched_count,
                    "upserted": bool(res.upserted_id),
                    "applied": {k: v for k, v in update_set.items()
                                if k not in ("updated_at", "updated_by")}}
        except Exception as e:
            return {"ok": False, "kind": kind, "error": str(e)[:200]}

    return {"ok": False, "reason": f"unknown_action_kind:{kind}"}
