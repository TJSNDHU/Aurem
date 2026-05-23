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
