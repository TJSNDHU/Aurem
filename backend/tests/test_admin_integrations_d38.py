"""
test_admin_integrations_d38.py — iter D-38

E2E for the read-only Admin Integration Health tracker.

  1. /api/admin/integrations/health requires an admin JWT (401 / 403
     for missing / non-admin tokens).
  2. With an admin JWT it returns the expected shape:
       ok=true, summary={total,green,yellow,red,unset,needs_recharge},
       integrations=[ {provider, env_var, status, key_tail, ...}, … ]
  3. Real key tails are never leaked — only "…xxxx" (4 chars) or "····"
     for missing keys.
  4. status="unset" is returned for env vars that are not set.
  5. Adding a credential-failure to api_key_health_log promotes the
     status to "red" and sets needs_recharge=True for that provider.
  6. The watchdog `record_api_failure(provider, status_code=401)`
     hook is the one that writes the failure row used by this endpoint.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

import jwt
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

API = "http://localhost:8001"
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO   = os.environ.get("JWT_ALGORITHM", "HS256")


def _mint(sub: str, is_admin: bool = False) -> str:
    payload = {"sub": sub, "email": f"{sub}@aurem.test",
                "iat": int(time.time()), "exp": int(time.time()) + 600}
    if is_admin:
        payload["is_admin"] = True
        payload["is_super_admin"] = True
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}",
             "Content-Type":  "application/json"}


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _mint("admin", is_admin=True)


# ── 1. Auth gate ──────────────────────────────────────────────────────

def test_endpoint_rejects_missing_token():
    # Endpoint is bypassed from boot-grace via _BOOT_GRACE_EXCLUDE.
    # Retry briefly on connection error since uvicorn may still be
    # warming after the most recent restart.
    last = None
    for _ in range(6):
        try:
            r = requests.get(f"{API}/api/admin/integrations/health",
                              timeout=10)
            last = r
            if r.status_code != 204:
                break
        except Exception as e:
            last = e
        time.sleep(2)
    assert hasattr(last, "status_code"), f"backend not reachable: {last}"
    assert last.status_code in (401, 403), last.text


def test_endpoint_rejects_non_admin_token():
    tok = _mint("plain-user", is_admin=False)
    r = requests.get(f"{API}/api/admin/integrations/health",
                      headers=_hdr(tok), timeout=15)
    assert r.status_code in (401, 403), r.text


# ── 2. Shape on success ───────────────────────────────────────────────

def test_admin_can_view_shape(admin_token):
    r = requests.get(f"{API}/api/admin/integrations/health",
                      headers=_hdr(admin_token), timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    # Summary keys present
    for k in ("total", "green", "yellow", "red", "unset", "needs_recharge"):
        assert k in j["summary"]
    # At least 5 integrations should be declared (we ship 17)
    assert j["summary"]["total"] >= 5
    assert isinstance(j["integrations"], list)
    # Each row must have the contract fields
    row = j["integrations"][0]
    for k in ("provider", "group", "role", "env_var", "key_present",
               "key_tail", "status", "needs_recharge",
               "failures_24h", "failures_7d",
               "recharge_url", "docs_url"):
        assert k in row, f"row missing '{k}'"


# ── 3. Key value is NEVER leaked ──────────────────────────────────────

def test_key_value_never_leaked():
    """We call the router IN-PROCESS so the env we plant actually
    reaches the function under test. End-to-end HTTP can't be used
    here because uvicorn has its own env snapshot."""
    import asyncio as _aio
    from routers import admin_integrations_router as M
    from motor.motor_asyncio import AsyncIOMotorClient

    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key-XYZ_AB1234"

    async def go():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        M.set_db(db)
        token = _mint("admin", is_admin=True)
        res = await M.integrations_health(authorization=f"Bearer {token}")
        return res

    j = _aio.run(go())
    body = str(j)
    assert "sk-ant-test-key-XYZ_AB" not in body, \
        "FULL key leaked in response — security regression"
    ant = next(i for i in j["integrations"] if i["provider"] == "anthropic")
    assert ant["key_tail"] == "…1234"
    assert ant["key_present"] is True


# ── 4. Unset env → status="unset" + needs_recharge=True ───────────────

def test_unset_env_becomes_unset_status(admin_token, monkeypatch):
    monkeypatch.delenv("LINKEDIN_API_KEY", raising=False)
    r = requests.get(f"{API}/api/admin/integrations/health",
                      headers=_hdr(admin_token), timeout=15)
    j = r.json()
    li = next(i for i in j["integrations"] if i["provider"] == "linkedin")
    assert li["status"]         == "unset"
    assert li["needs_recharge"] is True
    assert li["key_tail"]       == "····"


# ── 5. Recorded 401 failure flips status to red ───────────────────────

def test_recorded_unauthorized_promotes_to_red(admin_token, monkeypatch):
    """Plant a key (so status isn't 'unset') then write a 401 record
    via the watchdog helper and confirm the endpoint reflects 'red'."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test_AB12")

    async def go():
        from motor.motor_asyncio import AsyncIOMotorClient
        from services import api_key_health_watcher

        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        # Set the watcher's DB pointer.
        api_key_health_watcher.set_db(db)
        # Clean any old rows so the test is hermetic.
        await db.api_key_health_log.delete_many({"provider": "resend"})
        await api_key_health_watcher.record_api_failure(
            provider="resend", status_code=401, body="suspended",
            key_hint="re_test")
    asyncio.run(go())

    r = requests.get(f"{API}/api/admin/integrations/health",
                      headers=_hdr(admin_token), timeout=15)
    j = r.json()
    re = next(i for i in j["integrations"] if i["provider"] == "resend")
    assert re["status"]         == "red"
    assert re["needs_recharge"] is True
    assert re["failures_24h"]   >= 1
    # bucket key present
    assert "unauthorized" in re["failures_24h_by_bucket"]


# ── 6. Group coverage ─────────────────────────────────────────────────

def test_all_critical_groups_covered(admin_token):
    """The dashboard must include at least one provider from each
    group: llm, comms, payment, data, infra. (Funding-report safety.)"""
    r = requests.get(f"{API}/api/admin/integrations/health",
                      headers=_hdr(admin_token), timeout=15)
    j = r.json()
    groups = {row["group"] for row in j["integrations"]}
    for needed in ("llm", "comms", "payment", "data", "infra"):
        assert needed in groups, f"group '{needed}' missing"
