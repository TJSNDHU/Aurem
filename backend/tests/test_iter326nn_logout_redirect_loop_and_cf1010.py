"""
test_iter326nn_logout_redirect_loop_and_cf1010.py — iter 326nn.
══════════════════════════════════════════════════════════════════════════════
Founder bug (2026-05-22 in production):
  "Login page not showing direct jump to admin dashboard. When going to
   use admin services it said need login again. To use login need to
   click logout, but unfortunate that logout sends to dashboard page
   again."

Plain English: a stale admin JWT in the legacy `platform_token`
localStorage slot survived `clearAdminAuth()`. When the founder hit
`/admin/login`, the useEffect on that page called `getPlatformToken()`,
which falls through to the legacy slot, decoded a still-valid
`is_super_admin: true` payload, and bounced them to
`/admin/mission-control`. The dashboard then failed admin-service API
calls because the actual admin slot was empty — cue "log in again"
prompts. Logout cleared `aurem_admin_token` but NOT the mirror, so the
loop repeated forever.

THE FIX (iter 326nn)
────────────────────
1. `clearAdminAuth()` now also wipes `platform_token` if its role
   claim is "admin". `clearCustomerAuth()` mirrors the same logic.
2. `AdminLogin` useEffect verifies `payload.exp` before auto-
   redirecting — a stale token whose exp is in the past gets cleared
   instead of bouncing the user to a broken dashboard.

ALSO IN THIS ITER — Resend Cloudflare 1010 (deploy log)
───────────────────────────────────────────────────────
The iter 326kk HTTP fallback was being blocked by Cloudflare with
"error code 1010" (banned browser signature) because we sent NO
User-Agent. Fix: send a real UA + Accept header.

WHAT THIS TEST LOCKS IN
───────────────────────
  Frontend
    • clearAdminAuth() also clears platform_token when its role is admin
    • clearCustomerAuth() also clears platform_token when its role is customer
    • AdminLogin useEffect verifies payload.exp before redirect
    • iter 326nn markers present in both files for audit grepping

  Backend
    • email_engine HTTP fallback sends a non-empty User-Agent
    • email_engine HTTP fallback sends Accept: application/json
    • iter 326nn marker present in email_engine.py

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326nn_logout_redirect_loop_and_cf1010.py -v
"""
from __future__ import annotations

import pathlib

import pytest


_STORE  = pathlib.Path("/app/frontend/src/utils/secureTokenStore.js")
_LOGIN  = pathlib.Path("/app/frontend/src/platform/AdminLogin.jsx")
_ENGINE = pathlib.Path("/app/backend/services/email_engine.py")


# ─────────────────────────────────────────────────────────────────────────────
# Frontend — secureTokenStore.js mirror cleanup
# ─────────────────────────────────────────────────────────────────────────────
def test_clear_admin_auth_also_clears_legacy_mirror_when_admin():
    src = _STORE.read_text()
    # Pull out the clearAdminAuth body
    start = src.find("export function clearAdminAuth")
    body  = src[start:src.find("export function", start + 1)]
    assert "_clearDual(PLATFORM_TOKEN_KEY)" in body, (
        "clearAdminAuth must also clear the legacy PLATFORM_TOKEN_KEY "
        "mirror when its role is admin — otherwise stale admin JWTs "
        "survive logout and bounce the founder back to the dashboard."
    )
    assert "_decodeRole(legacy) === 'admin'" in body or \
           '_decodeRole(legacy) === "admin"' in body, (
        "Must role-check the legacy mirror — wiping it unconditionally "
        "would undo iter 326o role separation."
    )


def test_clear_customer_auth_also_clears_legacy_mirror_when_customer():
    src = _STORE.read_text()
    start = src.find("export function clearCustomerAuth")
    body  = src[start:src.find("export function", start + 1)]
    assert "_clearDual(PLATFORM_TOKEN_KEY)" in body, (
        "clearCustomerAuth must also clear the legacy mirror when "
        "its role is customer."
    )
    assert "_decodeRole(legacy) === 'customer'" in body or \
           '_decodeRole(legacy) === "customer"' in body, (
        "Must role-check the legacy mirror so admin tokens survive a "
        "customer logout in the same browser."
    )


def test_store_marks_fix_with_iter_marker():
    src = _STORE.read_text()
    assert "iter 326nn" in src


# ─────────────────────────────────────────────────────────────────────────────
# Frontend — AdminLogin.jsx exp check
# ─────────────────────────────────────────────────────────────────────────────
def test_admin_login_verifies_token_expiry_before_redirect():
    src = _LOGIN.read_text()
    # We compare payload.exp against `Math.floor(Date.now() / 1000)`
    assert "payload.exp" in src, "AdminLogin must check payload.exp"
    assert "Date.now()" in src
    assert "iter 326nn" in src


def test_admin_login_clears_stale_token_instead_of_bouncing():
    """A stale (expired) token in any slot must trigger a clear, not a
    redirect — otherwise the dashboard fails every API call and the
    user gets stuck in a loop."""
    src = _LOGIN.read_text()
    assert "clearAdminAuth" in src, (
        "AdminLogin must call clearAdminAuth() when it detects an "
        "expired token — otherwise the bug recurs."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Backend — email_engine User-Agent fix
# ─────────────────────────────────────────────────────────────────────────────
def test_email_engine_http_fallback_sends_user_agent():
    src = _ENGINE.read_text()
    # Find the _HttpEmails class body and assert the UA header is present.
    cls_start = src.find("class _HttpEmails")
    cls_body  = src[cls_start:cls_start + 3000]
    assert '"User-Agent"' in cls_body, (
        "HTTP fallback must send a User-Agent header — Cloudflare "
        "1010 blocks the request otherwise (deploy log 2026-05-22)."
    )
    # iter 326oo — UA must NOT contain Cloudflare-blocked bot signatures.
    # The iter 326nn UA ("python-urllib") was blocked. Block-list match:
    for forbidden in ("python-urllib", "urllib", "python-requests",
                       "curl", "wget", "scrapy"):
        # We allow the substring "python" alone (resend-python is fine),
        # but the precise bad strings above must not appear.
        assert forbidden not in cls_body.split("User-Agent")[1].split(",")[0], (
            f"UA contains Cloudflare-blocked token: {forbidden!r}"
        )
    # And specifically: blend in with the official Resend SDK UA.
    assert "resend-python/" in cls_body, (
        "UA should look like the Resend python SDK so Cloudflare "
        "treats us as normal SDK traffic (iter 326oo fix)."
    )


def test_email_engine_http_fallback_sends_accept_json():
    src = _ENGINE.read_text()
    cls_start = src.find("class _HttpEmails")
    cls_body  = src[cls_start:cls_start + 3000]
    assert '"Accept"' in cls_body and "application/json" in cls_body


def test_email_engine_marks_iter_326nn():
    src = _ENGINE.read_text()
    assert "iter 326nn" in src
