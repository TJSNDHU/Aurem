"""
High-Signal API — STM + AutoTune Endpoints
===========================================

Exposes G0DM0D3-ported modules as REST endpoints.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import os
import jwt
import logging

router = APIRouter(prefix="/api/highsignal", tags=["high-signal"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database
    from services.autotune_service import set_db as set_at_db
    set_at_db(database)


def _get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth.split(" ", 1)[1]
    secret = os.environ.get("JWT_SECRET", "")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


# ═══════════════════════════════════════════════════
# STM ENDPOINTS
# ═══════════════════════════════════════════════════

class STMRequest(BaseModel):
    text: str
    modules: List[str] = ["hedge_reducer", "direct_mode"]


@router.post("/stm/transform")
async def transform_text(request: Request, body: STMRequest):
    """Apply STM pipeline to text."""
    _get_user(request)
    from services.stm_service import apply_stm
    return apply_stm(body.text, body.modules)


# ═══════════════════════════════════════════════════
# AUTOTUNE ENDPOINTS
# ═══════════════════════════════════════════════════

class AutoTuneRequest(BaseModel):
    message: str
    conversation_history: Optional[list] = None


@router.post("/autotune/analyze")
async def analyze_context(request: Request, body: AutoTuneRequest):
    """Classify context and compute optimal LLM parameters."""
    _get_user(request)
    from services.autotune_service import compute_autotune_params
    return await compute_autotune_params(
        body.message,
        body.conversation_history,
    )


class FeedbackRequest(BaseModel):
    context: str
    rating: int  # +1 or -1
    params_used: dict
    response_text: str = ""


@router.post("/autotune/feedback")
async def submit_feedback(request: Request, body: FeedbackRequest):
    """Submit thumbs up/down for EMA parameter learning."""
    _get_user(request)

    if body.rating not in (1, -1):
        raise HTTPException(400, "Rating must be 1 (thumbs up) or -1 (thumbs down)")

    from services.autotune_service import record_feedback
    return await record_feedback(
        body.context,
        body.rating,
        body.params_used,
        body.response_text,
    )


@router.get("/autotune/profiles")
async def get_profiles(request: Request):
    """Get current parameter profiles and EMA learning status."""
    _get_user(request)

    from services.autotune_service import PARAMETER_PROFILES

    ema_profiles = {}
    if _db is not None:
        cursor = _db.ema_profiles.find({}, {"_id": 0})
        async for profile in cursor:
            ctx = profile.get("context", "unknown")
            ema_profiles[ctx] = {
                "sample_count": profile.get("sample_count", 0),
                "has_learned": profile.get("sample_count", 0) >= 3,
            }

    return {
        "base_profiles": PARAMETER_PROFILES,
        "ema_learning": ema_profiles,
    }
