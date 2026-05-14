"""
autonomous_stack.py — Façade for the 11 autonomous components.

Single read-only aggregator that the /admin/brain page calls. Avoids
fan-out from the frontend (one round-trip vs. 11) and keeps the page's
shape decoupled from internal collection schemas.

Component map (in pipeline order, signal → diagnose → repair → audit):
  1.  client_errors             — raw signal ingest from Sentinel
  2.  sentinel_repair_loop      — autonomous loop (60s scheduler)
  3.  sentinel_ai_diagnose      — Claude/triage layer (iter 322q)
  4.  llm_response_cache        — Claude token cache (iter 322q)
  5.  llm_costs                 — gateway-tracked spend
  6.  council_decisions_detailed — voter-level decisions
  7.  council_decisions         — legacy aggregate (29K+)
  8.  ora_proposal_bridge       — bridges suggestion → admin Dev Console
  9.  repair_suggestions        — Claude diagnoses (pending review)
  10. ora_dev_actions           — Dev Console proposals (await human approve)
  11. ora_brain_thoughts        — learning corpus

NO writes. NO LLM calls. Just reads + counts.
"""
from __future__ import annotations

import re as _re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _safe_count(db, name: str, query: Dict[str, Any] | None = None) -> int:
    try:
        return await db[name].count_documents(query or {})
    except Exception:
        return -1


async def get_overview(db) -> Dict[str, Any]:
    """High-level counts + 24h rollups for the 11 components."""
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    cutoff_24h = _now() - timedelta(hours=24)
    cutoff_iso = cutoff_24h.isoformat()

    # Collection-level totals
    totals: Dict[str, int] = {}
    last24h: Dict[str, int] = {}
    for name, time_field in [
        ("client_errors", "ts"),
        ("repair_suggestions", "created_at"),
        ("council_decisions_detailed", "ts"),
        ("council_decisions", "ts"),
        ("ora_brain_thoughts", "ts"),
        ("ora_dev_actions", "created_at"),
        ("llm_costs", "ts"),
        ("llm_response_cache", "created_at"),
        ("agent_actions", "ts"),
    ]:
        totals[name] = await _safe_count(db, name)
        # 24h rollup — datetime query first; only fall back to ISO-string
        # query if the datetime query actually FAILED (-1). Previous logic
        # also fell back on a legitimate 0, wasted a query, and `max(-1,-1,0)`
        # silently turned a double-failure into a clean zero.
        n_dt = await _safe_count(db, name, {time_field: {"$gte": cutoff_24h}})
        if n_dt == -1:
            n_iso = await _safe_count(db, name, {time_field: {"$gte": cutoff_iso}})
            last24h[name] = n_iso if n_iso >= 0 else -1
        else:
            last24h[name] = n_dt

    # Diagnose-path breakdown — proves the iter 322q optimization is live
    diag_paths: Dict[str, int] = {}
    try:
        async for r in db.repair_suggestions.aggregate([
            {"$group": {"_id": "$diagnose_path", "n": {"$sum": 1}}},
        ]):
            key = r["_id"] or "unknown"
            diag_paths[key] = r["n"]
    except Exception:
        diag_paths = {}

    # Council verdict split
    verdicts: Dict[str, int] = {}
    try:
        async for r in db.council_decisions_detailed.aggregate([
            {"$group": {"_id": "$verdict", "n": {"$sum": 1}}},
        ]):
            verdicts[r["_id"] or "unknown"] = r["n"]
    except Exception:
        verdicts = {}

    # Pending Dev Console proposals
    pending_dev = await _safe_count(db, "ora_dev_actions", {"status": "pending"})

    return {
        "ok": True,
        "ts": _now().isoformat(),
        "components": {
            "1_client_errors":             {"total": totals["client_errors"],          "h24": last24h["client_errors"]},
            "2_sentinel_repair_loop":      {"running": True, "interval_s": 60},
            "3_sentinel_ai_diagnose":      {"diag_path_breakdown": diag_paths},
            "4_llm_response_cache":        {"total": totals["llm_response_cache"],     "h24": last24h["llm_response_cache"]},
            "5_llm_costs":                 {"total": totals["llm_costs"],              "h24": last24h["llm_costs"]},
            "6_council_detailed":          {"total": totals["council_decisions_detailed"], "h24": last24h["council_decisions_detailed"], "verdicts": verdicts},
            "7_council_legacy":            {"total": totals["council_decisions"],      "h24": last24h["council_decisions"]},
            "8_ora_proposal_bridge":       {"pending_dev_actions": pending_dev},
            "9_repair_suggestions":        {"total": totals["repair_suggestions"],     "h24": last24h["repair_suggestions"]},
            "10_ora_dev_actions":          {"total": totals["ora_dev_actions"],        "h24": last24h["ora_dev_actions"], "pending": pending_dev},
            "11_ora_brain_thoughts":       {"total": totals["ora_brain_thoughts"],     "h24": last24h["ora_brain_thoughts"]},
        },
        "agent_actions_24h": last24h["agent_actions"],
    }


async def get_pipeline_flow(db, limit: int = 10) -> Dict[str, Any]:
    """Recent flow tracing — most recent client_error → suggestion → council
    → dev_action chain. For the timeline panel."""
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    rows: List[Dict[str, Any]] = []
    cur = db.repair_suggestions.find(
        {}, {"_id": 0, "suggestion_id": 1, "error_id": 1, "source": 1,
             "source_signature": 1, "created_at": 1, "status": 1, "severity": 1,
             "diagnose_path": 1, "triage_category": 1, "confidence": 1,
             "root_cause": 1, "error_snapshot": 1},
    ).sort("created_at", -1).limit(limit)
    async for r in cur:
        # Joins (best-effort, no _id leak). Bind the council decision to
        # THIS suggestion via its error_id / source_signature instead of
        # the previous loose regex which just grabbed the most recent
        # council row regardless of which error it belonged to.
        sig = r.get("source_signature")
        err_id = r.get("error_id")
        created_at = r.get("created_at")
        council_row = None
        dev_row = None
        _council_query: Dict[str, Any] = {"action": "sentinel_ai_diagnose"}
        _ored = []
        if err_id:
            _ored.append({"error_id": err_id})
            _ored.append({"payload.error_id": err_id})
        if sig:
            _ored.append({"source_signature": sig})
            _ored.append({"payload.source_signature": sig})
        if _ored:
            _council_query["$or"] = _ored
            # Only consider decisions made AT or AFTER the suggestion existed.
            if created_at is not None:
                _council_query["ts"] = {"$gte": created_at}
            council_row = await db.council_decisions_detailed.find_one(
                _council_query,
                {"_id": 0, "verdict": 1, "votes": 1, "confidence": 1, "ts": 1},
                sort=[("ts", -1)],
            )
        sug_id = r.get("suggestion_id")
        if sug_id:
            dev_row = await db.ora_dev_actions.find_one(
                {"suggestion_id": sug_id},
                {"_id": 0, "action_id": 1, "status": 1, "created_at": 1},
            )
        rows.append({
            "suggestion": r,
            "council": council_row,
            "dev_action": dev_row,
        })
    return {"ok": True, "count": len(rows), "flow": rows}


async def get_recent_decisions(
    db, limit: int = 50, action_filter: str | None = None,
    verdict_filter: str | None = None,
) -> Dict[str, Any]:
    """Recent council_decisions_detailed rows with optional filters."""
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    q: Dict[str, Any] = {}
    if action_filter:
        # Escape regex metacharacters so callers can only do literal-substring
        # (case-insensitive) matches. Without escape an admin-passed `.*`
        # silently widened the filter to ALL rows.
        q["action"] = {"$regex": _re.escape(action_filter), "$options": "i"}
    if verdict_filter:
        q["verdict"] = verdict_filter.upper()

    rows: List[Dict[str, Any]] = []
    cur = db.council_decisions_detailed.find(
        q, {"_id": 0, "action": 1, "requesting_agent": 1, "verdict": 1,
            "votes": 1, "confidence": 1, "rejected_by": 1, "ts": 1},
    ).sort("ts", -1).limit(limit)
    async for r in cur:
        # Coerce datetime → iso for JSON safety
        if isinstance(r.get("ts"), datetime):
            r["ts"] = r["ts"].isoformat()
        rows.append(r)
    return {"ok": True, "count": len(rows), "rows": rows}
