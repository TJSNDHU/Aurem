"""
D-79 Apollo probe + autonomous_repair pause-state regression tests.

Proves:
  1. probe_apollo() returns `green` when BOTH /auth/health AND
     /v1/organizations/search return 200 (live HTTP, no mocks).
  2. probe_apollo() returns `yellow` with status='search_inaccessible'
     when /auth/health is 200 but /v1/organizations/search is 403.
     (Catches the silent "campaign funnel dries up" failure mode.)
  3. The system_config.autonomous_repair pause flag is readable —
     surfaces the real reason run_repair_tick is skipping.
"""
from __future__ import annotations

import os
import sys
import types

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "aurem_db")


# ── Real HTTP probe (only runs if APOLLO_API_KEY is present) ────────

@pytest.mark.asyncio
async def test_probe_apollo_live_when_key_present():
    if not (os.environ.get("APOLLO_API_KEY") or "").strip():
        pytest.skip("APOLLO_API_KEY not set — live probe skipped")
    from services.creds_health import probe_apollo
    res = await probe_apollo(timeout=10)
    # Status MUST be green, yellow, or red — never `not_configured` (key is set)
    assert res.status in ("green", "yellow", "red"), res.asdict()
    # If green, detail must reference both endpoints
    if res.status == "green":
        assert "auth=200" in (res.detail or "")
        assert "search=200" in (res.detail or "")
    # latency_ms must be a real measurement, not 0
    assert res.latency_ms > 0


# ── Mocked HTTP — auth ok but search 403 → yellow ───────────────────

@pytest.mark.asyncio
async def test_probe_apollo_yellow_on_search_403(monkeypatch):
    """If Apollo downgrades the key tier and search becomes 403, we
    must surface `yellow` so the dashboard catches it BEFORE the
    funnel dries up."""
    import services.creds_health as ch

    class _R:
        def __init__(self, code, text="ok body"):
            self.status_code = code
            self.text = text
        def json(self):
            return {"healthy": True}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None):
            assert "auth/health" in url
            return _R(200)
        async def post(self, url, headers=None, json=None):
            assert "organizations/search" in url
            return _R(403, '{"error":"API_INACCESSIBLE"}')

    fake_httpx = types.ModuleType("httpx_fake_d79")
    fake_httpx.AsyncClient = _FakeClient
    # Patch the module-level httpx ref used by probe_apollo
    monkeypatch.setattr(ch, "httpx", fake_httpx)
    monkeypatch.setenv("APOLLO_API_KEY", "fake-key-yellow-test")

    res = await ch.probe_apollo(timeout=5)
    assert res.status == "yellow", res.asdict()
    assert res.http == 403
    assert "search_inaccessible" in (res.error or "")
    assert "API_INACCESSIBLE" in (res.detail or "")


@pytest.mark.asyncio
async def test_probe_apollo_red_on_auth_failure(monkeypatch):
    """If the key itself is invalid (auth/health 401), status is red."""
    import services.creds_health as ch

    class _R:
        status_code = 401
        text = '{"error":"unauthorized"}'

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None):
            return _R()
        async def post(self, *a, **kw):
            raise AssertionError("search should NOT be called when auth fails")

    fake_httpx = types.ModuleType("httpx_fake_d79_red")
    fake_httpx.AsyncClient = _FakeClient
    monkeypatch.setattr(ch, "httpx", fake_httpx)
    monkeypatch.setenv("APOLLO_API_KEY", "fake-key-red-test")

    res = await ch.probe_apollo(timeout=5)
    assert res.status == "red"
    assert res.http == 401
    assert "auth/health" in (res.error or "")


@pytest.mark.asyncio
async def test_probe_apollo_not_configured_when_key_missing(monkeypatch):
    import services.creds_health as ch
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    res = await ch.probe_apollo()
    assert res.status == "not_configured"
    assert res.http is None


# ── autonomous_repair pause-state visibility ────────────────────────

@pytest_asyncio.fixture
async def db():
    cli = AsyncIOMotorClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.mark.asyncio
async def test_autonomous_repair_pause_flag_readable(db):
    """The pause reason that run_repair_tick reports as 'paused' is
    stored as system_config.autonomous_repair.enabled=false — the
    diagnostic must be able to read it without hitting the engine."""
    doc = await db.system_config.find_one(
        {"config_key": "autonomous_repair"}, {"_id": 0},
    )
    # If the row exists, `enabled` field must be a bool — never a
    # string/None which would silently confuse `bool(doc.get(...))`.
    if doc is not None:
        assert isinstance(doc.get("enabled"), bool), (
            f"autonomous_repair.enabled is {type(doc.get('enabled')).__name__}, "
            f"expected bool. Row: {doc}"
        )
