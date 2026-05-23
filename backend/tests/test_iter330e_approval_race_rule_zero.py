"""
iter 330e — Approval race + Rule Zero fix
==========================================

Symptom (founder screenshot on aurem.live):
  - ORA proposed `create_file` (Tier-2, has 30 s auto-execute window).
  - Founder clicked APPROVE within seconds, but UI showed a red
    "Approval failed" banner with the message:
      "Yeh approval expire ho gayi (30 min window). ORA ko dobara
       bolo — fresh action banegi."

Two bugs combined:
  A) The Tier-2 auto-executor (runs every 5 s, fires at 30 s
     after the row is created) claimed the row by atomic
     find_one_and_update → flipped status to "auto_executing".
     The founder's subsequent click hit `decide()`, which only
     matches `status: pending`, so it missed → returned
     `expired_or_missing` even though the action ACTUALLY ran
     and completed successfully.
  B) The frontend error banner copy was Hindi/Urdu mixed —
     violates Rule Zero (plain English to the founder, always).

Fix:
  1. `resume_after_decision` now looks up the row a second time
     when the atomic gate misses, and returns one of:
       - `not_found`         (no such _id)
       - `already_executed`  (status in auto_executing/executing/done)
       - `already_failed`    (status == failed)
       - `already_rejected`  (status == rejected)
       - `expired_or_missing` (status == expired OR unknown)
     The `already_executed` case carries `soft_success: True` so the
     UI treats it as a success (the action ran via auto-execute).
  2. OraChat.jsx maps each error_code to plain English copy. No
     Hindi/Urdu anywhere. Soft-success refreshes history instead
     of showing a red error banner.
  3. Chat input placeholder rewritten in plain English.
"""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
AGENT_SRC = (BACKEND / "services" / "ora_agent.py").read_text()
FRONTEND_SRC = Path("/app/frontend/src/platform/admin/OraChat.jsx").read_text()


# ─────────────────────────────────────────────────────────
# Backend — error_code differentiation after atomic gate miss
# ─────────────────────────────────────────────────────────

def test_backend_distinguishes_already_executed_from_expired():
    """When the row exists but status moved past 'pending' via the
    Tier-2 auto-executor, the founder's click must NOT see a generic
    'expired' error — it must see a soft_success with error_code
    'already_executed'."""
    import re
    # Whitespace-tolerant — the source uses aligned colons in some
    # branches (e.g. "error_code":     "already_executed").
    assert re.search(r'"error_code"\s*:\s*"already_executed"', AGENT_SRC)
    assert re.search(r'"soft_success"\s*:\s*True', AGENT_SRC)


def test_backend_already_executed_includes_status_context():
    """The already_executed branch must check for the three live/done
    statuses (auto_executing, executing, done) so a Tier-2 row claimed
    by either the auto-executor OR a concurrent manual click is
    handled correctly."""
    import re
    m = re.search(r'"error_code"\s*:\s*"already_executed"', AGENT_SRC)
    assert m
    nearby = AGENT_SRC[max(0, m.start() - 800): m.start()]
    assert "auto_executing" in nearby
    assert "executing" in nearby
    assert "done" in nearby


def test_backend_distinguishes_already_rejected_and_failed():
    import re
    assert re.search(r'"error_code"\s*:\s*"already_rejected"', AGENT_SRC)
    assert re.search(r'"error_code"\s*:\s*"already_failed"', AGENT_SRC)


def test_backend_not_found_distinct_from_expired():
    """Truly-missing rows (never persisted, wrong id) return
    `not_found` instead of being lumped into `expired_or_missing`."""
    import re
    assert re.search(r'"error_code"\s*:\s*"not_found"', AGENT_SRC)


def test_backend_iter_330e_marker_present():
    assert "330e" in AGENT_SRC


# ─────────────────────────────────────────────────────────
# Frontend — Rule Zero (plain English) + soft-success path
# ─────────────────────────────────────────────────────────

def test_frontend_no_hindi_or_urdu_in_oracle_chat():
    """Rule Zero: the ORA cockpit chat speaks only in plain English to
    the founder. Hindi/Urdu fragments from older copy must be gone."""
    forbidden = [
        "Yeh approval expire ho gayi",
        "ORA ko dobara bolo",
        "fresh action banegi",
        "Bata kya karna hai",
        "Hindi/English mix chalega",
        "chalega",
    ]
    for needle in forbidden:
        assert needle not in FRONTEND_SRC, \
            f"Rule Zero violation: {needle!r} still in OraChat.jsx"


def test_frontend_handles_already_executed_as_soft_success():
    """When the backend reports error_code=already_executed, the UI
    must not show a red error banner. It treats it as a success and
    refreshes history."""
    assert "soft_success" in FRONTEND_SRC
    assert "already_executed" in FRONTEND_SRC or "Auto-executed" in FRONTEND_SRC


def test_frontend_friendly_messages_per_error_code():
    """Each known error_code maps to a distinct, plain English message
    in OraChat.jsx::decide()."""
    needed = [
        "Approval window closed",          # expired_or_missing / not_found
        "already rejected",                # already_rejected
        "already ran but failed",          # already_failed
        "different chat session",          # session_mismatch
        "not authorized",                  # not_authorized
    ]
    for needle in needed:
        assert needle in FRONTEND_SRC, \
            f"Missing friendly copy: {needle!r}"


def test_frontend_iter_330e_marker_present():
    assert "330e" in FRONTEND_SRC


# ─────────────────────────────────────────────────────────
# Sanity — old behaviour preserved for unchanged paths
# ─────────────────────────────────────────────────────────

def test_legacy_error_codes_still_present():
    """iter 326rr's original error_codes must still be supported."""
    assert '"error_code": "expired_or_missing"' in AGENT_SRC
    assert '"error_code": "session_mismatch"' in AGENT_SRC
    assert '"error_code": "not_authorized"' in AGENT_SRC


def test_pending_card_still_cleared_on_failure():
    """iter 326rr invariant — decide() must clear `pending` whether
    the API returned ok:true, ok:false, or threw a network error."""
    idx = FRONTEND_SRC.index("const decide = async (approved")
    decide_block = FRONTEND_SRC[idx: idx + 4000]
    assert decide_block.count("setPending(null)") >= 2
