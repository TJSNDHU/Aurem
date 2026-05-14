"""
Critic Agent API
================

Exposes the 6th Agent (Critic) as REST endpoints.
Allows manual validation, adversarial reviews, and rescue triggers.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import os
import jwt
import logging

router = APIRouter(prefix="/api/critic", tags=["critic-agent"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database
    from services.critic_agent import set_db as set_critic_db
    set_critic_db(database)


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


class ValidateRequest(BaseModel):
    agent_id: str
    intent: str
    result: dict


class AdversarialRequest(BaseModel):
    data: dict
    context: str = "manual_review"


class RescueRequest(BaseModel):
    agent_id: str
    result: dict
    confidence: float


class ScoreRequest(BaseModel):
    content: str
    query: str = ""
    context: str = ""


class ParseltongueRequest(BaseModel):
    text: str
    technique: str = "leetspeak"
    intensity: str = "medium"


@router.post("/validate")
async def validate_output(request: Request, body: ValidateRequest):
    """Submit agent output for Critic validation."""
    _get_user(request)
    from services.critic_agent import validate_agent_output
    return await validate_agent_output(body.agent_id, body.intent, body.result)


@router.post("/adversarial")
async def adversarial_check(request: Request, body: AdversarialRequest):
    """Adversarial review — actively challenge the data."""
    _get_user(request)
    from services.critic_agent import adversarial_review
    return await adversarial_review(body.data, body.context)


@router.post("/rescue")
async def rescue_agent(request: Request, body: RescueRequest):
    """Trigger rescue fallback for low-confidence agent output."""
    _get_user(request)
    from services.critic_agent import rescue_fallback
    return await rescue_fallback(body.agent_id, body.result, body.confidence)


@router.get("/status")
async def critic_status(request: Request):
    """Critic Agent operational status and review history."""
    _get_user(request)
    if _db is None:
        return {"status": "OPERATIONAL", "reviews": 0, "rescues": 0}

    total_validates = await _db.audit_chain.count_documents(
        {"action": {"$regex": "^critic_validate"}}
    )
    total_adversarial = await _db.audit_chain.count_documents(
        {"action": {"$regex": "^critic_adversarial"}}
    )
    total_rescues = await _db.audit_chain.count_documents(
        {"action": {"$regex": "^critic_rescue"}}
    )

    return {
        "status": "OPERATIONAL",
        "agent": "critic",
        "role": "Zero-Trust Validation Layer (6th Agent)",
        "total_validations": total_validates,
        "total_adversarial_reviews": total_adversarial,
        "total_rescues": total_rescues,
        "modes": ["validate", "adversarial", "rescue", "ultraplinian", "parseltongue"],
        "g0dm0d3": {
            "ultraplinian": "5-Axis Composite Scorer (100pt)",
            "parseltongue": "Adversarial Red-Team Engine (6 techniques x 3 intensities)",
        },
    }


@router.post("/ultraplinian")
async def ultraplinian_score(request: Request, body: ScoreRequest):
    """Run ULTRAPLINIAN 5-axis scoring on arbitrary content."""
    _get_user(request)
    from services.ultraplinian_scorer import score_response, score_for_envoy_gate
    result = score_response(body.content, body.query, body.context)
    envoy = score_for_envoy_gate(body.content, body.query)
    result["envoy_pass"] = envoy["envoy_pass"]
    result["envoy_threshold"] = envoy["threshold"]
    return result


@router.post("/parseltongue")
async def parseltongue_transform(request: Request, body: ParseltongueRequest):
    """Run Parseltongue adversarial transformation on text."""
    _get_user(request)
    from services.parseltongue import transform
    return transform(body.text, body.technique, body.intensity)


@router.post("/parseltongue/suite")
async def parseltongue_full_suite(request: Request, body: ParseltongueRequest):
    """Run full Parseltongue adversarial suite (all techniques x all intensities)."""
    _get_user(request)
    from services.parseltongue import run_adversarial_suite
    return run_adversarial_suite(body.text)
