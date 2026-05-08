"""Tests for the unified LLM gateway — iter 282al-5."""
from __future__ import annotations

import asyncio

import pytest

from services.llm_gateway import (
    FAIL_MSG,
    LLM_PROVIDER_ORDER,
    call_llm,
    call_llm_with_meta,
    sovereign_health,
)


def test_provider_chain_order_sovereign_first():
    """Sovereign must be priority 1, fallback last."""
    assert LLM_PROVIDER_ORDER[0] == "sovereign"
    assert LLM_PROVIDER_ORDER[-1] == "fallback"
    assert "openrouter" in LLM_PROVIDER_ORDER
    assert "emergent" in LLM_PROVIDER_ORDER


def test_fail_msg_is_stable():
    """Callers grep for this prefix to detect total miss."""
    assert "LLM unavailable" in FAIL_MSG


def test_call_llm_returns_string_when_all_providers_miss(monkeypatch):
    """With no keys and no sovereign URL, must gracefully degrade."""
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("SOVEREIGN_NODE_URL", "https://invalid-tunnel.example")
    monkeypatch.setenv("OLLAMA_URL",          "https://invalid-tunnel.example")

    out = asyncio.new_event_loop().run_until_complete(
        call_llm("sys", "hello", max_tokens=50),
    )
    assert isinstance(out, str)
    # Either the hardcoded miss string OR a real reply (if a tunnel is up)
    assert out != ""


def test_call_llm_with_meta_returns_shape(monkeypatch):
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "https://invalid.example")

    r = asyncio.new_event_loop().run_until_complete(
        call_llm_with_meta("sys", "hi", max_tokens=20),
    )
    assert "provider" in r
    assert "content" in r
    assert "ok" in r
    assert r["provider"] in LLM_PROVIDER_ORDER


def test_sovereign_health_grey_when_url_missing(monkeypatch):
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("SOVEREIGN_NODE_URL", raising=False)
    r = asyncio.new_event_loop().run_until_complete(sovereign_health())
    assert r["status"] == "grey"
    assert r["url"] is None


def test_sovereign_health_red_or_yellow_when_unreachable(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "https://offline-tunnel-xyz.invalid")
    r = asyncio.new_event_loop().run_until_complete(sovereign_health())
    assert r["status"] in ("red", "yellow")
    assert r["url"] == "https://offline-tunnel-xyz.invalid"


def test_composer_uses_gateway_not_direct_emergent_call():
    """Regression: outreach_composer must import llm_gateway.call_llm_with_meta,
    not the raw emergent SDK, so the Sovereign-first chain is honoured."""
    src = open("/app/backend/services/outreach_composer.py", "r",
                 encoding="utf-8").read()
    assert "from services.llm_gateway import call_llm_with_meta" in src
    # The raw LlmChat call path in the main compose loop must be gone
    # (we only allow it inside fallback utilities, which don't exist here).
    assert "LlmChat(" not in src


def test_morning_brief_uses_gateway():
    src = open("/app/backend/services/morning_brief.py", "r",
                 encoding="utf-8").read()
    assert "from services.llm_gateway import call_llm" in src


def test_dev_skill_uses_gateway():
    src = open("/app/backend/services/skill_router.py", "r",
                 encoding="utf-8").read()
    # _run_dev_skill must route via the gateway, not raw LlmChat
    import re
    dev_block = re.search(
        r"async def _run_dev_skill.*?(?=\n\nasync def )",
        src, re.DOTALL,
    )
    assert dev_block is not None
    assert "from services.llm_gateway import call_llm" in dev_block.group(0)
