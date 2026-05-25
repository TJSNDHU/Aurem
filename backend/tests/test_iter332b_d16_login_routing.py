"""
iter 332b D-16 — Homepage top-right "Log In" must point at /my for
unauthenticated visitors, and AdminLogin must render a meaningful error
for 5xx gateway responses instead of dumping users into the generic
"Connection error" catch-all.

Founder bug report (Rule Zero):
  "log in button must be land on https://aurem.live/my . and admin
   page also not going through showing erron on signin"
"""
import re


def test_homepage_login_link_lands_on_my():
    src = open("/app/frontend/src/platform/AuremHomepage.jsx").read()
    # The nav-link-login Link must point at /my (was /login).
    m = re.search(
        r'<Link\s+to="([^"]+)"\s+className="nav-login"\s+data-testid="nav-link-login"',
        src,
    )
    assert m, "nav-link-login Link not found on homepage"
    assert m.group(1) == "/my", (
        f"nav-link-login should point at /my but points at {m.group(1)!r}"
    )


def test_homepage_login_keeps_smart_redirect():
    """Regression: /my fallback must NOT remove the smart-redirect that
    short-circuits already-authenticated admin/dev/customer sessions."""
    src = open("/app/frontend/src/platform/AuremHomepage.jsx").read()
    assert "handleSignIn" in src
    assert "/admin/mission-control" in src
    assert "/developers/dashboard" in src


def test_admin_login_handles_502_gracefully():
    """AdminLogin must safe-parse the response body (production 502s
    return HTML, not JSON) and surface a clear server-down message."""
    src = open("/app/frontend/src/platform/AdminLogin.jsx").read()
    # Safe parse via res.text() + JSON.parse, not await res.json().
    assert "await res.text()" in src, (
        "AdminLogin still calls res.json() — will throw on 502 HTML bodies"
    )
    assert "JSON.parse" in src
    # Distinct error branch for gateway errors.
    assert "502" in src and "503" in src and "504" in src, (
        "AdminLogin missing 5xx-specific error branches"
    )
