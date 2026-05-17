"""
Tests for the Pixel→ORA Bridge — iter 323g

These tests use mongomock_motor when available. If not installed, they
gracefully skip (pytest.importorskip).
"""
from __future__ import annotations

import pytest
import asyncio
from datetime import datetime, timedelta, timezone

mongomock_motor = pytest.importorskip("mongomock_motor")

from services.pixel_to_ora_bridge import PixelToOraBridge  # noqa: E402


@pytest.fixture
def db():
    return mongomock_motor.AsyncMongoMockClient()["aurem_test_pixel_bridge"]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_event_triggers_task(db):
    """A fresh js_error should produce exactly one pixel_ora_tasks doc."""
    await db.pixel_events.insert_one({
        "tenant_id": "tenant-a",
        "event": "js_error",
        "url": "https://example.com/a",
        "data": {"message": "ReferenceError"},
        "received_at": _now_iso(),
    })
    summary = await PixelToOraBridge().run_cycle(db)
    assert summary["scanned_events"] == 1
    assert summary["enqueued"] == 1
    assert summary["skipped_dedup"] == 0
    count = await db.pixel_ora_tasks.count_documents({"tenant_id": "tenant-a"})
    assert count == 1


@pytest.mark.asyncio
async def test_dedup_within_window(db):
    """Two identical events within 60 min → only one task enqueued."""
    base = {
        "tenant_id": "tenant-b",
        "event": "form_error",
        "url": "https://example.com/b",
        "data": {"field": "email"},
    }
    await db.pixel_events.insert_one({**base, "received_at": _now_iso()})
    await db.pixel_events.insert_one({**base, "received_at": _now_iso()})
    # First cycle enqueues one + dedups the second
    summary = await PixelToOraBridge().run_cycle(db)
    assert summary["enqueued"] == 1
    assert summary["skipped_dedup"] == 1
    # Insert another identical event and run again — still deduped
    await db.pixel_events.insert_one({**base, "received_at": _now_iso()})
    summary2 = await PixelToOraBridge().run_cycle(db)
    assert summary2["skipped_dedup"] >= 1
    total = await db.pixel_ora_tasks.count_documents({"tenant_id": "tenant-b"})
    assert total == 1


@pytest.mark.asyncio
async def test_github_path(db):
    """Tenant with a github_connections doc → task.kind == 'github'."""
    await db.github_connections.insert_one({
        "company_id": "tenant-c",
        "repo": "polaris/site",
        "branch": "main",
    })
    await db.pixel_events.insert_one({
        "tenant_id": "tenant-c",
        "event": "patch_failed",
        "url": "https://example.com/c",
        "data": {"patch_id": "p1"},
        "received_at": _now_iso(),
    })
    await PixelToOraBridge().run_cycle(db)
    task = await db.pixel_ora_tasks.find_one({"tenant_id": "tenant-c"}, {"_id": 0})
    assert task is not None
    assert task.get("kind") == "github"
    # No pending_pixel_patches write on the github path
    patches = await db.pending_pixel_patches.count_documents({"tenant_id": "tenant-c"})
    assert patches == 0


@pytest.mark.asyncio
async def test_pixel_patch_path(db):
    """No github_connections → task.kind == 'patch' AND pending_pixel_patches gets a doc."""
    await db.pixel_events.insert_one({
        "tenant_id": "tenant-d",
        "event": "js_error",
        "url": "https://example.com/d",
        "data": {"message": "TypeError"},
        "received_at": _now_iso(),
    })
    await PixelToOraBridge().run_cycle(db)
    task = await db.pixel_ora_tasks.find_one({"tenant_id": "tenant-d"}, {"_id": 0})
    assert task is not None
    assert task.get("kind") == "patch"
    patches = await db.pending_pixel_patches.count_documents({"tenant_id": "tenant-d"})
    assert patches == 1
