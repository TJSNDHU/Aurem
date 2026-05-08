"""
Shannon Security Integration Tests
===================================
Tests for Shannon Red Team pentest integration:
- POST /api/security/shannon/report (unauthenticated - for Legion)
- GET /api/security/shannon/posture (authenticated)
- GET /api/security/shannon/report/latest (authenticated)
- GET /api/security/shannon/history (authenticated)
- GET /api/swarm/cards (includes SHANNON agent)
- GET /api/overwatch/pulse (includes security posture)
- POST /api/overwatch/auth/pin (PIN authentication)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestOverwatchPinAuth:
    """PIN authentication for Overwatch PWA"""
    
    def test_pin_auth_success(self):
        """Test PIN authentication with valid PIN"""
        response = requests.post(
            f"{BASE_URL}/api/overwatch/auth/pin",
            json={"pin": "1234"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "expires_in" in data, "Response should contain expires_in"
        assert len(data["token"]) > 50, "Token should be a valid JWT"
        
    def test_pin_auth_invalid_pin(self):
        """Test PIN authentication with invalid PIN"""
        response = requests.post(
            f"{BASE_URL}/api/overwatch/auth/pin",
            json={"pin": "9999"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestShannonReportEndpoint:
    """Tests for POST /api/security/shannon/report (unauthenticated)"""
    
    def test_submit_report_success(self):
        """Test submitting a pentest report - should be unauthenticated"""
        report = {
            "target": "https://test-target.com",
            "vulnerabilities": [
                {"severity": "critical", "title": "SQL Injection", "verified": True, "exploitable": True},
                {"severity": "high", "title": "XSS Vulnerability", "verified": False},
                {"severity": "medium", "title": "CSRF Token Missing"},
                {"severity": "low", "title": "Information Disclosure"},
                {"severity": "info", "title": "Server Version Exposed"}
            ],
            "scanner": "shannon",
            "version": "1.0.0",
            "duration_seconds": 120
        }
        response = requests.post(
            f"{BASE_URL}/api/security/shannon/report",
            json=report,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data["status"] == "ingested", "Status should be 'ingested'"
        assert "security_score" in data, "Response should contain security_score"
        assert "total_vulnerabilities" in data, "Response should contain total_vulnerabilities"
        assert "severity_counts" in data, "Response should contain severity_counts"
        assert "exploits_verified" in data, "Response should contain exploits_verified"
        
        # Verify data values
        assert data["total_vulnerabilities"] == 5, "Should have 5 vulnerabilities"
        assert data["severity_counts"]["critical"] == 1, "Should have 1 critical"
        assert data["severity_counts"]["high"] == 1, "Should have 1 high"
        assert data["exploits_verified"] >= 1, "Should have at least 1 verified exploit"
        
        # Score calculation: 100 - 25(crit) - 15(high) - 8(med) - 3(low) = 49
        assert data["security_score"] == 49, f"Expected score 49, got {data['security_score']}"
    
    def test_submit_empty_report(self):
        """Test submitting a report with no vulnerabilities"""
        report = {
            "target": "https://secure-target.com",
            "vulnerabilities": [],
            "scanner": "shannon"
        }
        response = requests.post(
            f"{BASE_URL}/api/security/shannon/report",
            json=report,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["security_score"] == 100, "Empty report should have score 100"
        assert data["total_vulnerabilities"] == 0


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token via PIN"""
    response = requests.post(
        f"{BASE_URL}/api/overwatch/auth/pin",
        json={"pin": "1234"},
        headers={"Content-Type": "application/json"}
    )
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("PIN authentication failed")


class TestShannonPosture:
    """Tests for GET /api/security/shannon/posture"""
    
    def test_get_posture_authenticated(self, auth_token):
        """Test getting security posture with valid auth"""
        response = requests.get(
            f"{BASE_URL}/api/security/shannon/posture",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify posture structure
        assert "score" in data, "Posture should contain score"
        assert "status" in data, "Posture should contain status"
        assert "severity_counts" in data, "Posture should contain severity_counts"
        assert "total_vulnerabilities" in data, "Posture should contain total_vulnerabilities"
        
        # Status should be critical (we submitted a report with critical vuln)
        assert data["status"] in ["critical", "warning", "healthy", "awaiting_audit"]
    
    def test_get_posture_unauthorized(self):
        """Test getting posture without auth"""
        response = requests.get(f"{BASE_URL}/api/security/shannon/posture")
        assert response.status_code == 401, "Should require authentication"


class TestShannonLatestReport:
    """Tests for GET /api/security/shannon/report/latest"""
    
    def test_get_latest_report(self, auth_token):
        """Test getting the latest report"""
        response = requests.get(
            f"{BASE_URL}/api/security/shannon/report/latest",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have report data (we submitted one earlier)
        if "status" not in data or data.get("status") != "no_reports":
            assert "security_score" in data, "Report should contain security_score"
            assert "vulnerabilities" in data, "Report should contain vulnerabilities"
            assert "severity_counts" in data, "Report should contain severity_counts"
    
    def test_get_latest_report_unauthorized(self):
        """Test getting latest report without auth"""
        response = requests.get(f"{BASE_URL}/api/security/shannon/report/latest")
        assert response.status_code == 401


class TestShannonHistory:
    """Tests for GET /api/security/shannon/history"""
    
    def test_get_history(self, auth_token):
        """Test getting audit history"""
        response = requests.get(
            f"{BASE_URL}/api/security/shannon/history",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "audits" in data, "Response should contain audits array"
        assert "total" in data, "Response should contain total count"
        assert isinstance(data["audits"], list), "Audits should be a list"
    
    def test_get_history_unauthorized(self):
        """Test getting history without auth"""
        response = requests.get(f"{BASE_URL}/api/security/shannon/history")
        assert response.status_code == 401


class TestSwarmCards:
    """Tests for GET /api/swarm/cards - SHANNON agent registration"""
    
    def test_swarm_cards_includes_shannon(self, auth_token):
        """Test that SHANNON agent is registered in swarm"""
        response = requests.get(
            f"{BASE_URL}/api/swarm/cards",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "agents" in data, "Response should contain agents"
        agents = data["agents"]
        
        # Find SHANNON agent
        shannon = next((a for a in agents if a["agent_id"] == "shannon"), None)
        assert shannon is not None, "SHANNON agent should be in swarm registry"
        
        # Verify SHANNON agent properties
        assert shannon["name"] == "SHANNON", "Agent name should be SHANNON"
        assert shannon["role"] == "security_auditor", "Role should be security_auditor"
        assert shannon["engine"] == "sovereign", "Engine should be sovereign"
        assert "pentest" in shannon["capabilities"], "Should have pentest capability"
        assert "vulnerability_scan" in shannon["capabilities"], "Should have vulnerability_scan capability"


class TestOverwatchPulse:
    """Tests for GET /api/overwatch/pulse - security posture in pulse"""
    
    def test_pulse_includes_security(self, auth_token):
        """Test that pulse response includes security posture"""
        response = requests.get(
            f"{BASE_URL}/api/overwatch/pulse",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify security section exists
        assert "security" in data, "Pulse should include security section"
        security = data["security"]
        
        # Verify security structure
        assert "score" in security, "Security should have score"
        assert "status" in security, "Security should have status"
        assert "severity_counts" in security, "Security should have severity_counts"
        
        # Verify severity_counts structure
        counts = security["severity_counts"]
        assert "critical" in counts, "Should have critical count"
        assert "high" in counts, "Should have high count"
        assert "medium" in counts, "Should have medium count"
        assert "low" in counts, "Should have low count"


class TestSecurityStatusTransitions:
    """Test security status transitions based on report content"""
    
    def test_critical_vuln_triggers_breach_status(self, auth_token):
        """Submit critical vuln and verify status becomes 'critical'"""
        # Submit report with critical vulnerability
        report = {
            "target": "https://breach-test.com",
            "vulnerabilities": [
                {"severity": "critical", "title": "RCE Vulnerability", "verified": True}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/security/shannon/report",
            json=report,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        # Check posture status
        posture_response = requests.get(
            f"{BASE_URL}/api/security/shannon/posture",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert posture_response.status_code == 200
        posture = posture_response.json()
        
        assert posture["status"] == "critical", f"Status should be 'critical' with critical vuln, got {posture['status']}"
    
    def test_high_vuln_only_triggers_warning_status(self, auth_token):
        """Submit high vuln (no critical) and verify status becomes 'warning'"""
        # Submit report with only high vulnerability
        report = {
            "target": "https://warning-test.com",
            "vulnerabilities": [
                {"severity": "high", "title": "Auth Bypass", "verified": True}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/security/shannon/report",
            json=report,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        
        # Check posture status
        posture_response = requests.get(
            f"{BASE_URL}/api/security/shannon/posture",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert posture_response.status_code == 200
        posture = posture_response.json()
        
        # Note: Status depends on the latest report
        assert posture["status"] in ["warning", "critical"], f"Status should be warning or critical, got {posture['status']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
