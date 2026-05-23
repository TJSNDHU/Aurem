"""
admin_ora_router.py — Admin ORA Q&A across the BIN learning pool.
═══════════════════════════════════════════════════════════════════════════
Admin ORA learns from anonymized telemetry (db.admin_ora_brain) collected by
the service_gate decorator on EVERY paid action across EVERY BIN. Founders
can ask questions and get aggregated insights without seeing per-BIN PII.

  GET  /api/admin/ora/summary            → service usage rollups across all BINs
  POST /api/admin/ora/ask {question}     → Claude-backed Q&A grounded on the
                                           anonymized telemetry pool

Data scope:
  • db.admin_ora_brain rows have bin_hash (irreversible), service, plan, ts
  • NO emails, NO BIN strings, NO user identifiers leave the aggregation
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from middleware.bin_context import get_bin_ctx

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None

# Refusal-over-Hallucination: every Admin ORA answer MUST be grounded in
# real telemetry. If the grounding pool is empty (no service usage in
# window AND no tenant data), we refuse to answer rather than let Claude
# fabricate plausible-sounding numbers. Override via env for emergency
# debugging only — production should keep this hard-on.
GROUNDING_REQUIRED = os.environ.get("ADMIN_ORA_GROUNDING_REQUIRED", "1") == "1"
# Minimum signal floor — at least this many telemetry rows must exist
# before we let Claude attempt a synthesis.
GROUNDING_MIN_EVENTS = int(os.environ.get("ADMIN_ORA_GROUNDING_MIN_EVENTS", "5"))


def set_db(db):
    global _db
    _db = db
    # iter 331c — propagate to metrics module so cockpit tile works.
    try:
        from services import ora_metrics as _M
        _M.set_db(db)
    except Exception:
        pass
    # iter 331c Sprint 6.1 — propagate to consent network module.
    try:
        from services import consent_data_network as _CDN
        _CDN.set_db(db)
    except Exception:
        pass


def _ensure_admin(request: Request):
    ctx = get_bin_ctx(request, required=True)
    if not ctx.is_admin:
        raise HTTPException(403, "admin only")
    return ctx


@router.get("/api/admin/ora/summary")
async def admin_ora_summary(request: Request, hours: int = 168):
    """Aggregate service usage across all BINs over a time window. Default
    168h (7 days). Hash-anonymized — never reveals a specific BIN."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    pipeline = [
        {"$match": {"ts": {"$gte": cutoff}, "type": "service_usage"}},
        {"$group": {
            "_id": {"service": "$service", "plan": "$plan"},
            "events": {"$sum": 1},
            "unique_bins": {"$addToSet": "$bin_hash"},
        }},
        {"$project": {
            "_id": 0,
            "service": "$_id.service",
            "plan": "$_id.plan",
            "events": 1,
            "unique_bins": {"$size": "$unique_bins"},
        }},
        {"$sort": {"events": -1}},
    ]
    rows: List[Dict[str, Any]] = []
    async for r in _db.admin_ora_brain.aggregate(pipeline):
        rows.append(r)
    total_events = sum(r["events"] for r in rows)
    total_bins = await _db.admin_ora_brain.distinct("bin_hash", {"ts": {"$gte": cutoff}})
    return {
        "ok": True,
        "window_hours": hours,
        "total_events": total_events,
        "active_unique_bins": len(total_bins),
        "by_service_plan": rows,
    }


class AskReq(BaseModel):
    question: str


@router.get("/api/admin/ora/email-health")
async def admin_ora_email_health(request: Request, hours: int = 24):
    """iter 326ee — Phase 3 P2.3: Email channel health probe.

    Aggregates email send success/failure across BOTH log sources:
      • db.email_logs        — engine-sent (transactional)
      • db.campaign_leads.outreach_history[type=email] — blast cycles

    Returns total sent / failed / top failure reasons so the daily ORA
    digest can spot regressions like the iter 326x `resend.logs` bug
    BEFORE it burns through a campaign cycle.
    """
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    hours = max(1, min(hours, 720))
    cutoff_dt  = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff_dt.isoformat()

    sent       = 0
    failed     = 0
    err_counts: Dict[str, int] = {}

    # 1) engine logs (email_logs)
    try:
        async for d in _db.email_logs.find(
            {"sent_at": {"$gte": cutoff_iso}},
            {"_id": 0, "success": 1, "error": 1},
        ):
            if d.get("success"):
                sent += 1
            else:
                failed += 1
                err = (d.get("error") or "unknown")[:120]
                err_counts[err] = err_counts.get(err, 0) + 1
    except Exception as e:
        logger.warning(f"[email-health] email_logs scan failed: {e}")

    # 2) blast outreach_history (only email rows)
    try:
        pipeline = [
            {"$unwind": "$outreach_history"},
            {"$match": {
                "outreach_history.type": "email",
                "outreach_history.timestamp": {"$gte": cutoff_iso},
            }},
            {"$group": {
                "_id":  "$outreach_history.status",
                "n":    {"$sum": 1},
                "errs": {"$push": "$outreach_history.error"},
            }},
        ]
        async for r in _db.campaign_leads.aggregate(pipeline):
            status = (r.get("_id") or "").lower()
            n = int(r.get("n") or 0)
            if status == "sent":
                sent += n
            else:
                failed += n
                for e in (r.get("errs") or []):
                    if not e:
                        continue
                    key = str(e)[:120]
                    err_counts[key] = err_counts.get(key, 0) + 1
    except Exception as e:
        logger.warning(f"[email-health] outreach_history scan failed: {e}")

    total = sent + failed
    success_rate = round(sent / total, 4) if total else None
    top_errors = sorted(
        ({"error": k, "count": v} for k, v in err_counts.items()),
        key=lambda r: -r["count"],
    )[:10]

    # Founder-friendly verdict line
    if total == 0:
        verdict = "no email traffic in window"
    elif success_rate is None:
        verdict = "no signal"
    elif success_rate >= 0.95:
        verdict = "healthy"
    elif success_rate >= 0.80:
        verdict = "warning"
    else:
        verdict = "critical"

    return {
        "ok":            True,
        "window_hours":  hours,
        "sent":          sent,
        "failed":        failed,
        "total":         total,
        "success_rate":  success_rate,
        "verdict":       verdict,
        "top_errors":    top_errors,
    }


@router.get("/api/admin/ora/decisions")
async def admin_ora_decisions(
    request: Request,
    days: int = 7,
    limit: int = 50,
    outcome: Optional[str] = None,
    tag: Optional[str] = None,
):
    """iter 326cc — Recent ORA decisions panel for the admin sidebar.

    Returns the last `limit` decisions ORA approved / rejected /
    auto-executed within the last `days`. Optional filters: `outcome`
    (approved | rejected | auto_executed) and `tag` (cors, auth, stripe,
    etc. — auto-extracted at log time).
    """
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    days = max(1, min(days, 90))
    limit = max(1, min(limit, 200))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q: Dict[str, Any] = {"ts": {"$gte": cutoff}}
    if outcome:
        q["outcome"] = outcome
    if tag:
        q["tags"] = tag
    rows: List[Dict[str, Any]] = []
    counts = {"approved": 0, "rejected": 0, "auto_executed": 0, "other": 0}
    cur = (
        _db.ora_decisions
        .find(q, {
            "_id": 1, "ts": 1, "tool": 1, "summary": 1,
            "outcome": 1, "tags": 1, "founder_email": 1,
            "session_id": 1, "args_preview": 1,
        })
        .sort("ts", -1)
        .limit(limit)
    )
    async for d in cur:
        ts = d.get("ts")
        rows.append({
            "id":            d.get("_id"),
            "ts":            ts.isoformat() if isinstance(ts, datetime) else ts,
            "tool":          d.get("tool"),
            "summary":       d.get("summary"),
            "outcome":       d.get("outcome"),
            "tags":          d.get("tags") or [],
            "founder_email": d.get("founder_email"),
            "session_id":    d.get("session_id"),
            "args_preview":  d.get("args_preview"),
        })
        out = d.get("outcome") or "other"
        counts[out if out in counts else "other"] += 1
    return {
        "ok":           True,
        "window_days":  days,
        "count":        len(rows),
        "outcome_counts": counts,
        "decisions":    rows,
    }


@router.get("/api/admin/ora/cost-summary")
async def admin_ora_cost_summary(request: Request, days: int = 7):
    """iter 326w — Daily LLM spend dashboard.

    Returns last N days of ORA chat costs grouped by day and provider,
    plus running totals. Powers the founder's "watchdog before going
    autonomous overnight" need — spot a spend spike before it hits the bill.
    """
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    days = max(1, min(days, 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {"ts": {"$gte": cutoff}}},
        {"$group": {
            "_id": {"day": "$day", "provider": "$provider"},
            "cost_usd": {"$sum": "$cost_usd"},
            "calls":    {"$sum": 1},
        }},
        {"$project": {
            "_id":      0,
            "day":      "$_id.day",
            "provider": "$_id.provider",
            "cost_usd": {"$round": ["$cost_usd", 4]},
            "calls":    1,
        }},
        {"$sort": {"day": 1, "provider": 1}},
    ]
    by_day_provider: List[Dict[str, Any]] = []
    async for r in _db.ora_llm_costs.aggregate(pipeline):
        by_day_provider.append(r)

    # Roll up totals per day for the simple sparkline view
    by_day: Dict[str, Dict[str, float]] = {}
    by_provider: Dict[str, Dict[str, float]] = {}
    total_cost  = 0.0
    total_calls = 0
    for r in by_day_provider:
        d = r["day"]; p = r["provider"]; c = float(r["cost_usd"]); n = int(r["calls"])
        by_day.setdefault(d, {"cost_usd": 0.0, "calls": 0})
        by_day[d]["cost_usd"] += c
        by_day[d]["calls"]    += n
        by_provider.setdefault(p, {"cost_usd": 0.0, "calls": 0})
        by_provider[p]["cost_usd"] += c
        by_provider[p]["calls"]    += n
        total_cost  += c
        total_calls += n

    daily = sorted(
        [{"day": d, "cost_usd": round(v["cost_usd"], 4), "calls": v["calls"]}
         for d, v in by_day.items()],
        key=lambda x: x["day"],
    )
    providers = sorted(
        [{"provider": p, "cost_usd": round(v["cost_usd"], 4), "calls": v["calls"]}
         for p, v in by_provider.items()],
        key=lambda x: -x["cost_usd"],
    )
    return {
        "ok":           True,
        "window_days":  days,
        "total_cost_usd": round(total_cost, 4),
        "total_calls":  total_calls,
        "daily":        daily,
        "by_provider":  providers,
        "by_day_provider": by_day_provider,
    }


@router.post("/api/admin/ora/ask")
async def admin_ora_ask(body: AskReq, request: Request):
    """Claude-backed Q&A grounded on the admin telemetry pool. Useful for:
       • "Which services hit quota most?"
       • "What's our trial-to-paid conversion across plans?"
       • "Which features are under-used and may need a UX nudge?"
    """
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    q = (body.question or "").strip()
    if not q:
        raise HTTPException(400, "question required")

    # Build a small grounding snapshot
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    by_service: Dict[str, int] = {}
    by_plan: Dict[str, int] = {}
    async for r in _db.admin_ora_brain.aggregate([
        {"$match": {"ts": {"$gte": cutoff}, "type": "service_usage"}},
        {"$group": {"_id": {"s": "$service", "p": "$plan"}, "n": {"$sum": 1}}},
    ]):
        s = r["_id"].get("s") or "unknown"
        p = r["_id"].get("p") or "unknown"
        by_service[s] = by_service.get(s, 0) + r["n"]
        by_plan[p] = by_plan.get(p, 0) + r["n"]

    # Total tenants snapshot
    tenants = await _db.platform_users.count_documents({})
    paying = await _db.platform_users.count_documents({"plan": {"$in": ["starter", "growth", "pro", "enterprise"]}})

    # Trial conversion (anonymous count of trial vs converted)
    trialing = await _db.aurem_billing.count_documents({"status": "trialing"})
    expired = await _db.aurem_billing.count_documents({"status": "trial_expired"})
    converted = await _db.aurem_billing.count_documents({"plan": {"$in": ["starter", "growth", "pro", "enterprise"]}})

    grounding = {
        "window_days": 30,
        "service_usage_counts": dict(sorted(by_service.items(), key=lambda x: -x[1])[:25]),
        "plan_usage_counts": by_plan,
        "tenant_totals": {"total": tenants, "paying": paying},
        "trial_funnel": {"trialing": trialing, "expired": expired, "converted": converted},
    }

    # ── Refusal-over-Hallucination gate ─────────────────────────────────
    # If there's effectively no grounding signal, refuse with a structured
    # INSUFFICIENT_DATA response instead of letting Claude make things up.
    total_signal_events = sum(by_service.values()) + sum(by_plan.values())
    has_tenant_signal = tenants > 0
    if GROUNDING_REQUIRED and total_signal_events < GROUNDING_MIN_EVENTS and not has_tenant_signal:
        refusal = {
            "severity": "P3",
            "root_cause": "INSUFFICIENT_DATA — telemetry pool empty for this window.",
            "suggested_fix": (
                "Cannot answer without grounding. Need at least "
                f"{GROUNDING_MIN_EVENTS} service_usage events or 1 tenant in the "
                "30-day window before this question can be answered honestly."
            ),
            "confidence": 0.0,
            "requires_deploy": False,
            "safe_auto_apply": False,
            "refused": True,
            "refusal_reason": "grounding_unavailable",
        }
        try:
            await _db.admin_ora_qa.insert_one({
                "ts": datetime.now(timezone.utc).isoformat(),
                "question": q,
                "answer": refusal,
                "grounding_snapshot": grounding,
                "refused": True,
            })
        except Exception:
            pass
        return {"ok": True, "answer": refusal, "grounding": grounding, "refused": True}

    # Claude diagnose using shared service
    try:
        from services.sentinel_ai_diagnose import diagnose_error
        # Reuse the LLM helper with a tailored grounding doc
        import json as _json
        grounding_directive = (
            "GROUNDING DIRECTIVE: You may ONLY use facts present in the "
            "'Aggregated grounding' block below. If the data is "
            "insufficient to answer the founder's question with high "
            "confidence, you MUST set 'root_cause' to 'INSUFFICIENT_DATA' "
            "and return confidence <= 0.3. Never invent numbers, BIN names, "
            "or tenant identities. Refusal is preferred over hallucination."
        )
        synthetic = {
            "type": "admin_ora_question",
            "classification": "admin_query",
            "message": (
                f"{grounding_directive}\n\n"
                f"Founder question: {q}\n\n"
                f"Aggregated grounding (30d, anonymized):\n"
                f"{_json.dumps(grounding, indent=2)}"
            ),
            "status_code": 0,
            "url": "/api/admin/ora/ask",
            "method": "POST",
            "stack": "",
            "page_url": "",
            "hostname": "aurem-admin-ora",
        }
        parsed = await diagnose_error(synthetic)
        # Persist the Q&A so it becomes part of the brain
        await _db.admin_ora_qa.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(),
            "question": q,
            "answer": parsed,
            "grounding_snapshot": grounding,
        })
        return {"ok": True, "answer": parsed, "grounding": grounding}
    except Exception as e:
        logger.exception(f"[admin_ora_ask] LLM failed: {e}")
        raise HTTPException(500, f"admin ORA failed: {e}")


@router.get("/api/admin/ora/recent")
async def admin_ora_recent(request: Request, limit: int = 25):
    """Recent admin ORA Q&A history."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    rows: List[Dict[str, Any]] = []
    async for d in _db.admin_ora_qa.find({}, {"_id": 0}).sort("ts", -1).limit(limit):
        rows.append(d)
    return {"ok": True, "count": len(rows), "history": rows}



# ── iter 331c Sprint 6 — ORA Health tile (Cockpit) ─────────────────

@router.get("/api/admin/ora/health")
async def admin_ora_health(request: Request, days: int = 7):
    """Rolling-window health snapshot for the ORA Cockpit tile.

    Returns a green/yellow/red status + the underlying numbers so the
    founder can see at a glance whether ORA is degrading.
    """
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    try:
        from services.ora_metrics import health_snapshot
        snap = await health_snapshot(days=max(1, min(int(days or 7), 90)))
    except Exception as e:
        raise HTTPException(500, f"metrics error: {e}")
    return snap


# ── iter 331c Sprint 6 — Vanguard Security score (Cockpit) ─────────

@router.get("/api/admin/ora/vanguard-status")
async def admin_ora_vanguard_status(request: Request):
    """Return the latest Vanguard Security score for the Cockpit tile
    + Morning Brief line. Reads the most recent persisted score from
    `vanguard_scores` collection (populated by the existing Vanguard
    cron). Returns a neutral 'no data yet' shape when the collection is
    empty so the UI never crashes."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    try:
        # Look for the most recent doc across the most likely collection
        # names — the Vanguard router was added before this refactor.
        for col in ("vanguard_scores", "vanguard_runs",
                    "aurem_vanguard_scores", "vanguard_security_runs"):
            doc = await _db[col].find_one({}, {"_id": 0}, sort=[("ts", -1)])
            if doc:
                score = (
                    doc.get("score") or doc.get("overall_score")
                    or doc.get("security_score")
                )
                return {
                    "ok":     True,
                    "score":  score,
                    "status": (
                        "green"  if (score or 0) >= 80
                        else "yellow" if (score or 0) >= 60
                        else "red"
                    ),
                    "last_ts": doc.get("ts") or doc.get("created_at"),
                    "source_collection": col,
                    "raw":    {k: v for k, v in doc.items() if k != "details"},
                }
        return {
            "ok":     True,
            "score":  None,
            "status": "gray",
            "message": "No Vanguard score yet — run aurem_vanguard once.",
        }
    except Exception as e:
        raise HTTPException(500, f"vanguard query failed: {e}")
