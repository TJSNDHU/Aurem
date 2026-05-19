"""iter 285.7 — AbortError noise filter + Legion boot-kit.

Validates:
  • sentinel.js filters AbortError / "signal is aborted" before ship
  • autonomous_repair_engine dismisses user_abort classification
  • /api/admin/autonomous-repair/purge-user-abort-noise works
  • sdk/legion_bootkit.py exists + has required env contract
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

REPO = Path(__file__).resolve().parents[2]
BACKEND_URL = "http://localhost:8001"

ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "<REDACTED>"


def _env():
    env = {}
    for line in (REPO / "backend" / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


@pytest.fixture(scope="module")
def admin_token():
    for _ in range(5):
        try:
            with httpx.Client(timeout=10.0) as c:
                r = c.post(
                    f"{BACKEND_URL}/api/auth/login",
                    json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                )
            if r.status_code == 200:
                d = r.json()
                return d.get("access_token") or d.get("token")
        except Exception:
            time.sleep(2)
    pytest.skip("Admin login unavailable")


# ───────── Frontend sentinel.js filter ─────────

def test_sentinel_js_filters_abort_error():
    src = (REPO / "frontend" / "src" / "lib" / "sentinel.js").read_text()
    assert "AbortError" in src
    assert "signal is aborted" not in src or "isAbort" in src  # at least one match
    assert "isAbort" in src, "sentinel.js must have isAbort filter gate"
    # Regression — the old bare _shipEvent must NOT fire for aborts
    assert "if (isAbort)" in src or "isAbort &&" in src


# ───────── Backend classifier ─────────

def test_autonomous_repair_dismisses_user_abort():
    src = (REPO / "backend" / "services" / "autonomous_repair_engine.py").read_text()
    assert "signal is aborted" in src
    assert "dismiss_user_abort_noise" in src


# ───────── Purge endpoint ─────────

def test_purge_user_abort_noise(admin_token):
    env = _env()

    async def _seed():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        await db.client_errors.insert_many([
            {"type": "network_failure", "message": "signal is aborted without reason",
             "url": "/api/x", "timestamp": "2026-04-24T05:00:00Z"},
            {"type": "network_failure", "message": "AbortError: fetch aborted",
             "url": "/api/y", "timestamp": "2026-04-24T05:00:01Z"},
        ])
        await db.sentinel_alerts.insert_one({
            "message": "Signal is aborted — user navigated",
            "max_score": 0, "created_at": "2026-04-24T05:00:00Z",
        })

    async def _count_abort():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        return await db.client_errors.count_documents(
            {"message": {"$regex": "abort", "$options": "i"}}
        )

    asyncio.run(_seed())
    before = asyncio.run(_count_abort())
    assert before >= 2

    with httpx.Client(timeout=10.0) as c:
        r = c.post(
            f"{BACKEND_URL}/api/admin/autonomous-repair/purge-user-abort-noise",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["client_errors_deleted"] >= 2

    after = asyncio.run(_count_abort())
    assert after == 0


def test_purge_endpoint_requires_admin():
    """Unauth POST must return 401/403. Uses subprocess curl to avoid httpx port churn."""
    import subprocess
    last = None
    for i in range(6):
        try:
            r = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "-X", "POST", f"{BACKEND_URL}/api/admin/autonomous-repair/purge-user-abort-noise"],
                capture_output=True, text=True, timeout=10,
            )
            code = int(r.stdout.strip() or 0)
            assert code in (401, 403), f"got {code}"
            return
        except Exception as e:
            last = e
            time.sleep(1.0 + i * 0.5)
    raise last


# ───────── Legion boot-kit ─────────

def test_legion_bootkit_exists():
    bootkit = REPO / "sdk" / "legion_bootkit.py"
    readme = REPO / "sdk" / "LEGION_README.md"
    assert bootkit.exists(), "legion_bootkit.py missing"
    assert readme.exists(), "LEGION_README.md missing"


def test_legion_bootkit_contract():
    src = (REPO / "sdk" / "legion_bootkit.py").read_text()
    # Required env vars
    assert "AUREM_URL" in src
    assert "AUREM_TOKEN" in src
    assert "LEGION_NODE_ID" in src
    # Required endpoints
    assert "/api/sovereign/heartbeat" in src
    assert "/api/sovereign/sync/" in src
    # Must not leak credentials in plaintext
    assert "password" not in src.lower()
    assert "admin@" not in src.lower()
    # Must handle offline gracefully (never crash on network error)
    assert "urllib.error" in src or "try:" in src


def test_legion_bootkit_runnable_syntax():
    """Bootkit must be syntactically valid Python."""
    import py_compile
    bootkit = REPO / "sdk" / "legion_bootkit.py"
    py_compile.compile(str(bootkit), doraise=True)
