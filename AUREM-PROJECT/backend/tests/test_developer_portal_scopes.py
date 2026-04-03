"""
Developer Portal API Tests - Scope Bundles and Key Management
Tests for AUREM API key management with configurable scopes

Features tested:
- GET /api/aurem-keys/scope-bundles - Returns all 4 scope bundles
- POST /api/aurem-keys/create - Creates key with scopes
- GET /api/aurem-keys/list/{business_id} - Returns keys with scopes
- POST /api/aurem-keys/revoke - Revokes a key
- GET /api/aurem-keys/usage/{business_id} - Returns usage stats
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestScopeBundles:
    """Tests for scope bundles endpoint"""
    
    def test_get_scope_bundles_returns_all_four(self):
        """GET /api/aurem-keys/scope-bundles returns all 4 scope bundles"""
        response = requests.get(f"{BASE_URL}/api/aurem-keys/scope-bundles")
        assert response.status_code == 200
        
        data = response.json()
        assert "bundles" in data
        assert "all_scopes" in data
        
        # Verify all 4 bundles exist
        bundles = data["bundles"]
        assert "read_only" in bundles
        assert "standard" in bundles
        assert "full_access" in bundles
        assert "admin" in bundles
        
    def test_read_only_bundle_has_correct_scopes(self):
        """read_only bundle has only chat:read scope"""
        response = requests.get(f"{BASE_URL}/api/aurem-keys/scope-bundles")
        data = response.json()
        
        read_only = data["bundles"]["read_only"]
        assert read_only["scopes"] == ["chat:read"]
        assert "description" in read_only
        
    def test_standard_bundle_has_correct_scopes(self):
        """standard bundle has chat:read, chat:write, actions:email"""
        response = requests.get(f"{BASE_URL}/api/aurem-keys/scope-bundles")
        data = response.json()
        
        standard = data["bundles"]["standard"]
        assert "chat:read" in standard["scopes"]
        assert "chat:write" in standard["scopes"]
        assert "actions:email" in standard["scopes"]
        assert len(standard["scopes"]) == 3
        
    def test_full_access_bundle_has_all_action_scopes(self):
        """full_access bundle has all action scopes"""
        response = requests.get(f"{BASE_URL}/api/aurem-keys/scope-bundles")
        data = response.json()
        
        full_access = data["bundles"]["full_access"]
        expected_scopes = [
            "chat:read", "chat:write", 
            "actions:calendar", "actions:payments", 
            "actions:email", "actions:whatsapp"
        ]
        for scope in expected_scopes:
            assert scope in full_access["scopes"]
            
    def test_admin_bundle_has_admin_scopes(self):
        """admin bundle has admin:keys and admin:billing"""
        response = requests.get(f"{BASE_URL}/api/aurem-keys/scope-bundles")
        data = response.json()
        
        admin = data["bundles"]["admin"]
        assert "admin:keys" in admin["scopes"]
        assert "admin:billing" in admin["scopes"]
        assert len(admin["scopes"]) == 8  # All scopes


class TestKeyCreationWithScopes:
    """Tests for key creation with scope bundles"""
    
    @pytest.fixture
    def test_business_id(self):
        return f"TEST_dev_portal_{uuid.uuid4().hex[:8]}"
    
    def test_create_key_with_read_only_scope(self, test_business_id):
        """Create key with read_only scope bundle"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-keys/create",
            json={
                "business_id": test_business_id,
                "name": "TEST Read Only Key",
                "scope_bundle": "read_only",
                "rate_limit_daily": 500
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["scope_bundle"] == "read_only"
        assert data["scopes"] == ["chat:read"]
        assert data["rate_limit_daily"] == 500
        assert data["api_key"].startswith("sk_aurem_live_")
        
    def test_create_key_with_standard_scope(self, test_business_id):
        """Create key with standard scope bundle"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-keys/create",
            json={
                "business_id": test_business_id,
                "name": "TEST Standard Key",
                "scope_bundle": "standard"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["scope_bundle"] == "standard"
        assert "chat:read" in data["scopes"]
        assert "chat:write" in data["scopes"]
        assert "actions:email" in data["scopes"]
        
    def test_create_key_with_full_access_scope(self, test_business_id):
        """Create key with full_access scope bundle"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-keys/create",
            json={
                "business_id": test_business_id,
                "name": "TEST Full Access Key",
                "scope_bundle": "full_access"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["scope_bundle"] == "full_access"
        assert "actions:calendar" in data["scopes"]
        assert "actions:payments" in data["scopes"]
        assert "actions:whatsapp" in data["scopes"]
        
    def test_create_key_with_admin_scope(self, test_business_id):
        """Create key with admin scope bundle"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-keys/create",
            json={
                "business_id": test_business_id,
                "name": "TEST Admin Key",
                "scope_bundle": "admin"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["scope_bundle"] == "admin"
        assert "admin:keys" in data["scopes"]
        assert "admin:billing" in data["scopes"]
        
    def test_create_test_key_has_test_prefix(self, test_business_id):
        """Test keys have sk_aurem_test_ prefix"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-keys/create",
            json={
                "business_id": test_business_id,
                "name": "TEST Test Environment Key",
                "is_test": True,
                "scope_bundle": "standard"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["is_test"] == True
        assert data["api_key"].startswith("sk_aurem_test_")


class TestKeyListWithScopes:
    """Tests for listing keys with scope information"""
    
    @pytest.fixture
    def setup_keys(self):
        """Create test keys for listing"""
        business_id = f"TEST_list_{uuid.uuid4().hex[:8]}"
        
        # Create keys with different scopes
        requests.post(
            f"{BASE_URL}/api/aurem-keys/create",
            json={"business_id": business_id, "name": "TEST Key 1", "scope_bundle": "read_only"}
        )
        requests.post(
            f"{BASE_URL}/api/aurem-keys/create",
            json={"business_id": business_id, "name": "TEST Key 2", "scope_bundle": "admin"}
        )
        
        return business_id
    
    def test_list_keys_returns_scopes(self, setup_keys):
        """List keys includes scope information"""
        response = requests.get(f"{BASE_URL}/api/aurem-keys/list/{setup_keys}")
        assert response.status_code == 200
        
        data = response.json()
        assert "keys" in data
        assert "count" in data
        assert data["count"] >= 2
        
        # Verify scopes are included
        for key in data["keys"]:
            assert "scopes" in key
            assert "scope_bundle" in key
            assert isinstance(key["scopes"], list)
            
    def test_list_keys_shows_masked_prefix(self, setup_keys):
        """List keys shows masked key prefix"""
        response = requests.get(f"{BASE_URL}/api/aurem-keys/list/{setup_keys}")
        data = response.json()
        
        for key in data["keys"]:
            assert "key_prefix" in key
            assert key["key_prefix"].startswith("sk_aurem_")
            assert "..." in key["key_prefix"]
            # Verify full key hash is not exposed
            assert "key_hash" not in key


class TestKeyRevocation:
    """Tests for key revocation"""
    
    def test_revoke_key_success(self):
        """Revoke a key successfully"""
        business_id = f"TEST_revoke_{uuid.uuid4().hex[:8]}"
        
        # Create a key
        create_response = requests.post(
            f"{BASE_URL}/api/aurem-keys/create",
            json={"business_id": business_id, "name": "TEST Key to Revoke", "scope_bundle": "standard"}
        )
        key_id = create_response.json()["key_id"]
        
        # Revoke the key
        revoke_response = requests.post(
            f"{BASE_URL}/api/aurem-keys/revoke",
            json={"key_id": key_id, "business_id": business_id}
        )
        assert revoke_response.status_code == 200
        assert revoke_response.json()["success"] == True
        
        # Verify key is revoked in list
        list_response = requests.get(f"{BASE_URL}/api/aurem-keys/list/{business_id}")
        keys = list_response.json()["keys"]
        revoked_key = next((k for k in keys if k["key_id"] == key_id), None)
        assert revoked_key is not None
        assert revoked_key["status"] == "revoked"
        
    def test_revoke_nonexistent_key_returns_404(self):
        """Revoke non-existent key returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-keys/revoke",
            json={"key_id": "key_nonexistent123", "business_id": "test_business"}
        )
        assert response.status_code == 404


class TestUsageStats:
    """Tests for usage statistics endpoint"""
    
    def test_get_usage_stats(self):
        """Get usage stats for a business"""
        business_id = f"TEST_usage_{uuid.uuid4().hex[:8]}"
        
        response = requests.get(f"{BASE_URL}/api/aurem-keys/usage/{business_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "business_id" in data
        assert "billing_period" in data
        assert "total_requests" in data
        assert "total_tokens" in data
        assert "estimated_cost_usd" in data
        
    def test_usage_stats_with_billing_period(self):
        """Get usage stats with specific billing period"""
        business_id = f"TEST_usage_{uuid.uuid4().hex[:8]}"
        
        response = requests.get(
            f"{BASE_URL}/api/aurem-keys/usage/{business_id}",
            params={"billing_period": "2026-04"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["billing_period"] == "2026-04"


class TestHealthEndpoint:
    """Tests for health check endpoint"""
    
    def test_health_check(self):
        """Health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/aurem-keys/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "aurem-api-keys"
