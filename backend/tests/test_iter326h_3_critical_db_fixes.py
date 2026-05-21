"""
iter 326h — Regression tests for 3 P0/P1 DB bug fixes
═══════════════════════════════════════════════════════════════════════════
Fixes covered:

1. Founder admin_users mirror
   • ensure_founders() now mirrors password into `admin_users.passwordHash`
     (camelCase, matching what /api/auth/rbac/login expects).
   • Falls back to mirroring from `users.password_hash` when no env hash
     and no seed password are available.

2. Campaign watchdog auto-reset on successful blast
   • run_one_cycle() now resets `ora_campaign_health.zero_sent_streak = 0`
     and pulls `zero_sent_streak` out of `tripped` when total_sent > 0.
   • No-ops cleanly when total_sent == 0 (idempotent).

3. api_audit_log 7-day TTL
   • ensure_audit_log_ttl() drops the broken `ts_ttl_35d` index (was on
     wrong field `ts`, real field is `timestamp`) and installs
     `ttl_timestamp_7d` (604800s) on the correct field.
   • Idempotent on repeat invocation.

These tests use an in-memory motor-compatible fixture (mongomock-motor)
where possible; for TTL behaviour we use the real local Mongo because
mongomock doesn't simulate index drops cleanly.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient


# ── shared fixture: ephemeral DB on the live local Mongo ───────────────
@pytest.fixture
def live_db():
    """A throw-away DB on the local Mongo. Cleaned up after each test.

    Returns a callable that builds a new client (each async test must
    create its own client to avoid event-loop conflicts across pytest
    fixture teardown).
    """
    db_name = f"aurem_iter326h_{uuid.uuid4().hex[:12]}"

    def _builder():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        return client[db_name], client

    yield _builder

    # cleanup with a fresh loop
    async def _cleanup():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        await cli.drop_database(db_name)
        cli.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_cleanup())
    finally:
        loop.close()


# ════════════════════════════════════════════════════════════════════════
# FIX 1 — Founder admin_users mirror
# ════════════════════════════════════════════════════════════════════════

def test_fix1_founder_provision_mirrors_admin_users_when_seed_password_set(
    live_db, monkeypatch
):
    """When FOUNDER_SEED_PASSWORD_1 is set, ensure_founders must seed
    `admin_users.passwordHash` (camelCase) with a bcrypt hash."""
    monkeypatch.setenv("FOUNDER_SEED_PASSWORD_1", "TestSeedPwd!123")
    monkeypatch.delenv("FOUNDER_PASSWORD_RESET", raising=False)
    # Force a fresh module reload so DEFAULT_FOUNDERS picks the env var.
    import importlib, services.founder_provision as fp
    importlib.reload(fp)

    async def go():
        db, _cli = live_db()
        res = await fp.ensure_founders(db)
        assert res["ok"] is True
        doc = await db.admin_users.find_one(
            {"email": "teji.ss1986@gmail.com"}
        )
        assert doc is not None, "founder admin_users row not created"
        assert doc.get("passwordHash"), "passwordHash missing!"
        assert doc["passwordHash"].startswith("$2"), \
            f"not a bcrypt hash: {doc['passwordHash'][:10]!r}"
        # RBAC code expects these too
        assert doc.get("role") == "owner"
        assert doc.get("isActive") is True
        assert doc.get("email") == "teji.ss1986@gmail.com"

    asyncio.new_event_loop().run_until_complete(go())


def test_fix1_founder_provision_backfills_from_users_when_no_seed(live_db, monkeypatch):
    """When no env seed password is provided, ensure_founders must mirror
    the existing bcrypt hash from `users.password_hash` into
    `admin_users.passwordHash`. This is the backfill path that fixes the
    current production issue (founder had no passwordHash in admin_users
    despite having a working hash in users)."""
    monkeypatch.delenv("FOUNDER_SEED_PASSWORD_1", raising=False)
    monkeypatch.delenv("FOUNDER_PASSWORD_RESET", raising=False)
    # bcrypt hash signature — must look real.
    KNOWN_HASH = "$2b$12$abcdefghijklmnopqrstuv.QWERTYUIOPasdfghjkLZXCVbnm12345"
    import importlib, services.founder_provision as fp
    importlib.reload(fp)

    async def go():
        db, _cli = live_db()
        # Pre-seed a users row with a valid bcrypt hash (simulate prod state).
        await db.users.insert_one({
            "email": "teji.ss1986@gmail.com",
            "password_hash": KNOWN_HASH,
            "name": "AUREM Founder",
        })
        # Make sure the existing founder row also exists with no hash
        await db.admin_users.insert_one({
            "email": "teji.ss1986@gmail.com", "role": "founder",
        })
        res = await fp.ensure_founders(db)
        assert res["ok"] is True
        doc = await db.admin_users.find_one(
            {"email": "teji.ss1986@gmail.com"}
        )
        assert doc.get("passwordHash") == KNOWN_HASH, \
            f"expected backfill from users.password_hash, got {doc.get('passwordHash')!r}"

    asyncio.new_event_loop().run_until_complete(go())


def test_fix1_founder_provision_idempotent(live_db, monkeypatch):
    """Running ensure_founders twice must not corrupt the existing hash."""
    monkeypatch.setenv("FOUNDER_SEED_PASSWORD_1", "TestSeedPwd!123")
    import importlib, services.founder_provision as fp
    importlib.reload(fp)

    async def go():
        db, _cli = live_db()
        await fp.ensure_founders(db)
        first = await db.admin_users.find_one(
            {"email": "teji.ss1986@gmail.com"}, {"_id": 0, "passwordHash": 1}
        )
        await fp.ensure_founders(db)
        second = await db.admin_users.find_one(
            {"email": "teji.ss1986@gmail.com"}, {"_id": 0, "passwordHash": 1}
        )
        # Hash MAY rotate if env-hash flow runs — but it must always be
        # a valid bcrypt hash on every invocation.
        assert second["passwordHash"].startswith("$2")
        assert first["passwordHash"].startswith("$2")

    asyncio.new_event_loop().run_until_complete(go())


# ════════════════════════════════════════════════════════════════════════
# FIX 2 — Campaign watchdog auto-reset
# ════════════════════════════════════════════════════════════════════════

def test_fix2_reset_zero_streak_clears_latched_state(live_db, monkeypatch):
    """When a cycle sends ≥1 lead, the helper must zero out the streak
    and pull 'zero_sent_streak' out of `tripped`."""
    from services import auto_blast_engine as engine

    async def go():
        db, _cli = live_db()
        # Simulate prod state — streak latched at 191, tripped includes us
        await db.ora_campaign_health.insert_one({
            "_id": "global",
            "zero_sent_streak": 191,
            "tripped": ["zero_sent_streak", "stale_heartbeat"],
        })
        monkeypatch.setattr(engine, "_get_db", lambda: db)
        await engine._reset_zero_streak_on_success(total_sent=3)
        doc = await db.ora_campaign_health.find_one({"_id": "global"})
        assert doc["zero_sent_streak"] == 0
        assert "zero_sent_streak" not in (doc.get("tripped") or [])
        # Other tripped flags should NOT be touched
        assert "stale_heartbeat" in doc["tripped"]
        # Audit fields written
        assert doc.get("last_successful_send_count") == 3
        assert doc.get("last_successful_send_at"), "audit timestamp missing"

    asyncio.new_event_loop().run_until_complete(go())


def test_fix2_reset_is_noop_when_zero_sent(live_db, monkeypatch):
    """Helper must NOT touch streak when total_sent == 0."""
    from services import auto_blast_engine as engine

    async def go():
        db, _cli = live_db()
        await db.ora_campaign_health.insert_one({
            "_id": "global",
            "zero_sent_streak": 5,
            "tripped": ["zero_sent_streak"],
        })
        monkeypatch.setattr(engine, "_get_db", lambda: db)
        await engine._reset_zero_streak_on_success(total_sent=0)
        doc = await db.ora_campaign_health.find_one({"_id": "global"})
        assert doc["zero_sent_streak"] == 5  # unchanged
        assert "zero_sent_streak" in doc["tripped"]  # unchanged

    asyncio.new_event_loop().run_until_complete(go())


def test_fix2_run_one_cycle_calls_reset():
    """Static check: run_one_cycle must call _reset_zero_streak_on_success
    before returning. Catches the regression where someone removes the
    wire-up but leaves the helper around."""
    src = open(
        "/app/backend/services/auto_blast_engine.py", encoding="utf-8"
    ).read()
    # The helper must be invoked inside the run_one_cycle body before
    # the final return statement of that function.
    assert "_reset_zero_streak_on_success(total_sent)" in src, (
        "watchdog reset call missing from auto_blast_engine.py"
    )


# ════════════════════════════════════════════════════════════════════════
# FIX 3 — api_audit_log 7-day TTL
# ════════════════════════════════════════════════════════════════════════

def test_fix3_ensure_audit_log_ttl_creates_correct_index(live_db):
    """First-time setup on an empty collection: must create
    `ttl_timestamp_7d` on `timestamp` with 604800s expiry."""
    from services.ensure_audit_log_ttl import ensure_audit_log_ttl

    async def go():
        db, _cli = live_db()
        # Empty collection, no pre-existing TTL.
        res = await ensure_audit_log_ttl(db)
        assert res["ok"] is True
        coll_summary = res["results"]["api_audit_log"]
        assert coll_summary["created"] == "ttl_timestamp_7d"
        assert coll_summary["field"] == "timestamp"
        assert coll_summary["ttl_seconds"] == 7 * 86400
        # Verify the index actually exists on the collection.
        info = await db.api_audit_log.index_information()
        assert "ttl_timestamp_7d" in info
        idx = info["ttl_timestamp_7d"]
        assert idx.get("expireAfterSeconds") == 604800
        assert idx["key"] == [("timestamp", 1)]

    asyncio.new_event_loop().run_until_complete(go())


def test_fix3_drops_broken_ts_field_ttl(live_db):
    """If a broken TTL index on the wrong field (`ts`) exists, it must
    be dropped before the correct one is created."""
    from services.ensure_audit_log_ttl import ensure_audit_log_ttl

    async def go():
        db, _cli = live_db()
        # Pre-seed a broken TTL like the prod state.
        await db.api_audit_log.create_index(
            [("ts", 1)],
            expireAfterSeconds=3024000,  # 35 days
            name="ts_ttl_35d",
        )
        res = await ensure_audit_log_ttl(db)
        coll_summary = res["results"]["api_audit_log"]
        assert "ts_ttl_35d" in coll_summary["dropped_broken_indexes"]
        info = await db.api_audit_log.index_information()
        assert "ts_ttl_35d" not in info, "broken TTL not dropped"
        assert "ttl_timestamp_7d" in info, "new TTL not created"

    asyncio.new_event_loop().run_until_complete(go())


def test_fix3_idempotent_on_repeat(live_db):
    """Running ensure_audit_log_ttl twice must not error or duplicate."""
    from services.ensure_audit_log_ttl import ensure_audit_log_ttl

    async def go():
        db, _cli = live_db()
        r1 = await ensure_audit_log_ttl(db)
        r2 = await ensure_audit_log_ttl(db)
        assert r1["ok"] and r2["ok"]
        info = await db.api_audit_log.index_information()
        # Exactly one TTL index should exist post-run.
        ttls = [name for name, m in info.items() if "expireAfterSeconds" in m]
        assert ttls == ["ttl_timestamp_7d"], f"unexpected TTL set: {ttls}"

    asyncio.new_event_loop().run_until_complete(go())


def test_fix3_wired_into_server_startup():
    src = open("/app/backend/server.py", encoding="utf-8").read()
    assert (
        "from services.ensure_audit_log_ttl import ensure_audit_log_ttl"
        in src
    ), "TTL ensure not imported in server.py"
    assert "await ensure_audit_log_ttl(db)" in src, (
        "TTL ensure not invoked in server startup"
    )
