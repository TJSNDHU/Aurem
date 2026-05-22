"""
iter 326uu — ORA chat UI overhaul (10-gap parity with Emergent E1)
===================================================================

Backend-side regression tests for the structural changes in
OraChat.jsx + OraChatViews.jsx. Renderer logic itself is pure JS and
tested at the source-text level here (verify component contracts,
testids, key behaviours) since the project has no JS test harness yet.

10 gaps closed:
  1. Approval→error opacity              → ErrorContext (with hint)
  2. No live preview pane                → PreviewPane (right column)
  3. No inline file diffs                → DiffView (red/green lines)
  4. Test results buried                 → TestResultBlock (X passing header)
  5. Errors with no context              → ErrorContext + inferErrorHint
  6. No step tracker                     → StepTracker
  7. Approval card state confusion       → already fixed in iter 326rr
  8. No upfront plan preview             → PlanPreview + extractPlanSteps
  9. Tool output silently truncated      → ExpandableOutput (show more)
  10. No clickable file links            → FileLink
"""
from __future__ import annotations

from pathlib import Path

FRONTEND = Path("/app/frontend/src/platform/admin")
VIEWS = FRONTEND / "OraChatViews.jsx"
CHAT = FRONTEND / "OraChat.jsx"


# ─────────────────────────────────────────────
# File / wire-up presence
# ─────────────────────────────────────────────

def test_views_file_exists():
    assert VIEWS.is_file()
    src = VIEWS.read_text()
    assert len(src) > 3000
    assert "iter 326uu" in src


def test_chat_imports_from_views():
    src = CHAT.read_text()
    assert 'from "./OraChatViews"' in src
    for sym in ("SmartToolResult", "PreviewPane", "StepTracker",
                 "PlanPreview", "ErrorContext", "extractPlanSteps"):
        assert sym in src, f"OraChat must import {sym}"


# ─────────────────────────────────────────────
# Gap 1 — ErrorContext component exists
# ─────────────────────────────────────────────

def test_error_context_exports_and_has_testid():
    src = VIEWS.read_text()
    assert "export function ErrorContext(" in src
    assert 'data-testid="error-context"' in src
    assert 'data-testid="error-hint"' in src


def test_infer_error_hint_covers_all_main_cases():
    src = VIEWS.read_text()
    # Each line below is a real backend error string the LLM/tools can produce.
    must_match = [
        "not found, already processed, or expired",
        "path not allowed",
        "bad args for",
        "unknown tool",
        "no valid roles after filter",
        "timeout",
        "http 5",
        "rate limit",
        "dissent",
        "creds_missing",
    ]
    for needle in must_match:
        assert needle in src.lower(), f"inferErrorHint missing: {needle}"


# ─────────────────────────────────────────────
# Gap 2 — PreviewPane right column
# ─────────────────────────────────────────────

def test_preview_pane_present_in_chat_layout():
    src = CHAT.read_text()
    assert "<PreviewPane" in src
    assert 'data-testid="ora-preview-column"' in src
    # Empty state must also have testid (so e2e can detect it)
    views = VIEWS.read_text()
    assert 'data-testid="preview-pane-empty"' in views
    assert 'data-testid="preview-pane"' in views


# ─────────────────────────────────────────────
# Gap 3 — DiffView for safe_edit results
# ─────────────────────────────────────────────

def test_diff_view_renders_red_and_green_lines():
    src = VIEWS.read_text()
    assert "export function DiffView(" in src
    assert 'data-testid="diff-view"' in src
    assert 'data-testid={`diff-line-${ln.kind}`}' in src
    # Helper exposed for testing
    assert "export function buildDiffLines(" in src


def test_classify_result_routes_safe_edit_with_find_to_diff():
    """classifyResult inspects the result shape and routes to DiffView."""
    src = VIEWS.read_text()
    assert "export function classifyResult(" in src
    # safe_edit + find_string|replace_string|preview_diff → "diff"
    assert "find_string" in src and "replace_string" in src
    assert 'return "diff"' in src


# ─────────────────────────────────────────────
# Gap 4 — TestResultBlock + pytest summary parser
# ─────────────────────────────────────────────

def test_test_result_block_has_collapsible_header():
    src = VIEWS.read_text()
    assert "export function TestResultBlock(" in src
    assert 'data-testid="test-result-block"' in src
    assert 'data-testid="test-result-header"' in src
    # Uses ExpandableOutput for the body (collapsible)
    assert "<ExpandableOutput" in src


def test_parse_pytest_summary_pulls_counts():
    """parsePytestSummary is a pure helper — verify it's defined."""
    src = VIEWS.read_text()
    assert "export function parsePytestSummary(" in src
    # Regex looks for "X passed / Y failed / Z skipped in T s"
    assert "passed" in src and "failed" in src and "skipped" in src


# ─────────────────────────────────────────────
# Gap 5 — Errors carry retry affordance
# ─────────────────────────────────────────────

def test_error_context_has_retry_button():
    src = VIEWS.read_text()
    assert 'data-testid="error-retry-btn"' in src
    assert "Ask ORA to retry" in src


# ─────────────────────────────────────────────
# Gap 6 — StepTracker progress UI
# ─────────────────────────────────────────────

def test_step_tracker_renders_in_chat():
    src = CHAT.read_text()
    assert "<StepTracker" in src
    views = VIEWS.read_text()
    assert "export function StepTracker(" in views
    assert 'data-testid="step-tracker"' in views
    # Each step bar carries its own testid
    assert 'data-testid={`step-bar-${i}`}' in views


# ─────────────────────────────────────────────
# Gap 7 — Approval card state already fixed (iter 326rr).
# Sanity: the fix is still in place.
# ─────────────────────────────────────────────

def test_approval_card_clears_pending_after_decide():
    src = CHAT.read_text()
    # Count: setPending(null) called BOTH in success and catch paths
    # of decide(). iter 326rr fix.
    decide_start = src.index("const decide = async (approved")
    decide_block = src[decide_start: decide_start + 3500]
    assert decide_block.count("setPending(null)") >= 2


# ─────────────────────────────────────────────
# Gap 8 — PlanPreview + extractPlanSteps
# ─────────────────────────────────────────────

def test_plan_preview_wired_into_chat():
    src = CHAT.read_text()
    assert "<PlanPreview" in src
    assert "planSteps" in src   # derived state
    assert "extractPlanSteps" in src


def test_extract_plan_steps_recognises_numbered_and_bulleted():
    """Sanity — the parser supports both numbered (1.) and bulleted (-) lists."""
    src = VIEWS.read_text()
    assert "export function extractPlanSteps(" in src
    # Regex covers 1. / 1) / - / * / •
    assert "(?:\\d+[.)]|[-*•])" in src


# ─────────────────────────────────────────────
# Gap 9 — ExpandableOutput
# ─────────────────────────────────────────────

def test_expandable_output_is_used_and_has_toggle():
    src = VIEWS.read_text()
    assert "export function ExpandableOutput(" in src
    assert 'data-testid="expand-toggle"' in src
    assert "Show less" in src
    assert "Show all" in src


# ─────────────────────────────────────────────
# Gap 10 — FileLink clickable
# ─────────────────────────────────────────────

def test_file_link_component_present():
    src = VIEWS.read_text()
    assert "export function FileLink(" in src
    assert 'data-testid="file-link"' in src
    # Falls back to clipboard copy if no onClick provided
    assert "clipboard.writeText(path)" in src


# ─────────────────────────────────────────────
# Smart dispatcher coverage
# ─────────────────────────────────────────────

def test_smart_tool_result_handles_all_seven_kinds():
    src = VIEWS.read_text()
    # Each classification branch must render a component
    for kind in ("diff", "test_output", "shell_output", "file_content",
                 "lint", "council", "error", "edit_summary", "generic"):
        assert f'kind === "{kind}"' in src, f"SmartToolResult missing branch: {kind}"


def test_smart_tool_result_replaces_dumb_toolbadge_for_results():
    """Old ToolBadge JSON-dump path for tool_result rows is replaced."""
    src = CHAT.read_text()
    # Inside the Message() component, the tool_result branch now uses
    # SmartToolResult and NOT ToolBadge. Slice precisely between the
    # tool_result if-marker and the following decision if-marker.
    msg_fn_idx = src.index("function Message(")
    after_fn = src[msg_fn_idx:]
    start = after_fn.index('m.role === "tool_result"')
    end   = after_fn.index('m.role === "decision"', start)
    branch = after_fn[start:end]
    assert "<SmartToolResult" in branch, "tool_result must render via SmartToolResult"
    assert "<ToolBadge" not in branch, "tool_result must not fall back to <ToolBadge>"


# ─────────────────────────────────────────────
# History refresh hook
# ─────────────────────────────────────────────

def test_refresh_history_pulls_tool_results_after_turn():
    src = CHAT.read_text()
    assert "const refreshHistory" in src
    # Called from applyTurnResult on all branches
    assert src.count("refreshHistory()") >= 3


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_326uu_marker_present():
    assert "326uu" in VIEWS.read_text()
    # Chat doesn't strictly need the marker but planSteps + latestToolResult tags it
    assert "iter 326uu" in CHAT.read_text()
