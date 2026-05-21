"""
Retell voice-call bug fix tests — iter 325h.

Background: `_retell_create_phone_call` was a 2-arg function
(agent_id, to_number). `services/agents/closer_ora.py` was calling it
with `(to_number=phone, lead_context={...})` — no agent_id and a kwarg
that didn't exist. Every closer call raised TypeError, swallowed by the
try/except, and never reached Retell. Confirmation query proved 141/141
historical closer rows failed this way.

Fix:
  - Widened `_retell_create_phone_call` to
    `(agent_id, to_number, lead_context=None)`.
  - Returns a dict `{ok, call_id, error}` instead of a bare string.
  - Forwards `lead_context` into Retell's `retell_llm_dynamic_variables`
    so the AI prompt can address the lead by name.
  - `closer_ora.py` now resolves `agent_id` from lead config or
    `RETELL_AGENT_ID` env var.
"""
import asyncio
import inspect
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, "/app/backend")


# ─────────────────────────────────────────────────────────────────────
# 1. New signature exists and is backwards-compatible
# ─────────────────────────────────────────────────────────────────────
def test_retell_function_accepts_lead_context_kwarg():
    """The bug was a TypeError on `lead_context=`. After the fix the
    parameter must exist on the function signature."""
    from routers.voice_agent_router import _retell_create_phone_call
    sig = inspect.signature(_retell_create_phone_call)
    params = list(sig.parameters.keys())
    assert "agent_id" in params, "agent_id must still be the primary param"
    assert "to_number" in params, "to_number must still be a param"
    assert "lead_context" in params, "lead_context must now be accepted"
    # And it must have a default so old call-sites (test endpoint) keep working.
    assert sig.parameters["lead_context"].default is None


# ─────────────────────────────────────────────────────────────────────
# 2. lead_context is forwarded as retell_llm_dynamic_variables
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_lead_context_flows_into_dynamic_variables(monkeypatch):
    """Retell's create-phone-call API expects extra context under
    `retell_llm_dynamic_variables` so the AI agent prompt can reference
    them. Values must all be stringified."""
    from routers import voice_agent_router as vr
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+14314500004")

    captured = {}
    async def fake_request(method, path, payload):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        return {"call_id": "call_abc123"}
    monkeypatch.setattr(vr, "_retell_request", fake_request)

    out = await vr._retell_create_phone_call(
        agent_id="agent_xyz",
        to_number="+15551234567",
        lead_context={
            "business_name": "Acme Inc",
            "owner_name": "Jane",
            "trigger": "HOT_REPLY",
            "plan": "starter",
            "minutes_left": 17,  # int — must be stringified
        },
    )
    assert out["ok"] is True
    assert out["call_id"] == "call_abc123"
    assert out["error"] is None
    payload = captured["payload"]
    assert payload["from_number"] == "+14314500004"
    assert payload["to_number"] == "+15551234567"
    assert payload["override_agent_id"] == "agent_xyz"
    dyn = payload["retell_llm_dynamic_variables"]
    assert dyn["business_name"] == "Acme Inc"
    assert dyn["owner_name"] == "Jane"
    assert dyn["minutes_left"] == "17"  # stringified


# ─────────────────────────────────────────────────────────────────────
# 3. Missing agent_id is now a graceful failure, not an exception
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_missing_agent_id_returns_graceful_error(monkeypatch):
    from routers import voice_agent_router as vr
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+14314500004")
    out = await vr._retell_create_phone_call(
        agent_id="", to_number="+15551234567")
    assert out["ok"] is False
    assert out["call_id"] == ""
    assert "agent_id missing" in out["error"]


@pytest.mark.asyncio
async def test_missing_from_number_returns_graceful_error(monkeypatch):
    from routers import voice_agent_router as vr
    monkeypatch.delenv("RETELL_FROM_NUMBER", raising=False)
    out = await vr._retell_create_phone_call(
        agent_id="agent_xyz", to_number="+15551234567")
    assert out["ok"] is False
    assert "RETELL_FROM_NUMBER not set" in out["error"]


# ─────────────────────────────────────────────────────────────────────
# 4. closer_ora call site now passes agent_id (regression-guard the bug)
# ─────────────────────────────────────────────────────────────────────
def test_closer_ora_call_site_passes_agent_id():
    """The bug was that closer_ora forgot to pass agent_id and instead
    sent a kwarg that didn't exist. The fixed source MUST now pass
    agent_id explicitly."""
    src = open(
        "/app/backend/services/agents/closer_ora.py", encoding="utf-8"
    ).read()
    # Must resolve agent_id from somewhere (env or lead config).
    assert "RETELL_AGENT_ID" in src or "retell_agent_id" in src
    # Must call the function with agent_id= as a kwarg.
    assert "agent_id=agent_id" in src
    # And it must STILL pass lead_context — that's the whole point of the widen.
    assert "lead_context=" in src


def test_closer_ora_call_site_no_longer_misses_agent_id():
    """Old (buggy) call shape: `_retell_create_phone_call(to_number=phone, lead_context=...)`
    with no agent_id positional or kwarg. Make sure that pattern is GONE."""
    src = open(
        "/app/backend/services/agents/closer_ora.py", encoding="utf-8"
    ).read()
    # The full buggy call body — must not appear verbatim.
    buggy = "_retell_create_phone_call(\n            to_number=phone"
    assert buggy not in src


# ─────────────────────────────────────────────────────────────────────
# 5. End-to-end: closer_ora's _ask_cto path returns dict — even when
#    the Retell API errors out, no TypeError reaches the caller.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retell_call_never_raises_typeerror_anymore(monkeypatch):
    """Belt and braces — exercise the same kwargs closer_ora now uses
    and confirm the call returns a dict instead of raising."""
    from routers import voice_agent_router as vr
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+14314500004")

    async def fake_request(*a, **kw):
        # Simulate Retell rejecting (e.g. invalid agent).
        return {"error": "agent_not_found"}
    monkeypatch.setattr(vr, "_retell_request", fake_request)

    # Call EXACTLY like the fixed closer_ora does.
    out = await vr._retell_create_phone_call(
        agent_id="agent_xyz",
        to_number="+15551234567",
        lead_context={
            "business_name": "Test Biz",
            "owner_name": "Sam",
            "trigger": "NO_REPLY_DAY5",
            "plan": "starter",
        },
    )
    assert isinstance(out, dict), "must return dict, not raise"
    assert out["ok"] is False
    # No call_id from Retell → graceful failure surfaced.
    assert out["call_id"] == ""


@pytest.mark.asyncio
async def test_admin_test_call_endpoint_handles_new_dict_shape(monkeypatch):
    """The admin "Test Call" endpoint at /api/admin/voice-agent/test-call
    used to assume the function returned a string. After the widen it
    returns a dict. The handler must surface call_id correctly."""
    src = open(
        "/app/backend/routers/voice_agent_router.py", encoding="utf-8"
    ).read()
    # Look at the test-call handler block — it must unpack result["call_id"]
    # and NOT just stuff the whole result into the response as call_id.
    assert "result = await _retell_create_phone_call" in src
    assert 'result.get("call_id")' in src
    # And it must check ok first.
    assert 'if not result.get("ok")' in src
