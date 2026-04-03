"""
AUREM Redis Enterprise Scaling Tests
Tests for Phase 2.5 Redis features:
- Redis Hydrated Memory
- Semantic Cache
- Multi-tenant Rate Limiter
- WebSocket Hub
- Voice state sync
"""

import pytest
import requests
import os
import time
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRedisHealth:
    """Test Redis health endpoint - all services should be healthy"""
    
    def test_health_endpoint_returns_healthy(self):
        """Health endpoint should return healthy status with all services ok"""
        response = requests.get(f"{BASE_URL}/api/aurem-redis/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
        
        services = data["services"]
        assert services["redis_memory"] == "ok"
        assert services["semantic_cache"] == "ok"
        assert services["rate_limiter"] == "ok"
        assert services["websocket_hub"] == "ok"
        assert "websocket_connections" in services


class TestRateLimiter:
    """Test multi-tenant rate limiter with per-plan quotas"""
    
    def test_rate_limit_trial_plan(self):
        """Trial plan should have 10 messages/minute limit"""
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/rate-limit/test-trial-biz",
            params={"channel": "messages", "plan": "trial"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True
        assert data["limit"] == 10
        assert "remaining" in data
        assert "reset_in" in data
    
    def test_rate_limit_pro_plan(self):
        """Pro plan should have 200 messages/minute limit"""
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/rate-limit/test-pro-biz",
            params={"channel": "messages", "plan": "pro"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True
        assert data["limit"] == 200
        assert "remaining" in data
        assert "current" in data
    
    def test_rate_limit_enterprise_plan(self):
        """Enterprise plan should have 1000 messages/minute limit"""
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/rate-limit/test-enterprise-biz",
            params={"channel": "messages", "plan": "enterprise"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True
        assert data["limit"] == 1000
    
    def test_rate_limit_usage_endpoint(self):
        """Usage endpoint should return current usage across channels"""
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/rate-limit/test-usage-biz/usage"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "connected"
        assert "usage" in data
        assert "window_seconds" in data


class TestActivityLogging:
    """Test activity logging and retrieval"""
    
    def test_log_activity(self):
        """Should successfully log an activity"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-redis/activity/test-activity-biz",
            json={
                "activity_type": "agent",
                "description": "Scout Agent completed market scan",
                "metadata": {"brands_scanned": 5}
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
    
    def test_get_activities(self):
        """Should retrieve logged activities"""
        # First log an activity
        requests.post(
            f"{BASE_URL}/api/aurem-redis/activity/test-get-activities-biz",
            json={
                "activity_type": "flow",
                "description": "WhatsApp flow triggered",
                "metadata": {"messages_sent": 100}
            }
        )
        
        # Then retrieve activities
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/activities/test-get-activities-biz"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "activities" in data
        assert "count" in data
        assert isinstance(data["activities"], list)
    
    def test_activities_limit_parameter(self):
        """Should respect limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/activities/test-limit-biz",
            params={"limit": 5}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["activities"]) <= 5


class TestStateStorage:
    """Test UI state persistence across devices"""
    
    def test_set_state_boolean(self):
        """Should store boolean state value"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-redis/state/test-state-biz",
            json={"key": "voice_enabled", "value": True}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["key"] == "voice_enabled"
    
    def test_get_state(self):
        """Should retrieve stored state value"""
        # First set a state
        requests.post(
            f"{BASE_URL}/api/aurem-redis/state/test-get-state-biz",
            json={"key": "dark_mode", "value": True}
        )
        
        # Then retrieve it
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/state/test-get-state-biz/dark_mode"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["key"] == "dark_mode"
        assert data["value"] == True
    
    def test_state_persistence(self):
        """State should persist and be retrievable"""
        business_id = "test-persist-biz"
        
        # Set state
        requests.post(
            f"{BASE_URL}/api/aurem-redis/state/{business_id}",
            json={"key": "notifications", "value": False}
        )
        
        # Verify persistence
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/state/{business_id}/notifications"
        )
        assert response.status_code == 200
        assert response.json()["value"] == False
    
    def test_set_state_dict(self):
        """Should store dictionary state value"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-redis/state/test-dict-state-biz",
            json={"key": "preferences", "value": {"theme": "dark", "language": "en"}}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True


class TestSemanticCache:
    """Test semantic cache for AI responses"""
    
    def test_cache_stats(self):
        """Should return cache statistics"""
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/cache/test-cache-biz"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "connected"
        assert "cached_queries" in data
        assert "ttl_hours" in data
        assert data["ttl_hours"] == 24
    
    def test_cache_invalidate(self):
        """Should invalidate cache entries"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-redis/cache/test-invalidate-biz/invalidate"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["invalidated"] == "all"


class TestMemoryEndpoints:
    """Test Redis memory endpoints"""
    
    def test_memory_stats(self):
        """Should return memory statistics"""
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/memory/test-memory-biz"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "connected"
        assert data["business_id"] == "test-memory-biz"
        assert "active_conversations" in data
        assert "profile_cached" in data
    
    def test_conversation_context(self):
        """Should return conversation context (empty for new conversation)"""
        response = requests.get(
            f"{BASE_URL}/api/aurem-redis/context/test-context-biz/conv-123"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "messages" in data
        assert "profile" in data


class TestWebSocketEndpoint:
    """Test WebSocket endpoint exists"""
    
    def test_websocket_endpoint_exists(self):
        """WebSocket endpoint should be accessible (will fail upgrade but endpoint exists)"""
        # We can't fully test WebSocket with requests, but we can verify the endpoint exists
        # by checking the health endpoint reports websocket_hub as ok
        response = requests.get(f"{BASE_URL}/api/aurem-redis/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["services"]["websocket_hub"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
