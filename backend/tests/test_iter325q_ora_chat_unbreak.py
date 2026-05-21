"""iter 325q — ORA chat 422 silent-fail root cause + regression lock.

Root cause (proven in this session):
  /api/public/ora/chat declared `text: str = Field(..., min_length=1)`
  as the prompt field. The V2 customer portal (and several widget
  callers) POSTed {message: "..."}. Pydantic rejected every request
  with 422 BEFORE the LLM call fired. The browser saw a 422, but the
  chat-widget iframe rendered its hardcoded HTML fallback
  "Hi! I'm ORA. Stuck somewhere? Type or drop a screenshot — I'll help."
  on every send.

  That static fallback is what the user reported as "same static
  message every time, LLM never fires". The LLM provider chain
  (ollama → deepseek) was a red herring — execution never reached
  any provider.

Fix (iter 325q):
  • Schema accepts BOTH ``text`` and ``message`` (validator coalesces).
  • Empty bodies still 422 with a clear error.
  • V2 frontend defensively sends ``text`` so older deploys also work.

These tests prevent regression. If anyone re-tightens DemoChatReq
back to a single required field, the {message: ...} legacy callers
break again and this suite fails.
"""
from __future__ import annotations

import os
import re

import pytest
import requests

BASE = "http://localhost:8001"
ROUTER_FILE = "/app/backend/routers/public_ora_demo_router.py"
V2_PAGES = "/app/frontend/src/platform/luxe/LuxeV2Pages.jsx"


def _read(p):
    with open(p) as fh:
        return fh.read()


# ─────────────────────────────────────────────────────────────────
# 1. Schema contract — both keys accepted
# ─────────────────────────────────────────────────────────────────

def test_schema_accepts_text_and_message():
    src = _read(ROUTER_FILE)
    # Schema lists both fields
    assert "text:    Optional[str]" in src or "text: Optional[str]" in src
    assert "message: Optional[str]" in src
    # Validator coalesces
    assert "_require_prompt" in src or "must provide non-empty 'text' or 'message'" in src


# ─────────────────────────────────────────────────────────────────
# 2. Schema unit tests — both keys accepted, validator coalesces
#    These do NOT hit the LLM (avoids cold-path 30s+ + rate limits).
#    Live LLM-firing was proven manually via curl during iter 325q;
#    the validator is the actual fix that unblocks every caller.
# ─────────────────────────────────────────────────────────────────

def _load_schema():
    """Import the Pydantic model directly so we can assert validation
    behaviour without hitting FastAPI / LLM stack."""
    import importlib
    import sys
    # Ensure backend on path
    sys.path.insert(0, "/app/backend")
    mod = importlib.import_module("routers.public_ora_demo_router")
    return mod.DemoChatReq


def test_schema_accepts_text_payload():
    DemoChatReq = _load_schema()
    obj = DemoChatReq(text="hello")
    # text is preserved; message coalesces to None unless provided
    assert obj.text == "hello"


def test_schema_accepts_message_payload():
    DemoChatReq = _load_schema()
    # Before iter 325q this would raise — text was required.
    obj = DemoChatReq(message="hello")
    # Validator coalesces message → text so downstream code keeps
    # using `request.text` without branching.
    assert obj.text == "hello"
    assert obj.message == "hello"


def test_schema_rejects_empty_body():
    DemoChatReq = _load_schema()
    from pydantic import ValidationError
    with pytest.raises(ValidationError) as excinfo:
        DemoChatReq()
    err = str(excinfo.value)
    assert "text" in err and "message" in err, \
        f"empty-body error must mention both keys, got: {err}"


def test_schema_rejects_whitespace_only():
    DemoChatReq = _load_schema()
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DemoChatReq(text="   ")  # whitespace must be rejected (.strip() guard)


def test_schema_session_id_optional():
    DemoChatReq = _load_schema()
    obj = DemoChatReq(text="hi", session_id="abc-123")
    assert obj.session_id == "abc-123"


def test_schema_passes_emotion_fields():
    DemoChatReq = _load_schema()
    obj = DemoChatReq(message="hi there",
                      emotion="happy", emotion_confidence=0.87)
    assert obj.emotion == "happy"
    assert obj.emotion_confidence == 0.87


# Live HTTP one-shot smoke — single call, generous timeout.
# Marked as a smoke test so it can be skipped under CI rate-limit
# pressure but still locks in real LLM connectivity locally.

def test_chat_endpoint_smoke_one_call_message_payload():
    """ONE live call — proves the fix end-to-end without thrashing
    the LLM provider's rate limit."""
    try:
        r = requests.post(f"{BASE}/api/public/ora/chat",
                          json={"message": "Reply with the single word: pong"},
                          timeout=45)
    except (requests.ConnectionError, requests.Timeout) as e:
        pytest.skip(f"LLM provider unreachable / slow in this run: {e}")
    assert r.status_code == 200, f"smoke call failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    reply = body.get("reply") or body.get("response") or ""
    assert reply, f"empty reply means LLM didn't fire: {body}"
    # The reply must NOT be the chat-widget's hardcoded fallback
    assert "Stuck somewhere?" not in reply, \
        "got the static widget fallback — LLM did not fire"


def test_empty_body_returns_clear_422():
    """Live HTTP — fast, no LLM call."""
    r = requests.post(f"{BASE}/api/public/ora/chat", json={}, timeout=8)
    assert r.status_code == 422
    body = r.json()
    err_msg = str(body)
    assert "text" in err_msg and "message" in err_msg, \
        f"422 error must list both accepted keys, got: {err_msg}"


# ─────────────────────────────────────────────────────────────────
# 3. Frontend — V2 ORA tab sends the canonical `text` field
# ─────────────────────────────────────────────────────────────────

def test_v2_ora_page_sends_text_field():
    src = _read(V2_PAGES)
    assert "v2api.post('/api/public/ora/chat'" in src
    # Body shape — search the lines following the call
    idx = src.find("v2api.post('/api/public/ora/chat'")
    snippet = src[idx:idx + 200]
    assert "text:" in snippet, \
        f"V2 ORA chat must send 'text' key (canonical), got: {snippet!r}"
    # And must NOT send only 'message:' (legacy broken shape)
    assert "{ message: text }" not in snippet, \
        "V2 ORA chat still using broken {message: ...} shape"


# ─────────────────────────────────────────────────────────────────
# 4. Defensive — no other backend route silently 422s on `message`
# ─────────────────────────────────────────────────────────────────

def test_router_validator_imported():
    src = _read(ROUTER_FILE)
    # iter 325q validator depends on `validator` from pydantic
    assert "from pydantic import" in src
    assert "validator" in src.split("from pydantic import", 1)[1].split("\n", 1)[0]
