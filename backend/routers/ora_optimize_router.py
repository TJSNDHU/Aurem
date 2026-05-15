"""
ORA Optimize Admin Router — iter 322ep
=======================================
"Codeburn-pattern" LLM budget watchdog. Reads `llm_costs` +
`llm_response_cache` and surfaces:
  - Top expensive task_types (sum tokens_out, avg latency)
  - Cache hit ratio over last 24h
  - Stale cache rows (low/zero hits, near expiry) → drop candidates
  - Provider mix (sovereign $0 vs openrouter vs emergent)
  - Concrete recommendations + estimated savings

Endpoints (under /api/admin/ora-optimize):
  GET   /scan              full scan (~250ms)
  GET   /summary           tile-style stats for admin dashboard
  GET   /stale-cache       list of low-hit/expired cache entries
  POST  /purge-stale       drop {hits<=N, older_than_h} entries
  POST  /clear-cache       nuclear → wipe `llm_response_cache` (founder confirm)

Auth: JWT Bearer.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/ora-optimize", tags=["ora-optimize"])


def _verify_token(authorization: Optional[str] = None) -> str:
    """Bug-fix 145 — was validating JWT signature only; any user could wipe
    the entire LLM cache via /clear-cache (forces expensive API calls).
    Now requires admin claim/role/email."""
    if not authorization:
        raise HTTPException(401, "Authorization required")
    import jwt
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Authorization required")
    try:
        secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    from utils.admin_guard import is_admin_email
    is_admin = (
        payload.get("is_admin")
        or payload.get("is_super_admin")
        or payload.get("role") in ("admin", "super_admin")
        or is_admin_email(payload.get("email"))
    )
    if not is_admin:
        raise HTTPException(403, "Admin access required (ora-optimize)")
    return payload.get("user_id", payload.get("id", payload.get("sub", "unknown")))


def _get_db():
    from server import db
    if db is None:
        raise HTTPException(500, "Database not initialized")
    return db


# Per-1k-token cost estimates (USD) used ONLY for the savings calculator —
# these mirror current public list prices and are tunable later from
# `ora_optimize_prices` if the founder wants live-tracked numbers.
PRICE_PER_1K = {
    "anthropic": {"in": 0.003, "out": 0.015},  # Claude Sonnet 4.5
    "openrouter": {"in": 0.0008, "out": 0.001},  # Haiku via OR
    "sovereign": {"in": 0.0, "out": 0.0},  # Local Legion node
    "emergent": {"in": 0.003, "out": 0.015},  # Claude via Emergent key
    "fallback": {"in": 0.0, "out": 0.0},
}


def _cost_for(provider: str, tin: int, tout: int) -> float:
    p = PRICE_PER_1K.get((provider or "").lower(), PRICE_PER_1K["anthropic"])
    return round(((tin or 0) * p["in"] + (tout or 0) * p["out"]) / 1000.0, 6)


async def _scan_data(db, window_hours: int = 24):
    """Aggregate the raw signals — shared by /scan and /summary."""
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    # ── Cost rollup ─────────────────────────────────────────────────
    by_task_pipeline = [
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {
            "_id": {"task": "$task_type", "provider": "$provider"},
            "calls": {"$sum": 1},
            "tokens_in": {"$sum": "$tokens_in"},
            "tokens_out": {"$sum": "$tokens_out"},
            "latency_sum": {"$sum": "$latency_ms"},
            "fails": {"$sum": {"$cond": [{"$eq": ["$ok", False]}, 1, 0]}},
        }},
        {"$sort": {"tokens_out": -1}},
        {"$limit": 25},
    ]
    by_task = []
    async for r in db.llm_costs.aggregate(by_task_pipeline):
        gid = r.pop("_id", {}) or {}
        avg_lat = round(r["latency_sum"] / max(r["calls"], 1), 1)
        cost = _cost_for(gid.get("provider", ""), r["tokens_in"], r["tokens_out"])
        by_task.append({
            "task_type": gid.get("task", "?"),
            "provider": gid.get("provider", "?"),
            "calls": r["calls"],
            "tokens_in": r["tokens_in"],
            "tokens_out": r["tokens_out"],
            "avg_latency_ms": avg_lat,
            "fails": r["fails"],
            "est_cost_usd": cost,
        })

    # ── Provider mix ────────────────────────────────────────────────
    prov_mix = []
    async for r in db.llm_costs.aggregate([
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {
            "_id": "$provider",
            "calls": {"$sum": 1},
            "tokens_in": {"$sum": "$tokens_in"},
            "tokens_out": {"$sum": "$tokens_out"},
        }},
        {"$sort": {"calls": -1}},
    ]):
        cost = _cost_for(r["_id"], r["tokens_in"], r["tokens_out"])
        prov_mix.append({
            "provider": r["_id"] or "?",
            "calls": r["calls"],
            "tokens_out": r["tokens_out"],
            "est_cost_usd": cost,
        })

    total_calls_24h = sum(p["calls"] for p in prov_mix)
    total_cost_24h = round(sum(p["est_cost_usd"] for p in prov_mix), 4)

    # ── Cache signals ───────────────────────────────────────────────
    cache_total = await db.llm_response_cache.count_documents({})
    cache_stale = await db.llm_response_cache.count_documents({"hits": {"$lte": 0}})
    cache_hot = await db.llm_response_cache.count_documents({"hits": {"$gte": 3}})

    sum_hits = 0
    async for r in db.llm_response_cache.aggregate([
        {"$group": {"_id": None, "sum_hits": {"$sum": "$hits"}}}
    ]):
        sum_hits = int(r.get("sum_hits") or 0)

    # Best estimate of saved cost: each cache hit ≈ avg(tokens_out) at
    # the provider distribution we see in llm_costs over the window.
    avg_tokens_out = 0
    if total_calls_24h > 0:
        avg_tokens_out = round(
            sum(p["tokens_out"] for p in prov_mix) / total_calls_24h, 1
        )
    # Use Claude (anthropic) cost as the upper-bound saved-cost estimate.
    saved_cost_estimate = round(
        sum_hits * avg_tokens_out * PRICE_PER_1K["anthropic"]["out"] / 1000.0, 4
    )

    cache_hit_ratio = None
    if (cache_total + total_calls_24h) > 0:
        # hit ratio over the WINDOW only — cache hits don't write llm_costs,
        # so we approximate as sum_hits / (sum_hits + total_calls_24h)
        denom = sum_hits + total_calls_24h
        cache_hit_ratio = round(sum_hits / denom * 100, 1) if denom else None

    # ── Recommendations ─────────────────────────────────────────────
    recs = []
    if cache_stale > 50:
        recs.append({
            "id": "purge_stale_cache",
            "severity": "low",
            "title": f"Drop {cache_stale} zero-hit cache rows",
            "action": "POST /api/admin/ora-optimize/purge-stale (hits=0, older_than_h=24)",
            "impact": "Reclaims ~%.1f%% of cache slots, faster scans" % (cache_stale / max(cache_total, 1) * 100),
        })
    if cache_hit_ratio is not None and cache_hit_ratio < 20 and total_calls_24h > 50:
        recs.append({
            "id": "raise_cache_ttl",
            "severity": "medium",
            "title": "Cache hit ratio low — consider raising TTL",
            "action": "Increase llm_response_cache TTL to 24h (currently 12h)",
            "impact": f"Today's hit ratio {cache_hit_ratio}%, target ≥30%",
        })
    emergent_calls = next(
        (p for p in prov_mix if (p["provider"] or "").lower() == "emergent"), None
    )
    sovereign_calls = next(
        (p for p in prov_mix if (p["provider"] or "").lower() == "sovereign"), None
    )
    if emergent_calls and emergent_calls["calls"] > 50:
        recs.append({
            "id": "shift_to_sovereign",
            "severity": "high",
            "title": f"Emergent key handled {emergent_calls['calls']} calls (${emergent_calls['est_cost_usd']})",
            "action": "Bring Sovereign Node (Legion ngrok tunnel) back up to redirect ~80% to $0 inference",
            "impact": f"Could save ${round(emergent_calls['est_cost_usd'] * 0.8, 3)}/24h",
        })
    if sovereign_calls and total_calls_24h > 0:
        sov_pct = round(sovereign_calls["calls"] / total_calls_24h * 100, 1)
        if sov_pct < 50:
            recs.append({
                "id": "increase_sovereign_share",
                "severity": "medium",
                "title": f"Only {sov_pct}% of traffic on Sovereign Node",
                "action": "Verify Sovereign Node uptime and routing weight in llm_gateway.py",
                "impact": "Each +10% sovereign share reduces $/call by the same",
            })
    # Highest token-out task = top optimization target
    if by_task:
        top = by_task[0]
        if top["tokens_out"] > 5000 and top["provider"] != "sovereign":
            recs.append({
                "id": "shift_top_task",
                "severity": "medium",
                "title": f"Top task '{top['task_type']}' burned {top['tokens_out']:,} out-tokens via {top['provider']}",
                "action": "Lower max_tokens or route this task_type to Groq/Sovereign first",
                "impact": f"Saves up to ${round(top['est_cost_usd'] * 0.6, 3)}/24h",
            })
    # Cache failure pattern — many fails?
    fail_total = sum(t["fails"] for t in by_task)
    if fail_total > 5:
        recs.append({
            "id": "investigate_fails",
            "severity": "high",
            "title": f"{fail_total} LLM call failures in last {window_hours}h",
            "action": "Inspect /api/admin/ora-optimize/scan rows where fails>0 and tail backend.err.log",
            "impact": "Failed calls waste tokens AND latency",
        })

    return {
        "window_hours": window_hours,
        "since": since.isoformat(),
        "total_calls": total_calls_24h,
        "total_cost_usd": total_cost_24h,
        "by_task": by_task,
        "provider_mix": prov_mix,
        "cache": {
            "rows": cache_total,
            "stale_zero_hits": cache_stale,
            "hot_3plus_hits": cache_hot,
            "total_hits": sum_hits,
            "avg_tokens_per_hit": avg_tokens_out,
            "approx_hit_ratio_pct": cache_hit_ratio,
            "estimated_saved_usd": saved_cost_estimate,
        },
        "recommendations": recs,
    }


@router.get("/scan")
async def scan(
    window_hours: int = Query(24, ge=1, le=168),
    authorization: Optional[str] = Header(None),
):
    """Full optimization scan."""
    _verify_token(authorization)
    db = _get_db()
    started = datetime.now(timezone.utc)
    data = await _scan_data(db, window_hours)
    data["scanned_at"] = started.isoformat()
    data["took_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    return {"ok": True, **data}


@router.get("/summary")
async def summary(authorization: Optional[str] = Header(None)):
    """One-glance KPIs for the admin dashboard tile."""
    _verify_token(authorization)
    db = _get_db()
    data = await _scan_data(db, window_hours=24)
    return {
        "ok": True,
        "calls_24h": data["total_calls"],
        "cost_24h_usd": data["total_cost_usd"],
        "cache_rows": data["cache"]["rows"],
        "cache_hit_ratio_pct": data["cache"]["approx_hit_ratio_pct"],
        "cache_saved_usd": data["cache"]["estimated_saved_usd"],
        "recommendations_count": len(data["recommendations"]),
    }


@router.get("/stale-cache")
async def stale_cache(
    hits_max: int = Query(0, ge=0, le=10),
    older_than_hours: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=1000),
    authorization: Optional[str] = Header(None),
):
    """List cache rows that look safe to drop."""
    _verify_token(authorization)
    db = _get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    q = {"hits": {"$lte": hits_max}, "created_at": {"$lte": cutoff}}
    rows = await db.llm_response_cache.find(
        q,
        {"_id": 0, "cache_key": 1, "scope": 1, "signature": 1, "hits": 1,
         "created_at": 1, "expires_at": 1},
    ).sort("created_at", 1).limit(limit).to_list(length=limit)
    total = await db.llm_response_cache.count_documents(q)
    return {"ok": True, "match_total": total, "showing": len(rows), "rows": rows}


class PurgeRequest(BaseModel):
    hits_max: int = Field(0, ge=0, le=10)
    older_than_hours: int = Field(24, ge=1, le=720)


@router.post("/purge-stale")
async def purge_stale(req: PurgeRequest, authorization: Optional[str] = Header(None)):
    """Drop low-hit / old cache rows. Returns count deleted."""
    _verify_token(authorization)
    db = _get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=req.older_than_hours)
    q = {"hits": {"$lte": req.hits_max}, "created_at": {"$lte": cutoff}}
    matched = await db.llm_response_cache.count_documents(q)
    res = await db.llm_response_cache.delete_many(q)
    return {
        "ok": True,
        "matched": matched,
        "deleted": res.deleted_count,
        "criteria": req.dict(),
    }


@router.post("/clear-cache")
async def clear_cache(
    confirm: str = Query("", description="Must equal 'YES_NUKE_CACHE'"),
    authorization: Optional[str] = Header(None),
):
    """Nuclear option — wipe ALL of llm_response_cache. Requires
    explicit confirmation flag."""
    _verify_token(authorization)
    if confirm != "YES_NUKE_CACHE":
        raise HTTPException(400, "confirm flag mismatch. Send ?confirm=YES_NUKE_CACHE")
    db = _get_db()
    before = await db.llm_response_cache.count_documents({})
    await db.llm_response_cache.delete_many({})
    return {"ok": True, "deleted": before}


@router.get("/_/health")
async def opt_health():
    db = _get_db()
    costs = await db.llm_costs.count_documents({})
    cache = await db.llm_response_cache.count_documents({})
    return {"ok": True, "scope": "ora_optimize", "llm_costs": costs, "llm_cache": cache}
