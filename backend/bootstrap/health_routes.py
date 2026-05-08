"""Liveness / readiness / aggregated-health endpoints.

Extracted from the former 1,820 LOC server.py. These endpoints are mounted
BEFORE any heavy middleware so that K8s liveness / readiness probes return
instantly, even during cold starts or when upstreams (Mongo, Redis) are
sluggish. Every dependency check is wrapped in a hard timeout so one
unreachable upstream never stalls the pod.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import time


def _resolve_version() -> str:
    """Resolve a real deploy version, not a hardcoded string.

    Priority:
      1. APP_VERSION env var (set by CI/deploy pipeline)
      2. AUREM_BUILD_SHA env var (short git SHA from build)
      3. `git rev-parse --short HEAD` at runtime (fallback)
      4. Static fallback with today's date
    """
    # 1. Explicit env
    v = os.environ.get("APP_VERSION")
    if v:
        return v
    sha = os.environ.get("AUREM_BUILD_SHA")
    if sha:
        return f"git-{sha}"
    # 2. Live git read (backend container ships .git or at least a SHA file)
    try:
        out = subprocess.run(
            ["git", "-C", "/app", "rev-parse", "--short=8", "HEAD"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return f"git-{out.stdout.strip()}"
    except Exception:
        pass
    # 3. SHA file written by deploy script
    try:
        with open("/app/.build_sha", "r", encoding="utf-8") as fh:
            sha = fh.read().strip()
            if sha:
                return f"git-{sha[:8]}"
    except Exception:
        pass
    # 4. Static fallback with today's boot timestamp (always changes on restart)
    return f"boot-{int(time.time())}"


_APP_VERSION = _resolve_version()


def register_health_routes(app, db_getter, app_version: str = None) -> None:
    """Attach /health, /api/health, /api/platform/health, /ready and / to `app`.

    Parameters
    ----------
    app         : FastAPI instance
    db_getter   : callable returning the live motor db (None during boot is OK)
    app_version : version string surfaced in every response. If None, resolved
                  automatically from APP_VERSION env / git SHA / boot timestamp.
    """
    if app_version is None:
        app_version = _APP_VERSION

    @app.get("/health")
    async def health():
        """Minimal health check - no logging, no dependencies."""
        return {"status": "ok", "v": app_version}

    @app.get("/api/health")
    async def api_health():
        """Full system health — monitored by Emergent every 60 s.

        IMPORTANT: Must return in <1 s even when upstreams (Redis cloud, etc.)
        are unreachable. In K8s, if this endpoint hangs longer than the
        probeTimeoutSeconds the pod is killed and restarted, causing the
        deploy-stuck-in-restart-loop we saw before. Every external check is
        wrapped in a hard timeout.
        """
        _start = time.time()
        checks: dict = {}

        # MongoDB — 1 s hard cap
        try:
            db = db_getter()
            if db is not None:
                await asyncio.wait_for(db.command("ping"), timeout=1.0)
                checks["mongodb"] = "ok"
            else:
                checks["mongodb"] = "not_connected"
        except asyncio.TimeoutError:
            checks["mongodb"] = "timeout"
        except Exception as e:
            checks["mongodb"] = f"error: {str(e)[:80]}"

        # Redis — 0.3 s hard cap (non-essential; memory fallback is fine)
        try:
            redis_url = os.environ.get("REDIS_URL")
            if redis_url:
                from utils.redis_pool import get_async_redis
                _r = await asyncio.wait_for(get_async_redis(), timeout=0.3)
                if _r is not None:
                    await asyncio.wait_for(_r.ping(), timeout=0.3)
                    checks["redis"] = "ok"
                else:
                    checks["redis"] = "fallback_memory"
            else:
                checks["redis"] = "not_configured"
        except (asyncio.TimeoutError, Exception):
            checks["redis"] = "fallback_memory"

        # Schedulers (purely informational — never blocks)
        try:
            tasks = asyncio.all_tasks()
            task_names = [t.get_name() for t in tasks if not t.done()]
            expected = ["p1:", "p2:", "p3:", "p4:"]  # 4-Pillar workers
            running = [s for s in expected if any(tn.startswith(s) for tn in task_names)]
            checks["schedulers"] = f"{len(running)}/{len(expected)} pillar workers"
        except Exception:
            checks["schedulers"] = "unknown"

        # Liveness status — always "ok" as long as uvicorn can respond.
        # Dependencies shown informationally in `checks`. K8s readiness /
        # liveness only cares about HTTP 200, which we always return. DO NOT
        # flip to "degraded" — Emergent's deploy health probe may reject
        # non-"ok" and send the pod into a restart loop.
        uptime = None
        if hasattr(app.state, "start_time"):
            uptime = round(time.time() - app.state.start_time, 1)

        return {
            "status": "ok",
            "v": app_version,
            "uptime_seconds": uptime,
            "checks": checks,
            "response_ms": round((time.time() - _start) * 1000, 1),
        }

    @app.get("/api/platform/health")
    async def platform_health():
        """Platform health check for Kubernetes probes."""
        return {"status": "ok", "platform": "aurem"}

    @app.get("/ready")
    async def ready():
        """Readiness probe."""
        return {"status": "ok"}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"status": "ok"}


__all__ = ["register_health_routes"]
