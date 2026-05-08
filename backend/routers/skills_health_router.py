"""
Skills health router — iter 282ak.

  GET /api/admin/skills/health             — route + files probe (chip 1)
  GET /api/admin/skills/learning-health    — Learning Engine freshness (chip 2)
"""
from fastapi import APIRouter

from services.skill_learner import learning_engine_health
from services.skill_router import skills_router_health

router = APIRouter(prefix="/api/admin/skills", tags=["skills"])


@router.get("/health")
async def skills_health() -> dict:
    return await skills_router_health()


@router.get("/learning-health")
async def skills_learning_health() -> dict:
    try:
        import server as _srv  # type: ignore
        db = getattr(_srv, "db", None)
    except Exception:
        db = None
    return await learning_engine_health(db)
