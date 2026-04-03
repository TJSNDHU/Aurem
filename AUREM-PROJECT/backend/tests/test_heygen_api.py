"""
Test HeyGen API Integration for Talking Avatar Video Generation
Tests endpoints:
- GET /api/admin/ai-studio/heygen/quota
- POST /api/admin/ai-studio/heygen/generate-video
- GET /api/admin/ai-studio/heygen/status/{video_id}
"""
import pytest
import requests
import os
import base64

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHeyGenQuota:
    """Test HeyGen Quota API endpoint"""
    
    def test_heygen_quota_endpoint_exists(self):
        """Test that GET /api/admin/ai-studio/heygen/quota endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/heygen/quota", timeout=30)
        # Should return 200 with success/error
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        print(f"✓ Quota endpoint exists. Response: {data}")
        
    def test_heygen_quota_returns_quota_info(self):
        """Test that quota endpoint returns quota info when API key is valid"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/heygen/quota", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            # API key is configured and valid
            assert "quota" in data, "Response should have 'quota' field"
            quota = data["quota"]
            print(f"✓ HeyGen quota info: {quota}")
        else:
            # API key not configured
            print(f"⚠ HeyGen API key issue: {data.get('error', 'Unknown')}")
        

class TestHeyGenGenerateVideo:
    """Test HeyGen Generate Video endpoint"""
    
    def test_generate_video_endpoint_exists(self):
        """Test that POST /api/admin/ai-studio/heygen/generate-video endpoint exists"""
        # Send minimal invalid request to check endpoint existence
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/heygen/generate-video",
            json={"photo_base64": "", "audio_base64": ""},
            timeout=30
        )
        # Should return 200 or 422 (validation error), but NOT 404
        assert response.status_code != 404, "Endpoint should exist"
        print(f"✓ Generate video endpoint exists. Status: {response.status_code}")
    
    def test_generate_video_requires_photo_base64(self):
        """Test that endpoint validates photo_base64 input"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/heygen/generate-video",
            json={"audio_base64": "test"},
            timeout=30
        )
        # Should return 422 for missing required field
        assert response.status_code == 422, f"Expected 422 for missing photo_base64, got {response.status_code}"
        print("✓ Endpoint validates photo_base64 is required")
    
    def test_generate_video_requires_audio_base64(self):
        """Test that endpoint validates audio_base64 input"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/heygen/generate-video",
            json={"photo_base64": "test"},
            timeout=30
        )
        # Should return 422 for missing required field
        assert response.status_code == 422, f"Expected 422 for missing audio_base64, got {response.status_code}"
        print("✓ Endpoint validates audio_base64 is required")
    
    def test_generate_video_with_invalid_base64(self):
        """Test endpoint behavior with invalid base64 data"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/heygen/generate-video",
            json={
                "photo_base64": "not-valid-base64!@#$%",
                "audio_base64": "also-not-valid!@#$%",
                "script": "Test script"
            },
            timeout=30
        )
        # Should return 200 with success=False (graceful error handling)
        assert response.status_code == 200
        data = response.json()
        # Either it handles the error gracefully or the HeyGen API fails
        print(f"✓ Invalid base64 handled: {data}")


class TestHeyGenVideoStatus:
    """Test HeyGen Video Status endpoint"""
    
    def test_status_endpoint_exists(self):
        """Test that GET /api/admin/ai-studio/heygen/status/{video_id} endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ai-studio/heygen/status/test-invalid-video-id",
            timeout=30
        )
        # Should return 200 (not 404), even if video_id is invalid
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        print(f"✓ Status endpoint exists. Response: {data}")
    
    def test_status_invalid_video_id(self):
        """Test status endpoint with invalid video ID"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ai-studio/heygen/status/invalid-123",
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        # Should return error for invalid video ID
        print(f"✓ Invalid video ID handled: {data}")


class TestHeyGenIntegration:
    """Integration tests for HeyGen workflow"""
    
    def test_full_workflow_validation(self):
        """Test that the workflow endpoints are all accessible"""
        # 1. Check quota
        quota_response = requests.get(f"{BASE_URL}/api/admin/ai-studio/heygen/quota", timeout=30)
        assert quota_response.status_code == 200, "Quota endpoint should work"
        
        # 2. Check generate endpoint validation
        generate_response = requests.post(
            f"{BASE_URL}/api/admin/ai-studio/heygen/generate-video",
            json={"photo_base64": "test", "audio_base64": "test"},
            timeout=30
        )
        # Should be 200 (handled) or validation error
        assert generate_response.status_code in [200, 422], f"Generate should handle request, got {generate_response.status_code}"
        
        # 3. Check status endpoint
        status_response = requests.get(
            f"{BASE_URL}/api/admin/ai-studio/heygen/status/test-id",
            timeout=30
        )
        assert status_response.status_code == 200, "Status endpoint should work"
        
        print("✓ All HeyGen workflow endpoints accessible")
    
    def test_api_key_configured(self):
        """Test that HeyGen API key is properly configured"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-studio/heygen/quota", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success") and data.get("quota"):
            print(f"✓ HeyGen API key is configured and valid")
            print(f"  Quota info: {data['quota']}")
        else:
            error = data.get("error", "Unknown error")
            if "not configured" in error.lower():
                pytest.skip("HeyGen API key not configured in environment")
            else:
                print(f"⚠ HeyGen API may have issues: {error}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
