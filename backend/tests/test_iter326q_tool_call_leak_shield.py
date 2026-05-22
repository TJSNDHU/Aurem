"""
test_iter326q_tool_call_leak_shield.py — Regression for iter 326q.
══════════════════════════════════════════════════════════════════════════════
THE BUG THE FOUNDER REPORTED (verbatim chat transcript):

  Founder: "campaign report?"
  ORA:     `{"type": "function", "name": "campaign_status", "parameters": {}}`
  Founder: "reply human language"
  ORA:     (fabricated numbers — "Eligible: 8, Sent: 5, Streak: 0"
           when the real numbers were 12 / 0 / 1)
  Founder: "you hallucinating"
  ORA:     `{"type": "function", "name": "campaign_status", "parameters": {}}`

THREE BUGS COMBINED INTO ONE FAILURE:

  1. LEAK   — Some providers (Claude text fallback, Gemini, mid-loop NVIDIA)
              emit tool calls as plain JSON inside `content` instead of
              populating the OpenAI `tool_calls` array. The old salvage
              only ran inside `_call_ollama` so non-Ollama leaks went
              straight to chat.
  2. STRICT — Even the Ollama-only salvage demanded
              `content.startswith('{') and endswith('}')` — a single
              leading word ("Sure, ") or a ```json fence broke it.
  3. FAKE   — When the tool wasn't actually called, the model had no
              real data to anchor on AND no instruction not to invent
              one, so it fabricated plausible-looking numbers on the
              NEXT turn. This is the worst category of LLM failure.

THE iter 326q FIX (one file: services/ora_agent.py):

  A) Module-level `_extract_candidate_json(text)` — tolerates
     ```json fences```, leading prose ("here you go: { ... }"),
     trailing commentary, AND plain JSON-only content.
  B) Module-level `_salvage_inline_tool_call(msg)` — promotes any
     leaked JSON into a proper `tool_calls` array. Recognises 4
     call-shape conventions including the OpenAI-schema echo
     `{"type":"function","name":...,"parameters":...}` shape the
     founder actually saw.
  C) Final-reply safety net — if salvage already failed AND the
     content still looks like a tool-call leak, the loop REPLACES
     it with an honest "I couldn't fetch — retry" reply instead of
     delivering either the raw JSON or fabricated numbers.
  D) The shared salvage now runs in the agent main loop, after EVERY
     provider response — not just Ollama.

Run:  cd /app/backend && python3 -m pytest tests/test_iter326q_tool_call_leak_shield.py -v
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# A) _extract_candidate_json — tolerates messy wrapping
# ─────────────────────────────────────────────────────────────────────────────
def test_extract_handles_plain_json_only():
    from services.ora_agent import _extract_candidate_json

    txt = '{"name": "campaign_status", "parameters": {}}'
    assert _extract_candidate_json(txt) == txt


def test_extract_handles_markdown_json_fence():
    """The model often wraps tool calls in ```json ... ``` fences,
    especially after a 'reply human language' instruction. Old
    salvage's startswith('{') check failed on these every time."""
    from services.ora_agent import _extract_candidate_json

    txt = "Sure, here you go:\n```json\n{\"name\": \"campaign_status\", \"parameters\": {}}\n```"
    extracted = _extract_candidate_json(txt)
    assert extracted is not None
    assert '"name": "campaign_status"' in extracted


def test_extract_handles_leading_prose():
    """Models sometimes prefix the JSON with a sentence. Salvage must
    still find the JSON object inside."""
    from services.ora_agent import _extract_candidate_json

    txt = 'Calling the tool now: {"name": "campaign_status", "parameters": {}}'
    extracted = _extract_candidate_json(txt)
    assert extracted is not None
    assert '"campaign_status"' in extracted


def test_extract_returns_none_on_empty_and_non_json():
    from services.ora_agent import _extract_candidate_json

    assert _extract_candidate_json("") is None
    assert _extract_candidate_json(None) is None
    assert _extract_candidate_json("just regular prose with no JSON") is None


# ─────────────────────────────────────────────────────────────────────────────
# B) _salvage_inline_tool_call — promotes the 4 leak shapes
# ─────────────────────────────────────────────────────────────────────────────
def test_salvage_promotes_openai_schema_echo_shape():
    """The EXACT leak shape the founder saw in chat. This is the
    OpenAI tool-schema being echoed back as content. Must be salvaged."""
    from services.ora_agent import _salvage_inline_tool_call

    msg = {
        "content": '{"type": "function", "name": "campaign_status", "parameters": {}}',
        "tool_calls": None,
    }
    assert _salvage_inline_tool_call(msg) is True
    assert msg["tool_calls"] is not None
    assert len(msg["tool_calls"]) == 1
    assert msg["tool_calls"][0]["function"]["name"] == "campaign_status"
    assert msg["content"] == ""  # original leak content cleared


def test_salvage_promotes_name_parameters_shape():
    from services.ora_agent import _salvage_inline_tool_call

    msg = {"content": '{"name": "view_file", "parameters": {"path": "/x.py"}}',
           "tool_calls": None}
    assert _salvage_inline_tool_call(msg) is True
    assert msg["tool_calls"][0]["function"]["name"] == "view_file"


def test_salvage_promotes_tool_args_shape():
    from services.ora_agent import _salvage_inline_tool_call

    msg = {"content": '{"tool": "grep_codebase", "args": {"q": "foo"}}',
           "tool_calls": None}
    assert _salvage_inline_tool_call(msg) is True
    assert msg["tool_calls"][0]["function"]["name"] == "grep_codebase"


def test_salvage_promotes_function_arguments_shape():
    from services.ora_agent import _salvage_inline_tool_call

    msg = {"content": '{"function": "health_check", "arguments": {}}',
           "tool_calls": None}
    assert _salvage_inline_tool_call(msg) is True
    assert msg["tool_calls"][0]["function"]["name"] == "health_check"


def test_salvage_unwraps_markdown_fence_in_content():
    from services.ora_agent import _salvage_inline_tool_call

    msg = {
        "content": "```json\n{\"name\": \"campaign_status\", \"parameters\": {}}\n```",
        "tool_calls": None,
    }
    assert _salvage_inline_tool_call(msg) is True
    assert msg["tool_calls"][0]["function"]["name"] == "campaign_status"


def test_salvage_noop_when_tool_calls_already_present():
    """If the provider gave us proper structured tool_calls, salvage
    must NOT touch anything — otherwise we double-process the call."""
    from services.ora_agent import _salvage_inline_tool_call

    real_calls = [{"id": "x", "type": "function",
                   "function": {"name": "real_call", "arguments": "{}"}}]
    msg = {"content": "irrelevant", "tool_calls": real_calls}
    assert _salvage_inline_tool_call(msg) is False
    assert msg["tool_calls"] is real_calls
    assert msg["content"] == "irrelevant"  # unchanged


def test_salvage_noop_on_plain_prose():
    """Real conversational replies must NOT be mistaken for tool calls."""
    from services.ora_agent import _salvage_inline_tool_call

    msg = {"content": "Your queue has 12 leads ready to email.",
           "tool_calls": None}
    assert _salvage_inline_tool_call(msg) is False
    # content unchanged
    assert msg["content"] == "Your queue has 12 leads ready to email."


# ─────────────────────────────────────────────────────────────────────────────
# C) _looks_like_unhandled_tool_call — final safety net
# ─────────────────────────────────────────────────────────────────────────────
def test_safety_net_detects_the_exact_leak_the_founder_saw():
    from services.ora_agent import _looks_like_unhandled_tool_call

    leaked = '{"type": "function", "name": "campaign_status", "parameters": {}}'
    assert _looks_like_unhandled_tool_call(leaked) is True


def test_safety_net_detects_compact_no_space_variant():
    from services.ora_agent import _looks_like_unhandled_tool_call

    leaked = '{"type":"function","name":"campaign_status","parameters":{}}'
    assert _looks_like_unhandled_tool_call(leaked) is True


def test_safety_net_does_not_flag_legitimate_replies():
    """If the model actually answered properly in prose, the safety
    net must NOT trip — otherwise we'd replace good replies with
    'I couldn't fetch'."""
    from services.ora_agent import _looks_like_unhandled_tool_call

    legitimate = (
        "Your auto-blast queue currently holds 12 fresh leads. The last "
        "successful batch sent 254 emails about 7 hours ago. Nothing is "
        "broken — the system is just waiting for the next scheduled tick."
    )
    assert _looks_like_unhandled_tool_call(legitimate) is False


def test_safety_net_does_not_flag_empty_or_short_strings():
    from services.ora_agent import _looks_like_unhandled_tool_call

    assert _looks_like_unhandled_tool_call("") is False
    assert _looks_like_unhandled_tool_call("ok") is False


# ─────────────────────────────────────────────────────────────────────────────
# D) Combined: real failure flow — leak that the salvage CAN fix
# ─────────────────────────────────────────────────────────────────────────────
def test_end_to_end_leak_salvaged_to_tool_call():
    """Simulate the founder's exact failure mode and verify the salvage
    converts it back into a runnable tool call."""
    from services.ora_agent import _salvage_inline_tool_call

    # This is the literal content the founder saw — the model emitted
    # the OpenAI tool schema as the assistant's content.
    msg = {
        "role": "assistant",
        "content": '{"type": "function", "name": "campaign_status", "parameters": {}}',
        "tool_calls": None,
    }
    assert _salvage_inline_tool_call(msg) is True
    # After salvage, the agent loop will see a proper tool call and run
    # campaign_status, returning real data instead of the leaked JSON.
    assert msg["tool_calls"][0]["function"]["name"] == "campaign_status"
    assert msg["content"] == ""
