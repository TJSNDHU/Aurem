"""
bin_ora_router.py — Per-BIN ORA Q&A. Customer asks; ORA replies grounded
ONLY on that BIN's own data + best-practice insights from Admin ORA.
═══════════════════════════════════════════════════════════════════════════
  POST /api/bin/ora/ask {question}
       1. Route keyword → identify which layer agent owns the topic
       2. Pull THIS BIN's own recent layer events
       3. Pull admin's anonymized "best practice" insights for the same layer
       4. Claude answers, grounded on both — never reveals other BINs' data

Strict isolation: BinScopedRepo enforces business_id filtering. Best-practice
insights are aggregated from hashed-BIN admin_ora_brain — never per-BIN.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from middleware.bin_context import get_bin_ctx
from services.layer_agents.base import LAYERS, route_keyword_to_layer

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(db):
    global _db
    _db = db


class AskReq(BaseModel):
    question: str


@router.post("/api/bin/ora/ask")
async def bin_ora_ask(body: AskReq, request: Request):
    """Per-BIN ORA Q&A — strict data isolation enforced via business_id filter."""
    ctx = get_bin_ctx(request, required=True)
    if _db is None:
        raise HTTPException(503, "db not ready")
    q = (body.question or "").strip()
    if not q:
        raise HTTPException(400, "question required")

    # 1) Identify the layer
    layer_id = route_keyword_to_layer(q)
    layer = LAYERS.get(layer_id, {})

    # 2) Pull THIS BIN's own state grounding (filtered by business_id only)
    bin_grounding: Dict[str, Any] = {
        "business_id": ctx.business_id,
        "plan": ctx.plan,
        "services_unlocked": ctx.services_unlocked,
    }
    # Recent activity for this BIN (last 7 days)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        bin_grounding["leads_count"] = await _db.campaign_leads.count_documents(
            {"business_id": ctx.business_id}
        )
    except Exception:
        bin_grounding["leads_count"] = 0
    try:
        bin_grounding["recent_usage"] = []
        async for r in _db.service_usage_log.aggregate([
            {"$match": {"business_id": ctx.business_id, "ts": {"$gte": cutoff}}},
            {"$group": {"_id": "$service", "count": {"$sum": "$count"}}},
            {"$sort": {"count": -1}}, {"$limit": 10},
        ]):
            bin_grounding["recent_usage"].append({"service": r["_id"], "count": r["count"]})
    except Exception:
        pass

    # 3) Pull anonymized best-practice trend for this layer (across all BINs)
    best_practice = {"layer": layer_id, "trend": []}
    try:
        async for r in _db.admin_ora_brain.aggregate([
            {"$match": {"layer": layer_id, "ts": {"$gte": cutoff}}},
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}, {"$limit": 5},
        ]):
            best_practice["trend"].append({"event": r["_id"], "count": r["count"]})
    except Exception:
        pass

    # 4) Claude answer
    try:
        from services.sentinel_ai_diagnose import diagnose_error
        synthetic = {
            "type": "bin_ora_question",
            "classification": f"layer_{layer_id}",
            "message": (
                f"Customer (BIN-scoped) question: {q}\n\n"
                f"Layer: {layer.get('name')}\n\n"
                f"This BIN's grounding:\n{json.dumps(bin_grounding, indent=2)}\n\n"
                f"Anonymized best-practice trend (NOT this BIN's data):\n{json.dumps(best_practice, indent=2)}\n\n"
                "Answer ONLY using this BIN's own grounding for facts. Use trend "
                "data only as best-practice context. Never reveal other BINs' data."
            ),
            "status_code": 0,
            "url": "/api/bin/ora/ask",
            "method": "POST",
            "stack": "",
            "page_url": "",
            "hostname": f"bin-{ctx.business_id}",
        }
        parsed = await diagnose_error(synthetic)
    except Exception as e:
        logger.exception(f"[bin_ora_ask] LLM failed: {e}")
        raise HTTPException(500, f"BIN ORA failed: {e}")

    # Persist Q&A in BIN-scoped collection (never aggregated globally)
    try:
        await _db.bin_ora_qa.insert_one({
            "business_id": ctx.business_id,
            "user_id": ctx.user_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "question": q,
            "layer_id": layer_id,
            "answer": parsed,
        })
    except Exception:
        pass

    return {
        "ok": True,
        "answer": parsed,
        "layer_id": layer_id,
        "layer_name": layer.get("name"),
        "grounding": bin_grounding,
        "best_practice_signal": best_practice,
    }


@router.get("/api/bin/ora/recent")
async def bin_ora_recent(request: Request, limit: int = 10):
    """This BIN's own Q&A history."""
    ctx = get_bin_ctx(request, required=True)
    if _db is None:
        raise HTTPException(503, "db not ready")
    rows: List[Dict[str, Any]] = []
    async for d in _db.bin_ora_qa.find(
        {"business_id": ctx.business_id}, {"_id": 0}
    ).sort("ts", -1).limit(limit):
        rows.append(d)
    return {"ok": True, "count": len(rows), "history": rows}
