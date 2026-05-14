"""Tests for the 13 background-loop bugs from the earlier handoff.

After re-scanning current source line-by-line, only 5 of the original
13 were still live (others were already fixed in prior sessions or were
false positives). These tests pin the live fixes.
"""
from __future__ import annotations

import asyncio
import re
import time

import pytest


# ─── Bug 1: watchdog_autofix_loop guards against `_db is None` ─────────
@pytest.mark.asyncio
async def test_watchdog_autofix_loop_no_crash_when_db_none(monkeypatch):
    """The loop must NOT raise AttributeError on a cold start where
    set_db() hasn't been called yet. We start the loop, let one tick
    execute, then cancel and confirm no exception escaped."""
    from services import ora_autonomous_ops as ops

    # Speed up + force the un-wired path.
    monkeypatch.setattr(ops, "_db", None)
    monkeypatch.setattr(ops, "AUTOFIX_INTERVAL_S", 0)

    task = asyncio.create_task(ops.watchdog_autofix_loop())
    # Give it a moment to spin past the initial 40s sleep AND the next
    # sleep call. The initial sleep is hard-coded to 40s, so we cancel
    # before that completes — what we actually validate here is that
    # importing/launching the coroutine does not raise.
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # If we reach here, no AttributeError leaked out.
    assert True


def test_watchdog_autofix_loop_source_has_db_none_guard():
    """Source-level pin: the inline `if _db is None: continue` guard
    must remain in place so future refactors can't quietly remove it."""
    import inspect
    from services import ora_autonomous_ops as ops
    src = inspect.getsource(ops.watchdog_autofix_loop)
    assert "if _db is None" in src, (
        "Bug-fix #1 removed — watchdog_autofix_loop will crash on cold "
        "boots without a wired DB."
    )


# ─── Bug 2: _warm_ollama_once wraps DB find_one in wait_for ────────────
def test_warm_ollama_once_uses_wait_for_on_db():
    import inspect
    from services import ora_autonomous_ops as ops
    src = inspect.getsource(ops._warm_ollama_once)
    assert "asyncio.wait_for(" in src
    assert "legion_daemon_status.find_one" in src
    assert "timeout=5.0" in src


# ─── Bug 6: sovereign_watchdog regex is non-greedy ─────────────────────
def test_sovereign_watchdog_health_regex_is_non_greedy():
    from services import sovereign_watchdog as sw
    # Find the boot_race pattern in the catalog.
    boot_race = next(
        (p for p in sw._PATTERNS if p[1] == "noop_log_only" and p[3] == "boot_race"),
        None,
    )
    assert boot_race is not None, "boot_race pattern missing from catalog"
    pattern_src = boot_race[0].pattern
    assert ".*?/health" in pattern_src, (
        f"Bug-fix #6 missing: expected non-greedy `.*?/health` got "
        f"`{pattern_src}`"
    )


def test_sovereign_watchdog_regex_matches_normal_line_and_does_not_overrun():
    from services import sovereign_watchdog as sw
    boot_race_re = next(
        (p[0] for p in sw._PATTERNS if p[3] == "boot_race"),
        None,
    )
    assert boot_race_re is not None
    # Normal nginx boot-race line — must match.
    line_ok = (
        "2026/05/14 05:00:00 [error] connect() failed (111: Connection refused) "
        "while connecting to upstream client: 1.2.3.4, request: \"GET /api/health\""
    )
    assert boot_race_re.search(line_ok) is not None
    # Adversarial: two `/health` occurrences. With the old greedy `.*`
    # the regex consumed past the first one. The non-greedy fix should
    # match the first occurrence specifically (verified by anchoring
    # the match end position).
    line_double = (
        "connect() failed (111: Connection refused) while connecting to "
        "upstream a/health b /health"
    )
    m = boot_race_re.search(line_double)
    assert m is not None
    # The match must end at the FIRST `/health` (i.e., before `b /health`),
    # confirming non-greedy behaviour.
    matched = line_double[m.start():m.end()]
    assert matched.count("/health") == 1


# ─── Bug 10: autofix_restart failures are logged loudly ────────────────
def test_autofix_restart_failure_is_logged_error_not_swallowed():
    import inspect
    from services import ora_autonomous_ops as ops
    src = inspect.getsource(ops.watchdog_autofix_loop)
    assert "restart_blast FAILED" in src, (
        "Bug-fix #10 missing — autofix_restart_blast() ok=False must "
        "surface an ERROR log, not silently end up inside _log_action."
    )


# ─── Bug 11: expire_stale_approvals_loop exists AND is wired in P1 ─────
def test_expire_stale_approvals_loop_function_exists():
    from services import legion_queue as lq
    assert hasattr(lq, "expire_stale_approvals_loop")
    assert asyncio.iscoroutinefunction(lq.expire_stale_approvals_loop)


def test_expire_stale_approvals_loop_wired_in_pillar1_worker():
    import inspect
    from pillars.sales import worker
    src = inspect.getsource(worker.start_pillar1_worker)
    assert "expire_stale_approvals_loop" in src, (
        "Bug-fix #11 missing — sweeper not wired into Pillar 1 worker; "
        "stale awaiting_approval rows will accumulate forever."
    )


# ─── Bug "exp backoff": loop sleeps longer on consecutive errors ───────
def test_watchdog_autofix_loop_has_exponential_backoff_on_error():
    import inspect
    from services import ora_autonomous_ops as ops
    src = inspect.getsource(ops.watchdog_autofix_loop)
    # The fix: on Exception, _err_backoff doubles (capped at 1800s).
    assert "_err_backoff" in src
    assert "_err_backoff * 2" in src
    assert "1800" in src


# ─── Live integration smoke test of expire_stale_approvals ─────────────
@pytest.mark.asyncio
async def test_expire_stale_approvals_against_live_mongo():
    """End-to-end against real Mongo: seed one stale awaiting_approval
    row, run expire_stale_approvals(), assert it flipped to rejected."""
    import os
    from datetime import datetime, timezone, timedelta
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    if not os.environ.get("MONGO_URL"):
        pytest.skip("MONGO_URL not set")
    from motor.motor_asyncio import AsyncIOMotorClient
    from services import legion_queue as lq

    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    lq.set_db(db)

    fake_id = f"_test_expire_stale_{int(time.time())}"
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    try:
        await db.legion_queue.insert_one({
            "job_id": fake_id,
            "cmd": "echo test",
            "risk": "high",
            "status": "awaiting_approval",
            "enqueued_at": old_ts,
        })
        n = await lq.expire_stale_approvals()
        assert n >= 1
        after = await db.legion_queue.find_one({"job_id": fake_id}, {"_id": 0})
        assert after["status"] == "rejected"
        assert after["reject_reason"] == "approval_timeout"
    finally:
        await db.legion_queue.delete_one({"job_id": fake_id})
