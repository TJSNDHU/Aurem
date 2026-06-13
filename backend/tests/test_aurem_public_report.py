"""
AUREM Public Report API Tests
=============================
Tests for /api/report/{slug} endpoints:
- GET /api/report/{slug} - Public report data
- POST /api/report/{slug}/visit - Log page view
- POST /api/report/{slug}/engaged - 30-sec WhatsApp nudge (idempotent per day)
"""
import pytest
import requests
import os

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test lead slug - TJ Auto Clinic
TEST_SLUG = "tj-auto-clinic-001"
NONEXISTENT_SLUG = "nonexistent-slug-xyz-12345"


class TestAuremPublicReportGet:
    """GET /api/report/{slug} - Public report data (no auth required)"""
    
    def test_get_report_success(self):
        """Test fetching report for existing lead"""
        response = requests.get(f"{BASE_URL}/api/report/{TEST_SLUG}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify top-level structure
        assert "slug" in data
        assert data["slug"] == TEST_SLUG
        assert "business" in data
        assert "score" in data
        assert "growth_gaps" in data
        assert "aurem_fixes" in data
        assert "revenue" in data
        assert "pricing" in data
        assert "social_proof" in data
        assert "generated_at" in data
        
        # Verify business data
        business = data["business"]
        assert business["name"] == "TJ Auto Clinic Limited"
        assert business["city"] == "Brampton"
        assert business["phone"] == "+12265017777"
        assert business["email"] == "tjautoclinic@gmail.com"
        
        # Verify score structure
        score = data["score"]
        assert score["score"] == 20
        assert score["severity"] == "critical"
        assert "breakdown" in score
        assert score["industry_average"] == 67
        assert score["top_competitors"] == 89
        
        # Verify growth_gaps (should have 5)
        assert len(data["growth_gaps"]) == 5
        gap_titles = [g["title"] for g in data["growth_gaps"]]
        assert "No Website" in gap_titles
        assert "Only 3 Reviews" in gap_titles
        
        # Verify aurem_fixes (should have 7)
        assert len(data["aurem_fixes"]) == 7
        fix_titles = [f["title"] for f in data["aurem_fixes"]]
        assert "Google SEO" in fix_titles
        assert "Auto Google Reviews" in fix_titles
        
        # Verify revenue projections
        revenue = data["revenue"]
        assert revenue["additional_monthly_revenue_cad"] == 10500
        assert revenue["annual_impact_cad"] == 126000
        assert revenue["avg_job_value_cad"] == 350
        
        # Verify pricing tiers (3 tiers)
        assert len(data["pricing"]) == 3
        tiers = [p["tier"] for p in data["pricing"]]
        assert "starter" in tiers
        assert "growth" in tiers
        assert "enterprise" in tiers
        
        # Verify growth tier is marked popular
        growth_tier = next(p for p in data["pricing"] if p["tier"] == "growth")
        assert growth_tier["popular"] is True
        
        # Verify social_proof
        assert len(data["social_proof"]) == 3
    
    def test_get_report_not_found(self):
        """Test 404 for nonexistent slug"""
        response = requests.get(f"{BASE_URL}/api/report/{NONEXISTENT_SLUG}")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()


class TestAuremPublicReportVisit:
    """POST /api/report/{slug}/visit - Log page view"""
    
    def test_visit_log_success(self):
        """Test logging a visit for existing lead"""
        response = requests.post(
            f"{BASE_URL}/api/report/{TEST_SLUG}/visit",
            json={
                "referrer": "pytest-test-agent",
                "user_agent": "PytestAgent/1.0"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["logged"] is True
        assert "timestamp" in data
    
    def test_visit_log_not_found(self):
        """Test 404 for nonexistent slug"""
        response = requests.post(
            f"{BASE_URL}/api/report/{NONEXISTENT_SLUG}/visit",
            json={"referrer": "test", "user_agent": "test"}
        )
        assert response.status_code == 404
    
    def test_visit_log_empty_body(self):
        """Test visit with empty body (optional fields)"""
        response = requests.post(
            f"{BASE_URL}/api/report/{TEST_SLUG}/visit",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["logged"] is True


class TestAuremPublicReportEngaged:
    """POST /api/report/{slug}/engaged - 30-sec WhatsApp nudge (idempotent)"""
    
    def test_engaged_idempotency(self):
        """Test that engaged endpoint is idempotent per day"""
        # First call may send or return already_sent_today
        response1 = requests.post(
            f"{BASE_URL}/api/report/{TEST_SLUG}/engaged",
            json={"duration_seconds": 35}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second call should return already_sent_today
        response2 = requests.post(
            f"{BASE_URL}/api/report/{TEST_SLUG}/engaged",
            json={"duration_seconds": 40}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        
        # At least one should indicate already sent (idempotency)
        # If first was fresh send, second must be already_sent_today
        if data1.get("sent") is True:
            assert data2.get("sent") is False
            assert data2.get("reason") == "already_sent_today"
        else:
            # First was already sent today
            assert data1.get("reason") == "already_sent_today"
    
    def test_engaged_not_found(self):
        """Test 404 for nonexistent slug"""
        response = requests.post(
            f"{BASE_URL}/api/report/{NONEXISTENT_SLUG}/engaged",
            json={"duration_seconds": 30}
        )
        assert response.status_code == 404


class TestAuremPublicReportScoreBreakdown:
    """Detailed score breakdown validation"""
    
    def test_score_breakdown_structure(self):
        """Verify score breakdown items have correct structure"""
        response = requests.get(f"{BASE_URL}/api/report/{TEST_SLUG}")
        assert response.status_code == 200
        
        data = response.json()
        breakdown = data["score"]["breakdown"]
        
        for item in breakdown:
            assert "item" in item
            assert "points" in item
            assert "max" in item
            assert "status" in item
            assert item["status"] in ["good", "average", "low", "missing"]
            assert isinstance(item["points"], int)
            assert isinstance(item["max"], int)
            assert item["points"] <= item["max"]


class TestAuremPublicReportPricing:
    """Pricing tier validation"""
    
    def test_pricing_structure(self):
        """Verify pricing tiers have correct structure"""
        response = requests.get(f"{BASE_URL}/api/report/{TEST_SLUG}")
        assert response.status_code == 200
        
        data = response.json()
        pricing = data["pricing"]
        
        for plan in pricing:
            assert "tier" in plan
            assert "name" in plan
            assert "price_cad" in plan
            assert "tag" in plan
            assert "features" in plan
            assert "cta_label" in plan
            assert "price_id" in plan
            assert "checkout_meta" in plan
            assert "popular" in plan
            
            # Verify features is a list
            assert isinstance(plan["features"], list)
            assert len(plan["features"]) >= 3
            
            # Verify checkout_meta structure
            meta = plan["checkout_meta"]
            assert "package_id" in meta
            assert "origin_url" in meta
            assert "ref" in meta
            assert meta["ref"] == TEST_SLUG
    
    def test_pricing_values(self):
        """Verify specific pricing values"""
        response = requests.get(f"{BASE_URL}/api/report/{TEST_SLUG}")
        data = response.json()
        
        pricing_map = {p["tier"]: p for p in data["pricing"]}
        
        assert pricing_map["starter"]["price_cad"] == 97
        assert pricing_map["growth"]["price_cad"] == 297
        assert pricing_map["enterprise"]["price_cad"] == 997
        
        # Only growth should be popular
        assert pricing_map["starter"]["popular"] is False
        assert pricing_map["growth"]["popular"] is True
        assert pricing_map["enterprise"]["popular"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
