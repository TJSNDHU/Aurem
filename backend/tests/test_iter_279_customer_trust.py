"""
iter 279 regression tests — ORA tenant isolation + Stripe toggle + UX toast + Pillars link.
"""
from __future__ import annotations

import os
import time
import uuid
import importlib
from pathlib import Path

import pytest
import requests


BACKEND_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "http://localhost:8001",
)
API = f"{BACKEND_URL.rstrip('/')}/api"


# ═══════════════════════════════════════════════════════════════════
# Part 1 — ORA Session Tenant Isolation
# ═══════════════════════════════════════════════════════════════════

class TestOraTenantIsolation:
    """Prove that user B cannot resume user A's chat session."""

    def test_cross_tenant_resume_mints_fresh_session(self):
        # Alpha starts a session with a secret
        secret = f"IT279-{uuid.uuid4().hex[:8].upper()}"
        r1 = requests.post(
            f"{API}/aurem/chat",
            json={
                "message": f"Remember this secret codeword: {secret}",
                "tenant_id": f"alpha_{uuid.uuid4().hex[:6]}",
            },
            timeout=30,
        )
        assert r1.status_code == 200
        session = r1.json()["session_id"]
        assert session
        time.sleep(1)

        # Beta tries to resume Alpha's session — should get fresh one
        r2 = requests.post(
            f"{API}/aurem/chat",
            json={
                "message": "What was the codeword?",
                "session_id": session,
                "tenant_id": f"beta_{uuid.uuid4().hex[:6]}",
            },
            timeout=30,
        )
        assert r2.status_code == 200
        beta_session = r2.json()["session_id"]
        assert beta_session != session, "Beta got same session — isolation failed"
        # Beta must not see Alpha's secret
        assert secret not in r2.json().get("response", ""), "Secret leaked to Beta!"

    def test_same_tenant_session_resume_works(self):
        tenant = f"consistent_{uuid.uuid4().hex[:6]}"
        r1 = requests.post(
            f"{API}/aurem/chat",
            json={"message": "Note: my favorite fruit is DRAGONFRUIT279", "tenant_id": tenant},
            timeout=30,
        )
        session = r1.json()["session_id"]
        time.sleep(1)
        r2 = requests.post(
            f"{API}/aurem/chat",
            json={"message": "What's my favorite fruit?", "session_id": session, "tenant_id": tenant},
            timeout=30,
        )
        assert r2.status_code == 200
        assert r2.json()["session_id"] == session, "Same-tenant lost its session"

    def test_ora_session_owners_collection_populated(self):
        # Trigger a write
        tenant = f"probe_{uuid.uuid4().hex[:6]}"
        requests.post(
            f"{API}/aurem/chat",
            json={"message": "test probe", "tenant_id": tenant},
            timeout=30,
        )
        time.sleep(1)
        # Verify DB write
        import sys
        sys.path.insert(0, "/app/backend")
        from pymongo import MongoClient
        env = open("/app/backend/.env").read()
        mongo_url = env.split("MONGO_URL=")[1].split("\n")[0].strip('"\'')
        db_name = env.split("DB_NAME=")[1].split("\n")[0].strip('"\'')
        c = MongoClient(mongo_url); db = c[db_name]
        count = db.ora_session_owners.count_documents({"tenant_id": tenant})
        assert count >= 1, "Ownership not recorded in ora_session_owners"


# ═══════════════════════════════════════════════════════════════════
# Part 2 — Stripe Test/Live Mode Toggle
# ═══════════════════════════════════════════════════════════════════

class TestStripeModeToggle:
    def _reload_config(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from services import channel_config as cc
        importlib.reload(cc)
        return cc

    def test_default_mode_returns_valid_status(self):
        cc = self._reload_config()
        status = cc.stripe_status()
        assert status["configured"] in (True, False)
        assert "mode" in status

    def test_stripe_mode_test_env(self, monkeypatch):
        monkeypatch.setenv("STRIPE_MODE", "test")
        cc = self._reload_config()
        status = cc.stripe_status()
        # If STRIPE_SECRET_KEY_TEST exists, mode should be 'test'
        if os.environ.get("STRIPE_SECRET_KEY_TEST"):
            assert status["mode"] == "test"
        assert status["requested_mode"] == "test"

    def test_stripe_mode_live_env(self, monkeypatch):
        monkeypatch.setenv("STRIPE_MODE", "live")
        cc = self._reload_config()
        status = cc.stripe_status()
        assert status["requested_mode"] == "live"

    def test_get_stripe_api_key_never_crashes(self):
        cc = self._reload_config()
        key = cc.get_stripe_api_key()
        # Either a string (key set) or None (not set) — but no crash
        assert key is None or isinstance(key, str)


# ═══════════════════════════════════════════════════════════════════
# Part 3 — Frontend UX: Saved Toast on CustomerWebsite
# ═══════════════════════════════════════════════════════════════════

class TestCustomerWebsiteToast:
    FILE = Path("/app/frontend/src/platform/customer/CustomerWebsite.jsx")

    def test_saved_toast_state_exists(self):
        src = self.FILE.read_text()
        assert "savedToast" in src, "savedToast state missing"
        assert 'data-testid="friend-scan-saved-toast"' in src
        assert "setSavedToast" in src

    def test_success_and_error_branches(self):
        src = self.FILE.read_text()
        assert "'success'" in src
        assert "'error'" in src
        # Toast auto-dismisses
        assert "setTimeout(() => setSavedToast(null)" in src


# ═══════════════════════════════════════════════════════════════════
# Part 4 — /dashboard Sidebar Core Pulse Link
# ═══════════════════════════════════════════════════════════════════

class TestCorePulseSidebarLink:
    DASH = Path("/app/frontend/src/platform/AuremDashboard.jsx")
    PULSE = Path("/app/frontend/src/platform/CorePulseDot.jsx")

    def test_core_pulse_section_added(self):
        src = self.DASH.read_text()
        assert "AUREM Core Pulse" in src
        assert "'pillars-map-link'" in src
        assert "'command-blocks-link'" in src
        assert "'vanguard-link'" in src

    def test_external_navigation_wired(self):
        src = self.DASH.read_text()
        assert "/admin/pillars-map" in src
        assert "externalTargets" in src

    def test_core_pulse_component_exists(self):
        assert self.PULSE.exists()
        src = self.PULSE.read_text()
        # Must poll the pillars-map overview endpoint
        assert "/api/admin/pillars-map/overview" in src
        assert 'data-testid="core-pulse-dot"' in src
        # Must use correct health states
        for state in ("healthy", "degraded", "down"):
            assert f'"{state}"' in src or f"'{state}'" in src

    def test_wired_items_include_core_pulse(self):
        src = self.DASH.read_text()
        assert "'pillars-map-link', 'command-blocks-link', 'vanguard-link'" in src
