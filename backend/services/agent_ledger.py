"""
AUREM Agent Ledger — "Revenue-Reflector"
=========================================
Iter 288.0 — Sovereign Boardroom foundation.

Tracks every agent's cost (LLM tokens, email, SMS, WABA, Apollo credits) AND
revenue attribution (potential + realized) so the founder can run a P&L on
each AI employee.

Storage:
  db.agent_ledger_entries           — one row per cost/revenue event
  db.agent_rates                    — editable rate card (per channel)
  db.agent_kill_switch_log          — loss-making kill-switch audit

Contract:
  await record_cost(db, agent_id, source, units, meta=None)
  await record_revenue(db, agent_id, amount_usd, stage, lead_id=None, meta=None)
  await get_roi(db, agent_id, days=7)                -> dict
  await get_board(db, days=7)                        -> list (per-agent P&L)
  await get_rates(db)                                -> dict
  await set_rate(db, key, cost_usd, label=None)      -> dict
  await kill_switch_check(db, days=7, min_roi=0.5)   -> list of underperformers

All rates are USD. `units` semantics:
  - LLM        → units = total_tokens (input+output), cost = tokens / 1000 * rate
  - EMAIL      → units = emails_sent,   cost = units * rate
  - SMS / WABA → units = messages_sent, cost = units * rate
  - APOLLO     → units = enrich_credits,cost = units * rate
  - TELEGRAM / REDIS / INFRA  → usually 0-cost; retained for audit only.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# DEFAULT RATE CARD (editable from Admin PWA via /api/agents/board/rates)
# Per-unit USD cost. Tweak from UI — these values are seed-only.
# ─────────────────────────────────────────────────────────────
DEFAULT_RATES: Dict[str, Dict[str, Any]] = {
    "llm_openai_gpt4o":       {"rate": 0.005,  "unit": "per_1k_tokens", "label": "OpenAI GPT-4o (blended)"},
    "llm_openai_gpt4o_mini":  {"rate": 0.0006, "unit": "per_1k_tokens", "label": "OpenAI GPT-4o-mini"},
    "llm_anthropic_sonnet":   {"rate": 0.009,  "unit": "per_1k_tokens", "label": "Claude Sonnet 4.5 (blended)"},
    "llm_gemini_flash":       {"rate": 0.0005, "unit": "per_1k_tokens", "label": "Gemini Flash"},
    "email_resend":           {"rate": 0.0001, "unit": "per_email",     "label": "Resend (bulk)"},
    "sms_twilio":             {"rate": 0.01,   "unit": "per_sms",       "label": "Twilio SMS"},
    "waba_twilio":            {"rate": 0.005,  "unit": "per_message",   "label": "Twilio WABA (WhatsApp)"},
    "voice_retell":           {"rate": 0.07,   "unit": "per_minute",    "label": "Retell AI voice call"},
    "voice_twilio":           {"rate": 0.014,  "unit": "per_call",      "label": "Twilio outbound voice (avg 1min)"},
    "apollo_enrich":          {"rate": 0.10,   "unit": "per_credit",    "label": "Apollo.io enrich credit"},
    "tavily_search":          {"rate": 0.008,  "unit": "per_query",     "label": "Tavily web search"},
    "firecrawl_scrape":       {"rate": 0.003,  "unit": "per_page",      "label": "Firecrawl scrape"},
    "infra_compute":          {"rate": 0.0,    "unit": "per_second",    "label": "Compute (K8s)"},
}


# ─────────────────────────────────────────────────────────────
# RATES
# ─────────────────────────────────────────────────────────────
async def _ensure_seeded(db) -> None:
    """Seed the rates collection on first access."""
    if db is None:
        return
    existing = await db.agent_rates.count_documents({})
    if existing == 0:
        docs = [
            {"_id": k, "key": k, **v, "editable": True,
             "seeded_at": datetime.now(timezone.utc).isoformat()}
            for k, v in DEFAULT_RATES.items()
        ]
        await db.agent_rates.insert_many(docs)
        logger.info(f"[LEDGER] Seeded {len(docs)} default rates")


async def get_rates(db) -> Dict[str, Dict[str, Any]]:
    if db is None:
        return DEFAULT_RATES
    await _ensure_seeded(db)
    docs = await db.agent_rates.find({}, {"_id": 0}).to_list(length=200)
    return {d["key"]: d for d in docs}


async def set_rate(db, key: str, cost_usd: float, label: Optional[str] = None,
                   unit: Optional[str] = None) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable."}
    await _ensure_seeded(db)
    update = {"rate": float(cost_usd),
              "updated_at": datetime.now(timezone.utc).isoformat()}
    if label:
        update["label"] = label
    if unit:
        update["unit"] = unit
    res = await db.agent_rates.update_one(
        {"_id": key},
        {"$set": update, "$setOnInsert": {"key": key, "editable": True}},
        upsert=True,
    )
    return {"ok": True, "key": key, "rate": cost_usd,
            "matched": res.matched_count, "upserted": bool(res.upserted_id)}


async def _rate_for(db, source: str) -> float:
    rates = await get_rates(db)
    return float((rates.get(source) or DEFAULT_RATES.get(source) or {}).get("rate", 0.0))


# ─────────────────────────────────────────────────────────────
# COST / REVENUE RECORDING
# ─────────────────────────────────────────────────────────────
async def record_cost(db, agent_id: str, source: str, units: float,
                      meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Record a cost event. source must match a key in agent_rates (or DEFAULT_RATES).

    For LLM: `units` = total tokens; cost = (units / 1000) * rate
    For others: cost = units * rate
    """
    if db is None or not agent_id or not source:
        return {"ok": False, "cost_usd": 0.0}

    rate = await _rate_for(db, source)
    if source.startswith("llm_"):
        cost = (float(units) / 1000.0) * rate
    else:
        cost = float(units) * rate

    entry = {
        "kind": "cost",
        "agent_id": agent_id,
        "source": source,
        "units": float(units),
        "rate_usd": rate,
        "cost_usd": round(cost, 6),
        "meta": meta or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ttl_at": datetime.now(timezone.utc),  # 180-day TTL index (created elsewhere)
    }
    try:
        await db.agent_ledger_entries.insert_one(entry)
    except Exception as e:
        logger.warning(f"[LEDGER] record_cost insert failed: {e}")
        return {"ok": False, "cost_usd": 0.0}
    entry.pop("_id", None)
    entry.pop("ttl_at", None)
    return {"ok": True, **entry}


async def record_revenue(db, agent_id: str, amount_usd: float, stage: str,
                         lead_id: Optional[str] = None,
                         meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Attribute revenue to an originating agent.

    stage semantics:
      - potential   → lead scouted / qualified, estimated value
      - interested  → lead replied positively, weighted upward
      - closed_won  → realized revenue (actual $)
      - closed_lost → zero realized (kept for loss analysis)
    """
    if db is None or not agent_id:
        return {"ok": False}
    realized = stage == "closed_won"
    entry = {
        "kind": "revenue",
        "agent_id": agent_id,
        "stage": stage,
        "amount_usd": round(float(amount_usd), 2),
        "realized": realized,
        "lead_id": lead_id,
        "meta": meta or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ttl_at": datetime.now(timezone.utc),
    }
    try:
        await db.agent_ledger_entries.insert_one(entry)
    except Exception as e:
        logger.warning(f"[LEDGER] record_revenue insert failed: {e}")
        return {"ok": False}
    entry.pop("_id", None)
    entry.pop("ttl_at", None)
    return {"ok": True, **entry}


# ─────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────
async def get_roi(db, agent_id: str, days: int = 7,
                    exclude_synthetic: bool = False) -> Dict[str, Any]:
    """Per-agent ROI rollup.

    iter 315g — `synthetic` = revenue rows with `lead_id IS NULL` AND empty
    `meta`. These are seed/manual ledger entries (e.g. dashboard
    placeholders) with no Stripe/CRM provenance and should never be
    presented as real revenue.

    When `exclude_synthetic=True`, those rows are dropped from realized +
    potential totals (their amounts still surface in `synthetic_*` keys
    so the founder dashboard can show a "⚠️ N synthetic entries hidden"
    badge).
    """
    if db is None:
        return {"agent_id": agent_id, "cost_usd": 0.0, "revenue_realized_usd": 0.0,
                "revenue_potential_usd": 0.0, "roi": 0.0, "days": days,
                "synthetic_realized_usd": 0.0, "synthetic_potential_usd": 0.0,
                "synthetic_count": 0}
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    cost_agg = db.agent_ledger_entries.aggregate([
        {"$match": {"kind": "cost", "agent_id": agent_id,
                      "timestamp": {"$gte": since}}},
        {"$group": {"_id": None, "total": {"$sum": "$cost_usd"},
                    "by_source": {"$push": {"source": "$source", "cost": "$cost_usd"}}}},
    ])
    # Project a `synthetic` boolean flag per revenue row so we can split
    # totals without two round-trips.
    rev_agg = db.agent_ledger_entries.aggregate([
        {"$match": {"kind": "revenue", "agent_id": agent_id,
                      "timestamp": {"$gte": since}}},
        {"$addFields": {
            "_meta_empty": {"$cond": [
                {"$eq": [{"$ifNull": ["$meta", {}]}, {}]}, True, False]},
            "_no_lead": {"$or": [
                {"$eq": ["$lead_id", None]},
                {"$eq": ["$lead_id", ""]},
                {"$not": ["$lead_id"]}]}}},
        {"$addFields": {
            "_synthetic": {"$and": ["$_meta_empty", "$_no_lead"]}}},
        {"$group": {"_id": {"stage": "$stage", "synthetic": "$_synthetic"},
                    "total": {"$sum": "$amount_usd"},
                    "count": {"$sum": 1}}},
    ])

    cost_docs = await cost_agg.to_list(length=1)
    rev_docs = await rev_agg.to_list(length=20)

    cost_total = round((cost_docs[0]["total"] if cost_docs else 0.0) or 0.0, 4)
    cost_by_source: Dict[str, float] = {}
    if cost_docs:
        for e in cost_docs[0].get("by_source", []) or []:
            s = e.get("source", "unknown")
            cost_by_source[s] = round(cost_by_source.get(s, 0.0)
                                          + (e.get("cost", 0.0) or 0.0), 4)

    realized = 0.0
    potential = 0.0
    syn_realized = 0.0
    syn_potential = 0.0
    syn_count = 0
    by_stage: Dict[str, Dict[str, Any]] = {}
    for r in rev_docs:
        key = r["_id"] if isinstance(r["_id"], dict) else {}
        stage = key.get("stage")
        is_syn = bool(key.get("synthetic"))
        amt = round(r["total"] or 0.0, 2)
        cnt = int(r.get("count", 0))
        # Aggregate by stage (regardless of synthetic) for transparency
        bucket = by_stage.setdefault(stage,
                                          {"total_usd": 0.0, "count": 0,
                                           "synthetic_usd": 0.0,
                                           "synthetic_count": 0})
        bucket["total_usd"] = round(bucket["total_usd"] + amt, 2)
        bucket["count"] += cnt
        if is_syn:
            bucket["synthetic_usd"] = round(bucket["synthetic_usd"] + amt, 2)
            bucket["synthetic_count"] += cnt
            syn_count += cnt
            if stage == "closed_won":
                syn_realized += amt
            else:
                syn_potential += amt
        # Real (non-synthetic) tally
        if not is_syn:
            if stage == "closed_won":
                realized += amt
            else:
                potential += amt

    if not exclude_synthetic:
        realized += syn_realized
        potential += syn_potential

    roi_realized = ((realized / cost_total) if cost_total > 0
                      else (float("inf") if realized > 0 else 0.0))
    roi_potential = (((realized + potential) / cost_total) if cost_total > 0
                       else (float("inf") if (realized + potential) > 0 else 0.0))

    def _safe(v: float) -> float:
        return round(v, 3) if v != float("inf") else 999.0

    return {
        "agent_id": agent_id,
        "days": days,
        "cost_usd": cost_total,
        "cost_by_source": cost_by_source,
        "revenue_realized_usd": round(realized, 2),
        "revenue_potential_usd": round(potential, 2),
        "synthetic_realized_usd": round(syn_realized, 2),
        "synthetic_potential_usd": round(syn_potential, 2),
        "synthetic_count": syn_count,
        "roi_realized": _safe(roi_realized),
        "roi_potential": _safe(roi_potential),
        "stages": by_stage,
        "exclude_synthetic": exclude_synthetic,
    }


AGENT_IDS = ["hunter_ora", "followup_ora", "closer_ora", "referral_ora", "scout_ora", "envoy_ora"]


async def get_board(db, days: int = 7,
                       exclude_synthetic: bool = False) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for aid in AGENT_IDS:
        row = await get_roi(db, aid, days=days,
                              exclude_synthetic=exclude_synthetic)
        rows.append(row)
    # Also pull any dynamic agent_ids seen in the ledger (future-proof)
    if db is not None:
        seen = await db.agent_ledger_entries.distinct("agent_id")
        for aid in seen:
            if aid and aid not in AGENT_IDS:
                rows.append(await get_roi(db, aid, days=days,
                                              exclude_synthetic=exclude_synthetic))
    rows.sort(key=lambda r: r["cost_usd"], reverse=True)
    return rows


async def kill_switch_check(db, days: int = 7, min_roi: float = 0.5,
                            min_cost: float = 1.0) -> List[Dict[str, Any]]:
    """Identify agents losing money.

    Criteria: cost > `min_cost` AND roi_potential < `min_roi` over `days`.
    Returns the list of underperformers (main caller posts to Telegram etc).
    """
    board = await get_board(db, days=days)
    losers = [row for row in board
              if row["cost_usd"] >= min_cost and row["roi_potential"] < min_roi]
    # Audit
    if db is not None and losers:
        try:
            await db.agent_kill_switch_log.insert_one({
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "days": days, "min_roi": min_roi, "min_cost": min_cost,
                "losers": [row["agent_id"] for row in losers],
                "details": losers,
            })
        except Exception:
            pass
    return losers


# ─────────────────────────────────────────────────────────────
# TOP-LEVEL ROLLUP (for PWA header)
# ─────────────────────────────────────────────────────────────
async def get_top_rollup(db, days: int = 1,
                            exclude_synthetic: bool = False) -> Dict[str, Any]:
    board = await get_board(db, days=days,
                                exclude_synthetic=exclude_synthetic)
    gross_burn = round(sum(r["cost_usd"] for r in board), 4)
    realized = round(sum(r["revenue_realized_usd"] for r in board), 2)
    potential = round(sum(r["revenue_potential_usd"] for r in board), 2)
    syn_realized = round(
        sum(r.get("synthetic_realized_usd", 0.0) for r in board), 2)
    syn_potential = round(
        sum(r.get("synthetic_potential_usd", 0.0) for r in board), 2)
    syn_count = sum(int(r.get("synthetic_count", 0)) for r in board)
    top_spender = max(board, key=lambda r: r["cost_usd"]) if board else None
    firing_line = [r for r in board
                     if r["cost_usd"] > 0 and r["roi_potential"] < 0.5]
    return {
        "days": days,
        "gross_burn_usd": gross_burn,
        "realized_revenue_usd": realized,
        "potential_pipeline_usd": potential,
        "synthetic_realized_usd": syn_realized,
        "synthetic_potential_usd": syn_potential,
        "synthetic_count": syn_count,
        "exclude_synthetic": exclude_synthetic,
        "net_margin_usd": round((realized + potential) - gross_burn, 2),
        "top_spender": (top_spender["agent_id"]
                          if top_spender and top_spender["cost_usd"] > 0
                          else None),
        "firing_line": [r["agent_id"] for r in firing_line],
        "board": board,
    }
