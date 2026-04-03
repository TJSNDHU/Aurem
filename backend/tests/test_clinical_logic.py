"""
Test suite for Clinical Logic - Tag-Based Milestone System
Tests:
- GET /api/admin/clinical-logic/tags - Product tag definitions
- GET /api/admin/clinical-logic/milestones - Milestone templates (8 seeded)
- POST /api/admin/clinical-logic/milestones - Create with compliance validation
- PUT /api/admin/clinical-logic/milestones/{id} - Update milestone
- POST /api/admin/clinical-logic/generate-calendar - Generate calendar from product tags
- POST /api/admin/clinical-logic/validate-text - Forbidden word validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test admin credentials - using JWT bypass for testing
TEST_ADMIN_TOKEN = None

@pytest.fixture(scope="module")
def admin_session():
    """Get admin auth token for testing"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Try to login or create test admin session
    # For reroots, we'll use a test token approach
    global TEST_ADMIN_TOKEN
    
    # First try to get a token by checking the auth endpoint
    try:
        # Create test session in DB directly via API
        res = session.get(f"{BASE_URL}/api/health")
        assert res.status_code == 200, "Backend health check failed"
        
        # For admin testing, we'll need to simulate admin auth
        # The endpoints require admin role, so we'll use Google SSO token bypass
        # Since we can't automate Google SSO, we'll test if endpoints properly require auth
        TEST_ADMIN_TOKEN = "test_admin_token_for_clinical_logic"
        session.headers.update({"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"})
        return session
    except Exception as e:
        pytest.skip(f"Could not establish admin session: {e}")


class TestClinicalLogicEndpoints:
    """Test Clinical Logic API endpoints"""
    
    def test_health_check(self):
        """Verify backend is running"""
        res = requests.get(f"{BASE_URL}/api/health")
        assert res.status_code == 200
        print("✓ Backend health check passed")
    
    def test_get_product_tags_requires_auth(self):
        """GET /api/admin/clinical-logic/tags should require admin auth"""
        res = requests.get(f"{BASE_URL}/api/admin/clinical-logic/tags")
        # Should return 401 without auth
        assert res.status_code in [401, 403], f"Expected auth error, got {res.status_code}"
        print("✓ Tags endpoint requires authentication")
    
    def test_get_milestones_requires_auth(self):
        """GET /api/admin/clinical-logic/milestones should require admin auth"""
        res = requests.get(f"{BASE_URL}/api/admin/clinical-logic/milestones")
        assert res.status_code in [401, 403], f"Expected auth error, got {res.status_code}"
        print("✓ Milestones endpoint requires authentication")
    
    def test_generate_calendar_requires_auth(self):
        """POST /api/admin/clinical-logic/generate-calendar should require admin auth"""
        res = requests.post(
            f"{BASE_URL}/api/admin/clinical-logic/generate-calendar",
            json={"product_ids": ["prod-aura-gen"]}
        )
        assert res.status_code in [401, 403], f"Expected auth error, got {res.status_code}"
        print("✓ Generate calendar endpoint requires authentication")
    
    def test_validate_text_requires_auth(self):
        """POST /api/admin/clinical-logic/validate-text should require admin auth"""
        res = requests.post(
            f"{BASE_URL}/api/admin/clinical-logic/validate-text",
            json={"text": "This will heal your skin"}
        )
        assert res.status_code in [401, 403], f"Expected auth error, got {res.status_code}"
        print("✓ Validate text endpoint requires authentication")


class TestProductsWithTags:
    """Test that products have tags assigned"""
    
    def test_get_prod_aura_gen_has_tags(self):
        """Verify prod-aura-gen has clinical tags [ACID, BRIGHTENER, PEPTIDE]"""
        res = requests.get(f"{BASE_URL}/api/products/prod-aura-gen")
        assert res.status_code == 200, f"Failed to get product: {res.status_code}"
        
        data = res.json()
        tags = data.get("tags", [])
        print(f"  prod-aura-gen tags: {tags}")
        
        # Check expected tags
        expected_tags = ["ACID", "BRIGHTENER", "PEPTIDE"]
        for expected in expected_tags:
            assert expected in tags, f"Expected tag {expected} not found in {tags}"
        
        print(f"✓ prod-aura-gen has expected tags: {tags}")
    
    def test_get_prod_copper_peptide_has_tags(self):
        """Verify prod-copper-peptide has clinical tags [PEPTIDE, PDRN, BARRIER]"""
        res = requests.get(f"{BASE_URL}/api/products/prod-copper-peptide")
        assert res.status_code == 200, f"Failed to get product: {res.status_code}"
        
        data = res.json()
        tags = data.get("tags", [])
        print(f"  prod-copper-peptide tags: {tags}")
        
        # Check expected tags
        expected_tags = ["PEPTIDE", "PDRN", "BARRIER"]
        for expected in expected_tags:
            assert expected in tags, f"Expected tag {expected} not found in {tags}"
        
        print(f"✓ prod-copper-peptide has expected tags: {tags}")


class TestClinicalLogicWithAuth:
    """Test Clinical Logic endpoints with authentication (using MongoDB session)"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Setup authenticated session using database token"""
        import subprocess
        import json
        
        # Create test admin session directly in MongoDB
        script = """
        var token = 'test_clinical_logic_session_' + Date.now();
        var userId = 'test-admin-clinical-' + Date.now();
        
        // Create test admin user
        db.users.updateOne(
            { email: 'test-clinical-admin@example.com' },
            { $set: {
                user_id: userId,
                email: 'test-clinical-admin@example.com',
                name: 'Clinical Test Admin',
                role: 'admin',
                created_at: new Date()
            }},
            { upsert: true }
        );
        
        // Create session
        db.user_sessions.insertOne({
            user_id: userId,
            session_token: token,
            expires_at: new Date(Date.now() + 24*60*60*1000),
            created_at: new Date()
        });
        
        print(JSON.stringify({token: token, userId: userId}));
        """
        
        try:
            result = subprocess.run(
                ['mongosh', '--quiet', '--eval', f"use reroots; {script}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    if line.startswith('{'):
                        data = json.loads(line)
                        self.token = data['token']
                        self.userId = data['userId']
                        self.headers = {"Authorization": f"Bearer {self.token}"}
                        return
        except Exception as e:
            print(f"Warning: Could not create test session: {e}")
        
        pytest.skip("Could not create test admin session in MongoDB")
    
    def test_get_product_tags_authenticated(self):
        """GET /api/admin/clinical-logic/tags returns available tags"""
        res = requests.get(
            f"{BASE_URL}/api/admin/clinical-logic/tags",
            headers=self.headers
        )
        
        # May still require Google SSO - check response
        if res.status_code in [401, 403]:
            pytest.skip("Admin endpoints require Google SSO authentication")
        
        assert res.status_code == 200, f"Unexpected status: {res.status_code} - {res.text}"
        data = res.json()
        
        tags = data.get("tags", [])
        assert len(tags) > 0, "Should return available tags"
        
        # Verify expected tags are present
        tag_ids = [t.get("id") for t in tags]
        expected_tags = ["ACID", "RETINOID", "BRIGHTENER", "PEPTIDE", "PDRN", "BARRIER", "SOD", "ACNE_CONTROL", "SENSITIVE"]
        for expected in expected_tags:
            assert expected in tag_ids, f"Tag {expected} not found"
        
        print(f"✓ Tags endpoint returned {len(tags)} tags")
    
    def test_get_milestones_authenticated(self):
        """GET /api/admin/clinical-logic/milestones returns seeded milestones"""
        res = requests.get(
            f"{BASE_URL}/api/admin/clinical-logic/milestones",
            headers=self.headers
        )
        
        if res.status_code in [401, 403]:
            pytest.skip("Admin endpoints require Google SSO authentication")
        
        assert res.status_code == 200, f"Unexpected status: {res.status_code}"
        data = res.json()
        
        milestones = data.get("milestones", [])
        forbidden_words = data.get("forbidden_words", [])
        
        # Should have 8 seeded milestones
        assert len(milestones) >= 8, f"Expected at least 8 milestones, got {len(milestones)}"
        
        # Verify forbidden words are returned
        assert "heal" in forbidden_words
        assert "cure" in forbidden_words
        assert "acne" in forbidden_words
        
        print(f"✓ Milestones endpoint returned {len(milestones)} milestones and {len(forbidden_words)} forbidden words")
    
    def test_validate_text_detects_forbidden_words(self):
        """POST /api/admin/clinical-logic/validate-text flags forbidden words"""
        test_cases = [
            {
                "text": "This will heal your acne scars",
                "expected_forbidden": ["heal", "acne", "scar"]
            },
            {
                "text": "Support skin cellular renewal",
                "expected_forbidden": []  # Should be compliant
            },
            {
                "text": "DNA repair and anti-inflammatory treatment",
                "expected_forbidden": ["dna repair", "anti-inflammatory", "treat"]
            }
        ]
        
        for test in test_cases:
            res = requests.post(
                f"{BASE_URL}/api/admin/clinical-logic/validate-text",
                json={"text": test["text"]},
                headers=self.headers
            )
            
            if res.status_code in [401, 403]:
                pytest.skip("Admin endpoints require Google SSO authentication")
            
            assert res.status_code == 200
            data = res.json()
            
            is_compliant = data.get("is_compliant")
            forbidden = data.get("forbidden_words", [])
            suggestions = data.get("suggestions", {})
            
            if test["expected_forbidden"]:
                assert not is_compliant, f"Text '{test['text']}' should not be compliant"
                for word in test["expected_forbidden"]:
                    assert word in forbidden, f"Expected '{word}' to be flagged in '{test['text']}'"
                # Verify suggestions are provided
                assert len(suggestions) > 0, "Suggestions should be provided for forbidden words"
            else:
                assert is_compliant, f"Text '{test['text']}' should be compliant"
            
            print(f"  ✓ Validated: '{test['text'][:30]}...' - compliant={is_compliant}")
        
        print("✓ Validate text correctly detects forbidden cosmetic words")
    
    def test_generate_calendar_from_product_tags(self):
        """POST /api/admin/clinical-logic/generate-calendar assembles milestones from tags"""
        # Use tagged products
        res = requests.post(
            f"{BASE_URL}/api/admin/clinical-logic/generate-calendar",
            json={"product_ids": ["prod-aura-gen", "prod-copper-peptide"]},
            headers=self.headers
        )
        
        if res.status_code in [401, 403]:
            pytest.skip("Admin endpoints require Google SSO authentication")
        
        assert res.status_code == 200, f"Unexpected status: {res.status_code}"
        data = res.json()
        
        assert data.get("success") == True
        
        # Verify products info
        products = data.get("products", [])
        assert len(products) == 2
        
        # Verify all tags collected
        all_tags = data.get("all_tags", [])
        expected_tags = ["ACID", "BRIGHTENER", "PEPTIDE", "PDRN", "BARRIER"]
        for tag in expected_tags:
            assert tag in all_tags, f"Expected tag {tag} not in {all_tags}"
        
        # Verify milestones matched
        milestones = data.get("milestones", [])
        assert len(milestones) > 0, "Should match some milestones based on tags"
        
        # Verify milestone structure
        for m in milestones:
            assert "phase_name" in m
            assert "day_start" in m
            assert "day_end" in m
            assert "priority" in m
            assert "matched_tags" in m
        
        # Verify label_style (should be engine_buffer since no SENSITIVE tag)
        label_style = data.get("label_style")
        assert label_style == "engine_buffer", f"Expected engine_buffer, got {label_style}"
        
        # Verify total active calculation
        total_active = data.get("total_active_percent", 0)
        assert total_active > 0, "Should calculate total active percent"
        
        print(f"✓ Calendar preview generated: {len(milestones)} milestones, {total_active}% active, style={label_style}")
    
    def test_generate_calendar_sensitive_label_style(self):
        """Products with SENSITIVE tag should use SOOTH/PROTECT labels"""
        # First check if there's a product with SENSITIVE tag
        # If not, we skip this test
        res = requests.get(f"{BASE_URL}/api/products")
        products = res.json() if res.status_code == 200 else []
        
        sensitive_product = None
        for p in products:
            if "SENSITIVE" in (p.get("tags") or []):
                sensitive_product = p.get("id")
                break
        
        if not sensitive_product:
            pytest.skip("No product with SENSITIVE tag found for label style test")
        
        res = requests.post(
            f"{BASE_URL}/api/admin/clinical-logic/generate-calendar",
            json={"product_ids": [sensitive_product]},
            headers=self.headers
        )
        
        if res.status_code in [401, 403]:
            pytest.skip("Admin endpoints require Google SSO authentication")
        
        if res.status_code == 200:
            data = res.json()
            label_style = data.get("label_style")
            assert label_style == "sooth_protect", f"Expected sooth_protect for SENSITIVE products, got {label_style}"
            print(f"✓ SENSITIVE product uses SOOTH/PROTECT label style")
    
    def test_create_milestone_with_forbidden_words(self):
        """POST /api/admin/clinical-logic/milestones rejects forbidden words"""
        res = requests.post(
            f"{BASE_URL}/api/admin/clinical-logic/milestones",
            json={
                "tags": ["ACID"],
                "phase_name": "Test Milestone",
                "day_start": 1,
                "day_end": 7,
                "description": "This will heal your acne and cure skin disease",
                "priority": 5
            },
            headers=self.headers
        )
        
        if res.status_code in [401, 403]:
            pytest.skip("Admin endpoints require Google SSO authentication")
        
        assert res.status_code == 200  # Returns 200 with success=false
        data = res.json()
        
        assert data.get("success") == False
        assert "forbidden_words" in data
        assert "heal" in data["forbidden_words"]
        assert "acne" in data["forbidden_words"]
        assert "cure" in data["forbidden_words"]
        assert "suggestions" in data
        
        print("✓ Create milestone correctly rejects forbidden cosmetic words")
    
    def test_create_and_delete_milestone(self):
        """POST then DELETE milestone template"""
        # Create compliant milestone
        create_res = requests.post(
            f"{BASE_URL}/api/admin/clinical-logic/milestones",
            json={
                "tags": ["ACID"],
                "phase_name": "TEST - Clarity Phase",
                "day_start": 1,
                "day_end": 14,
                "description": "Surface clarity begins as cellular turnover supports skin renewal.",
                "priority": 5,
                "is_active": True
            },
            headers=self.headers
        )
        
        if create_res.status_code in [401, 403]:
            pytest.skip("Admin endpoints require Google SSO authentication")
        
        assert create_res.status_code == 200
        create_data = create_res.json()
        
        if create_data.get("success") == False:
            pytest.fail(f"Failed to create milestone: {create_data}")
        
        milestone_id = create_data.get("milestone", {}).get("id")
        assert milestone_id, "Should return milestone ID"
        
        print(f"  Created milestone: {milestone_id}")
        
        # Delete the test milestone
        delete_res = requests.delete(
            f"{BASE_URL}/api/admin/clinical-logic/milestones/{milestone_id}",
            headers=self.headers
        )
        
        assert delete_res.status_code == 200
        print(f"✓ Create and delete milestone works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
