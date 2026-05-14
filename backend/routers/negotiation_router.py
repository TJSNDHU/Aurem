"""
AgenticPay Negotiation Router — 5-round buyer/seller negotiation
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header, Body
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/negotiate", tags=["Negotiation"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.negotiation_engine import set_db as ne_set_db
    ne_set_db(database)


async def _get_auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


class StartNegotiationRequest(BaseModel):
    buyer_agent_id: str = "default_buyer"
    product_ids: list = []
    quantities: list = []
    proposed_discount_pct: float = 5.0
    justification: str = ""


class CounterOfferRequest(BaseModel):
    proposed_discount_pct: float
    justification: str = ""


@router.post("/start")
async def start_negotiation(body: StartNegotiationRequest, auth=Depends(_get_auth)):
    """Start a new 5-round negotiation session."""
    tenant_id = auth.get("tenant_id", auth.get("user_id", "default"))
    from services.negotiation_engine import start_negotiation
    result = await start_negotiation(
        tenant_id=tenant_id,
        buyer_agent_id=body.buyer_agent_id,
        product_ids=body.product_ids,
        quantities=body.quantities,
        initial_discount_pct=body.proposed_discount_pct,
        justification=body.justification,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok", **result}


@router.post("/{session_id}/counter")
async def counter_offer(session_id: str, body: CounterOfferRequest, auth=Depends(_get_auth)):
    """Buyer counters with a new discount proposal."""
    from services.negotiation_engine import counter_offer
    result = await counter_offer(
        session_id=session_id,
        proposed_discount_pct=body.proposed_discount_pct,
        justification=body.justification,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok", **result}


@router.post("/{session_id}/accept")
async def accept_offer(session_id: str, auth=Depends(_get_auth)):
    """Buyer accepts the seller's current offer."""
    from services.negotiation_engine import accept_final_offer
    result = await accept_final_offer(session_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok", **result}


@router.get("/{session_id}")
async def get_session(session_id: str, auth=Depends(_get_auth)):
    """Get full negotiation session with all rounds."""
    from services.negotiation_engine import get_session
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok", "session": session}


@router.get("/sessions/recent")
async def recent_sessions(limit: int = 20, auth=Depends(_get_auth)):
    """Get recent negotiation sessions for current tenant."""
    tenant_id = auth.get("tenant_id", auth.get("user_id", "default"))
    from services.negotiation_engine import get_tenant_sessions
    sessions = await get_tenant_sessions(tenant_id, limit)
    return {"status": "ok", "sessions": sessions, "count": len(sessions)}
