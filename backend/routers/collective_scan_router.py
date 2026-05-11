"""
Collective Scan Router — iter 322ar
====================================
REST surface for the 25-agent collective scanner.

  POST  /api/admin/collective-scan/run         — force a cycle now
  GET   /api/admin/collective-scan/last        — most recent cycle summary
  GET   /api/admin/collective-scan/recent      — last N cycles (default 10)
  GET   /api/admin/collective-scan/dependency-map — static map (for UI)
"""

from __future__ import annotations

import logging
import os
from fastapi import APIRouter, HTTPException, Request

try:
    import jwt
except Exception:
    jwt = None

from services import collective_scanner
from services.agent_dependency_map import ALL_AGENTS, DEPENDENCY_MAP

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/collective-scan", tags=["collective-scan"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    collective_scanner.set_db(database)


async def _require_admin(request: Request) -> dict:
    """Same dual-mode resolver as admin_bin_detail_router (email-or-user_id)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    if jwt is None:
        raise HTTPException(503, "jwt module unavailable")
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
    try:
        claims = jwt.decode(auth[7:], secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    email = (claims.get("email") or "").lower()
    user_id = claims.get("user_id") or claims.get("sub") or claims.get("id")
    if _db is None:
        raise HTTPException(503, "DB not ready")
    if email:
        user = await _db.users.find_one(
            {"email": email},
            {"_id": 0, "email": 1, "is_admin": 1, "is_super_admin": 1, "role": 1},
        )
    elif user_id:
        user = await _db.users.find_one(
            {"$or": [{"id": user_id}, {"user_id": user_id}]},
            {"_id": 0, "email": 1, "is_admin": 1, "is_super_admin": 1, "role": 1},
        )
    else:
        user = None
    if not user or not (
        user.get("is_admin") or user.get("is_super_admin")
        or user.get("role") in ("admin", "super_admin")
    ):
        raise HTTPException(403, "Admin access required")
    return {"email": email or user.get("email", "")}


@router.post("/run")
async def run_now(request: Request):
    """Force-trigger one collective scan cycle (founder-only)."""
    await _require_admin(request)
    summary = await collective_scanner.run_cycle(triggered_by="manual")
    return _sanitize(summary)


@router.get("/last")
async def get_last(request: Request):
    await _require_admin(request)
    doc = await collective_scanner.get_last_result()
    if not doc:
        return {"ok": True, "exists": False}
    return {"ok": True, "exists": True, "result": _sanitize(doc)}


@router.get("/recent")
async def get_recent(request: Request, limit: int = 10):
    await _require_admin(request)
    rows = await collective_scanner.get_recent_cycles(min(max(int(limit), 1), 50))
    return {"ok": True, "count": len(rows), "results": [_sanitize(r) for r in rows]}


@router.get("/dependency-map")
async def get_dep_map(request: Request):
    await _require_admin(request)
    return {
        "ok": True,
        "agents": ALL_AGENTS,
        "map": {
            a: {
                "feeds": d.get("feeds", []),
                "depends_on": d.get("depends_on", []),
            }
            for a, d in DEPENDENCY_MAP.items()
        },
    }


@router.get("/ora-stats")
async def ora_self_sufficiency_stats(request: Request, days: int = 30):
    """iter 322ar — ORA self-sufficiency tile data:
    ratio of free-source fixes vs paid (Emergent) plus running $ saved."""
    await _require_admin(request)
    from services.fix_learning_pipeline import (
        ora_self_sufficiency, fix_patterns_summary,
    )
    stats = await ora_self_sufficiency(days=min(max(int(days), 1), 365))
    patterns = await fix_patterns_summary()
    return {"ok": True, "stats": _sanitize(stats), "patterns": _sanitize(patterns)}


def _sanitize(doc):
    """Strip datetime objects → ISO strings so FastAPI JSON-serialises cleanly."""
    if isinstance(doc, dict):
        return {k: _sanitize(v) for k, v in doc.items() if k != "_id"}
    if isinstance(doc, list):
        return [_sanitize(x) for x in doc]
    try:
        from datetime import datetime as _dt
        if isinstance(doc, _dt):
            return doc.isoformat()
    except Exception:
        pass
    return doc
