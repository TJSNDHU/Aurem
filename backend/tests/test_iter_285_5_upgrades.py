"""iter 285.5 — 4 Recommended Upgrades.

Validates:
  1. A2A widget-signal endpoint emits event onto a2a_events
  2. MTTH by-tier breakdown returns 3 tiers × 3 windows shape
  3. Audit freshness (bytes threshold) detects degraded widgets
  4. Sidebar organizer groups 62 widgets into pillar buckets
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
A2A_AUDIT = REPO / "backend" / "routers" / "a2a_audit_router.py"

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


# ───────── Upgrade 1: widget-signal ─────────

def test_widget_signal_emits_a2a(admin_token):
    """Widget-signal endpoint must record an a2a_events row."""
    with _client() as c:
        r = c.post(
            f"{BACKEND_URL}/api/admin/a2a/widget-signal",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"widget": "global_pulse", "action": "refresh",
                  "context": {"range": "7d", "_test_": True}},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["a2a_emitted"] is True
    assert body["widget"] == "global_pulse"
    assert body["pillar"] == "p4_cognition"

    # Verify DB row
    env = _env()

    async def _check():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        doc = await db.a2a_events.find_one(
            {"from_agent": "widget:global_pulse", "event": "widget_refresh"},
            sort=[("timestamp", -1)],
        )
        return doc

    doc = asyncio.run(_check())
    assert doc is not None
    assert (doc.get("payload") or {}).get("pillar") == "p4_cognition"


def test_widget_signal_rejects_unknown_widget(admin_token):
    """Non-existent widgets still emit but default to cockpit pillar."""
    with _client() as c:
        r = c.post(
            f"{BACKEND_URL}/api/admin/a2a/widget-signal",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"widget": "fake_widget_xyz", "action": "test"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["widget"] == "fake_widget_xyz"
    assert body["pillar"] == "cockpit"


def test_widget_signal_requires_widget_field(admin_token):
    with _client() as c:
        r = c.post(
            f"{BACKEND_URL}/api/admin/a2a/widget-signal",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"action": "refresh"},
        )
    assert r.status_code == 400


# ───────── Upgrade 2: MTTH tier breakdown ─────────

def test_mtth_by_tier_shape(admin_token):
    with _client() as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/mtth/by-tier",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "tiers" in body
    for w in ("24h", "7d", "30d"):
        assert w in body["tiers"]
        for tier in ("tier_1", "tier_2", "tier_3"):
            t = body["tiers"][w][tier]
            assert "name" in t
            assert "count" in t
            assert "median_human" in t


def test_mtth_by_tier_classifies_correctly(admin_token):
    """Seed a stale_preview_pod fix → tier 1; unknown → tier 3."""
    env = _env()
    now = datetime.now(timezone.utc)

    async def _seed():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        # Tier 1 classifier
        await db.autonomous_repair_events.insert_one({
            "kind": "verify", "ok": True,
            "ts_iso": (now - timedelta(minutes=5)).isoformat(),
            "cycle_ts_iso": (now - timedelta(minutes=6)).isoformat(),
            "classification": "stale_preview_pod",
            "evidence": {"cycle_started_at": (now - timedelta(minutes=6)).isoformat()},
        })
        # Tier 3 classifier
        await db.autonomous_repair_events.insert_one({
            "kind": "verify", "ok": True,
            "ts_iso": (now - timedelta(minutes=3)).isoformat(),
            "cycle_ts_iso": (now - timedelta(minutes=45)).isoformat(),
            "classification": "unknown",
            "evidence": {"cycle_started_at": (now - timedelta(minutes=45)).isoformat()},
        })

    async def _cleanup():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        await db.autonomous_repair_events.delete_many(
            {"classification": {"$in": ["stale_preview_pod", "unknown"]}, "evidence.cycle_started_at": {"$gte": (now - timedelta(minutes=50)).isoformat()}}
        )

    asyncio.run(_seed())
    try:
        with _client() as c:
            r = c.get(
                f"{BACKEND_URL}/api/admin/mtth/by-tier",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        body = r.json()
        t1 = body["tiers"]["24h"]["tier_1"]
        t3 = body["tiers"]["24h"]["tier_3"]
        assert t1["count"] >= 1
        assert t3["count"] >= 1
        # Tier 1 should be fast (~60s), tier 3 should be slow (~45m)
        assert t1["median_seconds"] < 300
        assert t3["median_seconds"] > 1000
    finally:
        asyncio.run(_cleanup())


# ───────── Upgrade 3: Audit freshness ─────────

def test_audit_freshness_checks_bytes(admin_token):
    """Audit response must include min_bytes + fresh + http_ok per widget."""
    with _client(timeout=30.0) as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/a2a/audit/widgets",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    # Pick any widget with min_bytes > 0 to check the freshness field
    widget_with_threshold = next(
        (w for w in body["widgets"] if w.get("min_bytes", 0) > 0),
        None,
    )
    assert widget_with_threshold is not None
    for k in ("min_bytes", "http_ok", "fresh", "bytes"):
        assert k in widget_with_threshold
    # Degraded field must exist
    assert "degraded" in body


# ───────── Upgrade 4: Sidebar organizer ─────────

def test_sidebar_organizer_groups_all_62_widgets(admin_token):
    with _client() as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/a2a/sidebar/organized",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total_widgets"] >= 62
    pillars = {p["pillar"]: p for p in body["pillars"]}
    # Must have all 5 pillar buckets
    for key in ("cockpit", "p1_sales", "p2_billing", "p3_monitor", "p4_cognition"):
        assert key in pillars
        assert pillars[key]["count"] > 0
        assert pillars[key]["label"]
    # Sum must equal total
    total = sum(p["count"] for p in body["pillars"])
    assert total == body["total_widgets"]


def test_sidebar_widgets_have_required_fields(admin_token):
    with _client() as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/a2a/sidebar/organized",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    body = r.json()
    sample = body["pillars"][0]["widgets"][0]
    for k in ("widget", "label", "endpoint", "min_bytes"):
        assert k in sample
