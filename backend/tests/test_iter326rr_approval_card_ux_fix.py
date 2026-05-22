"""
iter 326rr — Approval-card UX bug fix
=====================================

Symptom (from founder screenshot): user clicked APPROVE on an ORA
safe_edit proposal but the row had already expired in the 30-min
window between propose-and-click. Backend returned ok:False with
"action not found, already processed, or expired", and the frontend:
  - kept the dead approval card on screen
  - kept the "decide first" lockout on the chat input
  - showed the red error banner ON TOP of the unusable card
  - had ALREADY echoed "✓ Approved" into history pre-emptively
    (before the API call returned), so the user saw a false success
    line for a request that failed

Backend fix:
  1. EXPIRY_MINUTES now defaults to 60 (was 30), env-overridable via
     ORA_APPROVAL_EXPIRY_MIN. Halves the chance of mid-discussion
     expiry.
  2. All three failure paths in `resume_after_decision` now return a
     structured `error_code` field:
       - "expired_or_missing"  (row gone / past expires_at)
       - "session_mismatch"
       - "not_authorized"
     so the UI can render distinct, friendlier messaging without
     parsing English strings.

Frontend fix (OraChat.jsx::decide()):
  1. Echo decision into history AFTER the API result, not before.
     Verb is "✓ Approved" / "✗ Rejected" only on ok=True; on failure
     it shows "⚠️ Approval failed" so the founder is not misled.
  2. Always `setPending(null)` after the API returns — pass or fail.
     The card is dead either way; the user cannot re-click it.
  3. Network error path also clears `pending`.
  4. Friendlier wording for the expired case ("Yeh approval expire ho
     gayi — ORA ko dobara bolo, fresh action banegi.") replaces the
     raw backend string.
"""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
FRONTEND = Path("/app/frontend/src/platform/admin/OraChat.jsx")


# ─────────────────────────────────────────────
# Backend — structured error_code on failure
# ─────────────────────────────────────────────

def test_expiry_minutes_now_60_min_default():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    assert 'ORA_APPROVAL_EXPIRY_MIN' in src
    # default fallback bumped to 60
    assert 'ORA_APPROVAL_EXPIRY_MIN", "60"' in src


def test_resume_after_decision_returns_error_code_on_missing_row():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    # The expired/missing branch must include error_code
    assert '"error_code": "expired_or_missing"' in src
    # Session-mismatch branch
    assert '"error_code": "session_mismatch"' in src
    # Auth-failure branch
    assert '"error_code": "not_authorized"' in src


def test_error_code_lives_in_correct_failure_branches():
    """Each error_code is in the SAME return statement as its error
    message (not just both present in the file by accident)."""
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    # Pair 1 — expired_or_missing
    idx = src.index('"error_code": "expired_or_missing"')
    nearby = src[max(0, idx - 400): idx + 200]
    assert "action not found, already processed, or expired" in nearby
    # Pair 2 — session_mismatch
    idx = src.index('"error_code": "session_mismatch"')
    nearby = src[max(0, idx - 200): idx + 200]
    assert '"error": "session mismatch"' in nearby
    # Pair 3 — not_authorized
    idx = src.index('"error_code": "not_authorized"')
    nearby = src[max(0, idx - 250): idx + 200]
    assert "not authorized to approve" in nearby


# ─────────────────────────────────────────────
# Frontend — decide() always clears pending
# ─────────────────────────────────────────────

def test_frontend_decide_clears_pending_after_api_returns():
    src = FRONTEND.read_text()
    # Locate the decide function body
    idx = src.index("const decide = async (approved")
    decide_block = src[idx: idx + 3000]
    # Must call setPending(null) after the fetch resolves (success
    # AND failure). Two places: post-result + catch.
    assert decide_block.count("setPending(null)") >= 2, \
        "decide() must clear pending on BOTH the result path and the catch"


def test_frontend_decide_no_premature_echo_to_history():
    """The pre-API history.push of '✓ Approved' is the bug. Verify the
    push now happens AFTER the result is known (after the fetch await)."""
    src = FRONTEND.read_text()
    idx = src.index("const decide = async (approved")
    decide_block = src[idx: idx + 3000]
    # The "✓ Approved" template MUST appear AFTER the `await fetch(`
    push_idx  = decide_block.index('"✓ Approved"')
    fetch_idx = decide_block.index("await fetch(")
    assert push_idx > fetch_idx, \
        "decide() still pre-echoes ✓ Approved before the fetch result"


def test_frontend_decide_shows_failure_verb_on_ok_false():
    src = FRONTEND.read_text()
    idx = src.index("const decide = async (approved")
    decide_block = src[idx: idx + 3000]
    # Failure-aware verb so a failed approval doesn't show as approved
    assert "Approval failed" in decide_block
    assert "Reject failed"   in decide_block


def test_frontend_decide_uses_friendlier_expired_message():
    src = FRONTEND.read_text()
    # Hindi-EN mixed copy per founder's directive
    assert "approval expire ho gayi" in src
    assert "ORA ko dobara bolo" in src


def test_iter_326rr_marker_present():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    assert "326rr" in src
    src2 = FRONTEND.read_text()
    assert "326rr" in src2
