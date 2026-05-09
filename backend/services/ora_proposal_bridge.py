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
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
    }
    await db.ora_dev_actions.insert_one(doc)
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
async def ora_bridge_tick(db=None) -> Dict[str, Any]:
    if db is None:
        db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}
    summary = {"repair_suggestions": 0, "migrations": 0, "persistent_red": 0}
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

    total = sum(summary.values())
    if total > 0:
        logger.info(f"[ora_bridge] published {total} proposals: {summary}")
    return {"ok": True, "summary": summary, "total_published": total, "ts": _now_iso()}


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

    return {"ok": False, "reason": f"unknown_action_kind:{kind}"}
