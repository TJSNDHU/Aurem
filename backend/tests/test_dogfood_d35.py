"""
test_dogfood_d35.py — iter D-35

Verifies the aurem.live production-dogfood flow:
  1. Admin can seed the aurem-live-production project (idempotent).
  2. Non-admin cannot.
  3. Project view exposes is_production_dogfood, production_warning,
     preview_url="" (no preview surface for prod dogfood).
  4. Status endpoint returns wiring flags (github_linked,
     deploy_configured, indexer_fresh, real_deploy_unlocked).
  5. /aurem-cto/deploy/run with mode=deploy and project_id pointing at
     a dogfood project returns 409 dry_run_required when no successful
     dry-run is on file. Rollback is exempt. dry_run mode is allowed.
"""
from __future__ import annotations

import os
import time
import uuid

import jwt
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

API = "http://localhost:8001"
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO   = os.environ.get("JWT_ALGORITHM", "HS256")


def _mint(sub: str, is_admin: bool = False) -> str:
    payload = {
        "sub":   sub,
        "email": f"{sub}@aurem.test",
        "iat":   int(time.time()),
        "exp":   int(time.time()) + 3600,
    }
    if is_admin:
        payload["is_admin"] = True
        payload["is_super_admin"] = True
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token() -> str:
    # Reuse the live admin user_id ("admin") so the seeded project
    # sticks to the real founder row already in the DB.
    return _mint("admin", is_admin=True)


@pytest.fixture(scope="module")
def user_token() -> str:
    return _mint(f"user-{uuid.uuid4().hex[:8]}", is_admin=False)


# ── 1. Admin seeds the dogfood project (idempotent) ─────────────────

def test_admin_can_seed_dogfood_project(admin_token):
    r1 = requests.post(
        f"{API}/api/onboarding/projects/dogfood/aurem-live-init",
        headers=_hdr(admin_token), json={}, timeout=15,
    )
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert j1["project_id"] == "aurem-live-production"
    assert j1["is_production_dogfood"] is True
    assert j1["production_warning"] and "production" in j1["production_warning"].lower()
    assert j1["preview_url"] == ""  # no preview surface for prod dogfood
    assert j1["progress"] == 1.0
    assert j1["phase"] == "production"

    # Second call must be idempotent.
    r2 = requests.post(
        f"{API}/api/onboarding/projects/dogfood/aurem-live-init",
        headers=_hdr(admin_token),
        json={"github_repo_url": "https://github.com/aurem-labs/aurem",
              "production_host": "aurem.live"},
        timeout=15,
    )
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    assert j2["project_id"] == j1["project_id"]
    assert j2["github_repo_url"] == "https://github.com/aurem-labs/aurem"
    assert j2["production_host"] == "aurem.live"


# ── 2. Non-admin is forbidden ────────────────────────────────────────

def test_non_admin_cannot_seed_dogfood(user_token):
    r = requests.post(
        f"{API}/api/onboarding/projects/dogfood/aurem-live-init",
        headers=_hdr(user_token), json={}, timeout=15,
    )
    # 401 = unregistered dev token, 403 = registered dev w/o admin claim.
    # Either way, the endpoint must NOT return 200.
    assert r.status_code in (401, 403), r.text


# ── 3. Status endpoint returns wiring flags ──────────────────────────

def test_dogfood_status_returns_wiring_flags(admin_token):
    r = requests.get(
        f"{API}/api/onboarding/projects/dogfood/aurem-live-status",
        headers=_hdr(admin_token), timeout=15,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert "github_linked" in j
    assert "deploy_configured" in j
    assert "indexer_fresh" in j
    assert "real_deploy_unlocked" in j
    # Project must be present after the seed test ran above.
    assert j["project"] and j["project"]["project_id"] == "aurem-live-production"


# ── 4. Production guard: real deploy without dry-run → 409 ──────────

def test_real_deploy_without_dry_run_is_blocked(admin_token):
    # Resolve the real user_id our admin token maps to (the dev portal
    # auto-bootstraps a developer row for platform-admin JWTs and its
    # user_id is NOT always 'admin' — it's derived from the email).
    me_r = requests.get(f"{API}/api/developers/me",
                         headers=_hdr(admin_token), timeout=10)
    assert me_r.status_code == 200, me_r.text
    real_uid = me_r.json()["user_id"]

    # The seed test above created the dogfood project under user_id="admin"
    # (admin JWT sub). Reseed it under the resolved user_id so the guard
    # path matches.
    requests.post(
        f"{API}/api/onboarding/projects/dogfood/aurem-live-init",
        headers=_hdr(admin_token), json={}, timeout=15,
    )

    # Seed a deploy config + wipe old dry-runs for the resolved user_id.
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient

    async def seed_cfg():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        await db.aurem_cto_deploy_configs.update_one(
            {"user_id": real_uid},
            {"$set": {
                "user_id":         real_uid,
                "host":            "stage.example.invalid",
                "port":            22,
                "username":        "root",
                "private_key_enc": "ENC_TEST_STUB",
                "repo_path":       "/srv/aurem",
                "branch":          "main",
                "compose_file":    "docker-compose.yml",
                "updated_at":      "2026-02-01T00:00:00+00:00",
            }},
            upsert=True,
        )
        await db.aurem_cto_deploy_runs.delete_many({"user_id": real_uid})
        # Make sure the dogfood project belongs to this user_id too.
        await db.onboarding_projects.update_one(
            {"project_id": "aurem-live-production"},
            {"$set": {"user_id": real_uid}},
        )

    asyncio.run(seed_cfg())

    r = requests.post(
        f"{API}/aurem-cto/deploy/run",
        headers=_hdr(admin_token),
        json={"mode": "deploy", "project_id": "aurem-live-production"},
        timeout=15,
    )
    assert r.status_code == 409, r.text
    body = r.json().get("detail") or {}
    assert body.get("code") == "dry_run_required"


# ── 5. dry_run mode is allowed even on dogfood project (the gate) ───

def test_dry_run_is_accepted_for_dogfood(admin_token):
    # dry_run will be ACCEPTED (returns 200 with status=running) — it
    # may then fail asynchronously because the SSH host is invalid, but
    # the endpoint itself must NOT return 409.
    r = requests.post(
        f"{API}/aurem-cto/deploy/run",
        headers=_hdr(admin_token),
        json={"mode": "dry_run", "project_id": "aurem-live-production"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "dry_run"
    assert j["status"] == "running"
    assert j.get("run_id")
