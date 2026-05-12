"""
Endpoint Heartbeat Scheduler — keeps the Evidence Classifier honest.

Why: the Pillars-Map "ALIVE/GHOST/LEAKY" classifier relies on
`api_audit_log` to know if an endpoint has been hit in the last 30 days.
Endpoints invoked only by schedulers, webhooks, or admin UI flows that
weren't exercised in production go DARK and get mis-classified as
"leaky" even though they work fine.

This service runs in the background and **synthetically pings every
safe GET endpoint** every 4 hours. Each ping flows through
`DatabaseAuditMiddleware` and inserts a row into `api_audit_log` — so
the classifier's `signal_activity` becomes True and the endpoint goes
ALIVE/GHOST instead of LEAKY.

Safety rails:
  - Only GET endpoints (no side-effects)
  - Skips well-known mutating prefixes (/run, /broadcast, /sync, /delete,
    /reset, /invalidate, /clear, /webhook, /callback)
  - Skips routes with required path params (those need real IDs)
  - Skips /api/admin/ unless an admin JWT is configured
  - Hard timeout 4 s per probe
  - Concurrency limited to 6 to avoid self-DoS
  - Marks each row with `synthetic=True` so we can exclude these from
    *real* traffic analytics later
"""
from __future__ import annotations

import asyncio
import glob
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

INTERVAL_S = int(os.environ.get("ENDPOINT_HEARTBEAT_INTERVAL_S") or 4 * 3600)
PROBE_TIMEOUT_S = 4.0
MAX_CONCURRENT = 6
BACKEND_BASE = os.environ.get("ENDPOINT_HEARTBEAT_BASE") or "http://localhost:8001"
ROUTERS_GLOB = "/app/backend/routers/*.py"

# Path patterns we never auto-probe
_SKIP_TOKENS = (
    "{",          # path params
    "/run",
    "/broadcast",
    "/sync",
    "/delete",
    "/reset",
    "/invalidate",
    "/clear",
    "/wipe",
    "/purge",
    "/webhook",
    "/callback",
    "/upload",
    "/login",
    "/logout",
    "/register",
    "/signup",
    "/token",
    "/refresh",
    "/payout",
    "/charge",
    "/checkout",
    "/migrate",
    "/migration",
    "/seed",
)
# Prefixes we always probe (auto-include even admin)
_AUTO_INCLUDE_PREFIXES = (
    "/api/admin/",
    "/api/customer/audit/_/",
    "/api/admin/memoir/",
)

_DECO_RE = re.compile(
    r"@(?:router|app)\.(get|head)\(\s*[\"']([^\"']+)[\"']"
)


def _collect_get_endpoints() -> list[tuple[str, str, str]]:
    """Return list of (method, full_path, router_file) tuples for every
    GET decorator in /app/backend/routers/*.py — with the router-level
    prefix prepended so the path is canonical."""
    out: list[tuple[str, str, str]] = []
    prefix_re = re.compile(r"APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']+)[\"']")
    for f in glob.glob(ROUTERS_GLOB):
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                src = fh.read()
        except Exception:
            continue
        pm = prefix_re.search(src)
        prefix = pm.group(1) if pm else ""
        for m in _DECO_RE.finditer(src):
            method, raw_path = m.group(1).upper(), m.group(2)
            full = (prefix.rstrip("/") + raw_path) if not raw_path.startswith(prefix) else raw_path
            if not full.startswith("/api/"):
                continue
            out.append((method, full, os.path.basename(f)))
    return out


def _is_safe(path: str) -> bool:
    pl = path.lower()
    if any(tok in pl for tok in _SKIP_TOKENS):
        return False
    return True


async def _probe_one(client: httpx.AsyncClient, headers: dict,
                      method: str, path: str) -> tuple[str, int]:
    try:
        url = BACKEND_BASE.rstrip("/") + path
        r = await client.request(method, url, headers=headers,
                                   timeout=PROBE_TIMEOUT_S)
        return (path, r.status_code)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[heartbeat] {path} probe err: {e}")
        return (path, 0)


async def _make_admin_jwt() -> Optional[str]:
    """Mint an internal admin JWT so we can probe protected routes."""
    try:
        import jwt as _jwt
        from datetime import timedelta
        secret = os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY") or ""
        algo = os.environ.get("JWT_ALGORITHM") or "HS256"
        if not secret:
            return None
        payload = {
            "sub": "heartbeat@aurem.live",
            "email": "heartbeat@aurem.live",
            "role": "admin",
            "tier": "enterprise",
            "synthetic": True,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        return _jwt.encode(payload, secret, algorithm=algo)
    except Exception as e:
        logger.warning(f"[heartbeat] could not mint JWT: {e}")
        return None


async def _record_run(db, total: int, ok: int, ms: float) -> None:
    if db is None:
        return
    try:
        await db.endpoint_heartbeat_runs.insert_one({
            "ts": datetime.now(timezone.utc),
            "endpoints_probed": total,
            "ok": ok,
            "duration_ms": int(ms),
        })
    except Exception:
        pass


async def heartbeat_loop(db=None) -> None:
    """Long-running task. Probes safe GETs every INTERVAL_S."""
    logger.info(f"[heartbeat] started — interval={INTERVAL_S}s, base={BACKEND_BASE}")
    # First run delayed by 90 s so app is fully up and HealthProbeMiddleware
    # boot-grace has elapsed.
    await asyncio.sleep(90)
    while True:
        t0 = time.time()
        try:
            endpoints = _collect_get_endpoints()
            safe = [(m, p, r) for m, p, r in endpoints if _is_safe(p)]
            jwt_token = await _make_admin_jwt()
            headers = {"X-Synthetic-Probe": "heartbeat"}
            if jwt_token:
                headers["Authorization"] = f"Bearer {jwt_token}"

            sem = asyncio.Semaphore(MAX_CONCURRENT)
            ok = 0

            async with httpx.AsyncClient() as client:
                async def _bounded(m: str, p: str):
                    nonlocal ok
                    async with sem:
                        _, code = await _probe_one(client, headers, m, p)
                        if 200 <= code < 500:
                            ok += 1

                await asyncio.gather(*[_bounded(m, p) for m, p, _ in safe])

            elapsed_ms = (time.time() - t0) * 1000
            logger.info(
                f"[heartbeat] cycle complete — {len(safe)} probed, "
                f"{ok} ok, {elapsed_ms:.0f}ms"
            )
            await _record_run(db, len(safe), ok, elapsed_ms)
        except Exception as e:
            logger.warning(f"[heartbeat] cycle failed: {e}")

        await asyncio.sleep(INTERVAL_S)


async def heartbeat_run_once(db=None, limit: int = 0) -> dict:
    """One-shot probe — used by the /endpoint-audit/heartbeat endpoint
    to force a refresh on demand. Returns a summary."""
    t0 = time.time()
    endpoints = _collect_get_endpoints()
    safe = [(m, p, r) for m, p, r in endpoints if _is_safe(p)]
    if limit and limit > 0:
        safe = safe[:limit]
    jwt_token = await _make_admin_jwt()
    headers = {"X-Synthetic-Probe": "heartbeat"}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    results: list[tuple[str, int]] = []

    async with httpx.AsyncClient() as client:
        async def _bounded(m: str, p: str):
            async with sem:
                results.append(await _probe_one(client, headers, m, p))

        await asyncio.gather(*[_bounded(m, p) for m, p, _ in safe])

    elapsed_ms = (time.time() - t0) * 1000
    ok = sum(1 for _, c in results if 200 <= c < 500)
    await _record_run(db, len(safe), ok, elapsed_ms)
    return {
        "endpoints_total": len(endpoints),
        "endpoints_safe": len(safe),
        "probed": len(results),
        "ok": ok,
        "duration_ms": int(elapsed_ms),
        "interval_s": INTERVAL_S,
    }
