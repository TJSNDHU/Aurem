"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Global Pulse Router — Economic Intelligence Hub
================================================
World-Sense Intelligence: news, markets, BoC data, ticker, learning deltas, live reporter.
COMPLIANCE: Economic data for business context only. Not investment advice.
"""
import logging
import os
from fastapi import APIRouter, Depends, Header, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/global-pulse", tags=["Global Pulse"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.global_pulse import set_db as set_gp_db
    set_gp_db(database)


async def _get_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        import jwt as pyjwt
        secret = os.environ.get("JWT_SECRET", "")
        token = authorization.replace("Bearer ", "")
        payload = pyjwt.decode(token, secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if not user_id or not _db:
            raise HTTPException(status_code=401, detail="Unauthorized")
        user = await _db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/latest")
async def get_latest_pulse(user=Depends(_get_user)):
    """Get the latest Global Pulse (news + markets) from cache."""
    from services.global_pulse import get_latest_pulse
    return await get_latest_pulse()


@router.post("/scan")
async def trigger_scan(user=Depends(_get_user)):
    """Manually trigger a Global Pulse scan."""
    from services.global_pulse import run_global_pulse
    return await run_global_pulse()


@router.get("/market")
async def get_market_data(user=Depends(_get_user)):
    """Get the latest financial market data (BoC + Alpha Vantage)."""
    from services.global_pulse import fetch_market_data
    return await fetch_market_data()


@router.get("/boc")
async def get_boc_data(user=Depends(_get_user)):
    """Get Bank of Canada data (CAD/USD, policy rate, prime rate)."""
    from services.global_pulse import get_boc_cached
    return await get_boc_cached()


@router.get("/ticker")
async def get_ticker_data(user=Depends(_get_user)):
    """Get ticker rotation items for the Economic Ticker bar."""
    from services.global_pulse import get_ticker_items
    tenant_id = user.get("tenant_id", user.get("id", "aurem_platform"))
    items = await get_ticker_items(tenant_id)
    return {"items": items, "rotation_interval_ms": 4000, "compliance": "Economic data for business context only. Not investment advice."}


@router.get("/economic-brief")
async def get_economic_brief(user=Depends(_get_user)):
    """Get the economic context line for Morning Brief injection."""
    from services.global_pulse import build_economic_brief_line
    line = await build_economic_brief_line()
    return {"economic_context": line, "compliance": "Economic data for business context only. Not investment advice."}


@router.get("/live-brief")
async def get_live_brief(user=Depends(_get_user)):
    """Get ORA's Live Reporter morning brief."""
    from services.global_pulse import build_live_reporter_brief
    tenant_id = user.get("tenant_id", user.get("id", "aurem_platform"))
    brief = await build_live_reporter_brief(tenant_id)
    return {"brief": brief, "source": "live_reporter", "compliance": "Economic data for business context only. Not investment advice."}


@router.post("/learn")
async def trigger_learning(user=Depends(_get_user)):
    """Manually trigger the Recursive Brain learning delta computation."""
    from services.global_pulse import compute_learning_delta
    return await compute_learning_delta()


@router.get("/deltas")
async def get_learning_deltas(user=Depends(_get_user)):
    """Get recent learning deltas (context accuracy history)."""
    if _db is None:
        return {"deltas": []}
    cursor = _db.learning_deltas.find({}, {"_id": 0}).sort("computed_at", -1).limit(14)
    deltas = await cursor.to_list(length=14)
    return {"deltas": deltas}


@router.get("/geo-context")
async def get_geo_context(user=Depends(_get_user)):
    """Get geo-aware economic context region for this tenant."""
    from services.global_pulse import get_geo_context
    tenant_id = user.get("tenant_id", user.get("id", "aurem_platform"))
    region = await get_geo_context(tenant_id)
    region_labels = {"ca": "Canada (BoC primary)", "in": "India (RBI/Alpha Vantage)", "us": "USA (Alpha Vantage + Fed)"}
    return {"region": region, "label": region_labels.get(region, "Canada (default)"), "tenant_id": tenant_id}
