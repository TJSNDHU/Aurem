"""
ORA Composer health router — iter 282ai.

Exposes GET /api/admin/composer/health for the Pillars Map
Intelligence chip.
"""
from fastapi import APIRouter

from services.outreach_composer import composer_health

router = APIRouter(prefix="/api/admin/composer", tags=["composer"])


@router.get("/health")
async def composer_health_endpoint() -> dict:
    """Live probe — runs one compose_outreach(sms, step=1) against the LLM.

    Returns {ok, status: green|yellow|red, model, fallback_used, detail}.
    Pillars Map chip treats `yellow` as warning (LLM unreachable, fallback
    bodies still being served, so outreach isn't fully broken).
    """
    return await composer_health()
