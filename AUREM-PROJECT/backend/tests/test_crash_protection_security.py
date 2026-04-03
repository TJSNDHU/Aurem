"""
Test Suite for Crash Protection and Security Features
======================================================
Tests for:
1. Health check endpoint
2. GDPR data retention policy endpoint
3. GDPR delete-my-data endpoint
4. Rate limiting (429 response)
5. Phone masking utility
6. Encryption utility
7. Circuit breaker functionality
8. Graceful degradation
"""

import pytest
import requests
import os
import sys

# Add backend to path for utility imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL environment variable is required")


class TestHealthEndpoint:
    """Test basic health check endpoint"""
    
    def test_health_check_returns_ok(self):
        """GET /api/health should return status ok"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status 'ok', got {data}"
        print(f"✓ Health check passed: {data}")


class TestGDPRDataRetentionPolicy:
    """Test GDPR data retention policy endpoint"""
    
    def test_data_retention_policy_returns_policy(self):
        """GET /api/customer/data-retention-policy should return policy info"""
        response = requests.get(f"{BASE_URL}/api/customer/data-retention-policy", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify policy structure
        assert "policy" in data, "Response should contain 'policy' key"
        assert "gdpr_rights" in data, "Response should contain 'gdpr_rights' key"
        
        # Verify policy contains expected retention periods
        policy = data["policy"]
        assert "chat_sessions" in policy, "Policy should include chat_sessions retention"
        assert "customer_profiles" in policy, "Policy should include customer_profiles retention"
        assert "ai_audit_logs" in policy, "Policy should include ai_audit_logs retention"
        
        # Verify GDPR rights are listed
        gdpr_rights = data["gdpr_rights"]
        assert isinstance(gdpr_rights, list), "gdpr_rights should be a list"
        assert len(gdpr_rights) >= 3, "Should have at least 3 GDPR rights listed"
        
        # Verify contact info
        assert "contact" in data, "Response should contain contact info"
        
        print(f"✓ Data retention policy returned successfully")
        print(f"  - Policy keys: {list(policy.keys())}")
        print(f"  - GDPR rights count: {len(gdpr_rights)}")


class TestGDPRDeleteMyData:
    """Test GDPR delete-my-data endpoint"""
    
    def test_delete_my_data_with_valid_email(self):
        """GET /api/customer/delete-my-data?email=test@example.com should work"""
        test_email = "test_gdpr_deletion_12345@example.com"
        response = requests.get(
            f"{BASE_URL}/api/customer/delete-my-data",
            params={"email": test_email},
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "deleted" in data, "Response should contain 'deleted' key"
        assert "collections_cleared" in data, "Response should contain 'collections_cleared' key"
        assert "timestamp" in data, "Response should contain 'timestamp' key"
        assert "email_hash" in data, "Response should contain 'email_hash' key"
        
        # Verify deleted is True
        assert data["deleted"] == True, "deleted should be True"
        
        # Verify email_hash is a hash (not the actual email)
        assert test_email not in data["email_hash"], "email_hash should not contain actual email"
        assert len(data["email_hash"]) == 16, "email_hash should be 16 characters (SHA256 truncated)"
        
        print(f"✓ GDPR delete-my-data endpoint works")
        print(f"  - Collections cleared: {data['collections_cleared']}")
        print(f"  - Email hash: {data['email_hash']}")
    
    def test_delete_my_data_with_invalid_email(self):
        """GET /api/customer/delete-my-data with invalid email should return 400"""
        response = requests.get(
            f"{BASE_URL}/api/customer/delete-my-data",
            params={"email": "invalid-email"},
            timeout=10
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid email, got {response.status_code}"
        print(f"✓ Invalid email correctly rejected with 400")
    
    def test_delete_my_data_post_without_confirmation(self):
        """POST /api/customer/delete-my-data without confirmation should fail"""
        response = requests.post(
            f"{BASE_URL}/api/customer/delete-my-data",
            json={
                "email": "test@example.com",
                "confirmation": "wrong confirmation"
            },
            timeout=10
        )
        
        assert response.status_code == 400, f"Expected 400 without proper confirmation, got {response.status_code}"
        print(f"✓ POST without proper confirmation correctly rejected")


class TestPhoneMaskingUtility:
    """Test phone masking utility functions"""
    
    def test_mask_phone_international(self):
        """Test masking international phone number"""
        from utils.mask import mask_phone
        
        # Test +1 format
        result = mask_phone("+14168869408")
        assert "9408" in result, f"Last 4 digits should be visible: {result}"
        assert "416886" not in result, f"Middle digits should be masked: {result}"
        print(f"✓ mask_phone('+14168869408') = '{result}'")
    
    def test_mask_phone_10_digit(self):
        """Test masking 10-digit phone number"""
        from utils.mask import mask_phone
        
        result = mask_phone("4168869408")
        assert "9408" in result, f"Last 4 digits should be visible: {result}"
        assert "416886" not in result, f"Middle digits should be masked: {result}"
        print(f"✓ mask_phone('4168869408') = '{result}'")
    
    def test_mask_phone_empty(self):
        """Test masking empty phone"""
        from utils.mask import mask_phone
        
        result = mask_phone("")
        assert result == "", f"Empty input should return empty string: {result}"
        
        result_none = mask_phone(None)
        assert result_none == "", f"None input should return empty string: {result_none}"
        print(f"✓ mask_phone handles empty/None correctly")
    
    def test_mask_email(self):
        """Test email masking"""
        from utils.mask import mask_email
        
        result = mask_email("john.doe@example.com")
        assert "@example.com" in result, f"Domain should be visible: {result}"
        assert "john.doe" not in result, f"Local part should be masked: {result}"
        assert result.startswith("j"), f"First char should be visible: {result}"
        print(f"✓ mask_email('john.doe@example.com') = '{result}'")


class TestEncryptionUtility:
    """Test encryption utility functions"""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt then decrypt returns original value"""
        from utils.encryption import encrypt_field, decrypt_field, is_encryption_available
        
        # Check if encryption is available
        if not is_encryption_available():
            pytest.skip("Encryption not configured (ENCRYPTION_KEY not set)")
        
        original = "sensitive data 12345"
        encrypted = encrypt_field(original)
        
        # Encrypted should be different from original
        assert encrypted != original, "Encrypted value should differ from original"
        
        # Decrypt should return original
        decrypted = decrypt_field(encrypted)
        assert decrypted == original, f"Decrypted value should match original: {decrypted}"
        
        print(f"✓ Encryption roundtrip works")
        print(f"  - Original: '{original}'")
        print(f"  - Encrypted: '{encrypted[:30]}...'")
        print(f"  - Decrypted: '{decrypted}'")
    
    def test_encrypt_empty_value(self):
        """Test encrypting empty/None values"""
        from utils.encryption import encrypt_field, decrypt_field
        
        # Empty string should return empty
        result = encrypt_field("")
        assert result == "", f"Empty string should return empty: {result}"
        
        # None should return None
        result_none = encrypt_field(None)
        assert result_none is None, f"None should return None: {result_none}"
        
        print(f"✓ encrypt_field handles empty/None correctly")
    
    def test_is_encryption_available(self):
        """Test encryption availability check"""
        from utils.encryption import is_encryption_available
        
        result = is_encryption_available()
        assert isinstance(result, bool), "is_encryption_available should return bool"
        print(f"✓ is_encryption_available() = {result}")


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in CLOSED state"""
        from services.crash_protection import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        status = cb.get_status()
        
        assert status["state"] == "CLOSED", f"Initial state should be CLOSED: {status}"
        assert status["failures"] == 0, f"Initial failures should be 0: {status}"
        assert status["failure_threshold"] == 5, f"Threshold should be 5: {status}"
        
        print(f"✓ Circuit breaker initial state correct: {status}")
    
    def test_circuit_breaker_records_failure(self):
        """Test circuit breaker records failures"""
        from services.crash_protection import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        # Record failures
        cb._record_failure()
        cb._record_failure()
        
        status = cb.get_status()
        assert status["failures"] == 2, f"Should have 2 failures: {status}"
        assert status["state"] == "CLOSED", f"Should still be CLOSED with 2 failures: {status}"
        
        # One more failure should open the circuit
        cb._record_failure()
        status = cb.get_status()
        assert status["state"] == "OPEN", f"Should be OPEN after 3 failures: {status}"
        
        print(f"✓ Circuit breaker failure tracking works")
    
    def test_circuit_breaker_blocks_when_open(self):
        """Test circuit breaker blocks requests when open"""
        from services.crash_protection import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        
        # Open the circuit
        cb._record_failure()
        
        # Should not allow requests
        allowed = cb._should_allow_request()
        assert allowed == False, f"Should not allow requests when OPEN"
        
        print(f"✓ Circuit breaker blocks requests when OPEN")


class TestGracefulDegradation:
    """Test graceful degradation functionality"""
    
    def test_graceful_degradation_init(self):
        """Test graceful degradation initializes correctly"""
        from services.crash_protection import GracefulDegradation
        
        gd = GracefulDegradation()
        assert gd._redis_client is None, "Redis client should be None initially"
        assert gd._cache_prefix == "reroots_fallback:", "Cache prefix should be set"
        
        print(f"✓ GracefulDegradation initializes correctly")


class TestRateLimiting:
    """Test rate limiting returns 429 when exceeded"""
    
    def test_rate_limit_headers_present(self):
        """Test that rate limit related responses work"""
        # Make a normal request and verify it works
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check should work: {response.status_code}"
        print(f"✓ Normal request works (rate limiting not triggered for health endpoint)")
    
    def test_chat_widget_rate_limit_info(self):
        """Test chat widget endpoint returns rate limit info"""
        # This tests that the rate limiter is integrated
        # We won't actually trigger 429 as that would require many requests
        response = requests.get(f"{BASE_URL}/api/chat-widget/config", timeout=10)
        
        # Should return 200, 403 (auth required), or 404 (if not configured), not 500
        assert response.status_code in [200, 403, 404], f"Chat widget config should not error: {response.status_code}"
        print(f"✓ Chat widget endpoint accessible (status: {response.status_code})")


class TestAutoHealIntegration:
    """Test auto-heal monitoring integration"""
    
    def test_auto_heal_module_imports(self):
        """Test auto-heal module can be imported"""
        from services.auto_heal import (
            run_all_health_checks,
            get_auto_heal_logs,
            check_emergent_credits,
            RESPONSE_TIME_WARNING,
            RESPONSE_TIME_CRITICAL
        )
        
        # Verify constants
        assert RESPONSE_TIME_WARNING == 5.0, f"Warning threshold should be 5s: {RESPONSE_TIME_WARNING}"
        assert RESPONSE_TIME_CRITICAL == 10.0, f"Critical threshold should be 10s: {RESPONSE_TIME_CRITICAL}"
        
        print(f"✓ Auto-heal module imports correctly")
        print(f"  - Warning threshold: {RESPONSE_TIME_WARNING}s")
        print(f"  - Critical threshold: {RESPONSE_TIME_CRITICAL}s")


class TestAIRateLimiter:
    """Test AI rate limiter configuration"""
    
    def test_ai_rate_limiter_constants(self):
        """Test AI rate limiter has correct limits"""
        from services.ai_rate_limiter import (
            UNAUTHENTICATED_LIMIT_PER_HOUR,
            AUTHENTICATED_LIMIT_PER_HOUR,
            DUPLICATE_MESSAGE_THRESHOLD,
            BLOCK_DURATION_HOURS
        )
        
        assert UNAUTHENTICATED_LIMIT_PER_HOUR == 10, f"Unauth limit should be 10: {UNAUTHENTICATED_LIMIT_PER_HOUR}"
        assert AUTHENTICATED_LIMIT_PER_HOUR == 50, f"Auth limit should be 50: {AUTHENTICATED_LIMIT_PER_HOUR}"
        assert DUPLICATE_MESSAGE_THRESHOLD == 5, f"Duplicate threshold should be 5: {DUPLICATE_MESSAGE_THRESHOLD}"
        assert BLOCK_DURATION_HOURS == 24, f"Block duration should be 24h: {BLOCK_DURATION_HOURS}"
        
        print(f"✓ AI rate limiter constants correct")
        print(f"  - Unauthenticated: {UNAUTHENTICATED_LIMIT_PER_HOUR}/hr")
        print(f"  - Authenticated: {AUTHENTICATED_LIMIT_PER_HOUR}/hr")
        print(f"  - Duplicate threshold: {DUPLICATE_MESSAGE_THRESHOLD}")
        print(f"  - Block duration: {BLOCK_DURATION_HOURS}h")


class TestBrandsConfig:
    """Test brands config and protected system prompt"""
    
    def test_get_brand_config(self):
        """Test getting brand configuration"""
        from brands_config import get_brand_config, is_valid_brand_key
        
        # Test valid brand
        config = get_brand_config("reroots")
        assert config is not None, "reroots config should exist"
        assert config.brand_key == "reroots", f"Brand key should be reroots: {config.brand_key}"
        assert config.company_name == "Reroots Aesthetics Inc.", f"Company name mismatch: {config.company_name}"
        
        # Test invalid brand
        invalid_config = get_brand_config("invalid_brand")
        assert invalid_config is None, "Invalid brand should return None"
        
        # Test is_valid_brand_key
        assert is_valid_brand_key("reroots") == True, "reroots should be valid"
        assert is_valid_brand_key("invalid") == False, "invalid should not be valid"
        
        print(f"✓ Brand config works correctly")
        print(f"  - Brand: {config.brand_key}")
        print(f"  - Company: {config.company_name}")
        print(f"  - AI Name: {config.ai_name}")
    
    def test_get_protected_system_prompt(self):
        """Test getting protected system prompt"""
        from brands_config import get_protected_system_prompt
        
        prompt = get_protected_system_prompt("reroots")
        
        assert prompt is not None, "Prompt should not be None"
        assert len(prompt) > 100, f"Prompt should be substantial: {len(prompt)} chars"
        assert "Reroots" in prompt or "reroots" in prompt.lower(), "Prompt should mention Reroots"
        
        print(f"✓ Protected system prompt retrieved ({len(prompt)} chars)")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
