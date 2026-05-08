"""
iter 277 regression tests — Alive Fix + Vanguard SKU.

Covers:
  1. /api/admin/pillars-map/subproduct/{tier} — happy path + validation
  2. Sidebar blocks contract — Vanguard block present
  3. Frontend surface manifest — preferred over subprocess grep
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import requests


BACKEND_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "http://localhost:8001",
)
API = f"{BACKEND_URL.rstrip('/')}/api"

TEST_EMAIL    = "teji.ss1986@gmail.com"
TEST_PASSWORD = "Admin123"


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"Login did not return a token: {data}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


# ═══════════════════════════════════════════════════════════════════
# Part A — Frontend Surface Manifest (Alive Fix)
# ═══════════════════════════════════════════════════════════════════

class TestSurfaceManifest:
    MANIFEST_JSON = Path("/app/backend/data/frontend_surface.json")
    MANIFEST_PY   = Path("/app/backend/routers/_frontend_surface_data.py")

    def test_manifest_py_module_exists(self):
        """iter 277 rev-b: Python module is the production-safe path."""
        assert self.MANIFEST_PY.exists(), (
            "Run `python3 /app/scripts/build_frontend_surface.py` to generate"
        )

    def test_manifest_py_module_imports(self):
        """Manifest module must be importable from backend/."""
        import importlib, sys
        sys.path.insert(0, "/app/backend")
        try:
            mod = importlib.import_module("routers._frontend_surface_data")
            importlib.reload(mod)
            assert hasattr(mod, "SURFACE_MANIFEST")
            assert hasattr(mod, "BUILT_AT")
            assert hasattr(mod, "ENDPOINT_COUNT")
            assert mod.ENDPOINT_COUNT > 100
            assert isinstance(mod.SURFACE_MANIFEST, dict)
        finally:
            sys.path.remove("/app/backend")

    def test_alive_count_nonzero_with_manifest(self, auth_headers):
        # Force fresh build to pick up manifest
        requests.post(
            f"{API}/admin/pillars-map/endpoint-audit/invalidate",
            headers=auth_headers,
            timeout=10,
        )
        r = requests.get(
            f"{API}/admin/pillars-map/endpoint-audit/summary",
            headers=auth_headers,
            timeout=30,
        )
        r.raise_for_status()
        dignity = r.json()["totals"]["by_dignity"]
        assert dignity["alive"] > 0, (
            "Alive dignity should be > 0 when manifest is present; "
            f"got {dignity}"
        )

    def test_build_script_runs(self):
        result = subprocess.run(
            ["python3", "/app/scripts/build_frontend_surface.py"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert "_frontend_surface_data.py" in result.stdout
        assert "distinct /api/ literals" in result.stdout


# ═══════════════════════════════════════════════════════════════════
# Part B — Vanguard SKU + Sub-Product Drill-down
# ═══════════════════════════════════════════════════════════════════

class TestSubProductDrill:
    def test_requires_auth(self):
        r = requests.get(
            f"{API}/admin/pillars-map/subproduct/T2_subproduct_vanguard",
            timeout=10,
        )
        assert r.status_code == 401

    def test_vanguard_drill_200(self, auth_headers):
        r = requests.get(
            f"{API}/admin/pillars-map/subproduct/T2_subproduct_vanguard",
            headers=auth_headers, timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["tier"] == "T2_subproduct_vanguard"
        assert d["endpoint_count"] >= 6  # at least 6 Vanguard endpoints
        assert "aurem_vanguard_router" in d["top_routers"]
        assert isinstance(d["endpoints"], list)
        # Each endpoint row must have the core contract
        for ep in d["endpoints"]:
            assert {"method", "path", "router", "dignity", "hits_30d"} <= set(ep)

    def test_customer_portal_drill_200(self, auth_headers):
        r = requests.get(
            f"{API}/admin/pillars-map/subproduct/T2_subproduct_customer_portal",
            headers=auth_headers, timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["endpoint_count"] > 0

    def test_invalid_tier_400(self, auth_headers):
        r = requests.get(
            f"{API}/admin/pillars-map/subproduct/T1_P1_acquisition",
            headers=auth_headers, timeout=10,
        )
        assert r.status_code == 400

    def test_nonexistent_subproduct_404(self, auth_headers):
        r = requests.get(
            f"{API}/admin/pillars-map/subproduct/T2_subproduct_nonexistent",
            headers=auth_headers, timeout=30,
        )
        assert r.status_code == 404


class TestSidebarVanguardBlock:
    def test_sidebar_includes_vanguard(self, auth_headers):
        r = requests.get(
            f"{API}/admin/pillars-map/sidebar-blocks",
            headers=auth_headers, timeout=30,
        )
        assert r.status_code == 200
        blocks = r.json().get("blocks", [])
        ids = [b.get("id") for b in blocks]
        assert "vanguard" in ids
        vanguard = next(b for b in blocks if b["id"] == "vanguard")
        assert vanguard["label"] == "Vanguard"
        assert "aurem_missions" in [badge.get("collection") for badge in vanguard.get("badges", [])]
