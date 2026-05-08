"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Viral Gate Router — 7-Day Taste Strategy
=========================================
Endpoints for trial status, review submission, and unlock verification.
"""
import logging
import os
from fastapi import APIRouter, Depends, Header, HTTPException, Body

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/viral-gate", tags=["Viral Gate"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.viral_gate import set_db as set_vg_db
    set_vg_db(database)


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


@router.get("/status")
async def viral_gate_status(user=Depends(_get_user)):
    """Get current Social Brain trial/unlock status."""
    from services.viral_gate import get_viral_status
    tenant_id = user.get("tenant_id", "aurem_platform")
    return await get_viral_status(tenant_id)


@router.post("/start-trial")
async def start_trial(user=Depends(_get_user)):
    """Manually start the 7-day Social Brain trial."""
    from services.viral_gate import start_trial as do_start
    tenant_id = user.get("tenant_id", "aurem_platform")
    return await do_start(tenant_id)


@router.post("/review")
async def record_review(body: dict = Body(...), user=Depends(_get_user)):
    """Record Google review completion — permanently unlocks Social Brain.
    Body: {review_url?: '...'}
    """
    from services.viral_gate import record_review as do_review
    tenant_id = user.get("tenant_id", "aurem_platform")
    review_url = body.get("review_url", "")
    return await do_review(tenant_id, review_url)
