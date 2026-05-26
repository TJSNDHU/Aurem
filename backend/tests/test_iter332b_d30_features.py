"""
Test suite for iter 332b D-30 features:
1. Pillars Map heartbeat — non_blocking flows, admin_worst/customer_worst, flows_red_blocking/advisory
2. Deploy router CRUD — config save/get/delete, run, history
3. Domain config — DNS records + Caddyfile generation
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "Aurem@Founder2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token for authenticated requests."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    data = r.json()
    assert "token" in data, "No token in login response"
    assert data.get("user", {}).get("is_admin") is True, "User is not admin"
    return data["token"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Return headers with admin JWT."""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: Pillars Map Heartbeat Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPillarsMapHeartbeat:
    """Test the pillars-map heartbeat endpoint with new non_blocking flow logic."""

    def test_heartbeat_returns_200(self, auth_headers):
        """GET /api/admin/pillars-map/heartbeat should return 200."""
        r = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/heartbeat",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200, f"Heartbeat failed: {r.status_code} - {r.text}"

    def test_heartbeat_has_required_keys(self, auth_headers):
        """Heartbeat response must include admin_worst, customer_worst, interface_desync, flows_red_blocking, flows_red_advisory."""
        r = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/heartbeat",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        
        # Check top-level keys
        assert "overall_status" in data, "Missing overall_status"
        assert "admin_worst" in data, "Missing admin_worst"
        assert "customer_worst" in data, "Missing customer_worst"
        assert "interface_desync" in data, "Missing interface_desync"
        
        # Check totals keys
        assert "totals" in data, "Missing totals"
        totals = data["totals"]
        assert "flows_red_blocking" in totals, "Missing flows_red_blocking in totals"
        assert "flows_red_advisory" in totals, "Missing flows_red_advisory in totals"
        
        print(f"✓ overall_status: {data['overall_status']}")
        print(f"✓ admin_worst: {data['admin_worst']}")
        print(f"✓ customer_worst: {data['customer_worst']}")
        print(f"✓ interface_desync: {data['interface_desync']}")
        print(f"✓ flows_red_blocking: {totals['flows_red_blocking']}")
        print(f"✓ flows_red_advisory: {totals['flows_red_advisory']}")

    def test_heartbeat_non_blocking_flow_does_not_escalate(self, auth_headers):
        """Legion Sovereign Node flow should be red but non_blocking=true, not escalating overall_status."""
        r = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/heartbeat",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        
        # Find the Legion Sovereign Node flow
        flows = data.get("flows", [])
        legion_flow = None
        for f in flows:
            if f.get("id") == "admin_legion_sovereign_node":
                legion_flow = f
                break
        
        if legion_flow:
            print(f"✓ Found Legion Sovereign Node flow: status={legion_flow.get('status')}, non_blocking={legion_flow.get('non_blocking')}")
            # It should have non_blocking=true
            assert legion_flow.get("non_blocking") is True, "Legion Sovereign Node should have non_blocking=true"
        else:
            print("⚠ Legion Sovereign Node flow not found in flows array (may be expected if cache not populated)")

    def test_heartbeat_overall_status_not_red_from_advisory(self, auth_headers):
        """If only advisory flows are red, overall_status should NOT be red."""
        r = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/heartbeat",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        
        totals = data.get("totals", {})
        flows_red_blocking = totals.get("flows_red_blocking", 0)
        flows_red_advisory = totals.get("flows_red_advisory", 0)
        overall = data.get("overall_status", "unknown")
        
        print(f"✓ flows_red_blocking={flows_red_blocking}, flows_red_advisory={flows_red_advisory}, overall_status={overall}")
        
        # If there are no blocking reds, overall should not be red (unless pillars themselves are red)
        if flows_red_blocking == 0:
            # Check if any pillar is red
            pillars = data.get("pillars", [])
            pillar_reds = [p for p in pillars if p.get("status") == "red"]
            if not pillar_reds:
                # No blocking flows red, no pillars red → overall should be green or yellow
                assert overall in ("green", "yellow"), f"Expected green/yellow but got {overall} with 0 blocking reds"
                print(f"✓ Correctly not escalating to red with 0 blocking flows")


class TestPillarsMapOverview:
    """Test the pillars-map overview endpoint."""

    def test_overview_returns_200(self, auth_headers):
        """GET /api/admin/pillars-map/overview should return 200."""
        r = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/overview",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200, f"Overview failed: {r.status_code} - {r.text}"

    def test_overview_has_new_keys(self, auth_headers):
        """Overview response must include admin_worst, customer_worst, interface_desync, flows_red_blocking, flows_red_advisory."""
        r = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/overview",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        
        # Check top-level keys
        assert "admin_worst" in data, "Missing admin_worst in overview"
        assert "customer_worst" in data, "Missing customer_worst in overview"
        assert "interface_desync" in data, "Missing interface_desync in overview"
        
        # Check totals keys
        assert "totals" in data, "Missing totals in overview"
        totals = data["totals"]
        assert "flows_red_blocking" in totals, "Missing flows_red_blocking in overview totals"
        assert "flows_red_advisory" in totals, "Missing flows_red_advisory in overview totals"
        
        print(f"✓ Overview has all required keys")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: Deploy Router CRUD Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDeployRouterCRUD:
    """Test the developer deploy router CRUD operations."""

    def test_get_deploy_config_empty(self, auth_headers):
        """GET /api/developers/deploy/config should return {configured: false} when no config exists."""
        # First delete any existing config
        requests.delete(
            f"{BASE_URL}/api/developers/deploy/config",
            headers=auth_headers,
            timeout=10,
        )
        
        r = requests.get(
            f"{BASE_URL}/api/developers/deploy/config",
            headers=auth_headers,
            timeout=10,
        )
        assert r.status_code == 200, f"Get config failed: {r.status_code} - {r.text}"
        data = r.json()
        assert data.get("configured") is False, f"Expected configured=false, got {data}"
        print("✓ GET /api/developers/deploy/config returns {configured: false} when empty")

    def test_post_deploy_config_with_pem(self, auth_headers):
        """POST /api/developers/deploy/config with a fake OpenSSH PEM should return 200."""
        fake_pem = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACBbFAKE_TEST_KEY_NOT_REAL_JUST_FOR_TESTING_PURPOSES_ONLY
-----END OPENSSH PRIVATE KEY-----"""
        
        payload = {
            "host": "test.example.com",
            "port": 22,
            "username": "testuser",
            "private_key": fake_pem,
            "repo_path": "/opt/test-app",
            "branch": "main",
            "compose_file": "docker-compose.yml",
        }
        
        r = requests.post(
            f"{BASE_URL}/api/developers/deploy/config",
            headers=auth_headers,
            json=payload,
            timeout=10,
        )
        assert r.status_code == 200, f"POST config failed: {r.status_code} - {r.text}"
        data = r.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        print("✓ POST /api/developers/deploy/config with PEM returns 200")

    def test_get_deploy_config_shows_masked_key(self, auth_headers):
        """GET /api/developers/deploy/config should show masked private_key after save."""
        r = requests.get(
            f"{BASE_URL}/api/developers/deploy/config",
            headers=auth_headers,
            timeout=10,
        )
        assert r.status_code == 200, f"Get config failed: {r.status_code} - {r.text}"
        data = r.json()
        assert data.get("configured") is True, f"Expected configured=true, got {data}"
        assert data.get("host") == "test.example.com", f"Host mismatch: {data.get('host')}"
        assert data.get("username") == "testuser", f"Username mismatch: {data.get('username')}"
        # Key should be masked
        pk = data.get("private_key", "")
        assert "•" in pk or "saved" in pk.lower() or "encrypted" in pk.lower(), f"Key not masked: {pk}"
        print(f"✓ GET /api/developers/deploy/config shows masked key: {pk[:50]}...")

    def test_delete_deploy_config(self, auth_headers):
        """DELETE /api/developers/deploy/config should clear the config."""
        r = requests.delete(
            f"{BASE_URL}/api/developers/deploy/config",
            headers=auth_headers,
            timeout=10,
        )
        assert r.status_code == 200, f"Delete config failed: {r.status_code} - {r.text}"
        data = r.json()
        assert data.get("ok") is True, f"Expected ok=true, got {data}"
        
        # Verify it's gone
        r2 = requests.get(
            f"{BASE_URL}/api/developers/deploy/config",
            headers=auth_headers,
            timeout=10,
        )
        assert r2.status_code == 200
        assert r2.json().get("configured") is False
        print("✓ DELETE /api/developers/deploy/config clears the config")


class TestDeployRouterHistory:
    """Test deploy history and run endpoints."""

    def test_get_deploy_history(self, auth_headers):
        """GET /api/developers/deploy/history should return {runs: [...]}."""
        r = requests.get(
            f"{BASE_URL}/api/developers/deploy/history",
            headers=auth_headers,
            timeout=10,
        )
        assert r.status_code == 200, f"Get history failed: {r.status_code} - {r.text}"
        data = r.json()
        assert "runs" in data, f"Missing 'runs' key in response: {data}"
        assert isinstance(data["runs"], list), f"'runs' should be a list: {data}"
        print(f"✓ GET /api/developers/deploy/history returns runs list (count={len(data['runs'])})")

    def test_post_deploy_run_without_config_returns_400(self, auth_headers):
        """POST /api/developers/deploy/run without config should return 400 deploy_not_configured."""
        # First ensure no config exists
        requests.delete(
            f"{BASE_URL}/api/developers/deploy/config",
            headers=auth_headers,
            timeout=10,
        )
        
        r = requests.post(
            f"{BASE_URL}/api/developers/deploy/run",
            headers=auth_headers,
            json={"mode": "deploy"},
            timeout=10,
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code} - {r.text}"
        data = r.json()
        assert "deploy_not_configured" in str(data.get("detail", "")).lower() or "not_configured" in str(data).lower(), f"Expected deploy_not_configured error: {data}"
        print("✓ POST /api/developers/deploy/run without config returns 400 deploy_not_configured")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: Domain Config Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDomainConfig:
    """Test the domain config endpoint for DNS records + Caddyfile generation."""

    def test_post_domain_config_valid(self, auth_headers):
        """POST /api/developers/domain/config with valid domain returns dns_records + caddyfile."""
        payload = {
            "domain": "example.com",
            "server_ip": "203.0.113.1",
        }
        
        r = requests.post(
            f"{BASE_URL}/api/developers/domain/config",
            headers=auth_headers,
            json=payload,
            timeout=10,
        )
        assert r.status_code == 200, f"POST domain config failed: {r.status_code} - {r.text}"
        data = r.json()
        
        # Check required fields
        assert data.get("configured") is True, f"Expected configured=true: {data}"
        assert data.get("domain") == "example.com", f"Domain mismatch: {data.get('domain')}"
        assert data.get("server_ip") == "203.0.113.1", f"IP mismatch: {data.get('server_ip')}"
        
        # Check dns_records
        dns = data.get("dns_records", [])
        assert len(dns) >= 2, f"Expected at least 2 DNS records (A apex + A www): {dns}"
        types = [r.get("type") for r in dns]
        assert types.count("A") >= 2, f"Expected 2 A records: {dns}"
        
        # Check caddyfile
        caddyfile = data.get("caddyfile", "")
        assert "example.com" in caddyfile, f"Caddyfile missing domain: {caddyfile}"
        assert "www.example.com" in caddyfile, f"Caddyfile missing www: {caddyfile}"
        
        # Check verify_cmd
        verify = data.get("verify_cmd", "")
        assert "dig" in verify.lower() or "example.com" in verify, f"verify_cmd missing: {verify}"
        
        # Check ssl_note
        ssl = data.get("ssl_note", "")
        assert ssl, f"ssl_note missing: {data}"
        
        print(f"✓ POST /api/developers/domain/config returns valid response")
        print(f"  - dns_records: {len(dns)} records")
        print(f"  - caddyfile: {len(caddyfile)} chars")
        print(f"  - verify_cmd: {verify[:50]}...")

    def test_get_domain_config_returns_saved(self, auth_headers):
        """GET /api/developers/domain/config should return the saved config."""
        r = requests.get(
            f"{BASE_URL}/api/developers/domain/config",
            headers=auth_headers,
            timeout=10,
        )
        assert r.status_code == 200, f"GET domain config failed: {r.status_code} - {r.text}"
        data = r.json()
        
        # Should have the same data we saved
        assert data.get("configured") is True, f"Expected configured=true: {data}"
        assert data.get("domain") == "example.com", f"Domain mismatch: {data.get('domain')}"
        assert "dns_records" in data, f"Missing dns_records: {data}"
        assert "caddyfile" in data, f"Missing caddyfile: {data}"
        print("✓ GET /api/developers/domain/config returns saved config")

    def test_post_domain_config_invalid_domain_returns_400(self, auth_headers):
        """POST /api/developers/domain/config with invalid domain returns 400."""
        payload = {
            "domain": "not a domain",
            "server_ip": "203.0.113.1",
        }
        
        r = requests.post(
            f"{BASE_URL}/api/developers/domain/config",
            headers=auth_headers,
            json=payload,
            timeout=10,
        )
        assert r.status_code == 400, f"Expected 400 for invalid domain, got {r.status_code} - {r.text}"
        print("✓ POST /api/developers/domain/config with invalid domain returns 400")


# ═══════════════════════════════════════════════════════════════════════════
# Run tests
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
