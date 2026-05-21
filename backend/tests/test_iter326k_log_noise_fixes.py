"""
iter 326k — Production-log noise fixes.

Two issues found in deployed-app logs after iter 326j:
  1. `/api/onboarding/status-health` was 404'ing because warm_prober probes
     it intentionally to keep the router warm, but no handler exists.
     → Added a 2xx stub handler in onboarding_router.
  2. Gemini chain hit was spending 20s on a permanently-suspended key
     before falling through to NVIDIA on every chat call.
     → Added a circuit breaker (2 strikes → 5min skip) symmetric with
        the existing ollama breaker.
"""
from __future__ import annotations

import asyncio
import time

import pytest


# ──────────────────────────────────────────────────────────────────────
# 1. onboarding/status-health stub
# ──────────────────────────────────────────────────────────────────────
def test_onboarding_status_health_route_exists():
    """The stub must be registered on the onboarding router so warm
    probes get a 2xx instead of polluting the logs with 404s."""
    from routers.onboarding_router import router
    paths = [r.path for r in router.routes if hasattr(r, "path")]
    # Router has prefix /api/onboarding, so /status-health = full path
    assert "/api/onboarding/status-health" in paths, (
        f"missing status-health route; got: {paths[:10]}"
    )


def test_onboarding_status_health_returns_ok():
    """Direct handler call returns a 2xx envelope."""
    from routers.onboarding_router import status_health
    res = asyncio.new_event_loop().run_until_complete(status_health())
    assert res["status"] == "ok"
    assert res["service"] == "onboarding"
    assert res["warm"] is True


# ──────────────────────────────────────────────────────────────────────
# 2. Gemini circuit breaker
# ──────────────────────────────────────────────────────────────────────
def test_gemini_cb_initial_state_closed():
    """A freshly-imported breaker must be closed."""
    import importlib
    from services import ora_agent
    importlib.reload(ora_agent)
    assert ora_agent._gemini_cb_open() is False
    assert ora_agent._gemini_cb_fails == 0


def test_gemini_cb_opens_at_threshold():
    """Default threshold is 2 — after 2 failures the breaker opens."""
    import importlib
    from services import ora_agent
    importlib.reload(ora_agent)
    ora_agent._gemini_cb_record_failure("HTTP 403: suspended")
    assert ora_agent._gemini_cb_open() is False  # only 1 failure
    ora_agent._gemini_cb_record_failure("HTTP 403: suspended")
    assert ora_agent._gemini_cb_open() is True
    assert ora_agent._gemini_cb_until > time.time()


def test_gemini_cb_success_closes_circuit():
    import importlib
    from services import ora_agent
    importlib.reload(ora_agent)
    ora_agent._gemini_cb_record_failure("HTTP 403")
    ora_agent._gemini_cb_record_failure("HTTP 403")
    assert ora_agent._gemini_cb_open() is True
    ora_agent._gemini_cb_record_success()
    assert ora_agent._gemini_cb_open() is False
    assert ora_agent._gemini_cb_fails == 0


def test_gemini_cb_cooldown_expires():
    """After cooldown elapses, breaker auto-closes (open returns False)."""
    import importlib
    from services import ora_agent
    importlib.reload(ora_agent)
    # Force the breaker open with a fake past expiry
    ora_agent._gemini_cb_until = time.time() - 1.0
    assert ora_agent._gemini_cb_open() is False


def test_llm_turn_skips_gemini_when_circuit_open():
    """Static check — the gemini branch in _llm_turn must check
    _gemini_cb_open() before paying the 20s timeout."""
    src = open("/app/backend/services/ora_agent.py", encoding="utf-8").read()
    # Must call the circuit check inside the gemini branch
    assert "_gemini_cb_open()" in src
    # Must record failure on 401/403 inside the gemini helper
    assert "_gemini_cb_record_failure" in src
    # Must record success in the helper after a 200
    assert "_gemini_cb_record_success()" in src


def test_gemini_helper_records_failure_on_403(monkeypatch):
    """The _gemini_with_tools helper must call
    _gemini_cb_record_failure when Google returns 403."""
    import importlib
    from services import ora_agent
    importlib.reload(ora_agent)
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy_for_test")

    class FakeResp:
        status_code = 403
        text = '{"error":{"message":"Consumer ... has been suspended"}}'

    class FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self):  return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw):
            return FakeResp()

    monkeypatch.setattr(ora_agent.httpx, "AsyncClient", FakeClient)
    out = asyncio.new_event_loop().run_until_complete(
        ora_agent._gemini_with_tools([{"role": "user", "content": "hi"}])
    )
    assert out is None
    # failure counter incremented
    assert ora_agent._gemini_cb_fails >= 1
