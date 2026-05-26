"""
iter 332b D-29 — Dev CTO chat web search injection.

Founder report: "our developer chat said they dont have access to direct
internet". We already pay for Tavily (used by Scout), so the LLM just
wasn't being given the results. This iter:

  1. Extends the system prompt to declare live web search.
  2. Adds `_maybe_inject_web_search()` which sniffs the latest user
     message for search-intent (URLs / "latest" / "/search …" / etc.)
     and injects the top 3 Tavily hits as a system message *before*
     the user's question.
  3. Wires both `cto_chat()` (BYOK) and `cto_chat_stream()` (free tier).
  4. Updates the chat UI placeholder + tier badge to advertise it.
"""
from __future__ import annotations

import pytest


def test_system_prompt_advertises_internet():
    from services import dev_cto_chat as M
    assert "INTERNET ACCESS" in M.SYSTEM_PROMPT
    assert "Tavily" in M.SYSTEM_PROMPT or "web search" in M.SYSTEM_PROMPT
    # The "don't claim no internet" rule must be present.
    assert "don't claim you have no internet" in M.SYSTEM_PROMPT


# ── Query extraction heuristics ───────────────────────────────────────
def test_extract_query_slash_search_prefix():
    from services.dev_cto_chat import _extract_search_query
    assert _extract_search_query("/search Postgres LISTEN/NOTIFY") == "Postgres LISTEN/NOTIFY"
    assert _extract_search_query("/web how does FastAPI lifespan work") == "how does FastAPI lifespan work"


def test_extract_query_url_in_prompt():
    from services.dev_cto_chat import _extract_search_query
    out = _extract_search_query("Read https://fastapi.tiangolo.com/lifespan/ and tell me")
    assert out and out.startswith("https://")


def test_extract_query_recency_intent():
    from services.dev_cto_chat import _extract_search_query
    assert _extract_search_query("What is the latest React 19 syntax?") is not None
    assert _extract_search_query("look up Stripe checkout 2026") is not None
    assert _extract_search_query("find me a Tavily SDK example") is not None


def test_extract_query_skips_normal_messages():
    from services.dev_cto_chat import _extract_search_query
    # Plain greetings / code chatter should NOT trigger search.
    assert _extract_search_query("Hi") is None
    assert _extract_search_query("write me a Python function to add two ints") is None
    assert _extract_search_query("explain my code") is None
    # Empty + oversize bail safely.
    assert _extract_search_query("") is None
    assert _extract_search_query("x" * 2000) is None


# ── Injection path actually inserts a system message before the user turn ─
@pytest.mark.asyncio
async def test_injects_tavily_results_before_user_turn(monkeypatch):
    from services import dev_cto_chat as M

    async def fake_tavily(query, **_):
        assert "FastAPI" in query
        return {
            "answer": "FastAPI is a modern Python web framework.",
            "results": [
                {"title": "FastAPI Docs", "url": "https://fastapi.tiangolo.com",
                 "content": "Official documentation."},
                {"title": "GitHub", "url": "https://github.com/fastapi/fastapi",
                 "content": "Source code."},
            ],
        }
    # Patch the import target inside the helper.
    import services.tier1_upgrades as TU
    monkeypatch.setattr(TU, "tavily_search", fake_tavily, raising=False)

    full = [
        {"role": "system", "content": "<system prompt>"},
        {"role": "user", "content": "What is the latest FastAPI version?"},
    ]
    out = await M._maybe_inject_web_search(full, [full[1]])
    # Injected one system message right BEFORE the user turn.
    assert len(out) == 3
    assert out[-1]["role"] == "user"
    assert out[-2]["role"] == "system"
    injected = out[-2]["content"]
    assert "Live web search results" in injected
    assert "FastAPI Docs" in injected
    assert "https://fastapi.tiangolo.com" in injected


@pytest.mark.asyncio
async def test_injection_noop_when_no_intent(monkeypatch):
    from services import dev_cto_chat as M
    # Even if Tavily would respond, no-intent message must not trigger.
    called = {"n": 0}
    async def fake_tavily(q, **_):
        called["n"] += 1
        return {"results": []}
    import services.tier1_upgrades as TU
    monkeypatch.setattr(TU, "tavily_search", fake_tavily, raising=False)

    full = [{"role": "system", "content": "<sys>"},
            {"role": "user", "content": "write a haiku about cats"}]
    out = await M._maybe_inject_web_search(full, [full[1]])
    assert out == full
    assert called["n"] == 0


# ── Frontend UI flags live search ────────────────────────────────────
def test_chat_panel_advertises_live_web():
    src = open("/app/frontend/src/platform/developers/DevCtoChatPanel.jsx").read()
    assert "/search" in src
    assert "Live web" in src
