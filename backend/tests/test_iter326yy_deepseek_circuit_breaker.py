"""
iter 326yy — DeepSeek (OpenRouter) suspended-key circuit breaker
================================================================

Production log noise on https://aurem.live:
    WARNING:services.ora_agent:[ora-agent] deepseek 401:
      {"error":{"message":"User not found.","code":401}}

Root cause: the OPENROUTER_API_KEY in production env was revoked /
rotated. Every ORA turn was burning ~1 s pinging the dead key before
falling through to Gemini. App stayed up (the chain has fallbacks)
but the log got spammed and the founder never got an alert.

Fix (mirrors the existing Gemini breaker pattern from iter 326k):
  - Add a process-wide `_deepseek_cb_open()` circuit. 2 consecutive
    401/403s open the circuit for 5 minutes (env-overridable via
    ORA_DEEPSEEK_CB_THRESHOLD / ORA_DEEPSEEK_CB_COOLDOWN_S).
  - While open, the provider chain SKIPS the deepseek branch
    silently and routes to the next provider.
  - One Telegram ping per process via `alert_autonomous_401`
    so the founder sees `Autonomous run hit HTTP 401 (deepseek)`
    and knows to rotate the OpenRouter key.
  - 5xx and timeouts do NOT trip the breaker — those use the
    normal log + fall-through path (transient by nature).
"""
from __future__ import annotations

import asyncio
import importlib
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

BACKEND = Path(__file__).resolve().parent.parent
AGENT = BACKEND / "services" / "ora_agent.py"


# ─────────────────────────────────────────────
# Module surface
# ─────────────────────────────────────────────

def _reload_ora_agent():
    """Re-import ora_agent to reset the module-level circuit state
    between independent tests (the state is process-global)."""
    import services.ora_agent as m
    importlib.reload(m)
    return m


def test_deepseek_breaker_helpers_exist():
    m = _reload_ora_agent()
    assert hasattr(m, "_deepseek_cb_open")
    assert hasattr(m, "_deepseek_cb_record_failure")
    assert hasattr(m, "_deepseek_cb_record_success")
    assert callable(m._deepseek_cb_open)


def test_breaker_opens_after_two_consecutive_401s():
    m = _reload_ora_agent()
    assert m._deepseek_cb_open() is False
    m._deepseek_cb_record_failure(401, "User not found.")
    assert m._deepseek_cb_open() is False  # 1 strike only
    m._deepseek_cb_record_failure(401, "User not found.")
    assert m._deepseek_cb_open() is True   # 2 strikes → open


def test_breaker_closes_on_success_after_open():
    m = _reload_ora_agent()
    m._deepseek_cb_record_failure(401, "x")
    m._deepseek_cb_record_failure(401, "x")
    assert m._deepseek_cb_open() is True
    m._deepseek_cb_record_success()
    assert m._deepseek_cb_open() is False
    # Failures counter must also reset so the next 1 strike doesn't
    # accidentally re-open the circuit on its own.
    assert m._deepseek_cb_fails == 0


def test_breaker_threshold_configurable_via_env(monkeypatch):
    monkeypatch.setenv("ORA_DEEPSEEK_CB_THRESHOLD", "3")
    m = _reload_ora_agent()
    m._deepseek_cb_record_failure(401)
    m._deepseek_cb_record_failure(401)
    assert m._deepseek_cb_open() is False  # 2 strikes, threshold=3
    m._deepseek_cb_record_failure(401)
    assert m._deepseek_cb_open() is True


def test_alert_fires_only_once_per_process():
    """Don't spam Telegram every minute — single ping per process,
    re-enabled after a successful call."""
    m = _reload_ora_agent()
    sent = []
    fake = MagicMock(side_effect=lambda **kw: sent.append(kw))
    with patch("services.silent_failure_alerts.alert_autonomous_401", fake):
        m._deepseek_cb_record_failure(401, "rev")
        m._deepseek_cb_record_failure(401, "rev")  # threshold hit
        assert len(sent) == 1
        # Further failures while open must NOT re-fire
        m._deepseek_cb_record_failure(401, "rev")
        m._deepseek_cb_record_failure(401, "rev")
        assert len(sent) == 1
        # After success + new failures, alert flag resets and can fire again
        m._deepseek_cb_record_success()
        m._deepseek_cb_record_failure(401)
        m._deepseek_cb_record_failure(401)
        assert len(sent) == 2


# ─────────────────────────────────────────────
# Wire-up in the provider chain + http path
# ─────────────────────────────────────────────

def test_provider_chain_skips_deepseek_when_breaker_open():
    """The provider-chain branch for deepseek/openrouter must check
    `_deepseek_cb_open()` and `continue` to the next provider."""
    src = AGENT.read_text()
    # Find the deepseek elif block
    idx = src.index('elif provider in ("deepseek"')
    block = src[idx: idx + 1500]
    # The block must consult the breaker
    assert "_deepseek_cb_open()" in block
    # The block must skip (continue) when open
    assert "continue" in block


def test_http_path_records_failure_on_401_403():
    """`_deepseek_with_tools` must call `_deepseek_cb_record_failure`
    when OpenRouter returns 401 or 403."""
    src = AGENT.read_text()
    idx = src.index("async def _deepseek_with_tools(")
    block = src[idx: idx + 2500]
    assert "_deepseek_cb_record_failure(" in block
    # And success path resets the breaker
    assert "_deepseek_cb_record_success()" in block
    # Only 401/403 trip the breaker (not 5xx/rate-limit)
    assert "r.status_code in (401, 403)" in block


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_326yy_marker_present():
    assert "326yy" in AGENT.read_text()
