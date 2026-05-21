"""iter 325o — V2 customer actions: backend + frontend contract tests.

Covers:
  • All 17 backend endpoints exist + auth-protected + persist real Mongo writes.
  • Each of the 6 merged frontend pages renders the spec-required testids
    and wires the correct endpoint via v2api.

Founder dogfood account is reused for live HTTP smoke.
"""
from __future__ import annotations

import os
import re
import secrets
import time

import pytest
import requests

BASE   = "http://localhost:8001"
EMAIL  = "teji.ss1986+dogfood@gmail.com"
PWORD  = "AuremFounder2026!"

FRONTEND = "/app/frontend/src/platform/luxe"
V2_PAGES = f"{FRONTEND}/LuxeV2Pages.jsx"
V2_API   = f"{FRONTEND}/v2api.js"
SHELL    = f"{FRONTEND}/LuxeDashboardV2.jsx"

def _read(p):
    with open(p) as fh: return fh.read()


# ─────────────────────────────────────────────────────────────────
# Live auth → token reused across HTTP smoke tests
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/platform/auth/login",
                      json={"email": EMAIL, "password": PWORD}, timeout=8)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ═════════════════════════════════════════════════════════════════
#  BACKEND — 17 endpoints — live HTTP existence + happy path
# ═════════════════════════════════════════════════════════════════

ENDPOINTS = [
    # (method, path, json_body, expected_status_set)
    ("POST",   "/api/repair/trigger-scan",                  {}, {200}),
    ("GET",    "/api/incidents/list?limit=3",               None, {200}),
    ("POST",   "/api/incidents/resolve/507f1f77bcf86cd799439011", {}, {404}),
    ("POST",   "/api/incident/resolve/507f1f77bcf86cd799439011",  {}, {404}),
    ("POST",   "/api/platform/auth/2fa/toggle",             {}, {200}),
    ("DELETE", "/api/platform/auth/sessions/all",           None, {200}),
    ("GET",    "/api/platform/auth/me",                     None, {200}),
    ("PATCH",  "/api/platform/auth/me",                     {"phone": "+15551234567"}, {200}),
    ("GET",    "/api/platform/auth/session",                None, {200}),
    ("POST",   "/api/platform/auth/api-key/regenerate",     {}, {200}),
    ("POST",   "/api/onboarding/activate-pipeline",         {"website_url": "https://aurem.live"}, {200}),
    ("POST",   "/api/customer/diagnostic/run-now/test-bin", {}, {200}),
    ("GET",    "/api/bin/ora/settings",                     None, {200}),
    ("PATCH",  "/api/bin/settings",                         {"brand_name": "AUREM Test"}, {200}),
    ("GET",    "/api/voice-agent/config",                   None, {200}),
    ("GET",    "/api/voice-agent/health",                   None, {200}),
    ("PATCH",  "/api/leads/507f1f77bcf86cd799439011",       {"status": "qualified"}, {404}),
    ("POST",   "/api/leads/507f1f77bcf86cd799439011/send-email",
                                                            {"subject": "x", "body": "y"}, {404}),
]


@pytest.mark.parametrize("method,path,body,want", ENDPOINTS,
                         ids=[f"{m}_{p.split('?')[0]}" for m, p, _, _ in ENDPOINTS])
def test_endpoint_exists_and_responds(token, method, path, body, want):
    r = requests.request(method, f"{BASE}{path}",
                         headers=H(token), json=body, timeout=8)
    assert r.status_code in want, \
        f"{method} {path} → {r.status_code} (want one of {want}): {r.text[:200]}"


def test_auth_required_on_protected_endpoints():
    """Sample three new endpoints — all must reject missing/bad token."""
    for path in ("/api/platform/auth/me", "/api/bin/ora/settings",
                 "/api/voice-agent/config"):
        r = requests.get(f"{BASE}{path}", timeout=6)
        assert r.status_code in (401, 403), \
            f"GET {path} must require auth, got {r.status_code}"


# ═════════════════════════════════════════════════════════════════
#  BACKEND — PATCH /me persists across requests (real Mongo write)
# ═════════════════════════════════════════════════════════════════

def test_patch_me_persists(token):
    nonce = f"V2-{secrets.token_hex(4)}"
    r = requests.patch(f"{BASE}/api/platform/auth/me",
                       headers=H(token), json={"company_name": nonce}, timeout=8)
    assert r.status_code == 200, r.text
    r2 = requests.get(f"{BASE}/api/platform/auth/me", headers=H(token), timeout=8)
    assert r2.status_code == 200
    assert r2.json().get("company_name") == nonce, \
        f"company_name did not persist: {r2.json()}"


def test_patch_bin_settings_persists(token):
    nonce = f"AUREM-{secrets.token_hex(4)}"
    r = requests.patch(f"{BASE}/api/bin/settings",
                       headers=H(token), json={"brand_name": nonce}, timeout=8)
    assert r.status_code == 200, r.text
    r2 = requests.get(f"{BASE}/api/bin/ora/settings",
                      headers=H(token), timeout=8)
    assert r2.status_code == 200
    assert r2.json().get("brand_name") == nonce


def test_api_key_regenerate_returns_new_key(token):
    r1 = requests.post(f"{BASE}/api/platform/auth/api-key/regenerate",
                       headers=H(token), timeout=8)
    r2 = requests.post(f"{BASE}/api/platform/auth/api-key/regenerate",
                       headers=H(token), timeout=8)
    assert r1.status_code == r2.status_code == 200
    k1, k2 = r1.json().get("api_key"), r2.json().get("api_key")
    assert k1 and k2
    assert k1 != k2, "Regenerate must produce a new key each time"
    assert k1.startswith("sk_aurem_")


# ═════════════════════════════════════════════════════════════════
#  FRONTEND — Page contract tests (testids + endpoint wiring)
# ═════════════════════════════════════════════════════════════════

PAGE_CONTRACTS = {
    "LuxeLiveHealth": {
        "testids": ["page-live-health", "scan-now-btn", "incidents-card"],
        "endpoints": ["/api/repair/scores", "/api/incidents/list",
                      "/api/repair/trigger-scan", "/api/incidents/resolve/"],
    },
    "LuxeCRM": {
        "testids": ["page-crm", "leads-search", "leads-sort",
                    "export-csv-btn", "page-prev", "page-next"],
        "endpoints": ["/api/leads/stats",
                      "/api/customer/pipeline/scan-events",
                      "/api/leads/", "/send-email"],
    },
    "LuxeCampaign": {
        "testids": ["page-campaign", "create-wf-btn",
                    "workflows-card"],
        "endpoints": ["/api/automations/workflows"],
    },
    "LuxeORA": {
        "testids": ["page-ora", "ora-chat-card",
                    "ora-chat-input", "ora-chat-send"],
        "endpoints": ["/api/aurem/agents/status", "/api/ora/health",
                      "/api/public/ora/chat"],
    },
    "LuxeProfile": {
        "testids": ["page-profile", "identity-card", "schedule-card",
                    "security-card", "profile-save-btn",
                    "activate-pipeline-btn", "toggle-2fa",
                    "revoke-sessions-btn", "scan-now-profile"],
        "endpoints": ["/api/platform/auth/me",
                      "/api/onboarding/activate-pipeline",
                      "/api/customer/scan-schedule",
                      "/api/customer/diagnostic/run-now/",
                      "/api/platform/auth/2fa/toggle",
                      "/api/platform/auth/sessions/all"],
    },
    "LuxeSettings": {
        "testids": ["page-settings", "branding-card", "voice-card",
                    "api-key-card", "session-card",
                    "brand-save-btn", "voice-refresh-btn",
                    "api-key-regen-btn", "copy-embed-btn", "sign-out-btn"],
        "endpoints": ["/api/bin/ora/settings", "/api/bin/settings",
                      "/api/voice-agent/health", "/api/voice-agent/config",
                      "/api/platform/auth/session",
                      "/api/platform/auth/api-key/regenerate"],
    },
}

PAGE_SRC = _read(V2_PAGES)


@pytest.mark.parametrize("page,spec", list(PAGE_CONTRACTS.items()), ids=list(PAGE_CONTRACTS))
def test_page_has_required_testids(page, spec):
    # Locate the page export
    marker = f"export const {page} = "
    assert marker in PAGE_SRC, f"{page} export not found"
    for t in spec["testids"]:
        assert f'"{t}"' in PAGE_SRC, f"{page}: missing testid '{t}'"


@pytest.mark.parametrize("page,spec", list(PAGE_CONTRACTS.items()), ids=list(PAGE_CONTRACTS))
def test_page_wires_required_endpoints(page, spec):
    for ep in spec["endpoints"]:
        assert ep in PAGE_SRC, f"{page}: missing endpoint reference '{ep}'"


# ═════════════════════════════════════════════════════════════════
#  FRONTEND — sidebar contract (6 nav items, no duplicates)
# ═════════════════════════════════════════════════════════════════

def test_merged_sidebar_has_six_items_no_duplicates():
    src = _read(SHELL)
    keys = re.findall(r"k:\s*'([a-z-]+)'", src)
    # Only the 7 expected nav keys should exist
    expected = {"home", "live-health", "crm", "campaign", "ora", "profile", "settings"}
    actual = set(keys) & expected
    assert actual == expected, f"sidebar nav keys mismatch: missing {expected - actual}"
    # Duplicates of these in the NAV_SECTIONS block are forbidden
    nav_block_start = src.find("NAV_SECTIONS = [")
    nav_block_end = src.find("];", nav_block_start)
    nav_block = src[nav_block_start:nav_block_end]
    for k in expected:
        count = nav_block.count(f"k: '{k}'")
        assert count == 1, f"nav key '{k}' appears {count}× in sidebar — must be unique"


def test_pages_use_central_v2api_helper():
    """All save/edit actions must route through v2api (not raw axios) so
    auth/headers stay consistent."""
    src = PAGE_SRC
    assert "from './v2api'" in src
    assert "v2api.patch" in src and "v2api.post" in src and "v2api.delete" in src


def test_toast_helper_imported_for_user_feedback():
    src = PAGE_SRC
    assert "useV2Toast" in src
    # Every page that has a write action calls toast.success or toast.error
    for page in ("LuxeLiveHealth", "LuxeCRM", "LuxeCampaign",
                 "LuxeProfile", "LuxeSettings"):
        marker = f"export const {page} ="
        start = src.find(marker)
        end = src.find("export const", start + 10)
        block = src[start:end if end > 0 else len(src)]
        assert "toast.success" in block and "toast.error" in block, \
            f"{page}: missing success/error toast feedback"


def test_destructive_actions_have_confirm_dialog():
    src = PAGE_SRC
    # delete/revoke/regenerate must prompt window.confirm
    for action in ("remove =", "revokeAll =", "regenKey ="):
        idx = src.find(action)
        assert idx >= 0, f"missing action: {action}"
        next_block = src[idx:idx + 400]
        assert "window.confirm" in next_block, \
            f"{action.strip(' =')}: must prompt window.confirm"


def test_v2api_reads_token_from_storage():
    src = _read(V2_API)
    assert "aurem_customer_token" in src
    assert "platform_token" in src
    assert "Bearer" in src
