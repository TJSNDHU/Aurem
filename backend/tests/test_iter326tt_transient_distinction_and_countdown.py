"""
iter 326tt — Transient failure distinction + live approval countdown
====================================================================

Two halt gaps closed (the ones left over from iter 326ss):

Gap #4 — transient vs deterministic failure distinction
-------------------------------------------------------
Old behaviour: any 2 consecutive failures of the same tool → halt
with `halted_for: fail_ceiling`. Network blips + 5xx hiccups +
upstream rate limits would all trigger the same halt as genuine LLM
hallucinations (bad args, unknown tool).

Fix: two buckets.
  - `fail_counts`      — deterministic errors (LLM's fault). 2 strikes.
  - `transient_counts` — env errors (network/5xx/rate-limit). 5 strikes.
A successful call clears BOTH buckets. Transient failures still emit
a recovery directive so the LLM can choose to back off or retry.

Live approval countdown (UX bug found in screenshot)
----------------------------------------------------
Old behaviour: approval card showed a static "Expires in 30m" label
that never ticked. Founder couldn't see when an action was about to
die mid-conversation.

Fix:
  - Backend now includes `expires_at` (ISO timestamp) in the
    action_required payload.
  - Frontend renders a live ExpiryCountdown that ticks every second,
    shows mm:ss, colour-shifts gold → amber (≤5min) → red (≤1min),
    and displays "Expired" cleanly at zero.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent
FRONTEND = Path("/app/frontend/src/platform/admin/OraChat.jsx")


# ─────────────────────────────────────────────
# Gap #4 — transient detector
# ─────────────────────────────────────────────

def test_is_transient_failure_catches_network_timeouts():
    from services.ora_agent import _is_transient_failure
    for err in (
        "timeout while connecting to https://api.openai.com",
        "Connection refused",
        "ServerSelectionTimeoutError: no suitable servers",
        "HTTP 502: bad gateway",
        "HTTP 503 service unavailable",
        "HTTP 504 gateway timeout",
        "HTTP 500 internal server error",
        "HTTP 429 too many requests",
        "rate limit exceeded",
        "SSL handshake failed",
        "EOF occurred in violation of protocol",
        "DNS resolution failed",
        "name or service not known",
        "Remote end closed connection",
    ):
        assert _is_transient_failure({"ok": False, "error": err}) is True, \
            f"should classify as transient: {err!r}"


def test_is_transient_failure_rejects_deterministic_errors():
    from services.ora_agent import _is_transient_failure
    for err in (
        "bad args for view_file: missing 'path'",
        "path not allowed: /etc/passwd",
        "unknown tool: hallucinated_xyz",
        "invalid scan_type: foo",
        "no valid roles after filter",
        "rationale required (>=10 chars)",
        "action not found, already processed, or expired",
        "session mismatch",
    ):
        assert _is_transient_failure({"ok": False, "error": err}) is False, \
            f"should NOT classify as transient: {err!r}"


def test_is_transient_failure_handles_empty_or_malformed_input():
    from services.ora_agent import _is_transient_failure
    assert _is_transient_failure(None) is False
    assert _is_transient_failure({}) is False
    assert _is_transient_failure({"ok": True}) is False
    assert _is_transient_failure({"ok": False}) is False
    assert _is_transient_failure({"ok": False, "error": ""}) is False
    assert _is_transient_failure({"ok": False, "error": None}) is False
    # Non-dict input
    assert _is_transient_failure("string") is False  # type: ignore[arg-type]
    assert _is_transient_failure([]) is False        # type: ignore[arg-type]


# ─────────────────────────────────────────────
# Gap #4 — wiring inside the run loop
# ─────────────────────────────────────────────

def test_transient_counts_bucket_exists_and_is_used():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    # Bucket initialised
    assert "transient_counts: dict" in src
    # Bucket incremented on transient hits
    assert "transient_counts[call[\"name\"]] = (" in src
    # Both buckets reset on success
    assert "transient_counts.pop(call[\"name\"], None)" in src


def test_separate_halt_ceiling_for_transients():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    # 5-strike transient ceiling
    assert 'transient_counts.get(call["name"], 0) >= 5' in src
    assert '"halted_for": "transient_ceiling"' in src
    # Deterministic ceiling unchanged
    assert 'fail_counts.get(call["name"], 0) >= 2' in src
    assert '"halted_for": "fail_ceiling"' in src


def test_recovery_directive_uses_combined_strike_count():
    """The recovery directive should reflect the TOTAL strikes
    (deterministic + transient) so the LLM sees the full pressure."""
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    # The directive call now passes the sum, not just fail_counts[...]
    assert "fail_counts.get(call[\"name\"], 0)" in src
    assert "+ transient_counts.get(call[\"name\"], 0)" in src


# ─────────────────────────────────────────────
# Live countdown — backend surface
# ─────────────────────────────────────────────

def test_action_required_payload_includes_expires_at_iso():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    # The Tier 2/3 return block must include expires_at
    assert '"expires_at":         _expires_at_iso' in src
    # It uses _now() + EXPIRY_MINUTES (matches the row in Mongo)
    assert "_iso(_now() + timedelta(minutes=EXPIRY_MINUTES))" in src


# ─────────────────────────────────────────────
# Live countdown — frontend renders ExpiryCountdown
# ─────────────────────────────────────────────

def test_frontend_uses_live_countdown_component():
    src = FRONTEND.read_text()
    # New component defined
    assert "function ExpiryCountdown(" in src
    # Used in the approval card footer
    assert "<ExpiryCountdown expiresAt={action.expires_at}" in src
    # Hard-coded "30m" literal is GONE (the bug we're fixing)
    assert 'Expires in {action.expires_in_minutes || 30}m' not in src


def test_countdown_has_testid_for_e2e_assertions():
    src = FRONTEND.read_text()
    assert 'data-testid="approval-expiry-countdown"' in src


def test_countdown_falls_back_when_backend_doesnt_send_expires_at():
    """Old sessions without expires_at still render — never blank."""
    src = FRONTEND.read_text()
    # Fallback branch checks !expiresAt and uses fallbackMin
    assert "if (!expiresAt)" in src
    assert "fallbackMin" in src


def test_countdown_uses_real_setInterval_tick():
    src = FRONTEND.read_text()
    # Should set up a 1-second tick + clean up on unmount
    idx = src.index("function ExpiryCountdown(")
    block = src[idx: idx + 1500]
    assert "setInterval" in block
    assert "1000" in block            # tick interval
    assert "clearInterval" in block   # cleanup
    # Uses tabular-nums to avoid layout shift on every tick
    assert "tabular-nums" in block


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_326tt_marker_present():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    assert "326tt" in src
    src2 = FRONTEND.read_text()
    assert "326tt" in src2
