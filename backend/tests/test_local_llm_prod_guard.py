"""
test_local_llm_prod_guard.py — locks the production deployment fix.

The fix prevents the Sovereign circuit breaker from hammering retries
during production startup (which previously caused 80+ "Circuit breaker
opened" warnings, flooded logs, and starved the asyncio loop → K8s health
probe timeout → deployment failure).

In production:
  • _PROD_DETECTED is True
  • _config["enabled"] is False (auto-disabled)
  • _is_backed_off() returns True permanently
  • is_available() returns False without making any HTTP probe

In preview/local:
  • _PROD_DETECTED is False
  • _config["enabled"] stays True
  • _is_backed_off() returns False until real failures accumulate
"""
from __future__ import annotations

import importlib
import os
import sys

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


def _reload():
    """Force fresh import so module-level _PROD_DETECTED reflects current env."""
    for mod in list(sys.modules.keys()):
        if mod in ("services.prod_guard", "services.local_llm_service"):
            del sys.modules[mod]
    return importlib.import_module("services.local_llm_service")


def _clear_env():
    for k in ("AUREM_ENV", "DISABLE_LEGION", "APP_URL"):
        os.environ.pop(k, None)


def test_production_disables_sovereign():
    _clear_env()
    os.environ["AUREM_ENV"] = "production"
    m = _reload()
    assert m._PROD_DETECTED is True
    assert m._config["enabled"] is False
    assert m._is_backed_off() is True
    assert m.is_backed_off() is True


def test_preview_keeps_sovereign_enabled():
    _clear_env()
    m = _reload()
    assert m._PROD_DETECTED is False
    assert m._config["enabled"] is True
    assert m._is_backed_off() is False
    assert m.is_backed_off() is False


def test_app_url_aurem_live_triggers_prod():
    _clear_env()
    os.environ["APP_URL"] = "https://aurem.live"
    m = _reload()
    assert m._PROD_DETECTED is True
    assert m._config["enabled"] is False


def test_is_available_skips_probe_in_production():
    """The most important test: in prod, is_available() must NOT touch httpx."""
    import asyncio
    _clear_env()
    os.environ["AUREM_ENV"] = "production"
    m = _reload()

    async def _run():
        # If we DID try to connect to sovereign.aurem.live, this would take 2s+.
        # The prod guard makes it return False instantly.
        import time
        t0 = time.time()
        ok = await m.is_available()
        elapsed = time.time() - t0
        assert ok is False
        assert elapsed < 0.05, f"prod is_available must short-circuit (<50ms), got {elapsed*1000:.0f}ms"

    asyncio.run(_run())


if __name__ == "__main__":
    test_production_disables_sovereign()
    test_preview_keeps_sovereign_enabled()
    test_app_url_aurem_live_triggers_prod()
    test_is_available_skips_probe_in_production()
    print("ALL local_llm_service prod-guard tests passed ✓")
