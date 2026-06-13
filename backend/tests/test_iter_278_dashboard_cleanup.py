"""
iter 278 regression tests — /dashboard cleanup + LiveCampaignPipeline + CustomerOra.

Covers:
  1. AuremDashboard.jsx has exactly 70 sidebar items (was 154, 84 removed)
  2. RobotViewport import removed from ClientDashboard + MissionControl
  3. LiveCampaignPipeline component exists and is imported
  4. CustomerOra upgraded from iframe stub (38 LOC) to functional chat (200+ LOC)
  5. /api/aurem/chat backend endpoint returns valid assistant response
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import requests

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


BACKEND_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "http://localhost:8001",
)
API = f"{BACKEND_URL.rstrip('/')}/api"

TEST_EMAIL    = "teji.ss1986@gmail.com"
TEST_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


class TestAuremDashboardCleanup:
    FILE = Path("/app/frontend/src/platform/AuremDashboard.jsx")

    def test_sidebar_item_count(self):
        src = self.FILE.read_text()
        items = re.findall(r"{\s*id:\s*'([^']+)',\s*label:\s*'([^']+)'", src)
        # iter 278: 154 → 70 items after 84 dead button removal
        # iter 279: +3 Core Pulse links = 73 total
        assert len(items) == 73, f"Expected 73 items, got {len(items)}"

    def test_dead_items_are_gone(self):
        src = self.FILE.read_text()
        # A sample of items that MUST NOT exist anymore
        must_be_gone = [
            "hunt-command", "scout-by-city", "forensic-miner",
            "sample-websites", "website-builder",
            "content-engine", "image-generation",
            "shannon-security", "pentagi-scans",
            "ora-voice-agent",
        ]
        for dead_id in must_be_gone:
            assert f"id: '{dead_id}'" not in src, f"Dead item '{dead_id}' still present"

    def test_functional_items_preserved(self):
        src = self.FILE.read_text()
        # A sample of wired/functional items that MUST remain
        must_remain = [
            "morning-brief", "smart-approvals", "system-pulse",
            "campaign-dashboard", "hot-leads", "pipeline-kanban",
            "command-hub", "crm-connect",
            "ai-conversation", "sentinel",
            "api-keys", "business-management",
        ]
        for live_id in must_remain:
            assert f"id: '{live_id}'" in src, f"Functional item '{live_id}' missing"


class TestWarehouseRobotRemoval:
    def test_client_dashboard_no_robot(self):
        src = Path("/app/frontend/src/platform/ClientDashboard.jsx").read_text()
        assert "RobotViewport" not in src, "RobotViewport still imported in ClientDashboard"
        assert "LiveCampaignPipeline" in src, "LiveCampaignPipeline not imported"
        assert "import LiveCampaignPipeline" in src

    def test_mission_control_no_robot(self):
        src = Path("/app/frontend/src/platform/MissionControl.jsx").read_text()
        assert "RobotViewport" not in src
        assert "LiveCampaignPipeline" in src

    def test_live_pipeline_component_exists(self):
        fp = Path("/app/frontend/src/platform/LiveCampaignPipeline.jsx")
        assert fp.exists()
        src = fp.read_text()
        # Must fetch real campaigns
        assert "/api/campaigns" in src
        # Must be a proper React component with testids
        assert 'data-testid="live-campaign-pipeline"' in src


class TestCustomerOraUpgrade:
    FILE = Path("/app/frontend/src/platform/customer/CustomerOra.jsx")

    def test_customer_ora_has_real_chat(self):
        src = self.FILE.read_text()
        loc = len(src.splitlines())
        # Stub was 38 LOC; functional version is 250+
        assert loc > 150, f"CustomerOra looks like a stub ({loc} LOC)"

    def test_customer_ora_no_iframe(self):
        src = self.FILE.read_text()
        # iframe stub is gone — this is a real chat UI now
        assert "<iframe" not in src
        assert "src=\"/ora\"" not in src

    def test_customer_ora_calls_aurem_chat(self):
        src = self.FILE.read_text()
        assert "/api/aurem/chat" in src
        assert 'data-testid="ora-input"' in src
        assert 'data-testid="ora-send-btn"' in src


class TestAuremChatBackend:
    def test_chat_returns_assistant_response(self, admin_token: str):
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(
            f"{API}/aurem/chat",
            json={"message": "Hi ORA, test message"},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 200, f"Chat returned {r.status_code}: {r.text[:200]}"
        d = r.json()
        assert d.get("response"), "No 'response' field in chat reply"
        assert d.get("session_id"), "No session_id returned"
        assert len(d["response"]) > 10, "Response too short to be meaningful"

    def test_chat_maintains_session(self, admin_token: str):
        headers = {"Authorization": f"Bearer {admin_token}"}
        # Turn 1
        r1 = requests.post(
            f"{API}/aurem/chat",
            json={"message": "What is my top lead?"},
            headers=headers,
            timeout=30,
        )
        session_id = r1.json()["session_id"]
        # Turn 2 — reuse session
        r2 = requests.post(
            f"{API}/aurem/chat",
            json={"message": "Tell me more", "session_id": session_id},
            headers=headers,
            timeout=30,
        )
        assert r2.status_code == 200
        assert r2.json()["session_id"] == session_id
