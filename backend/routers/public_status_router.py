"""
AUREM Public Status router (iter 322m Day 5+ — Sales-Leverage)
==============================================================
Two **unauthenticated** read-only endpoints:

  - ``GET /api/public/status``           → full sanitized JSON
  - ``GET /api/public/status/badge.json`` → shields.io-compatible payload

Both are cached for 60s in-process (single-instance TTL cache) so a
traffic spike on a public link never thrashes Mongo.

The payload is sanitized in `services/public_status_aggregator.py` —
this router is a thin HTTP adapter, no business logic.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter

from services.public_status_aggregator import build_public_status

router = APIRouter(prefix="/api/public", tags=["public-status"])

_db = None
_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
_CACHE_TTL_S = 60


def set_db(database) -> None:
    global _db
    _db = database


async def _cached_payload() -> Dict[str, Any]:
    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL_S:
        return _cache["data"]
    data = await build_public_status(_db)
    _cache.update({"data": data, "ts": now})
    return data


@router.get("/status")
async def public_status() -> Dict[str, Any]:
    """Public Sovereign-Status payload (no auth, 60s cache)."""
    return await _cached_payload()


_BADGE_COLOR_MAP = {
    "green": "brightgreen",
    "yellow": "yellow",
    "red": "red",
}


@router.get("/status/badge.json")
async def public_status_badge() -> Dict[str, Any]:
    """Shields.io endpoint badge — drop the URL into any README:

        ![status](https://img.shields.io/endpoint?url=https%3A%2F%2Faurem.live%2Fapi%2Fpublic%2Fstatus%2Fbadge.json)
    """
    data = await _cached_payload()
    autonomy = data.get("system_autonomy_pct", 0.0)
    color = _BADGE_COLOR_MAP.get(data.get("badge_color", "yellow"), "yellow")
    return {
        "schemaVersion": 1,
        "label": "AUREM Autonomy",
        "message": f"{autonomy:.2f}%",
        "color": color,
    }
