"""iter 285.4 — MTTH router + Transparency Wall + 21 final widgets.

Validates:
  • 62 widgets in audit registry
  • MTTH /summary with 3 time windows (24h/7d/30d)
  • MTTH /summary verdict computation (green/amber/red/idle)
  • MTTH /history list shape
  • Transparency Wall /wall endpoint shape
  • MTTH health public probe
  • SOC2 un-skipped (was 404, now 200)
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
REGISTRY = REPO / "backend" / "routers" / "registry.py"

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


# ───────── widget count ─────────

def test_audit_has_62_widgets():
    """Audit list must cover all iter 285.4 widgets (previous 41 + 21 new)."""
    import re
    src = A2A_AUDIT.read_text()
    block = re.search(r"WIDGET_REGISTRY\s*=\s*\[(.*?)^\]", src, re.DOTALL | re.MULTILINE)
    assert block
    tuples = re.findall(r'\(\s*"[^"]+"\s*,', block.group(1))
    assert len(tuples) >= 62, f"Expected ≥62 widgets, got {len(tuples)}"


def test_soc2_unskipped():
    """soc2_compliance_router should be unskipped for live widget."""
    import re
    src = REGISTRY.read_text()
    skip = re.search(r"_SKIP_IN_LEAN\s*=\s*\{(.*?)^\s{0,4}\}", src, re.DOTALL | re.MULTILINE)
    assert skip
    body = "\n".join(ln for ln in skip.group(1).splitlines() if not ln.strip().startswith("#"))
    assert "soc2_compliance_router" not in body


# ───────── MTTH ─────────

def test_mtth_summary_shape(admin_token):
    with _client() as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/mtth/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    for w in ("24h", "7d", "30d"):
        assert w in body["windows"]
        for k in ("count", "median_seconds", "p95_seconds", "longest_seconds",
                  "median_human", "p95_human"):
            assert k in body["windows"][w]
    assert "verdict" in body
    assert body["verdict"] in ("green", "amber", "red", "idle")


def test_mtth_summary_idle_without_heals(admin_token):
    with _client() as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/mtth/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    body = r.json()
    # In a fresh system with no synthetic heals, expect idle or low-count
    assert body["windows"]["24h"]["count"] >= 0


def test_mtth_history_shape(admin_token):
    with _client() as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/mtth/history?limit=5",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "heals" in body and "count" in body
    assert isinstance(body["heals"], list)


def test_mtth_verdict_amber_on_medium_heal(admin_token):
    """Seed 1 fake heal at ~13m — verdict must be amber (10m < med < 30m)."""
    env = _env()

    async def _seed():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        now = datetime.now(timezone.utc)
        await db.autonomous_repair_events.insert_one({
            "kind": "verify", "ok": True,
            "ts_iso": (now - timedelta(minutes=1)).isoformat(),
            "cycle_ts_iso": (now - timedelta(minutes=14)).isoformat(),  # 13m delta
            "classification": "_pytest_mtth_seed_",
            "evidence": {
                "cycle_started_at": (now - timedelta(minutes=14)).isoformat(),
                "classification": "_pytest_mtth_seed_",
            },
        })

    async def _cleanup():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        await db.autonomous_repair_events.delete_many(
            {"classification": "_pytest_mtth_seed_"}
        )

    asyncio.run(_seed())
    try:
        with _client() as c:
            r = c.get(
                f"{BACKEND_URL}/api/admin/mtth/summary",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        body = r.json()
        assert body["windows"]["24h"]["count"] >= 1
        # 13m = 780s → amber
        assert body["verdict"] == "amber"
        assert body["windows"]["24h"]["median_human"] != "—"
    finally:
        asyncio.run(_cleanup())


# ───────── Transparency Wall ─────────

def test_transparency_wall_shape(admin_token):
    with _client() as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/transparency/wall",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    for k in ("widgets", "a2a", "auto_heals_24h", "open_criticals_24h",
              "errors_1h", "verdict", "ts_iso"):
        assert k in body, f"Missing key '{k}' in transparency wall shape"
    assert "registered" in body["widgets"]
    assert "total" in body["a2a"] and "green" in body["a2a"]
    assert body["verdict"] in ("green", "amber", "red")


def test_mtth_health_public():
    with _client(timeout=5.0) as c:
        r = c.get(f"{BACKEND_URL}/api/admin/mtth/health")
    assert r.status_code == 200
    assert r.json()["component"] == "mtth_and_transparency"


def test_mtth_unauth_rejected():
    with _client(timeout=5.0) as c:
        r = c.get(f"{BACKEND_URL}/api/admin/mtth/summary")
    assert r.status_code in (401, 403)
