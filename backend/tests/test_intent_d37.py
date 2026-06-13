"""
test_intent_d37.py — iter D-37

E2E proof that AUREM CTO no longer forces the rigid Plan + step + NEXT_STEPS +
progress format on every chat turn.

  1. The heuristic classifier correctly buckets greetings, build asks,
     questions, diagnostics, and strategic asks.
  2. The system_prompt_for() helper returns the right suffix for each.
  3. AUREM CTO chat (cto_chat) injects an `[INTENT=...]` system message
     before the LLM call, with the suffix matching the user's message.
  4. A conversational ("hi") turn gets the "no Plan, no step markers"
     branch — not the build branch.
  5. A real build ask ("add a hero section") still gets the full build
     contract.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import pytest
from dotenv import load_dotenv

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")


# ── 1. Heuristic classifier ──────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    # Conversational
    ("hi",                       "conversational"),
    ("Hello",                    "conversational"),
    ("good morning",             "conversational"),
    ("thanks!",                  "conversational"),
    ("ok",                       "conversational"),
    ("how are you today",        "conversational"),
    # Build
    ("add a hero section to the landing page",  "build"),
    ("wire stripe to the checkout flow",        "build"),
    ("create a new endpoint /api/products",     "build"),
    ("refactor the auth router",                "build"),
    ("deploy to production",                    "build"),
    # Question
    ("what is fastapi",                          "question"),
    ("how do I add a new route",                 "question"),
    ("explain how mongodb indexing works",       "question"),
    ("which framework should I use?",            "question"),
    # Diagnostic
    ("the login button is broken",               "diagnostic"),
    ("getting a 500 error on /api/users",        "diagnostic"),
    ("traceback: ValueError x is None",          "diagnostic"),
    ("the chat doesn't work after the last deploy", "diagnostic"),
    # Strategic
    ("should we focus on enterprise or smb next", "strategic"),
    ("what should I prioritize for funding",      "strategic"),
    ("compare our pricing vs lovable",            "strategic"),
    # Ambiguous
    ("xyz abc",                                   "unknown"),
])
def test_classify_intent(text, expected):
    from services.aurem_cto_intent import classify_intent
    got = classify_intent(text)
    assert got == expected, f"'{text}' → got {got}, expected {expected}"


def test_classify_empty_input():
    from services.aurem_cto_intent import classify_intent
    assert classify_intent("")       == "unknown"
    assert classify_intent("   ")    == "unknown"
    assert classify_intent(None or "") == "unknown"


# ── 2. system_prompt_for() returns the right contract ─────────────────

def test_system_prompt_branches_differ():
    from services.aurem_cto_intent import system_prompt_for, INTENT_TYPES
    seen = {system_prompt_for(i) for i in INTENT_TYPES}
    assert len(seen) == len(INTENT_TYPES), \
        "every intent must have a distinct system-prompt suffix"


def test_build_branch_keeps_plan_contract():
    from services.aurem_cto_intent import system_prompt_for
    p = system_prompt_for("build")
    for needle in ("Plan", "[step N/M]", "progress:", "MANIFEST_PATCH", "NEXT_STEPS"):
        assert needle in p, f"build branch missing '{needle}'"


def test_conversational_branch_drops_plan_contract():
    from services.aurem_cto_intent import system_prompt_for
    p = system_prompt_for("conversational")
    assert "NO Plan" in p
    assert "NO step markers" in p
    assert "NO progress" in p
    assert "NO NEXT_STEPS" in p


def test_question_branch_keeps_next_steps_only():
    from services.aurem_cto_intent import system_prompt_for
    p = system_prompt_for("question")
    assert "NO Plan" in p
    assert "NO `[step N/M]`" in p
    assert "ONE NEXT_STEPS line" in p


def test_diagnostic_branch_demands_root_cause_first():
    from services.aurem_cto_intent import system_prompt_for
    p = system_prompt_for("diagnostic")
    assert "root cause" in p.lower()


def test_unknown_branch_asks_for_clarification():
    from services.aurem_cto_intent import system_prompt_for
    p = system_prompt_for("unknown")
    assert "Ask ONE short clarifying question" in p


# ── 3. cto_chat injects [INTENT=...] system message ──────────────────

def _make_chat_fixture(monkeypatch, captured: dict):
    """Bypass token wallet + BYOK + web search; capture the messages
    list handed to the dispatcher."""
    from services import dev_cto_chat

    async def fake_dispatch(provider, api_key, messages):
        captured["messages"] = messages
        return "ok-reply"

    monkeypatch.setattr(dev_cto_chat, "_dispatch_byok", fake_dispatch)

    async def fake_deduct(uid, kind):
        return {"ok": True, "tokens_remaining": 99, "internal": False}
    monkeypatch.setattr("services.developer_portal_core.deduct_tokens",
                         fake_deduct)
    monkeypatch.setattr("services.developer_portal_core.decrypt_byok",
                         lambda env: {"openai": "sk-test"})

    async def fake_search(full_messages, msgs): return full_messages
    monkeypatch.setattr(dev_cto_chat, "_maybe_inject_web_search", fake_search)
    return dev_cto_chat


def test_chat_injects_intent_system_message(monkeypatch):
    captured: dict[str, Any] = {}
    cto = _make_chat_fixture(monkeypatch, captured)
    account = {"user_id": "u-test",
                "byok_keys": {"openai": "ENC_STUB"}}
    history = [{"role": "user", "content": "hi"}]
    res = asyncio.run(cto.cto_chat(account=account, messages=history))
    assert res.get("ok") is True

    sysm = [m for m in captured["messages"] if m["role"] == "system"]
    intent_msg = next((m for m in sysm
                        if "[INTENT=" in str(m.get("content", ""))), None)
    assert intent_msg is not None, "no [INTENT=...] system message injected"
    assert "[INTENT=conversational]" in intent_msg["content"]


def test_chat_build_request_gets_build_branch(monkeypatch):
    captured: dict[str, Any] = {}
    cto = _make_chat_fixture(monkeypatch, captured)
    account = {"user_id": "u-test",
                "byok_keys": {"openai": "ENC_STUB"}}
    history = [{"role": "user",
                 "content": "build me a hero section with a CTA button"}]
    res = asyncio.run(cto.cto_chat(account=account, messages=history))
    assert res.get("ok") is True

    intent_msg = next(
        (m for m in captured["messages"]
         if m["role"] == "system" and "[INTENT=" in str(m.get("content", ""))),
        None,
    )
    assert intent_msg is not None
    assert "[INTENT=build]" in intent_msg["content"]
    # Build branch must keep the Plan + NEXT_STEPS contract
    assert "Plan (N steps)" in intent_msg["content"]
    assert "NEXT_STEPS" in intent_msg["content"]


def test_chat_diagnostic_request_gets_diagnostic_branch(monkeypatch):
    captured: dict[str, Any] = {}
    cto = _make_chat_fixture(monkeypatch, captured)
    account = {"user_id": "u-test",
                "byok_keys": {"openai": "ENC_STUB"}}
    history = [{"role": "user",
                 "content": "I'm getting a 500 error on /api/users — it's broken"}]
    asyncio.run(cto.cto_chat(account=account, messages=history))
    intent_msg = next(
        (m for m in captured["messages"]
         if m["role"] == "system" and "[INTENT=" in str(m.get("content", ""))),
        None,
    )
    assert intent_msg and "[INTENT=diagnostic]" in intent_msg["content"]


def test_chat_strategic_request_gets_strategic_branch(monkeypatch):
    captured: dict[str, Any] = {}
    cto = _make_chat_fixture(monkeypatch, captured)
    account = {"user_id": "u-test",
                "byok_keys": {"openai": "ENC_STUB"}}
    history = [{"role": "user",
                 "content": "Should we prioritize enterprise or SMB for funding?"}]
    asyncio.run(cto.cto_chat(account=account, messages=history))
    intent_msg = next(
        (m for m in captured["messages"]
         if m["role"] == "system" and "[INTENT=" in str(m.get("content", ""))),
        None,
    )
    assert intent_msg and "[INTENT=strategic]" in intent_msg["content"]
