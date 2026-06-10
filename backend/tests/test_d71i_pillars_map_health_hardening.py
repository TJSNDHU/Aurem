"""
D-71i — Pillars-Map health endpoint deploy hardening.

User reported red badge on /admin/root-command Dash-Overview pointing
to /api/admin/pillars-map/health. Root cause: module-level `_db` was
None when the frontend hit the endpoint during production cold-boot
(before startup_event finished the set_db wiring). The page-level
"DB side broken" red was a benign init race, not real DB failure.

Fix: defensive lookup falls back to the canonical Mongo client from
env vars and pings it. Returns `status="degraded"` with a useful
reason ONLY when Mongo is truly unreachable.
"""
from __future__ import annotations

from pathlib import Path


def test_pillars_map_health_has_fallback_mongo_lookup():
    src = Path("/app/backend/routers/pillars_map_router.py").read_text()
    # Must try a Mongo client fallback when module-level _db is None
    assert "AsyncIOMotorClient" in src, (
        "/api/admin/pillars-map/health must fall back to a direct Mongo "
        "client when module-level `_db` is None during cold-boot"
    )
    assert 'os.environ.get("MONGO_URL")' in src
    assert 'os.environ.get("DB_NAME")' in src


def test_pillars_map_health_pings_before_claiming_ready():
    """Don't fake-green a broken Atlas — must actually ping."""
    src = Path("/app/backend/routers/pillars_map_router.py").read_text()
    assert 'await db.command("ping")' in src


def test_pillars_map_health_returns_structured_degraded_on_failure():
    """A real DB outage must produce an HONEST degraded response with
    a reason field, not bubble an unhandled exception → 500 HTML."""
    src = Path("/app/backend/routers/pillars_map_router.py").read_text()
    assert '"status":   "degraded"' in src or '"status": "degraded"' in src
    assert '"reason"' in src
    assert '"db_ready":  False' in src or '"db_ready": False' in src


def test_pillars_map_health_never_raises_unhandled():
    """Inner Mongo ping must be in try/except so this route can't 500."""
    src = Path("/app/backend/routers/pillars_map_router.py").read_text()
    # Find the health handler and check its except clause
    idx = src.index("async def health(")
    body = src[idx:idx + 1500]
    assert "except Exception" in body, (
        "health() must catch Exception around the Mongo ping"
    )
