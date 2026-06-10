"""
routers/creds_health_router.py — iter D-75 Part 2 #1.

Admin surface for the `creds_health` live-probe system.

Endpoints (admin-only, audited via `creds_health_history`):

  GET  /api/admin/creds-health/probe-all
       Probe every registered provider in parallel (~5s wall clock).
       Returns: { ok, results: [ProbeResult, ...], summary }
       Writes a snapshot row per provider to `creds_health_history`.

  POST /api/admin/creds-health/probe/{provider}
       On-demand probe of one specific provider (the "Test Connection"
       button in the dashboard). Writes one history row.

  GET  /api/admin/creds-health/history?provider=<name>&limit=20
       Recent probe results for trend display. Read-only.

  GET  /api/admin/creds-health/providers
       Lightweight list of provider names (for the UI dropdown / row
       seeding before the first probe completes).

No mocks anywhere. Every status comes from a real HTTP round-trip.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import jwt
from fastapi import APIRouter, HTTPException, Header, Path

from services import creds_health as ch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/creds-health", tags=["Creds Health"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


async def _require_admin(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET not configured")
    try:
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from None
    is_admin = bool(
        payload.get("is_admin")
        or payload.get("is_super_admin")
        or payload.get("role") in ("admin", "super_admin")
    )
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return payload.get("email") or "unknown"


def _summarize(results: list[ch.ProbeResult]) -> dict[str, int]:
    summary = {"green": 0, "yellow": 0, "red": 0, "not_configured": 0}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    return summary


@router.get("/providers")
async def list_providers_endpoint(authorization: str = Header(None)) -> dict[str, Any]:
    """Bare provider list — used by the dashboard to render empty rows
    before the first probe completes."""
    await _require_admin(authorization)
    return {"ok": True, "providers": ch.list_providers()}


@router.get("/probe-all")
async def probe_all_endpoint(timeout: float = 6.0,
                             authorization: str = Header(None)) -> dict[str, Any]:
    """Fan-out probe — all providers in parallel. Bounded by `timeout`
    per-provider; total wall time ≈ `timeout` (not sum)."""
    admin_email = await _require_admin(authorization)
    timeout = max(2.0, min(float(timeout), 15.0))

    started_at = datetime.now(timezone.utc).isoformat()
    results = await ch.probe_all(timeout=timeout)

    # Persist snapshot (best-effort)
    if _db is not None:
        await ch.write_history(_db, results)

    body = {
        "ok": True,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "probed_by": admin_email,
        "results": [r.asdict() for r in results],
        "summary": _summarize(results),
        "providers_total": len(results),
    }
    return body


@router.post("/probe/{provider}")
async def probe_one_endpoint(
    provider: str = Path(..., min_length=1, max_length=40),
    timeout: float = 6.0,
    authorization: str = Header(None),
) -> dict[str, Any]:
    """On-demand single-provider probe — the dashboard's `Test
    Connection` button. Always writes one history row, even on red.
    """
    admin_email = await _require_admin(authorization)
    timeout = max(2.0, min(float(timeout), 15.0))

    if provider not in ch.list_providers():
        raise HTTPException(
            status_code=404,
            detail=f"unknown_provider:{provider} — known: {ch.list_providers()}",
        )

    result = await ch.probe_one(provider, timeout=timeout)
    if _db is not None:
        await ch.write_history(_db, [result])
    return {
        "ok": True,
        "probed_by": admin_email,
        "result": result.asdict(),
    }


@router.get("/history")
async def history_endpoint(
    provider: Optional[str] = None,
    limit: int = 50,
    authorization: str = Header(None),
) -> dict[str, Any]:
    """Recent probe results — trend data for the dashboard chart."""
    await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")
    limit = max(1, min(int(limit), 500))

    flt: dict[str, Any] = {}
    if provider:
        flt["provider"] = provider

    rows: list[dict[str, Any]] = []
    cursor = _db.creds_health_history.find(flt, {"_id": 0}).sort(
        "snapshot_at", -1,
    ).limit(limit)
    async for doc in cursor:
        # snapshot_at is BSON Date; isoformat for JSON
        snap = doc.get("snapshot_at")
        if hasattr(snap, "isoformat"):
            doc["snapshot_at"] = snap.isoformat()
        rows.append(doc)

    return {"ok": True, "rows": rows, "count": len(rows),
            "provider_filter": provider}
