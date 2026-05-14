"""
OpenRouter API — Model Routing Status & Testing
================================================

Exposes the zero-cost model routing infrastructure as REST endpoints.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import os
import jwt
import logging

router = APIRouter(prefix="/api/openrouter", tags=["openrouter"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database
    from services.openrouter_client import set_db as set_or_db
    set_or_db(database)


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


@router.get("/status")
async def openrouter_status(request: Request):
    """OpenRouter model routing status and configuration."""
    _get_user(request)
    from services.openrouter_client import get_routing_table

    table = get_routing_table()

    # Get model usage stats from audit chain
    stats = {}
    if _db is not None:
        try:
            pipeline = [
                {"$match": {"action": {"$regex": "^model_route_"}}},
                {"$group": {"_id": "$data.model", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ]
            async for doc in _db.audit_chain.aggregate(pipeline):
                stats[doc["_id"]] = doc["count"]
        except Exception:
            pass

    return {
        **table,
        "usage_stats": stats,
    }


class TestModelRequest(BaseModel):
    model: str = "stepfun/step-3.5-flash:free"
    prompt: str = "Respond with exactly: AUREM ONLINE"


@router.post("/test")
async def test_model(request: Request, body: TestModelRequest):
    """Test a specific OpenRouter model to verify connectivity."""
    _get_user(request)
    from services.openrouter_client import call_model

    result = await call_model(
        body.model,
        "You are a diagnostic assistant. Follow instructions exactly.",
        body.prompt,
        temperature=0.1,
        max_tokens=100,
    )
    return {
        "model_tested": body.model,
        "response": result.get("content", "")[:500],
        "provider": result.get("provider", "unknown"),
        "model_used": result.get("model", "unknown"),
        "success": bool(result.get("content")),
    }


@router.post("/test-consensus")
async def test_consensus(request: Request):
    """Test the dual-model Critic consensus validation."""
    _get_user(request)
    from services.openrouter_client import consensus_validate
    from services.critic_agent import CRITIC_VALIDATE_PROMPT

    test_input = """Agent: SCOUT
Intent: LEAD_SCORE
Output:
{"summary": "Scored 5 leads. Top: Acme Corp (A, 92), Beta Inc (B, 78)", "leads_scored": 5, "top_grade": "A"}

Review this output for Misinterpretations, Missing Corner Cases, Data Errors, Logic Gaps, and Brand Voice violations."""

    result = await consensus_validate(CRITIC_VALIDATE_PROMPT, test_input)
    return result
