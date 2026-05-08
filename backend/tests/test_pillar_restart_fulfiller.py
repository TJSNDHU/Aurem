"""Tests for the Pillar Restart Fulfiller (iter 322l Day 2.3)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from services import pillar_restart_fulfiller as prf

from test_sovereign_memory import FakeDB


@pytest.mark.asyncio
async def test_fulfill_once_no_pending_is_noop():
    db = FakeDB()
    summary = await prf.fulfill_once(db)
    assert summary["processed"] == 0


@pytest.mark.asyncio
async def test_unknown_pillar_returns_error():
    db = FakeDB()
    out = await prf._launch_pillar("99", db)
    assert out["ok"] is False
    assert "unknown_pillar" in out["error"]


@pytest.mark.asyncio
async def test_fulfill_once_marks_request_fulfilled():
    """Even when the launch fails, the request row must be flagged
    `fulfilled: true` so we don't re-process in tight loops."""
    db = FakeDB()
    await db["pillar_restart_requests"].insert_one({
        "pillar": "99",  # bogus → launcher will error
        "ts": datetime.now(timezone.utc).isoformat(),
        "fulfilled": False,
        "source": "sovereign_watchdog",
    })
    summary = await prf.fulfill_once(db)
    assert summary["processed"] == 1
    assert summary["failed"] == 1
    rows = db["pillar_restart_requests"].docs
    assert rows[0]["fulfilled"] is True
    assert "attempt_result" in rows[0]


@pytest.mark.asyncio
async def test_failed_launch_submits_learning_candidate():
    """A failed launch must trigger a memory-guard submission so the
    Council can audit whether the launcher mapping needs updating."""
    db = FakeDB()
    await db["pillar_restart_requests"].insert_one({
        "pillar": "99",
        "ts": datetime.now(timezone.utc).isoformat(),
        "fulfilled": False,
    })
    sub = AsyncMock(return_value="learning-id")
    with patch("services.sovereign_memory.submit_learning", side_effect=sub):
        await prf.fulfill_once(db)
    assert sub.called
    # The kind must include the pillar number for downstream filtering.
    call_kwargs = sub.call_args.kwargs
    assert call_kwargs["kind"].startswith("pillar_restart_failure:p99")
    assert call_kwargs["agent_role"] == "watchdog"


@pytest.mark.asyncio
async def test_successful_launch_does_not_submit_learning():
    """Happy path — no Memory-Guard noise."""
    db = FakeDB()
    await db["pillar_restart_requests"].insert_one({
        "pillar": "1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "fulfilled": False,
    })
    fake_launch = AsyncMock(return_value={"ok": True, "launcher": "fake"})
    sub = AsyncMock(return_value="x")
    with patch.object(prf, "_launch_pillar", side_effect=fake_launch):
        with patch("services.sovereign_memory.submit_learning", side_effect=sub):
            summary = await prf.fulfill_once(db)
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    assert not sub.called
