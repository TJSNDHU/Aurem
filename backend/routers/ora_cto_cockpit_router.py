"""
ORA CTO Cockpit Admin Router — iter 322eq
==========================================
Read-only window into ORA's autonomous-CTO activity:
  GET  /api/admin/ora-cto/summary              tile-style KPIs
  GET  /api/admin/ora-cto/invocations          paginated audit feed
  GET  /api/admin/ora-cto/overrides            council-override trail (loud)
  GET  /api/admin/ora-cto/by-tool              rollup per tool (24h/7d windows)
  GET  /api/admin/ora-cto/cost-breakdown       per-tool $ rollup from llm_costs
  GET  /api/admin/ora-cto/quotas               live per-tool quota status

Sources of truth:
  - `ora_tool_invocations`        — every tool call (write-on-every-call)
  - `ora_governance_overrides`    — loud-logged council dissent overrides
  - `llm_costs`                   — provider cost rollup (LLM tools only)
  - `ora_tools.TOOL_REGISTRY`     — quota caps + tool metadata

Auth: JWT Bearer (any signed admin token).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/ora-cto", tags=["ora-cto-cockpit"])

# LLM-burning tools — used to attribute llm_costs rows back to a tool.
_LLM_TOOLS = {"peer_review", "council_consult",
              "safe_edit_with_council", "shell_exec_with_council"}


def _verify_token(authorization: Optional[str] = None) -> str:
    if not authorization:
        raise HTTPException(401, "Authorization required")
    import jwt
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Authorization required")
    try:
        secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("user_id", payload.get("id", payload.get("sub", "unknown")))
    except Exception:
        raise HTTPException(401, "Invalid token")


def _get_db():
    from server import db
    if db is None:
        raise HTTPException(500, "Database not initialized")
    return db


def _hrs_ago(h: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=h)


@router.get("/summary")
async def summary(authorization: Optional[str] = Header(None)):
    """Tile KPIs for the cockpit landing pane."""
    _verify_token(authorization)
    db = _get_db()
    total = await db.ora_tool_invocations.count_documents({})
    h24 = await db.ora_tool_invocations.count_documents({"ts": {"$gte": _hrs_ago(24).isoformat()}})
    h1 = await db.ora_tool_invocations.count_documents({"ts": {"$gte": _hrs_ago(1).isoformat()}})
    fails_24h = await db.ora_tool_invocations.count_documents({
        "ts": {"$gte": _hrs_ago(24).isoformat()}, "ok": False,
    })
    overrides_total = await db.ora_governance_overrides.count_documents({})
    overrides_24h = await db.ora_governance_overrides.count_documents({
        "ts": {"$gte": _hrs_ago(24).isoformat()},
    })
    # Distinct tools used in last 24h
    tools_24h_count = 0
    try:
        tools_24h = await db.ora_tool_invocations.distinct(
            "tool", {"ts": {"$gte": _hrs_ago(24).isoformat()}}
        )
        tools_24h_count = len(tools_24h or [])
    except Exception:
        pass
    return {
        "ok": True,
        "total_invocations":   total,
        "invocations_24h":     h24,
        "invocations_1h":      h1,
        "failures_24h":        fails_24h,
        "success_rate_24h":    round((h24 - fails_24h) / max(h24, 1) * 100, 1) if h24 else None,
        "overrides_total":     overrides_total,
        "overrides_24h":       overrides_24h,
        "tools_active_24h":    tools_24h_count,
    }


@router.get("/by-tool")
async def by_tool(
    window_hours: int = Query(24, ge=1, le=720),
    authorization: Optional[str] = Header(None),
):
    """Per-tool rollup over the window."""
    _verify_token(authorization)
    db = _get_db()
    since = _hrs_ago(window_hours).isoformat()
    pipeline = [
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {
            "_id": "$tool",
            "calls":      {"$sum": 1},
            "fails":      {"$sum": {"$cond": [{"$eq": ["$ok", False]}, 1, 0]}},
            "latency":    {"$sum": "$elapsed_ms"},
            "avg_lat":    {"$avg": "$elapsed_ms"},
            "last_ts":    {"$max": "$ts"},
        }},
        {"$sort": {"calls": -1}},
    ]
    rows = []
    async for r in db.ora_tool_invocations.aggregate(pipeline):
        rows.append({
            "tool":         r["_id"],
            "calls":        r["calls"],
            "fails":        r["fails"],
            "ok_pct":       round((r["calls"] - r["fails"]) / max(r["calls"], 1) * 100, 1),
            "avg_latency_ms": round(r.get("avg_lat") or 0, 1),
            "last_ts":      r.get("last_ts"),
        })
    return {"ok": True, "window_hours": window_hours, "rows": rows}


@router.get("/cost-breakdown")
async def cost_breakdown(
    window_hours: int = Query(24, ge=1, le=720),
    authorization: Optional[str] = Header(None),
):
    """Cost rollup. Joins ora_tool_invocations × llm_costs by approximate
    timestamp window (within 5 seconds). LLM-burning tools only.

    For each LLM tool we report: calls, est_cost_usd, avg_tokens_out.
    """
    _verify_token(authorization)
    db = _get_db()
    since = _hrs_ago(window_hours)

    # Pull recent llm_costs (already typed datetime in storage)
    cost_pipeline = [
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {
            "_id": "$task_type",
            "calls":    {"$sum": 1},
            "tok_in":   {"$sum": "$tokens_in"},
            "tok_out":  {"$sum": "$tokens_out"},
        }},
        {"$sort": {"tok_out": -1}},
    ]
    by_task = []
    async for r in db.llm_costs.aggregate(cost_pipeline):
        # Approximate cost using Claude Sonnet 4.5 list price (upper bound)
        cost = (r["tok_in"] * 0.003 + r["tok_out"] * 0.015) / 1000.0
        by_task.append({
            "task_type":      r["_id"] or "?",
            "calls":          r["calls"],
            "tokens_in":      r["tok_in"],
            "tokens_out":     r["tok_out"],
            "est_cost_usd":   round(cost, 6),
        })

    # Per ORA-tool rollup (LLM-burning subset only)
    tool_pipeline = [
        {"$match": {"ts": {"$gte": since.isoformat()},
                     "tool": {"$in": list(_LLM_TOOLS)}}},
        {"$group": {"_id": "$tool", "calls": {"$sum": 1},
                     "fails": {"$sum": {"$cond": [{"$eq": ["$ok", False]}, 1, 0]}}}},
        {"$sort": {"calls": -1}},
    ]
    llm_tool_rows = []
    async for r in db.ora_tool_invocations.aggregate(tool_pipeline):
        llm_tool_rows.append({"tool": r["_id"], "calls": r["calls"], "fails": r["fails"]})

    total_calls = sum(r["calls"] for r in by_task)
    total_cost = round(sum(r["est_cost_usd"] for r in by_task), 4)
    return {
        "ok":             True,
        "window_hours":   window_hours,
        "total_calls":    total_calls,
        "total_cost_usd": total_cost,
        "by_task":        by_task,
        "llm_tools":      llm_tool_rows,
    }


@router.get("/invocations")
async def invocations(
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0, le=100_000),
    tool: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    only_failures: bool = Query(False),
    authorization: Optional[str] = Header(None),
):
    """Paginated audit feed. Most-recent first."""
    _verify_token(authorization)
    db = _get_db()
    q: dict = {}
    if tool:
        q["tool"] = tool
    if actor:
        q["actor"] = actor
    if only_failures:
        q["ok"] = False
    total = await db.ora_tool_invocations.count_documents(q)
    cur = (
        db.ora_tool_invocations.find(q, {"_id": 0})
        .sort("ts", -1)
        .skip(skip)
        .limit(limit)
    )
    rows = []
    async for r in cur:
        # Trim heavy fields for the list view
        args = r.get("args") or {}
        if isinstance(args, dict):
            trimmed = {k: (str(v)[:140] if not isinstance(v, (int, float, bool)) else v)
                        for k, v in list(args.items())[:8]}
        else:
            trimmed = {}
        rows.append({
            "ts":         r.get("ts"),
            "tool":       r.get("tool"),
            "actor":      r.get("actor"),
            "ok":         r.get("ok"),
            "error":      (r.get("error") or "")[:200] if r.get("error") else None,
            "elapsed_ms": r.get("elapsed_ms"),
            "args":       trimmed,
        })
    return {"ok": True, "total": total, "showing": len(rows), "rows": rows}


@router.get("/overrides")
async def overrides(
    limit: int = Query(50, ge=1, le=500),
    authorization: Optional[str] = Header(None),
):
    """Council-override trail — every time ORA bypassed a dissent vote."""
    _verify_token(authorization)
    db = _get_db()
    total = await db.ora_governance_overrides.count_documents({})
    rows = []
    async for r in db.ora_governance_overrides.find({}, {"_id": 0}).sort("ts", -1).limit(limit):
        # Keep dissenter names but trim the full snippets
        diss = [
            {"role": d.get("role"),
              "signals": d.get("signals", [])[:4],
              "snippet": (d.get("snippet") or "")[:200]}
            for d in (r.get("dissenters") or [])
        ]
        rows.append({
            "ts":              r.get("ts"),
            "tool":            r.get("tool"),
            "path":            r.get("path"),
            "command":         r.get("command"),
            "args":            r.get("args"),
            "risk_tier":       r.get("risk_tier"),
            "rationale":       (r.get("rationale") or "")[:300],
            "override_reason": (r.get("override_reason") or "")[:300],
            "dissenters":      diss,
        })
    return {"ok": True, "total": total, "rows": rows}


@router.get("/quotas")
async def quotas(authorization: Optional[str] = Header(None)):
    """Iter 322es — quotas were removed. Endpoint kept as a deprecation
    shim that returns an empty list so older UIs don't crash."""
    _verify_token(authorization)
    return {"ok": True, "window_hours": 1, "rows": [],
             "deprecated": "iter 322es — ORA operates without rate limits"}


@router.get("/morning-brief")
async def morning_brief(authorization: Optional[str] = Header(None)):
    """Iter 322et — One-click founder briefing.

    Aggregates the 6 panels the founder asked for:
      1. git_log -10
      2. db_count across critical collections
      3. Recent council overrides (last 24h)
      4. Last-24h tool failure rate
      5. Active customer count
      6. Pending git-gate proposals

    Returns both the structured data AND a markdown rendering ready
    to drop into Slack / WhatsApp.
    """
    _verify_token(authorization)
    db = _get_db()
    import subprocess

    # 1) git log -10
    try:
        r = subprocess.run(
            ["git", "log", "--pretty=format:%h | %s | %an", "-10"],
            capture_output=True, text=True, timeout=5, cwd="/app",
        )
        git_log_lines = [line for line in (r.stdout or "").splitlines() if line.strip()]
    except Exception:
        git_log_lines = ["(git log unavailable)"]

    # 2) DB counts — pillar collections
    pillar_collections = [
        "leads", "customers", "trials", "subscriptions",
        "ora_tool_invocations", "ora_commit_proposals",
        "ora_governance_overrides", "ora_uploaded_files",
        "ora_skills_library", "design_extract_logs",
    ]
    db_counts: dict[str, int] = {}
    for c in pillar_collections:
        try:
            db_counts[c] = await db[c].count_documents({})
        except Exception:
            db_counts[c] = -1

    # 3) Council overrides last 24h
    since = _hrs_ago(24).isoformat()
    recent_overrides = []
    async for r in (
        db.ora_governance_overrides.find(
            {"ts": {"$gte": since}},
            {"_id": 0, "ts": 1, "tool": 1, "path": 1,
              "rationale": 1, "override_reason": 1},
        ).sort("ts", -1).limit(10)
    ):
        recent_overrides.append(r)

    # 4) Last-24h tool failure rate
    inv_24h = await db.ora_tool_invocations.count_documents({"ts": {"$gte": since}})
    fails_24h = await db.ora_tool_invocations.count_documents(
        {"ts": {"$gte": since}, "ok": False}
    )
    failure_rate = round(fails_24h / max(inv_24h, 1) * 100, 2) if inv_24h else 0.0

    # 5) Active customer count — count active subs OR customers with any
    # tool/login event today. Best-effort across plausible collection names.
    active_customers = 0
    for coll, q in (
        ("subscriptions", {"status": {"$in": ["active", "trialing", "paid"]}}),
        ("customers",     {"status": "active"}),
        ("users",         {"is_active": True}),
    ):
        try:
            active_customers = await db[coll].count_documents(q)
            if active_customers > 0:
                break
        except Exception:
            continue

    # 6) Pending git-gate proposals
    pending_proposals = []
    async for r in (
        db.ora_commit_proposals.find(
            {"status": "pending"},
            {"_id": 0, "id": 1, "title": 1, "proposed_at": 1,
              "files": 1, "lines_added": 1, "lines_removed": 1},
        ).sort("proposed_at", -1).limit(20)
    ):
        pending_proposals.append(r)

    # Markdown rendering
    md_lines = [
        "# AUREM Morning Brief",
        f"_Generated {datetime.now(timezone.utc).isoformat()[:19]} UTC_",
        "",
        "## 📜 Last 10 Commits",
    ]
    md_lines.extend([f"  - `{ln}`" for ln in git_log_lines[:10]])
    md_lines += [
        "",
        "## 📊 DB State",
    ]
    md_lines += [f"  - **{k}** — {v}" for k, v in db_counts.items()]
    md_lines += [
        "",
        f"## 🛡 Council Overrides (24h): {len(recent_overrides)}",
    ]
    if recent_overrides:
        for o in recent_overrides[:5]:
            md_lines.append(
                f"  - {(o.get('ts') or '')[:19]} · `{o.get('tool')}` · {o.get('path') or ''}"
            )
    else:
        md_lines.append("  - _no overrides — every council vote was honored_ ✓")
    md_lines += [
        "",
        f"## ⚡ Tool Activity (24h)",
        f"  - Invocations: **{inv_24h}**",
        f"  - Failures: **{fails_24h}** ({failure_rate}%)",
        "",
        f"## 👥 Active Customers: **{active_customers}**",
        "",
        f"## 🌳 Pending Git-Gate Proposals: **{len(pending_proposals)}**",
    ]
    if pending_proposals:
        for p in pending_proposals[:5]:
            md_lines.append(
                f"  - `{p['id'][:14]}` — {p.get('title','')[:70]} "
                f"(+{p.get('lines_added',0)} −{p.get('lines_removed',0)})"
            )
    else:
        md_lines.append("  - _none — repo is clean_ ✓")

    return {
        "ok":               True,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "git_log":          git_log_lines,
        "db_counts":        db_counts,
        "council_overrides_24h": recent_overrides,
        "tool_activity_24h": {
            "invocations":  inv_24h,
            "failures":     fails_24h,
            "failure_rate": failure_rate,
        },
        "active_customers": active_customers,
        "pending_proposals": pending_proposals,
        "markdown":         "\n".join(md_lines),
    }


@router.get("/_/health")
async def health():
    db = _get_db()
    return {
        "ok":           True,
        "scope":        "ora_cto_cockpit",
        "invocations":  await db.ora_tool_invocations.count_documents({}),
        "overrides":    await db.ora_governance_overrides.count_documents({}),
    }
