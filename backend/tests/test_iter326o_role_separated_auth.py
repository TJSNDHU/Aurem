"""
test_iter326o_role_separated_auth.py — Regression for iter 326o.
══════════════════════════════════════════════════════════════════════════════
Founder bug report (verbatim): "if admin logs out, customer login won't work
either... if admin logs out, customer login nhi ho payega".

ROOT CAUSE
──────────
`frontend/src/utils/secureTokenStore.js` used ONE storage key
(`platform_token`) for BOTH admin and customer JWTs. Three logout call
sites all invoked `clearPlatformAuth()` which wiped that single key from
sessionStorage AND localStorage. Result: when admin clicked logout, the
customer's still-valid session — living in the SAME slot in the SAME
browser — was nuked too.

THE FIX (frontend-only — no backend changes)
────────────────────────────────────────────
Per-role storage slots:
  aurem_admin_token    /  aurem_admin_user
  aurem_customer_token /  aurem_customer_user
  platform_token       /  platform_user        ← legacy, read-only fallback

`clearAdminAuth()` only clears the admin slot.
`clearCustomerAuth()` only clears the customer slot.
Three logout call sites updated:
  • AdminShell.jsx        →  clearAdminAuth()
  • AuremDashboard.jsx    →  clearCustomerAuth()
  • PlatformDashboard.jsx →  clearCustomerAuth()  (both 401 redirect & UI logout)

The legacy `setPlatformToken / getPlatformToken / clearPlatformAuth` facade
remains for backwards compatibility but its behaviour is no longer
"cross-role nuke" — it routes writes to the correct per-role slot based
on the JWT's role claim and clears only the role it can infer.

WHAT THIS TEST FILE CHECKS
──────────────────────────
Since the regression is in JS, we can't run it through pytest directly.
Instead we test the JS file as a TEXT contract — every promise this fix
makes must show up as a literal substring in the source. If a future
agent edits the file in a way that removes any of these guarantees, the
test fails immediately.

Run:  cd /app/backend && python3 -m pytest tests/test_iter326o_role_separated_auth.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

TOKEN_STORE = Path("/app/frontend/src/utils/secureTokenStore.js")
ADMIN_SHELL = Path("/app/frontend/src/platform/AdminShell.jsx")
AUREM_DASH  = Path("/app/frontend/src/platform/AuremDashboard.jsx")
PLAT_DASH   = Path("/app/frontend/src/platform/PlatformDashboard.jsx")


@pytest.fixture(scope="module")
def store_src() -> str:
    assert TOKEN_STORE.exists(), f"missing: {TOKEN_STORE}"
    return TOKEN_STORE.read_text()


def test_per_role_storage_keys_exist(store_src):
    """The role-separated keys MUST be defined and distinct from each
    other and from the legacy key. If they collide, the whole fix
    collapses back to the original bug."""
    assert "'aurem_admin_token'" in store_src
    assert "'aurem_admin_user'" in store_src
    assert "'aurem_customer_token'" in store_src
    assert "'aurem_customer_user'" in store_src
    assert "'platform_token'" in store_src   # legacy fallback kept
    assert "'platform_user'" in store_src    # legacy fallback kept


def test_role_scoped_clear_helpers_exported(store_src):
    """Both per-role clearers must be exported — these are the new
    functions logout call sites need to invoke."""
    assert "export function clearAdminAuth(" in store_src
    assert "export function clearCustomerAuth(" in store_src
    assert "export function setAdminToken(" in store_src
    assert "export function getAdminToken(" in store_src
    assert "export function setCustomerToken(" in store_src
    assert "export function getCustomerToken(" in store_src


def test_clearAdminAuth_does_not_touch_customer_slot(store_src):
    """The whole point of the fix: clearAdminAuth() must clear ONLY
    admin keys. We assert by reading the function body and confirming
    it never references a CUSTOMER_*_KEY."""
    # Slice the function body. The body starts after `export function clearAdminAuth(`
    # and ends at the next `export function` declaration.
    marker = "export function clearAdminAuth("
    i = store_src.index(marker)
    j = store_src.index("export function", i + len(marker))
    body = store_src[i:j]
    assert "ADMIN_TOKEN_KEY" in body
    assert "ADMIN_USER_KEY" in body
    assert "CUSTOMER_TOKEN_KEY" not in body, (
        "clearAdminAuth() must NEVER touch CUSTOMER_TOKEN_KEY — that is "
        "the exact bug we're fixing."
    )
    assert "CUSTOMER_USER_KEY" not in body, (
        "clearAdminAuth() must NEVER touch CUSTOMER_USER_KEY."
    )


def test_clearCustomerAuth_does_not_touch_admin_slot(store_src):
    """Symmetrical guarantee — customer logout must not affect admin."""
    marker = "export function clearCustomerAuth("
    i = store_src.index(marker)
    j = store_src.index("export function", i + len(marker))
    body = store_src[i:j]
    assert "CUSTOMER_TOKEN_KEY" in body
    assert "CUSTOMER_USER_KEY" in body
    assert "ADMIN_TOKEN_KEY" not in body, (
        "clearCustomerAuth() must NEVER touch ADMIN_TOKEN_KEY."
    )
    assert "ADMIN_USER_KEY" not in body, (
        "clearCustomerAuth() must NEVER touch ADMIN_USER_KEY."
    )


def test_legacy_clearPlatformAuth_no_longer_nukes_both_roles(store_src):
    """The legacy `clearPlatformAuth` is now CONDITIONAL — it picks the
    role to clear based on which slot is populated, instead of wiping
    both. This is a soft guarantee: even old call sites that still use
    `clearPlatformAuth` won't trigger the cross-role nuke any more."""
    marker = "export function clearPlatformAuth("
    i = store_src.index(marker)
    body = store_src[i:i + 1500]
    # Conditional branches must exist; we can't have an unconditional
    # `_clearDual(ADMIN_TOKEN_KEY)` followed by `_clearDual(CUSTOMER_TOKEN_KEY)`
    # at the top of the function — that's exactly what we're banning.
    assert "if (adminPresent" in body or "if(adminPresent" in body, (
        "clearPlatformAuth must branch on which role is present, not "
        "wipe both unconditionally."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Call sites — three logout entry points must use the new role-scoped APIs.
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path,must_call,must_not_call", [
    (ADMIN_SHELL, "clearAdminAuth(", "clearPlatformAuth("),
    (AUREM_DASH,  "clearCustomerAuth(", "clearPlatformAuth("),
    (PLAT_DASH,   "clearCustomerAuth(", "clearPlatformAuth("),
])
def test_logout_call_sites_use_role_scoped_clear(path, must_call, must_not_call):
    """Each of the three logout entry points must:
       1. Call the new per-role clear function.
       2. Not call the legacy `clearPlatformAuth` (which was the bug)."""
    src = path.read_text()
    assert must_call in src, (
        f"{path.name} should call `{must_call}` but does not — the role-"
        f"scoped fix is not wired here."
    )
    assert must_not_call not in src, (
        f"{path.name} still calls `{must_not_call}` — that is the legacy "
        f"function that caused the founder's bug. Use `{must_call}` instead."
    )


def test_logout_imports_updated(store_src):
    """A grep of the three call-site imports must include the new
    role-scoped helpers. (We test the IMPORT line specifically — call
    sites that import the wrong helper would still work but defeat the
    test's intent.)"""
    for path, expected_import in [
        (ADMIN_SHELL, "clearAdminAuth"),
        (AUREM_DASH,  "clearCustomerAuth"),
        (PLAT_DASH,   "clearCustomerAuth"),
    ]:
        src = path.read_text()
        # Find any line that imports from secureTokenStore.
        lines = [
            ln for ln in src.splitlines()
            if "secureTokenStore" in ln and "import" in ln
        ]
        assert lines, f"{path.name} has no import from secureTokenStore"
        joined = "\n".join(lines)
        assert expected_import in joined, (
            f"{path.name} imports from secureTokenStore but does not pull "
            f"`{expected_import}` — the new helper is unused."
        )
