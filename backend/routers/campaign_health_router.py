"""
routers/campaign_health_router.py — iter D-59

Admin endpoints for the Campaign Health page:

  GET  /api/admin/campaign/health            → live status of every
                                                  campaign-critical service
  POST /api/admin/campaign/autofix/{tag}      → run a single autofix
  POST /api/admin/campaign/autofix-all        → run every available
                                                  autofix from the
                                                  current report
  GET  /api/admin/campaign/autofix-log?limit  → audit trail
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/campaign", tags=["campaign-health"])


def set_db(database) -> None:
    from services import campaign_health as _ch
    from services import campaign_autofix as _af
    _ch.set_db(database)
    _af.set_db(database)


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


@router.get("/health")
async def health(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.campaign_health import full_report
    return await full_report()


@router.post("/autofix/{tag}")
async def autofix_one(tag: str = Path(..., min_length=2, max_length=40),
                       authorization: str = Header(None)
                       ) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.campaign_autofix import apply
    return await apply(tag)


@router.post("/autofix-all")
async def autofix_all(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.campaign_health import full_report
    from services.campaign_autofix import apply_all_from_report
    report = await full_report()
    return await apply_all_from_report(report.get("rows", []))


@router.get("/autofix-log")
async def autofix_log(limit: int = Query(50, ge=1, le=200),
                       authorization: str = Header(None)
                       ) -> dict[str, Any]:
    await _require_admin(authorization)
    from services import campaign_autofix as _af
    if _af._db is None:
        return {"ok": True, "items": []}
    items = await _af._db.campaign_autofix_log.find(
        {}, {"_id": 0},
    ).sort("ts", -1).limit(limit).to_list(limit)
    return {"ok": True, "items": items, "count": len(items)}
