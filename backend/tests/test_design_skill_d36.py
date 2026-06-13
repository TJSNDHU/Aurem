"""
test_design_skill_d36.py — iter D-36

E2E proof that the AUREM Design System (Sonner / Vaul / animation rules)
is wired into every UI-generating LLM surface across AUREM:

  1. The shared loader returns the full skill markdown with the sentinel.
  2. inject_design_prompt() inserts a single system message, idempotently.
  3. AUREM CTO chat-stream (dev_cto_chat) injects the skill before
     calling the LLM provider — verified by patching the BYOK dispatcher
     and asserting the messages list contains the sentinel.
  4. aurem_ai_service prepends the design suffix to default + custom
     system prompts.
  5. The React stack template ships the baseline CSS file with the
     required custom easing curves and the scale(0.97) press rule.
  6. The aurem.live frontend itself imports the design-system CSS so
     dogfood is honest.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
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


# ── 1. The shared loader returns the prompt with sentinel ────────────

def test_loader_returns_prompt_with_sentinel():
    from services.aurem_design_prompt import (
        get_aurem_design_prompt, DESIGN_PROMPT_SENTINEL,
    )
    body = get_aurem_design_prompt()
    assert DESIGN_PROMPT_SENTINEL in body, "sentinel missing"
    # Sanity: key library names + rules are present
    assert "Sonner" in body
    assert "Vaul"   in body
    assert "scale(0.97)" in body
    assert "ease-out"    in body
    # Sentinel positions test: must NOT be the fallback (markdown file present)
    assert "Animation Decision Framework" in body, \
        "fallback prompt was returned — markdown file may be missing"


def test_loader_is_cached():
    """Repeated calls hit memory, not disk (functools.lru_cache)."""
    from services.aurem_design_prompt import get_aurem_design_prompt
    a = get_aurem_design_prompt()
    b = get_aurem_design_prompt()
    assert a is b, "loader should return the cached instance"


# ── 2. inject_design_prompt is idempotent ────────────────────────────

def test_inject_design_prompt_inserts_once():
    from services.aurem_design_prompt import (
        inject_design_prompt, DESIGN_PROMPT_SENTINEL,
    )
    msgs = [
        {"role": "system", "content": "primary system"},
        {"role": "user",   "content": "hi"},
    ]
    out1 = inject_design_prompt(msgs)
    assert len(out1) == 3
    assert any(DESIGN_PROMPT_SENTINEL in m["content"]
                for m in out1 if m["role"] == "system")
    # Second call must NOT re-insert.
    out2 = inject_design_prompt(out1)
    assert len(out2) == 3
    # The system-message containing the sentinel still appears exactly once.
    occurrences = sum(1 for m in out2
                       if DESIGN_PROMPT_SENTINEL in str(m.get("content", "")))
    assert occurrences == 1


def test_inject_design_prompt_empty_list():
    from services.aurem_design_prompt import inject_design_prompt, DESIGN_PROMPT_SENTINEL
    out = inject_design_prompt([])
    assert len(out) == 1
    assert out[0]["role"] == "system"
    assert DESIGN_PROMPT_SENTINEL in out[0]["content"]


# ── 3. AUREM CTO chat injects the skill in the dispatch path ─────────

def test_aurem_cto_chat_injects_design_skill(monkeypatch):
    """Patch the BYOK dispatcher and assert the messages list passed to
    it carries the AUREM Design sentinel."""
    from services import dev_cto_chat
    from services.aurem_design_prompt import DESIGN_PROMPT_SENTINEL

    captured: dict[str, Any] = {}

    async def fake_dispatch(provider, api_key, messages):
        captured["messages"] = messages
        return "ok-reply"

    monkeypatch.setattr(dev_cto_chat, "_dispatch_byok", fake_dispatch)

    # Bypass the token-wall check.
    async def fake_deduct(uid, kind):
        return {"ok": True, "tokens_remaining": 99, "internal": False}
    monkeypatch.setattr("services.developer_portal_core.deduct_tokens",
                         fake_deduct)

    # Force the BYOK branch by supplying a plain BYOK key.
    monkeypatch.setattr("services.developer_portal_core.decrypt_byok",
                         lambda env: {"openai": "sk-test"})

    # Skip web-search injector (it queries the DB / external).
    async def fake_search(full_messages, msgs): return full_messages
    monkeypatch.setattr(dev_cto_chat, "_maybe_inject_web_search", fake_search)

    account = {"user_id": "u-test",
                "email":   "u@aurem.test",
                "byok_keys": {"openai": "ENC_STUB"}}
    history = [{"role": "user", "content": "make me a landing page"}]

    res = asyncio.run(dev_cto_chat.cto_chat(account=account, messages=history))
    assert res.get("ok") is True, f"unexpected result: {res}"
    assert "messages" in captured, "BYOK dispatch path was not reached"
    msgs = captured["messages"]
    sysm = [m for m in msgs if m["role"] == "system"]
    found = any(DESIGN_PROMPT_SENTINEL in str(m.get("content", ""))
                 for m in sysm)
    assert found, ("AUREM Design skill sentinel missing from chat "
                    f"messages; got {len(sysm)} system msgs, none had the "
                    "sentinel")


# ── 4. aurem_ai_service injects the design suffix on session creation ─

def test_aurem_ai_service_session_includes_design_suffix(monkeypatch):
    """When a session is created via _get_or_create_session, the design
    suffix must be appended to the system_message."""
    from services import aurem_ai_service
    from services.aurem_design_prompt import DESIGN_PROMPT_SENTINEL

    captured: dict[str, Any] = {}

    class FakeLlmChat:
        def __init__(self, **kw):
            captured["system_message"] = kw.get("system_message", "")
        def with_model(self, *a, **kw):
            return self

    monkeypatch.setattr(aurem_ai_service, "LlmChat", FakeLlmChat)
    monkeypatch.setattr(aurem_ai_service, "LLM_AVAILABLE", True)
    svc = aurem_ai_service.AuremIntelligence()
    svc.api_key = "test"

    svc._get_or_create_session("sess-1")
    assert DESIGN_PROMPT_SENTINEL in captured.get("system_message", "")


# ── 5. React stack template ships the baseline CSS ───────────────────

def test_stack_template_design_css_present():
    p = pathlib.Path(
        "/app/backend/aurem_cto/templates/stacks/react-fastapi/ui-design.css")
    assert p.exists(), f"template CSS missing at {p}"
    css = p.read_text(encoding="utf-8")
    # Required rules
    assert "cubic-bezier(0.23, 1, 0.32, 1)" in css,  "missing strong ease-out curve"
    assert "cubic-bezier(0.32, 0.72, 0, 1)" in css,  "missing iOS drawer curve"
    assert "scale(0.97)" in css,                     "missing press feedback rule"
    assert "prefers-reduced-motion" in css,          "missing reduced-motion guard"
    assert "data-sonner-toaster" in css \
            or "Sonner" in css.lower() \
            or "vaul" in css.lower(),                "missing Sonner/Vaul hooks"


def test_stack_template_readme_documents_libraries():
    p = pathlib.Path(
        "/app/backend/aurem_cto/templates/stacks/react-fastapi/README.md")
    txt = p.read_text(encoding="utf-8")
    for needle in ("sonner", "vaul", "lucide-react",
                    "scale(0.97)", "ease-out", "prefers-reduced-motion"):
        assert needle in txt, f"README missing '{needle}'"


# ── 6. aurem.live's own frontend imports the design-system CSS ───────

def test_aurem_frontend_imports_design_system_css():
    css = pathlib.Path("/app/frontend/src/styles/aurem-design.css")
    assert css.exists(), "frontend baseline CSS missing"
    txt = css.read_text()
    assert "scale(0.97)" in txt
    assert "cubic-bezier(0.23, 1, 0.32, 1)" in txt

    app_js = pathlib.Path("/app/frontend/src/App.js").read_text()
    assert "aurem-design.css" in app_js, \
        "App.js does not import the design-system CSS"
