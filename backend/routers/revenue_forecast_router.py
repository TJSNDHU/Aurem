"""
Revenue Forecast Router — API endpoints for 90-day revenue forecasting
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional

from utils.tenant import current_tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/revenue-forecast", tags=["Revenue Forecast"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.revenue_forecast import set_db as set_rf_db
    set_rf_db(database)


async def _get_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if _db is not None and user_id:
            user = await _db.users.find_one({"id": user_id}, {"_id": 0})
            if user and (user.get("is_admin") or user.get("role") == "admin"):
                return user
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/90day")
async def get_forecast(tenant_id: str = Depends(current_tenant), admin=Depends(_get_admin)):
    from services.revenue_forecast import compute_90day_forecast
    forecast = await compute_90day_forecast(tenant_id)
    return {"status": "ok", **forecast}


@router.get("/brief-line")
async def get_brief_line(tenant_id: str = Depends(current_tenant), admin=Depends(_get_admin)):
    from services.revenue_forecast import get_morning_brief_line
    line = await get_morning_brief_line(tenant_id)
    return {"status": "ok", "brief_line": line}


@router.get("/history")
async def forecast_history_api(tenant_id: str = Depends(current_tenant), limit: int = 10, admin=Depends(_get_admin)):
    from services.revenue_forecast import get_forecast_history
    history = await get_forecast_history(tenant_id, limit)
    return {"status": "ok", "history": history, "count": len(history)}
