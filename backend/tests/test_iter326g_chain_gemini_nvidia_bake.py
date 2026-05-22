"""
iter 326g — Verify ORA chain is now `deepseek → gemini → nvidia → claude → groq`
and that the Gemini/NVIDIA helpers + timeout constants are correctly declared.

Founder decision (2026-05-21): skip FreeLLMAPI proxy entirely. Bake Gemini +
NVIDIA directly into the ORA provider chain. Both API keys are already in
/app/backend/.env (GOOGLE_API_KEY, NVIDIA_NIM_API_KEY).

These tests are pure / no-network:
  • Import-time tests verify constants exist (catches NameError on cold-call)
  • Default chain order is the new one
  • Helpers `gemini_health` / `nvidia_health` / `warm_gemini` / `warm_nvidia`
    return graceful dicts when env keys are absent (monkeypatched)
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import re

import pytest


# ── 1. Timeout constants exist (NameError shield) ──────────────────────────
def test_gemini_nvidia_timeout_constants_declared():
    """Previously _GEMINI_*/_NVIDIA_* were USED but never DECLARED → NameError
    on the first provider call. Confirm they now exist and are sensible."""
    from services import ora_agent
    for name in ("_GEMINI_HTTPX_TIMEOUT", "_GEMINI_WAIT_FOR",
                 "_NVIDIA_HTTPX_TIMEOUT", "_NVIDIA_WAIT_FOR"):
        assert hasattr(ora_agent, name), f"{name} not declared"
        val = getattr(ora_agent, name)
        assert isinstance(val, (int, float)) and val > 0, f"{name} invalid: {val!r}"
    # httpx must always be < wait_for (clean socket close invariant)
    assert ora_agent._GEMINI_HTTPX_TIMEOUT < ora_agent._GEMINI_WAIT_FOR
    assert ora_agent._NVIDIA_HTTPX_TIMEOUT < ora_agent._NVIDIA_WAIT_FOR


# ── 2. Default chain order is correct ──────────────────────────────────────
def test_default_chain_order_excludes_freellmapi_and_ollama():
    """The MEDIUM-tier chain (which is the default for untagged
    traffic after iter 326u) must be the founder-approved
    `deepseek,gemini,nvidia,claude,groq` — FreeLLMAPI + Legion Ollama
    are intentionally NOT in the default chain."""
    from services.ora_agent import _chain_order_for
    providers = _chain_order_for("medium")
    assert providers == ["deepseek", "gemini", "nvidia", "claude", "groq"], (
        f"unexpected default chain: {providers}"
    )
    assert "freellmapi" not in providers
    assert "legion_ollama" not in providers


def test_health_router_default_matches_agent_default():
    src = open("/app/backend/routers/ora_providers_router.py", encoding="utf-8").read()
    assert '"deepseek,gemini,nvidia,claude,groq"' in src, (
        "router default chain not updated"
    )
    assert "freellmapi,legion_ollama" not in src or (
        # still ok if the string appears inside a comment / dead code,
        # but the new default must be present
        '"deepseek,gemini,nvidia,claude,groq"' in src
    )


# ── 3. Helpers exist and are async ─────────────────────────────────────────
def test_gemini_nvidia_helpers_exist():
    from services import ora_agent
    for fname in ("_gemini_with_tools", "_nvidia_with_tools",
                  "warm_gemini", "warm_nvidia",
                  "gemini_health", "nvidia_health"):
        fn = getattr(ora_agent, fname, None)
        assert fn is not None and inspect.iscoroutinefunction(fn), (
            f"{fname} missing or not async"
        )


# ── 4. Server.py wires both warmups at startup ─────────────────────────────
def test_server_startup_warms_gemini_and_nvidia():
    src = open("/app/backend/server.py", encoding="utf-8").read()
    assert "from services.ora_agent import warm_gemini, warm_nvidia" in src
    assert "asyncio.create_task(warm_gemini())" in src
    assert "asyncio.create_task(warm_nvidia())" in src


# ── 5. health() helpers fail GRACEFULLY when keys are absent ───────────────
def test_gemini_health_no_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from services.ora_agent import gemini_health

    async def _go():
        return await gemini_health()

    out = asyncio.run(_go())
    assert out["ok"] is False
    assert out["configured"] is False
    assert "GOOGLE_API_KEY" in out["reason"]


def test_nvidia_health_no_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    from services.ora_agent import nvidia_health

    async def _go():
        return await nvidia_health()

    out = asyncio.run(_go())
    assert out["ok"] is False
    assert out["configured"] is False
    assert "NVIDIA_NIM_API_KEY" in out["reason"]


# ── 6. warm helpers no-op gracefully on missing key ────────────────────────
def test_warm_gemini_no_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from services.ora_agent import warm_gemini
    assert asyncio.run(warm_gemini()) is False


def test_warm_nvidia_no_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    from services.ora_agent import warm_nvidia
    assert asyncio.run(warm_nvidia()) is False
