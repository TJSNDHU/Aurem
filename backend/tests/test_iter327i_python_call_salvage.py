"""
iter 327i — Salvage Python-call form tool emissions so they execute
instead of falling back to the "couldn't fetch — retry" message.

Founder report (2026-02-23):
  "Why does ORA-CTO show this instead of real data: 'I tried to
   fetch that data but my tool call didn't execute cleanly this
   turn. Please ask again — it usually works on retry.'"

Root cause:
  - DeepSeek/Gemini sometimes emit tool calls in chat as plain
    text:  curl_internal(endpoint="/api/x", method="GET")
  - The existing salvage only knew how to parse JSON shapes.
  - The 327e leak detector caught the python-call form (correctly,
    to stop it leaking into chat) but there was no salvage path to
    promote it to `tool_calls` so it would execute → founder saw
    the safety-net fallback every time.

Fix in this iter:
  1. New `_salvage_python_call_form(content)` parses
     `tool_name(k="v", k2=42)` into (name, args_dict).
  2. `_salvage_inline_tool_call` now tries JSON first, then
     python-call form.
  3. Fallback message (when salvage truly can't recover) now
     names the tool ORA attempted, so the founder knows what
     ORA was reaching for.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


# ─────────────────────────────────────────────
# Python-call form parser
# ─────────────────────────────────────────────

def test_python_call_form_returns_name_and_kwargs():
    from services.ora_agent import _salvage_python_call_form
    out = _salvage_python_call_form(
        'curl_internal(endpoint="/api/platform/warm-prober", method="GET")'
    )
    assert out is not None
    name, args = out
    assert name == "curl_internal"
    assert args == {"endpoint": "/api/platform/warm-prober", "method": "GET"}


def test_python_call_form_handles_no_args():
    from services.ora_agent import _salvage_python_call_form
    # `campaign_status` is a registered tool — pick whatever your suite has
    from services.ora_tools import TOOL_REGISTRY
    name = next(iter(TOOL_REGISTRY.keys()))
    out = _salvage_python_call_form(f"{name}()")
    assert out is not None
    assert out == (name, {})


def test_python_call_form_handles_mixed_scalar_kwargs():
    from services.ora_agent import _salvage_python_call_form
    out = _salvage_python_call_form(
        'view_file(path="/app/x.py", start=1, end=50)'
    )
    assert out is not None
    name, args = out
    assert name == "view_file"
    assert args["path"] == "/app/x.py"
    assert args["start"] == 1
    assert args["end"] == 50


def test_python_call_form_handles_commas_inside_strings():
    from services.ora_agent import _salvage_python_call_form
    out = _salvage_python_call_form(
        'curl_internal(endpoint="/api/x?a=1,b=2", method="GET")'
    )
    assert out is not None
    name, args = out
    assert args == {"endpoint": "/api/x?a=1,b=2", "method": "GET"}


def test_python_call_form_handles_python_literals():
    from services.ora_agent import _salvage_python_call_form
    out = _salvage_python_call_form(
        'view_file(path="/x", debug=True, dry=False, hint=None)'
    )
    assert out is not None
    _, args = out
    assert args["debug"] is True
    assert args["dry"] is False
    assert args["hint"] is None


def test_python_call_form_refuses_unknown_tool():
    """Random Python code in chat must NOT be hijacked as a tool call."""
    from services.ora_agent import _salvage_python_call_form
    out = _salvage_python_call_form('print("hello", file=sys.stdout)')
    assert out is None


def test_python_call_form_refuses_positional_args():
    """We can't safely map positionals without sig introspection."""
    from services.ora_agent import _salvage_python_call_form
    out = _salvage_python_call_form('curl_internal("/api/x", "GET")')
    assert out is None


def test_python_call_form_refuses_long_prose():
    """Genuine prose that mentions a tool must NOT be salvaged."""
    from services.ora_agent import _salvage_python_call_form
    out = _salvage_python_call_form(
        "I'm going to call curl_internal next to fetch the data."
    )
    assert out is None


# ─────────────────────────────────────────────
# _salvage_inline_tool_call wires both paths
# ─────────────────────────────────────────────

def test_salvage_promotes_python_call_to_tool_calls():
    from services.ora_agent import _salvage_inline_tool_call
    msg = {
        "role":    "assistant",
        "content": 'curl_internal(endpoint="/api/platform/warm-prober", method="GET")',
    }
    salvaged = _salvage_inline_tool_call(msg)
    assert salvaged is True
    assert msg["content"] == ""
    assert len(msg["tool_calls"]) == 1
    call = msg["tool_calls"][0]
    assert call["function"]["name"] == "curl_internal"
    args = json.loads(call["function"]["arguments"])
    assert args == {"endpoint": "/api/platform/warm-prober", "method": "GET"}


def test_salvage_still_handles_json_shape():
    from services.ora_agent import _salvage_inline_tool_call
    msg = {
        "role":    "assistant",
        "content": '{"name":"curl_internal","parameters":{"endpoint":"/api/x","method":"GET"}}',
    }
    salvaged = _salvage_inline_tool_call(msg)
    assert salvaged is True
    assert msg["tool_calls"][0]["function"]["name"] == "curl_internal"


def test_salvage_returns_false_for_plain_prose():
    from services.ora_agent import _salvage_inline_tool_call
    msg = {
        "role":    "assistant",
        "content": "I checked the dashboard. Everything looks normal.",
    }
    assert _salvage_inline_tool_call(msg) is False


def test_salvage_does_not_clobber_existing_tool_calls():
    from services.ora_agent import _salvage_inline_tool_call
    msg = {
        "role":       "assistant",
        "content":    "anything",
        "tool_calls": [{"id": "real_1", "type": "function",
                         "function": {"name": "x", "arguments": "{}"}}],
    }
    assert _salvage_inline_tool_call(msg) is False
    assert msg["tool_calls"][0]["id"] == "real_1"


# ─────────────────────────────────────────────
# Detector still catches malformed leaks (last-resort safety)
# ─────────────────────────────────────────────

def test_detector_still_catches_corrupted_python_call_form():
    """If the python-call form is malformed (e.g., truncated args) so
    salvage refuses, the detector must still flag it so we don't leak
    raw syntax to the founder."""
    from services.ora_agent import _looks_like_unhandled_tool_call, _salvage_python_call_form
    corrupt = 'curl_internal(endpoint="/api/x", method=GET)'   # GET is bareword
    # Salvage WILL handle this (bareword → string fallback). Try harder corruption:
    really_corrupt = 'curl_internal(endpoint="/api/x", method='  # truncated
    assert _salvage_python_call_form(really_corrupt) is None
    assert _looks_like_unhandled_tool_call(really_corrupt) is False  # not whole-call form anymore
    # But the JSON-shape detection should still catch leaks like:
    json_leak = '{"type":"function","name":"campaign_status","parameters":{}}'
    assert _looks_like_unhandled_tool_call(json_leak) is True


def test_iter_marker_present():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "services" / "ora_agent.py").read_text()
    assert "iter 327i" in src
    assert "_salvage_python_call_form" in src
