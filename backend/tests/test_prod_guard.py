"""
test_prod_guard.py — verifies production-guard activation & ORA agent
short-circuit (iter 322g+).

Why this exists:
  In an earlier deploy (May 2026) the production pod returned HTTP 520
  because ORA chat requests hung 270s waiting on Legion daemon (unreachable
  from prod), while background warmer loops hammered legion_exec calls
  that also timed out. Workers exhausted → /health refused → Cloudflare 520.

  prod_guard.is_production_pod() now centralises detection and is used by:
    - services/ora_agent._llm_turn       (returns preview-only msg in <1s)
    - services/sovereign_warmer          (skips loop in prod)
    - services/ollama_warmer             (skips loop in prod)
    - services/ora_autonomous_ops        (skips warmer + autofix in prod)

  These tests freeze the contract so a future refactor cannot reintroduce
  the 270s hang or hammer Legion from prod.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import sys


def _reload_prod_guard():
    """Force a fresh import so lru_cache picks up the new env."""
    for mod in list(sys.modules.keys()):
        if mod.endswith("services.prod_guard") or mod == "services.prod_guard":
            del sys.modules[mod]
    return importlib.import_module("services.prod_guard")


def _clear_env():
    for k in ("AUREM_ENV", "DISABLE_LEGION", "APP_URL"):
        os.environ.pop(k, None)


def test_preview_default_returns_false():
    _clear_env()
    pg = _reload_prod_guard()
    assert pg.is_production_pod() is False
    assert pg.env_label() == "preview"


def test_aurem_env_production_returns_true():
    _clear_env()
    os.environ["AUREM_ENV"] = "production"
    pg = _reload_prod_guard()
    assert pg.is_production_pod() is True
    assert pg.env_label() == "production"


def test_disable_legion_returns_true():
    _clear_env()
    os.environ["DISABLE_LEGION"] = "true"
    pg = _reload_prod_guard()
    assert pg.is_production_pod() is True


def test_app_url_aurem_live_returns_true():
    _clear_env()
    os.environ["APP_URL"] = "https://aurem.live"
    pg = _reload_prod_guard()
    assert pg.is_production_pod() is True


def test_ora_agent_short_circuits_in_production():
    """In prod, _llm_turn must return the preview-only message in <1s."""
    _clear_env()
    os.environ["AUREM_ENV"] = "production"
    # Reload prod_guard AND ora_agent so the cached is_production_pod() flips.
    for mod in list(sys.modules.keys()):
        if "prod_guard" in mod or mod == "services.ora_agent":
            del sys.modules[mod]
    from services.ora_agent import _llm_turn

    import time

    async def _run():
        t0 = time.time()
        msg = await _llm_turn([{"role": "user", "content": "hello"}])
        elapsed = time.time() - t0
        assert elapsed < 2.0, f"prod LLM call must short-circuit fast, got {elapsed:.1f}s"
        assert msg["role"] == "assistant"
        assert "preview" in msg["content"].lower()
        assert msg.get("tool_calls") == []

    asyncio.run(_run())


if __name__ == "__main__":
    test_preview_default_returns_false()
    test_aurem_env_production_returns_true()
    test_disable_legion_returns_true()
    test_app_url_aurem_live_returns_true()
    test_ora_agent_short_circuits_in_production()
    print("ALL prod_guard tests passed ✓")
