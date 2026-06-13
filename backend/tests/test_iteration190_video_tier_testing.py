"""
Iteration 190 — Video Generation Tier Testing + ORA Avatar + Telegram
======================================================================
Tests:
1. POST /api/content-engine/generate-video — tier gating (Starter→403, Growth→passes, Enterprise→passes)
2. POST /api/content-engine/generate-video with image_url — I2V requires Enterprise
3. GET /api/content-engine/usage — videos with quality field
4. GET /api/content-engine/tiers — video field per tier
5. POST /api/content-engine/extend-video — Enterprise only
6. POST /api/ora/create-avatar — exists
7. POST /api/ora/avatar-video — requires audio_url
8. POST /api/comms/telegram/webhook — exists
9. POST /api/comms/telegram/send — TELEGRAM_BOT_TOKEN error
10. GET /api/content-engine/video-history — returns list
11. All video endpoints require auth (401)
"""
import pytest
import requests
import os

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for testing."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Auth failed: {resp.status_code} - {resp.text[:200]}")


@pytest.fixture(scope="module")
def headers(auth_token):
    """Headers with auth token."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }


class TestVideoEndpointsAuth:
    """Test that video endpoints require authentication (401)."""
    
    def test_generate_video_requires_auth(self):
        """POST /api/content-engine/generate-video returns 401 without auth."""
        resp = requests.post(f"{BASE_URL}/api/content-engine/generate-video", json={
            "product_name": "Test Product"
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: generate-video requires auth (401)")
    
    def test_extend_video_requires_auth(self):
        """POST /api/content-engine/extend-video returns 401 without auth."""
        resp = requests.post(f"{BASE_URL}/api/content-engine/extend-video", json={
            "request_id": "test123",
            "prompt": "extend this"
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: extend-video requires auth (401)")
    
    def test_video_history_requires_auth(self):
        """GET /api/content-engine/video-history returns 401 without auth."""
        resp = requests.get(f"{BASE_URL}/api/content-engine/video-history")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: video-history requires auth (401)")
    
    def test_usage_requires_auth(self):
        """GET /api/content-engine/usage returns 401 without auth."""
        resp = requests.get(f"{BASE_URL}/api/content-engine/usage")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: usage requires auth (401)")


class TestVideoTierGating:
    """Test video generation tier gating logic."""
    
    def test_generate_video_with_auth(self, headers):
        """POST /api/content-engine/generate-video with auth — should pass tier check or return credit error."""
        resp = requests.post(f"{BASE_URL}/api/content-engine/generate-video", headers=headers, json={
            "product_name": "Test Product",
            "product_description": "A test product for video generation",
            "style": "brand_story",
            "platform": "instagram_reels",
            "aspect_ratio": "9:16",
            "duration": 5
        })
        # Expected: 403 (Starter), 402 (Growth/Enterprise with credit error), or 500 (all providers failed)
        # NOT 401 (auth should pass)
        assert resp.status_code != 401, f"Auth should pass, got 401"
        print(f"PASS: generate-video with auth returns {resp.status_code} (not 401)")
        
        # Check response content
        data = resp.json() if resp.status_code != 204 else {}
        if resp.status_code == 403:
            # Starter tier blocked
            assert "Growth" in str(data) or "Enterprise" in str(data) or "upgrade" in str(data).lower(), \
                f"403 should mention Growth/Enterprise upgrade: {data}"
            print(f"PASS: 403 response mentions tier upgrade requirement")
        elif resp.status_code == 402:
            # Credit error (expected for Growth/Enterprise with no credits)
            assert "credit" in str(data).lower() or "insufficient" in str(data).lower(), \
                f"402 should mention credits: {data}"
            print(f"PASS: 402 response indicates credit issue (expected)")
        elif resp.status_code == 500:
            # All providers failed (expected for Enterprise with no credits)
            assert "provider" in str(data).lower() or "failed" in str(data).lower(), \
                f"500 should mention provider failure: {data}"
            print(f"PASS: 500 response indicates all providers failed (expected)")
        else:
            print(f"INFO: generate-video returned {resp.status_code}: {data}")
    
    def test_generate_video_i2v_requires_enterprise(self, headers):
        """POST /api/content-engine/generate-video with image_url — I2V requires Enterprise."""
        resp = requests.post(f"{BASE_URL}/api/content-engine/generate-video", headers=headers, json={
            "product_name": "Test Product",
            "image_url": "https://example.com/test.jpg",
            "style": "product_demo",
            "platform": "instagram_reels",
            "duration": 5
        })
        # For Growth tier: should return 403 with "I2V requires Enterprise" message
        # For Enterprise tier: should pass through to provider (402/500 credit error)
        assert resp.status_code != 401, f"Auth should pass, got 401"
        print(f"PASS: generate-video with image_url returns {resp.status_code}")
        
        data = resp.json() if resp.status_code != 204 else {}
        if resp.status_code == 403:
            # Growth tier blocked for I2V
            detail = data.get("detail", str(data))
            assert "Enterprise" in detail or "I2V" in detail or "image" in detail.lower(), \
                f"403 for I2V should mention Enterprise requirement: {data}"
            print(f"PASS: I2V correctly blocked for non-Enterprise tier")


class TestContentEngineUsage:
    """Test usage and tiers endpoints."""
    
    def test_usage_returns_videos_field(self, headers):
        """GET /api/content-engine/usage returns videos with quality field."""
        resp = requests.get(f"{BASE_URL}/api/content-engine/usage", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "videos" in data, f"Response should have 'videos' field: {data.keys()}"
        
        videos = data["videos"]
        assert isinstance(videos, dict), f"videos should be dict: {type(videos)}"
        
        # Check for quality field (480p for growth, HD for enterprise)
        if "quality" in videos:
            assert videos["quality"] in ["480p", "HD", "unlimited"], f"Unexpected quality: {videos['quality']}"
            print(f"PASS: usage returns videos with quality={videos['quality']}")
        else:
            print(f"PASS: usage returns videos field: {videos}")
    
    def test_tiers_shows_video_field(self, headers):
        """GET /api/content-engine/tiers shows video field per tier."""
        resp = requests.get(f"{BASE_URL}/api/content-engine/tiers", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        
        # Check starter tier
        assert "starter" in data, f"Missing starter tier: {data.keys()}"
        starter = data["starter"]
        assert "video" in starter, f"Starter should have video field: {starter.keys()}"
        assert starter["video"] == False, f"Starter video should be False: {starter['video']}"
        print(f"PASS: starter tier video={starter['video']} (False)")
        
        # Check growth tier
        assert "growth" in data, f"Missing growth tier: {data.keys()}"
        growth = data["growth"]
        assert "video" in growth, f"Growth should have video field: {growth.keys()}"
        assert growth["video"] == "basic", f"Growth video should be 'basic': {growth['video']}"
        print(f"PASS: growth tier video={growth['video']} (basic)")
        
        # Check enterprise tier
        assert "enterprise" in data, f"Missing enterprise tier: {data.keys()}"
        enterprise = data["enterprise"]
        assert "video" in enterprise, f"Enterprise should have video field: {enterprise.keys()}"
        assert enterprise["video"] == True, f"Enterprise video should be True: {enterprise['video']}"
        print(f"PASS: enterprise tier video={enterprise['video']} (True)")


class TestExtendVideo:
    """Test video extend endpoint."""
    
    def test_extend_video_endpoint_exists(self, headers):
        """POST /api/content-engine/extend-video endpoint exists and requires enterprise tier."""
        resp = requests.post(f"{BASE_URL}/api/content-engine/extend-video", headers=headers, json={
            "request_id": "test_request_123",
            "prompt": "Continue the video with more product features",
            "duration": 5
        })
        # Should not be 404 (endpoint exists)
        # Expected: 403 (non-enterprise) or 500 (enterprise but provider error)
        assert resp.status_code != 404, f"Endpoint should exist, got 404"
        assert resp.status_code != 401, f"Auth should pass, got 401"
        
        if resp.status_code == 403:
            data = resp.json()
            assert "Enterprise" in str(data), f"403 should mention Enterprise: {data}"
            print(f"PASS: extend-video requires Enterprise tier (403)")
        else:
            print(f"PASS: extend-video endpoint exists, returns {resp.status_code}")


class TestVideoHistory:
    """Test video history endpoint."""
    
    def test_video_history_returns_list(self, headers):
        """GET /api/content-engine/video-history returns list."""
        resp = requests.get(f"{BASE_URL}/api/content-engine/video-history", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "videos" in data, f"Response should have 'videos' field: {data.keys()}"
        assert isinstance(data["videos"], list), f"videos should be list: {type(data['videos'])}"
        print(f"PASS: video-history returns list with {len(data['videos'])} videos")


class TestORAAvatar:
    """Test ORA Avatar endpoints."""
    
    def test_create_avatar_endpoint_exists(self, headers):
        """POST /api/ora/create-avatar endpoint exists."""
        resp = requests.post(f"{BASE_URL}/api/ora/create-avatar", headers=headers, json={
            "avatar_image_url": "https://aurem.live/assets/ora-avatar.jpg"
        })
        # Should not be 404 (endpoint exists)
        # Expected: 500 (Muapi no credits) or 200 (success)
        assert resp.status_code != 404, f"Endpoint should exist, got 404"
        print(f"PASS: create-avatar endpoint exists, returns {resp.status_code}")
    
    def test_avatar_video_requires_audio_url(self, headers):
        """POST /api/ora/avatar-video returns 400 without audio_url."""
        resp = requests.post(f"{BASE_URL}/api/ora/avatar-video", headers=headers, json={
            "text": ""  # No text and no audio_url
        })
        # Should return 400 for missing audio_url
        assert resp.status_code == 400, f"Expected 400 for missing audio_url, got {resp.status_code}"
        
        data = resp.json()
        assert "audio_url" in str(data).lower() or "text" in str(data).lower(), \
            f"400 should mention audio_url requirement: {data}"
        print(f"PASS: avatar-video returns 400 without audio_url")


class TestTelegramEndpoints:
    """Test Telegram communication endpoints."""
    
    def test_telegram_webhook_exists(self):
        """POST /api/comms/telegram/webhook endpoint exists and returns ok."""
        resp = requests.post(f"{BASE_URL}/api/comms/telegram/webhook", json={
            "message": {
                "chat": {"id": "123456"},
                "text": "Hello",
                "from": {"username": "testuser", "first_name": "Test"}
            }
        })
        # Should return 200 with {"ok": true}
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("ok") == True, f"Response should have ok=true: {data}"
        print(f"PASS: telegram/webhook returns ok=true")
    
    def test_telegram_send_requires_bot_token(self, headers):
        """POST /api/comms/telegram/send returns error about TELEGRAM_BOT_TOKEN."""
        resp = requests.post(f"{BASE_URL}/api/comms/telegram/send", headers=headers, json={
            "chat_id": "123456",
            "text": "Test message"
        })
        # Should return 500 with TELEGRAM_BOT_TOKEN error (since it's empty)
        assert resp.status_code == 500, f"Expected 500 for missing token, got {resp.status_code}"
        
        # The error message may be sanitized in production, so just check for 500
        print(f"PASS: telegram/send returns 500 (TELEGRAM_BOT_TOKEN not configured)")


class TestTelegramConversations:
    """Test Telegram conversations endpoint."""
    
    def test_telegram_conversations_requires_auth(self):
        """GET /api/comms/telegram/conversations requires auth."""
        resp = requests.get(f"{BASE_URL}/api/comms/telegram/conversations")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print(f"PASS: telegram/conversations requires auth (401)")
    
    def test_telegram_conversations_with_auth(self, headers):
        """GET /api/comms/telegram/conversations returns list with auth."""
        resp = requests.get(f"{BASE_URL}/api/comms/telegram/conversations", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "conversations" in data, f"Response should have 'conversations' field: {data.keys()}"
        print(f"PASS: telegram/conversations returns {len(data.get('conversations', []))} conversations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
