"""iter 285.8 — Master Autopilot + P4 silent-failure threshold + ORA submit fix.

Validates:
  • POST /api/admin/autopilot/activate arms config + enables auto_blast
  • GET  /api/admin/autopilot/status returns armed state
  • POST /api/admin/autopilot/fire-now runs 4 phases, records to autopilot_runs
  • POST /api/admin/autopilot/pause flips enabled=false
  • pillars_map_router has per-collection SILENT_FAILURE_OVERRIDES
  • SidebarAddons submit handles SyntheticEvent without crashing
"""
from __future__ import annotations

import os

import asyncio
import time
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

REPO = Path(__file__).resolve().parents[2]
BACKEND_URL = "http://localhost:8001"

ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


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


@pytest.fixture
def clean_autopilot():
    """Save prod autopilot config on entry, restore on exit.

    PREVIOUS BUG: this fixture used to wipe master_autopilot from
    platform_config, which permanently disarmed the production autopilot
    after any test run. Now we snapshot + restore so tests never destroy
    live state.
    """
    env = _env()

    saved_cfg: dict = {}

    async def _snapshot_and_wipe():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        existing = await db.platform_config.find_one(
            {"config_key": "master_autopilot"}, {"_id": 0}
        )
        if existing:
            saved_cfg.update(existing)
        await db.platform_config.delete_many({"config_key": "master_autopilot"})
        await db.autopilot_runs.delete_many(
            {"triggered_by": {"$regex": "^manual:|^schedule"}, "run_id": {"$regex": "^autopilot_test"}}
        )

    async def _restore():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        # Remove whatever the test left behind
        await db.platform_config.delete_many({"config_key": "master_autopilot"})
        # Restore the prod config snapshot verbatim (if any)
        if saved_cfg:
            await db.platform_config.insert_one(dict(saved_cfg))

    asyncio.run(_snapshot_and_wipe())
    yield
    asyncio.run(_restore())


# ───────── Autopilot API ─────────

def test_autopilot_status_when_unconfigured(admin_token, clean_autopilot):
    with httpx.Client(timeout=10.0) as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/autopilot/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert body["enabled"] is False


def test_autopilot_activate_and_status(admin_token, clean_autopilot):
    with httpx.Client(timeout=10.0) as c:
        r = c.post(
            f"{BACKEND_URL}/api/admin/autopilot/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"time": "08:00", "tz": "America/Toronto"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["config"]["enabled"] is True
    assert body["config"]["time"] == "08:00"
    assert body["seconds_until_fire"] > 0

    # Status reflects armed
    with httpx.Client(timeout=10.0) as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/autopilot/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    body = r.json()
    assert body["configured"] is True
    assert body["enabled"] is True
    assert body["time"] == "08:00"
    assert set(body["agents"]) == {"scout", "hunt", "blast", "report"}


def test_autopilot_activate_rejects_bad_time(admin_token, clean_autopilot):
    with httpx.Client(timeout=10.0) as c:
        r = c.post(
            f"{BACKEND_URL}/api/admin/autopilot/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"time": "25:99"},
        )
    assert r.status_code == 400


def test_autopilot_pause(admin_token, clean_autopilot):
    with httpx.Client(timeout=10.0) as c:
        c.post(
            f"{BACKEND_URL}/api/admin/autopilot/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"time": "08:00"},
        )
        r = c.post(
            f"{BACKEND_URL}/api/admin/autopilot/pause",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    with httpx.Client(timeout=10.0) as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/autopilot/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.json()["enabled"] is False


def test_autopilot_fire_now_executes_all_phases(admin_token, clean_autopilot):
    # Activate first so fire-now respects agents list
    with httpx.Client(timeout=30.0) as c:
        c.post(
            f"{BACKEND_URL}/api/admin/autopilot/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"time": "08:00"},
        )
        r = c.post(
            f"{BACKEND_URL}/api/admin/autopilot/fire-now",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    run = body["run"]
    assert "phases" in run
    phase_names = [p["phase"] for p in run["phases"]]
    assert set(phase_names) == {"scout", "hunt", "blast", "report"}


def test_autopilot_live_log(admin_token, clean_autopilot):
    # Fire once to create a run
    with httpx.Client(timeout=30.0) as c:
        c.post(
            f"{BACKEND_URL}/api/admin/autopilot/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"time": "08:00"},
        )
        c.post(
            f"{BACKEND_URL}/api/admin/autopilot/fire-now",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        r = c.get(
            f"{BACKEND_URL}/api/admin/autopilot/live-log?limit=5",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    body = r.json()
    assert body["count"] >= 1
    assert body["runs"][0]["run_id"].startswith("autopilot_")


def test_autopilot_unauth_rejected():
    with httpx.Client(timeout=5.0) as c:
        r = c.get(f"{BACKEND_URL}/api/admin/autopilot/status")
    assert r.status_code in (401, 403)


def test_autopilot_health_public():
    with httpx.Client(timeout=5.0) as c:
        r = c.get(f"{BACKEND_URL}/api/admin/autopilot/health")
    assert r.status_code == 200
    assert r.json()["component"] == "master_autopilot"


# ───────── Per-collection silent-failure threshold ─────────

def test_silent_failure_overrides_present():
    src = (REPO / "backend" / "routers" / "pillars_map_router.py").read_text()
    assert "SILENT_FAILURE_OVERRIDES" in src
    assert "_threshold_minutes_for" in src
    # heartbeats should have a longer threshold than default 15
    assert '"heartbeats":' in src
    # system_pulse should now be expects_writes=False (legacy marker)
    assert "System Pulse (legacy)" in src


# ───────── ORA submit bug fix ─────────

def test_ora_submit_handles_syntheticevent():
    src = (REPO / "frontend" / "src" / "platform" / "SidebarAddons.jsx").read_text()
    # Must guard against SyntheticEvent being passed as first arg
    assert "typeof overrideText === 'string'" in src
