"""
test_iter326ll_auth_interceptor_role_isolation.py — iter 326ll regression.
══════════════════════════════════════════════════════════════════════════════
Production bug (2026-05-22): founder reported "login and logout not working
in production". Repro path:

  1. Admin logs in → admin token saved to `aurem_admin_token` (and the
     legacy `auth_token` mirror slot).
  2. Customer (same browser tab / window) is also logged in →
     `aurem_customer_token` is set.
  3. A background poller fires an admin-scoped API call whose access
     token has expired. The axios interceptor in `lib/api.js` attempts
     a silent refresh; the refresh endpoint returns 401.
  4. The OLD `clearTokens()` helper iterated over ALL token slots
     (admin + customer + legacy) and removed them from BOTH
     localStorage and sessionStorage.
  5. Net effect: the customer (and admin) get kicked out simultaneously.
     The founder typed credentials, watched the page bounce back to
     login, and reported the whole flow as "broken".

THE FIX (iter 326ll)
────────────────────
- `clearTokens()` is gone.
- The interceptor now identifies which slot the failing request's token
  came from and clears ONLY that slot.
- The other role's session is left alone, exactly like
  `clearAdminAuth` / `clearCustomerAuth` in secureTokenStore.js.

WHAT THIS TEST LOCKS IN (file-level smoke; the JS-side e2e is separate)
───────────────────────────────────────────────────────────────────────
  • `clearTokens` is no longer defined or called in /app/frontend/src/lib/api.js
  • The role-aware helpers `_detectActiveSlot` and `_clearSingleSlot` exist
  • Both 401-handling branches (auth-endpoint-direct AND refresh-failed)
    use the per-slot clear, never the blind multi-slot clear
  • The three slot constants (admin / customer / legacy) are explicit

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326ll_auth_interceptor_role_isolation.py -v
"""
from __future__ import annotations

import pathlib
import re

import pytest


_API = pathlib.Path("/app/frontend/src/lib/api.js")


def test_api_js_no_longer_defines_clearTokens():
    src = _API.read_text()
    assert "const clearTokens" not in src, (
        "clearTokens helper is back. iter 326ll deleted it because it "
        "wiped both admin AND customer tokens on a single auth-endpoint "
        "401 — re-introducing it will break prod login again."
    )


def test_api_js_does_not_call_clearTokens():
    src = _API.read_text()
    # Strip single-line comments so the regex doesn't false-positive on
    # the comment that still references the old name for context.
    code_only = re.sub(r"//.*$", "", src, flags=re.MULTILINE)
    # A bare `clearTokens(` call would re-introduce the role-blind wipe.
    assert not re.search(r'\bclearTokens\s*\(', code_only), (
        "clearTokens() invocation found in api.js — must use the "
        "role-aware _clearSingleSlot() instead."
    )


def test_api_js_defines_role_aware_clear_helpers():
    src = _API.read_text()
    for needle in ("_detectActiveSlot", "_clearSingleSlot"):
        assert needle in src, f"missing helper: {needle}"


def test_api_js_uses_per_slot_clear_in_both_branches():
    """Both 401 paths (direct auth-endpoint failure AND refresh-failed
    after one retry) must clear via _clearSingleSlot, NOT via a blind
    multi-slot loop."""
    src = _API.read_text()
    # Two _clearSingleSlot call sites: one in the auth-endpoint short-
    # circuit, one in the post-refresh fallback. Both required.
    assert src.count("_clearSingleSlot(") >= 2, (
        "iter 326ll expects per-slot clear in BOTH 401 branches. "
        f"Found {src.count('_clearSingleSlot(')} call(s)."
    )


def test_api_js_lists_admin_customer_legacy_slot_constants():
    src = _API.read_text()
    for const in (
        "ADMIN_TOKEN_KEY    = 'aurem_admin_token'",
        "CUSTOMER_TOKEN_KEY = 'aurem_customer_token'",
        "LEGACY_TOKEN_KEY   = 'auth_token'",
    ):
        assert const in src, f"slot constant missing: {const}"


def test_api_js_marks_the_fix_with_iter_marker():
    """Future-proofing — auditors greping for `iter 326ll` find the
    fix and the reasoning attached to it."""
    src = _API.read_text()
    assert "iter 326ll" in src, (
        "Fix marker missing. Auditors won't find the rationale via "
        "git grep."
    )
