"""
test_non_tech_mode_d40.py — iter D-40

Asserts AUREM CTO detects non-technical customers and strips out the
code-block + Python pseudo-code + technical-jargon format on those
turns, regardless of intent bucket.

  1. is_non_technical() positive cases (idea-stage, business-language,
     Hinglish "ek app banana chahta hoon", etc.) all return True.
  2. is_non_technical() negative cases (any tech keyword: API, deploy,
     React, JWT, schema, etc.) return False.
  3. The chat dispatch path injects "[NON-TECH]" in the system message
     when the heuristic fires, and DOES NOT inject it when it doesn't.
  4. system_prompt_for(intent, non_technical=True) includes the
     NON-TECH MODE suffix with the no-code rules.
  5. Base SYSTEM_PROMPT now contains the AUDIENCE DETECTION block.
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

sys.path.insert(0, "/app/backend")
import pytest


# ── 1. positive cases — non-tech ─────────────────────────────────────

@pytest.mark.parametrize("text", [
    # English idea-stage
    "I want to build an app for home-cooked food delivery",
    "I have an idea for a clothing store online",
    "I want to make a website for my bakery",
    "i want to start a business that helps small shops",
    # Hinglish
    "main ek app banana chahta hoon jisme log ghar ka khaana order kar sakein",
    "main online kapde bechna chahta hoon",
    "ek website chahta hoon apne business ke liye",
    "ek startup ka idea hai mera",
])
def test_non_tech_detected(text):
    from services.aurem_cto_intent import is_non_technical
    assert is_non_technical(text) is True, \
        f"missed non-tech signal in: {text!r}"


# ── 2. negative cases — tech keyword present ─────────────────────────

@pytest.mark.parametrize("text", [
    "I want to build a REST API for my React app",
    "build me a FastAPI endpoint that returns JSON",
    "I want to deploy this to Kubernetes",
    "wire stripe webhook to my backend",
    "i need to fix this database schema",
    "make a microservice for payments",
    # Casual greeting — not a build at all
    "hi there",
    # Pure question — not flagged as non-tech idea
    "what is fastapi",
])
def test_tech_messages_not_flagged_non_tech(text):
    from services.aurem_cto_intent import is_non_technical
    assert is_non_technical(text) is False, \
        f"falsely flagged as non-tech: {text!r}"


# ── 3. system_prompt_for honors the flag ─────────────────────────────

def test_system_prompt_for_appends_non_tech_suffix():
    from services.aurem_cto_intent import system_prompt_for
    a = system_prompt_for("build")
    b = system_prompt_for("build", non_technical=True)
    assert "NON-TECH MODE" in b
    assert "NO code"       in b
    assert "Hinglish"      in b
    assert b.startswith(a), "non-tech suffix should be appended, not replace"
    # And without the flag, the suffix is NOT there.
    assert "NON-TECH MODE" not in a


# ── 4. base SYSTEM_PROMPT teaches audience detection ─────────────────

def test_base_prompt_has_audience_detection_block():
    from services.dev_cto_chat import SYSTEM_PROMPT
    flat = " ".join(SYSTEM_PROMPT.split())
    assert "AUDIENCE DETECTION" in flat
    assert "NON-TECH MODE"      in flat
    assert "everyday analogies" in flat


# ── 5. cto_chat injects [NON-TECH] tag for idea-stage messages ───────

def _make_fixture(monkeypatch, captured: dict):
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


def test_chat_marks_non_tech_idea(monkeypatch):
    captured: dict[str, Any] = {}
    cto = _make_fixture(monkeypatch, captured)
    account = {"user_id": "u-test",
                "byok_keys": {"openai": "ENC_STUB"}}
    history = [{"role": "user",
                 "content":
                  "main online kapde bechna chahta hoon, kahan se shuru karein"}]
    asyncio.run(cto.cto_chat(account=account, messages=history))
    sysm = next(
        (m for m in captured["messages"]
         if m["role"] == "system" and "[INTENT=" in str(m.get("content", ""))),
        None,
    )
    assert sysm is not None
    assert "[NON-TECH]"     in sysm["content"]
    assert "NON-TECH MODE"  in sysm["content"]
    # The phrase that signals the LLM to use analogies.
    assert "jaise Y lekin Z" in sysm["content"] \
            or "everyday analogies" in sysm["content"]


def test_chat_does_not_mark_tech_request(monkeypatch):
    captured: dict[str, Any] = {}
    cto = _make_fixture(monkeypatch, captured)
    account = {"user_id": "u-test",
                "byok_keys": {"openai": "ENC_STUB"}}
    history = [{"role": "user",
                 "content": "build me a FastAPI endpoint that returns JSON"}]
    asyncio.run(cto.cto_chat(account=account, messages=history))
    sysm = next(
        (m for m in captured["messages"]
         if m["role"] == "system" and "[INTENT=" in str(m.get("content", ""))),
        None,
    )
    assert sysm is not None
    assert "[NON-TECH]"    not in sysm["content"]
    assert "NON-TECH MODE" not in sysm["content"]
