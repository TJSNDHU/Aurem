"""
Tests for the 2 login UX fixes (iter 325e):

  Bug 1 — bcrypt was blocking the event loop on the first /login click.
  Bug 2 — Admin TOTP input only rendered after a 401 round-trip.

Backend changes (bug 1):
  - utils/auth.py adds averify_password / ahash_password async wrappers.
  - routes/auth.py customer login + team-member + admin_login + register
    + reset all use the async path.
  - routers/platform_auth_router.py login + register migration use the
    async path.

Frontend change (bug 2):
  - AdminLogin.jsx reveals the TOTP input immediately when the typed
    email looks like an admin account (KNOWN_ADMIN_EMAILS or
    @aurem.live).
  - AdminLogin.jsx + LuxeAuthOverlay.jsx button now shows a textual
    progress label ("Authenticating…" / "Signing in…") not just a spinner.
"""
import asyncio
import sys

import pytest

sys.path.insert(0, "/app/backend")


# ─────────────────────────────────────────────────────────────────────
# Bug 1 — async bcrypt wrappers
# ─────────────────────────────────────────────────────────────────────
def test_utils_auth_exports_async_wrappers():
    """The async wrappers MUST exist so callers can swap drop-in."""
    from utils.auth import averify_password, ahash_password
    assert asyncio.iscoroutinefunction(averify_password)
    assert asyncio.iscoroutinefunction(ahash_password)


@pytest.mark.asyncio
async def test_averify_password_matches_sync_behavior():
    from utils.auth import hash_password, averify_password
    h = hash_password("hunter2")
    assert await averify_password("hunter2", h) is True
    assert await averify_password("wrong", h) is False
    # Empty hash returns False without raising
    assert await averify_password("anything", "") is False


@pytest.mark.asyncio
async def test_ahash_password_roundtrips_through_async_verify():
    from utils.auth import ahash_password, averify_password
    h = await ahash_password("S3cure!1")
    assert h.startswith("$2b$"), "must produce a bcrypt hash"
    assert await averify_password("S3cure!1", h) is True


@pytest.mark.asyncio
async def test_async_verify_keeps_event_loop_responsive():
    """The whole point of moving bcrypt to a thread: while bcrypt is
    burning CPU, other coroutines must still progress. We launch a
    bcrypt verify and a 1-ms sleep in parallel and assert the sleep
    completed *before* verify. If verify were still sync-blocking the
    loop, the sleep would finish only after verify did."""
    from utils.auth import hash_password, averify_password
    h = hash_password("blocking-test")

    timings = {}

    async def quick_sleep():
        await asyncio.sleep(0.001)
        timings["sleep_done"] = asyncio.get_event_loop().time()

    async def verify():
        ok = await averify_password("blocking-test", h)
        timings["verify_done"] = asyncio.get_event_loop().time()
        return ok

    ok, _ = await asyncio.gather(verify(), quick_sleep())
    assert ok is True
    assert "sleep_done" in timings and "verify_done" in timings
    # If verify weren't truly async-offloaded, sleep couldn't finish first.
    assert timings["sleep_done"] <= timings["verify_done"]


def test_platform_auth_login_uses_async_verify():
    """Regression-guard: the platform_auth login path MUST call the
    async wrapper, not the sync bcrypt. The audit found 3 call sites in
    this file; all three must be on the async path now."""
    src = open(
        "/app/backend/routers/platform_auth_router.py", encoding="utf-8"
    ).read()
    # ahash + averify defined locally
    assert "async def averify_password_hash" in src
    assert "async def ahash_password" in src
    # The three call sites:
    #   1. admin_row password compare
    #   2. in-memory ADMIN_USERS compare
    #   3. platform_users compare + migration hash
    assert "await averify_password_hash(request.password, cand)" in src
    assert 'await averify_password_hash(request.password, stored)' in src
    assert "await averify_password_hash(request.password, user[\"password_hash\"])" in src
    assert "await averify_password_hash(request.password, user.get(\"password_hash\", \"\"))" in src
    assert "await ahash_password(request.password)" in src


def test_routes_auth_login_paths_use_async_verify():
    """Same regression-guard for the legacy /auth/login + /auth/admin/login."""
    src = open("/app/backend/routes/auth.py", encoding="utf-8").read()
    assert "from utils.auth import (" in src
    assert "averify_password" in src and "ahash_password" in src
    # Customer login
    assert "await averify_password(credentials.password, user.get(\"password\", \"\"))" in src
    # Team member login
    assert "await averify_password(\n                credentials.password, team_member[\"password_hash\"]" in src
    # Admin login password gate
    assert "if not await averify_password(credentials.password, user.get(\"password\", \"\"))" in src
    # Register + reset must hash async too
    assert "await ahash_password(user_data.password)" in src
    assert "await ahash_password(request_data.new_password)" in src


# ─────────────────────────────────────────────────────────────────────
# Bug 2 — AdminLogin TOTP shows on email match (no server round-trip)
# ─────────────────────────────────────────────────────────────────────
def test_admin_login_renders_totp_proactively_on_admin_email():
    src = open(
        "/app/frontend/src/platform/AdminLogin.jsx", encoding="utf-8"
    ).read()
    # New KNOWN_ADMIN_EMAILS + heuristic helper
    assert "KNOWN_ADMIN_EMAILS" in src
    assert "looksLikeAdmin" in src
    # The effect must trigger setNeedTotp on email change.
    assert "if (!needTotp && looksLikeAdmin(email))" in src
    assert "setNeedTotp(true)" in src
    # Domain heuristic — must match @aurem.live
    assert "@aurem.live" in src


def test_admin_login_button_shows_textual_progress_state():
    """Bug-2 part b: the spinner alone was easy to miss; the founder
    thought the click hadn't registered and clicked twice. The button
    now spells out 'Authenticating…' next to the spinner."""
    src = open(
        "/app/frontend/src/platform/AdminLogin.jsx", encoding="utf-8"
    ).read()
    assert "Authenticating…" in src


def test_luxe_overlay_button_shows_signing_in_label_on_login():
    src = open(
        "/app/frontend/src/platform/luxe/LuxeAuthOverlay.jsx",
        encoding="utf-8",
    ).read()
    assert "Signing in…" in src
