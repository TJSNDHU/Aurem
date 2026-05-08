"""iter 287.1 — Deploy Trigger Webhook tests."""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[2]
BACKEND_URL = "http://localhost:8001"


def _env():
    env = {}
    for line in (REPO / "backend" / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


@pytest.fixture(scope="module")
def deploy_secret():
    return _env().get("DEPLOY_SECRET") or ""


def test_health_endpoint_is_public():
    with httpx.Client(timeout=10.0) as c:
        r = c.get(f"{BACKEND_URL}/api/admin/deploy/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["component"] == "deploy-trigger"
    assert isinstance(d["secret_configured"], bool)


def test_trigger_rejects_missing_bearer():
    with httpx.Client(timeout=10.0) as c:
        r = c.post(f"{BACKEND_URL}/api/admin/deploy/trigger",
                   json={"trigger": "manual"})
    assert r.status_code == 401
    assert "Bearer" in r.json().get("detail", "") or "Missing" in r.json().get("detail", "")


def test_trigger_rejects_wrong_secret():
    with httpx.Client(timeout=10.0) as c:
        r = c.post(
            f"{BACKEND_URL}/api/admin/deploy/trigger",
            json={"trigger": "manual"},
            headers={"Authorization": "Bearer totally_wrong_secret_xyz"},
        )
    assert r.status_code == 401


def test_trigger_accepts_valid_secret_and_returns_202(deploy_secret):
    if not deploy_secret:
        pytest.skip("DEPLOY_SECRET not set in .env")
    with httpx.Client(timeout=15.0) as c:
        r = c.post(
            f"{BACKEND_URL}/api/admin/deploy/trigger",
            json={
                "trigger": "manual",
                "branch": "main",
                "commit": f"test_sha_{int(time.time())}",
                "message": "test: deploy trigger integration",
                "actor": "pytest",
                "run_id": f"test_run_{int(time.time())}",
            },
            headers={"Authorization": f"Bearer {deploy_secret}"},
        )
    assert r.status_code == 202, r.text
    d = r.json()
    assert d["ok"] is True
    assert "trigger_id" in d
    assert d["status"] == "Deployment Initiated"
    assert d["deploy_kind"] in ("preview", "production")


def test_trigger_replay_dedup(deploy_secret):
    if not deploy_secret:
        pytest.skip("DEPLOY_SECRET not set in .env")
    commit = f"replay_test_{int(time.time())}"
    run_id = f"replay_run_{int(time.time())}"
    with httpx.Client(timeout=15.0) as c:
        r1 = c.post(
            f"{BACKEND_URL}/api/admin/deploy/trigger",
            json={"trigger": "manual", "branch": "main", "commit": commit,
                  "message": "first", "run_id": run_id},
            headers={"Authorization": f"Bearer {deploy_secret}"},
        )
        assert r1.status_code == 202
        tid1 = r1.json()["trigger_id"]
        # Second call with same commit+run_id → should be deduped
        r2 = c.post(
            f"{BACKEND_URL}/api/admin/deploy/trigger",
            json={"trigger": "manual", "branch": "main", "commit": commit,
                  "message": "second", "run_id": run_id},
            headers={"Authorization": f"Bearer {deploy_secret}"},
        )
        assert r2.status_code == 202
        d2 = r2.json()
        assert d2["trigger_id"] == tid1
        assert d2["status"] == "duplicate_ignored"


def test_status_endpoint_returns_trigger_details(deploy_secret):
    if not deploy_secret:
        pytest.skip("DEPLOY_SECRET not set in .env")
    with httpx.Client(timeout=15.0) as c:
        # Create a trigger
        r = c.post(
            f"{BACKEND_URL}/api/admin/deploy/trigger",
            json={"trigger": "manual", "branch": "main",
                  "commit": f"status_test_{int(time.time())}",
                  "run_id": f"st_run_{int(time.time())}"},
            headers={"Authorization": f"Bearer {deploy_secret}"},
        )
        assert r.status_code == 202
        tid = r.json()["trigger_id"]
        # Poll status
        r2 = c.get(
            f"{BACKEND_URL}/api/admin/deploy/status/{tid}",
            headers={"Authorization": f"Bearer {deploy_secret}"},
        )
    assert r2.status_code == 200
    d = r2.json()
    assert d["trigger_id"] == tid
    assert d["status"] in ("running", "success", "failed")
    assert "ts_iso" in d


def test_status_rejects_missing_secret(deploy_secret):
    if not deploy_secret:
        pytest.skip("DEPLOY_SECRET not set in .env")
    with httpx.Client(timeout=10.0) as c:
        r = c.get(f"{BACKEND_URL}/api/admin/deploy/status/nonexistent_id")
    assert r.status_code == 401


def test_recent_endpoint(deploy_secret):
    if not deploy_secret:
        pytest.skip("DEPLOY_SECRET not set in .env")
    with httpx.Client(timeout=10.0) as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/deploy/recent?limit=5",
            headers={"Authorization": f"Bearer {deploy_secret}"},
        )
    assert r.status_code == 200
    d = r.json()
    assert "triggers" in d
    assert isinstance(d["triggers"], list)


def test_auto_heal_gating_when_enabled(monkeypatch, deploy_secret):
    """When DEPLOY_AUTO_HEAL_ONLY=1, commits WITHOUT [auto-heal] get 400."""
    if not deploy_secret:
        pytest.skip("DEPLOY_SECRET not set in .env")
    # Can't mutate server env at runtime from client — skip unless already set
    if _env().get("DEPLOY_AUTO_HEAL_ONLY", "0") not in ("1", "true", "yes"):
        pytest.skip("DEPLOY_AUTO_HEAL_ONLY not enabled on server")
    with httpx.Client(timeout=10.0) as c:
        r = c.post(
            f"{BACKEND_URL}/api/admin/deploy/trigger",
            json={"trigger": "manual", "message": "plain commit, no marker",
                  "commit": "x", "run_id": "y"},
            headers={"Authorization": f"Bearer {deploy_secret}"},
        )
    assert r.status_code == 400
