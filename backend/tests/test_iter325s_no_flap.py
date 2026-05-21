"""iter 325s — Online/offline blink fix contract tests.

Locks in the two-layer cure for the recurring "API error / Admin offline"
flap users reported on production:

  Layer 1 — apiFetch retries transient 5xx + network errors with backoff
            (GET/HEAD only; 250ms + 700ms; max 3 attempts).
  Layer 2 — useLiveApi requires 3 consecutive failures (~45s sustained
            downtime) before flipping `error` state. Single transient
            blips keep stale data on screen with no error UI.

These tests prevent the regression from reappearing if anyone simplifies
the hook back to "fail fast on first 5xx".
"""
from __future__ import annotations

import re

import pytest

HOOK_FILE = "/app/frontend/src/hooks/useAuthFetch.js"


def _read():
    with open(HOOK_FILE) as fh:
        return fh.read()


# ─────────────────────────────────────────────────────────────────
# Layer 1 — apiFetch retry contract
# ─────────────────────────────────────────────────────────────────

def test_apifetch_has_retry_loop():
    src = _read()
    assert "RETRY_DELAYS_MS" in src, "Retry constant missing"
    # Two retry delays = three total attempts
    assert re.search(r"RETRY_DELAYS_MS\s*=\s*isReadOnly\s*\?\s*\[\s*250\s*,\s*700\s*\]",
                     src), "Retry backoff must be [250, 700] ms"


def test_apifetch_only_retries_read_methods():
    src = _read()
    # POST/PATCH/DELETE must NOT retry — they could be mutating.
    assert 'method === "GET" || method === "HEAD"' in src, \
        "Retry must be gated to GET/HEAD only"
    assert "isReadOnly ? [250, 700] : []" in src, \
        "Non-read methods must get an empty retry list"


def test_apifetch_only_retries_transient_5xx():
    src = _read()
    # Catch 502/503/504. 4xx must NOT retry — they're deterministic.
    assert "r.status === 502 || r.status === 503 || r.status === 504" in src, \
        "Retry must be limited to 502/503/504"
    # Ensure 401/403/404/400 are NOT in the retry condition
    bad_patterns = ["status === 401", "status === 403", "status === 404", "status === 400"]
    for pat in bad_patterns:
        # If present at all, must NOT be inside the retry conditional
        if pat in src:
            # extract retry block and check
            start = src.find("for (let attempt")
            end = src.find("// Exhausted retries", start)
            block = src[start:end] if end > 0 else src[start:start + 2000]
            assert pat not in block, f"4xx ({pat}) must not trigger retry"


# ─────────────────────────────────────────────────────────────────
# Layer 2 — useLiveApi failure-debounce contract
# ─────────────────────────────────────────────────────────────────

def test_failure_streak_threshold_is_three():
    src = _read()
    assert "FAILURE_THRESHOLD = 3" in src, \
        "Must require 3 consecutive failures before declaring offline"


def test_failure_streak_resets_on_success():
    src = _read()
    # The success branch must zero the counter
    assert "failStreak.current = 0" in src, \
        "Success must reset the failure streak"
    # The setError(null) must be alongside the reset
    success_idx = src.find("failStreak.current = 0")
    nearby = src[success_idx:success_idx + 200]
    assert "setError(null)" in nearby, \
        "Success branch must also clear setError(null) for fresh-data UI"


def test_failure_streak_only_increments_on_non_auth():
    """Auth errors (401/403) must surface immediately — re-login UX
    cannot be debounced. Only 5xx / network errors get the debounce."""
    src = _read()
    assert "e?.status === 401 || e?.status === 403" in src, \
        "Auth-error fast path missing"
    assert "isAuthError || firstLoad.current" in src, \
        "First-load failures must also bypass the debounce so a permanently-broken endpoint surfaces immediately"


def test_failure_threshold_documented():
    """The fix must carry a clear comment explaining WHY this debounce
    exists — protects future devs from removing it."""
    src = _read()
    assert "iter 325s" in src and "single-failure flap" in src, \
        "iter 325s root-cause comment must stay"


# ─────────────────────────────────────────────────────────────────
# Behaviour sanity — no regression of the data preservation guarantee
# ─────────────────────────────────────────────────────────────────

def test_stale_data_preserved_on_transient_error():
    """During the debounce window, `setData` must NOT be reset, so the
    UI keeps showing last-known-good values instead of flashing empty."""
    src = _read()
    # Find the runOnce catch block specifically (it sets failStreak).
    # We anchor on the failStreak.current += 1 line to avoid matching
    # the apiFetch retry catch.
    anchor = src.find("failStreak.current += 1")
    assert anchor > 0, "iter 325s failStreak increment missing"
    # Walk backward to the enclosing `} catch (e) {` and forward to next `}`
    catch_start = src.rfind("} catch (e) {", 0, anchor)
    finally_start = src.find("} finally", anchor)
    assert catch_start > 0 and finally_start > anchor
    block = src[catch_start:finally_start]
    assert "setData" not in block, \
        f"runOnce catch must NOT touch data — stale data must stay on screen. Block:\n{block}"
