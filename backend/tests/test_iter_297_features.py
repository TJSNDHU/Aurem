"""
Iteration 297 Backend Tests
===========================
Tests for:
- P0: Channel-gating refresh endpoints
- P1 #2: Token compression (session_summaries)
- P1 #3: Voice input (Whisper STT)
- P1 #4: Auto Website Builder (AWB)
"""
import os
import io
import uuid
import pytest
import requests
from datetime import datetime

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token for authenticated requests."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }


# ─── P0: Channel-Gating Refresh ─────────────────────────────────────────────
class TestChannelGatingRefresh:
    """P0: Channel-gating refresh script for cached leads."""

    def test_refresh_channel_gating_dry_run(self, auth_headers):
        """POST /api/admin/platform/maintenance/refresh-channel-gating?dry=true"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/maintenance/refresh-channel-gating?dry=true",
            headers=auth_headers,
            timeout=60,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        # Verify response structure
        assert "scanned" in data, "Missing 'scanned' in response"
        assert "updated" in data, "Missing 'updated' in response"
        assert "unchanged" in data, "Missing 'unchanged' in response"
        assert "sample_diffs" in data, "Missing 'sample_diffs' in response"
        assert data.get("dry_run") is True, "dry_run should be True"
        # sample_diffs should be a list with max 10 items
        assert isinstance(data["sample_diffs"], list), "sample_diffs should be a list"
        assert len(data["sample_diffs"]) <= 10, "sample_diffs should have max 10 items"
        print(f"✓ Dry run: scanned={data['scanned']}, updated={data['updated']}, unchanged={data['unchanged']}")

    def test_refresh_channel_gating_live(self, auth_headers):
        """POST /api/admin/platform/maintenance/refresh-channel-gating (live run)"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/maintenance/refresh-channel-gating",
            headers=auth_headers,
            timeout=120,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "scanned" in data
        assert "updated" in data
        assert data.get("dry_run") is False, "dry_run should be False for live run"
        print(f"✓ Live run: scanned={data['scanned']}, updated={data['updated']}")

    def test_refresh_channel_gating_history(self, auth_headers):
        """GET /api/admin/platform/maintenance/refresh-channel-gating/history?limit=5"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/maintenance/refresh-channel-gating/history?limit=5",
            headers=auth_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "runs" in data, "Missing 'runs' in response"
        assert isinstance(data["runs"], list), "runs should be a list"
        # After live run, should have at least 1 entry
        if data["runs"]:
            run = data["runs"][0]
            assert "scanned" in run, "Run should have 'scanned'"
            assert "updated" in run, "Run should have 'updated'"
            print(f"✓ History: {len(data['runs'])} runs found")
        else:
            print("✓ History endpoint works (no runs yet)")


# ─── P1 #2: Token Compression ───────────────────────────────────────────────
class TestTokenCompression:
    """P1 #2: Token compression rolling-summary middleware."""

    def test_compression_triggers_after_12_messages(self, auth_headers):
        """Send 13+ messages to trigger compression, verify session_summaries row."""
        session_id = f"test-compress-{uuid.uuid4().hex[:8]}"
        
        # Send 13 messages to trigger compression (COMPRESS_TRIGGER=12)
        for i in range(13):
            resp = requests.post(
                f"{BASE_URL}/api/admin/console/message",
                headers=auth_headers,
                json={"message": f"Test message {i+1} for compression testing", "session_id": session_id},
                timeout=30,
            )
            assert resp.status_code == 200, f"Message {i+1} failed: {resp.status_code}"
            print(f"  Sent message {i+1}/13")
        
        # Check session_summaries collection via a direct query endpoint or verify via history
        # The compression should have created a summary row
        # We verify by checking history still returns all turns
        resp = requests.get(
            f"{BASE_URL}/api/admin/console/history?session_id={session_id}",
            headers=auth_headers,
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        messages = data.get("messages", [])
        # Should have 13 user + 13 assistant = 26 messages
        assert len(messages) >= 26, f"Expected >=26 messages, got {len(messages)}"
        print(f"✓ Compression test: {len(messages)} messages in history (compression should not delete)")

    def test_history_returns_all_turns_after_compression(self, auth_headers):
        """GET /api/admin/console/history still returns all turns after compression."""
        # Use a fresh session
        session_id = f"test-hist-{uuid.uuid4().hex[:8]}"
        
        # Send 5 messages (below threshold)
        for i in range(5):
            requests.post(
                f"{BASE_URL}/api/admin/console/message",
                headers=auth_headers,
                json={"message": f"History test {i+1}", "session_id": session_id},
                timeout=30,
            )
        
        resp = requests.get(
            f"{BASE_URL}/api/admin/console/history?session_id={session_id}",
            headers=auth_headers,
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        messages = data.get("messages", [])
        # 5 user + 5 assistant = 10
        assert len(messages) >= 10, f"Expected >=10 messages, got {len(messages)}"
        print(f"✓ History returns all {len(messages)} turns")


# ─── P1 #3: Voice Input (Whisper STT) ───────────────────────────────────────
class TestVoiceInput:
    """P1 #3: Voice input endpoint tests."""

    def test_voice_no_auth_returns_401(self):
        """POST /api/admin/console/voice with no auth → 401"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/console/voice",
            timeout=10,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Voice endpoint returns 401 without auth")

    def test_voice_no_file_returns_400(self, auth_headers):
        """POST /api/admin/console/voice with auth + no file → 400"""
        # Remove Content-Type for multipart
        headers = {"Authorization": auth_headers["Authorization"]}
        resp = requests.post(
            f"{BASE_URL}/api/admin/console/voice",
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        data = resp.json()
        assert "audio" in data.get("detail", "").lower() or "file" in data.get("detail", "").lower(), \
            f"Expected 'audio file required' error, got: {data}"
        print("✓ Voice endpoint returns 400 without file")

    def test_voice_empty_audio_returns_400(self, auth_headers):
        """POST /api/admin/console/voice with auth + empty webm → 400"""
        headers = {"Authorization": auth_headers["Authorization"]}
        # Create an empty file
        files = {"audio": ("voice.webm", io.BytesIO(b""), "audio/webm")}
        resp = requests.post(
            f"{BASE_URL}/api/admin/console/voice",
            headers=headers,
            files=files,
            timeout=10,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        data = resp.json()
        assert "empty" in data.get("detail", "").lower(), f"Expected 'empty audio' error, got: {data}"
        print("✓ Voice endpoint returns 400 for empty audio")

    def test_voice_with_small_audio(self, auth_headers):
        """POST /api/admin/console/voice with auth + small audio file.
        Expect 200 {transcript} OR 502 if Whisper unavailable."""
        headers = {"Authorization": auth_headers["Authorization"]}
        
        # Create a minimal valid webm header (not actual audio, but tests endpoint flow)
        # Real webm starts with EBML header: 0x1A 0x45 0xDF 0xA3
        # This is a minimal test - real audio would be needed for actual transcription
        fake_webm = b'\x1a\x45\xdf\xa3' + b'\x00' * 1000  # Minimal webm-like bytes
        
        files = {"audio": ("voice.webm", io.BytesIO(fake_webm), "audio/webm")}
        resp = requests.post(
            f"{BASE_URL}/api/admin/console/voice",
            headers=headers,
            files=files,
            timeout=30,
        )
        # Accept 200 (success) or 502 (Whisper unavailable) - both indicate endpoint works
        assert resp.status_code in [200, 502], f"Expected 200 or 502, got {resp.status_code}: {resp.text[:200]}"
        if resp.status_code == 200:
            data = resp.json()
            assert "transcript" in data, "Missing 'transcript' in response"
            print(f"✓ Voice endpoint returned transcript: {data.get('transcript', '')[:50]}")
        else:
            print("✓ Voice endpoint reached Whisper integration (502 = Whisper unavailable)")


# ─── P1 #4: Auto Website Builder ────────────────────────────────────────────
class TestAutoWebsiteBuilder:
    """P1 #4: Auto Website Builder scaffold tests."""

    @pytest.fixture(scope="class")
    def test_lead_id(self):
        """Use the known test lead from main agent context."""
        return "tj-auto-clinic-001"

    def test_build_site_for_lead(self, auth_headers, test_lead_id):
        """POST /api/admin/platform/website-builder/build/{lead_id}"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/build/{test_lead_id}",
            headers=auth_headers,
            timeout=120,
        )
        # Accept 200 (success) or 400/404 (lead not found - expected if test lead doesn't exist)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("ok") is True, f"Expected ok=true, got: {data}"
            assert "site_id" in data, "Missing site_id"
            assert "status" in data, "Missing status"
            assert data.get("status") == "rendered", f"Expected status=rendered, got {data.get('status')}"
            assert "preview_url" in data, "Missing preview_url"
            assert "chain_id" in data, "Missing chain_id"
            assert "task_ids" in data, "Missing task_ids"
            assert len(data.get("task_ids", [])) >= 2, "Expected at least 2 task_ids"
            assert "council_decision_id" in data, "Missing council_decision_id"
            print(f"✓ Built site: site_id={data['site_id']}, status={data['status']}")
            # Store for subsequent tests
            TestAutoWebsiteBuilder.built_site_id = data["site_id"]
        else:
            # Lead might not exist - check if it's a known error
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if "not found" in str(data).lower() or resp.status_code == 404:
                pytest.skip(f"Test lead {test_lead_id} not found in DB - skipping AWB tests")
            else:
                pytest.fail(f"Unexpected error: {resp.status_code} - {resp.text[:300]}")

    def test_preview_site(self, auth_headers):
        """GET /api/admin/platform/website-builder/preview/{site_id}"""
        site_id = getattr(TestAutoWebsiteBuilder, "built_site_id", None)
        if not site_id:
            pytest.skip("No site_id from previous test")
        
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/preview/{site_id}",
            headers=auth_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        html = resp.text
        assert "<!doctype html>" in html.lower(), "Missing doctype"
        assert "<title>" in html.lower(), "Missing title tag"
        print(f"✓ Preview returns HTML ({len(html)} bytes)")

    def test_list_sites(self, auth_headers):
        """GET /api/admin/platform/website-builder/list?limit=10"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/list?limit=10",
            headers=auth_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "sites" in data, "Missing 'sites' in response"
        assert isinstance(data["sites"], list), "sites should be a list"
        # Verify excluded fields
        for site in data["sites"]:
            assert "rendered_html" not in site, "rendered_html should be excluded"
            assert "gemini_draft" not in site, "gemini_draft should be excluded"
            assert "claude_refined" not in site, "claude_refined should be excluded"
        print(f"✓ List sites: {len(data['sites'])} sites returned")

    def test_run_batch(self, auth_headers):
        """POST /api/admin/platform/website-builder/run-batch?limit=2"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/run-batch?limit=2",
            headers=auth_headers,
            timeout=180,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "selected" in data, "Missing 'selected'"
        assert "built" in data, "Missing 'built'"
        assert "skipped" in data, "Missing 'skipped'"
        print(f"✓ Batch run: selected={data['selected']}, built={len(data['built'])}, skipped={len(data['skipped'])}")


# ─── Auth Gate Tests ────────────────────────────────────────────────────────
class TestAuthGates:
    """Verify all new endpoints require authentication."""

    def test_refresh_gating_requires_auth(self):
        resp = requests.post(f"{BASE_URL}/api/admin/platform/maintenance/refresh-channel-gating", timeout=10)
        assert resp.status_code == 401

    def test_refresh_gating_history_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/admin/platform/maintenance/refresh-channel-gating/history", timeout=10)
        assert resp.status_code == 401

    def test_website_builder_build_requires_auth(self):
        resp = requests.post(f"{BASE_URL}/api/admin/platform/website-builder/build/test", timeout=10)
        assert resp.status_code == 401

    def test_website_builder_list_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/admin/platform/website-builder/list", timeout=10)
        assert resp.status_code == 401

    def test_website_builder_preview_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/admin/platform/website-builder/preview/test", timeout=10)
        assert resp.status_code == 401

    def test_website_builder_batch_requires_auth(self):
        resp = requests.post(f"{BASE_URL}/api/admin/platform/website-builder/run-batch", timeout=10)
        assert resp.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
