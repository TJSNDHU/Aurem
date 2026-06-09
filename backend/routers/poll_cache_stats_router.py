"""
poll_cache_stats_router.py — D-71 perf observability.

Exposes the in-memory poll cache for ops visibility. Admin-only.

  GET  /api/admin/poll-cache/stats      → live key list + TTL remaining
  POST /api/admin/poll-cache/invalidate → drop key or prefix (force refresh)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from services.poll_cache import stats, invalidate, invalidate_prefix, tune, reset_tune
from utils.admin_guard import verify_admin

router = APIRouter(prefix="/api/admin/poll-cache", tags=["Poll Cache Ops"])


@router.get("/stats")
async def get_stats(authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    return {"ok": True, **stats()}


class InvalidateBody(BaseModel):
    key: Optional[str] = None
    prefix: Optional[str] = None


@router.post("/invalidate")
async def invalidate_cache(body: InvalidateBody, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    if not body.key and not body.prefix:
        raise HTTPException(400, "Provide either 'key' or 'prefix'")
    removed = 0
    if body.key:
        invalidate(body.key)
        removed += 1
    if body.prefix:
        removed += invalidate_prefix(body.prefix)
    return {"ok": True, "removed": removed}


class TuneBody(BaseModel):
    key: str
    multiplier: float = 2.0


@router.post("/tune")
async def tune_cache(body: TuneBody, authorization: Optional[str] = Header(None)):
    """Bump a cache key's effective TTL by `multiplier` (default 2x).

    Used by the admin sidebar auto-tune button when an endpoint's
    hit-rate drops under 40%. One call per endpoint, no code change.
    Returns the new effective TTL.
    """
    verify_admin(authorization)
    # Defence in depth — clamp the multiplier so a fat-finger doesn't
    # set a 1000x TTL.
    multiplier = max(1.1, min(10.0, float(body.multiplier)))
    result = tune(body.key, multiplier=multiplier)
    if not result.get("ok"):
        # unknown_key — return 404 so the UI can show "no data yet, poll once first"
        raise HTTPException(404, result.get("reason", "tune failed"))
    return result


class ResetTuneBody(BaseModel):
    key: str


@router.post("/reset-tune")
async def reset_tune_cache(body: ResetTuneBody, authorization: Optional[str] = Header(None)):
    """Remove a tuned TTL override, falling back to the developer default."""
    verify_admin(authorization)
    return reset_tune(body.key)
