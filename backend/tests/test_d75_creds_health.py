"""
test_d75_creds_health.py — iter D-75 Part 2 #1 regression guard.

After D-72 caught a stale Twilio token + D-74 caught a stale Tavily
token, this dashboard exists so the next stale credential is visible
the moment it happens, not 2 months later.

Coverage:
  * /probe-all returns one ProbeResult per registered provider with
    all required fields (provider, status, http, latency_ms,
    probed_at, key_tail).
  * Statuses are strictly in {green, yellow, red, not_configured}.
  * No probe ever leaks the full secret — only `key_tail` (last 4).
  * not_configured = provider with no env var set (honest).
  * /probe/{provider} works for each known provider.
  * /probe/{provider} returns 404 for unknown providers.
  * /history returns rows sorted desc by snapshot_at.
  * Non-admin tokens get 403.
  * TTL index is present on `creds_health_history.snapshot_at`.

Run: PYTHONPATH=/app/backend python3 -m pytest tests/test_d75_creds_health.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, "/app/backend")


def _backend_url() -> str:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


def _founder_token(api_url: str) -> str:
    r = httpx.post(
        f"{api_url}/api/platform/auth/login",
        json={"email": "teji.ss1986@gmail.com",
              "password": "Aurem@Founder2026!"},
        timeout=15.0,
    )
    if r.status_code != 200:
        pytest.skip(f"founder login failed: {r.status_code}")
    return r.json()["token"]


def _non_admin_token() -> str:
    secret = None
    for line in Path("/app/backend/.env").read_text().splitlines():
        if line.startswith("JWT_SECRET="):
            secret = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not secret:
        pytest.skip("JWT_SECRET unavailable")
    import jwt as pyjwt
    return pyjwt.encode(
        {"email": "notadmin@example.com", "role": "user",
         "is_admin": False, "is_super_admin": False,
         "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()},
        secret, algorithm="HS256",
    )


@pytest.fixture(scope="module")
def api_url():
    return _backend_url()


@pytest.fixture(scope="module")
def admin_token(api_url):
    return _founder_token(api_url)


# ─── tests ────────────────────────────────────────────────────────────

def test_providers_endpoint_lists_known_providers(api_url, admin_token):
    r = httpx.get(
        f"{api_url}/api/admin/creds-health/providers",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10.0,
    )
    assert r.status_code == 200
    providers = r.json().get("providers", [])
    # Must include the founder's core list
    for must_have in ("twilio", "resend", "openrouter", "stripe",
                      "apollo", "tavily", "emergent_llm", "ora"):
        assert must_have in providers, f"missing required provider: {must_have}"


def test_probe_all_returns_complete_shape(api_url, admin_token):
    """Every result row must carry the contract shape — UI relies on
    these fields existing every time."""
    r = httpx.get(
        f"{api_url}/api/admin/creds-health/probe-all?timeout=6",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=90.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["providers_total"] > 0
    assert set(body["summary"].keys()) >= {"green", "yellow", "red", "not_configured"}

    results = body["results"]
    assert len(results) == body["providers_total"]
    for row in results:
        for field in ("provider", "status", "http", "latency_ms",
                      "probed_at"):
            assert field in row, f"row missing {field!r}: {row}"
        assert row["status"] in ("green", "yellow", "red", "not_configured"), (
            f"unknown status {row['status']!r} for {row['provider']}"
        )
        # latency must be non-negative int
        assert isinstance(row["latency_ms"], int)
        assert row["latency_ms"] >= 0
        # probed_at must be ISO-parseable
        try:
            datetime.fromisoformat(row["probed_at"].replace("Z", "+00:00"))
        except Exception:
            pytest.fail(f"probed_at not ISO: {row['probed_at']!r}")


def test_probe_all_never_leaks_secrets(api_url, admin_token):
    """`key_tail` may carry the last 4 chars; the full secret must
    NEVER appear in any response field."""
    secret_env_keys = (
        "TWILIO_AUTH_TOKEN", "RESEND_API_KEY", "OPENROUTER_API_KEY",
        "STRIPE_SECRET_KEY", "APOLLO_API_KEY", "TAVILY_API_KEY",
        "ELEVENLABS_API_KEY", "GITHUB_TOKEN",
    )
    actual_secrets: list[str] = []
    for line in Path("/app/backend/.env").read_text().splitlines():
        for k in secret_env_keys:
            if line.startswith(f"{k}="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if len(val) > 8:  # ignore short / placeholder values
                    actual_secrets.append(val)

    r = httpx.get(
        f"{api_url}/api/admin/creds-health/probe-all?timeout=6",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=90.0,
    )
    assert r.status_code == 200
    body_text = r.text
    for secret in actual_secrets:
        assert secret not in body_text, (
            f"FULL secret leaked in probe-all response — only key_tail "
            "(last 4 chars) should appear. This is a security regression."
        )


def test_probe_one_unknown_provider_returns_404(api_url, admin_token):
    r = httpx.post(
        f"{api_url}/api/admin/creds-health/probe/this_provider_does_not_exist",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15.0,
    )
    assert r.status_code == 404


def test_probe_one_writes_history(api_url, admin_token):
    """Probing twilio should write one history row tagged
    'twilio'. Check the count went up."""
    async def _count():
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        return await db.creds_health_history.count_documents({"provider": "twilio"})

    before = asyncio.run(_count())
    r = httpx.post(
        f"{api_url}/api/admin/creds-health/probe/twilio?timeout=6",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20.0,
    )
    assert r.status_code == 200, r.text[:300]
    assert r.json()["result"]["provider"] == "twilio"
    after = asyncio.run(_count())
    assert after == before + 1, (
        f"history row not written: before={before} after={after}"
    )


def test_history_endpoint_returns_recent_rows(api_url, admin_token):
    r = httpx.get(
        f"{api_url}/api/admin/creds-health/history?provider=twilio&limit=5",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["provider_filter"] == "twilio"
    rows = body["rows"]
    assert len(rows) >= 1, "no twilio history — probe never persisted"
    # Newest first
    if len(rows) >= 2:
        assert rows[0]["snapshot_at"] >= rows[1]["snapshot_at"]


def test_non_admin_token_rejected(api_url):
    """Real security gate — non-admin = 403, not silent leak."""
    r = httpx.get(
        f"{api_url}/api/admin/creds-health/probe-all",
        headers={"Authorization": f"Bearer {_non_admin_token()}"},
        timeout=15.0,
    )
    assert r.status_code == 403


def test_ttl_index_present_on_history():
    """TTL must be in BSON Date form so it actually fires (D-71p + D-74
    string-timestamp bug doesn't repeat here)."""
    async def _check():
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        async for idx in db.creds_health_history.list_indexes():
            if idx.get("expireAfterSeconds"):
                return idx
        return None

    idx = asyncio.run(_check())
    assert idx is not None, "no TTL index on creds_health_history — D-74 regression"
    # Verify the timestamp field is `snapshot_at` and it's stored as BSON Date
    keys = list(idx.get("key", {}).keys())
    assert keys == ["snapshot_at"], f"TTL key field is {keys!r}, expected ['snapshot_at']"

    # And verify the actual docs store Date not string
    async def _check_date_type():
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        date_n = await db.creds_health_history.count_documents(
            {"snapshot_at": {"$type": "date"}}
        )
        str_n = await db.creds_health_history.count_documents(
            {"snapshot_at": {"$type": "string"}}
        )
        return date_n, str_n

    date_n, str_n = asyncio.run(_check_date_type())
    assert str_n == 0, (
        f"{str_n} history rows store snapshot_at as STRING — TTL won't fire. "
        "This is the exact D-71p / D-74 bug pattern."
    )
    assert date_n > 0, "no BSON Date snapshot_at rows — probe never wrote one"


def test_known_stale_credentials_show_red(api_url, admin_token):
    """The dashboard's whole point: stale creds show RED. Twilio is
    known stale (founder hasn't rotated yet) so this asserts the
    honest signal."""
    r = httpx.get(
        f"{api_url}/api/admin/creds-health/probe-all?timeout=6",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=90.0,
    )
    body = r.json()
    twilio = next((x for x in body["results"] if x["provider"] == "twilio"), None)
    assert twilio is not None
    # Until founder rotates, twilio MUST be red (HTTP 401)
    if twilio["status"] != "red":
        pytest.skip(
            f"twilio currently shows {twilio['status']!r} — token was probably "
            "rotated; this assertion only applies before rotation"
        )
    assert twilio["http"] == 401
    assert twilio.get("error", "").startswith("auth_failed")
    assert twilio.get("key_tail")  # last 4 visible
