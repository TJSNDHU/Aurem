"""iter 285.2 — Auto-Heal Bridge end-to-end test.

Validates:
  • _action_stage_code_fix injects [auto-heal] commit_message into the doc
  • GET /api/admin/autonomous-repair/pending-fixes returns staged fixes
  • POST /approve transitions status + returns commit_message
  • POST /reject transitions status
  • GET /stats aggregates by status
  • GitHub workflow detects [auto-heal] prefix (static source check)
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

REPO = Path(__file__).resolve().parents[2]
BACKEND_URL = "http://localhost:8001"

ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "Admin123"


def _load_env():
    env = {}
    for line in (REPO / "backend" / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


@pytest.fixture(scope="module")
def admin_token():
    for _ in range(3):
        try:
            r = httpx.post(
                f"{BACKEND_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                timeout=10.0,
            )
            if r.status_code == 200:
                d = r.json()
                return d.get("access_token") or d.get("token")
        except Exception:
            time.sleep(2)
    pytest.skip("Admin login unavailable")


@pytest.fixture
def seeded_fix():
    """Insert a synthetic fix, yield its id, then clean up."""
    env = _load_env()
    fix_id = f"codefix_test_{int(time.time())}"
    doc = {
        "id": fix_id,
        "classification": "unknown",
        "signature_hash": "abcd1234ef",
        "sample_message": "TypeError at line 42",
        "occurrences_1h": 5,
        "url": "https://aurem.live/dashboard",
        "status": "needs_human_review",
        "commit_message": "[auto-heal] unknown: TypeError at line 42 (sig=abcd1234, count=5)",
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "staged_by": "autonomous_repair_engine",
    }

    async def _insert():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        await db.pending_code_fixes.insert_one(dict(doc))

    async def _cleanup():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        await db.pending_code_fixes.delete_one({"id": fix_id})

    asyncio.run(_insert())
    yield fix_id
    asyncio.run(_cleanup())


def test_pending_fixes_list(admin_token, seeded_fix):
    r = httpx.get(
        f"{BACKEND_URL}/api/admin/autonomous-repair/pending-fixes?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 200
    body = r.json()
    ids = [f["id"] for f in body["fixes"]]
    assert seeded_fix in ids


def test_pending_fixes_stats(admin_token, seeded_fix):
    r = httpx.get(
        f"{BACKEND_URL}/api/admin/autonomous-repair/pending-fixes/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["needs_human_review"] >= 1
    assert "total" in body


def test_approve_transitions_status(admin_token, seeded_fix):
    r = httpx.post(
        f"{BACKEND_URL}/api/admin/autonomous-repair/pending-fixes/{seeded_fix}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["fix"]["status"] == "approved_for_deploy"
    assert body["fix"]["approved_by"]
    assert body["commit_message"].startswith("[auto-heal]")
    assert "next_step" in body


def test_reject_transitions_status(admin_token, seeded_fix):
    r = httpx.post(
        f"{BACKEND_URL}/api/admin/autonomous-repair/pending-fixes/{seeded_fix}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["fix"]["status"] == "rejected"


def test_engine_stage_includes_commit_message():
    """Static source guard: _action_stage_code_fix must build [auto-heal] commit_message."""
    src = (REPO / "backend" / "services" / "autonomous_repair_engine.py").read_text()
    assert "commit_message" in src
    assert "[auto-heal]" in src


def test_github_workflow_detects_auto_heal():
    """The GitHub workflow must grep commit message for [auto-heal] prefix."""
    wf = (REPO / ".github" / "workflows" / "deploy-reminder.yml").read_text()
    assert "[auto-heal]" in wf or "\\[auto-heal\\]" in wf
    assert "is_auto_heal" in wf
    assert "AUREM_EMERGENT_DEPLOY_WEBHOOK" in wf


def test_unauthorized_access_rejected():
    r = httpx.get(
        f"{BACKEND_URL}/api/admin/autonomous-repair/pending-fixes",
        timeout=5.0,
    )
    assert r.status_code in (401, 403)
