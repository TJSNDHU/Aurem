"""iter 325j — ORA chat agent DeepSeek wiring regression tests.

Locks in:
  1. ``deepseek`` is a valid provider in the chat chain.
  2. Default provider order leads with DeepSeek (not legion_ollama).
  3. ``_deepseek_with_tools`` hits OpenRouter with the right model + tools.
  4. The degraded-mode fallback no longer hardcodes Ollama troubleshooting.
"""
from __future__ import annotations

import asyncio
import inspect
import os
from unittest.mock import patch, AsyncMock

import pytest

from services import ora_agent

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


def test_deepseek_function_exists():
    assert hasattr(ora_agent, "_deepseek_with_tools")
    sig = inspect.signature(ora_agent._deepseek_with_tools)
    assert "messages" in sig.parameters
    assert "model" in sig.parameters


def test_default_provider_order_leads_with_deepseek(monkeypatch):
    """Default order must start with deepseek so chat never tries laptop first."""
    monkeypatch.delenv("ORA_AGENT_PROVIDER_ORDER", raising=False)
    src = inspect.getsource(ora_agent._llm_turn)
    # The literal default string in _llm_turn
    assert '"deepseek,claude,legion_ollama,groq"' in src or \
           "'deepseek,claude,legion_ollama,groq'" in src


def test_env_default_is_deepseek_first():
    """The .env file must mirror the in-code default so prod parity holds."""
    env_path = "/app/backend/.env"
    if not os.path.exists(env_path):
        pytest.skip(".env not present in this environment")
    with open(env_path) as fh:
        body = fh.read()
    assert "ORA_AGENT_PROVIDER_ORDER=deepseek" in body, \
        "ORA chat must lead with DeepSeek in .env"


def test_deepseek_uses_openrouter_v31_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    captured = {}

    class _FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {"choices": [{"message": {"content": "ok", "tool_calls": []}}]}

    class _FakeClient:
        def __init__(self, *a, **kw):
            self.timeout = kw.get("timeout")
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["model"] = json["model"]
            captured["has_tools"] = "tools" in json
            captured["auth"] = headers.get("Authorization", "")
            return _FakeResp()

    with patch.object(ora_agent.httpx, "AsyncClient", _FakeClient):
        msg = asyncio.run(ora_agent._deepseek_with_tools([{"role": "user", "content": "hi"}]))

    assert msg == {"content": "ok", "tool_calls": []}
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["model"] == "deepseek/deepseek-chat-v3.1"
    assert captured["has_tools"] is True
    assert captured["auth"].startswith("Bearer sk-or-test")


def test_deepseek_no_key_returns_none(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = asyncio.run(ora_agent._deepseek_with_tools([{"role": "user", "content": "x"}]))
    assert result is None


def test_llm_turn_dispatches_to_deepseek(monkeypatch):
    """When provider order starts with 'deepseek', _llm_turn must call it."""
    monkeypatch.setenv("ORA_AGENT_PROVIDER_ORDER", "deepseek")

    fake_msg = {"content": "from deepseek", "tool_calls": []}
    called = {"n": 0}

    async def _fake_ds(messages, *, model=None):
        called["n"] += 1
        return fake_msg

    with patch.object(ora_agent, "_deepseek_with_tools", _fake_ds):
        out = asyncio.run(ora_agent._llm_turn([{"role": "user", "content": "ping"}]))

    assert out == fake_msg
    assert called["n"] == 1


def test_degraded_fallback_no_longer_mentions_ollama_list():
    """The hardcoded laptop troubleshooting must be gone."""
    src = inspect.getsource(ora_agent)
    # The OLD bug-text must be removed
    assert "ollama list" not in src
    assert "pkill -9 -f legion_daemon" not in src
    assert "tail -5 ~/legion_daemon.log" not in src
    # The NEW guidance must be present
    assert "DeepSeek" in src
    assert "OpenRouter key" in src or "OPENROUTER_API_KEY" in src
