"""
iter 332b A-4 — Session-expired toast (auth UX hand-off) +
                python3-saml ACS handler wiring.
"""
from __future__ import annotations

import pytest


def test_route_guards_set_session_expired_flag():
    """RouteGuards.jsx must stash sessionStorage['aurem_session_expired']
    when bouncing an expired/invalid JWT — AdminLogin reads this flag."""
    from pathlib import Path
    src = Path("/app/frontend/src/platform/RouteGuards.jsx").read_text()
    assert "aurem_session_expired" in src
    assert "flagSessionExpired" in src
    # Both expiry AND invalid token paths set the flag
    assert src.count("flagSessionExpired") >= 4


def test_admin_login_reads_session_expired_flag():
    """AdminLogin.jsx must read the flag once on mount, show the banner,
    then clear sessionStorage so it doesn't reappear on refresh."""
    from pathlib import Path
    src = Path("/app/frontend/src/platform/AdminLogin.jsx").read_text()
    assert "aurem_session_expired" in src
    assert "Your session expired" in src
    assert "admin-login-session-expired" in src
    assert "sessionStorage.removeItem" in src


def test_python3_saml_is_installed_and_importable():
    """Sanity: the integration playbook required python3-saml 1.16+.
    If this fails the ACS handler will silently fall back to the
    'python3_saml_not_installed' error string."""
    from onelogin.saml2.auth import OneLogin_Saml2_Auth   # noqa: F401
    from onelogin.saml2.settings import OneLogin_Saml2_Settings  # noqa: F401


def test_saml_build_settings_assembles_for_okta():
    from services.saml_sso import build_saml_settings
    org = {"slug": "acme", "org_id": "abc123"}
    cfg = {
        "idp_provider":  "okta",
        "idp_entity_id": "http://www.okta.com/exk123",
        "idp_sso_url":   "https://acme.okta.com/app/abc/sso/saml",
        "idp_cert":      "-----BEGIN CERTIFICATE-----\nMIIfake\n-----END CERTIFICATE-----",
        "sp_entity_id":  "https://aurem.live/saml/acme/metadata",
        "acs_url":       "https://aurem.live/api/saml/abc123/acs",
    }
    s = build_saml_settings(org, cfg)
    assert s["strict"] is True
    assert s["sp"]["entityId"] == "https://aurem.live/saml/acme/metadata"
    assert s["sp"]["assertionConsumerService"]["url"].endswith("/api/saml/abc123/acs")
    assert s["idp"]["entityId"] == "http://www.okta.com/exk123"
    assert s["idp"]["singleSignOnService"]["url"].startswith("https://acme.okta.com")
    assert s["security"]["wantAssertionsSigned"] is True


def test_map_saml_attributes_pulls_email_first_last():
    from services.saml_sso import map_saml_attributes
    attrs = {
        "Email":      ["user@example.com"],
        "FirstName":  ["Jane"],
        "LastName":   ["Doe"],
    }
    out = map_saml_attributes(attrs, name_id="user@example.com", cfg={})
    assert out["email"] == "user@example.com"
    assert out["first_name"] == "Jane"
    assert out["last_name"] == "Doe"


def test_map_saml_attributes_falls_back_to_name_id_for_email():
    from services.saml_sso import map_saml_attributes
    out = map_saml_attributes({}, name_id="fallback@example.com", cfg={})
    assert out["email"] == "fallback@example.com"


def test_map_saml_attributes_handles_azure_ad_claims():
    """Azure AD uses long URN claim names. Our defaults must catch them."""
    from services.saml_sso import map_saml_attributes
    attrs = {
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": ["bob@ms.example"],
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname":     ["Bob"],
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname":       ["Stone"],
    }
    out = map_saml_attributes(attrs, name_id=None, cfg={})
    assert out["email"] == "bob@ms.example"
    assert out["first_name"] == "Bob"
    assert out["last_name"] == "Stone"


def test_prepare_fastapi_request_uses_forwarded_proto():
    """When sitting behind k8s ingress, scheme must come from
    X-Forwarded-Proto, not request.url.scheme — otherwise python3-saml's
    Destination check fails."""
    from services.saml_sso import prepare_fastapi_request

    class FakeURL:
        scheme = "http"
        hostname = "backend-internal"
        port = 80
        path = "/api/saml/abc/acs"
        query = ""

    class FakeReq:
        url = FakeURL()
        headers = {
            "x-forwarded-proto": "https",
            "x-forwarded-host":  "aurem.live",
        }
        query_params = {}

    req_data = prepare_fastapi_request(FakeReq(), "fake_b64", "/admin/landing")
    assert req_data["https"] == "on"
    assert req_data["http_host"] == "aurem.live"
    assert req_data["post_data"]["SAMLResponse"] == "fake_b64"
    assert req_data["post_data"]["RelayState"] == "/admin/landing"


def test_saml_acs_landing_page_exists():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/SamlAcsLanding.jsx").read_text()
    assert "saml-acs-landing" in src
    assert "setPlatformToken" in src
    # Hash-based token plucking (NOT query) — required for log hygiene.
    assert "window.location.hash" in src


def test_saml_acs_redirects_to_landing_page():
    from pathlib import Path
    src = Path("/app/backend/routers/saml_router.py").read_text()
    assert "/saml/landing" in src
    assert "create_token" in src
    assert "upsert_saml_user" in src


def test_requirements_txt_pins_python3_saml():
    from pathlib import Path
    req = Path("/app/backend/requirements.txt").read_text()
    assert "python3-saml" in req
    assert "xmlsec" in req
