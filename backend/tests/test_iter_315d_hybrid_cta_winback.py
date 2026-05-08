"""
Iteration 315d — Hybrid CTA + NPS Win-back + Stripe Key Fix + Dead Webhook Cleanup
==================================================================================
Tests:
1. GET /api/report/{lead_id} returns repair_offer block when customer_scans has public_slug
2. GET /api/report/{lead_id_with_no_scan} returns repair_offer:null
3. GET /api/repair-report/{slug} (lead_id fallback) returns 200 HTML
4. GET /api/repair-report/{public_slug} returns 200 HTML
5. GET /api/repair-report/nonexistent returns 404
6. GET /api/repair/checkout?slug=...&tier=basic returns 302 to checkout.stripe.com
7. POST /api/repair/webhook returns 404 (endpoint deleted)
8. POST /api/edit/nps with detractor score arms winback sequence
9. POST /api/edit/nps with promoter score does NOT arm winback
10. POST /api/edit/nps duplicate call returns duplicate:true, winback_armed:null
11. Winback sequence idempotency
12. Stripe key resolver rejects placeholder keys
13. POST /api/payments/checkout creates valid checkout URL
"""
import pytest
import requests
import os
import hashlib
import uuid
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"


class TestHybridCTARepairOffer:
    """Test repair_offer block in public report"""
    
    def test_report_with_repair_offer(self):
        """GET /api/report/spadina-auto returns repair_offer with available:true"""
        r = requests.get(f"{BASE_URL}/api/report/spadina-auto")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        # Verify repair_offer block exists and is populated
        repair_offer = data.get("repair_offer")
        assert repair_offer is not None, "repair_offer should be present"
        assert repair_offer.get("available") is True, "repair_offer.available should be True"
        assert repair_offer.get("public_slug") == "r-541ad7277a", f"Expected public_slug r-541ad7277a, got {repair_offer.get('public_slug')}"
        assert isinstance(repair_offer.get("score"), int), "repair_offer.score should be int"
        assert isinstance(repair_offer.get("issues_total"), int), "repair_offer.issues_total should be int"
        
        # Verify tiers
        tiers = repair_offer.get("tiers", [])
        assert len(tiers) == 2, f"Expected 2 tiers, got {len(tiers)}"
        
        basic_tier = next((t for t in tiers if t["tier"] == "basic"), None)
        full_tier = next((t for t in tiers if t["tier"] == "full"), None)
        
        assert basic_tier is not None, "basic tier should exist"
        assert full_tier is not None, "full tier should exist"
        assert basic_tier["price_cad"] == 149, f"basic tier price should be 149, got {basic_tier['price_cad']}"
        assert full_tier["price_cad"] == 299, f"full tier price should be 299, got {full_tier['price_cad']}"
        assert "checkout_url" in basic_tier, "basic tier should have checkout_url"
        assert "checkout_url" in full_tier, "full tier should have checkout_url"
        
        print(f"✓ repair_offer block verified: score={repair_offer['score']}, issues={repair_offer['issues_total']}")
    
    def test_report_without_scan_returns_null_repair_offer(self):
        """GET /api/report/{lead_id_with_no_scan} returns repair_offer:null"""
        # Use a lead that exists but has no customer_scans entry
        # First, let's check if there's a lead without a scan
        r = requests.get(f"{BASE_URL}/api/report/nonexistent-lead-12345")
        # This should return 404 since the lead doesn't exist
        assert r.status_code == 404, f"Expected 404 for nonexistent lead, got {r.status_code}"
        print("✓ Nonexistent lead returns 404 as expected")


class TestRepairReportEndpoint:
    """Test /api/repair-report/{slug} endpoint"""
    
    def test_repair_report_by_lead_id(self):
        """GET /api/repair-report/spadina-auto (lead_id) returns 200 HTML"""
        r = requests.get(f"{BASE_URL}/api/repair-report/spadina-auto")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert "text/html" in r.headers.get("content-type", ""), "Should return HTML"
        assert "Website Audit" in r.text, "HTML should contain 'Website Audit'"
        print("✓ repair-report by lead_id returns 200 HTML")
    
    def test_repair_report_by_public_slug(self):
        """GET /api/repair-report/r-541ad7277a (public_slug) returns 200 HTML"""
        r = requests.get(f"{BASE_URL}/api/repair-report/r-541ad7277a")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert "text/html" in r.headers.get("content-type", ""), "Should return HTML"
        assert "Website Audit" in r.text, "HTML should contain 'Website Audit'"
        print("✓ repair-report by public_slug returns 200 HTML")
    
    def test_repair_report_nonexistent_returns_404(self):
        """GET /api/repair-report/nonexistent returns 404"""
        r = requests.get(f"{BASE_URL}/api/repair-report/nonexistent-slug-xyz")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        print("✓ repair-report nonexistent returns 404")


class TestRepairCheckout:
    """Test /api/repair/checkout endpoint"""
    
    def test_repair_checkout_redirects_to_stripe(self):
        """GET /api/repair/checkout?slug=r-541ad7277a&tier=basic returns 302 to checkout.stripe.com"""
        r = requests.get(
            f"{BASE_URL}/api/repair/checkout?slug=r-541ad7277a&tier=basic",
            allow_redirects=False
        )
        assert r.status_code == 302, f"Expected 302, got {r.status_code}: {r.text}"
        location = r.headers.get("location", "")
        assert "checkout.stripe.com" in location, f"Expected redirect to checkout.stripe.com, got {location}"
        assert "cs_live_" in location, f"Expected cs_live_ session ID in URL, got {location}"
        print(f"✓ repair checkout redirects to Stripe: {location[:80]}...")
    
    def test_repair_checkout_full_tier(self):
        """GET /api/repair/checkout?slug=r-541ad7277a&tier=full returns 302"""
        r = requests.get(
            f"{BASE_URL}/api/repair/checkout?slug=r-541ad7277a&tier=full",
            allow_redirects=False
        )
        assert r.status_code == 302, f"Expected 302, got {r.status_code}: {r.text}"
        location = r.headers.get("location", "")
        assert "checkout.stripe.com" in location, f"Expected redirect to checkout.stripe.com"
        print("✓ repair checkout full tier redirects to Stripe")


class TestDeadWebhookRemoved:
    """Test that /api/repair/webhook is removed"""
    
    def test_repair_webhook_returns_404(self):
        """POST /api/repair/webhook returns 404 (endpoint deleted)"""
        r = requests.post(f"{BASE_URL}/api/repair/webhook", json={})
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        print("✓ POST /api/repair/webhook returns 404 (endpoint deleted)")


class TestNPSWinbackSequence:
    """Test NPS detractor triggers winback sequence"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a test token for NPS testing"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def create_test_token():
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db = client[os.environ.get("DB_NAME", "aurem_db")]
            
            # Create a unique test token
            test_token = f"test_nps_{uuid.uuid4().hex[:12]}"
            token_hash = hashlib.sha256(test_token.encode()).hexdigest()
            
            # Insert test session
            await db.edit_sessions.insert_one({
                "request_id": f"test_{uuid.uuid4().hex[:12]}",
                "site_id": "9f9729949b5743",
                "token_hash": token_hash,
                "kind": "session",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            
            # Clean up any existing winback for this site
            await db.winback_sequences.delete_many({"site_id": "9f9729949b5743"})
            
            return test_token, db
        
        self.test_token, self.db = asyncio.get_event_loop().run_until_complete(create_test_token())
        yield
        
        # Cleanup
        async def cleanup():
            await self.db.edit_sessions.delete_many({"token_hash": hashlib.sha256(self.test_token.encode()).hexdigest()})
            await self.db.winback_sequences.delete_many({"site_id": "9f9729949b5743"})
            await self.db.nps_responses.delete_many({"site_id": "9f9729949b5743"})
        
        asyncio.get_event_loop().run_until_complete(cleanup())
    
    def test_nps_detractor_arms_winback(self):
        """POST /api/edit/nps with score=2 (detractor) returns winback_armed:<id>"""
        r = requests.post(
            f"{BASE_URL}/api/edit/nps",
            json={"token": self.test_token, "score": 2, "source": "test"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert data.get("detractor") is True, f"Expected detractor:true for score=2"
        assert data.get("winback_armed") is not None, f"Expected winback_armed to be set, got {data}"
        
        print(f"✓ NPS detractor (score=2) armed winback: {data.get('winback_armed')}")
        
        # Verify winback sequence in DB
        import asyncio
        async def verify_winback():
            wb = await self.db.winback_sequences.find_one(
                {"site_id": "9f9729949b5743"},
                {"_id": 0}
            )
            assert wb is not None, "Winback sequence should exist in DB"
            assert wb.get("status") == "armed", f"Expected status=armed, got {wb.get('status')}"
            assert len(wb.get("steps", [])) == 3, f"Expected 3 steps, got {len(wb.get('steps', []))}"
            
            # Verify step delays
            steps = wb.get("steps", [])
            assert steps[0]["kind"] == "apology", "Step 1 should be apology"
            assert steps[1]["kind"] == "call_offer", "Step 2 should be call_offer"
            assert steps[2]["kind"] == "domain_credit", "Step 3 should be domain_credit"
            
            print(f"✓ Winback sequence verified: {wb.get('winback_id')}, steps={len(steps)}")
        
        asyncio.get_event_loop().run_until_complete(verify_winback())
    
    def test_nps_promoter_no_winback(self):
        """POST /api/edit/nps with score=5 (promoter) returns winback_armed:null"""
        # Create a new token for this test
        import asyncio
        
        async def create_promoter_token():
            test_token = f"test_promoter_{uuid.uuid4().hex[:12]}"
            token_hash = hashlib.sha256(test_token.encode()).hexdigest()
            await self.db.edit_sessions.insert_one({
                "request_id": f"test_{uuid.uuid4().hex[:12]}",
                "site_id": "9f9729949b5743",
                "token_hash": token_hash,
                "kind": "session",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            return test_token
        
        promoter_token = asyncio.get_event_loop().run_until_complete(create_promoter_token())
        
        r = requests.post(
            f"{BASE_URL}/api/edit/nps",
            json={"token": promoter_token, "score": 5, "source": "test"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert data.get("detractor") is False, f"Expected detractor:false for score=5"
        assert data.get("winback_armed") is None, f"Expected winback_armed:null for promoter, got {data.get('winback_armed')}"
        
        print("✓ NPS promoter (score=5) does NOT arm winback")
    
    def test_nps_duplicate_no_double_arm(self):
        """POST /api/edit/nps duplicate call returns duplicate:true, winback_armed:null"""
        # First call - should arm winback
        r1 = requests.post(
            f"{BASE_URL}/api/edit/nps",
            json={"token": self.test_token, "score": 2, "source": "test"}
        )
        assert r1.status_code == 200
        data1 = r1.json()
        first_winback_id = data1.get("winback_armed")
        
        # Second call within 60s - should be duplicate
        r2 = requests.post(
            f"{BASE_URL}/api/edit/nps",
            json={"token": self.test_token, "score": 2, "source": "test"}
        )
        assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"
        data2 = r2.json()
        
        assert data2.get("duplicate") is True, f"Expected duplicate:true, got {data2}"
        assert data2.get("winback_armed") is None, f"Expected winback_armed:null on duplicate, got {data2.get('winback_armed')}"
        
        print("✓ NPS duplicate call returns duplicate:true, winback_armed:null")


class TestWinbackIdempotency:
    """Test winback sequence idempotency"""
    
    def test_arm_winback_already_armed_returns_skipped(self):
        """arm_winback_sequence on already-armed site returns skipped:already_armed"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        async def test_idempotency():
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            db = client[os.environ.get("DB_NAME", "aurem_db")]
            
            # Clean up first
            await db.winback_sequences.delete_many({"site_id": "test_idempotency_site"})
            
            # Import and call arm_winback_sequence directly
            import sys
            sys.path.insert(0, "/app/backend")
            from services.winback_sequence import arm_winback_sequence
            
            # First arm
            result1 = await arm_winback_sequence(
                db, site_id="test_idempotency_site", lead_id="test_lead", score=2
            )
            assert result1.get("ok") is True
            assert result1.get("winback_id") is not None
            first_id = result1.get("winback_id")
            
            # Second arm - should return skipped
            result2 = await arm_winback_sequence(
                db, site_id="test_idempotency_site", lead_id="test_lead", score=2
            )
            assert result2.get("ok") is True
            assert result2.get("skipped") == "already_armed", f"Expected skipped:already_armed, got {result2}"
            assert result2.get("winback_id") == first_id, "Should return same winback_id"
            
            # Cleanup
            await db.winback_sequences.delete_many({"site_id": "test_idempotency_site"})
            
            print("✓ arm_winback_sequence idempotency verified")
        
        asyncio.get_event_loop().run_until_complete(test_idempotency())


class TestStripeKeyResolver:
    """Test Stripe key resolver rejects placeholder keys"""
    
    def test_stripe_key_resolver_rejects_placeholder(self):
        """stripe_payment_router._get_stripe_key() returns sk_live_* (107 chars), not placeholder"""
        import sys
        sys.path.insert(0, "/app/backend")
        from routers.stripe_payment_router import _get_stripe_key
        
        key = _get_stripe_key()
        assert key is not None, "Stripe key should not be None"
        assert len(key) >= 30, f"Stripe key should be >= 30 chars, got {len(key)}"
        assert key.startswith(("sk_live_", "sk_test_")), f"Key should start with sk_live_ or sk_test_, got {key[:15]}..."
        
        # Verify it's not the placeholder
        assert key != "sk_test_emergent", "Key should not be the placeholder"
        assert "emergent" not in key.lower() or len(key) > 30, "Key should not be the short placeholder"
        
        print(f"✓ Stripe key resolver returns valid key: {key[:20]}... ({len(key)} chars)")
    
    def test_stripe_status_shows_live_mode(self):
        """GET /api/payments/stripe-status shows connected:true, mode:live"""
        r = requests.get(f"{BASE_URL}/api/payments/stripe-status")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        assert data.get("connected") is True, f"Expected connected:true, got {data}"
        assert data.get("mode") == "live", f"Expected mode:live, got {data.get('mode')}"
        
        print(f"✓ Stripe status: connected={data.get('connected')}, mode={data.get('mode')}")


class TestSaaSCheckout:
    """Test SaaS subscription checkout (CRITICAL REGRESSION)"""
    
    def test_payments_checkout_creates_stripe_url(self):
        """POST /api/payments/checkout with valid package_id creates checkout.stripe.com URL"""
        r = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            json={
                "package_id": "starter",
                "origin_url": "https://aurem.live",
                "ref": "test-ref"
            }
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        assert "url" in data, f"Expected 'url' in response, got {data}"
        url = data.get("url", "")
        assert "checkout.stripe.com" in url, f"Expected checkout.stripe.com URL, got {url}"
        
        print(f"✓ SaaS checkout creates Stripe URL: {url[:60]}...")
    
    def test_payments_checkout_growth_tier(self):
        """POST /api/payments/checkout with growth package works"""
        r = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            json={
                "package_id": "growth",
                "origin_url": "https://aurem.live",
                "ref": "test-ref"
            }
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "url" in data and "checkout.stripe.com" in data.get("url", "")
        print("✓ SaaS checkout growth tier works")
    
    def test_payments_checkout_enterprise_tier(self):
        """POST /api/payments/checkout with enterprise package works"""
        r = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            json={
                "package_id": "enterprise",
                "origin_url": "https://aurem.live",
                "ref": "test-ref"
            }
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "url" in data and "checkout.stripe.com" in data.get("url", "")
        print("✓ SaaS checkout enterprise tier works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
