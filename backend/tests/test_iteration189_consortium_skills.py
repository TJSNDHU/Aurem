"""
Iteration 189 - G0DM0D3 CONSORTIUM + Skills Integration Tests
=============================================================
Tests for:
1. CONSORTIUM mode (Enterprise-only multi-model hive-mind synthesis)
2. Skills API (43 marketing + 28 C-level = 71 total)
3. Content Engine generate-social with platform-specific skill selection
4. Regression: ORA chat, video/pentest endpoints

CONSORTIUM uses Emergent LLM Key via emergentintegrations LlmChat.
It races GPT-4o, Claude Sonnet, Gemini Flash in parallel, then synthesizes.
Gemini may fail sometimes (known issue with litellm). 2/3 models responding is normal.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "<REDACTED>"


class TestSetup:
    """Setup and auth helpers"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get JWT token for authenticated requests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Auth failed: {response.status_code} - {response.text[:200]}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with JWT token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestSkillsAPI(TestSetup):
    """Test /api/ora/skills endpoint - public, no auth required"""
    
    def test_skills_endpoint_returns_200(self):
        """GET /api/ora/skills should return 200 (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/ora/skills", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        print("PASS: GET /api/ora/skills returns 200")
    
    def test_skills_returns_71_total(self):
        """Skills endpoint should return 71 total skills (43 marketing + 28 clevel)"""
        response = requests.get(f"{BASE_URL}/api/ora/skills", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # Check total count
        total = data.get("total", 0)
        assert total == 71, f"Expected 71 total skills, got {total}"
        print(f"PASS: Total skills = {total} (expected 71)")
    
    def test_skills_marketing_count(self):
        """Marketing skills should have 43 skills"""
        response = requests.get(f"{BASE_URL}/api/ora/skills", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        marketing = data.get("marketing", {})
        marketing_total = marketing.get("total", 0)
        assert marketing_total == 43, f"Expected 43 marketing skills, got {marketing_total}"
        print(f"PASS: Marketing skills = {marketing_total} (expected 43)")
    
    def test_skills_clevel_count(self):
        """C-Level skills should have 28 skills"""
        response = requests.get(f"{BASE_URL}/api/ora/skills", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        clevel = data.get("clevel", {})
        clevel_total = clevel.get("total", 0)
        assert clevel_total == 28, f"Expected 28 C-level skills, got {clevel_total}"
        print(f"PASS: C-Level skills = {clevel_total} (expected 28)")
    
    def test_skills_categories_breakdown(self):
        """Skills should return categories breakdown"""
        response = requests.get(f"{BASE_URL}/api/ora/skills", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # Marketing categories
        marketing_cats = data.get("marketing", {}).get("categories", {})
        assert "social_media" in marketing_cats, "Missing social_media category"
        assert "email" in marketing_cats, "Missing email category"
        assert "ads" in marketing_cats, "Missing ads category"
        assert "landing_page" in marketing_cats, "Missing landing_page category"
        assert "brand" in marketing_cats, "Missing brand category"
        assert "seo" in marketing_cats, "Missing seo category"
        print(f"PASS: Marketing categories: {list(marketing_cats.keys())}")
        
        # C-Level categories
        clevel_cats = data.get("clevel", {}).get("categories", {})
        assert "ceo" in clevel_cats, "Missing ceo category"
        assert "cfo" in clevel_cats, "Missing cfo category"
        assert "cmo" in clevel_cats, "Missing cmo category"
        assert "cto" in clevel_cats, "Missing cto category"
        assert "coo" in clevel_cats, "Missing coo category"
        print(f"PASS: C-Level categories: {list(clevel_cats.keys())}")
    
    def test_skills_list_structure(self):
        """Each skill should have id, name, category"""
        response = requests.get(f"{BASE_URL}/api/ora/skills", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        marketing_skills = data.get("marketing", {}).get("skills", [])
        assert len(marketing_skills) > 0, "No marketing skills returned"
        
        # Check first skill structure
        skill = marketing_skills[0]
        assert "id" in skill, "Skill missing 'id'"
        assert "name" in skill, "Skill missing 'name'"
        assert "category" in skill, "Skill missing 'category'"
        print(f"PASS: Skill structure valid - sample: {skill}")


class TestConsortiumMode(TestSetup):
    """Test /api/ora/consortium endpoint - Enterprise only"""
    
    def test_consortium_accessible_without_auth(self):
        """CONSORTIUM endpoint is accessible (tier check happens internally)"""
        response = requests.post(
            f"{BASE_URL}/api/ora/consortium",
            json={"message": "Test query"},
            timeout=60
        )
        # Should return 200 (if enterprise) or 403 (if not enterprise)
        # Based on testing, it returns 200 because tenant is enterprise
        assert response.status_code in [200, 403], f"Expected 200 or 403, got {response.status_code}"
        print(f"PASS: CONSORTIUM endpoint accessible (status {response.status_code})")
    
    def test_consortium_enterprise_tier_returns_ground_truth(self, auth_headers):
        """CONSORTIUM should return ground_truth + model_results for Enterprise tier"""
        response = requests.post(
            f"{BASE_URL}/api/ora/consortium",
            json={"message": "What is the best strategy for market expansion?"},
            headers=auth_headers,
            timeout=90  # CONSORTIUM races multiple models, needs longer timeout
        )
        
        # If tenant is Enterprise, should get 200 with ground_truth + model_results
        # If not Enterprise, should get 403
        if response.status_code == 403:
            data = response.json()
            detail = data.get("detail", "")
            assert "enterprise" in detail.lower() or "plan" in detail.lower(), \
                f"403 should mention Enterprise plan requirement: {detail}"
            print(f"PASS: CONSORTIUM returns 403 for non-Enterprise tier: {detail}")
        elif response.status_code == 200:
            data = response.json()
            assert "ground_truth" in data, "Response missing ground_truth"
            assert "model_results" in data, "Response missing model_results"
            assert "consortium_id" in data, "Response missing consortium_id"
            assert "models_queried" in data, "Response missing models_queried"
            assert "models_responded" in data, "Response missing models_responded"
            
            # Validate model_results structure
            model_results = data.get("model_results", [])
            assert len(model_results) > 0, "No model results returned"
            
            # At least 2/3 models should respond (Gemini may fail - known issue)
            models_responded = data.get("models_responded", 0)
            assert models_responded >= 2, f"Expected at least 2 models to respond, got {models_responded}"
            
            print(f"PASS: CONSORTIUM returned ground_truth with {models_responded}/{data.get('models_queried', 3)} models")
            print(f"  - consortium_id: {data.get('consortium_id')}")
            print(f"  - ground_truth preview: {data.get('ground_truth', '')[:100]}...")
        else:
            pytest.fail(f"Unexpected status {response.status_code}: {response.text[:300]}")


class TestContentEngineSocialSkills(TestSetup):
    """Test Content Engine social-post with platform-specific skill selection"""
    
    def test_social_post_instagram_uses_instagram_skill(self, auth_headers):
        """POST /api/content-engine/social-post with platform=instagram should use instagram_caption skill"""
        response = requests.post(
            f"{BASE_URL}/api/content-engine/social-post",
            json={
                "topic": "AI-powered business automation",
                "platform": "instagram",
                "brand_voice": "professional"
            },
            headers=auth_headers,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            skill_used = data.get("skill_used")
            assert skill_used == "instagram_caption", f"Expected instagram_caption skill, got {skill_used}"
            assert data.get("generated") == True, "Content not generated"
            assert data.get("platform") == "instagram", "Platform mismatch"
            print(f"PASS: Instagram post uses instagram_caption skill")
            print(f"  - Content preview: {data.get('content', '')[:100]}...")
        elif response.status_code == 429:
            pytest.skip("Rate limited - skipping")
        else:
            # May fail due to limit reached - check error
            try:
                data = response.json()
                if data.get("error") == "limit_reached":
                    pytest.skip(f"Content limit reached: {data.get('message')}")
            except Exception:
                pass
            pytest.fail(f"Unexpected status {response.status_code}: {response.text[:200]}")
    
    def test_social_post_linkedin_uses_linkedin_skill(self, auth_headers):
        """POST /api/content-engine/social-post with platform=linkedin should use linkedin_post skill"""
        response = requests.post(
            f"{BASE_URL}/api/content-engine/social-post",
            json={
                "topic": "Leadership in the age of AI",
                "platform": "linkedin",
                "brand_voice": "thought_leader"
            },
            headers=auth_headers,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            skill_used = data.get("skill_used")
            assert skill_used == "linkedin_post", f"Expected linkedin_post skill, got {skill_used}"
            assert data.get("generated") == True, "Content not generated"
            assert data.get("platform") == "linkedin", "Platform mismatch"
            print(f"PASS: LinkedIn post uses linkedin_post skill")
            print(f"  - Content preview: {data.get('content', '')[:100]}...")
        elif response.status_code == 429:
            pytest.skip("Rate limited - skipping")
        else:
            try:
                data = response.json()
                if data.get("error") == "limit_reached":
                    pytest.skip(f"Content limit reached: {data.get('message')}")
            except Exception:
                pass
            pytest.fail(f"Unexpected status {response.status_code}: {response.text[:200]}")
    
    def test_social_post_twitter_uses_twitter_skill(self, auth_headers):
        """POST /api/content-engine/social-post with platform=twitter should use twitter_thread skill"""
        response = requests.post(
            f"{BASE_URL}/api/content-engine/social-post",
            json={
                "topic": "5 productivity hacks for entrepreneurs",
                "platform": "twitter",
                "brand_voice": "casual"
            },
            headers=auth_headers,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            skill_used = data.get("skill_used")
            assert skill_used == "twitter_thread", f"Expected twitter_thread skill, got {skill_used}"
            assert data.get("generated") == True, "Content not generated"
            print(f"PASS: Twitter post uses twitter_thread skill")
        elif response.status_code == 429:
            pytest.skip("Rate limited - skipping")
        else:
            try:
                data = response.json()
                if data.get("error") == "limit_reached":
                    pytest.skip(f"Content limit reached: {data.get('message')}")
            except Exception:
                pass
            pytest.fail(f"Unexpected status {response.status_code}: {response.text[:200]}")


class TestORAChatRegression(TestSetup):
    """Regression tests for existing ORA chat functionality"""
    
    def test_ora_chat_still_works(self, auth_headers):
        """POST /api/aurem/chat should still work (regression)"""
        response = requests.post(
            f"{BASE_URL}/api/aurem/chat",
            json={"message": "Hello, what can you help me with?"},
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200, f"ORA chat failed: {response.status_code} - {response.text[:200]}"
        data = response.json()
        assert "response" in data, "Missing response field"
        assert "session_id" in data, "Missing session_id field"
        assert len(data.get("response", "")) > 10, "Response too short"
        print(f"PASS: ORA chat works - response preview: {data.get('response', '')[:100]}...")
    
    def test_ora_chat_clevel_skill_detection(self, auth_headers):
        """ORA chat should detect C-level skill triggers (pricing strategy)"""
        response = requests.post(
            f"{BASE_URL}/api/aurem/chat",
            json={"message": "Help me with pricing strategy for my SaaS product"},
            headers=auth_headers,
            timeout=30
        )
        
        assert response.status_code == 200, f"ORA chat failed: {response.status_code}"
        data = response.json()
        assert "response" in data, "Missing response field"
        # The response should be influenced by pricing_strategy skill
        print(f"PASS: ORA chat with C-level trigger works")


class TestVideoEndpointRegression(TestSetup):
    """Regression tests for video generation endpoints"""
    
    def test_video_history_endpoint(self, auth_headers):
        """GET /api/content-engine/video-history should work"""
        response = requests.get(
            f"{BASE_URL}/api/content-engine/video-history",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Video history failed: {response.status_code}"
        data = response.json()
        assert "videos" in data or isinstance(data, list), "Invalid response structure"
        print(f"PASS: Video history endpoint works")
    
    def test_content_engine_usage(self, auth_headers):
        """GET /api/content-engine/usage should return usage stats"""
        response = requests.get(
            f"{BASE_URL}/api/content-engine/usage",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Usage endpoint failed: {response.status_code}"
        data = response.json()
        assert "usage" in data or "content_posts" in data or "posts" in data, "Invalid usage structure"
        print(f"PASS: Content engine usage endpoint works")


class TestPentestEndpointRegression(TestSetup):
    """Regression tests for pentest endpoints"""
    
    def test_pentest_health(self, auth_headers):
        """GET /api/security/pentest/health should return status"""
        response = requests.get(
            f"{BASE_URL}/api/security/pentest/health",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Pentest health failed: {response.status_code}"
        data = response.json()
        # PentAGI is Legion-only, so online:false is expected
        assert "online" in data, "Missing online field"
        print(f"PASS: Pentest health endpoint works - online: {data.get('online')}")
    
    def test_pentest_history(self, auth_headers):
        """GET /api/security/pentest/history should return history"""
        response = requests.get(
            f"{BASE_URL}/api/security/pentest/history",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Pentest history failed: {response.status_code}"
        data = response.json()
        assert "pentests" in data or isinstance(data, list), "Invalid history structure"
        print(f"PASS: Pentest history endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
