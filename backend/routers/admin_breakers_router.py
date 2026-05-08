"""
Admin — Circuit Breaker Status
===============================
Live snapshot of all 6 AUREM breakers (mongodb, redis, openrouter,
twilio, resend, groq). State pulled from each breaker's Redis-backed
`CircuitRedisStorage`, so it survives pod restarts.

Admin-only. Safe to poll every 30 s from the Control Center widget.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/breakers", tags=["Admin Circuit Breakers"])


# Reuse the exact same admin verifier used by mission-control so behaviour
# stays consistent across admin endpoints.
async def _verify_admin(
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None),
):
    from routers.admin_mission_control_router import verify_admin
    return await verify_admin(authorization=authorization, x_admin_key=x_admin_key)


@router.get("/status")
async def breakers_status(admin=Depends(_verify_admin)):
    """Snapshot of every named breaker — state, fail_counter, thresholds."""
    try:
        from services.breakers import ALL_BREAKERS
    except Exception as e:
        raise HTTPException(500, f"breakers module import failed: {e}")

    out = []
    all_healthy = True
    for b in ALL_BREAKERS:
        try:
            state = b.current_state
            fail_count = b.fail_counter
            entry = {
                "name": b.name,
                "state": state,            # "closed" | "open" | "half-open"
                "fail_count": fail_count,
                "fail_max": b.fail_max,
                "reset_timeout": b.reset_timeout,
            }
        except Exception as e:
            entry = {"name": getattr(b, "name", "unknown"), "error": str(e)[:200]}
            state = "error"
        if state != "closed":
            all_healthy = False
        out.append(entry)

    return {
        "breakers": out,
        "all_healthy": all_healthy,
        "count": len(out),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["router"]
