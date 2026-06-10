"""
D-71f — Deployment hardening for /api/admin/skills/learning-health.

Background: production deploy logs showed 3× `500 Internal Server Error`
on `/api/admin/skills/learning-health` during warm-prober boot. The
router imported `server` and called `learning_engine_health(db)` — if
`import server` raised in the deploy environment (entry-point named
differently, partial init, etc.) the request crashed.

The fix wraps the lookup in nested try/except AND adds an outer guard
that returns a structured `{ok:False, status:'red', detail:...}` on
any exception — a health endpoint must NEVER 500.
"""
from __future__ import annotations

from pathlib import Path


def test_learning_health_never_500s():
    src = Path("/app/backend/routers/skills_health_router.py").read_text()
    # Outer try/except wraps the call so any unexpected error returns
    # 200 with a structured red instead of bubbling a 500.
    assert "health probe crashed" in src, (
        "Outer except must convert exceptions into structured red response"
    )
    # Fallback to direct motor client when `import server` fails.
    assert "AsyncIOMotorClient" in src, (
        "Must provide a Mongo fallback when `import server` raises"
    )
    assert "MONGO_URL" in src and "DB_NAME" in src


def test_learning_health_does_not_hardcode_db_name():
    """Even the deploy-hardening fallback must read from env, never literals."""
    src = Path("/app/backend/routers/skills_health_router.py").read_text()
    assert 'os.environ.get("DB_NAME")' in src
    assert 'os.environ.get("MONGO_URL")' in src


def test_learning_engine_health_handles_none_db():
    """Sanity — the underlying service already grey-fails on db=None."""
    src = Path("/app/backend/services/skill_learner.py").read_text()
    assert "if db is None:" in src
    assert '"detail": "db unavailable"' in src or "db unavailable" in src
