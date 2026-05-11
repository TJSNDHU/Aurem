"""
AUREM Collective Scanner — iter 322ar
========================================
Phase 1 → 6 pipeline for the 25-agent collective:

  1. SCAN        — every agent's health derived from its `scan` recipe
  2. AGGREGATE   — bucket all findings by `subject_agent`
  3. ROOT CAUSE  — for each broken agent, count how many *upstream*
                   agents are also broken; if zero, this agent IS the
                   root cause. Cascade impact = downstream_of(agent).
  4. SUBMIT      — emit one packet per root-cause to the Council via
                   `services.council_deliberate.deliberate()`. Approved
                   packets get written into `ora_dev_actions` (the
                   existing Dev Console queue → Tier-1 auto / Tier-2
                   founder approval).
  5. EXECUTE     — Dev Console picks up `ora_dev_actions` rows; nothing
                   to do here.
  6. VERIFY      — mini-scan re-runs after `verify_delay_minutes`.

The scanner is read-only on the agents' own collections. It NEVER
writes into agent-owned tables; it only writes into:

  collective_scan_buffer   — raw evidence rows (one per (collector, subject))
  collective_scan_results  — aggregated cycle summary (one per scan_id)
  ora_dev_actions          — Tier-1/2 proposals (Council-routed)
  truth_ledger             — final cycle audit row

Run with:
    from services.collective_scanner import run_cycle
    await run_cycle()
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.agent_dependency_map import (
    ALL_AGENTS,
    DEPENDENCY_MAP,
    downstream_of,
)

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    """Wired from registry.py at startup."""
    global _db
    _db = database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────
# PHASE 1 — SCAN every agent
# ─────────────────────────────────────────────────────────────────────

async def _scan_agent(agent: str, spec: Dict) -> Dict[str, Any]:
    """Return a single evidence dict describing this agent's health."""
    scan = spec.get("scan") or ("count", "non_existent", 0)
    kind = scan[0]
    out: Dict[str, Any] = {
        "subject_agent": agent,
        "ts": _utc_now(),
        "evidence_type": "unknown",
        "metric_name": "",
        "metric_value": 0,
        "expected_value": 0,
        "gap": 0,
        "status": "healthy",
        "raw_evidence": {},
    }
    if _db is None:
        out.update(status="critical", evidence_type="db_unavailable")
        return out

    try:
        if kind == "recent":
            _, col, fresh_min = scan
            cutoff = _utc_now() - timedelta(minutes=int(fresh_min))
            n = await _db[col].count_documents({"ts": {"$gte": cutoff}})
            if n == 0:
                # Fallback to `created_at` for collections that use that key.
                n = await _db[col].count_documents({"created_at": {"$gte": cutoff}})
            out["metric_name"] = f"docs_since_{fresh_min}min"
            out["metric_value"] = n
            out["expected_value"] = 1
            out["gap"] = max(0, 1 - n)
            out["evidence_type"] = "recency"
            out["status"] = "healthy" if n > 0 else "warning"
            # If the agent has been silent >2x its fresh window, escalate
            if n == 0:
                old_cutoff = _utc_now() - timedelta(minutes=int(fresh_min) * 2)
                older = await _db[col].count_documents({"ts": {"$gte": old_cutoff}})
                if older == 0:
                    older = await _db[col].count_documents({"created_at": {"$gte": old_cutoff}})
                if older == 0:
                    out["status"] = "critical"
                    out["evidence_type"] = "no_runs"

        elif kind == "count":
            _, col, min_docs = scan
            n = await _db[col].estimated_document_count()
            out["metric_name"] = "total_docs"
            out["metric_value"] = n
            out["expected_value"] = int(min_docs)
            out["gap"] = max(0, int(min_docs) - n)
            out["evidence_type"] = "missing_data" if n < int(min_docs) else "ok"
            out["status"] = "healthy" if n >= int(min_docs) else "warning"

        elif kind == "scheduler":
            # Sentinel-style: probe the agent_heartbeats row keyed by job_id
            _, job_id, max_late = scan
            row = await _db.agent_heartbeats.find_one(
                {"agent_id": job_id}, {"_id": 0, "last_run": 1}
            )
            last = row.get("last_run") if row else None
            if not last:
                out["status"] = "critical"
                out["evidence_type"] = "scheduler_silent"
            else:
                if isinstance(last, str):
                    last = datetime.fromisoformat(last.replace("Z", "+00:00"))
                lag = (_utc_now() - last).total_seconds()
                out["metric_name"] = "lag_seconds"
                out["metric_value"] = int(lag)
                out["expected_value"] = int(max_late)
                out["gap"] = max(0, int(lag) - int(max_late))
                out["status"] = "healthy" if lag <= max_late else "warning"

    except Exception as e:
        logger.warning(f"[collective-scan] {agent}: {e}")
        out["status"] = "warning"
        out["evidence_type"] = "scan_error"
        out["raw_evidence"]["error"] = str(e)[:200]

    return out


async def _scan_all() -> List[Dict[str, Any]]:
    """Phase 1 — all 25 agents probed in parallel."""
    tasks = [_scan_agent(name, spec) for name, spec in DEPENDENCY_MAP.items()]
    return await asyncio.gather(*tasks)


# ─────────────────────────────────────────────────────────────────────
# PHASE 2/3 — AGGREGATE + find root causes
# ─────────────────────────────────────────────────────────────────────

def _classify(findings: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    critical, warning, healthy = [], [], []
    for f in findings:
        s = f.get("status", "healthy")
        a = f.get("subject_agent")
        if s == "critical":
            critical.append(a)
        elif s == "warning":
            warning.append(a)
        else:
            healthy.append(a)
    return {"critical": critical, "warning": warning, "healthy": healthy}


def _build_fix_priority(broken: List[str]) -> List[Dict[str, Any]]:
    """Order broken agents by how many other broken agents they unblock.
    True root causes (zero broken upstream) come first; pure leaves last."""
    broken_set = set(broken)
    scored: List[Dict[str, Any]] = []
    for a in broken:
        ups = DEPENDENCY_MAP[a].get("depends_on", [])
        broken_upstream = [u for u in ups if u in broken_set]
        dependents = downstream_of(a)
        cascade = [d for d in dependents if d in broken_set]
        scored.append({
            "agent": a,
            "is_root_cause": len(broken_upstream) == 0,
            "broken_upstream": broken_upstream,
            "fixes_these_too": cascade,
            "cascade_size": len(cascade),
        })
    # Root causes first, then by cascade size desc, then alpha
    scored.sort(key=lambda x: (not x["is_root_cause"], -x["cascade_size"], x["agent"]))
    for i, row in enumerate(scored, start=1):
        row["order"] = i
        row["reason"] = (
            "root cause" if row["is_root_cause"]
            else f"downstream of {','.join(row['broken_upstream'])}"
        )
    return scored


# ─────────────────────────────────────────────────────────────────────
# PHASE 4 — submit to Council + Dev Console
# ─────────────────────────────────────────────────────────────────────

async def _route_to_council_and_devconsole(
    scan_id: str, fix_priority: List[Dict[str, Any]],
    findings_by_agent: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """For each root-cause-bearing fix step, ask Council for a verdict;
    on APPROVE write a Dev Console proposal row."""
    if _db is None:
        return {"approved": 0, "rejected": 0, "errors": 1}
    approved = rejected = errors = 0
    pending: List[Dict[str, Any]] = []
    try:
        from services.council_deliberate import deliberate
    except Exception as e:
        logger.error(f"[collective-scan] council import failed: {e}")
        return {"approved": 0, "rejected": 0, "errors": 1, "reason": str(e)[:100]}

    for step in fix_priority:
        if not step["is_root_cause"]:
            # Skip downstream items — root fix should cascade
            continue
        agent = step["agent"]
        evidence = findings_by_agent.get(agent, {})
        payload = {
            "scan_id": scan_id,
            "agent": agent,
            "cascade_size": step["cascade_size"],
            "fixes_these_too": step["fixes_these_too"],
            "evidence": evidence,
        }
        try:
            verdict = await deliberate(
                action="collective_scan_fix",
                agent=agent,
                payload=payload,
                required=["qa"],
                advisory=["security"],
            )
        except Exception as e:
            logger.warning(f"[collective-scan] council deliberate({agent}): {e}")
            errors += 1
            continue
        if verdict.get("verdict") == "APPROVED":
            approved += 1
            await _publish_dev_console_proposal(scan_id, agent, step, evidence)
        else:
            rejected += 1
            pending.append({"agent": agent, "verdict": verdict.get("verdict")})

    return {"approved": approved, "rejected": rejected, "errors": errors, "pending": pending}


async def _publish_dev_console_proposal(
    scan_id: str, agent: str, step: Dict[str, Any], evidence: Dict[str, Any],
) -> None:
    """Build a fix proposal via the cost-tier router (ORA → Sovereign →
    OpenRouter → Emergent) and persist it as an `ora_dev_actions` row.
    Falls back to the old plain message if the fixer is unavailable."""
    try:
        from services.emergent_code_fixer import request_code_fix
        issue = {
            "agent": agent,
            "subject_agent": agent,
            "evidence_type": evidence.get("evidence_type"),
            "metric_name": evidence.get("metric_name"),
            "metric_value": evidence.get("metric_value"),
            "expected_value": evidence.get("expected_value"),
            "gap": evidence.get("gap"),
            "status": evidence.get("status"),
            "scan_id": scan_id,
            "cascade_size": step.get("cascade_size", 0),
            "fixes_these_too": step.get("fixes_these_too", []),
        }
        await request_code_fix(issue)
        return
    except Exception as e:
        logger.warning(f"[collective-scan] cost-tier fixer failed, falling back: {e}")

    # Plain fallback (legacy behaviour)
    cascade = step.get("fixes_these_too", [])
    cascade_txt = f" (cascade-fixes: {', '.join(cascade)})" if cascade else ""
    proposal = {
        "scan_id": scan_id,
        "action_id": str(uuid.uuid4()),
        "kind": "collective_scan_fix",
        "agent": agent,
        "tier": "tier_2",
        "status": "pending",
        "title": f"Fix {agent} — {evidence.get('evidence_type', 'unknown')}",
        "message_plain": (
            f"Collective scan ne {agent} ko {evidence.get('status','?')} "
            f"detect kiya. Reason: {evidence.get('evidence_type','unknown')} "
            f"(metric {evidence.get('metric_name','?')}={evidence.get('metric_value','?')}, "
            f"expected ≥ {evidence.get('expected_value','?')})."
            f"{cascade_txt}"
        ),
        "evidence": evidence,
        "fixes_these_too": cascade,
        "ts": _utc_now(),
    }
    try:
        await _db.ora_dev_actions.insert_one(proposal)
    except Exception as e:
        logger.warning(f"[collective-scan] fallback proposal write failed: {e}")


# ─────────────────────────────────────────────────────────────────────
# CYCLE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

async def run_cycle(triggered_by: str = "scheduler") -> Dict[str, Any]:
    """Run a single Phase 1–6 cycle. Idempotent — every cycle gets a
    unique `scan_id`. Returns a JSON-serialisable summary."""
    if _db is None:
        return {"ok": False, "reason": "db_unavailable"}

    scan_id = str(uuid.uuid4())
    started_at = _utc_now()

    # Phase 1
    findings = await _scan_all()
    findings_by_agent = {f["subject_agent"]: f for f in findings}
    # Persist raw rows (best-effort, non-blocking errors).
    try:
        await _db.collective_scan_buffer.insert_many(
            [{**f, "scan_id": scan_id} for f in findings],
            ordered=False,
        )
    except Exception as e:
        logger.warning(f"[collective-scan] buffer write: {e}")

    # Phase 2 — classify
    buckets = _classify(findings)
    broken = buckets["critical"] + buckets["warning"]

    # Phase 3 — root cause + fix priority
    fix_priority = _build_fix_priority(broken) if broken else []

    # Phase 4 — Council + Dev Console
    routing = (
        await _route_to_council_and_devconsole(scan_id, fix_priority, findings_by_agent)
        if fix_priority else {"approved": 0, "rejected": 0, "errors": 0}
    )

    finished_at = _utc_now()
    summary = {
        "scan_id": scan_id,
        "triggered_by": triggered_by,
        "agents_scanned": len(findings),
        "buckets": buckets,
        "fix_priority": fix_priority,
        "routing": routing,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": (finished_at - started_at).total_seconds(),
    }

    # Phase 6 — persist + truth ledger
    try:
        await _db.collective_scan_results.insert_one(summary)
    except Exception as e:
        logger.warning(f"[collective-scan] result write: {e}")
    try:
        await _db.truth_ledger.insert_one({
            "kind": "collective_scan_complete",
            "scan_id": scan_id,
            "agents_scanned": len(findings),
            "critical": len(buckets["critical"]),
            "warning": len(buckets["warning"]),
            "healthy": len(buckets["healthy"]),
            "approved_fixes": routing.get("approved", 0),
            "rejected_fixes": routing.get("rejected", 0),
            "ts": finished_at,
        })
    except Exception:
        pass

    logger.info(
        f"[collective-scan] cycle {scan_id[:8]} done: "
        f"{len(buckets['critical'])} critical, "
        f"{len(buckets['warning'])} warning, "
        f"{len(buckets['healthy'])} healthy, "
        f"approved={routing.get('approved', 0)}, "
        f"rejected={routing.get('rejected', 0)}"
    )
    return summary


async def get_last_result() -> Optional[Dict[str, Any]]:
    if _db is None:
        return None
    doc = await _db.collective_scan_results.find_one(
        {}, {"_id": 0}, sort=[("finished_at", -1)],
    )
    return doc


async def get_recent_cycles(limit: int = 10) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    cur = _db.collective_scan_results.find({}, {"_id": 0}).sort("finished_at", -1).limit(int(limit))
    return await cur.to_list(int(limit))
