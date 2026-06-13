"""
Iteration 176 - Document Skills + Forensic Miner Queue Outreach Tests
=====================================================================
Tests for:
1. POST /api/docs/generate — generates DOCX, PPTX, and PDF documents
2. POST /api/docs/proposal — auto-generates welcome proposal as DOCX
3. POST /api/docs/campaign-report — generates campaign performance PDF
4. POST /api/docs/health-deck — generates monthly health PPTX
5. GET /api/docs/download/{doc_id} — downloads generated document file
6. GET /api/docs/history — lists document generation history
7. POST /api/forensic-miner/queue-outreach — queues outreach for a lead
8. GET /api/forensic-miner/outreach-status — gets outreach queue status
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestDocumentSkillsAuthGuards:
    """Test that all document endpoints require authentication."""
    
    def test_generate_requires_auth(self):
        """POST /api/docs/generate requires auth."""
        response = requests.post(f"{BASE_URL}/api/docs/generate", json={
            "title": "Test", "sections": [], "format": "docx"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/docs/generate requires auth")
    
    def test_proposal_requires_auth(self):
        """POST /api/docs/proposal requires auth."""
        response = requests.post(f"{BASE_URL}/api/docs/proposal", json={
            "client_name": "Test", "business": "Test Co"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/docs/proposal requires auth")
    
    def test_campaign_report_requires_auth(self):
        """POST /api/docs/campaign-report requires auth."""
        response = requests.post(f"{BASE_URL}/api/docs/campaign-report", json={
            "campaign_name": "Test Campaign"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/docs/campaign-report requires auth")
    
    def test_health_deck_requires_auth(self):
        """POST /api/docs/health-deck requires auth."""
        response = requests.post(f"{BASE_URL}/api/docs/health-deck", json={
            "shop": "test-shop"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/docs/health-deck requires auth")
    
    def test_download_requires_auth(self):
        """GET /api/docs/download/{doc_id} requires auth."""
        response = requests.get(f"{BASE_URL}/api/docs/download/test_doc_id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/docs/download requires auth")
    
    def test_history_requires_auth(self):
        """GET /api/docs/history requires auth."""
        response = requests.get(f"{BASE_URL}/api/docs/history")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/docs/history requires auth")


class TestDocumentGeneration:
    """Test document generation endpoints."""
    
    def test_generate_docx(self, auth_headers):
        """POST /api/docs/generate - generate DOCX document."""
        response = requests.post(
            f"{BASE_URL}/api/docs/generate",
            headers=auth_headers,
            json={
                "title": "Test DOCX Document",
                "sections": [
                    {"heading": "Introduction", "content": "This is a test document."},
                    {"heading": "Features", "content": ["Feature 1", "Feature 2"], "style": "bullet"}
                ],
                "format": "docx",
                "doc_type": "test_document"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "doc_id" in data, "Response should contain doc_id"
        assert data.get("format") == "docx", "Format should be docx"
        assert data.get("generated") == True, "Generated should be True"
        print(f"PASS: Generated DOCX - doc_id: {data.get('doc_id')}")
        return data.get("doc_id")
    
    def test_generate_pptx(self, auth_headers):
        """POST /api/docs/generate - generate PPTX document."""
        response = requests.post(
            f"{BASE_URL}/api/docs/generate",
            headers=auth_headers,
            json={
                "title": "Test PPTX Presentation",
                "sections": [
                    {"heading": "Slide 1", "content": "Introduction content"},
                    {"heading": "Slide 2", "content": ["Point 1", "Point 2", "Point 3"]}
                ],
                "format": "pptx",
                "doc_type": "test_presentation"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "doc_id" in data, "Response should contain doc_id"
        assert data.get("format") == "pptx", "Format should be pptx"
        assert data.get("generated") == True, "Generated should be True"
        assert "slides" in data, "Response should contain slides count"
        print(f"PASS: Generated PPTX - doc_id: {data.get('doc_id')}, slides: {data.get('slides')}")
        return data.get("doc_id")
    
    def test_generate_pdf(self, auth_headers):
        """POST /api/docs/generate - generate PDF document."""
        response = requests.post(
            f"{BASE_URL}/api/docs/generate",
            headers=auth_headers,
            json={
                "title": "Test PDF Report",
                "sections": [
                    {"heading": "Summary", "content": "This is a test PDF report."},
                    {"heading": "Data", "content": [
                        {"metric": "Revenue", "value": "$10,000"},
                        {"metric": "Users", "value": "500"}
                    ], "style": "table"}
                ],
                "format": "pdf",
                "doc_type": "test_report"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "doc_id" in data, "Response should contain doc_id"
        assert data.get("format") == "pdf", "Format should be pdf"
        assert data.get("generated") == True, "Generated should be True"
        print(f"PASS: Generated PDF - doc_id: {data.get('doc_id')}")
        return data.get("doc_id")
    
    def test_generate_invalid_format(self, auth_headers):
        """POST /api/docs/generate - invalid format returns 400."""
        response = requests.post(
            f"{BASE_URL}/api/docs/generate",
            headers=auth_headers,
            json={
                "title": "Test",
                "sections": [],
                "format": "invalid_format"
            }
        )
        assert response.status_code == 400, f"Expected 400 for invalid format, got {response.status_code}"
        print("PASS: Invalid format returns 400")


class TestDocumentProposal:
    """Test proposal generation endpoint."""
    
    def test_generate_proposal(self, auth_headers):
        """POST /api/docs/proposal - generate client proposal DOCX."""
        response = requests.post(
            f"{BASE_URL}/api/docs/proposal",
            headers=auth_headers,
            json={
                "client_name": "Test Client",
                "business": "Test Business Inc",
                "services": ["SEO Optimization", "Content Marketing", "Social Media"]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "doc_id" in data, "Response should contain doc_id"
        assert data.get("format") == "docx", "Proposal should be DOCX format"
        assert data.get("generated") == True, "Generated should be True"
        assert "Welcome Proposal" in data.get("title", ""), "Title should contain 'Welcome Proposal'"
        print(f"PASS: Generated proposal - doc_id: {data.get('doc_id')}, title: {data.get('title')}")
        return data.get("doc_id")


class TestCampaignReport:
    """Test campaign report generation endpoint."""
    
    def test_generate_campaign_report(self, auth_headers):
        """POST /api/docs/campaign-report - generate campaign performance PDF."""
        response = requests.post(
            f"{BASE_URL}/api/docs/campaign-report",
            headers=auth_headers,
            json={
                "campaign_name": "Q1 Marketing Campaign",
                "metrics": {
                    "posts_published": 25,
                    "impressions": 50000,
                    "clicks": 2500,
                    "conversions": 150,
                    "roi": "450%"
                }
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "doc_id" in data, "Response should contain doc_id"
        assert data.get("format") == "pdf", "Campaign report should be PDF format"
        assert data.get("generated") == True, "Generated should be True"
        assert "Campaign Report" in data.get("title", ""), "Title should contain 'Campaign Report'"
        print(f"PASS: Generated campaign report - doc_id: {data.get('doc_id')}, title: {data.get('title')}")
        return data.get("doc_id")


class TestHealthDeck:
    """Test health deck generation endpoint."""
    
    def test_generate_health_deck(self, auth_headers):
        """POST /api/docs/health-deck - generate monthly health PPTX."""
        response = requests.post(
            f"{BASE_URL}/api/docs/health-deck",
            headers=auth_headers,
            json={
                "shop": "test-store.myshopify.com",
                "metrics": {
                    "products": 100,
                    "avg_health_score": 85,
                    "seo_fixes_applied": 250,
                    "carts_recovered": 30,
                    "revenue_recovered": "$1,500"
                }
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "doc_id" in data, "Response should contain doc_id"
        assert data.get("format") == "pptx", "Health deck should be PPTX format"
        assert data.get("generated") == True, "Generated should be True"
        assert "Health Report" in data.get("title", ""), "Title should contain 'Health Report'"
        assert "slides" in data, "Response should contain slides count"
        print(f"PASS: Generated health deck - doc_id: {data.get('doc_id')}, slides: {data.get('slides')}")
        return data.get("doc_id")


class TestDocumentDownload:
    """Test document download endpoint."""
    
    def test_download_generated_document(self, auth_headers):
        """GET /api/docs/download/{doc_id} - download generated document."""
        # First generate a document
        gen_response = requests.post(
            f"{BASE_URL}/api/docs/generate",
            headers=auth_headers,
            json={
                "title": "Download Test Document",
                "sections": [{"heading": "Test", "content": "Test content"}],
                "format": "docx"
            }
        )
        assert gen_response.status_code == 200, f"Failed to generate document: {gen_response.text}"
        doc_id = gen_response.json().get("doc_id")
        
        # Now download it
        download_response = requests.get(
            f"{BASE_URL}/api/docs/download/{doc_id}",
            headers={"Authorization": auth_headers["Authorization"]}
        )
        assert download_response.status_code == 200, f"Expected 200, got {download_response.status_code}"
        assert len(download_response.content) > 0, "Downloaded file should have content"
        content_type = download_response.headers.get("content-type", "")
        assert "application/vnd.openxmlformats" in content_type or "application/octet-stream" in content_type, f"Unexpected content type: {content_type}"
        print(f"PASS: Downloaded document - doc_id: {doc_id}, size: {len(download_response.content)} bytes")
    
    def test_download_nonexistent_document(self, auth_headers):
        """GET /api/docs/download/{doc_id} - nonexistent document returns 404."""
        response = requests.get(
            f"{BASE_URL}/api/docs/download/nonexistent_doc_12345",
            headers={"Authorization": auth_headers["Authorization"]}
        )
        assert response.status_code == 404, f"Expected 404 for nonexistent doc, got {response.status_code}"
        print("PASS: Nonexistent document returns 404")


class TestDocumentHistory:
    """Test document history endpoint."""
    
    def test_get_document_history(self, auth_headers):
        """GET /api/docs/history - get document generation history."""
        response = requests.get(
            f"{BASE_URL}/api/docs/history",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "documents" in data, "Response should contain documents array"
        assert "count" in data, "Response should contain count"
        assert isinstance(data["documents"], list), "Documents should be a list"
        print(f"PASS: Got document history - count: {data.get('count')}")
        if data["documents"]:
            doc = data["documents"][0]
            print(f"  Latest doc: {doc.get('doc_id')} - {doc.get('type')} ({doc.get('format')})")


class TestForensicMinerOutreach:
    """Test Forensic Miner queue outreach endpoints."""
    
    def test_queue_outreach_requires_auth(self):
        """POST /api/forensic-miner/queue-outreach requires auth."""
        response = requests.post(f"{BASE_URL}/api/forensic-miner/queue-outreach", json={
            "domain": "test.com", "email": "test@test.com"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/forensic-miner/queue-outreach requires auth")
    
    def test_outreach_status_requires_auth(self):
        """GET /api/forensic-miner/outreach-status requires auth."""
        response = requests.get(f"{BASE_URL}/api/forensic-miner/outreach-status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/forensic-miner/outreach-status requires auth")
    
    def test_queue_outreach_with_email(self, auth_headers):
        """POST /api/forensic-miner/queue-outreach - queue outreach for lead with email."""
        response = requests.post(
            f"{BASE_URL}/api/forensic-miner/queue-outreach",
            headers=auth_headers,
            json={
                "domain": "test-lead-store.com",
                "email": "contact@test-lead-store.com",
                "phone": "",
                "health_score": 45,
                "issues": ["missing_meta_description", "no_alt_text"],
                "scan_id": "test_scan_123"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("queued") == True, "Should be queued"
        assert data.get("domain") == "test-lead-store.com", "Domain should match"
        assert "email" in data.get("channels", []), "Email should be in channels"
        assert data.get("status") == "queued", "Status should be queued"
        print(f"PASS: Queued outreach - domain: {data.get('domain')}, channels: {data.get('channels')}")
    
    def test_queue_outreach_with_phone(self, auth_headers):
        """POST /api/forensic-miner/queue-outreach - queue outreach with phone (adds WhatsApp)."""
        response = requests.post(
            f"{BASE_URL}/api/forensic-miner/queue-outreach",
            headers=auth_headers,
            json={
                "domain": "test-lead-with-phone.com",
                "email": "info@test-lead-with-phone.com",
                "phone": "+14165551234",
                "health_score": 35,
                "issues": ["missing_og_tags", "slow_page_speed"],
                "scan_id": "test_scan_456"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("queued") == True, "Should be queued"
        assert "email" in data.get("channels", []), "Email should be in channels"
        assert "whatsapp" in data.get("channels", []), "WhatsApp should be in channels when phone provided"
        print(f"PASS: Queued outreach with phone - channels: {data.get('channels')}")
    
    def test_get_outreach_status(self, auth_headers):
        """GET /api/forensic-miner/outreach-status - get outreach queue status."""
        response = requests.get(
            f"{BASE_URL}/api/forensic-miner/outreach-status",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "queue" in data, "Response should contain queue array"
        assert "count" in data, "Response should contain count"
        assert isinstance(data["queue"], list), "Queue should be a list"
        print(f"PASS: Got outreach status - count: {data.get('count')}")
        if data["queue"]:
            item = data["queue"][0]
            print(f"  Latest queued: {item.get('domain')} - status: {item.get('status')}, channels: {item.get('channels')}")


class TestEndToEndDocumentFlow:
    """Test complete document generation and download flow."""
    
    def test_full_proposal_flow(self, auth_headers):
        """Test complete flow: generate proposal -> verify in history -> download."""
        # 1. Generate proposal
        gen_response = requests.post(
            f"{BASE_URL}/api/docs/proposal",
            headers=auth_headers,
            json={
                "client_name": "E2E Test Client",
                "business": "E2E Test Business",
                "services": ["Service A", "Service B"]
            }
        )
        assert gen_response.status_code == 200, f"Failed to generate: {gen_response.text}"
        doc_id = gen_response.json().get("doc_id")
        print(f"Step 1: Generated proposal - doc_id: {doc_id}")
        
        # 2. Verify in history
        history_response = requests.get(
            f"{BASE_URL}/api/docs/history?limit=5",
            headers=auth_headers
        )
        assert history_response.status_code == 200
        history = history_response.json()
        doc_ids = [d.get("doc_id") for d in history.get("documents", [])]
        assert doc_id in doc_ids, f"Generated doc_id {doc_id} should be in history"
        print(f"Step 2: Verified in history - found {len(doc_ids)} documents")
        
        # 3. Download
        download_response = requests.get(
            f"{BASE_URL}/api/docs/download/{doc_id}",
            headers={"Authorization": auth_headers["Authorization"]}
        )
        assert download_response.status_code == 200
        assert len(download_response.content) > 1000, "Downloaded file should have substantial content"
        print(f"Step 3: Downloaded - size: {len(download_response.content)} bytes")
        
        print("PASS: Full proposal flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
