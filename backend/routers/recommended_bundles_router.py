"""
routers/recommended_bundles_router.py — iter 326j Gaps 3 + 5
═══════════════════════════════════════════════════════════════════════════
Endpoints:
  GET  /api/catalog/tier-bundles
  GET  /api/catalog/recommended-bundles?industry=restaurant|salon|clinic|agency
  POST /api/customer/bundle-price       — live price for an arbitrary cart
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import recommended_bundles

logger = logging.getLogger(__name__)

router = APIRouter()
_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ── Models ───────────────────────────────────────────────────────────
class BundlePriceRequest(BaseModel):
    service_ids: list[str] = Field(..., min_length=1, max_length=30)


# ── Tier bundles (Starter / Growth / Pro / Enterprise) ───────────────
@router.get("/api/catalog/tier-bundles")
async def list_tier_bundles():
    if _db is None:
        raise HTTPException(503, "db not ready")
    out = []
    async for d in _db.subscription_plans.find(
        {}, {"_id": 0}
    ).sort("tier_order", 1):
        # Live-price each tier so the badge stays in sync with catalog.
        if d.get("service_ids"):
            pricing = await recommended_bundles.price_bundle(_db, d["service_ids"])
            d["computed"] = pricing
        out.append(d)
    return {"ok": True, "count": len(out), "tiers": out}


# ── Industry recommended bundles ─────────────────────────────────────
@router.get("/api/catalog/recommended-bundles")
async def list_recommended_bundles(industry: Optional[str] = None):
    if _db is None:
        raise HTTPException(503, "db not ready")
    q = {"industry": industry} if industry else {}
    out = []
    async for d in _db.recommended_bundles.find(q, {"_id": 0}):
        if d.get("service_ids"):
            pricing = await recommended_bundles.price_bundle(_db, d["service_ids"])
            d["computed"] = pricing
        out.append(d)
    return {"ok": True, "count": len(out),
            "industry": industry, "bundles": out}


# ── Live cart pricing for arbitrary mix ───────────────────────────────
@router.post("/api/customer/bundle-price")
async def compute_bundle_price(body: BundlePriceRequest):
    if _db is None:
        raise HTTPException(503, "db not ready")
    res = await recommended_bundles.price_bundle(_db, body.service_ids)
    if not res.get("ok"):
        raise HTTPException(503, res.get("reason", "pricing unavailable"))
    return res
