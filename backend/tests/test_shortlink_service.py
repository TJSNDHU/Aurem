"""
Shortlink service — iter 282al.

Covers the carrier-filter bypass path (Twilio error 30007) end-to-end:
  • create → unique slug + DB row
  • get_or_create → idempotent for same (lead_id, target_url)
  • resolve → rewrites to real target, increments click counter
  • expired slug → falls back to aurem.live
  • Mongo-stored naive `expires_at` compared against aware `now()` (regression:
    was returning fallback because of offset-naive/aware TypeError).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from services.shortlink_service import (
    SHORTLINK_BASE,
    create_shortlink,
    get_or_create_shortlink,
    resolve_shortlink,
    shortlink_stats,
    ensure_shortlink_indexes,
)


@pytest.fixture()
def db():
    """Isolated test DB per test run — dropped on teardown."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    name = f"aurem_test_shortlink_{uuid.uuid4().hex[:8]}"
    yield client[name]
    try:
        asyncio.get_event_loop().run_until_complete(client.drop_database(name))
    except Exception:
        pass


@pytest.mark.asyncio
async def test_create_mints_slug_and_short_url(db):
    
    r = await create_shortlink(db, "lead-1", "https://aurem.live/report/lead-1")
    assert r["slug"] and len(r["slug"]) >= 6
    assert r["short_url"].startswith(f"{SHORTLINK_BASE}/r/")

    stored = await db.shortlinks.find_one({"slug": r["slug"]})
    assert stored["target_url"] == "https://aurem.live/report/lead-1"
    assert stored["lead_id"] == "lead-1"
    assert stored["clicks"] == 0


@pytest.mark.asyncio
async def test_get_or_create_is_idempotent(db):
    
    url = "https://aurem.live/report/lead-idem"
    a = await get_or_create_shortlink(db, "lead-idem", url)
    b = await get_or_create_shortlink(db, "lead-idem", url)
    assert a == b
    # Only one doc per (lead_id, target_url)
    count = await db.shortlinks.count_documents({"lead_id": "lead-idem"})
    assert count == 1


@pytest.mark.asyncio
async def test_resolve_returns_target_and_increments_clicks(db):
    
    r = await create_shortlink(db, "lead-2", "https://aurem.live/report/lead-2")
    target = await resolve_shortlink(db, r["slug"])
    assert target == "https://aurem.live/report/lead-2"
    stored = await db.shortlinks.find_one({"slug": r["slug"]})
    assert stored["clicks"] == 1
    click = await db.shortlink_clicks.find_one({"slug": r["slug"]})
    assert click and click["lead_id"] == "lead-2"


@pytest.mark.asyncio
async def test_resolve_naive_expires_at_regression(db):
    """Mongo strips tz info on read — service must still compare cleanly.

    This is the iter 282al bug: `resolve_shortlink` was hitting
    TypeError('offset-naive vs aware'), swallowing it, and returning the
    aurem.live fallback instead of the real target.
    """
    
    r = await create_shortlink(db, "lead-naive", "https://aurem.live/report/lead-naive")
    # Force the stored expires_at to be timezone-naive (what real Mongo returns)
    future_naive = datetime.utcnow() + timedelta(days=10)
    await db.shortlinks.update_one(
        {"slug": r["slug"]},
        {"$set": {"expires_at": future_naive}},
    )
    target = await resolve_shortlink(db, r["slug"])
    assert target == "https://aurem.live/report/lead-naive"


@pytest.mark.asyncio
async def test_resolve_expired_falls_back(db):
    
    r = await create_shortlink(db, "lead-old", "https://aurem.live/report/lead-old")
    past = datetime.now(timezone.utc) - timedelta(days=1)
    await db.shortlinks.update_one(
        {"slug": r["slug"]}, {"$set": {"expires_at": past}},
    )
    target = await resolve_shortlink(db, r["slug"])
    assert target == SHORTLINK_BASE


@pytest.mark.asyncio
async def test_resolve_unknown_slug_returns_base(db):
    
    assert await resolve_shortlink(db, "does-not-exist") == SHORTLINK_BASE


@pytest.mark.asyncio
async def test_stats_reports_clicks_and_last_click(db):
    
    r = await create_shortlink(db, "lead-s", "https://aurem.live/report/lead-s")
    await resolve_shortlink(db, r["slug"])
    await resolve_shortlink(db, r["slug"])
    stats = await shortlink_stats(db, "lead-s")
    assert stats["clicks"] == 2
    assert stats["last_click"] is not None
    assert stats["short_url"] == r["short_url"]


@pytest.mark.asyncio
async def test_ensure_indexes_is_idempotent(db):
    
    await ensure_shortlink_indexes(db)
    await ensure_shortlink_indexes(db)  # idempotent
    info = await db.shortlinks.index_information()
    assert "slug_uniq" in info
    assert "expires_ttl" in info


if __name__ == "__main__":
    asyncio.run(test_create_mints_slug_and_short_url())
    asyncio.run(test_resolve_naive_expires_at_regression())
    print("OK")
