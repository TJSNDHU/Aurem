"""
routers/bug_catch_router.py — iter D-60

Admin-only bug capture endpoints (BugCatch).

All require admin Bearer JWT:
  POST   /api/admin/bug-reports                 submit (widget calls this)
  GET    /api/admin/bug-reports?status=&limit=  list  (no heavy fields)
  GET    /api/admin/bug-reports/stats           counts per status
  GET    /api/admin/bug-reports/{id}            full detail (screenshot + logs)
  PATCH  /api/admin/bug-reports/{id}/status     set status
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/bug-reports",
                    tags=["bug-catch"])


def set_db(database) -> None:
    from services import bug_catch as _svc
    _svc.set_db(database)


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


class BugReportBody(BaseModel):
    description:    str    = Field("", max_length=4000)
    severity:       str    = Field("med", max_length=10)
    screenshot_b64: str    = Field("", max_length=3_000_000)  # ~2.2 MB raw
    url:            str    = Field("", max_length=400)
    viewport:       dict   = Field(default_factory=dict)
    user_agent:     str    = Field("", max_length=400)
    console_logs:   list   = Field(default_factory=list)
    network_calls:  list   = Field(default_factory=list)
    annotations:    list   = Field(default_factory=list)


class StatusBody(BaseModel):
    status: str = Field(..., max_length=20)


@router.post("")
async def submit(body: BugReportBody,
                  authorization: str = Header(None)) -> dict[str, Any]:
    email = await _require_admin(authorization)
    from services.bug_catch import create_report
    try:
        return {"ok": True,
                 "report": await create_report(body.model_dump(),
                                                submitted_by=email)}
    except Exception as e:
        logger.exception("[bugcatch] submit failed")
        raise HTTPException(500, f"submit_failed: {type(e).__name__}: {e}")


@router.get("")
async def list_all(status: str = Query("", max_length=20),
                    limit: int = Query(50, ge=1, le=200),
                    authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.bug_catch import list_reports
    return {"ok": True, "items": await list_reports(status=status, limit=limit)}


@router.get("/stats")
async def stats(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.bug_catch import stats as _st
    return {"ok": True, "stats": await _st()}


@router.get("/{report_id}")
async def detail(report_id: str = Path(..., min_length=4, max_length=40),
                   authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.bug_catch import get_report
    r = await get_report(report_id)
    if not r:
        raise HTTPException(404, "not_found")
    return {"ok": True, "report": r}


@router.patch("/{report_id}/status")
async def set_status(body: StatusBody,
                      report_id: str = Path(..., min_length=4, max_length=40),
                      authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.bug_catch import set_status as _ss
    return await _ss(report_id, body.status)
