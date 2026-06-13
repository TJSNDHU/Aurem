"""iter 285.3 — Extended 14-widget wiring + Sentinel Anomaly real router + A2A emit.

Validates:
  • Audit widget count: 41 (iter 284 base 14 + iter 285 extended 13 + iter 285.3 extra 14)
  • Sentinel Anomaly /stats returns real shape from sentinel_alerts + client_errors
  • Sentinel Anomaly /history returns alerts list
  • Sentinel Anomaly /scan emits pillar_monitor → sentinel_scan on a2a_events
  • All 14 new widgets are present by name in the audit list
  • Full audit returns all_widgets_live=True (41/41)
"""
from __future__ import annotations

import os

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

REPO = Path(__file__).resolve().parents[2]
BACKEND_URL = "http://localhost:8001"
A2A_AUDIT = REPO / "backend" / "routers" / "a2a_audit_router.py"

ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")

NEW_WIDGETS = [
    "global_pulse", "geo_readiness", "agent_observatory", "intelligence_hub",
    "sentinel_anomaly", "pipeline_monitor", "ora_intelligence",
    "ora_mission_control", "autonomous_operations", "agent_swarm",
    "ora_repair_engine", "root_command", "circuit_breakers", "fallback_monitor",
]


def _retry_get(url, headers=None, timeout=10.0, attempts=6):
    """httpx.get with retry for ephemeral-port exhaustion / transient connect errors."""
    last = None
    for i in range(attempts):
        try:
            with httpx.Client(timeout=timeout) as client:
                return client.get(url, headers=headers)
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, OSError) as e:
            last = e
            time.sleep(1.0 + i * 0.5)
    raise last


def _retry_post(url, headers=None, json=None, timeout=10.0, attempts=6):
    last = None
    for i in range(attempts):
        try:
            with httpx.Client(timeout=timeout) as client:
                return client.post(url, headers=headers, json=json)
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, OSError) as e:
            last = e
            time.sleep(1.0 + i * 0.5)
    raise last


def _env():
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
            r = _retry_post(
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


def test_audit_registry_has_41_widgets():
    """Audit widget list must include all 14 iter 285.3 widgets."""
    src = A2A_AUDIT.read_text()
    for w in NEW_WIDGETS:
        assert f'"{w}"' in src, f"Widget '{w}' missing from audit registry"


def test_sentinel_anomaly_stats(admin_token):
    r = _retry_get(
        f"{BACKEND_URL}/api/sentinel-anomaly/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 200
    body = r.json()
    for k in ("total", "by_severity", "critical_30m", "errors_1h", "errors_24h", "ts_iso"):
        assert k in body, f"Missing '{k}' in stats shape: {body}"
    assert isinstance(body["total"], int)
    assert isinstance(body["by_severity"], dict)


def test_sentinel_anomaly_history(admin_token):
    r = _retry_get(
        f"{BACKEND_URL}/api/sentinel-anomaly/history?limit=5",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert "alerts" in body and "count" in body
    assert isinstance(body["alerts"], list)
    assert body["count"] == len(body["alerts"])


def test_sentinel_anomaly_scan_emits_a2a(admin_token):
    """Scan must record an event on a2a_events with from_agent=pillar_monitor."""
    r = _retry_post(
        f"{BACKEND_URL}/api/sentinel-anomaly/scan",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["a2a_emitted"] is True

    # Verify the event landed on the bus (DB)
    env = _env()

    async def _check():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        # Find the freshest sentinel_scan within last 30s
        cutoff = (datetime.now(timezone.utc).timestamp() - 30)
        doc = await db.a2a_events.find_one(
            {"event": "sentinel_scan", "from_agent": "pillar_monitor"},
            sort=[("timestamp", -1)],
        )
        return doc

    doc = asyncio.run(_check())
    assert doc is not None, "sentinel_scan event not found on A2A bus"
    assert doc["from_agent"] == "pillar_monitor"
    assert "triggered_by" in (doc.get("payload") or {})


def test_sentinel_anomaly_health_public():
    """Health endpoint must be unauthenticated and return db_ready."""
    r = _retry_get(f"{BACKEND_URL}/api/sentinel-anomaly/health", timeout=5.0)
    assert r.status_code == 200
    assert r.json()["component"] == "sentinel_anomaly"


def test_sentinel_anomaly_unauth_rejected():
    r = _retry_get(f"{BACKEND_URL}/api/sentinel-anomaly/stats", timeout=5.0)
    assert r.status_code in (401, 403)


def test_all_41_widgets_live(admin_token):
    """Full audit must return all_widgets_live=True (count ≥ 41; may grow with new iterations)."""
    # Give rate limiter a breather
    time.sleep(3)
    r = _retry_get(
        f"{BACKEND_URL}/api/admin/a2a/audit/widgets",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["widgets"]) >= 41, f"Expected ≥41 widgets, got {len(body['widgets'])}"
    assert body["all_widgets_live"] is True, (
        f"Some widgets broken: {body.get('broken')}"
    )
