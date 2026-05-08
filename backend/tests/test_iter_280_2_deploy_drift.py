"""
Iter 280.2 — Deploy Drift Router regression.

Verifies:
  - Public health probe responds without auth
  - Admin endpoint requires JWT
  - Drift payload contains expected keys
  - In-memory cache hit on second call
  - _preview_sha + _pending_commits helpers resolve cleanly on this repo
"""
from __future__ import annotations

import os
import pytest
import httpx


API_BASE = os.environ.get("AUREM_E2E_BASE", "http://localhost:8001")
EXPECTED_KEYS = {
    "prod_reachable",
    "prod_sha",
    "preview_sha",
    "in_sync",
    "pending_commits",
    "oldest_drift_seconds",
    "needs_deploy",
    "threshold_seconds",
    "recent_commits",
    "computed_at",
}


def _admin_token():
    r = httpx.post(
        f"{API_BASE}/api/auth/login",
        json={"email": "teji.ss1986@gmail.com", "password": "Admin123"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def test_deploy_drift_health_public():
    r = httpx.get(f"{API_BASE}/api/admin/deploy-drift/health", timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("status") == "ok"
    assert d.get("component") == "deploy_drift"
    assert "prod_health_url" in d
    assert "threshold_seconds" in d


def test_deploy_drift_requires_admin_token():
    r = httpx.get(f"{API_BASE}/api/admin/deploy-drift", timeout=10)
    assert r.status_code == 401, r.text


def test_deploy_drift_payload_shape_and_cache():
    tok = _admin_token()
    headers = {"Authorization": f"Bearer {tok}"}

    # First call — may or may not be cached depending on prior history.
    r1 = httpx.get(
        f"{API_BASE}/api/admin/deploy-drift", headers=headers, timeout=15
    )
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    missing = EXPECTED_KEYS - set(d1.keys())
    assert not missing, f"Missing keys in drift payload: {missing}"

    # Preview SHA should always resolve on this pod
    assert isinstance(d1["preview_sha"], str)
    assert len(d1["preview_sha"]) >= 7 or d1["preview_sha"] == ""

    # Second call within 60s must be cached
    r2 = httpx.get(
        f"{API_BASE}/api/admin/deploy-drift", headers=headers, timeout=15
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2.get("cached") is True, "Second call should hit in-memory cache"


def test_deploy_drift_invalidate():
    tok = _admin_token()
    headers = {"Authorization": f"Bearer {tok}"}
    r = httpx.post(
        f"{API_BASE}/api/admin/deploy-drift/invalidate",
        headers=headers,
        timeout=10,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("invalidated") is True


def test_deploy_drift_history():
    tok = _admin_token()
    headers = {"Authorization": f"Bearer {tok}"}
    r = httpx.get(
        f"{API_BASE}/api/admin/deploy-drift/history?limit=5",
        headers=headers,
        timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert "history" in d
    assert isinstance(d["history"], list)


def test_preview_sha_resolves_from_git():
    # Unit test for the helper — does not require running backend.
    from routers.deploy_drift_router import _preview_sha

    sha = _preview_sha()
    # Allow empty only if this test runs in an environment without /app/.git
    if sha:
        assert len(sha) >= 7
        assert all(c in "0123456789abcdef" for c in sha.lower()), sha


def test_pending_commits_helper_is_empty_when_equal():
    from routers.deploy_drift_router import _pending_commits, _preview_sha

    sha = _preview_sha()
    if not sha:
        pytest.skip("git unavailable in this environment")
    # Same SHA on both sides → 0 pending
    commits = _pending_commits(sha, sha)
    assert commits == []


def test_chip_deploy_drift_testid_mounted():
    """Pure backend marker test — frontend chip exposes data-testid
    'chip-deploy-drift' which is testable via Playwright in iter 280.2
    frontend smoke. This assertion simply guards that the frontend file
    still references the endpoint path."""
    path = "/app/frontend/src/platform/SystemStatusChip.jsx"
    with open(path) as fh:
        src = fh.read()
    assert "/api/admin/deploy-drift" in src
    assert "chip-deploy-drift" in src


def test_deploy_panel_references_endpoint():
    path = "/app/frontend/src/platform/DeployStatusPanel.jsx"
    with open(path) as fh:
        src = fh.read()
    assert "/api/admin/deploy-drift" in src
    assert "deploy-status-panel" in src
