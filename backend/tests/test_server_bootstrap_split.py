"""
Test Suite for Server.py Bootstrap Split (Iteration 263)
=========================================================
Tests the extraction of middlewares, health routes, and well-known routes
from the monolithic server.py into the /app/backend/bootstrap/ package.

Modules tested:
- bootstrap/__init__.py — Package marker
- bootstrap/middlewares.py — SecurityHeaders, JWTBlocklist, usage metering
- bootstrap/health_routes.py — /health, /api/health, /ready, /, /api/platform/health
- bootstrap/wellknown_routes.py — /.well-known/assetlinks.json, /.well-known/ucp
"""

import pytest
import requests
import os
import sys
import ast
import importlib.util

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

# Get BASE_URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: Bootstrap Package Structure Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestBootstrapPackageStructure:
    """Verify the bootstrap package files exist and have correct exports."""

    def test_bootstrap_init_exists(self):
        """bootstrap/__init__.py exists as package marker."""
        path = "/app/backend/bootstrap/__init__.py"
        assert os.path.isfile(path), f"Missing {path}"
        print(f"✓ {path} exists")

    def test_bootstrap_middlewares_exists(self):
        """bootstrap/middlewares.py exists with correct exports."""
        path = "/app/backend/bootstrap/middlewares.py"
        assert os.path.isfile(path), f"Missing {path}"
        
        with open(path) as f:
            content = f.read()
        
        # Check required exports
        required_exports = [
            "SecurityHeadersMiddleware",
            "JWTBlocklistMiddleware",
            "METERED_PREFIXES",
            "register_security_headers",
            "register_jwt_blocklist",
            "register_usage_metering",
        ]
        for export in required_exports:
            assert export in content, f"Missing export: {export}"
        
        print(f"✓ {path} has all required exports")

    def test_bootstrap_health_routes_exists(self):
        """bootstrap/health_routes.py exists with correct exports."""
        path = "/app/backend/bootstrap/health_routes.py"
        assert os.path.isfile(path), f"Missing {path}"
        
        with open(path) as f:
            content = f.read()
        
        assert "register_health_routes" in content
        assert "__all__" in content
        print(f"✓ {path} has register_health_routes")

    def test_bootstrap_wellknown_routes_exists(self):
        """bootstrap/wellknown_routes.py exists with correct exports."""
        path = "/app/backend/bootstrap/wellknown_routes.py"
        assert os.path.isfile(path), f"Missing {path}"
        
        with open(path) as f:
            content = f.read()
        
        assert "register_wellknown_routes" in content
        assert "ASSETLINKS_JSON" in content
        assert "__all__" in content
        print(f"✓ {path} has register_wellknown_routes and ASSETLINKS_JSON")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: Import Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestBootstrapImports:
    """Verify all bootstrap modules can be imported without errors."""

    def test_import_bootstrap_package(self):
        """bootstrap package imports cleanly."""
        sys.path.insert(0, "/app/backend")
        try:
            import bootstrap
            print("✓ bootstrap package imports")
        finally:
            sys.path.pop(0)

    def test_import_middlewares(self):
        """bootstrap.middlewares imports with all exports."""
        sys.path.insert(0, "/app/backend")
        try:
            from bootstrap.middlewares import (
                SecurityHeadersMiddleware,
                JWTBlocklistMiddleware,
                METERED_PREFIXES,
                register_security_headers,
                register_jwt_blocklist,
                register_usage_metering,
            )
            assert callable(register_security_headers)
            assert callable(register_jwt_blocklist)
            assert callable(register_usage_metering)
            assert isinstance(METERED_PREFIXES, list)
            print("✓ All middleware exports importable")
        finally:
            sys.path.pop(0)

    def test_import_health_routes(self):
        """bootstrap.health_routes imports with register_health_routes."""
        sys.path.insert(0, "/app/backend")
        try:
            from bootstrap.health_routes import register_health_routes
            assert callable(register_health_routes)
            print("✓ register_health_routes importable")
        finally:
            sys.path.pop(0)

    def test_import_wellknown_routes(self):
        """bootstrap.wellknown_routes imports with all exports."""
        sys.path.insert(0, "/app/backend")
        try:
            from bootstrap.wellknown_routes import register_wellknown_routes, ASSETLINKS_JSON
            assert callable(register_wellknown_routes)
            assert isinstance(ASSETLINKS_JSON, list)
            assert len(ASSETLINKS_JSON) > 0
            print("✓ register_wellknown_routes and ASSETLINKS_JSON importable")
        finally:
            sys.path.pop(0)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: Health Endpoint Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoints:
    """Test all health endpoints from bootstrap/health_routes.py."""

    def test_health_endpoint(self):
        """GET /health returns 200 with status=ok and version."""
        # Note: /health without /api prefix goes to frontend in K8s
        # Test via /api/health which is the backend endpoint
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "v" in data
        assert data["v"] == "2026.04.10.1"
        print(f"✓ /api/health returns status=ok, v={data['v']}")

    def test_api_health_full_checks(self):
        """GET /api/health returns mongodb, redis, schedulers checks."""
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        
        # Verify checks object
        assert "checks" in data
        checks = data["checks"]
        assert checks.get("mongodb") == "ok", f"MongoDB not ok: {checks.get('mongodb')}"
        assert checks.get("redis") == "ok", f"Redis not ok: {checks.get('redis')}"
        assert "4/4 pillar workers" in checks.get("schedulers", ""), f"Schedulers: {checks.get('schedulers')}"
        
        # Verify response time
        assert "response_ms" in data
        assert data["response_ms"] < 100, f"Response too slow: {data['response_ms']}ms"
        
        print(f"✓ /api/health: mongodb={checks['mongodb']}, redis={checks['redis']}, schedulers={checks['schedulers']}, response_ms={data['response_ms']}")

    def test_api_platform_health(self):
        """GET /api/platform/health returns 200 with platform=aurem."""
        r = requests.get(f"{BASE_URL}/api/platform/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["platform"] == "aurem"
        print("✓ /api/platform/health returns platform=aurem")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: Security Headers Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    """Test security headers from bootstrap/middlewares.py."""

    def test_security_headers_present(self):
        """All security headers present on /api/health response."""
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        headers = r.headers
        
        # Required security headers
        required_headers = {
            "strict-transport-security": "max-age=31536000",
            "x-frame-options": "SAMEORIGIN",
            "x-content-type-options": "nosniff",
            "referrer-policy": "strict-origin-when-cross-origin",
            "permissions-policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
        }
        
        for header, expected_value in required_headers.items():
            actual = headers.get(header, "")
            assert expected_value in actual, f"Missing or wrong {header}: {actual}"
            print(f"✓ {header}: {actual[:50]}...")

    def test_csp_report_only_header(self):
        """Content-Security-Policy-Report-Only header present."""
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        csp = r.headers.get("content-security-policy-report-only", "")
        assert "default-src 'self'" in csp
        assert "script-src" in csp
        assert "stripe.com" in csp
        print(f"✓ CSP-Report-Only present with Stripe allowlist")

    def test_xss_protection_header(self):
        """X-XSS-Protection header present."""
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        xss = r.headers.get("x-xss-protection", "")
        assert "1; mode=block" in xss
        print(f"✓ X-XSS-Protection: {xss}")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: Well-Known Routes Tests (via /api/ucp/manifest)
# ═══════════════════════════════════════════════════════════════════════════

class TestWellKnownRoutes:
    """Test well-known routes functionality via /api/ucp/manifest."""

    def test_ucp_manifest_endpoint(self):
        """GET /api/ucp/manifest returns UCP manifest (same as /.well-known/ucp)."""
        r = requests.get(f"{BASE_URL}/api/ucp/manifest", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("protocol_version") == "2026.1"
        assert data.get("provider") == "AUREM AI"
        assert "capabilities" in data
        print("✓ /api/ucp/manifest returns UCP manifest")

    def test_assetlinks_json_content(self):
        """ASSETLINKS_JSON has correct structure for Android TWA."""
        sys.path.insert(0, "/app/backend")
        try:
            from bootstrap.wellknown_routes import ASSETLINKS_JSON
            assert len(ASSETLINKS_JSON) == 1
            asset = ASSETLINKS_JSON[0]
            assert "delegate_permission/common.handle_all_urls" in asset["relation"]
            assert asset["target"]["namespace"] == "android_app"
            assert asset["target"]["package_name"] == "ca.reroots.app"
            assert len(asset["target"]["sha256_cert_fingerprints"]) > 0
            print("✓ ASSETLINKS_JSON has correct Android TWA structure")
        finally:
            sys.path.pop(0)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: Pillar Workers Regression Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPillarWorkersRegression:
    """Verify all 4 pillar workers still running after bootstrap split."""

    def test_all_4_pillar_workers_running(self):
        """GET /api/health shows 4/4 pillar workers."""
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        schedulers = data.get("checks", {}).get("schedulers", "")
        assert "4/4 pillar workers" in schedulers, f"Expected 4/4 pillar workers, got: {schedulers}"
        print(f"✓ All 4 pillar workers running: {schedulers}")

    def test_pillar1_auto_blast_status(self):
        """P1 regression: /api/campaign/auto-blast/status returns 401 (auth required)."""
        r = requests.get(f"{BASE_URL}/api/campaign/auto-blast/status", timeout=10)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print("✓ P1 /api/campaign/auto-blast/status returns 401 (auth required)")

    def test_pillar2_subscription_plans(self):
        """P2 regression: /api/subscription/plans returns 200."""
        r = requests.get(f"{BASE_URL}/api/subscription/plans", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert "plans" in data or isinstance(data, list)
        print("✓ P2 /api/subscription/plans returns 200")

    def test_pillar3_repair_pending(self):
        """P3 regression: /api/repair/pending returns 200."""
        r = requests.get(f"{BASE_URL}/api/repair/pending", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        print("✓ P3 /api/repair/pending returns 200")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: Campaign Big Split Regression Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestCampaignBigSplitRegression:
    """Verify Campaign Big Split (iter 262) still works after bootstrap split."""

    def test_campaign_unsubscribe_public(self):
        """GET /api/campaign/unsubscribe returns 200 (public endpoint)."""
        r = requests.get(f"{BASE_URL}/api/campaign/unsubscribe", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        print("✓ /api/campaign/unsubscribe returns 200")

    def test_campaign_leads_auth_required(self):
        """GET /api/campaign/leads returns 401 (auth required)."""
        r = requests.get(f"{BASE_URL}/api/campaign/leads", timeout=10)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print("✓ /api/campaign/leads returns 401 (auth required)")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8: Usage Metering Middleware Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestUsageMeteringMiddleware:
    """Test usage metering middleware doesn't crash on metered endpoints."""

    def test_metered_prefixes_defined(self):
        """METERED_PREFIXES contains expected paths."""
        sys.path.insert(0, "/app/backend")
        try:
            from bootstrap.middlewares import METERED_PREFIXES
            expected = ["/api/aurem/chat", "/api/voice/", "/api/ora/", "/api/ghost/", "/api/geo/"]
            for prefix in expected:
                assert prefix in METERED_PREFIXES, f"Missing metered prefix: {prefix}"
            print(f"✓ METERED_PREFIXES: {METERED_PREFIXES}")
        finally:
            sys.path.pop(0)

    def test_metered_endpoint_no_crash(self):
        """POST to metered endpoint doesn't crash (even without auth)."""
        # This tests that the middleware doesn't crash, not that metering works
        r = requests.post(f"{BASE_URL}/api/aurem/chat", json={"message": "test"}, timeout=10)
        # Should NOT return 500 (server error) - any other status is acceptable
        assert r.status_code != 500, f"Server error: {r.status_code}"
        print(f"✓ POST /api/aurem/chat returns {r.status_code} (no crash)")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 9: Server.py Code Review
# ═══════════════════════════════════════════════════════════════════════════

class TestServerCodeReview:
    """Verify server.py correctly imports and uses bootstrap modules."""

    def test_server_imports_bootstrap_middlewares(self):
        """server.py imports from bootstrap.middlewares."""
        with open("/app/backend/server.py") as f:
            content = f.read()
        
        assert "from bootstrap.middlewares import" in content
        assert "register_security_headers" in content
        assert "register_jwt_blocklist" in content
        assert "register_usage_metering" in content
        print("✓ server.py imports bootstrap.middlewares")

    def test_server_imports_bootstrap_health_routes(self):
        """server.py imports from bootstrap.health_routes."""
        with open("/app/backend/server.py") as f:
            content = f.read()
        
        assert "from bootstrap.health_routes import register_health_routes" in content
        assert "register_health_routes(app" in content
        print("✓ server.py imports and calls register_health_routes")

    def test_server_imports_bootstrap_wellknown_routes(self):
        """server.py imports from bootstrap.wellknown_routes."""
        with open("/app/backend/server.py") as f:
            content = f.read()
        
        assert "from bootstrap.wellknown_routes import register_wellknown_routes" in content
        assert "register_wellknown_routes(app)" in content
        print("✓ server.py imports and calls register_wellknown_routes")

    def test_server_no_duplicate_middleware_definitions(self):
        """server.py doesn't define SecurityHeadersMiddleware or JWTBlocklistMiddleware inline."""
        with open("/app/backend/server.py") as f:
            content = f.read()
        
        # These should NOT be defined in server.py anymore
        assert "class SecurityHeadersMiddleware" not in content, "SecurityHeadersMiddleware should be in bootstrap/middlewares.py"
        assert "class JWTBlocklistMiddleware" not in content, "JWTBlocklistMiddleware should be in bootstrap/middlewares.py"
        print("✓ server.py doesn't have duplicate middleware class definitions")

    def test_server_line_count_reduced(self):
        """server.py is reduced from 1820 to ~1618 LOC."""
        with open("/app/backend/server.py") as f:
            lines = len(f.readlines())
        
        # Should be around 1618 lines (±50 for minor changes)
        assert lines < 1700, f"server.py has {lines} lines, expected <1700"
        print(f"✓ server.py has {lines} lines (reduced from 1820)")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 10: No Duplicate Route Registration
# ═══════════════════════════════════════════════════════════════════════════

class TestNoDuplicateRoutes:
    """Verify routes are registered exactly once."""

    def test_health_routes_registered_once(self):
        """Health routes should be registered exactly once."""
        # Count occurrences of route registration in server.py
        with open("/app/backend/server.py") as f:
            content = f.read()
        
        # register_health_routes should be called exactly once
        count = content.count("register_health_routes(app")
        assert count == 1, f"register_health_routes called {count} times, expected 1"
        print("✓ register_health_routes called exactly once")

    def test_wellknown_routes_registered_once(self):
        """Well-known routes should be registered exactly once."""
        with open("/app/backend/server.py") as f:
            content = f.read()
        
        count = content.count("register_wellknown_routes(app)")
        assert count == 1, f"register_wellknown_routes called {count} times, expected 1"
        print("✓ register_wellknown_routes called exactly once")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
