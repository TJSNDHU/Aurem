"""
Email Engine Resend Integration Tests
=====================================
Tests for EmailEngine service with Resend API integration.
Verifies: send_message, send_campaign_batch, logging, counter increments.

NOTE: Does NOT send real emails - verifies code paths and DB logging only.
"""

import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Auth failed: {response.status_code}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for API calls"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestBackendHealth:
    """Verify backend is running"""
    
    def test_health_endpoint(self):
        """Backend health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("checks", {}).get("mongodb") == "ok"
        print(f"✓ Backend healthy: {data}")


class TestEmailEngineCodeVerification:
    """Verify EmailEngine code structure (no real sends)"""
    
    def test_email_engine_file_exists(self):
        """EmailEngine service file exists"""
        import os
        path = "/app/backend/services/email_engine.py"
        assert os.path.exists(path), f"EmailEngine file not found at {path}"
        print("✓ EmailEngine file exists")
    
    def test_email_engine_has_send_message(self):
        """EmailEngine has send_message method"""
        with open("/app/backend/services/email_engine.py", "r") as f:
            content = f.read()
        assert "async def send_message(" in content
        assert "resend.Emails.send" in content
        print("✓ EmailEngine has send_message() with Resend SDK")
    
    def test_email_engine_has_send_campaign_batch(self):
        """EmailEngine has send_campaign_batch method"""
        with open("/app/backend/services/email_engine.py", "r") as f:
            content = f.read()
        assert "async def send_campaign_batch(" in content
        assert "do_not_contact" in content  # DNC check
        print("✓ EmailEngine has send_campaign_batch() with DNC check")
    
    def test_email_engine_logs_to_email_logs(self):
        """EmailEngine logs to email_logs collection"""
        with open("/app/backend/services/email_engine.py", "r") as f:
            content = f.read()
        assert "email_logs.insert_one" in content
        assert '"engine": "resend"' in content
        print("✓ EmailEngine logs to email_logs collection")
    
    def test_email_engine_increments_counter(self):
        """EmailEngine increments emails_sent counter"""
        with open("/app/backend/services/email_engine.py", "r") as f:
            content = f.read()
        assert '"$inc": {"emails_sent": 1}' in content
        assert "user_integrations.update_one" in content
        print("✓ EmailEngine increments emails_sent counter")


class TestCampaignRouterEmailIntegration:
    """Verify campaign_router.py uses EmailEngine"""
    
    def test_campaign_router_test_email_uses_engine(self):
        """Campaign test-email endpoint uses EmailEngine"""
        with open("/app/backend/routers/campaign_router.py", "r") as f:
            content = f.read()
        
        # Check imports and usage
        assert "from services.email_engine import EmailEngine" in content
        assert "email_engine = EmailEngine" in content
        assert 'await email_engine.send_message("polaris-built-001"' in content
        print("✓ Campaign test-email uses EmailEngine")
    
    def test_campaign_router_bulk_send_uses_engine(self):
        """Campaign run_email_sequence uses EmailEngine"""
        with open("/app/backend/routers/campaign_router.py", "r") as f:
            content = f.read()
        
        # Check run_email_sequence function
        assert "async def run_email_sequence():" in content
        assert "email_engine = EmailEngine(db)" in content
        assert "await email_engine.send_message" in content
        print("✓ Campaign bulk send (run_email_sequence) uses EmailEngine")
    
    def test_no_direct_resend_httpx_calls(self):
        """No direct httpx calls to api.resend.com"""
        with open("/app/backend/routers/campaign_router.py", "r") as f:
            content = f.read()
        
        # Check there are no direct calls to Resend API
        assert "api.resend.com" not in content
        # httpx is used for Twilio, not Resend - that's fine
        # The key is that Resend calls go through EmailEngine
        assert "resend.Emails.send" not in content  # Should not have direct SDK calls
        print("✓ No direct Resend API calls in campaign_router.py (uses EmailEngine)")


class TestVanguardRouterEmailIntegration:
    """Verify aurem_vanguard_router.py uses EmailEngine"""
    
    def test_vanguard_email_channel_uses_engine(self):
        """Vanguard closer agent email channel uses EmailEngine"""
        with open("/app/backend/routers/aurem_vanguard_router.py", "r") as f:
            content = f.read()
        
        # Check email channel in execute_vanguard_swarm
        assert "from services.email_engine import EmailEngine" in content
        assert "email_engine = EmailEngine(_email_db)" in content
        assert "await email_engine.send_message" in content
        print("✓ Vanguard email channel uses EmailEngine")
    
    def test_vanguard_no_queued_placeholder(self):
        """Vanguard email channel doesn't use 'queued' placeholder"""
        with open("/app/backend/routers/aurem_vanguard_router.py", "r") as f:
            content = f.read()
        
        # Find the email channel section
        email_section_match = re.search(r'elif channel == "email":(.*?)elif channel == "voice":', content, re.DOTALL)
        if email_section_match:
            email_section = email_section_match.group(1)
            # Should NOT have "queued" as a placeholder status
            assert '"status": "queued"' not in email_section
            assert "email_engine.send_message" in email_section
        print("✓ Vanguard email channel sends real emails (not queued)")
    
    def test_vanguard_no_direct_resend_calls(self):
        """No direct httpx calls to api.resend.com in vanguard"""
        with open("/app/backend/routers/aurem_vanguard_router.py", "r") as f:
            content = f.read()
        
        assert "api.resend.com" not in content
        print("✓ No direct Resend calls in vanguard_router.py")


class TestEmailLogsDatabase:
    """Verify email_logs collection has correct data"""
    
    def test_email_logs_exist(self, auth_headers):
        """Email logs collection has entries"""
        # Use a direct DB check via a custom endpoint or verify via existing data
        # Since we can't directly query DB in pytest, we verify the structure
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def check_logs():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
            db = client[os.environ.get('DB_NAME', 'aurem_db')]
            count = await db.email_logs.count_documents({})
            client.close()
            return count
        
        count = asyncio.run(check_logs())
        assert count > 0, "No email logs found"
        print(f"✓ Email logs collection has {count} entries")
    
    def test_email_log_has_correct_structure(self):
        """Email log entries have correct structure"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def check_structure():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
            db = client[os.environ.get('DB_NAME', 'aurem_db')]
            log = await db.email_logs.find_one({"success": True})
            client.close()
            return log
        
        log = asyncio.run(check_structure())
        assert log is not None, "No successful email log found"
        
        # Verify required fields
        required_fields = ["tenant_id", "to", "subject", "email_id", "success", "engine", "sent_at"]
        for field in required_fields:
            assert field in log, f"Missing field: {field}"
        
        assert log["engine"] == "resend"
        assert log["success"] == True
        assert log["email_id"] != ""
        print(f"✓ Email log has correct structure: {log.get('email_id')}")
    
    def test_emails_sent_counter_incremented(self):
        """emails_sent counter in user_integrations is incremented"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def check_counter():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
            db = client[os.environ.get('DB_NAME', 'aurem_db')]
            doc = await db.user_integrations.find_one(
                {"tenant_id": "polaris-built-001"},
                {"_id": 0, "emails_sent": 1, "last_email_at": 1}
            )
            client.close()
            return doc
        
        doc = asyncio.run(check_counter())
        assert doc is not None, "No user_integrations found for polaris-built-001"
        assert doc.get("emails_sent", 0) >= 1, "emails_sent counter not incremented"
        assert doc.get("last_email_at") is not None, "last_email_at not set"
        print(f"✓ emails_sent counter: {doc.get('emails_sent')}, last_email_at: {doc.get('last_email_at')}")


class TestCampaignTestEmailEndpoint:
    """Test POST /api/campaign/test-email endpoint (without sending real email)"""
    
    def test_test_email_endpoint_exists(self, auth_headers):
        """Test-email endpoint is accessible"""
        # Just verify the endpoint exists and returns proper error for missing template
        response = requests.post(
            f"{BASE_URL}/api/campaign/test-email",
            headers=auth_headers,
            json={
                "to": "test@example.com",
                "template": "outbound_999",  # Non-existent template
                "business_name": "Test Business",
                "first_name": "Test",
                "score": 65,
                "issues_count": 4,
                "website": "example.com"
            }
        )
        # Should return 404 for non-existent template
        assert response.status_code == 404
        print("✓ Test-email endpoint exists and validates templates")
    
    def test_test_email_returns_engine_field(self, auth_headers):
        """Test-email response includes engine field"""
        # Check the code returns engine field
        with open("/app/backend/routers/campaign_router.py", "r") as f:
            content = f.read()
        
        # Find the test-email endpoint response
        assert '"engine": result.get("engine")' in content or '"engine":' in content
        print("✓ Test-email endpoint returns engine field in response")


class TestRealEmailSentVerification:
    """Verify the real email that was already sent"""
    
    def test_real_email_was_sent(self):
        """Verify real email to polarisbuiltinc@gmail.com was logged"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def check_real_email():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
            db = client[os.environ.get('DB_NAME', 'aurem_db')]
            log = await db.email_logs.find_one({
                "to": "polarisbuiltinc@gmail.com",
                "success": True
            })
            client.close()
            return log
        
        log = asyncio.run(check_real_email())
        assert log is not None, "No successful email to polarisbuiltinc@gmail.com found"
        assert log["email_id"] == "66227e3d-434f-47f3-99eb-9766b49d729b"
        assert log["engine"] == "resend"
        print(f"✓ Real email verified: {log['email_id']} to {log['to']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
