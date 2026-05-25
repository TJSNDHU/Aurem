"""
iter 332b D-21 — Admin login/logout loop fix.

Founder bug (verbatim):
  "log in and log out . i just tried to log in my admin pannel but when i
   tried to land on admin login it direct land on admin dashbord and some
   functions want login but when i tried to log out that land me on
   https://aurem.live/admin/mission-control but no log out workes . means
   stucked in a loop."

These tests are file-text assertions because the loop is React-router /
browser-storage behavior the testing agent will validate live.
Pytest's job here is to make sure the fix never regresses.
"""


def test_secure_token_store_exports_force_logout():
    """A nuclear `forceLogoutAdminEverywhere()` must exist and wipe every
    known admin storage slot."""
    src = open("/app/frontend/src/utils/secureTokenStore.js").read()
    assert "forceLogoutAdminEverywhere" in src
    # Hard-clears the refresh handle
    assert "aurem_admin_refresh" in src
    # Drops the tombstone the interceptor + login page honor
    assert "aurem_just_logged_out" in src
    # Dispatches a global event so live components stop polling
    assert "aurem:force-logout" in src


def test_admin_shell_logout_uses_force_logout_and_hard_reload():
    src = open("/app/frontend/src/platform/AdminShell.jsx").read()
    assert "forceLogoutAdminEverywhere" in src
    # Calls backend logout to clear the HttpOnly refresh cookie
    assert "/api/auth/admin/logout" in src
    # Full page reload (not react-router navigate) so in-flight axios
    # requests die before the refresh interceptor can re-mint a token.
    assert "window.location.replace" in src
    assert "/admin/login?logged_out=1" in src


def test_admin_login_honors_logout_tombstone_and_force_flag():
    """AdminLogin must never auto-redirect when any of:
       - `?force=1`
       - `?logged_out=1`
       - sessionStorage['aurem_just_logged_out'] === '1'"""
    src = open("/app/frontend/src/platform/AdminLogin.jsx").read()
    assert "useLocation" in src
    assert "force" in src and "logged_out" in src
    assert "aurem_just_logged_out" in src
    assert "forceLogoutAdminEverywhere" in src


def test_api_interceptor_skips_refresh_after_logout():
    """The 401 → silent-refresh interceptor must short-circuit when the
    tombstone is set; otherwise the founder gets re-minted into the
    dashboard a heartbeat after clicking Sign out."""
    src = open("/app/frontend/src/lib/api.js").read()
    assert "aurem_just_logged_out" in src
    # The check must live INSIDE the response error handler, BEFORE the
    # axios.post call to /api/auth/admin/refresh. Skip the docstring
    # comment on line 41 by anchoring on the actual axios call.
    idx_tombstone = src.find("aurem_just_logged_out")
    idx_refresh   = src.find("axios\n          .post")
    if idx_refresh < 0:
        idx_refresh = src.find("axios.post")
    assert idx_refresh > 0, "Could not locate the silent-refresh axios call."
    assert 0 < idx_tombstone < idx_refresh, (
        "Tombstone check must precede the silent refresh attempt."
    )


def test_admin_login_route_still_mounted():
    """Sanity: /admin/login route still wired in App.js."""
    src = open("/app/frontend/src/App.js").read()
    assert '"/admin/login"' in src or "'/admin/login'" in src
