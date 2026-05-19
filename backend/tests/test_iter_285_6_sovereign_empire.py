"""iter 285.6 — Sovereign Node + Empire HUD + Live Campaign fix.

Validates:
  • POST /api/sovereign/heartbeat registers a node
  • GET /api/sovereign/nodes computes online/offline correctly
  • POST /api/sovereign/queue buffers events for offline nodes
  • POST /api/sovereign/sync/{id} drains queue
  • GET /api/empire-hud/nodes includes sovereign + integration nodes
  • LiveCampaignPipeline points at proximity+comms endpoints (no /api/campaigns/ 404)
  • ORA Command chips + Ctrl+/ shortcut present in SidebarAddons
  • A2A event emitted on heartbeat
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
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


def _client(timeout=10.0):
    return httpx.Client(timeout=timeout)


@pytest.fixture(scope="module")
def admin_token():
    for _ in range(5):
        try:
            with _client() as c:
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
def clean_test_nodes():
    """Clean up any test nodes before and after."""
    env = _env()

    async def _wipe():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        await db.sovereign_nodes.delete_many({"node_id": {"$regex": "^_test_"}})
        await db.sovereign_queue.delete_many({"node_id": {"$regex": "^_test_"}})

    asyncio.run(_wipe())
    yield
    asyncio.run(_wipe())


# ───────── Sovereign Node ─────────

def test_heartbeat_registers_node(admin_token, clean_test_nodes):
    with _client() as c:
        r = c.post(
            f"{BACKEND_URL}/api/sovereign/heartbeat",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"node_id": "_test_legion_alpha",
                  "node_name": "Legion Alpha",
                  "ip": "10.0.0.5",
                  "version": "1.0.0"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["node_id"] == "_test_legion_alpha"
    assert "ts_iso" in body


def test_nodes_list_marks_online_vs_offline(admin_token, clean_test_nodes):
    # Register a fresh node
    with _client() as c:
        c.post(
            f"{BACKEND_URL}/api/sovereign/heartbeat",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"node_id": "_test_legion_hot", "node_name": "Legion Hot",
                  "ip": "10.0.0.10"},
        )
    # Seed a stale node directly via DB
    env = _env()

    async def _stale():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        stale_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        await db.sovereign_nodes.insert_one({
            "node_id": "_test_legion_cold",
            "node_name": "Legion Cold",
            "ip": "10.0.0.11",
            "version": "0.9",
            "metadata": {},
            "last_heartbeat_at": stale_iso,
            "first_seen_at": stale_iso,
            "status": "online",  # stale stale; server should recompute offline
        })

    asyncio.run(_stale())

    with _client() as c:
        r = c.get(
            f"{BACKEND_URL}/api/sovereign/nodes",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    body = r.json()
    by_id = {n["node_id"]: n for n in body["nodes"]}
    assert by_id["_test_legion_hot"]["status"] == "online"
    assert by_id["_test_legion_cold"]["status"] == "offline"


def test_queue_and_sync_roundtrip(admin_token, clean_test_nodes):
    # Register node first
    with _client() as c:
        c.post(
            f"{BACKEND_URL}/api/sovereign/heartbeat",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"node_id": "_test_legion_queue"},
        )
        # Queue 3 events
        for i in range(3):
            c.post(
                f"{BACKEND_URL}/api/sovereign/queue",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"node_id": "_test_legion_queue",
                      "event_type": "sms_send",
                      "event_payload": {"idx": i}},
            )
        # Drain
        r = c.post(
            f"{BACKEND_URL}/api/sovereign/sync/_test_legion_queue",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    body = r.json()
    assert body["drained"] == 3
    assert len(body["events"]) == 3


def test_heartbeat_emits_a2a_event(admin_token, clean_test_nodes):
    with _client() as c:
        c.post(
            f"{BACKEND_URL}/api/sovereign/heartbeat",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"node_id": "_test_legion_a2a"},
        )
    env = _env()

    async def _find():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        return await db.a2a_events.find_one(
            {"from_agent": "sovereign:_test_legion_a2a", "event": "node_heartbeat"},
            sort=[("timestamp", -1)],
        )

    doc = asyncio.run(_find())
    assert doc is not None
    assert (doc.get("payload") or {}).get("node_id") == "_test_legion_a2a"


def test_sovereign_health_public():
    with _client(timeout=5.0) as c:
        r = c.get(f"{BACKEND_URL}/api/sovereign/health")
    assert r.status_code == 200
    assert r.json()["component"] == "sovereign_node"


def test_sovereign_auth_gate():
    with _client(timeout=5.0) as c:
        r = c.get(f"{BACKEND_URL}/api/sovereign/nodes")
    assert r.status_code in (401, 403)


# ───────── Empire HUD ─────────

def test_empire_hud_returns_integration_and_sovereign(admin_token, clean_test_nodes):
    with _client() as c:
        r = c.get(
            f"{BACKEND_URL}/api/empire-hud/nodes",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    ids = {n["id"]: n for n in body["nodes"]}
    # Must have the 4 integration nodes
    for expected in ("twilio", "whapi", "resend", "stripe"):
        assert expected in ids, f"Missing integration node: {expected}"
        assert ids[expected]["kind"] == "integration"
    # Must have at least one sovereign slot (placeholder if empty)
    sovereigns = [n for n in body["nodes"] if n["kind"] == "sovereign"]
    assert len(sovereigns) >= 1
    # Each node must have a verdict
    for n in body["nodes"]:
        assert n["verdict"] in ("green", "amber", "red", "grey")


# ───────── Live Campaign widget fix ─────────

def test_live_campaign_uses_real_endpoints():
    """LiveCampaignPipeline.jsx should point at proximity+comms, not /api/campaigns/."""
    src = (REPO / "frontend" / "src" / "platform" / "LiveCampaignPipeline.jsx").read_text()
    # Must not have an active fetch call to the deprecated endpoint
    assert 'fetch(`${API}/api/campaigns/`' not in src, (
        "LiveCampaignPipeline must not fetch deprecated /api/campaigns/ endpoint"
    )
    assert "/api/proximity/campaigns" in src
    assert "/api/comms/campaigns" in src


# ───────── ORA Command chips ─────────

def test_ora_command_chips_present():
    src = (REPO / "frontend" / "src" / "platform" / "SidebarAddons.jsx").read_text()
    assert "QUICK_CHIPS" in src
    # All 5 chip labels
    for lbl in ("scan", "brief", "blast", "leads", "health"):
        assert f'"{lbl}"' in src
    assert 'data-testid="ora-command-chips"' in src
    assert 'Ctrl + /' in src
    assert 'data-testid="ora-command-expand"' in src


def test_ora_command_keyboard_shortcut():
    src = (REPO / "frontend" / "src" / "platform" / "SidebarAddons.jsx").read_text()
    assert "ctrlKey" in src and "metaKey" in src
    assert "'/'" in src
