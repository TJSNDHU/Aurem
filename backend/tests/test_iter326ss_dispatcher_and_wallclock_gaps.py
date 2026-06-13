"""
iter 326ss — Two more ORA halt-cause gaps closed
================================================

Gap #2 (same class as council bug iter 326qq):
  When the LLM brain passes wrong args to a tool, the dispatcher
  raised TypeError → returned a one-line "bad args for X: ..." error
  with NO hint at the correct shape. ORA's brain retried with similar
  wrong args → fail_ceiling = 2 → halt.

  Fix: the bad-args branch now also returns:
    - "args_spec"  : the canonical args spec for that tool
    - "args_passed": the keys the LLM actually sent
  so the next iteration can self-correct without burning a strike.

Gap #3:
  Wall-clock loop budget was 150s — tight for multi-step builds
  that involve council_consult calls (each peer can take 12-50s on
  OpenRouter). A 6-step build like the CASL audit-trail trivially
  blew past 150s and halted with `halted_for: wall_clock`, forcing
  the founder to send "continue".

  Fix: default bumped to 300s (still env-overridable via
  ORA_MAX_LOOP_S so power users can extend further). Halt path is
  unchanged — same clean exit, same "continue to resume" UX.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# Gap #2 — bad args now returns args_spec
# ─────────────────────────────────────────────

def test_bad_args_path_returns_args_spec_for_self_correction():
    """Drive invoke_tool with intentionally-wrong args and assert the
    response includes the canonical spec so the LLM can correct."""
    from services.ora_tools import invoke_tool, TOOL_REGISTRY
    # Pick a tool that has a non-trivial args_spec
    tool_name = "view_file"
    assert tool_name in TOOL_REGISTRY  # sanity
    # Pass a deliberately-wrong arg name
    r = asyncio.run(invoke_tool(tool_name,
                                 {"wrong_arg": "/app/backend/server.py"},
                                 actor="pytest:326ss"))
    assert r["ok"] is False
    assert "bad args for view_file" in r["error"]
    assert "args_spec" in r, "must surface args_spec on bad-args"
    assert isinstance(r["args_spec"], dict)
    assert len(r["args_spec"]) > 0
    assert "args_passed" in r
    assert r["args_passed"] == ["wrong_arg"]


def test_unknown_tool_path_still_lists_available_tools():
    """Sanity — the existing unknown-tool surface is untouched."""
    from services.ora_tools import invoke_tool
    r = asyncio.run(invoke_tool("totally_made_up_tool_xyz", {},
                                 actor="pytest:326ss"))
    assert r["ok"] is False
    assert "unknown tool" in r["error"]
    assert "available_tools" in r
    assert isinstance(r["available_tools"], list)
    assert len(r["available_tools"]) >= 20  # we have 25+ tools


def test_args_spec_returned_matches_registry_for_that_tool():
    """The returned spec is the live one from TOOL_REGISTRY, not a copy
    that could drift."""
    from services.ora_tools import invoke_tool, TOOL_REGISTRY
    r = asyncio.run(invoke_tool("council_consult",
                                 {"bogus": 1},  # missing required `question`
                                 actor="pytest:326ss"))
    assert r["ok"] is False
    canonical = TOOL_REGISTRY["council_consult"]["args_spec"]
    assert r["args_spec"] == canonical


def test_normal_tool_call_unchanged_no_args_spec_on_success():
    """Successful calls must NOT carry args_spec — it would bloat the
    history and burn LLM context budget."""
    from services.ora_tools import invoke_tool
    r = asyncio.run(invoke_tool("view_file",
                                 {"path": "/app/backend/server.py"},
                                 actor="pytest:326ss"))
    # We don't care if file exists / read succeeded — only that the
    # debug fields are absent on the happy path.
    assert "args_spec" not in r
    assert "args_passed" not in r


# ─────────────────────────────────────────────
# Gap #3 — wall-clock bumped 150 → 300
# ─────────────────────────────────────────────

def test_wall_clock_default_now_300_seconds():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    # Default fallback in the os.environ.get(...)
    assert 'ORA_MAX_LOOP_S", "300"' in src
    # Old value must be gone
    assert 'ORA_MAX_LOOP_S", "150"' not in src


def test_wall_clock_still_env_overridable(monkeypatch):
    """User can still pin it lower (e.g. for cheaper sessions) or
    higher (huge builds) via env."""
    monkeypatch.setenv("ORA_MAX_LOOP_S", "600")
    # Re-import the module to re-read env
    import importlib
    import services.ora_agent as m
    importlib.reload(m)
    assert m.MAX_LOOP_WALL_SECONDS == 600
    # Restore to default so other tests aren't affected
    monkeypatch.setenv("ORA_MAX_LOOP_S", "300")
    importlib.reload(m)
    assert m.MAX_LOOP_WALL_SECONDS == 300


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_326ss_marker_present():
    src = (BACKEND / "services" / "ora_tools.py").read_text()
    assert "326ss" in src
