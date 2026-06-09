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

from services.poll_cache import stats, invalidate, invalidate_prefix
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
