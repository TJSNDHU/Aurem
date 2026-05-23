"""
iter 331e — Developer Portal Hardening
=======================================

Backend test suite for Batch A:

  Part 1 — Security guards
    • SSRF: private/loopback/link-local/internal hostnames blocked
    • SSRF: DNS-rebinding attempt (hostname → 127.0.0.1) blocked
    • File size limits: per-file 10 MB cap returns HTTP 413
    • File size limits: per-session 50 MB cumulative cap returns 413
    • Concurrent sessions: 3rd attempt refused with active list
    • Concurrent sessions: stale sessions auto-pruned
    • Output masking: JWT, bearer token, API keys, env values, paths
    • Output masking: nested dict + list traversal
    • Internal-path block: /app/backend/services/... refused

  Part 4 — Email sequence
    • classify_account: Day 3 / 7 / 25 buckets correct
    • classify_account: already-sent buckets skipped
    • Email rendering: subject + body + first-name extraction
    • run_sequence_tick: end-to-end with mocked Resend wrapper
    • run_sequence_tick: idempotent on re-run

  Part 6 — Stale test sanity
    • test_iter327n + test_iter329 stale assertions repaired
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest_asyncio.fixture
async def fresh_dev(db):
    from services import dev_security_guards as _SG
    from services import developer_portal_core as _D
    _SG.set_db(db)
    _D.set_db(db)
    user_id = f"sec-test-{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id":          user_id,
        "email":            f"sec+{uuid.uuid4().hex[:8]}@example.com",
        "email_verified":   True,
        "name":             "Security Tester",
        "password_hash":    "sha256$x$y",
        "tokens_remaining": 100,
        "tokens_total_used": 0,
        "github_connected": False,
        "active_sessions":  [],
        "created_at":       datetime.now(timezone.utc).isoformat(),
        "last_active_at":   datetime.now(timezone.utc).isoformat(),
    }
    await db.developer_accounts.insert_one(doc)
    yield doc
    await db.developer_accounts.delete_one({"user_id": user_id})


# ═══════════════════════════════════════════════════════════════════
# Part 1 — SSRF
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("url,expected_blocked,expected_reason_substr", [
    ("http://localhost:8001/api/admin",       True,  "blocked_exact_host"),
    ("http://127.0.0.1/api/health",           True,  "loopback"),
    ("http://10.0.0.5/internal",              True,  "private"),
    ("http://172.16.5.1/admin",               True,  "private"),
    ("http://192.168.1.1/router",             True,  "private"),
    ("http://169.254.169.254/latest/meta",    True,  "blocked_exact_host"),
    ("http://kubernetes.default.svc/",        True,  "blocked_exact_host"),
    ("http://metadata.google.internal/",      True,  "blocked_exact_host"),
    ("http://internal-api.local/",            True,  "blocked_suffix"),
    ("http://myhost.intranet/",               True,  "blocked_suffix"),
    ("https://example.com/api",               False, ""),
    ("https://api.github.com/repos",          False, ""),
])
def test_ssrf_url_filter(url, expected_blocked, expected_reason_substr):
    from services.dev_security_guards import assert_url_safe
    r = assert_url_safe(url, resolve_dns=False)
    assert (not r["ok"]) is expected_blocked, \
        f"{url}: expected blocked={expected_blocked}, got {r}"
    if expected_blocked:
        assert expected_reason_substr in (r.get("reason") or "")


def test_ssrf_ipv6_loopback_blocked():
    from services.dev_security_guards import assert_url_safe
    r = assert_url_safe("http://[::1]/foo", resolve_dns=False)
    assert r["ok"] is False
    assert "loopback" in r["reason"]


def test_ssrf_dns_resolution_re_checks_resolved_ip(monkeypatch):
    """DNS-rebinding defense: hostname looks public but resolves to
    127.0.0.1 — must be refused."""
    import socket
    import services.dev_security_guards as SG

    def _fake_getaddrinfo(host, port, *a, **kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "",
                 ("127.0.0.1", port or 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    r = SG.assert_url_safe("http://127-0-0-1.nip.io/admin")
    assert r["ok"] is False
    assert r.get("resolved_to") == "127.0.0.1"


def test_ssrf_dns_failure_refuses():
    """If DNS itself can't resolve, refuse — fail closed."""
    from services.dev_security_guards import assert_url_safe
    r = assert_url_safe("http://this-host-definitely-does-not-exist-xyz-12345.invalid/")
    assert r["ok"] is False
    assert "dns_resolve_failed" in r["reason"]


# ═══════════════════════════════════════════════════════════════════
# Part 1 — File size limits
# ═══════════════════════════════════════════════════════════════════

def test_file_size_per_file_cap_returns_413():
    from services.dev_security_guards import (
        enforce_file_size_limits, reset_session_bytes, MAX_FILE_BYTES,
    )
    sid = f"size-test-{uuid.uuid4().hex[:8]}"
    reset_session_bytes(sid)
    r = enforce_file_size_limits(sid, file_bytes=MAX_FILE_BYTES + 1,
                                  file_path="huge.bin")
    assert r["ok"] is False
    assert r["http_status"] == 413
    assert r["reason"] == "file_too_large"
    assert "MB" in r["message"]


def test_file_size_session_cap_returns_413():
    from services.dev_security_guards import (
        enforce_file_size_limits, reset_session_bytes,
        MAX_FILE_BYTES, MAX_SESSION_BYTES,
    )
    sid = f"size-sess-{uuid.uuid4().hex[:8]}"
    reset_session_bytes(sid)
    # Burn the session budget with N * MAX_FILE_BYTES reads
    each = MAX_FILE_BYTES
    n = MAX_SESSION_BYTES // each
    for _ in range(n):
        r = enforce_file_size_limits(sid, file_bytes=each)
        assert r["ok"] is True
    # Next read pushes past the session cap
    r = enforce_file_size_limits(sid, file_bytes=each)
    assert r["ok"] is False
    assert r["http_status"] == 413
    assert r["reason"] == "session_quota_exceeded"
    reset_session_bytes(sid)


def test_file_size_zero_byte_file_allowed():
    from services.dev_security_guards import (
        enforce_file_size_limits, reset_session_bytes,
    )
    sid = f"size-zero-{uuid.uuid4().hex[:8]}"
    reset_session_bytes(sid)
    r = enforce_file_size_limits(sid, file_bytes=0)
    assert r["ok"] is True


# ═══════════════════════════════════════════════════════════════════
# Part 1 — Concurrent session limit
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_concurrent_session_third_attempt_refused(db, fresh_dev):
    from services.dev_security_guards import (
        acquire_session, release_session, MAX_ACTIVE_SESSIONS,
    )
    uid = fresh_dev["user_id"]
    granted_ids = []
    for i in range(MAX_ACTIVE_SESSIONS):
        sid = f"sess-{i}-{uuid.uuid4().hex[:6]}"
        r = await acquire_session(uid, sid)
        assert r["ok"] is True
        assert r["active_count"] == i + 1
        granted_ids.append(sid)
    # 3rd attempt must be refused
    extra = f"sess-extra-{uuid.uuid4().hex[:6]}"
    r = await acquire_session(uid, extra)
    assert r["ok"] is False
    assert r["reason"] == "too_many_sessions"
    assert r["active_count"] == MAX_ACTIVE_SESSIONS
    assert extra not in (r.get("active_session_ids") or [])
    assert "Close one" in r["message"]
    # After releasing one slot, new acquire succeeds
    await release_session(uid, granted_ids[0])
    r2 = await acquire_session(uid, extra)
    assert r2["ok"] is True


@pytest.mark.asyncio
async def test_concurrent_session_stale_auto_pruned(db, fresh_dev):
    """Sessions with heartbeat > SESSION_STALE_MINUTES old are dropped
    before counting against the limit."""
    from services.dev_security_guards import (
        acquire_session, SESSION_STALE_MINUTES, MAX_ACTIVE_SESSIONS,
    )
    uid = fresh_dev["user_id"]
    # Seed MAX_ACTIVE_SESSIONS sessions, all with stale heartbeats
    stale_iso = (
        datetime.now(timezone.utc) - timedelta(minutes=SESSION_STALE_MINUTES + 5)
    ).isoformat()
    stale_rows = [{
        "session_id": f"stale-{i}-{uuid.uuid4().hex[:6]}",
        "started_at": stale_iso,
        "heartbeat":  stale_iso,
    } for i in range(MAX_ACTIVE_SESSIONS)]
    await db.developer_accounts.update_one(
        {"user_id": uid},
        {"$set": {"active_sessions": stale_rows}},
    )
    # New acquire should succeed — stale ones pruned first
    r = await acquire_session(uid, "new-fresh")
    assert r["ok"] is True
    assert r["active_count"] == 1


@pytest.mark.asyncio
async def test_concurrent_session_renewal_idempotent(db, fresh_dev):
    """Acquiring the same session_id twice just refreshes heartbeat."""
    from services.dev_security_guards import acquire_session
    uid = fresh_dev["user_id"]
    sid = "renew-test"
    r1 = await acquire_session(uid, sid)
    assert r1["ok"] is True
    r2 = await acquire_session(uid, sid)
    assert r2["ok"] is True
    assert r2.get("renewed") is True
    assert r2["active_count"] == 1


# ═══════════════════════════════════════════════════════════════════
# Part 1 — Output masking
# ═══════════════════════════════════════════════════════════════════

def test_mask_jwt_in_string():
    from services.dev_security_guards import mask_sensitive_output
    # 3-segment base64url JWT shape
    fake_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.AbCdEfGhIj-_kLmNoP"
    text = f"got token {fake_jwt} for user"
    out = mask_sensitive_output(text)
    assert fake_jwt not in out
    assert "[REDACTED-JWT]" in out


def test_mask_bearer_header():
    from services.dev_security_guards import mask_sensitive_output
    out = mask_sensitive_output("Authorization: Bearer xyz123abc456def-_=")
    assert "xyz123abc456def" not in out
    assert "[REDACTED]" in out


def test_mask_stripe_and_google_keys():
    from services.dev_security_guards import mask_sensitive_output
    # Build the secret-like strings WITHOUT putting real-looking prefixes
    # in source so GitHub secret scanning doesn't choke.
    stripe_live = "sk_" + "live_" + "ABCDEFGHIJ1234567"
    google_key  = "AIza" + "ABCDEFGHIJKLMNOPQRSTUVWX"
    text = f"keys are {stripe_live} and {google_key}"
    out = mask_sensitive_output(text)
    assert stripe_live not in out
    assert google_key  not in out
    assert "[REDACTED-STRIPE-LIVE]" in out
    assert "[REDACTED-GOOGLE-KEY]" in out


def test_mask_mongo_connection_string():
    from services.dev_security_guards import mask_sensitive_output
    raw = "mongodb+srv://user:pass@cluster.mongodb.net/db?retryWrites=true"
    out = mask_sensitive_output(f"connection: {raw}")
    assert raw not in out
    assert "[REDACTED-MONGO-URL]" in out


def test_mask_env_var_values(monkeypatch):
    from services.dev_security_guards import mask_sensitive_output
    monkeypatch.setenv("PYTEST_FAKE_API_KEY", "supersecret-value-1234567")
    out = mask_sensitive_output("the key is supersecret-value-1234567 ok")
    assert "supersecret-value-1234567" not in out
    assert "[REDACTED-PYTEST_FAKE_API_KEY]" in out


def test_mask_walks_nested_dicts_and_lists():
    from services.dev_security_guards import mask_sensitive_output
    fake_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.zzz"
    payload = {
        "ok": True,
        "rows": [
            {"token": fake_jwt, "name": "alice"},
            {"path":  "/app/backend/services/founder_provision.py"},
        ],
    }
    out = mask_sensitive_output(payload)
    assert out["rows"][0]["token"] == "[REDACTED-JWT]"
    assert "[INTERNAL]/" in out["rows"][1]["path"]
    assert out["ok"] is True   # non-string values untouched


def test_internal_path_block_detects_services_routers():
    from services.dev_security_guards import is_internal_path
    assert is_internal_path("/app/backend/services/founder_provision.py") is True
    assert is_internal_path("/app/backend/routers/registry.py") is True
    assert is_internal_path("/app/backend/.env") is True
    assert is_internal_path("/tmp/ora-sandbox-abc/main.py") is False
    assert is_internal_path("/app/frontend/src/App.js") is False
    assert is_internal_path("") is False


# ═══════════════════════════════════════════════════════════════════
# Part 4 — Email sequence
# ═══════════════════════════════════════════════════════════════════

def _make_account(*, days_ago: float, tokens_used: int = 0,
                  tokens_remaining: int = 1000, github_connected: bool = False,
                  sent: list[str] | None = None,
                  email_verified: bool = True) -> dict:
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "user_id":             f"acc-{uuid.uuid4().hex[:8]}",
        "email":               "x@example.com",
        "name":                "Alice Tester",
        "email_verified":      email_verified,
        "tokens_total_used":   tokens_used,
        "tokens_remaining":    tokens_remaining,
        "github_connected":    github_connected,
        "created_at":          created.isoformat(),
        "email_sequence_sent": sent or [],
    }


def test_classify_day3_github_nudge_fires_when_not_connected():
    from services.developer_email_sequence import classify_account
    acc = _make_account(days_ago=3.5, github_connected=False)
    assert "day3_github_nudge" in classify_account(acc)


def test_classify_day3_skipped_when_github_connected():
    from services.developer_email_sequence import classify_account
    acc = _make_account(days_ago=3.5, github_connected=True)
    assert classify_account(acc) == []


def test_classify_day7_unused_when_no_token_consumption():
    from services.developer_email_sequence import classify_account
    acc = _make_account(days_ago=7.5, tokens_used=0,
                         tokens_remaining=1000, github_connected=True)
    assert "day7_unused" in classify_account(acc)


def test_classify_day7_halfway_when_under_500_remaining():
    from services.developer_email_sequence import classify_account
    acc = _make_account(days_ago=7.5, tokens_used=600,
                         tokens_remaining=400, github_connected=True)
    assert "day7_halfway" in classify_account(acc)
    # Unused bucket must NOT also fire
    assert "day7_unused" not in classify_account(acc)


def test_classify_day25_expiry_window():
    from services.developer_email_sequence import classify_account
    acc = _make_account(days_ago=25.5, github_connected=True)
    assert "day25_expiry" in classify_account(acc)


def test_classify_skips_already_sent_buckets():
    from services.developer_email_sequence import classify_account
    acc = _make_account(days_ago=3.5, github_connected=False,
                         sent=["day3_github_nudge"])
    assert "day3_github_nudge" not in classify_account(acc)


def test_classify_unverified_returns_empty():
    from services.developer_email_sequence import classify_account
    acc = _make_account(days_ago=7.5, email_verified=False)
    assert classify_account(acc) == []


def test_day3_render_has_first_name_and_connect_link():
    from services.developer_email_sequence import render_day3_github_nudge
    subject, html, text = render_day3_github_nudge("Alice Smith")
    assert subject == "Connect GitHub to get started"
    assert "Hi Alice" in html       # first name only
    assert "/developers/connect" in html
    assert "5 minutes" in text


def test_day7_halfway_render_has_tokens_count():
    from services.developer_email_sequence import render_day7_halfway
    subject, html, text = render_day7_halfway("Bob", 250)
    assert subject == "You're halfway through your tokens"
    assert "250 tokens" in html
    assert "BYOK" in html


def test_day25_expiry_render_has_expiry_phrase():
    from services.developer_email_sequence import render_day25_expiry
    subject, html, text = render_day25_expiry("Eve Founder", 80)
    assert subject == "Your free tokens expire in 5 days"
    assert "expire in 5 days" in text


@pytest.mark.asyncio
async def test_run_sequence_tick_fires_and_stamps(db, monkeypatch):
    """End-to-end with mocked Resend. Verify the right bucket is sent
    and the account's `email_sequence_sent` is stamped."""
    from services import developer_email_sequence as _ES

    sent_calls = []

    async def _fake_send(**kw):
        sent_calls.append(kw)
        return True, f"mock-msg-{len(sent_calls)}"

    import services.email_service_resend as _esr
    monkeypatch.setattr(_esr, "send_email", _fake_send)

    # Seed an account that should hit day3_github_nudge
    user_id = f"seq-{uuid.uuid4().hex[:10]}"
    email = f"seq+{uuid.uuid4().hex[:6]}@example.com"
    created = (datetime.now(timezone.utc) - timedelta(days=3.5)).isoformat()
    await db.developer_accounts.insert_one({
        "user_id":          user_id,
        "email":            email,
        "name":             "Alice Tester",
        "email_verified":   True,
        "tokens_total_used": 0,
        "tokens_remaining":  1000,
        "github_connected":  False,
        "created_at":        created,
        "email_sequence_sent": [],
    })
    try:
        _ES.set_db(db)
        r = await _ES.run_sequence_tick(limit=50)
        assert r["ok"] is True
        # Locate our specific row sent
        ours = [s for s in r["sent_buckets"] if s["email"] == email]
        assert ours, f"our account should have been emailed: {r}"
        assert ours[0]["bucket_id"] == "day3_github_nudge"
        # Account stamped
        acc = await db.developer_accounts.find_one({"user_id": user_id})
        assert "day3_github_nudge" in (acc.get("email_sequence_sent") or [])
        # Idempotent re-run shouldn't fire again
        r2 = await _ES.run_sequence_tick(limit=50)
        again = [s for s in r2["sent_buckets"] if s["email"] == email]
        assert again == []
    finally:
        await db.developer_accounts.delete_one({"user_id": user_id})
        await db.developer_email_sequence_log.delete_many({"user_id": user_id})


# ═══════════════════════════════════════════════════════════════════
# Part 6 — sanity: scheduler wire-up
# ═══════════════════════════════════════════════════════════════════

def test_email_sequence_cron_wired_in_registry():
    from pathlib import Path
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_dev_email_sequence" in src
    assert "hour=5, minute=0" in src
    assert "run_sequence_tick" in src


def test_security_guards_set_db_wired_in_registry():
    from pathlib import Path
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "dev_security_guards" in src


def test_three_new_developer_endpoints_registered():
    from pathlib import Path
    src = Path("/app/backend/routers/developer_portal_router.py").read_text()
    assert "/api/developers/session/acquire" in src
    assert "/api/developers/session/release" in src
    assert "/api/developers/sessions" in src
    assert "/api/admin/developers/email-sequence/run" in src
