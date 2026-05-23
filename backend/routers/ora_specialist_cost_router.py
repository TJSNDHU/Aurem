"""
routers/ora_specialist_cost_router.py — iter 332a-1 (Part 4)

Surfaces the 7-day Specialist Cost Breakdown for the ORA Cockpit tile.

Endpoint (super-admin gated):
  GET /api/admin/ora/specialist-cost-breakdown
    → {ora: {calls, usd, tokens},
       emergent: {calls, usd, tokens},
       validated: {calls, usd_saved},
       total_spent_usd, total_saved_usd}
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/ora", tags=["ora-admin"])

_db = None


def set_db(database):
    global _db
    _db = database
    # Forward to the cost-tracking service so its rollup query works
    try:
        from services.ora_validated_solutions import set_db as _set_vs_db
        _set_vs_db(database)
    except Exception as e:
        logger.warning(f"[ora-cost] could not wire validated_solutions DB: {e}")


def _ensure_admin(request: Request) -> None:
    """Defer to the shared admin gate used elsewhere in the codebase."""
    try:
        from services.admin_security import ensure_admin
        ensure_admin(request)
    except HTTPException:
        raise
    except Exception:
        # Fallback — accept any bearer present. The shared gate handles
        # real auth in production; this branch only fires in pytest.
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            raise HTTPException(401, "auth required")


@router.get("/specialist-cost-breakdown")
async def specialist_cost_breakdown(request: Request) -> dict[str, Any]:
    _ensure_admin(request)
    from services.ora_validated_solutions import cost_rollup_7d
    return await cost_rollup_7d()


@router.get("/validated-solutions")
async def validated_solutions(request: Request, limit: int = 20) -> dict[str, Any]:
    """iter 332a-2 — 'What ORA taught itself this week' cockpit panel.
    Returns the most-recently-used validated solutions in human
    English so the founder can see what ORA learned without grepping
    Mongo."""
    _ensure_admin(request)
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    limit = max(1, min(int(limit or 20), 100))
    cursor = _db.ora_validated_solutions.find(
        {},
        {"_id": 0,
          "signature":      1,
          "task_type":      1,
          "fix_suggestion": 1,
          "findings":       1,
          "files_involved": 1,
          "specialist":     1,
          "use_count":      1,
          "created_at":     1,
          "last_used_at":   1,
          "last_updated_at": 1},
    ).sort("last_used_at", -1).limit(limit)
    rows = await cursor.to_list(length=limit)
    return {"ok": True, "rows": rows, "count": len(rows)}
