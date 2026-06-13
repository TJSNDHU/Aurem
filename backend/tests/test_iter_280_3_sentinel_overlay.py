"""
Iter 280.3 — Sentinel Overlay + Served-From + Sync verification.

Asserts that /overview, /heartbeat, and /sync all expose the sentinel overlay
and the cache-age transparency fields so Dev Console and Pillars Map show
consistent truth.
"""
from __future__ import annotations

import os
import time
import hashlib
from datetime import datetime, timezone, timedelta

import pytest
import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

load_dotenv("/app/backend/.env")

API_BASE = os.environ.get("AUREM_E2E_BASE", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _admin_token():
    r = httpx.post(
        f"{API_BASE}/api/auth/login",
        json={"email": "teji.ss1986@gmail.com", "password": os.environ.get("AUREM_ADMIN_PASSWORD", "")},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def _headers():
    return {"Authorization": f"Bearer {_admin_token()}"}


def test_overview_has_sentinel_overlay_keys():
    r = httpx.get(f"{API_BASE}/api/admin/pillars-map/overview", headers=_headers(), timeout=15)
    assert r.status_code == 200
    d = r.json()
    overlay = d.get("sentinel_overlay")
    assert overlay is not None, "overview must embed sentinel_overlay"
    for k in ("errors_1h", "errors_24h", "critical_alerts", "verdict",
              "hot_threshold_1h", "warm_threshold_1h"):
        assert k in overlay, f"overlay missing {k}"
    assert overlay["verdict"] in ("green", "yellow", "red")


def test_heartbeat_reports_served_from_and_age():
    r = httpx.get(f"{API_BASE}/api/admin/pillars-map/heartbeat", headers=_headers(), timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "served_from" in d
    assert d["served_from"] in ("cache", "live")
    assert "cached_age_sec" in d
    assert "stale" in d


def test_sync_forces_refresh_and_returns_overlay():
    r = httpx.post(f"{API_BASE}/api/admin/pillars-map/sync", headers=_headers(), timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    assert d.get("forced") is True
    assert "sentinel_overlay" in d


@pytest.mark.asyncio
async def test_overlay_escalates_p3_monitor_on_error_burst():
    """Inject >hot_threshold errors → verify p3_monitor pillar flips to red."""
    cli = AsyncIOMotorClient(MONGO_URL)
    db = cli[DB_NAME]
    now = datetime.now(timezone.utc)

    # Clean first
    await db.client_errors.delete_many({"injected_by": "test_iter_280_3"})

    # Inject 25 (exceeds hot threshold of 20)
    docs = []
    for i in range(25):
        docs.append({
            "session_id": f"iter280_3_test_{i}",
            "ts": now - timedelta(minutes=i),
            "signature_hash": hashlib.md5(f"sig_{i}".encode()).hexdigest(),
            "url": "/test/iter280_3",
            "classification": "test_synthetic",
            "injected_by": "test_iter_280_3",
        })
    await db.client_errors.insert_many(docs)

    try:
        # Force fresh /overview (not cached snapshot from before injection)
        r = httpx.get(f"{API_BASE}/api/admin/pillars-map/overview",
                      headers=_headers(), timeout=15)
        assert r.status_code == 200
        d = r.json()
        overlay = d["sentinel_overlay"]
        assert overlay["errors_1h"] >= 20, \
            f"expected ≥20 errors_1h after injection, got {overlay['errors_1h']}"
        assert overlay["verdict"] == "red", \
            f"expected verdict red at errors_1h={overlay['errors_1h']}, got {overlay['verdict']}"

        p3 = next((p for p in d["pillars"] if p.get("key") == "p3_monitor"), None)
        assert p3 is not None
        assert p3["status"] == "red", \
            f"p3_monitor must escalate to red on burst, got {p3['status']}"
        assert p3.get("sentinel_overlay") is not None
    finally:
        await db.client_errors.delete_many({"injected_by": "test_iter_280_3"})
        cli.close()


def test_frontend_pillars_map_references_sync_button():
    path = "/app/frontend/src/platform/AdminPillarsMap.jsx"
    with open(path) as fh:
        src = fh.read()
    assert "sync-pillars-now-btn" in src
    assert "sentinel-overlay-banner" in src
    assert "served-from-strip" in src
    assert "/api/admin/pillars-map/sync" in src


def test_helper_cache_age_increments():
    """get_cached_age_seconds should increment between two reads."""
    from routers.pillars_map_router import set_cached_snapshot, get_cached_age_seconds

    set_cached_snapshot({"fake": True})
    a1 = get_cached_age_seconds()
    time.sleep(0.5)
    a2 = get_cached_age_seconds()
    assert a2 > a1, f"age should increase: {a1} → {a2}"


def test_sentinel_thresholds_are_documented_constants():
    from routers.pillars_map_router import SENTINEL_HOT_1H, SENTINEL_WARM_1H
    assert isinstance(SENTINEL_HOT_1H, int) and SENTINEL_HOT_1H > 0
    assert isinstance(SENTINEL_WARM_1H, int) and SENTINEL_WARM_1H > 0
    assert SENTINEL_HOT_1H > SENTINEL_WARM_1H, "hot must be stricter than warm"
