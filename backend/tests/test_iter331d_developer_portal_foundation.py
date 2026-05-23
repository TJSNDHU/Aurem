"""
iter 331d — Developer Portal Foundation
========================================

Backend test suite for the dev-portal foundation. Covers:

  • Signup state machine (anti-bot throttle + disposable-email reject)
  • OTP issue + verify + expiry + max attempts
  • JWT issue + decode
  • BYOK save (Fernet envelope via credential_crypto)
  • Token deduction + token wall (HTTP-402-equivalent)
  • Abuse pattern detection (port scan / crypto miner / SQLi / mass mail)
  • Per-developer rate limits (per-minute + per-day)
  • Pixel domain validation (localhost / private IP / .local blocked)
  • Referral bonus award
  • Sandbox cleanup (45-day idle)
  • Day-0 welcome email (subject + body construction; Resend mocked)

20 cases. All tests share a session-scoped Mongo client and a fresh
synthetic user_id per case so they don't collide with each other or
with the real founder rows.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest_asyncio.fixture
async def fresh_user(db):
    """Insert a verified synthetic developer account and yield the doc."""
    from services.developer_portal_core import set_db
    set_db(db)
    user_id = f"pytest-{uuid.uuid4().hex[:16]}"
    email   = f"pytest+{uuid.uuid4().hex[:8]}@example.com"
    doc = {
        "user_id":           user_id,
        "email":             email,
        "email_verified":    True,
        "name":              "Pytest User",
        "password_hash":     "sha256$x$y",
        "github_username":   "",
        "byok_keys":         None,
        "tokens_remaining":  100,
        "tokens_total_used": 0,
        "pixel_key":         f"DEV-{user_id[:8]}-x",
        "pixel_verified":    False,
        "pixel_domain":      None,
        "referral_code":     f"rt{uuid.uuid4().hex[:6]}",
        "referred_by":       None,
        "subscription_status": "free",
        "abuse_flagged":     False,
        "build_intent":      "",
        "signup_ip":         "127.0.0.1",
        "created_at":        datetime.now(timezone.utc).isoformat(),
        "last_active_at":    datetime.now(timezone.utc).isoformat(),
    }
    await db.developer_accounts.insert_one(doc)
    yield doc
    # Cleanup
    await db.developer_accounts.delete_one({"user_id": user_id})
    await db.developer_tokens.delete_many({"user_id": user_id})
    await db.developer_abuse_flags.delete_many({"user_id": user_id})


# ═══════════════════════════════════════════════════════════════════
# 1. Signup state machine
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_signup_disposable_email_rejected(db):
    from services.developer_portal_core import signup_anti_bot_check, set_db
    set_db(db)
    r = await signup_anti_bot_check(ip="1.2.3.4",
                                    email="alice@mailinator.com")
    assert r["ok"] is False
    assert r["reason"] == "disposable_email"


@pytest.mark.asyncio
async def test_signup_per_ip_throttle_after_5(db):
    """6th signup from same IP within an hour is refused."""
    from services.developer_portal_core import (
        signup_anti_bot_check, set_db, SIGNUP_RATE_PER_IP_HR,
    )
    set_db(db)
    ip = f"203.0.113.{uuid.uuid4().int % 200 + 50}"   # unique per run
    # Seed SIGNUP_RATE_PER_IP_HR rows
    now = datetime.now(timezone.utc).isoformat()
    seeded = [{
        "user_id": f"throttle-{i}-{uuid.uuid4().hex[:6]}",
        "email":   f"x{i}-{uuid.uuid4().hex[:4]}@example.com",
        "signup_ip": ip,
        "created_at": now,
    } for i in range(SIGNUP_RATE_PER_IP_HR)]
    await db.developer_accounts.insert_many(seeded)
    try:
        r = await signup_anti_bot_check(ip=ip, email="new@example.com")
        assert r["ok"] is False
        assert r["reason"] == "signup_rate_per_ip"
    finally:
        await db.developer_accounts.delete_many(
            {"user_id": {"$in": [s["user_id"] for s in seeded]}}
        )


@pytest.mark.asyncio
async def test_signup_creates_account_and_issues_otp(db):
    from services.developer_portal_core import create_signup, set_db
    set_db(db)
    email = f"pytest+{uuid.uuid4().hex[:8]}@example.com"
    try:
        r = await create_signup(
            email=email, name="Test User",
            password_hash="sha256$x$y", ip="198.51.100.5",
        )
        assert r["ok"] is True
        assert r["tokens_granted"] == 1000
        assert r["referral_code"].startswith("r")
        assert r.get("_otp_for_testing")   # exposed for dev mode
        # OTP row exists
        otp_row = await db.developer_otp_codes.find_one({"email": email})
        assert otp_row is not None
        assert otp_row["attempts"] == 0
    finally:
        await db.developer_accounts.delete_many({"email": email})
        await db.developer_otp_codes.delete_many({"email": email})


# ═══════════════════════════════════════════════════════════════════
# 2. OTP verify
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_otp_verify_success_mints_jwt(db):
    from services.developer_portal_core import (
        create_signup, verify_otp, decode_dev_jwt, set_db,
    )
    set_db(db)
    email = f"pytest+{uuid.uuid4().hex[:8]}@example.com"
    try:
        s = await create_signup(
            email=email, name="OTP Tester",
            password_hash="sha256$x$y", ip="198.51.100.10",
        )
        otp = s["_otp_for_testing"]
        v = await verify_otp(email=email, otp=otp)
        assert v["ok"] is True
        assert v["jwt"]
        payload = decode_dev_jwt(v["jwt"])
        assert payload["sub"] == s["user_id"]
        assert payload["email"] == email
        assert payload["kind"] == "developer"
        # email_verified flipped
        acc = await db.developer_accounts.find_one({"email": email})
        assert acc["email_verified"] is True
    finally:
        await db.developer_accounts.delete_many({"email": email})
        await db.developer_otp_codes.delete_many({"email": email})


@pytest.mark.asyncio
async def test_otp_verify_wrong_code_rejected(db):
    from services.developer_portal_core import (
        create_signup, verify_otp, set_db,
    )
    set_db(db)
    email = f"pytest+{uuid.uuid4().hex[:8]}@example.com"
    try:
        await create_signup(
            email=email, name="Wrong OTP",
            password_hash="sha256$x$y", ip="198.51.100.11",
        )
        v = await verify_otp(email=email, otp="000000")
        assert v["ok"] is False
        assert v["error"] == "wrong_otp"
    finally:
        await db.developer_accounts.delete_many({"email": email})
        await db.developer_otp_codes.delete_many({"email": email})


@pytest.mark.asyncio
async def test_otp_expired_rejected(db):
    """Force the expires_at into the past and assert otp_expired."""
    from services.developer_portal_core import (
        create_signup, verify_otp, set_db,
    )
    set_db(db)
    email = f"pytest+{uuid.uuid4().hex[:8]}@example.com"
    try:
        s = await create_signup(
            email=email, name="Expired OTP",
            password_hash="sha256$x$y", ip="198.51.100.12",
        )
        # Backdate expires_at
        await db.developer_otp_codes.update_one(
            {"email": email},
            {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=5)}},
        )
        v = await verify_otp(email=email, otp=s["_otp_for_testing"])
        assert v["ok"] is False
        assert v["error"] == "otp_expired"
    finally:
        await db.developer_accounts.delete_many({"email": email})
        await db.developer_otp_codes.delete_many({"email": email})


@pytest.mark.asyncio
async def test_otp_max_attempts_lockout(db):
    """After OTP_MAX_ATTEMPTS wrong tries, even the right one is refused."""
    from services.developer_portal_core import (
        create_signup, verify_otp, set_db, OTP_MAX_ATTEMPTS,
    )
    set_db(db)
    email = f"pytest+{uuid.uuid4().hex[:8]}@example.com"
    try:
        s = await create_signup(
            email=email, name="Lockout Test",
            password_hash="sha256$x$y", ip="198.51.100.13",
        )
        # Burn the allowed attempts
        for _ in range(OTP_MAX_ATTEMPTS):
            await verify_otp(email=email, otp="000000")
        # Even right OTP now fails
        v = await verify_otp(email=email, otp=s["_otp_for_testing"])
        assert v["ok"] is False
        assert v["error"] == "too_many_attempts"
    finally:
        await db.developer_accounts.delete_many({"email": email})
        await db.developer_otp_codes.delete_many({"email": email})


# ═══════════════════════════════════════════════════════════════════
# 3. JWT round trip
# ═══════════════════════════════════════════════════════════════════

def test_jwt_round_trip():
    from services.developer_portal_core import issue_jwt, decode_dev_jwt
    tok = issue_jwt("user-abc", "x@y.z")
    payload = decode_dev_jwt(tok)
    assert payload["sub"] == "user-abc"
    assert payload["email"] == "x@y.z"
    assert payload["kind"] == "developer"
    assert payload["exp"] > int(time.time())


def test_jwt_garbage_returns_empty():
    from services.developer_portal_core import decode_dev_jwt
    assert decode_dev_jwt("") == {}
    assert decode_dev_jwt("not-a-real.jwt") == {}


# ═══════════════════════════════════════════════════════════════════
# 4. BYOK
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_byok_save_encrypts_and_persists(db, fresh_user):
    from services.developer_portal_core import (
        save_byok_keys, set_db, decrypt_byok,
    )
    set_db(db)
    plain = {"anthropic": "sk-ant-test-001",
             "deepseek":  "sk-dsk-test-002",
             "gemini":    ""}
    r = await save_byok_keys(fresh_user["user_id"], plain)
    assert r["ok"] is True
    assert "anthropic" in r["providers"]
    assert "gemini" not in r["providers"]    # empty value dropped
    # Verify roundtrip
    row = await db.developer_accounts.find_one(
        {"user_id": fresh_user["user_id"]}
    )
    decrypted = decrypt_byok(row["byok_keys"])
    assert decrypted["anthropic"] == "sk-ant-test-001"


@pytest.mark.asyncio
async def test_byok_requires_one_supported_provider(db, fresh_user):
    from services.developer_portal_core import save_byok_keys, set_db
    set_db(db)
    r = await save_byok_keys(fresh_user["user_id"],
                              {"openai": "sk-open-x"})  # wrong provider
    assert r["ok"] is False
    assert "must_include" in r["error"]


# ═══════════════════════════════════════════════════════════════════
# 5. Token deduction + wall
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_token_deduction_decrements_balance(db, fresh_user):
    from services.developer_portal_core import deduct_tokens, set_db
    set_db(db)
    before = fresh_user["tokens_remaining"]
    r = await deduct_tokens(fresh_user["user_id"], tool_name="view_file")
    assert r["ok"] is True
    assert r["deducted"] == 2                  # file_read cost
    assert r["tokens_remaining"] == before - 2


@pytest.mark.asyncio
async def test_token_wall_at_zero_balance(db, fresh_user):
    from services.developer_portal_core import (
        deduct_tokens, enforce_token_wall, set_db,
    )
    set_db(db)
    # Zero the balance directly
    await db.developer_accounts.update_one(
        {"user_id": fresh_user["user_id"]},
        {"$set": {"tokens_remaining": 0}},
    )
    wall = await enforce_token_wall(fresh_user["user_id"])
    assert wall["ok"] is False
    assert wall["error"] == "token_wall"
    assert wall["tokens_remaining"] == 0
    # Deduct against zero balance should also refuse
    d = await deduct_tokens(fresh_user["user_id"], tool_name="deploy_to_platform")
    assert d["ok"] is False
    assert d["error"] == "insufficient_tokens"


@pytest.mark.asyncio
async def test_token_cost_table_lookup():
    from services.developer_portal_core import cost_for_tool, DEFAULT_TOOL_COST
    assert cost_for_tool("view_file") == 2
    assert cost_for_tool("safe_edit") == 2
    assert cost_for_tool("run_pytest") == 3
    assert cost_for_tool("deploy_to_platform") == 5
    assert cost_for_tool("fork_context") == 10
    assert cost_for_tool("unknown_tool") == DEFAULT_TOOL_COST


# ═══════════════════════════════════════════════════════════════════
# 6. Abuse patterns
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("cmd,label", [
    ("nmap -sV 10.0.0.0/24",        "port_scanning"),
    ("./xmrig --donate-level 1",    "crypto_mining"),
    ("' OR 1=1 --",                  "sql_injection"),
    ("python -c 'import smtplib; mass email send loop'", "mass_email_outside_aurem"),
    ("nc -l -p 4444 -e /bin/bash",   "network_recon"),
])
@pytest.mark.asyncio
async def test_abuse_patterns_block_and_flag(db, fresh_user, cmd, label):
    from services.developer_portal_core import check_abuse_pattern, set_db
    set_db(db)
    r = await check_abuse_pattern(fresh_user["user_id"], cmd)
    assert r["ok"] is False
    assert r["blocked"] is True
    assert r["matched"] == label
    # abuse_flagged stamped on account
    acc = await db.developer_accounts.find_one(
        {"user_id": fresh_user["user_id"]}
    )
    assert acc["abuse_flagged"] is True


# ═══════════════════════════════════════════════════════════════════
# 7. Rate limits
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_rate_limit_per_min_trips(db, fresh_user):
    from services.developer_portal_core import (
        check_rate_limit, set_db, RATE_LIMIT_PER_MIN,
    )
    set_db(db)
    # Seed RATE_LIMIT_PER_MIN tool-call rows within the last 60 s
    now = datetime.now(timezone.utc).isoformat()
    rows = [{
        "user_id":     fresh_user["user_id"],
        "action_type": "file_read",
        "tool_name":   "view_file",
        "tokens_used": 2,
        "session_id":  "rl-test",
        "timestamp":   now,
    } for _ in range(RATE_LIMIT_PER_MIN)]
    await db.developer_tokens.insert_many(rows)
    r = await check_rate_limit(fresh_user["user_id"])
    assert r["ok"] is False
    assert r["error"] == "rate_limit_per_min"
    assert r["limit"] == RATE_LIMIT_PER_MIN


@pytest.mark.asyncio
async def test_rate_limit_paid_users_unlimited(db, fresh_user):
    from services.developer_portal_core import check_rate_limit, set_db
    set_db(db)
    await db.developer_accounts.update_one(
        {"user_id": fresh_user["user_id"]},
        {"$set": {"subscription_status": "paid"}},
    )
    # Seed plenty of token rows — should still pass
    now = datetime.now(timezone.utc).isoformat()
    await db.developer_tokens.insert_many([{
        "user_id":     fresh_user["user_id"],
        "tool_name":   "view_file",
        "tokens_used": 2,
        "timestamp":   now,
    } for _ in range(50)])
    r = await check_rate_limit(fresh_user["user_id"])
    assert r["ok"] is True
    assert r.get("tier") == "paid"


# ═══════════════════════════════════════════════════════════════════
# 8. Pixel domain validation
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("raw,ok", [
    ("aurem.live",          True),
    ("https://example.com", True),
    ("sub.example.com",     True),
    ("localhost",           False),
    ("127.0.0.1",           False),
    ("192.168.1.1",         False),
    ("10.0.0.5",            False),
    ("myapp.local",         False),
    ("",                    False),
    ("nopuncutation",       False),
])
def test_pixel_domain_validation(raw, ok):
    from services.developer_portal_core import validate_pixel_domain
    r = validate_pixel_domain(raw)
    assert r["ok"] is ok


# ═══════════════════════════════════════════════════════════════════
# 9. Referral bonus
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_referral_bonus_credits_referrer(db, fresh_user):
    from services.developer_portal_core import (
        award_referral_bonus, set_db, REFERRAL_BONUS_TOKENS,
    )
    set_db(db)
    before = fresh_user["tokens_remaining"]
    r = await award_referral_bonus(
        referrer_user_id=fresh_user["user_id"],
        new_user_id="downstream-x",
    )
    assert r["ok"] is True
    assert r["modified"] == 1
    acc = await db.developer_accounts.find_one(
        {"user_id": fresh_user["user_id"]}
    )
    assert acc["tokens_remaining"] == before + REFERRAL_BONUS_TOKENS


# ═══════════════════════════════════════════════════════════════════
# 10. Sandbox cleanup
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sandbox_cleanup_removes_stale_dirs(tmp_path, monkeypatch):
    """Create 2 fake sandboxes — one stale, one fresh — and confirm
    only the stale one is removed."""
    monkeypatch.setattr(
        "services.developer_portal_core.SANDBOX_ROOT", tmp_path,
    )
    from services.developer_portal_core import cleanup_inactive_sandboxes
    stale = tmp_path / "ora-sandbox-stale"
    fresh = tmp_path / "ora-sandbox-fresh"
    stale.mkdir()
    fresh.mkdir()
    (stale / "marker.txt").write_text("x")
    (fresh / "marker.txt").write_text("y")
    # Backdate the stale folder by 60 days
    old_ts = time.time() - 60 * 86400
    os.utime(stale, (old_ts, old_ts))
    r = await cleanup_inactive_sandboxes(max_age_days=45)
    assert r["ok"] is True
    assert r["removed"] == 1
    assert not stale.exists()
    assert fresh.exists()


# ═══════════════════════════════════════════════════════════════════
# 11. Day-0 welcome email
# ═══════════════════════════════════════════════════════════════════

def test_welcome_email_subject_and_body_construction():
    from services.developer_portal_core import _welcome_email_html
    subject, html = _welcome_email_html(
        name="Alice Smith",
        login_url="https://aurem.live/developers/login",
        connect_url="https://aurem.live/developers/connect",
    )
    assert subject == "Welcome to ORA CTO — Your 1000 tokens are ready"
    # First name only used
    assert "Welcome to ORA CTO, Alice." in html
    assert "1,000 free" in html
    assert "Connect your GitHub" in html
    assert "https://aurem.live/developers/login" in html
    assert "https://aurem.live/developers/connect" in html
    # 3-step content present
    assert "Log in to your dashboard" in html
    assert "Tell ORA what you want to build" in html


@pytest.mark.asyncio
async def test_welcome_email_sends_via_resend_wrapper(db, monkeypatch):
    """Patch the Resend wrapper and confirm _send_welcome_email
    delivers the correct payload."""
    captured = {}

    async def _fake_send(**kw):
        captured.update(kw)
        return True, "msg_pytest_id"

    # Inject the fake into the resend wrapper module so the helper
    # imports it dynamically and we still intercept
    import services.email_service_resend as _esr
    monkeypatch.setattr(_esr, "send_email", _fake_send)

    from services.developer_portal_core import _send_welcome_email
    ok = await _send_welcome_email(email="founder@aurem.live", name="Founder")
    assert ok is True
    assert captured["to"] == "founder@aurem.live"
    assert captured["subject"] == "Welcome to ORA CTO — Your 1000 tokens are ready"
    assert "1,000 free" in captured["html"]
    assert "tokens" in (captured.get("text") or "").lower()


@pytest.mark.asyncio
async def test_verify_otp_triggers_welcome_email(db, monkeypatch):
    """End-to-end: signup → verify_otp → welcome email helper invoked."""
    sent = []

    async def _fake_welcome(email, name):
        sent.append({"to": email, "name": name})
        return True

    import services.developer_portal_core as _dpc
    monkeypatch.setattr(_dpc, "_send_welcome_email", _fake_welcome)
    _dpc.set_db(db)

    email = f"pytest+{uuid.uuid4().hex[:8]}@example.com"
    try:
        s = await _dpc.create_signup(
            email=email, name="Welcome Tester",
            password_hash="sha256$x$y", ip="198.51.100.99",
        )
        v = await _dpc.verify_otp(email=email, otp=s["_otp_for_testing"])
        assert v["ok"] is True
        # Allow the fire-and-forget task to run
        await asyncio.sleep(0.05)
        assert any(s_["to"] == email for s_ in sent)
    finally:
        await db.developer_accounts.delete_many({"email": email})
        await db.developer_otp_codes.delete_many({"email": email})


# ═══════════════════════════════════════════════════════════════════
# 12. Scheduler wire-up smoke (registry source)
# ═══════════════════════════════════════════════════════════════════

def test_sandbox_cleanup_cron_wired_in_registry():
    """Source-level proof that the cron is registered."""
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_dev_sandbox_cleanup" in src
    assert "cleanup_inactive_sandboxes" in src
    assert "hour=4, minute=30" in src
    assert "Developer Sandbox Cleanup" in src
