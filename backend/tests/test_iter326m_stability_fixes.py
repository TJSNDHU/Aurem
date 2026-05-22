"""
test_iter326m_stability_fixes.py — Regression for iter 326m stability work.
══════════════════════════════════════════════════════════════════════════════
Covers two production stability bugs that combined caused the "blinking"
preview pod the user reported on 2026-05-22:

(1) MongoDB FD exhaustion driven by ~40 services each creating their own
    `AsyncIOMotorClient(mongo_url)` (default maxPoolSize=100) → up to 4000
    socket slots requested on a single mongod → "Too many open files,
    errno: 24" → "connection closed" cascade on EVERY backend → 502 health.

    Fix: `utils/mongo_pool_guard.py` monkey-patches both
    `AsyncIOMotorClient.__init__` and `pymongo.MongoClient.__init__` to
    set `maxPoolSize=5` (and other sane defaults) UNLESS caller passed
    explicit values. Imported FIRST in `server.py`, before any service
    constructs a client.

(2) Campaign watchdog falsely tripping `zero_sent_streak` whenever the
    queue was legitimately empty (engine ran, processed 0 leads, sent 0).
    This produced streak=203 alarms with no real delivery problem and
    fired the autofix playbook every minute for hours.

    Fix: `services/ora_campaign_watchdog.py` now distinguishes:
       - silent failure: last_run_processed > 0 BUT last_run_sent == 0
       - empty queue:    last_run_processed == 0 OR note=="no-eligible-leads"
    Streak only increments on silent failure. Empty queue holds it steady.

Run:  cd /app/backend && python3 -m pytest tests/test_iter326m_stability_fixes.py -v
"""
from __future__ import annotations

import asyncio
import importlib
import os

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 1 — mongo-pool-guard monkey-patch
# ─────────────────────────────────────────────────────────────────────────────
def test_mongo_pool_guard_caps_motor_defaults():
    """Every fresh AsyncIOMotorClient should get maxPoolSize<=5 even if the
    caller does not pass it explicitly. This is the patch's whole purpose."""
    import utils.mongo_pool_guard  # noqa: F401  apply patch (idempotent)
    from motor.motor_asyncio import AsyncIOMotorClient

    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    # Motor stores options on the underlying pymongo client.
    opts = c.delegate.options
    pool_opts = opts.pool_options
    assert pool_opts.max_pool_size == 5, (
        f"mongo-pool-guard FAILED to cap motor maxPoolSize → "
        f"actual={pool_opts.max_pool_size}, expected=5"
    )


def test_mongo_pool_guard_caps_pymongo_defaults():
    """Same guarantee for synchronous pymongo MongoClient (used by routers
    like pwa_router, broadcast_service, and a handful of legacy spots)."""
    import utils.mongo_pool_guard  # noqa: F401
    from pymongo import MongoClient

    c = MongoClient(os.environ["MONGO_URL"])
    pool_opts = c.options.pool_options
    assert pool_opts.max_pool_size == 5, (
        f"mongo-pool-guard FAILED to cap pymongo maxPoolSize → "
        f"actual={pool_opts.max_pool_size}, expected=5"
    )


def test_mongo_pool_guard_respects_explicit_maxpoolsize():
    """If a service genuinely needs a bigger pool (e.g. bulk worker), it
    must be able to ask. The patch uses setdefault — explicit wins."""
    import utils.mongo_pool_guard  # noqa: F401
    from pymongo import MongoClient

    c = MongoClient(os.environ["MONGO_URL"], maxPoolSize=20)
    pool_opts = c.options.pool_options
    assert pool_opts.max_pool_size == 20, (
        "patch must not override an explicit caller value"
    )


def test_mongo_pool_guard_idempotent():
    """apply() called twice must be a no-op — otherwise hot-reload would
    chain monkey-patches and recursion-explode."""
    import utils.mongo_pool_guard as g

    first = g.apply()
    second = g.apply()
    # first run is either True (fresh import) or False (already patched
    # by `import` side-effect); subsequent run MUST be False.
    assert second is False, "apply() not idempotent — would stack patches"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 2 — watchdog empty-queue vs silent-failure
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_watchdog_empty_queue_does_not_inflate_streak():
    """When the engine reports `last_run_processed=0` (or
    note=='no-eligible-leads'), the watchdog must NOT increment
    zero_sent_streak. Doing so produced the 203-cycle false alarm."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from services import ora_campaign_watchdog as w

    importlib.reload(w)  # pick up the iter326m edit if pytest cached

    test_db_name = "aurem_test_iter326m"
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[test_db_name]
    try:
        await db.auto_blast_config.delete_many({})
        await db.ora_campaign_health.delete_many({})
        await db.do_not_contact.delete_many({})

        # Seed the "empty queue" cycle: engine ran (last_run_at fresh) but
        # processed zero leads with the empty-queue note.
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.auto_blast_config.insert_one({
            "tenant_id": "global",
            "enabled": True,
            "last_run_at": now_iso,
            "last_run_processed": 0,
            "last_run_sent": 0,
            "last_run_note": "no-eligible-leads",
        })
        # Seed prior streak at 5 — patch must hold it steady, not inflate.
        await db.ora_campaign_health.insert_one({
            "_id": "global", "zero_sent_streak": 5, "tripped": [],
        })

        w.set_db(db)
        snap = await w._check_once()

        assert snap["empty_queue"] is True
        assert snap["last_run_note"] == "no-eligible-leads"
        assert snap["zero_sent_streak"] == 5, (
            f"streak inflated on empty-queue cycle "
            f"(actual={snap['zero_sent_streak']}, expected=5 steady)"
        )
        assert "zero_sent_streak" not in snap["tripped"], (
            "empty-queue cycle must NOT trip zero_sent_streak guard"
        )
    finally:
        await client.drop_database(test_db_name)
        client.close()


@pytest.mark.asyncio
async def test_watchdog_silent_failure_still_increments_streak():
    """When the engine processed leads but none got sent, the watchdog
    MUST still increment the streak — that's a real silent failure."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from services import ora_campaign_watchdog as w

    test_db_name = "aurem_test_iter326m_silent"
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[test_db_name]
    try:
        await db.auto_blast_config.delete_many({})
        await db.ora_campaign_health.delete_many({})

        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.auto_blast_config.insert_one({
            "tenant_id": "global",
            "enabled": True,
            "last_run_at": now_iso,
            "last_run_processed": 12,   # processed real leads
            "last_run_sent": 0,         # but sent 0 → silent failure
            "last_run_note": "all-vetoed",
        })
        await db.ora_campaign_health.insert_one({
            "_id": "global", "zero_sent_streak": 2, "tripped": [],
        })

        w.set_db(db)
        snap = await w._check_once()

        assert snap["empty_queue"] is False
        assert snap["zero_sent_streak"] == 3, (
            f"streak did not advance on silent failure "
            f"(actual={snap['zero_sent_streak']}, expected=3)"
        )
        # 3 is the SILENT_RUN_SENT_ZERO_CYCLES threshold — trip expected.
        assert "zero_sent_streak" in snap["tripped"], (
            "silent failure must trip zero_sent_streak guard"
        )
    finally:
        await client.drop_database(test_db_name)
        client.close()


@pytest.mark.asyncio
async def test_watchdog_resets_streak_on_real_send():
    """When at least one lead actually got sent, streak must reset to 0
    regardless of prior history. Otherwise a healed system stays alarmed."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from services import ora_campaign_watchdog as w

    test_db_name = "aurem_test_iter326m_reset"
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[test_db_name]
    try:
        await db.auto_blast_config.delete_many({})
        await db.ora_campaign_health.delete_many({})

        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.auto_blast_config.insert_one({
            "tenant_id": "global", "enabled": True,
            "last_run_at": now_iso,
            "last_run_processed": 5, "last_run_sent": 3,
        })
        await db.ora_campaign_health.insert_one({
            "_id": "global", "zero_sent_streak": 99, "tripped": ["zero_sent_streak"],
        })

        w.set_db(db)
        snap = await w._check_once()

        assert snap["zero_sent_streak"] == 0
        assert "zero_sent_streak" not in snap["tripped"]
    finally:
        await client.drop_database(test_db_name)
        client.close()
