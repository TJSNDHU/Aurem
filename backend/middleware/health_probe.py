"""
Health Probe + Flood Gate ASGI Shim — K8s-safe outermost layer
==============================================================

Two purpose-built ASGI short-circuits that run BEFORE every middleware,
router, and DB touch:

1. Liveness/readiness probes (`GET /health|/ready|/live`) respond
   instantly with 200 OK so K8s never times out during cold-start,
   heavy APScheduler cron fires, or Mongo Atlas slow windows.

2. `POST /api/sentinel/client-error` (and `/api/sentinel/heartbeat`)
   are well-known flood targets. Stale preview-pod clients and GCP
   crawlers (e.g. 34.49.222.149) hammer them with dead URLs. Each
   inner handler does 3-4 `count_documents` on Atlas which, under a
   few hundred req/s, saturates the uvicorn event loop and starves
   the liveness probe → nginx upstream timeout → pod restart.

   We apply a TWO-TIER token bucket AT THE OUTERMOST ASGI LAYER:

   • Process-wide bucket: 2/s sustained, burst 5 (was 5/20).
   • Per-IP bucket: 1/30s sustained, burst 3. Tracks last 1024 IPs
     in a tiny LRU; same client cannot hammer the endpoint.

   When either bucket is drained we immediately ACK with `204 No Content`
   without touching Python routing or Mongo. The inner rate-limiter
   inside the router still runs for normal traffic — these gates only
   fire during abuse.

Install order matters: this must be the OUTERMOST ASGI wrapper. Because
Starlette builds middleware LIFO, `add_middleware(HealthProbeMiddleware)`
must be the LAST call made on the FastAPI app.
"""

from __future__ import annotations

import time
from collections import OrderedDict

from starlette.types import ASGIApp, Receive, Scope, Send

_OK_BODY = b'{"status":"ok","platform":"aurem"}'
_OK_HEADERS = [
    (b"content-type", b"application/json"),
    (b"cache-control", b"no-store"),
    (b"content-length", str(len(_OK_BODY)).encode()),
]

# iter 322aa — K8s probe paths that MUST always reply <50ms.
# Nginx rewrites GET /health → http://127.0.0.1:8001/api/platform/health,
# so /api/platform/health gets the same outermost-ASGI fast path or the
# pod gets killed when scheduler ticks (Sentinel/Bridge/A2A) saturate the
# event loop with 60s Claude calls. Production observed 15+ consecutive
# upstream timeouts on this path → this short-circuit prevents that.
_PROBE_PATHS = frozenset({
    "/health", "/ready", "/live",
    "/api/health",            # alt mount used by some routers
    "/api/platform/health",   # K8s liveness/readiness target (nginx rewrite)
    "/api/ready",             # alt readiness mount
})

# ─────────────────────────────────────────────────────────────────────
# Startup self-flood gate — during the first 90s of pod life the
# in-pod APScheduler fires every health-check job at once
# (admin/skills/health, webclaw/health, composer/health, etc.) which
# saturates the event loop and starves the K8s liveness probe →
# upstream timeout → pod kill. We short-circuit those internal cron
# probes during the warm-up window.
# ─────────────────────────────────────────────────────────────────────
_BOOT_TS = time.monotonic()
_BOOT_GRACE_SECONDS = 90.0
_INTERNAL_PROBE_PREFIXES = (
    "/api/admin/",
    "/api/seo/unlinked/health",
    "/api/admin/composer/health",
    "/api/admin/webclaw/",
    "/api/admin/skills/health",
    "/api/admin/skills/learning-health",
    "/api/admin/sovereign/health",
    "/api/admin/pillars-map/",
    "/api/admin/stem-fix/health",
    "/api/admin/site-monitor/overview",
    "/api/admin/payments/health",
    "/api/agents/board/",
    "/api/pillars/health",
    "/api/qa/",
)

# iter D-38 — paths that must NEVER be short-circuited by the boot
# grace window. The admin Integration Health tracker reads live data
# and any 204 confuses the UI into thinking the endpoint is empty.
# iter D-59 — Campaign Health + Public API Keys admin pages need
# real responses (founder hits them from the UI during boot grace too).
_BOOT_GRACE_EXCLUDE = (
    "/api/admin/integrations/",
    "/api/admin/campaign/",
    "/api/admin/public-api-keys",
    "/api/admin/bug-reports",
)


def _in_boot_grace() -> bool:
    return (time.monotonic() - _BOOT_TS) < _BOOT_GRACE_SECONDS

# ─────────────────────────────────────────────────────────────────────
# Flood gate — process-wide + per-IP token buckets.
# ─────────────────────────────────────────────────────────────────────
_FLOOD_PATHS = frozenset({
    "/api/sentinel/client-error",
    "/api/sentinel/heartbeat",
})

# Process-wide bucket
_GLOBAL_REFILL_RATE = 2.0   # sustained req/s through the gate
_GLOBAL_BUCKET_MAX = 5.0    # burst
_global_state = {"tokens": _GLOBAL_BUCKET_MAX, "ts": time.monotonic()}

# Per-IP bucket — 1 token / 30 s sustained, burst 3
_PER_IP_REFILL_RATE = 1.0 / 30.0
_PER_IP_BUCKET_MAX = 3.0
_PER_IP_LRU_MAX = 1024
_per_ip_state: "OrderedDict[str, list[float]]" = OrderedDict()  # ip → [tokens, ts]

_DROP_HEADERS = [
    (b"content-type", b"application/json"),
    (b"cache-control", b"no-store"),
    (b"content-length", b"0"),
]


def _take_global_token() -> bool:
    now = time.monotonic()
    elapsed = now - _global_state["ts"]
    _global_state["ts"] = now
    _global_state["tokens"] = min(
        _GLOBAL_BUCKET_MAX,
        _global_state["tokens"] + elapsed * _GLOBAL_REFILL_RATE,
    )
    if _global_state["tokens"] >= 1.0:
        _global_state["tokens"] -= 1.0
        return True
    return False


def _take_ip_token(ip: str) -> bool:
    if not ip:
        return True
    now = time.monotonic()
    state = _per_ip_state.get(ip)
    if state is None:
        # First time we've seen this IP — give it the full burst.
        if len(_per_ip_state) >= _PER_IP_LRU_MAX:
            _per_ip_state.popitem(last=False)
        _per_ip_state[ip] = [_PER_IP_BUCKET_MAX - 1.0, now]
        return True
    tokens, ts = state
    elapsed = now - ts
    tokens = min(_PER_IP_BUCKET_MAX, tokens + elapsed * _PER_IP_REFILL_RATE)
    if tokens >= 1.0:
        state[0] = tokens - 1.0
        state[1] = now
        _per_ip_state.move_to_end(ip)
        return True
    state[0] = tokens
    state[1] = now
    return False


def _client_ip(scope: Scope) -> str:
    # Honour X-Forwarded-For first hop when behind nginx
    for k, v in scope.get("headers") or []:
        if k == b"x-forwarded-for":
            try:
                return v.decode("ascii", errors="ignore").split(",")[0].strip()
            except Exception:
                pass
    client = scope.get("client") or ()
    return client[0] if client else ""


async def _drain_request_body(receive: Receive) -> None:
    """Consume request body so client gets a clean ACK rather than ECONNRESET."""
    while True:
        msg = await receive()
        if msg.get("type") != "http.request":
            return
        if not msg.get("more_body", False):
            return


class HealthProbeMiddleware:
    """Pure ASGI — no FastAPI, no Starlette Response, no middleware chain."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method")
        path = scope.get("path")

        # 1. Liveness / readiness probe — always-instant 200
        if method in ("GET", "HEAD") and path in _PROBE_PATHS:
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": _OK_HEADERS,
            })
            body = b"" if method == "HEAD" else _OK_BODY
            await send({
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            })
            return

        # 1b. Boot-grace short-circuit — during first 90s of pod life,
        # in-pod APScheduler floods internal health endpoints which
        # saturates the loop and starves the K8s probe. Reply 204 to
        # those internal cron probes (clients don't retry) so the loop
        # stays free for liveness/ready and real user traffic.
        if (
            method == "GET"
            and _in_boot_grace()
            and path
            and path.startswith(_INTERNAL_PROBE_PREFIXES)
            and not path.startswith(_BOOT_GRACE_EXCLUDE)  # iter D-38
        ):
            client = scope.get("client") or ("", 0)
            client_host = client[0] if isinstance(client, (tuple, list)) and client else ""
            if client_host in ("127.0.0.1", "::1", "localhost", ""):
                await send({
                    "type": "http.response.start",
                    "status": 204,
                    "headers": _DROP_HEADERS,
                })
                await send({
                    "type": "http.response.body",
                    "body": b"",
                    "more_body": False,
                })
                return

        # 2. Sentinel flood gate — drop above 2/s global OR > burst-3 per-IP.
        if path in _FLOOD_PATHS and method in ("POST", "GET"):
            ip = _client_ip(scope)
            if not _take_ip_token(ip) or not _take_global_token():
                await _drain_request_body(receive)
                await send({
                    "type": "http.response.start",
                    "status": 204,  # No Content — clients won't retry
                    "headers": _DROP_HEADERS,
                })
                await send({
                    "type": "http.response.body",
                    "body": b"",
                    "more_body": False,
                })
                return

        await self.app(scope, receive, send)


__all__ = ["HealthProbeMiddleware"]
