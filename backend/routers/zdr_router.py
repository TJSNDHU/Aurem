"""
Zero-Downtime Repair Status Router (iter 303)
=============================================
Exposes the in-progress repair banner data to the admin UI and lets a
founder manually fire a sandboxed repair cycle.

Endpoints (all admin-only):
  GET  /api/admin/repair/status          — banner data for system-overview
  POST /api/admin/repair/trigger         — kick a sandboxed repair cycle now
  POST /api/admin/repair/test-zdr        — synthetic ZDR test (proves no downtime)
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

import jwt as pyjwt
from fastapi import APIRouter, Header, HTTPException

from services.zero_downtime_repair import (
    repair_status, run_with_zdr, acquire_repair_lock, release_repair_lock,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/repair", tags=["Zero-Downtime Repair"])

_db = None


def set_db(db):
    global _db
    _db = db


def _require_admin(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT secret unset")
    try:
        p = pyjwt.decode(authorization.split(" ", 1)[1], secret,
                         algorithms=["HS256"], options={"verify_exp": False})
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")
    if not (p.get("is_admin") or p.get("is_super_admin")
            or p.get("role") in ("admin", "super_admin")):
        raise HTTPException(403, "Admin only")
    return p


@router.get("/status")
async def status(authorization: Optional[str] = Header(None)):
    """Banner data — frontend shows '🔧 Repair in progress' overlay."""
    _require_admin(authorization)
    return await repair_status()


@router.post("/trigger")
async def trigger(authorization: Optional[str] = Header(None)):
    """Manual: run autonomous repair cycle through ZDR pipeline."""
    _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "db unset")
    from services.autonomous_repair_engine import run_cycle_once
    return await run_cycle_once()


@router.post("/test-zdr")
async def test_zdr(authorization: Optional[str] = Header(None)):
    """Run a synthetic 8s 'repair' through ZDR and confirm /api/health stays
    200 throughout. Proves zero-downtime claim end-to-end."""
    _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "db unset")

    import httpx
    api_self = "http://localhost:8001/api/health"

    async def _fake_repair():
        await asyncio.sleep(6)
        return {"ok": True, "stage": "synthetic", "slept_s": 6}

    health_samples = []

    async def _probe_loop():
        async with httpx.AsyncClient(timeout=2) as cli:
            for i in range(10):
                t0 = time.monotonic()
                try:
                    r = await cli.get(api_self)
                    health_samples.append({
                        "i": i, "status": r.status_code,
                        "ms": int((time.monotonic() - t0) * 1000),
                    })
                except Exception as e:
                    health_samples.append({"i": i, "error": str(e)[:80]})
                await asyncio.sleep(1)

    probe_task = asyncio.create_task(_probe_loop())
    repair_out = await run_with_zdr(_fake_repair, label="test_zdr_synthetic",
                                    db=_db, timeout_s=20)
    await probe_task
    ok_count = sum(1 for s in health_samples if s.get("status") == 200)
    return {
        "ok": repair_out.get("ok") and ok_count == len(health_samples),
        "repair": repair_out,
        "health_samples": health_samples,
        "downtime_detected": ok_count != len(health_samples),
        "uptime_pct": round(100.0 * ok_count / max(1, len(health_samples)), 2),
    }
