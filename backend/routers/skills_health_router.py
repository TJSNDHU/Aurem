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
    """iter D-71f — defensive db lookup. During cold boot (when this
    is called by the warm-prober before `set_db` finishes wiring) the
    `import server` path could raise if the entry-point isn't named
    `server` in the deploy environment. Catch everything and fall
    through to `learning_engine_health(None)` which already returns a
    valid {ok:True, status:"grey"} response."""
    db = None
    try:
        import server as _srv  # type: ignore
        db = getattr(_srv, "db", None)
    except Exception:
        # Try the canonical motor client as a fallback so production
        # deployments that don't expose a global `db` still answer 200.
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            import os
            url = os.environ.get("MONGO_URL")
            name = os.environ.get("DB_NAME")
            if url and name:
                db = AsyncIOMotorClient(url, serverSelectionTimeoutMS=2000)[name]
        except Exception:
            db = None
    try:
        return await learning_engine_health(db)
    except Exception as e:
        # Never 500 a health endpoint — return a structured red instead.
        return {"ok": False, "status": "red", "detail": f"health probe crashed: {e}"}
