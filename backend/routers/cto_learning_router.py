"""
routers/cto_learning_router.py — iter D-53

HTTP surface for the self-learning system. All endpoints are admin-only
and follow the same JWT-direct gate used by cto_tools / cto_verify.

  POST /api/developers/cto/learning/record
       body: {task_type, approach, result, verified_by, metadata?}
       → saves a learning row. Rejects with 403 if verified_by is NOT
         one of {"code_green","github_green","deploy_green",
                 "user_thumbs_up"} (no self-reporting allowed).

  GET  /api/developers/cto/learning/similar?task_type=…&limit=5
       → ranked list of approaches for that task_type.

  GET  /api/developers/cto/learning/confidence?task_type=…
       → {n, success_rate, best_approach} — used by the chat to render
         the confidence badge BEFORE the LLM replies.

  GET  /api/developers/cto/learning/stats
       → platform-wide totals.

  GET  /api/developers/cto/learning/weekly-report
       → most-recent weekly self-review.

  POST /api/developers/cto/learning/weekly-report/run-now
       (admin) → force-generate this week's report. Normally fires from
       a Sunday 02:00 UTC APScheduler job wired in registry.py.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/developers/cto/learning",
                    tags=["cto-learning"])


def set_db(database) -> None:
    from services import cto_learning as _svc
    _svc.set_db(database)


async def _require_admin(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    token = authorization.split(" ", 1)[1]
    try:
        import os as _os
        import jwt as _jwt
        from config import JWT_SECRET, JWT_ALGORITHM
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if (payload.get("is_admin") or payload.get("is_super_admin") or
                payload.get("role") in ("admin", "super_admin", "founder")):
            return payload.get("email") or payload.get("sub") or "admin"
    except Exception:
        pass
    raise HTTPException(403, "admin_required")


# ── Models ───────────────────────────────────────────────────────────

class RecordBody(BaseModel):
    task_type:   str = Field(..., min_length=2, max_length=80)
    approach:    str = Field(..., min_length=2, max_length=200)
    result:      str = Field(..., pattern="^(success|failure)$")
    verified_by: str = Field(..., min_length=2, max_length=40)
    metadata:    dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/record")
async def record(body: RecordBody,
                  authorization: str = Header(None)) -> dict[str, Any]:
    actor = await _require_admin(authorization)
    from services.cto_learning import record_outcome
    try:
        doc = await record_outcome(
            task_type=body.task_type, approach=body.approach,
            result=body.result, verified_by=body.verified_by,
            actor=actor, metadata=body.metadata,
        )
    except ValueError as e:
        # Self-report or invalid input — never silently swallow.
        raise HTTPException(403, str(e))
    return {"ok": True, **doc}


@router.get("/similar")
async def similar(task_type: str = Query(..., min_length=2, max_length=80),
                   limit: int = Query(5, ge=1, le=50),
                   authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.cto_learning import find_similar
    rows = await find_similar(task_type, limit=limit)
    return {"ok": True, "items": rows, "task_type": task_type}


@router.get("/confidence")
async def confidence(task_type: str = Query(..., min_length=2, max_length=80),
                      authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.cto_learning import confidence_for
    out = await confidence_for(task_type)
    return {"ok": True, "task_type": task_type, **out}


@router.get("/stats")
async def stats(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.cto_learning import overall_stats
    out = await overall_stats()
    return {"ok": True, **out}


@router.get("/weekly-report")
async def weekly_report(authorization: str = Header(None)
                         ) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.cto_learning import latest_weekly_report
    rpt = await latest_weekly_report()
    return {"ok": True, "report": rpt}


@router.post("/weekly-report/run-now")
async def weekly_report_run_now(authorization: str = Header(None)
                                  ) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.cto_learning import weekly_self_review
    return await weekly_self_review()
