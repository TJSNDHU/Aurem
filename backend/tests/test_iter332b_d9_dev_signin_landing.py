"""
iter 332b D-9 — Dev portal Sign-In landing fix.

Bug: top-right "Sign in" on /developers landed on /developers/signup,
which forced returning users through a 3-step OTP signup wizard.

Fix: dedicated /developers/login page hits POST /api/developers/login
directly; DeveloperShell's nav link repointed; /developers/signin
mirror route added.
"""
from __future__ import annotations


def test_dev_login_page_exists():
    src = open(
        "/app/frontend/src/platform/developers/DevLogin.jsx"
    ).read()
    for tid in ("dev-login-title", "dev-login-card",
                "dev-login-email", "dev-login-password",
                "dev-login-submit", "dev-login-go-signup"):
        assert tid in src, f"Missing testid {tid}"
    # Hits the real login endpoint (not signup)
    assert "/api/developers/login" in src
    assert "/api/developers/signup" not in src  # mustn't accidentally call signup
    # Friendly error mapping is present
    assert "invalid_credentials" in src
    assert "account_not_found" in src


def test_developer_shell_signin_points_to_login_not_signup():
    src = open(
        "/app/frontend/src/platform/developers/DeveloperShell.jsx"
    ).read()
    # The nav link must point at /developers/login. We grep for the
    # specific test id + the to= value on its own line.
    idx = src.find('data-testid="dev-shell-login-link"')
    assert idx > 0, "Signin nav link missing from DeveloperShell"
    window = src[max(0, idx - 200): idx + 200]
    assert 'to="/developers/login"' in window, (
        f"Signin link still points at the wrong route. Surrounding code:\n{window}"
    )


def test_app_js_wires_both_login_routes():
    src = open("/app/frontend/src/App.js").read()
    assert "import DevLogin" in src
    assert '/developers/login' in src
    # /signin mirror so old shareable links don't break
    assert '/developers/signin' in src
