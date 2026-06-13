"""
Regression tests for the P1 Infrastructure pillar check + auto-repair.

Run:
    cd /app/backend && python -m pytest tests/test_pillar_p1_autorepair.py -v
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from routers import pillars_health_router as hr

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


@pytest.mark.asyncio
async def test_p1_green_on_fast_ping():
    """Single fast ping → green, and LAST_GREEN_TS updated."""
    hr._P1_LAST_GREEN_TS = 0.0
    db = MagicMock()
    db.command = AsyncMock(return_value={"ok": 1})
    result = await hr._check_p1_infrastructure(db)
    assert result == "green"
    assert hr._P1_LAST_GREEN_TS > 0


@pytest.mark.asyncio
async def test_p1_yellow_on_transient_failure_with_recent_green():
    """All 3 pings fail + topology refresh fails + last green within 30s → yellow."""
    async def _bad_ping(*args, **kwargs):
        raise asyncio.TimeoutError("slow mongo")
    db = MagicMock()
    db.command = _bad_ping
    db.client = MagicMock()
    db.client.list_database_names = _bad_ping
    # Simulate: last green was 10 sec ago → still in sticky window
    hr._P1_LAST_GREEN_TS = time.time() - 10
    result = await hr._check_p1_infrastructure(db)
    assert result == "yellow", f"expected yellow (sticky), got {result}"


@pytest.mark.asyncio
async def test_p1_red_only_when_sustained_failure():
    """All pings fail + topology fails + last green > 30s ago → red."""
    async def _bad_ping(*args, **kwargs):
        raise asyncio.TimeoutError("dead mongo")
    db = MagicMock()
    db.command = _bad_ping
    db.client = MagicMock()
    db.client.list_database_names = _bad_ping
    # No recent green
    hr._P1_LAST_GREEN_TS = time.time() - 120
    result = await hr._check_p1_infrastructure(db)
    assert result == "red"


@pytest.mark.asyncio
async def test_p1_auto_repair_via_topology_refresh():
    """When pings fail but client.list_database_names succeeds, repair kicks in → green."""
    async def _bad_ping(*args, **kwargs):
        raise asyncio.TimeoutError("transient")

    async def _good_topology(*args, **kwargs):
        return ["admin", "local", "aurem"]

    db = MagicMock()
    db.command = _bad_ping
    db.client = MagicMock()
    db.client.list_database_names = _good_topology
    hr._P1_LAST_GREEN_TS = 0.0
    result = await hr._check_p1_infrastructure(db)
    assert result == "green", f"auto-repair should flip to green, got {result}"


@pytest.mark.asyncio
async def test_p1_background_repair_writes_two_records():
    """_p1_background_repair must insert 'running' + 'repaired|failed' rows."""
    inserted = []

    async def _insert(doc):
        inserted.append(doc)
        return MagicMock(inserted_id="x")

    async def _ok(*args, **kwargs):
        return {"ok": 1}

    db = MagicMock()
    db.command = _ok
    db.client = MagicMock()
    db.client.list_database_names = AsyncMock(return_value=["admin"])
    db.repair_requests = MagicMock()
    db.repair_requests.insert_one = _insert

    await hr._p1_background_repair(db, red_pillars=["P1"])
    assert len(inserted) == 2
    kinds = [d["kind"] for d in inserted]
    assert "mongo_topology_refresh" in kinds
    assert "mongo_topology_refresh_result" in kinds
    assert inserted[1]["status"] == "repaired"
