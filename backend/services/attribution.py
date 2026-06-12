"""
Outcome Attribution + ORA Learning Bias (iter 315)
====================================================
Closes the compounding loop. Every lead response/booking/payment is
linked back to its `forecast_campaign_id` + `forecast_id`, so the next
Sunday Forecast can rank campaigns by revenue-per-100-leads, and the
Council prompt biases BUILD verdicts toward proven converters.

Public:
  await attribute_lead_outcome(db, lead_id, outcome_type, revenue_cad,
                                  source_hint="paid|responded|booked") -> dict
  await top_performing_bets(db, days=30, limit=3) -> list[dict]
  await record_proven_bets_learning(db, bets) -> dict
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

OUTCOME_TYPES = {"responded", "booked", "paid"}


async def _find_active_campaign(db, lead_id: str) -> Optional[Dict[str, Any]]:
    """Most recent armed/fired campaign that included this lead."""
    if not lead_id:
        return None
    cursor = db.forecast_campaigns.find(
        {"lead_ids": lead_id,
         "status": {"$in": ["armed", "fired"]}},
        {"_id": 0, "campaign_id": 1, "forecast_id": 1, "bet_topic": 1,
          "armed_at": 1, "fired_at": 1, "status": 1},
    ).sort("armed_at", -1).limit(1)
    docs = await cursor.to_list(1)
    return docs[0] if docs else None


async def attribute_lead_outcome(
    db, lead_id: str, outcome_type: str,
    revenue_cad: float = 0.0,
    source_hint: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Stamp the lead + write a campaign_outcomes row. Idempotent on
    (campaign_id, lead_id, outcome_type) — second call updates revenue."""
    if outcome_type not in OUTCOME_TYPES:
        return {"ok": False, "error": f"invalid_outcome:{outcome_type}"}
    if not lead_id:
        return {"ok": False, "error": "lead_id_required"}

    camp = await _find_active_campaign(db, lead_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Stamp the lead either way (lets us count responses even pre-campaign)
    lead_set: Dict[str, Any] = {f"converted_{outcome_type}_at": now_iso}
    if camp:
        lead_set["source_campaign_id"] = camp["campaign_id"]
        lead_set["source_forecast_id"] = camp.get("forecast_id")
    if outcome_type == "paid":
        lead_set["converted_at"] = now_iso
        lead_set["revenue_attributed_cad"] = float(revenue_cad or 0)
    try:
        await db.campaign_leads.update_one(
            {"lead_id": lead_id, "business_id": FOUNDER_BIN},
            {"$set": lead_set})
    except Exception as e:
        logger.debug(f"[attrib] lead update failed: {e}")

    if not camp:
        return {"ok": True, "outcome": outcome_type,
                "campaign_attributed": False,
                "reason": "no_active_campaign_for_lead"}

    rec = {
        "id": uuid.uuid4().hex[:14],
        "campaign_id": camp["campaign_id"],
        "forecast_id": camp.get("forecast_id"),
        "bet_topic": camp.get("bet_topic"),
        "lead_id": lead_id,
        "outcome_type": outcome_type,
        "revenue_cad": float(revenue_cad or 0),
        "source_hint": source_hint,
        "converted_at": now_iso,
        "extra": extra or {},
    }
    try:
        # Idempotent upsert on (campaign_id, lead_id, outcome_type)
        await db.campaign_outcomes.update_one(
            {"campaign_id": camp["campaign_id"],
              "lead_id": lead_id,
              "outcome_type": outcome_type},
            {"$set": {k: v for k, v in rec.items() if k != "id"},
              "$setOnInsert": {"id": rec["id"],
                                "first_seen_at": now_iso}},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[attrib] outcome upsert failed: {e}")
        return {"ok": False, "error": str(e)[:160]}

    return {"ok": True, "outcome": outcome_type,
            "campaign_id": camp["campaign_id"],
            "forecast_id": camp.get("forecast_id"),
            "bet_topic": camp.get("bet_topic"),
            "revenue_cad": rec["revenue_cad"]}


# ─── Performance ranking ─────────────────────────────────────────────────
async def top_performing_bets(db, days: int = 30,
                                 limit: int = 3) -> List[Dict[str, Any]]:
    """Rank campaigns by revenue-per-100-leads over the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Pull recent campaigns with status fired
    camps = await db.forecast_campaigns.find(
        {"status": "fired",
         "fired_at": {"$gte": cutoff}},
        {"_id": 0, "campaign_id": 1, "bet_topic": 1, "lead_count": 1,
          "fired_at": 1, "forecast_id": 1},
    ).to_list(500)
    if not camps:
        return []

    # Aggregate outcomes
    pipeline = [
        {"$match": {"converted_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$campaign_id",
            "responded": {"$sum": {"$cond": [
                {"$eq": ["$outcome_type", "responded"]}, 1, 0]}},
            "booked": {"$sum": {"$cond": [
                {"$eq": ["$outcome_type", "booked"]}, 1, 0]}},
            "paid": {"$sum": {"$cond": [
                {"$eq": ["$outcome_type", "paid"]}, 1, 0]}},
            "revenue": {"$sum": "$revenue_cad"},
        }},
    ]
    outcomes_by_camp: Dict[str, Dict[str, Any]] = {}
    async for row in db.campaign_outcomes.aggregate(pipeline):
        outcomes_by_camp[row["_id"]] = row

    enriched: List[Dict[str, Any]] = []
    for c in camps:
        cid = c["campaign_id"]
        n = max(1, int(c.get("lead_count") or 1))
        oc = outcomes_by_camp.get(cid, {})
        rev = float(oc.get("revenue", 0) or 0)
        enriched.append({
            "campaign_id": cid,
            "bet_topic": (c.get("bet_topic") or "")[:120],
            "lead_count": n,
            "responded": oc.get("responded", 0),
            "booked": oc.get("booked", 0),
            "paid": oc.get("paid", 0),
            "revenue_cad": rev,
            "revenue_per_100": round(rev * 100.0 / n, 2),
            "fired_at": c.get("fired_at"),
        })
    enriched.sort(key=lambda x: (x["revenue_per_100"], x["paid"],
                                    x["booked"], x["responded"]),
                   reverse=True)
    return enriched[:limit]


async def proven_bets_summary(db, days: int = 30) -> str:
    """One-liner for use inside ORA system prompts."""
    bets = await top_performing_bets(db, days=days, limit=3)
    if not bets:
        return ""
    parts = []
    for b in bets:
        parts.append(
            f"{b['bet_topic'][:60]} (${b['revenue_per_100']:.0f}/100 leads, "
            f"{b['paid']}p/{b['booked']}b/{b['responded']}r)"
        )
    return " · ".join(parts)


async def record_proven_bets_learning(db, bets: List[Dict[str, Any]],
                                        ) -> Dict[str, Any]:
    """Persist the top bets into ora_learnings as a 'proven_converter' row.
    Used by the Council bias prompt + by the next Sunday Forecast."""
    if not bets:
        return {"ok": False, "skipped": "no_bets"}
    rec = {
        "id": uuid.uuid4().hex[:14],
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_title": "Proven Converter Bets (rolling 30d)",
        "weight": "proven_converter",
        "build_path": "attribution_summary",
        "council_verdict": "BUILD",
        "risk_score": 2,
        "outcome": "compound",
        "high_performing_bets": [
            {"bet_topic": b["bet_topic"],
              "revenue_per_100": b["revenue_per_100"],
              "paid": b["paid"], "booked": b["booked"],
              "responded": b["responded"],
              "campaign_id": b["campaign_id"]}
            for b in bets
        ],
    }
    try:
        await db.ora_learnings.insert_one(dict(rec))
    except Exception as e:
        logger.warning(f"[attrib] proven bets persist failed: {e}")
    rec.pop("_id", None)
    return {"ok": True, "record": rec}
