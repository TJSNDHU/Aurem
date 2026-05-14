"""
ORA Dispatcher API
==================

Exposes the dispatcher as REST endpoints so the frontend (and ORA chat)
can trigger agent delegation, refresh daily summaries, and query the
lean context.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import os
import jwt
import logging

router = APIRouter(prefix="/api/ora", tags=["ora-dispatcher"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database
    from services.ora_dispatcher import set_db as set_dispatcher_db
    set_dispatcher_db(database)


def _get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth.split(" ", 1)[1]
    secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


class DispatchRequest(BaseModel):
    message: str
    params: dict = {}


class SummaryRefreshRequest(BaseModel):
    force: bool = False


# ═══════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════

@router.post("/dispatch")
async def dispatch_intent(request: Request, body: DispatchRequest):
    """
    Classify user message and dispatch to the appropriate agent.
    Returns classification + agent execution result.
    """
    _get_user(request)

    from services.ora_dispatcher import classify_intent, dispatch

    classification = classify_intent(body.message)

    if not classification["should_delegate"]:
        return {
            "dispatched": False,
            "classification": classification,
            "message": "No delegation needed — ORA will handle conversationally.",
        }

    result = await dispatch(
        intent=classification["intent"],
        agent_id=classification["agent"],
        params=body.params,
    )

    return {
        "dispatched": True,
        "classification": classification,
        "execution": result,
    }


@router.get("/summary")
async def get_daily_summary(request: Request):
    """Get today's pre-computed daily business summary."""
    _get_user(request)

    from services.ora_dispatcher import get_daily_summary

    summary = await get_daily_summary()
    if not summary:
        raise HTTPException(500, "Could not generate daily summary")

    return summary


@router.post("/summary/refresh")
async def refresh_daily_summary(request: Request):
    """Force-regenerate the daily summary."""
    _get_user(request)

    from services.ora_dispatcher import generate_daily_summary

    summary = await generate_daily_summary()
    return {"refreshed": True, "summary": summary}


@router.post("/classify")
async def classify_message(request: Request, body: DispatchRequest):
    """Classify a message without executing — for UI preview."""
    _get_user(request)

    from services.ora_dispatcher import classify_intent

    return classify_intent(body.message)
