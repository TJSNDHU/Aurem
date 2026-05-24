"""
iter 332b D-7 — Admin developer signups page + Telegram nudge.

Founder asked for one thing: a way to SEE the emails of every developer
who signed up to the dev portal. Backend `GET /api/admin/developers`
already existed (iter 331f) — this slice ships the React page that
displays it + a fire-and-forget Telegram nudge on every new signup
so the founder is pinged in real time.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid

import jwt
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.developer_portal_core import set_db as _set_dev_db
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    _set_dev_db(database)
    yield database
    await database.developer_accounts.delete_many(
        {"email": {"$regex": "^pytest_d7_"}}
    )
    await database.developer_otp_codes.delete_many(
        {"email": {"$regex": "^pytest_d7_"}}
    )
    client.close()


def _mint_admin_token(email: str = "admin@aurem.local") -> str:
    from config import JWT_SECRET, JWT_ALGORITHM
    payload = {
        "user_id": f"admin_{uuid.uuid4().hex[:8]}",
        "is_admin": True, "is_super_admin": True,
        "email": email, "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ───────────────────────── Backend list endpoint ─────────────────────────

def _api_base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL")
    if not base:
        import pathlib
        envf = pathlib.Path("/app/frontend/.env")
        if envf.exists():
            for line in envf.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    base = line.split("=", 1)[1].strip()
                    break
    return (base or "http://localhost:8001").rstrip("/")


@pytest.mark.asyncio
async def test_admin_developers_endpoint_returns_rows(db):
    """GET /api/admin/developers must respond with rows + total + flagged,
    and must NOT include password_hash / byok_keys / signup_ip."""
    import httpx
    # Seed two signups
    for i in range(2):
        await db.developer_accounts.insert_one({
            "user_id":         f"pytest_d7_user_{i}_{uuid.uuid4().hex[:6]}",
            "email":           f"pytest_d7_{i}_{uuid.uuid4().hex[:6]}@x.test",
            "name":            f"Pytest D7 {i}",
            "plan":            "free",
            "tokens_remaining": 1000,
            "email_verified":  True,
            "password_hash":   "should-never-appear",
            "byok_keys":       {"anthropic": "should-never-appear"},
            "signup_ip":       "1.2.3.4",
            "created_at":      "2026-01-01T00:00:00Z",
            "abuse_flagged":   False,
        })
    tok = _mint_admin_token()
    # Use sync httpx via to_thread — async client hits a middleware quirk
    # in this codebase where unauth requests can return 204 instead of 401.
    def _call():
        with httpx.Client(timeout=15.0) as c:
            return c.get(f"{_api_base()}/api/admin/developers?limit=200",
                          headers={"Authorization": f"Bearer {tok}"})
    r = await asyncio.to_thread(_call)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["total"] >= 2
    pytest_rows = [row for row in j["rows"]
                   if row.get("email", "").startswith("pytest_d7_")]
    assert len(pytest_rows) >= 2
    # Secrets MUST be stripped by the backend projection
    for row in pytest_rows:
        assert "password_hash" not in row
        assert "byok_keys" not in row
        assert "signup_ip" not in row
        assert row.get("email")
        assert "plan" in row


def test_admin_developers_endpoint_rejects_anon():
    """No bearer → 401. Sync httpx; async client in this codebase
    hits a middleware quirk that returns 204."""
    import httpx
    with httpx.Client(timeout=15.0) as c:
        r = c.get(f"{_api_base()}/api/admin/developers")
    assert r.status_code in (401, 403), (
        f"Endpoint is unprotected — HTTP {r.status_code}"
    )


# ───────────────────────── Telegram nudge on signup ──────────────────────

@pytest.mark.asyncio
async def test_verify_otp_fires_telegram_nudge(db, monkeypatch):
    """Successful OTP verify must schedule a 'new_dev_signup' Telegram alert."""
    captured = []

    async def _fake_alert(message="", alert_type="generic", fingerprint=None, **_):
        captured.append({"message": message, "alert_type": alert_type,
                         "fingerprint": fingerprint})
        return {"ok": True}

    # Patch the import path used inside verify_otp
    import services.telegram_bot_service as tbs
    monkeypatch.setattr(tbs, "send_telegram_alert", _fake_alert)
    # Email service patched out so we don't hit real Resend
    import services.developer_portal_core as core
    async def _noop_email(**kw): return {"ok": True}
    monkeypatch.setattr(core, "_send_welcome_email", _noop_email)

    # Seed a pre-verified-ready signup
    import hashlib
    email = f"pytest_d7_{uuid.uuid4().hex[:8]}@x.test"
    user_id = f"pytest_d7_u_{uuid.uuid4().hex[:6]}"
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "D7 Test User",
        "plan": "free", "tokens_remaining": 1000,
        "email_verified": False, "abuse_flagged": False,
        "created_at": now.isoformat(),
    })
    otp_plain = "654321"
    await db.developer_otp_codes.insert_one({
        "email": email,
        "otp_hash": hashlib.sha256(otp_plain.encode()).hexdigest(),
        "attempts": 0,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
    })

    r = await core.verify_otp(email, otp_plain)
    assert r["ok"] is True, f"verify_otp failed: {r}"
    # Give the fire-and-forget task a chance to run
    for _ in range(20):
        if captured:
            break
        await asyncio.sleep(0.05)
    assert captured, "Telegram nudge never fired."
    payload = captured[0]
    assert payload["alert_type"] == "new_dev_signup"
    assert email in payload["message"]
    assert payload["fingerprint"] == email
    assert "/admin/developer-signups" in payload["message"]


# ───────────────────────── Frontend wiring guards ────────────────────────

def test_admin_developer_signups_page_exists_and_is_routed():
    """The page module must exist AND be mounted in App.js inside the
    AdminGuard / AdminShell block."""
    page = open(
        "/app/frontend/src/platform/AdminDeveloperSignups.jsx"
    ).read()
    assert "admin-dev-signups-page" in page
    assert "admin-dev-search" in page
    assert "admin-dev-copy-emails" in page
    assert "/api/admin/developers" in page

    app_src = open("/app/frontend/src/App.js").read()
    assert "AdminDeveloperSignups" in app_src
    assert "/admin/developer-signups" in app_src


def test_page_does_not_leak_sensitive_fields():
    """Page must NOT render password_hash / byok_keys / signup_ip
    even if the backend ever regressed and started returning them."""
    page = open(
        "/app/frontend/src/platform/AdminDeveloperSignups.jsx"
    ).read()
    for bad in ("password_hash", "byok_keys", "signup_ip"):
        assert bad not in page, f"Page references forbidden field: {bad}"
