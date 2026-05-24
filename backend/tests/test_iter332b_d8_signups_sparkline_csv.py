"""
iter 332b D-8 — 24h sparkline + CSV export for developer signups.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import pytest_asyncio


def _api_base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL")
    if not base:
        envf = pathlib.Path("/app/frontend/.env")
        if envf.exists():
            for line in envf.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    base = line.split("=", 1)[1].strip()
                    break
    return (base or "http://localhost:8001").rstrip("/")


def _mint_admin_token() -> str:
    from config import JWT_ALGORITHM, JWT_SECRET
    return jwt.encode(
        {"user_id": f"a_{uuid.uuid4().hex[:8]}",
         "is_admin": True, "is_super_admin": True,
         "email": "d8@aurem.local",
         "exp": int(time.time()) + 3600},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.developer_portal_core import set_db as _set_dev_db
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    _set_dev_db(database)
    yield database
    await database.developer_accounts.delete_many(
        {"email": {"$regex": "^pytest_d8_"}}
    )
    client.close()


@pytest.mark.asyncio
async def test_timeseries_returns_24_buckets_and_counts_recent(db):
    """Recent signup in the last hour should land in the last bucket."""
    now = datetime.now(timezone.utc)
    # Seed two signups: one 30 minutes ago, one 5 hours ago
    for offset_min in (30, 300):
        await db.developer_accounts.insert_one({
            "user_id": f"pytest_d8_{uuid.uuid4().hex[:8]}",
            "email":   f"pytest_d8_{uuid.uuid4().hex[:8]}@x.test",
            "name":    "D8 signup",
            "plan":    "free", "tokens_remaining": 1000,
            "email_verified": True, "abuse_flagged": False,
            "created_at": (now - timedelta(minutes=offset_min)).isoformat(),
        })
    tok = _mint_admin_token()

    def _call():
        with httpx.Client(timeout=15.0) as c:
            return c.get(f"{_api_base()}/api/admin/developers/timeseries",
                          headers={"Authorization": f"Bearer {tok}"})
    r = await asyncio.to_thread(_call)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert len(j["buckets"]) == 24
    assert j["total_24h"] >= 2
    # Last bucket (most recent hour) should include the 30-min-ago signup
    assert j["buckets"][-1] >= 1


def test_timeseries_rejects_anon():
    with httpx.Client(timeout=15.0) as c:
        r = c.get(f"{_api_base()}/api/admin/developers/timeseries")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_csv_export_returns_real_csv_and_strips_secrets(db):
    """CSV must include header + at least one row, must NOT leak password
    hashes or BYOK keys even if those fields exist on the doc."""
    await db.developer_accounts.insert_one({
        "user_id": f"pytest_d8_{uuid.uuid4().hex[:8]}",
        "email":   f"pytest_d8_{uuid.uuid4().hex[:8]}@x.test",
        "name":    "CSV Test",
        "plan":    "free", "tokens_remaining": 1000,
        "tokens_total_used": 250,
        "email_verified": True, "abuse_flagged": False,
        "github_username": "csvtester",
        "password_hash": "MUST_NOT_LEAK",
        "byok_keys": {"anthropic": "MUST_NOT_LEAK"},
        "signup_ip": "9.9.9.9",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    tok = _mint_admin_token()

    def _call():
        with httpx.Client(timeout=15.0) as c:
            return c.get(f"{_api_base()}/api/admin/developers/export.csv",
                          headers={"Authorization": f"Bearer {tok}"})
    r = await asyncio.to_thread(_call)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/csv")
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd and ".csv" in cd
    body = r.text
    assert body.startswith("email,name,plan,verified,github,")
    assert "MUST_NOT_LEAK" not in body, "Secret leaked into CSV export."
    assert "9.9.9.9" not in body, "Signup IP leaked into CSV export."
    assert "csvtester" in body
    assert "CSV Test" in body


def test_csv_export_rejects_anon():
    with httpx.Client(timeout=15.0) as c:
        r = c.get(f"{_api_base()}/api/admin/developers/export.csv")
    assert r.status_code in (401, 403)


# ───────────────────────── Frontend wiring guards ────────────────────────

def test_pulse_tile_has_sparkline():
    src = open(
        "/app/frontend/src/platform/admin/DeveloperPortalPulseTile.jsx"
    ).read()
    assert "/api/admin/developers/timeseries" in src
    for tid in ("dev-pulse-signups-24h",
                "dev-pulse-signups-24h-count",
                "dev-pulse-signups-sparkline",
                "dev-pulse-view-all"):
        assert tid in src, f"Missing testid {tid}"


def test_signups_page_has_csv_button():
    src = open(
        "/app/frontend/src/platform/AdminDeveloperSignups.jsx"
    ).read()
    assert "admin-dev-export-csv" in src
    assert "/api/admin/developers/export.csv" in src
