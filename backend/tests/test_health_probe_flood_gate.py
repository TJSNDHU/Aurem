"""
iter 282al-25 — Tests for the hardened HealthProbeMiddleware ASGI shim.
Covers:
  • /health probe always 200 (instant, no app call)
  • Per-IP token bucket drops 4th burst from same IP with 204
  • Global token bucket drops bursts above 5
  • Heartbeat path also gated
  • Non-flood paths pass through to the wrapped app
"""
from __future__ import annotations

import asyncio
import importlib

import pytest


def _reset_module_state():
    """Re-import the module so global buckets reset between tests."""
    import middleware.health_probe as hp
    importlib.reload(hp)
    return hp


async def _call(mw, method, path, ip="1.2.3.4"):
    """Drive the ASGI middleware once, capture status + body."""
    sent = []

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(b"x-forwarded-for", ip.encode())],
        "client": (ip, 0),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    await mw(scope, receive, send)

    status = next((m["status"] for m in sent if m["type"] == "http.response.start"), None)
    body = b"".join(
        m.get("body", b"") for m in sent if m["type"] == "http.response.body"
    )
    return status, body


class _DummyApp:
    """Records that it was called — meaning the middleware did NOT short-circuit."""
    def __init__(self):
        self.calls = 0

    async def __call__(self, scope, receive, send):
        self.calls += 1
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b'{"app":"ok"}',
                    "more_body": False})


# ─────────────── Probe paths ───────────────
@pytest.mark.asyncio
async def test_health_probe_short_circuits_with_200():
    hp = _reset_module_state()
    app = _DummyApp()
    mw = hp.HealthProbeMiddleware(app)
    status, body = await _call(mw, "GET", "/health")
    assert status == 200
    assert body == b'{"status":"ok"}'
    assert app.calls == 0  # didn't reach the app


@pytest.mark.asyncio
async def test_ready_and_live_also_short_circuit():
    hp = _reset_module_state()
    app = _DummyApp()
    mw = hp.HealthProbeMiddleware(app)
    for path in ("/ready", "/live"):
        status, _ = await _call(mw, "GET", path)
        assert status == 200
    assert app.calls == 0


@pytest.mark.asyncio
async def test_head_health_returns_empty_body():
    hp = _reset_module_state()
    app = _DummyApp()
    mw = hp.HealthProbeMiddleware(app)
    status, body = await _call(mw, "HEAD", "/health")
    assert status == 200
    assert body == b""


# ─────────────── Per-IP flood gate ───────────────
@pytest.mark.asyncio
async def test_per_ip_burst_3_then_drops_204():
    hp = _reset_module_state()
    app = _DummyApp()
    mw = hp.HealthProbeMiddleware(app)
    # Same IP — should pass through 3 times then drop with 204
    for _ in range(3):
        status, _ = await _call(mw, "POST", "/api/sentinel/client-error", ip="9.9.9.9")
        assert status == 200
    status, body = await _call(mw, "POST", "/api/sentinel/client-error", ip="9.9.9.9")
    assert status == 204
    assert body == b""
    assert app.calls == 3  # only the first 3 reached the app


@pytest.mark.asyncio
async def test_different_ips_each_get_their_own_burst():
    hp = _reset_module_state()
    app = _DummyApp()
    mw = hp.HealthProbeMiddleware(app)
    # IP A drains its own per-IP bucket — but global bucket has 5 tokens.
    for _ in range(3):
        status, _ = await _call(mw, "POST", "/api/sentinel/client-error", ip="1.1.1.1")
        assert status == 200
    # IP A's 4th request — drops at the per-IP gate (no global token consumed)
    status, _ = await _call(mw, "POST", "/api/sentinel/client-error", ip="1.1.1.1")
    assert status == 204
    # IP B's first 2 requests — still within global bucket (5 - 3 = 2 left)
    for _ in range(2):
        status, _ = await _call(mw, "POST", "/api/sentinel/client-error", ip="2.2.2.2")
        assert status == 200
    # Global bucket drained → 3rd request from IP B dropped at global gate
    status, _ = await _call(mw, "POST", "/api/sentinel/client-error", ip="2.2.2.2")
    assert status == 204


# ─────────────── Heartbeat path also gated ───────────────
@pytest.mark.asyncio
async def test_heartbeat_path_also_short_circuits_under_flood():
    hp = _reset_module_state()
    app = _DummyApp()
    mw = hp.HealthProbeMiddleware(app)
    # Drain per-IP bucket on heartbeat
    for _ in range(3):
        status, _ = await _call(mw, "GET", "/api/sentinel/heartbeat", ip="7.7.7.7")
        assert status == 200
    status, _ = await _call(mw, "GET", "/api/sentinel/heartbeat", ip="7.7.7.7")
    assert status == 204


# ─────────────── Non-flood paths pass through ───────────────
@pytest.mark.asyncio
async def test_non_flood_path_passes_through():
    hp = _reset_module_state()
    app = _DummyApp()
    mw = hp.HealthProbeMiddleware(app)
    # /api/aurem/chat is not gated — should reach the app
    for _ in range(20):
        status, body = await _call(mw, "POST", "/api/aurem/chat", ip="5.5.5.5")
        assert status == 200
        assert body == b'{"app":"ok"}'
    assert app.calls == 20


# ─────────────── Refill behaviour ───────────────
@pytest.mark.asyncio
async def test_global_bucket_refills_over_time(monkeypatch):
    hp = _reset_module_state()
    app = _DummyApp()
    mw = hp.HealthProbeMiddleware(app)

    # Drain the global bucket
    for i in range(5):
        await _call(mw, "POST", "/api/sentinel/client-error", ip=f"10.0.0.{i}")
    status, _ = await _call(mw, "POST", "/api/sentinel/client-error", ip="10.0.0.99")
    assert status == 204

    # Forward time by ~3s — global bucket refills 2/s = 6 tokens (capped at 5)
    real_monotonic = hp.time.monotonic
    base = real_monotonic()
    monkeypatch.setattr(hp.time, "monotonic", lambda: base + 3.0)
    status, _ = await _call(mw, "POST", "/api/sentinel/client-error", ip="10.0.0.50")
    assert status == 200
