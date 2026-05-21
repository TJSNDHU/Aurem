"""
iter 326a — FreeLLMAPI wiring regression suite.

Verifies that the FreeLLMAPI proxy provider is fully wired into the
ORA agent chain:

  1. New constants `_FREELLMAPI_HTTPX_TIMEOUT` / `_FREELLMAPI_WAIT_FOR`
     exist and respect the inner<outer rule.
  2. `_freellmapi_with_tools` helper exists, is async, and no-ops
     cleanly when env vars are missing (so unconfigured deployments
     simply skip the provider).
  3. `freellmapi_health` returns a dict-shape diagnostic — never raises.
  4. The default provider order in code includes `freellmapi`.
  5. The provider chain calls `_freellmapi_with_tools` when the
     `freellmapi` provider name appears in the order.
  6. `warm_freellmapi` is wired into server.py startup.
  7. The `/api/admin/ora/providers/health` watchdog endpoint exists
     and includes `freellmapi` in the live order.
"""
import asyncio
import inspect
import os
import sys

sys.path.insert(0, "/app/backend")


# ─── Constants ────────────────────────────────────────────────────────

def test_freellmapi_timeouts_respect_inner_outer_rule():
    from services import ora_agent
    assert hasattr(ora_agent, "_FREELLMAPI_HTTPX_TIMEOUT")
    assert hasattr(ora_agent, "_FREELLMAPI_WAIT_FOR")
    assert ora_agent._FREELLMAPI_HTTPX_TIMEOUT < ora_agent._FREELLMAPI_WAIT_FOR, (
        "inner httpx timeout must be < outer asyncio.wait_for"
    )


# ─── Provider helper ──────────────────────────────────────────────────

def test_freellmapi_provider_helper_exists_and_async():
    from services import ora_agent
    assert hasattr(ora_agent, "_freellmapi_with_tools")
    assert inspect.iscoroutinefunction(ora_agent._freellmapi_with_tools)


def test_freellmapi_provider_returns_none_when_unconfigured(monkeypatch):
    """Unconfigured env → clean None return, no exception."""
    monkeypatch.delenv("FREELLMAPI_BASE_URL", raising=False)
    monkeypatch.delenv("FREELLMAPI_API_KEY", raising=False)
    from services.ora_agent import _freellmapi_with_tools

    async def _go():
        return await _freellmapi_with_tools(
            [{"role": "user", "content": "ping"}]
        )

    result = asyncio.get_event_loop().run_until_complete(_go())
    assert result is None


# ─── Health probe ─────────────────────────────────────────────────────

def test_freellmapi_health_unconfigured(monkeypatch):
    monkeypatch.delenv("FREELLMAPI_BASE_URL", raising=False)
    monkeypatch.delenv("FREELLMAPI_API_KEY", raising=False)
    from services.ora_agent import freellmapi_health

    async def _go():
        return await freellmapi_health()

    r = asyncio.get_event_loop().run_until_complete(_go())
    assert isinstance(r, dict)
    assert r["ok"] is False
    assert r["configured"] is False


def test_freellmapi_health_against_openrouter():
    """E2E proof: point FREELLMAPI_BASE_URL at OpenRouter (which is
    itself OpenAI-compat) and verify the watchdog correctly reports
    200 OK with models_total > 0. This proves the wiring works end to
    end without needing the actual proxy deployed."""
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        import pytest
        pytest.skip("OPENROUTER_API_KEY not set in test env")

    os.environ["FREELLMAPI_BASE_URL"] = "https://openrouter.ai/api/v1"
    os.environ["FREELLMAPI_API_KEY"]  = api_key
    try:
        from services.ora_agent import freellmapi_health

        async def _go():
            return await freellmapi_health()

        r = asyncio.get_event_loop().run_until_complete(_go())
        assert r["ok"] is True, f"got {r}"
        assert r["status"] == 200
        assert r["models_total"] >= 1
        assert r["latency_ms"] >= 0
    finally:
        os.environ.pop("FREELLMAPI_BASE_URL", None)
        os.environ.pop("FREELLMAPI_API_KEY",  None)


# ─── Chain integration ────────────────────────────────────────────────

def test_default_chain_includes_freellmapi():
    """iter 326g superseded the iter 326a contract: founder decided to
    skip FreeLLMAPI proxy entirely and bake Gemini + NVIDIA directly
    into the chain (both keys already in /app/backend/.env). The
    `_freellmapi_with_tools` helper + provider branch must STILL exist
    (so operators who set FREELLMAPI_BASE_URL still get it), but the
    DEFAULT chain order no longer references freellmapi by default.
    Operator can re-add via env: ORA_AGENT_PROVIDER_ORDER="...,freellmapi,..."
    """
    src = open("/app/backend/services/ora_agent.py", encoding="utf-8").read()
    # New iter 326g default chain
    assert '"deepseek,gemini,nvidia,claude,groq"' in src, (
        "iter 326g default chain missing"
    )
    # The freellmapi helper + branch MUST still be wired (opt-in via env)
    assert "_freellmapi_with_tools" in src
    assert 'elif provider == "freellmapi":' in src


def test_provider_branch_exists():
    """_llm_turn must have an `elif provider == "freellmapi"` branch."""
    src = open("/app/backend/services/ora_agent.py", encoding="utf-8").read()
    assert 'elif provider == "freellmapi":' in src
    assert "_freellmapi_with_tools(messages, model=model)" in src


# ─── Warmup wiring ────────────────────────────────────────────────────

def test_warm_freellmapi_exists():
    from services import ora_agent
    assert hasattr(ora_agent, "warm_freellmapi")
    assert inspect.iscoroutinefunction(ora_agent.warm_freellmapi)


def test_warm_freellmapi_scheduled_in_server_startup():
    src = open("/app/backend/server.py", encoding="utf-8").read()
    assert "from services.ora_agent import warm_freellmapi" in src
    assert "asyncio.create_task(warm_freellmapi())" in src


# ─── Watchdog endpoint ────────────────────────────────────────────────

def test_watchdog_endpoint_module_imports():
    """The new health-watchdog router module must import cleanly."""
    from routers import ora_providers_router
    assert hasattr(ora_providers_router, "router")
    assert ora_providers_router.router.prefix == "/api/admin/ora/providers"


def test_watchdog_includes_freellmapi_checker():
    from routers import ora_providers_router
    assert "freellmapi" in ora_providers_router._CHECKERS


def test_watchdog_wired_into_server():
    src = open("/app/backend/server.py", encoding="utf-8").read()
    assert "from routers.ora_providers_router import router" in src


# ─── Documentation ────────────────────────────────────────────────────

def test_integration_doc_present():
    """Operator-facing setup doc must be checked in so future agents
    don't have to re-derive the deployment recipe."""
    import os
    p = "/app/memory/FREELLMAPI_INTEGRATION.md"
    assert os.path.exists(p), "missing /app/memory/FREELLMAPI_INTEGRATION.md"
    body = open(p, encoding="utf-8").read()
    assert "FREELLMAPI_BASE_URL" in body
    assert "FREELLMAPI_API_KEY" in body
    assert "ORA_AGENT_PROVIDER_ORDER" in body
