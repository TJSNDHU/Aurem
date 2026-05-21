"""
Health Warm-Prober Cron
=======================
Pings internal `/api/health` every 90s so cold-start never hits a
real customer's browser. K8s pod warm-up takes 15-25s on first request
to heavy routers (auth, catalog, etc.) — this keeps the FastAPI worker
+ Mongo client + jit-loaded modules in a hot state at all times.

Notes:
  • Calls localhost:8001 (internal, bypasses ingress, no DNS, no cost).
  • Failure is logged but never crashes the scheduler.
  • Disabled cleanly via AUREM_WARM_PROBER_DISABLED=1 if ever needed.
  • Adds zero externally-visible traffic; only health pings.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Endpoints to keep warm. Add any heavy router whose first hit lags.
WARM_ENDPOINTS = (
    "/api/health",
    "/api/public/status",
    "/api/catalog/services",
    "/api/platform/auth/health",
    "/api/onboarding/status-health",  # may 404 — that's fine, still warms the router
)

# Run every 90s — matches the user's spec. Cold-start window is 15-25s,
# so a 90s cycle keeps the worker hot with a safe buffer.
WARM_INTERVAL_SECONDS = 90


async def _probe_one(client, base: str, path: str) -> Dict[str, Any]:
    t0 = asyncio.get_event_loop().time()
    try:
        r = await client.get(f"{base}{path}")
        elapsed_ms = int((asyncio.get_event_loop().time() - t0) * 1000)
        return {"path": path, "status": r.status_code, "elapsed_ms": elapsed_ms}
    except Exception as e:
        return {"path": path, "status": "exception",
                "error": f"{type(e).__name__}: {str(e)[:80]}"}


async def warm_probe_tick() -> Dict[str, Any]:
    """Hit every endpoint in WARM_ENDPOINTS once (in parallel).

    iter 325t — was serial w/ 10s timeout per call → 5 endpoints × 10s = 50s
    worst case → next 90s tick overlapped → APScheduler 'max instances reached'
    warnings every cycle. Fix: parallel asyncio.gather + 5s timeout caps the
    whole tick at ~5s regardless of how many endpoints are added.
    """
    if os.environ.get("AUREM_WARM_PROBER_DISABLED", "").strip() in ("1", "true", "yes"):
        return {"ok": True, "skipped": True, "reason": "disabled_via_env"}

    import httpx
    base = "http://127.0.0.1:8001"  # internal, never ingress

    started = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(timeout=5.0) as client:
        results = await asyncio.gather(
            *[_probe_one(client, base, p) for p in WARM_ENDPOINTS],
            return_exceptions=False,
        )

    slow = sum(1 for r in results if isinstance(r.get("elapsed_ms"), int) and r["elapsed_ms"] > 2000)
    if slow:
        logger.warning(
            f"[warm-prober] {slow}/{len(WARM_ENDPOINTS)} endpoints slow "
            f"(>2s). Cold-start may still bite real users."
        )
    else:
        logger.debug(f"[warm-prober] all {len(WARM_ENDPOINTS)} hot")
    return {"ok": True, "started": started, "slow_count": slow, "results": results}


def install_scheduler(scheduler) -> Optional[str]:
    """Hook the warm-prober into the existing AsyncIOScheduler."""
    try:
        from apscheduler.triggers.interval import IntervalTrigger
    except Exception as e:
        logger.warning(f"[warm-prober] apscheduler not importable: {e}")
        return None

    job = scheduler.add_job(
        warm_probe_tick,
        IntervalTrigger(seconds=WARM_INTERVAL_SECONDS),
        id="aurem_warm_prober",
        name="API Warm Prober",
        replace_existing=True,
        max_instances=2,            # iter 325t — tolerate one overlapping tick
        coalesce=True,
        misfire_grace_time=120,     # iter 325t — don't pile up missed runs
    )
    logger.info(
        f"[warm-prober] scheduled — every {WARM_INTERVAL_SECONDS}s, "
        f"{len(WARM_ENDPOINTS)} endpoints"
    )
    return job.id
