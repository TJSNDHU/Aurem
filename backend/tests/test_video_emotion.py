"""
iter 282al-14 — Tests for ORA Video Session emotion-aware tone.

Verifies:
  1. `/api/public/ora/chat` accepts `emotion` + `emotion_confidence`
     fields and the schema validation passes.
  2. The `_emotion_context` helper emits the correct tone hint string
     for known emotions and an empty string for unknown / missing.
  3. `aurem_chat.ChatRequest` accepts the same fields.
  4. Emotion line is injected into the system prompt path used by the
     LLM call (verified via a stubbed LlmChat that captures the prompt).
"""
from __future__ import annotations

import importlib
import sys
import types
import pytest


# ── Helper-level tests (no I/O) ─────────────────────────────────────
def test_emotion_context_known_label():
    from routers.public_ora_demo_router import _emotion_context
    out = _emotion_context("happy", 0.83)
    assert "happy" in out
    assert "83%" in out
    assert "warmth" in out.lower() or "upbeat" in out.lower()


def test_emotion_context_unknown_label_is_empty():
    from routers.public_ora_demo_router import _emotion_context
    assert _emotion_context("ecstatic", 0.9) == ""
    assert _emotion_context(None, 0.9) == ""
    assert _emotion_context("", 0.9) == ""


def test_emotion_context_handles_missing_confidence():
    from routers.public_ora_demo_router import _emotion_context
    out = _emotion_context("sad", None)
    assert "sad" in out
    assert "—" in out  # fallback symbol when confidence unknown


# ── Schema acceptance tests ─────────────────────────────────────────
def test_demo_chat_req_accepts_emotion():
    from routers.public_ora_demo_router import DemoChatReq
    r = DemoChatReq(text="hi", emotion="happy", emotion_confidence=0.72)
    assert r.emotion == "happy"
    assert r.emotion_confidence == 0.72


def test_demo_chat_req_emotion_optional():
    from routers.public_ora_demo_router import DemoChatReq
    r = DemoChatReq(text="hi")
    assert r.emotion is None
    assert r.emotion_confidence is None


def test_demo_chat_req_rejects_invalid_confidence():
    from routers.public_ora_demo_router import DemoChatReq
    with pytest.raises(Exception):
        DemoChatReq(text="hi", emotion="happy", emotion_confidence=1.5)


def test_aurem_chat_request_accepts_emotion():
    from routers.aurem_chat import ChatRequest
    r = ChatRequest(message="hi", emotion="angry", emotion_confidence=0.55)
    assert r.emotion == "angry"
    assert r.emotion_confidence == 0.55


def test_aurem_chat_emotion_helper_known_and_unknown():
    from routers.aurem_chat import _emotion_context
    assert "angry" in _emotion_context("angry", 0.9).lower()
    assert _emotion_context("blissful", 0.9) == ""


# ── End-to-end: stub LLM, confirm prompt carries emotion ────────────
@pytest.mark.asyncio
async def test_public_demo_chat_injects_emotion_into_system_prompt(monkeypatch):
    """
    Stub `emergentintegrations.llm.chat` so we can capture the
    system_message passed to the LLM and confirm the emotion line lands.
    """
    captured: dict = {}

    class _StubMessage:
        def __init__(self, *_, **__): pass

    class _StubChat:
        def __init__(self, api_key=None, session_id=None, system_message=None):
            captured["system"] = system_message

        def with_model(self, *_a, **_kw):
            return self

        async def send_message(self, *_a, **_kw):
            return "stubbed reply"

    fake_mod = types.ModuleType("emergentintegrations.llm.chat")
    fake_mod.LlmChat = _StubChat
    fake_mod.UserMessage = _StubMessage
    fake_pkg = types.ModuleType("emergentintegrations.llm")
    fake_pkg.chat = fake_mod
    fake_root = types.ModuleType("emergentintegrations")
    fake_root.llm = fake_pkg
    sys.modules["emergentintegrations"] = fake_root
    sys.modules["emergentintegrations.llm"] = fake_pkg
    sys.modules["emergentintegrations.llm.chat"] = fake_mod

    # Force re-import so the patched module is picked up
    if "routers.public_ora_demo_router" in sys.modules:
        importlib.reload(sys.modules["routers.public_ora_demo_router"])
    mod = importlib.import_module("routers.public_ora_demo_router")

    req = mod.DemoChatReq(
        text="hello", emotion="sad", emotion_confidence=0.71,
    )
    out = await mod.public_demo_chat(req, authorization=None)
    assert out["ok"] is True
    assert out["reply"] == "stubbed reply"
    assert "sad" in (captured.get("system") or "").lower()
    assert "LIVE EMOTION SIGNAL" in (captured.get("system") or "")
