"""
routers/cto_brief_router.py — iter D-58

HTTP surface for Daily Brief + Template Performance + Proactive ORA.
All endpoints admin-only (JWT super_admin / founder).

Endpoints:

  GET  /api/cto/brief/latest
  POST /api/cto/brief/run-now?kind=morning|evening
  GET  /api/cto/brief/list?limit=14

  GET  /api/cto/perf/templates?window_days=14
  POST /api/cto/perf/rotate-now
  GET  /api/cto/perf/state

  GET  /api/cto/proactive/config?tenant_id=global
  POST /api/cto/proactive/config        (toggle a rule)
  POST /api/cto/proactive/run-now?tenant_id=global
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cto", tags=["cto-brief"])


def set_db(database) -> None:
    from services import daily_brief as _db1
    from services import template_performance as _tp
    from services import proactive_ora as _pa
    _db1.set_db(database)
    _tp.set_db(database)
    _pa.set_db(database)


async def _require_admin(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    token = authorization.split(" ", 1)[1]
    try:
        import jwt as _jwt
        from config import JWT_SECRET, JWT_ALGORITHM
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if (payload.get("is_admin") or payload.get("is_super_admin") or
                payload.get("role") in ("admin", "super_admin", "founder")):
            return payload.get("email") or payload.get("sub") or "admin"
    except Exception:
        pass
    raise HTTPException(403, "admin_required")


# ── Daily Brief ─────────────────────────────────────────────────────

@router.get("/brief/latest")
async def brief_latest(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.daily_brief import latest_brief
    doc = await latest_brief()
    return {"ok": True, "brief": doc}


@router.get("/brief/list")
async def brief_list(limit: int = Query(14, ge=1, le=60),
                      authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.daily_brief import _db as _briefs_db
    if _briefs_db is None:
        return {"ok": True, "items": []}
    items = await _briefs_db.daily_briefs.find(
        {}, {"_id": 0, "text": 0},
    ).sort("generated_at", -1).limit(limit).to_list(limit)
    return {"ok": True, "items": items}


@router.post("/brief/run-now")
async def brief_run_now(kind: str = Query("morning",
                                            pattern="^(morning|evening)$"),
                        authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.daily_brief import send_morning_brief, send_evening_brief
    if kind == "morning":
        return await send_morning_brief()
    return await send_evening_brief()


# ── Template Performance ────────────────────────────────────────────

@router.get("/perf/templates")
async def perf_templates(window_days: int = Query(14, ge=1, le=120),
                          authorization: str = Header(None)
                          ) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.template_performance import stats_for
    rows = await stats_for(window_days=window_days)
    return {"ok": True, "items": rows, "window_days": window_days}


@router.post("/perf/rotate-now")
async def perf_rotate(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.template_performance import weekly_rotate
    state = await weekly_rotate()
    return {"ok": True, "state": state}


@router.get("/perf/state")
async def perf_state(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.template_performance import current_state
    return {"ok": True, "state": await current_state()}


# ── Proactive ORA ───────────────────────────────────────────────────

class ProactiveToggle(BaseModel):
    tenant_id: str = "global"
    rule:      str = Field(..., pattern="^R[1-4]$")
    enabled:   bool


@router.get("/proactive/config")
async def proactive_config(tenant_id: str = "global",
                            authorization: str = Header(None)
                            ) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.proactive_ora import get_config
    return {"ok": True, "config": await get_config(tenant_id)}


@router.post("/proactive/config")
async def proactive_set(body: ProactiveToggle,
                         authorization: str = Header(None)
                         ) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.proactive_ora import set_rule
    try:
        cfg = await set_rule(body.tenant_id, body.rule, body.enabled)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "config": cfg}


@router.post("/proactive/run-now")
async def proactive_run_now(tenant_id: str = Query("global"),
                              authorization: str = Header(None)
                              ) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.proactive_ora import run_all
    return await run_all(tenant_id=tenant_id)
