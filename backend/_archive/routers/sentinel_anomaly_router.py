"""
Sentinel Anomaly Router — API endpoints for anomaly detection
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header, Body
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sentinel-anomaly", tags=["Sentinel Anomaly"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.sentinel_anomaly import set_db as set_sa_db
    set_sa_db(database)


async def _get_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if _db is not None and user_id:
            user = await _db.users.find_one({"id": user_id}, {"_id": 0})
            if user and (user.get("is_admin") or user.get("role") == "admin"):
                return user
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/scan")
async def run_anomaly_scan(body: dict = Body({}), admin=Depends(_get_admin)):
    tenant_id = body.get("tenant_id", "aurem_platform")
    from services.sentinel_anomaly import run_anomaly_detection
    result = await run_anomaly_detection(tenant_id)
    return {"status": "ok", **result}


@router.get("/history")
async def anomaly_history_api(tenant_id: Optional[str] = None, limit: int = 20, admin=Depends(_get_admin)):
    from services.sentinel_anomaly import get_anomaly_history
    history = await get_anomaly_history(tenant_id, limit)
    return {"status": "ok", "history": history, "count": len(history)}


@router.get("/stats")
async def anomaly_stats_api(tenant_id: Optional[str] = None, admin=Depends(_get_admin)):
    from services.sentinel_anomaly import get_anomaly_stats
    stats = await get_anomaly_stats(tenant_id)
    return {"status": "ok", **stats}
