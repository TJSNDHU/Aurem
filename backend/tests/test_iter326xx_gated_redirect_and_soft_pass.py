"""
iter 326xx — Gated-tool auto-redirect + council soft-pass
==========================================================

Two related ORA halts the founder hit on production aurem.live
(screenshots 2026-05-22 23:xx):

1. ORA called `shell_exec` for a Tier-1 check ("does .env.production
   appear in git history?"). The dispatcher returned the gated error:
     "tool 'shell_exec' is gated — call shell_exec_with_council instead"
   ORA's brain misread this as needing a "second opinion" and fired
   `council_consult` instead of just calling the wrapper. Council
   returned "0 peers" (provider hiccup). ORA looped: shell_exec fails
   → council fails → shell_exec fails again → ...

2. The `council_consult` returned ok=False whenever every peer failed
   transiently (e.g. all 3 LLM peers got a 502 in the same window).
   That ok=False then propagated up to safe_edit_with_council /
   shell_exec_with_council, which interpreted it as "council rejected"
   and refused the action — even though no actual rejection happened.

Fixes shipped this iter:

  A) `invoke_tool()` now silently AUTO-REDIRECTS gated tools to their
     `*_with_council` variants with the same args. Founder sees the
     successful result with a calm "auto-routed from shell_exec" tag
     instead of a red error followed by ORA's loop.

  B) `council_consult()` now distinguishes "all peers transiently
     unreachable" from "council rejected". When every opinion's error
     matches a transient pattern (timeout / 5xx / rate-limit / etc.)
     it returns ok=True with verdict="soft_pass" + an explanatory note.
     The wrapping `*_with_council` tools still apply their OWN policy
     gates (path allow-list, dissent keyword scan) so safety isn't
     weakened — only transient outage cascading is stopped.

  C) `SYSTEM_PROMPT` updated so ORA's brain stops calling
     `council_consult` defensively before shell_exec / safe_edit —
     the wrapper fires council automatically.

  D) UI: when a tool result carries `_redirected_from`, the chat
     shows "tool · auto-routed from shell_exec" instead of any
     red error banner.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent
TOOLS = BACKEND / "services" / "ora_tools.py"
AGENT = BACKEND / "services" / "ora_agent.py"
VIEWS = Path("/app/frontend/src/platform/admin/OraChatViews.jsx")


# ─────────────────────────────────────────────
# Fix A — gated-tool auto-redirect
# ─────────────────────────────────────────────

def test_invoke_tool_shell_exec_auto_redirects():
    """invoke_tool('shell_exec', ...) silently calls shell_exec_with_council."""
    from services.ora_tools import invoke_tool, TOOL_REGISTRY
    # Stub out the wrapper so the test doesn't hit real council/LLM.
    fake_called = {}
    async def fake_wrapper(**kw):
        fake_called.update(kw)
        return {"ok": True, "stdout": "ok", "stderr": ""}
    with patch.dict(TOOL_REGISTRY,
                     {"shell_exec_with_council": {
                         "fn": fake_wrapper,
                         "args_spec": {},
                         "description": "test"}},
                     clear=False):
        r = asyncio.run(invoke_tool("shell_exec",
                                      {"cmd": "git log -1"},
                                      actor="pytest:326xx"))
    assert r["ok"] is True
    assert r["tool"] == "shell_exec_with_council"
    assert r["_redirected_from"] == "shell_exec"
    assert fake_called == {"cmd": "git log -1"}


def test_invoke_tool_safe_edit_auto_redirects():
    from services.ora_tools import invoke_tool, TOOL_REGISTRY
    fake_called = {}
    async def fake_wrapper(**kw):
        fake_called.update(kw)
        return {"ok": True, "path": kw.get("path"), "occurrences": 1}
    with patch.dict(TOOL_REGISTRY,
                     {"safe_edit_with_council": {
                         "fn": fake_wrapper,
                         "args_spec": {},
                         "description": "test"}},
                     clear=False):
        r = asyncio.run(invoke_tool("safe_edit",
                                      {"path": "/tmp/x.py",
                                       "find": "a", "replace": "b"},
                                      actor="pytest:326xx"))
    assert r["ok"] is True
    assert r["_redirected_from"] == "safe_edit"
    assert r["tool"] == "safe_edit_with_council"
    assert fake_called["path"] == "/tmp/x.py"


def test_redirect_preserves_elapsed_and_ts():
    """The redirect path still attaches tool/elapsed_ms/ts so the UI
    renders the result chrome correctly."""
    from services.ora_tools import invoke_tool, TOOL_REGISTRY
    async def fake_wrapper(**kw):
        return {"ok": True}
    with patch.dict(TOOL_REGISTRY,
                     {"shell_exec_with_council": {
                         "fn": fake_wrapper, "args_spec": {}, "description": ""}},
                     clear=False):
        r = asyncio.run(invoke_tool("shell_exec", {"cmd": "echo"},
                                      actor="pytest:326xx"))
    assert "elapsed_ms" in r
    assert "ts" in r
    assert r["tool"] == "shell_exec_with_council"


# ─────────────────────────────────────────────
# Fix B — council soft-pass on transient outage
# ─────────────────────────────────────────────

def test_council_soft_passes_when_all_peers_transient_fail():
    from services import ora_tools as ot
    async def fake_peer_review(role, question, context=""):
        return {"ok": False, "role": role,
                "error": "HTTP 502 bad gateway"}
    with patch.object(ot, "peer_review", side_effect=fake_peer_review):
        r = asyncio.run(ot.council_consult("ship CASL field",
                                             roles=["security", "backend", "qa"]))
    assert r["ok"] is True
    assert r["verdict"] == "soft_pass"
    assert "0/3 peers reachable" in r["consensus"]
    assert "transiently unreachable" in r["note"]


def test_council_still_returns_ok_false_on_real_rejection():
    """If peers reply but at least one disagrees (real opinion), the
    result must NOT collapse to soft_pass."""
    from services import ora_tools as ot
    async def fake_peer_review(role, question, context=""):
        if role == "security":
            return {"ok": True, "role": role,
                    "opinion": "REJECT — CASL needs explicit consent"}
        return {"ok": True, "role": role, "opinion": "ok"}
    with patch.object(ot, "peer_review", side_effect=fake_peer_review):
        r = asyncio.run(ot.council_consult("foo", roles=["security", "backend"]))
    assert r["ok"] is True
    assert r.get("verdict") != "soft_pass"
    assert "2/2 peers responded" in r["consensus"]


def test_looks_transient_classifier():
    from services.ora_tools import _looks_transient
    for transient in ("HTTP 502", "timeout", "Connection refused",
                       "Rate limit hit", "SSL handshake failed",
                       "504 gateway timeout", "DNS resolution failed",
                       "no response from upstream"):
        assert _looks_transient(transient) is True, transient
    for deterministic in ("invalid role", "REJECT - missing CASL",
                           "args not understood", ""):
        assert _looks_transient(deterministic) is False, deterministic


def test_council_does_not_soft_pass_when_errors_are_deterministic():
    """If peers failed with deterministic errors (not transient), keep
    ok=False so ORA actually addresses the root cause."""
    from services import ora_tools as ot
    async def fake_peer_review(role, question, context=""):
        return {"ok": False, "role": role,
                "error": "invalid input — context too long"}
    with patch.object(ot, "peer_review", side_effect=fake_peer_review):
        r = asyncio.run(ot.council_consult("foo", roles=["security", "qa"]))
    # No soft-pass — these aren't transient
    assert r["ok"] is False
    assert r.get("verdict") != "soft_pass"


# ─────────────────────────────────────────────
# Fix C — system prompt teaches the new behaviour
# ─────────────────────────────────────────────

def test_system_prompt_documents_gated_auto_redirect():
    src = AGENT.read_text()
    # Find SYSTEM_PROMPT and assert the new section is present
    idx = src.index('SYSTEM_PROMPT = """')
    block = src[idx: idx + 8000]
    assert "iter 326xx" in block
    assert "auto-redirect" in block.lower()
    assert "shell_exec_with_council" in block
    assert "safe_edit_with_council" in block
    # And tells ORA NOT to fan-out to council_consult before these
    assert "DO NOT call council_consult yourself" in block


def test_shell_exec_moved_to_tier2_in_prompt():
    """shell_exec is gated (Tier 2 with auto-execute), not Tier 1."""
    src = AGENT.read_text()
    idx = src.index('SYSTEM_PROMPT = """')
    block = src[idx: idx + 8000]
    # Tier 1 list must not include shell_exec
    t1_idx = block.index("TIER 1 (auto)")
    t1_end = block.index("TIER 2 (approve)")
    t1_block = block[t1_idx:t1_end]
    assert "shell_exec" not in t1_block, "shell_exec must not be listed under Tier 1"
    # Tier 2 list must include it
    t2_idx = block.index("TIER 2 (approve)")
    t2_end = block.index("TIER 3 (high risk)")
    t2_block = block[t2_idx:t2_end]
    assert "shell_exec" in t2_block


# ─────────────────────────────────────────────
# Fix D — UI surfaces redirect calmly
# ─────────────────────────────────────────────

def test_ui_shows_redirect_note_not_error():
    src = VIEWS.read_text()
    assert "_redirected_from" in src
    assert 'data-testid="redirect-note"' in src
    assert "auto-routed from" in src


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_326xx_marker_present():
    assert "326xx" in TOOLS.read_text()
    assert "326xx" in AGENT.read_text()
    assert "326xx" in VIEWS.read_text()
