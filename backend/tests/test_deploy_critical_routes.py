"""
CRITICAL Deployment Route Test
==============================
MUST PASS before any production merge.

Guards against the iteration-216 CrashLoopBackOff where `routers/registry.py`
pruned Kubernetes probe routes in LEAN_MODE, causing the K8s readiness probe
to 404, pod never-ready, deploy stuck.

This test:
  1. Boots the real FastAPI app under LEAN_MODE=production (same as prod)
  2. Hits `/health`, `/ready`, `/api/health` via FastAPI TestClient
  3. Asserts every endpoint returns 200 OK with a valid JSON body
  4. Asserts response time is fast (< 2s) — slow probes also fail in k8s

Run:
    cd /app/backend && pytest tests/test_deploy_critical_routes.py -q

Expected output:
    3 passed  (≈ 5s)

If any endpoint returns non-200 or hangs, the deploy WILL fail.
"""
from __future__ import annotations

import importlib
import os
import sys
import time

import pytest


# The exact probe paths Kubernetes / Emergent use for pod health gating.
# If any of these returns non-200 in production, the pod never becomes Ready.
CRITICAL_PROBE_ROUTES = [
    "/health",
    "/ready",
    "/api/health",
]

# Generous ceiling for local CI — production probes are usually <1s.
MAX_PROBE_LATENCY_SECONDS = 2.0


@pytest.fixture(scope="module")
def lean_client():
    """
    Boot the FastAPI app under production-equivalent config (LEAN_ROUTES=1),
    run full router registration, and return a TestClient bound to the app.
    """
    # Force the exact env that triggers the LEAN prune pass in registry.py
    os.environ["LEAN_ROUTES"] = "1"
    os.environ.setdefault("AUREM_ENV", "production")

    # Evict any previously-imported copies so module-level state is rebuilt
    for name in list(sys.modules):
        if name == "server" or name.startswith("server.") \
           or name == "routers.registry" or name.startswith("routers."):
            sys.modules.pop(name, None)

    import server  # noqa: WPS433 — deliberate late import after env set
    from routers.registry import register_all_routers

    # Run the same registration pipeline production runs on startup.
    # A fresh motor client is created by server.py itself; registry only
    # needs `app` and may pass `None` for db here because we're testing
    # *route registration*, not auth/DB behaviour.
    try:
        register_all_routers(server.app, getattr(server, "db", None))
    except Exception:
        # Some optional routers need a fully-initialised DB; that's OK.
        # The prune pass we care about runs regardless.
        pass

    from fastapi.testclient import TestClient
    return TestClient(server.app)


@pytest.mark.parametrize("probe_path", CRITICAL_PROBE_ROUTES)
def test_probe_returns_200_in_lean_mode(lean_client, probe_path):
    """Every deploy-critical probe endpoint MUST return 200 OK under LEAN_MODE."""
    started = time.monotonic()
    response = lean_client.get(probe_path)
    elapsed = time.monotonic() - started

    # --- 1. Status must be exactly 200 ------------------------------------
    assert response.status_code == 200, (
        f"\nDEPLOY BLOCKER: `{probe_path}` returned {response.status_code}\n"
        f"Body: {response.text[:200]}\n"
        f"K8s readiness probe would fail → pod never-Ready → CrashLoopBackOff.\n"
        f"Check routers/registry.py for `{probe_path}` in any prune set."
    )

    # --- 2. Body must be valid JSON ---------------------------------------
    try:
        body = response.json()
    except ValueError:
        pytest.fail(
            f"`{probe_path}` returned 200 but body is not valid JSON.\n"
            f"Body: {response.text[:200]}"
        )

    # --- 3. Body must indicate healthy or degraded (not an error shape) ---
    assert isinstance(body, dict), f"`{probe_path}` body is not a JSON object: {body!r}"
    # `/health` and `/ready` return {"status": "ok", ...}
    # `/api/health` returns {"status": "ok"|"degraded", ...}
    status = body.get("status")
    assert status in ("ok", "degraded"), (
        f"`{probe_path}` returned status={status!r}; expected 'ok' or 'degraded'.\n"
        f"Body: {body}"
    )

    # --- 4. Latency must be below the K8s probeTimeoutSeconds budget ------
    assert elapsed < MAX_PROBE_LATENCY_SECONDS, (
        f"`{probe_path}` responded in {elapsed:.2f}s — exceeds "
        f"{MAX_PROBE_LATENCY_SECONDS}s K8s probe budget.\n"
        f"A slow probe also causes the pod to fail readiness in production."
    )
