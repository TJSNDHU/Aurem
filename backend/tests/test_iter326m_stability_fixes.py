"""
test_iter326m_stability_fixes.py — Regression for iter 326m stability work.
══════════════════════════════════════════════════════════════════════════════
Covers two production stability bugs that combined caused the "blinking"
preview pod the user reported on 2026-05-22:

(1) MongoDB FD exhaustion driven by ~40 services each creating their own
    `AsyncIOMotorClient(mongo_url)` (default maxPoolSize=100) → up to 4000
    socket slots requested on a single mongod → "Too many open files,
    errno: 24" → "connection closed" cascade on EVERY backend → 502 health.

    Fixes:
      • `utils/mongo_pool_guard.py` monkey-patches `AsyncIOMotorClient`
        and `pymongo.MongoClient` to default `maxPoolSize=5` (was 100).
      • Customer-facing docker-compose stacks raise mongod / api nofile
        ulimit 1024 → 65536 (`legion`, `hetzner`, `aurem-cto`).

(2) Campaign watchdog falsely tripping `zero_sent_streak` whenever the
    queue was legitimately empty (engine ran, processed 0 leads, sent 0).
    This produced streak=203 alarms with no real delivery problem and
    fired the autofix playbook every minute for hours.

    Fix: `services/ora_campaign_watchdog.py` now distinguishes:
       - silent failure: last_run_processed > 0 BUT last_run_sent == 0
       - empty queue:    last_run_processed == 0 OR note=="no-eligible-leads"
    Streak only increments on silent failure. Empty queue holds it steady.

═══════════════════════════════════════════════════════════════════════════
TEST INFRA (iter 326m-stab refactor)
═══════════════════════════════════════════════════════════════════════════
Originally each watchdog test built its own `AsyncIOMotorClient` per test,
ran on a fresh DB, then called `drop_database` + `client.close()` in
`finally`. That worked but:
  - 3 connection pools × 5 sockets each = 15 fresh sockets per session
    (worse if pytest reruns).
  - On test failure mid-`finally`, the cleanup leaked the database.
  - Each test re-paid the connect-handshake latency.

Refactored to:
  - **One** session-scoped `AsyncIOMotorClient` reused across all watchdog
    tests (`mongo_session_client` fixture, scope="session").
  - Each test gets a unique ephemeral DB via `ephemeral_db` (function
    scope) which YIELDs the db handle and ALWAYS drops it in teardown,
    even on exception.
  - Cleanup is explicit: every collection used by `_check_once` is purged
    on entry; the entire DB is dropped on exit.
  - Pre-test seeding helpers are factored out (`_seed_engine_cycle`,
    `_seed_health_state`) so the test bodies show INTENT, not plumbing.

Run:  cd /app/backend && python3 -m pytest tests/test_iter326m_stability_fixes.py -v
"""
from __future__ import annotations

import importlib
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

# ─────────────────────────────────────────────────────────────────────────────
# Session-scoped Mongo client (refactor — replaces per-test ephemeral pools).
# Reuses one connection pool across the whole test module; each test gets
# its own ephemeral DB on top of that shared client.
#
# NOTE on event loops (pytest-asyncio 1.3+): a session-scoped async fixture
# must run on the same loop as the tests that consume it. We pin BOTH the
# fixtures and the consuming tests to `loop_scope="session"` so motor's
# internal tasks aren't orphaned across loops between tests.
# ─────────────────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def mongo_session_client():
    """Single AsyncIOMotorClient for the whole session — bounded pool,
    explicit `close()` after the last test runs."""
    # Ensure pool guard is applied so this client respects the cap.
    import utils.mongo_pool_guard  # noqa: F401  (idempotent)
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        # Confirm reachable before any test runs.
        await client.admin.command("ping")
        yield client
    finally:
        client.close()


@pytest_asyncio.fixture(loop_scope="session")
async def ephemeral_db(mongo_session_client):
    """Per-test ephemeral DB. Unique name (uuid-suffixed) so concurrent
    pytest workers never collide. Drops the DB in teardown — guaranteed
    cleanup even when a test raises mid-flight."""
    db_name = f"aurem_test_iter326m_{uuid.uuid4().hex[:10]}"
    db = mongo_session_client[db_name]
    # Belt-and-braces: ensure a clean slate even if a prior aborted run
    # somehow left behind a same-named DB (uuid collision is astronomical
    # but the cleanup is cheap).
    await mongo_session_client.drop_database(db_name)
    try:
        yield db
    finally:
        await mongo_session_client.drop_database(db_name)


async def _seed_engine_cycle(db, *, processed: int, sent: int,
                             note: str = "", enabled: bool = True) -> None:
    """Helper — paint the auto_blast_config row to look like the engine
    just finished a cycle with the given outcome."""
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.auto_blast_config.delete_many({})
    await db.auto_blast_config.insert_one({
        "tenant_id": "global",
        "enabled": enabled,
        "last_run_at": now_iso,
        "last_run_processed": processed,
        "last_run_sent": sent,
        "last_run_note": note,
    })


async def _seed_health_state(db, *, streak: int,
                             tripped: list | None = None) -> None:
    """Helper — pre-populate ora_campaign_health so the watchdog has
    history to evolve from on the next `_check_once` call."""
    await db.ora_campaign_health.delete_many({})
    await db.ora_campaign_health.insert_one({
        "_id": "global",
        "zero_sent_streak": streak,
        "tripped": tripped or [],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Bug 1 — mongo-pool-guard monkey-patch
# ─────────────────────────────────────────────────────────────────────────────
def test_mongo_pool_guard_caps_motor_defaults():
    """Every fresh AsyncIOMotorClient should get maxPoolSize<=5 even if the
    caller does not pass it explicitly. This is the patch's whole purpose."""
    import utils.mongo_pool_guard  # noqa: F401  apply patch (idempotent)
    from motor.motor_asyncio import AsyncIOMotorClient

    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        opts = c.delegate.options
        assert opts.pool_options.max_pool_size == 5, (
            f"mongo-pool-guard FAILED to cap motor maxPoolSize → "
            f"actual={opts.pool_options.max_pool_size}, expected=5"
        )
    finally:
        c.close()


def test_mongo_pool_guard_caps_pymongo_defaults():
    """Same guarantee for synchronous pymongo MongoClient."""
    import utils.mongo_pool_guard  # noqa: F401
    from pymongo import MongoClient

    c = MongoClient(os.environ["MONGO_URL"])
    try:
        assert c.options.pool_options.max_pool_size == 5
    finally:
        c.close()


def test_mongo_pool_guard_respects_explicit_maxpoolsize():
    """If a service genuinely needs a bigger pool (e.g. bulk worker), it
    must be able to ask. The patch uses setdefault — explicit wins."""
    import utils.mongo_pool_guard  # noqa: F401
    from pymongo import MongoClient

    c = MongoClient(os.environ["MONGO_URL"], maxPoolSize=20)
    try:
        assert c.options.pool_options.max_pool_size == 20
    finally:
        c.close()


def test_mongo_pool_guard_idempotent():
    """apply() called twice must be a no-op — otherwise hot-reload would
    chain monkey-patches and recursion-explode."""
    import utils.mongo_pool_guard as g

    g.apply()                         # ensure applied (no-op if already)
    second = g.apply()
    assert second is False, "apply() not idempotent — would stack patches"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 1b — docker-compose ulimit ceilings (customer-facing prod stacks)
# ─────────────────────────────────────────────────────────────────────────────
import yaml  # noqa: E402  (kept module-local to avoid bloating top-of-file)


@pytest.mark.parametrize("compose_path,service_name,why", [
    ("/app/legion/docker-compose.yml",   "aurem-mongodb",
     "primary self-hosted mongod — must raise FD ceiling on the SERVER side"),
    ("/app/hetzner/docker-compose.yml",  "backend",
     "backend holds the mongo client pool — must raise FD on the CONSUMER side"),
    ("/app/aurem-cto/docker-compose.yml", "api",
     "api holds the Atlas mongo pool + integration sockets"),
])
def test_compose_stack_raises_nofile_to_65536(compose_path, service_name, why):
    """Each customer-facing compose stack must declare nofile=65536 on the
    relevant service (mongo OR the consumer holding the pool). Without
    this, `iter 326m-stab` is incomplete on the boxes that actually serve
    paying customers."""
    with open(compose_path) as f:
        compose = yaml.safe_load(f)
    services = compose.get("services") or {}
    assert service_name in services, (
        f"service `{service_name}` missing from {compose_path}"
    )
    svc = services[service_name]
    ulimits = svc.get("ulimits") or {}
    nofile = ulimits.get("nofile") or {}
    assert nofile.get("soft") == 65536, (
        f"{compose_path}::{service_name} ulimits.nofile.soft missing/wrong "
        f"(actual={nofile.get('soft')}, expected=65536). Reason: {why}"
    )
    assert nofile.get("hard") == 65536, (
        f"{compose_path}::{service_name} ulimits.nofile.hard missing/wrong "
        f"(actual={nofile.get('hard')}, expected=65536). Reason: {why}"
    )


@pytest.mark.parametrize("compose_path,service_name", [
    ("/app/legion/docker-compose.yml",   "aurem-mongodb"),
    ("/app/hetzner/docker-compose.yml",  "backend"),
    ("/app/aurem-cto/docker-compose.yml", "api"),
])
def test_compose_stack_raises_somaxconn_to_4096(compose_path, service_name):
    """Listen-backlog must match the raised FD ceiling. Default 128 silently
    drops connections under the load that 65536 FDs unlocks."""
    with open(compose_path) as f:
        compose = yaml.safe_load(f)
    sysctls = (compose.get("services") or {}).get(service_name, {}).get("sysctls") or {}
    # docker-compose normalises `key: value` AND `[key=value]` shapes — both pass.
    if isinstance(sysctls, list):
        sysctls = dict(s.split("=", 1) for s in sysctls)
    actual = sysctls.get("net.core.somaxconn")
    assert int(actual) == 4096, (
        f"{compose_path}::{service_name}.sysctls['net.core.somaxconn'] "
        f"actual={actual!r}, expected=4096"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bug 2 — watchdog empty-queue vs silent-failure
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio(loop_scope="session")
async def test_watchdog_empty_queue_does_not_inflate_streak(ephemeral_db):
    """When the engine reports `last_run_processed=0` (or
    note=='no-eligible-leads'), the watchdog must NOT increment
    zero_sent_streak. Doing so produced the 203-cycle false alarm."""
    from services import ora_campaign_watchdog as w

    importlib.reload(w)  # pick up the iter326m edit if pytest cached

    await _seed_engine_cycle(
        ephemeral_db, processed=0, sent=0, note="no-eligible-leads"
    )
    await _seed_health_state(ephemeral_db, streak=5, tripped=[])

    w.set_db(ephemeral_db)
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


@pytest.mark.asyncio(loop_scope="session")
async def test_watchdog_silent_failure_still_increments_streak(ephemeral_db):
    """When the engine processed leads but none got sent, the watchdog
    MUST still increment the streak — that's a real silent failure."""
    from services import ora_campaign_watchdog as w

    await _seed_engine_cycle(
        ephemeral_db, processed=12, sent=0, note="all-vetoed"
    )
    await _seed_health_state(ephemeral_db, streak=2, tripped=[])

    w.set_db(ephemeral_db)
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


@pytest.mark.asyncio(loop_scope="session")
async def test_watchdog_resets_streak_on_real_send(ephemeral_db):
    """When at least one lead actually got sent, streak must reset to 0
    regardless of prior history. Otherwise a healed system stays alarmed."""
    from services import ora_campaign_watchdog as w

    await _seed_engine_cycle(ephemeral_db, processed=5, sent=3)
    await _seed_health_state(
        ephemeral_db, streak=99, tripped=["zero_sent_streak"]
    )

    w.set_db(ephemeral_db)
    snap = await w._check_once()

    assert snap["zero_sent_streak"] == 0
    assert "zero_sent_streak" not in snap["tripped"]
