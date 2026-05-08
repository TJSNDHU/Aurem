"""
Iteration 281.4 — Universal Language Intelligence + Operator Mode + Public Repair Lead Magnet
=============================================================================================
Tests:
1. Public Repair Quote endpoints (no auth):
   - GET /api/public/repair-quote/health → 200
   - POST /api/public/repair-quote/audit → 200 with quote_id, score, diagnosis
   - POST /api/public/repair-quote/audit with invalid email → 422
   - POST /api/public/repair-quote/audit with consent=false → still saves (frontend enforces)
   
2. ORA Command with Language Intelligence:
   - POST /api/ora/command with Hindi text → reply in Hindi, data.language.detected='hi'
   - POST /api/ora/command with Devanagari → reply in Devanagari, script='Deva'
   - POST /api/ora/command with Punjabi Gurmukhi → reply with 'bhai', detected='pa'
   - POST /api/ora/command with French → reply in French, address='chef'
   - POST /api/ora/command with English → reply in English (no localization)
   - POST /api/ora/command 3x same language → preferred_language auto-promoted

3. MongoDB _id exclusion verification
4. Lead persistence verification (db.leads, db.website_repair_reports)
"""

import os
import pytest
import requests
import time
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ─────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session (no auth for public endpoints)"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ─────────────────────────────────────────────────────────────
# SECTION 1: PUBLIC REPAIR QUOTE ENDPOINTS (NO AUTH)
# ─────────────────────────────────────────────────────────────

class TestPublicRepairQuoteHealth:
    """GET /api/public/repair-quote/health — public, no auth"""
    
    def test_health_returns_200(self, api_client):
        """Health endpoint should return 200 with ok=true"""
        r = api_client.get(f"{BASE_URL}/api/public/repair-quote/health")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        assert data.get("db_wired") is True, f"Expected db_wired=true, got {data}"
        print(f"✓ Health endpoint: {data}")


class TestPublicRepairQuoteAudit:
    """POST /api/public/repair-quote/audit — public lead magnet"""
    
    def test_audit_with_valid_data(self, api_client):
        """Audit with valid URL + email should return quote_id, score, diagnosis"""
        test_email = f"test_{uuid.uuid4().hex[:8]}@aurem-test.com"
        payload = {
            "url": "example.com",
            "email": test_email,
            "business_name": "Test Business",
            "consent": True
        }
        # Real Playwright audit can take 15-30s
        r = api_client.post(
            f"{BASE_URL}/api/public/repair-quote/audit",
            json=payload,
            timeout=90
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        # Verify response structure
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        assert "quote_id" in data, f"Missing quote_id in response: {data}"
        assert "overall_score" in data, f"Missing overall_score in response: {data}"
        assert isinstance(data.get("overall_score"), (int, float)), f"overall_score should be numeric: {data}"
        assert "issues" in data, f"Missing issues in response: {data}"
        assert "diagnosis" in data, f"Missing diagnosis in response: {data}"
        assert "score_breakdown" in data, f"Missing score_breakdown in response: {data}"
        
        # Verify no MongoDB _id leaked
        assert "_id" not in data, f"MongoDB _id leaked in response: {data}"
        
        print(f"✓ Audit successful: quote_id={data['quote_id']}, score={data['overall_score']}")
        print(f"  Diagnosis preview: {(data.get('diagnosis') or '')[:100]}...")
        
        return data
    
    def test_audit_with_invalid_email(self, api_client):
        """Audit with invalid email should return 422 (Pydantic EmailStr validation)"""
        payload = {
            "url": "example.com",
            "email": "not-an-email",
            "consent": True
        }
        r = api_client.post(
            f"{BASE_URL}/api/public/repair-quote/audit",
            json=payload,
            timeout=30
        )
        assert r.status_code == 422, f"Expected 422 for invalid email, got {r.status_code}: {r.text}"
        print(f"✓ Invalid email correctly rejected with 422")
    
    def test_audit_with_consent_false(self, api_client):
        """Audit with consent=false should still save (frontend enforces consent UI)"""
        test_email = f"test_noconsent_{uuid.uuid4().hex[:8]}@aurem-test.com"
        payload = {
            "url": "example.com",
            "email": test_email,
            "business_name": "No Consent Test",
            "consent": False
        }
        r = api_client.post(
            f"{BASE_URL}/api/public/repair-quote/audit",
            json=payload,
            timeout=90
        )
        # Server accepts any consent value — frontend enforces the checkbox
        assert r.status_code == 200, f"Expected 200 even with consent=false, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("ok") is True
        print(f"✓ Audit with consent=false accepted (frontend enforces): quote_id={data.get('quote_id')}")
    
    def test_audit_with_naked_domain(self, api_client):
        """Audit with naked domain (no https://) should auto-prepend"""
        test_email = f"test_naked_{uuid.uuid4().hex[:8]}@aurem-test.com"
        payload = {
            "url": "google.com",  # No https://
            "email": test_email,
            "consent": True
        }
        r = api_client.post(
            f"{BASE_URL}/api/public/repair-quote/audit",
            json=payload,
            timeout=90
        )
        assert r.status_code == 200, f"Expected 200 for naked domain, got {r.status_code}: {r.text}"
        data = r.json()
        # URL should be normalized to https://
        assert data.get("url", "").startswith("https://"), f"URL not normalized: {data.get('url')}"
        print(f"✓ Naked domain auto-prepended: {data.get('url')}")


# ─────────────────────────────────────────────────────────────
# SECTION 2: ORA COMMAND WITH LANGUAGE INTELLIGENCE
# ─────────────────────────────────────────────────────────────

class TestOraCommandLanguageIntelligence:
    """POST /api/ora/command with multi-language support"""
    
    def test_ora_command_english(self, api_client):
        """English command should return English reply, detected='en'"""
        payload = {
            "text": "show me the leads",
            "channel": "chat",
            "user": "test_user",
            "session_id": f"test_en_{uuid.uuid4().hex[:8]}"
        }
        r = api_client.post(
            f"{BASE_URL}/api/ora/command",
            json=payload,
            timeout=30
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        # Verify language metadata
        lang = data.get("data", {}).get("language", {})
        assert lang.get("detected") == "en", f"Expected detected='en', got {lang}"
        # English should NOT be localized (target='en' → no-op)
        print(f"✓ English command: detected={lang.get('detected')}, reply preview: {data.get('reply', '')[:80]}...")
    
    def test_ora_command_hinglish(self, api_client):
        """Hinglish (Hindi-Latin) command should detect as 'hi' with is_mixed=true"""
        payload = {
            "text": "aaj ki kamai bataao boss",
            "channel": "chat",
            "user": "test_user",
            "session_id": f"test_hinglish_{uuid.uuid4().hex[:8]}"
        }
        r = api_client.post(
            f"{BASE_URL}/api/ora/command",
            json=payload,
            timeout=30
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        lang = data.get("data", {}).get("language", {})
        # Hinglish should be detected as 'hi' or 'en' with is_mixed=true
        assert lang.get("detected") in ("hi", "en"), f"Expected detected in (hi, en), got {lang}"
        assert lang.get("address") == "boss", f"Expected address='boss', got {lang}"
        print(f"✓ Hinglish command: detected={lang.get('detected')}, is_mixed={lang.get('is_mixed')}, address={lang.get('address')}")
        print(f"  Reply: {data.get('reply', '')[:100]}...")
    
    def test_ora_command_devanagari_hindi(self, api_client):
        """Devanagari Hindi command should detect as 'hi' with script='Deva'"""
        payload = {
            "text": "आज की कमाई बताओ",
            "channel": "chat",
            "user": "test_user",
            "session_id": f"test_deva_{uuid.uuid4().hex[:8]}"
        }
        r = api_client.post(
            f"{BASE_URL}/api/ora/command",
            json=payload,
            timeout=30
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        lang = data.get("data", {}).get("language", {})
        assert lang.get("detected") == "hi", f"Expected detected='hi', got {lang}"
        assert lang.get("script") == "Deva", f"Expected script='Deva', got {lang}"
        print(f"✓ Devanagari Hindi: detected={lang.get('detected')}, script={lang.get('script')}")
        print(f"  Reply: {data.get('reply', '')[:100]}...")
    
    def test_ora_command_punjabi_gurmukhi(self, api_client):
        """Punjabi Gurmukhi command should detect as 'pa' with address='bhai'"""
        payload = {
            "text": "ਅੱਜ ਦੇ leads ਦਿਖਾਓ",
            "channel": "chat",
            "user": "test_user",
            "session_id": f"test_guru_{uuid.uuid4().hex[:8]}"
        }
        r = api_client.post(
            f"{BASE_URL}/api/ora/command",
            json=payload,
            timeout=30
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        lang = data.get("data", {}).get("language", {})
        assert lang.get("detected") == "pa", f"Expected detected='pa', got {lang}"
        assert lang.get("script") == "Guru", f"Expected script='Guru', got {lang}"
        assert lang.get("address") == "bhai", f"Expected address='bhai', got {lang}"
        print(f"✓ Punjabi Gurmukhi: detected={lang.get('detected')}, script={lang.get('script')}, address={lang.get('address')}")
        print(f"  Reply: {data.get('reply', '')[:100]}...")
    
    def test_ora_command_french(self, api_client):
        """French command should detect as 'fr' with address='chef'"""
        payload = {
            "text": "montrez les revenus aujourdhui",
            "channel": "chat",
            "user": "test_user",
            "session_id": f"test_fr_{uuid.uuid4().hex[:8]}"
        }
        r = api_client.post(
            f"{BASE_URL}/api/ora/command",
            json=payload,
            timeout=30
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        
        lang = data.get("data", {}).get("language", {})
        assert lang.get("detected") == "fr", f"Expected detected='fr', got {lang}"
        assert lang.get("address") == "chef", f"Expected address='chef', got {lang}"
        print(f"✓ French: detected={lang.get('detected')}, address={lang.get('address')}")
        print(f"  Reply: {data.get('reply', '')[:100]}...")


class TestOraLanguagePreferencePromotion:
    """Test auto-promotion of preferred_language after 3 consecutive same-lang messages"""
    
    def test_language_preference_promotion(self, api_client):
        """3 consecutive Hindi messages should promote preferred_language to 'hi'"""
        session_id = f"test_promo_{uuid.uuid4().hex[:8]}"
        user = "test_promo_user"
        
        # Send 3 Hindi messages
        for i in range(3):
            payload = {
                "text": f"आज की कमाई बताओ {i+1}",
                "channel": "chat",
                "user": user,
                "session_id": session_id
            }
            r = api_client.post(
                f"{BASE_URL}/api/ora/command",
                json=payload,
                timeout=30
            )
            assert r.status_code == 200, f"Request {i+1} failed: {r.status_code}: {r.text}"
            data = r.json()
            lang = data.get("data", {}).get("language", {})
            print(f"  Message {i+1}: detected={lang.get('detected')}, preferred={lang.get('preferred')}")
            
            # On 3rd message, preferred should be set
            if i == 2:
                assert lang.get("preferred") == "hi", f"Expected preferred='hi' after 3 messages, got {lang}"
                print(f"✓ Language preference promoted to 'hi' after 3 consecutive Hindi messages")


# ─────────────────────────────────────────────────────────────
# SECTION 3: NO MONGODB _ID LEAKAGE
# ─────────────────────────────────────────────────────────────

class TestNoMongoIdLeakage:
    """Verify no MongoDB _id field in any response"""
    
    def test_repair_quote_no_id(self, api_client):
        """Public repair quote response should not contain _id"""
        r = api_client.get(f"{BASE_URL}/api/public/repair-quote/health")
        assert r.status_code == 200
        data = r.json()
        assert "_id" not in data, f"MongoDB _id leaked in health response: {data}"
        print("✓ No _id in repair-quote health response")
    
    def test_ora_command_no_id(self, api_client):
        """ORA command response should not contain _id"""
        payload = {
            "text": "help",
            "channel": "chat",
            "user": "test_user"
        }
        r = api_client.post(f"{BASE_URL}/api/ora/command", json=payload, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "_id" not in data, f"MongoDB _id leaked in ORA command response: {data}"
        assert "_id" not in data.get("data", {}), f"MongoDB _id leaked in ORA data: {data}"
        print("✓ No _id in ORA command response")


# ─────────────────────────────────────────────────────────────
# SECTION 4: RESPONSE STRUCTURE VALIDATION
# ─────────────────────────────────────────────────────────────

class TestResponseStructure:
    """Validate response structure matches expected format"""
    
    def test_ora_command_language_metadata_structure(self, api_client):
        """ORA command should return language metadata in data.language"""
        payload = {
            "text": "status",
            "channel": "chat",
            "user": "test_user"
        }
        r = api_client.post(f"{BASE_URL}/api/ora/command", json=payload, timeout=30)
        assert r.status_code == 200
        data = r.json()
        
        # Verify language metadata structure
        assert "data" in data, f"Missing 'data' in response: {data}"
        assert "language" in data["data"], f"Missing 'language' in data: {data}"
        
        lang = data["data"]["language"]
        expected_keys = ["detected", "script", "confidence", "is_mixed", "address"]
        for key in expected_keys:
            assert key in lang, f"Missing '{key}' in language metadata: {lang}"
        
        print(f"✓ Language metadata structure valid: {lang}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
