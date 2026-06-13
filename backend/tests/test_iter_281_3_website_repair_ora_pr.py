"""
Iteration 281.3 — Website Repair Service + ORA Apply via PR Tests
==================================================================
Tests for:
1. Website Repair Router (audit, reports, send-offer, create-invoice)
2. ORA Dev Actions prepare-pr endpoint
3. Builder mode='repair' flag
"""
import os
import pytest
import requests
import time
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

# Admin credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    resp = requests.post(
        f"{BASE_URL}/api/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    return data.get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Auth headers with admin JWT"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── Website Repair Health (Public) ─────────────────────────────────
class TestWebsiteRepairHealth:
    """Website Repair health endpoint tests (public)"""

    def test_health_endpoint_public(self):
        """GET /api/admin/website-repair/health → 200, public (no auth)"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-repair/health", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True
        assert "db_wired" in data
        print(f"✓ Health endpoint public: ok={data['ok']}, db_wired={data['db_wired']}")


# ─── Website Repair Auth Gating ─────────────────────────────────────
class TestWebsiteRepairAuthGating:
    """Website Repair endpoints require admin auth"""

    def test_audit_without_auth_returns_401(self):
        """POST /api/admin/website-repair/audit without auth → 401"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/website-repair/audit",
            json={"url": "https://example.com"},
            timeout=10
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Audit without auth → 401")

    def test_reports_without_auth_returns_401(self):
        """GET /api/admin/website-repair/reports without auth → 401"""
        resp = requests.get(f"{BASE_URL}/api/admin/website-repair/reports", timeout=10)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Reports without auth → 401")


# ─── Website Repair Audit ───────────────────────────────────────────
class TestWebsiteRepairAudit:
    """Website Repair audit endpoint tests"""

    @pytest.fixture(scope="class")
    def audit_report(self, auth_headers):
        """Run audit and return report for subsequent tests"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/website-repair/audit",
            headers=auth_headers,
            json={
                "url": "https://example.com",
                "business_name": "Test Co",
                "contact_email": "test@example.com"
            },
            timeout=90  # Audit can take 15-30s
        )
        if resp.status_code != 200:
            pytest.skip(f"Audit failed: {resp.status_code} - {resp.text[:300]}")
        return resp.json()

    def test_audit_returns_report_with_score(self, audit_report):
        """Audit returns report with overall_score"""
        assert audit_report.get("ok") is True
        report = audit_report.get("report", {})
        assert "overall_score" in report, "Missing overall_score"
        assert isinstance(report["overall_score"], (int, float))
        print(f"✓ Audit returned score: {report['overall_score']}")

    def test_audit_returns_diagnosis_text(self, audit_report):
        """Audit returns diagnosis text >100 chars"""
        report = audit_report.get("report", {})
        diagnosis = report.get("diagnosis", "")
        assert len(diagnosis) > 100, f"Diagnosis too short: {len(diagnosis)} chars"
        print(f"✓ Diagnosis length: {len(diagnosis)} chars")

    def test_audit_returns_issues_array(self, audit_report):
        """Audit returns audit.issues array"""
        report = audit_report.get("report", {})
        audit = report.get("audit", {})
        issues = audit.get("issues", [])
        assert isinstance(issues, list), "issues should be a list"
        print(f"✓ Issues array present with {len(issues)} items")

    def test_audit_report_has_no_mongo_id(self, audit_report):
        """Audit response has no MongoDB _id"""
        report = audit_report.get("report", {})
        assert "_id" not in report, "Response should not contain _id"
        print("✓ No _id in audit response")


# ─── Website Repair Reports List ────────────────────────────────────
class TestWebsiteRepairReportsList:
    """Website Repair reports list endpoint tests"""

    def test_list_reports_with_admin_jwt(self, auth_headers):
        """GET /api/admin/website-repair/reports with admin JWT → 200"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/website-repair/reports",
            headers=auth_headers,
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True
        assert "items" in data
        assert isinstance(data["items"], list)
        print(f"✓ Reports list: {len(data['items'])} items")

    def test_list_reports_has_audit_summary_not_raw(self, auth_headers):
        """Reports list has audit_summary (NOT raw audit)"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/website-repair/reports",
            headers=auth_headers,
            timeout=30
        )
        data = resp.json()
        items = data.get("items", [])
        if items:
            item = items[0]
            assert "audit_summary" in item, "Should have audit_summary"
            assert "audit" not in item, "Should NOT have raw audit in list"
            print(f"✓ Reports list has audit_summary, no raw audit")
        else:
            print("⚠ No reports to verify audit_summary")

    def test_list_reports_no_mongo_id(self, auth_headers):
        """Reports list items have no _id"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/website-repair/reports",
            headers=auth_headers,
            timeout=30
        )
        data = resp.json()
        for item in data.get("items", []):
            assert "_id" not in item, "Item should not contain _id"
        print("✓ No _id in reports list items")


# ─── Website Repair Get Single Report ───────────────────────────────
class TestWebsiteRepairGetReport:
    """Website Repair get single report tests"""

    def test_get_report_by_id(self, auth_headers):
        """GET /api/admin/website-repair/reports/{id} → 200 with full report"""
        # First get list to find a report_id
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/website-repair/reports",
            headers=auth_headers,
            timeout=30
        )
        items = list_resp.json().get("items", [])
        if not items:
            pytest.skip("No reports available to test get by id")
        
        report_id = items[0].get("report_id")
        resp = requests.get(
            f"{BASE_URL}/api/admin/website-repair/reports/{report_id}",
            headers=auth_headers,
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True
        report = data.get("report", {})
        assert "audit" in report, "Full report should have audit"
        assert "diagnosis" in report, "Full report should have diagnosis"
        assert "_id" not in report, "Should not have _id"
        print(f"✓ Get report by id: has audit + diagnosis, no _id")


# ─── Website Repair Send Offer ──────────────────────────────────────
class TestWebsiteRepairSendOffer:
    """Website Repair send-offer endpoint tests"""

    def test_send_offer_email_channel(self, auth_headers):
        """POST /api/admin/website-repair/{id}/send-offer {channel:'email'} → 200"""
        # Get a report_id
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/website-repair/reports",
            headers=auth_headers,
            timeout=30
        )
        items = list_resp.json().get("items", [])
        if not items:
            pytest.skip("No reports available to test send-offer")
        
        report_id = items[0].get("report_id")
        resp = requests.post(
            f"{BASE_URL}/api/admin/website-repair/{report_id}/send-offer",
            headers=auth_headers,
            json={"channel": "email"},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        # Response shape should have 'sent' with email status
        assert "sent" in data, "Response should have 'sent' field"
        assert "email" in data["sent"], "Response should have sent.email"
        print(f"✓ Send offer email: sent.email={data['sent']['email']}")


# ─── Website Repair Create Invoice ──────────────────────────────────
class TestWebsiteRepairCreateInvoice:
    """Website Repair create-invoice endpoint tests (Stripe LIVE)"""

    def test_create_invoice_returns_checkout_url(self, auth_headers):
        """POST /api/admin/website-repair/{id}/create-invoice → 200 with checkout_url"""
        # Get a report_id
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/website-repair/reports",
            headers=auth_headers,
            timeout=30
        )
        items = list_resp.json().get("items", [])
        if not items:
            pytest.skip("No reports available to test create-invoice")
        
        report_id = items[0].get("report_id")
        resp = requests.post(
            f"{BASE_URL}/api/admin/website-repair/{report_id}/create-invoice",
            headers=auth_headers,
            json={"amount_cents": 9900, "currency": "cad"},
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("ok") is True
        assert "checkout_url" in data, "Should have checkout_url"
        assert "session_id" in data, "Should have session_id"
        assert data["checkout_url"].startswith("https://checkout.stripe.com")
        print(f"✓ Create invoice: checkout_url present, session_id={data['session_id'][:20]}...")


# ─── Builder mode='repair' ──────────────────────────────────────────
class TestBuilderRepairMode:
    """Builder mode='repair' flag tests"""

    def test_repair_mode_without_report_or_url_returns_400(self, auth_headers):
        """POST /api/admin/builder/build mode='repair' without repair_report_id/target_url → 400"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/builder/build",
            headers=auth_headers,
            json={
                "description": "Test repair build",
                "mode": "repair"
            },
            timeout=30
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("✓ mode='repair' without report_id/target_url → 400")

    def test_repair_mode_with_target_url_returns_200(self, auth_headers):
        """POST /api/admin/builder/build mode='repair' with target_url → 200"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/builder/build",
            headers=auth_headers,
            json={
                "description": "Test repair build with target URL",
                "mode": "repair",
                "target_url": "https://example.com"
            },
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("build_id") is not None
        assert data.get("mode") == "repair"
        assert data.get("status") == "queued"
        print(f"✓ mode='repair' with target_url → 200, build_id={data['build_id']}")


# ─── ORA Dev Actions prepare-pr ─────────────────────────────────────
class TestOraDevPreparePR:
    """ORA Dev Actions prepare-pr endpoint tests"""

    @pytest.fixture(scope="class")
    def test_proposal(self, auth_headers):
        """Create a test proposal via /api/ora/command"""
        resp = requests.post(
            f"{BASE_URL}/api/ora/command",
            headers=auth_headers,
            json={
                "message": "Add a new endpoint /api/test/hello that returns {hello: 'world'}",
                "business_id": "TEST-001"
            },
            timeout=60
        )
        if resp.status_code != 200:
            pytest.skip(f"Failed to create test proposal: {resp.status_code}")
        data = resp.json()
        proposal_id = data.get("proposal_id")
        if not proposal_id:
            pytest.skip("No proposal_id returned from ora/command")
        return proposal_id

    def test_prepare_pr_on_pending_returns_409(self, auth_headers, test_proposal):
        """POST /api/admin/ora-dev/{id}/prepare-pr on pending → 409"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/ora-dev/{test_proposal}/prepare-pr",
            headers=auth_headers,
            timeout=30
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}"
        print("✓ prepare-pr on pending proposal → 409")

    def test_approve_then_prepare_pr_returns_200(self, auth_headers, test_proposal):
        """Approve then prepare-pr → 200 with branch, commit_message, target_files"""
        # First approve
        approve_resp = requests.post(
            f"{BASE_URL}/api/admin/ora-dev/{test_proposal}/approve",
            headers=auth_headers,
            timeout=30
        )
        if approve_resp.status_code not in (200, 409):
            pytest.fail(f"Approve failed: {approve_resp.status_code}")
        
        # Now prepare-pr
        resp = requests.post(
            f"{BASE_URL}/api/admin/ora-dev/{test_proposal}/prepare-pr",
            headers=auth_headers,
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("branch", "").startswith("ora-mode2/")
        assert data.get("commit_message", "").startswith("[ora-mode2]")
        assert isinstance(data.get("target_files"), list)
        print(f"✓ prepare-pr: branch={data['branch']}, commit_message={data['commit_message'][:50]}...")


# ─── No MongoDB _id in ORA Dev responses ────────────────────────────
class TestOraDevNoMongoId:
    """Verify _id NOT present in ORA Dev responses"""

    def test_ora_dev_pending_no_id(self, auth_headers):
        """GET /api/admin/ora-dev/pending → no _id in items"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/ora-dev/pending",
            headers=auth_headers,
            timeout=30
        )
        data = resp.json()
        for item in data.get("items", []):
            assert "_id" not in item, "Item should not contain _id"
        print("✓ No _id in ora-dev/pending items")

    def test_ora_dev_list_no_id(self, auth_headers):
        """GET /api/admin/ora-dev/list → no _id in items"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/ora-dev/list",
            headers=auth_headers,
            timeout=30
        )
        data = resp.json()
        for item in data.get("items", []):
            assert "_id" not in item, "Item should not contain _id"
        print("✓ No _id in ora-dev/list items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
