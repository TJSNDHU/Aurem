"""
Tests for fallback_monitor — log, failure counter, reset.
Run: cd /app/backend && python3 -m pytest tests/test_fallback_monitor.py -v
"""
import os
import asyncio
import pytest
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.fallback_monitor import (  # noqa: E402
    log_fallback,
    record_primary_failure,
    reset_primary_failure,
)


def _db():
    mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
    db_name = os.environ.get("DB_NAME", "aurem_db").strip().strip('"').strip("'")
    return AsyncIOMotorClient(mongo_url)[db_name]


def test_log_fallback_creates_row():
    db = _db()

    async def _run():
        before = await db.fallback_usage_log.count_documents({"service": "test"})
        await log_fallback(db, service="test", primary="p1", used="p2",
                           result="fallback", reason="unit")
        after = await db.fallback_usage_log.count_documents({"service": "test"})
        assert after == before + 1
        # cleanup
        await db.fallback_usage_log.delete_many({"service": "test"})
    asyncio.run(_run())


def test_record_primary_failure_increments():
    db = _db()

    async def _run():
        # start clean
        await db.fallback_failure_state.delete_many({"service": "test"})
        await record_primary_failure(db, service="test", primary="p1", reason="x")
        await record_primary_failure(db, service="test", primary="p1", reason="x")
        doc = await db.fallback_failure_state.find_one({"service": "test", "primary": "p1"})
        assert doc["consecutive_failures"] == 2
        await reset_primary_failure(db, service="test", primary="p1")
        doc = await db.fallback_failure_state.find_one({"service": "test", "primary": "p1"})
        assert doc["consecutive_failures"] == 0
        # cleanup
        await db.fallback_failure_state.delete_many({"service": "test"})
    asyncio.run(_run())


def test_log_is_silent_on_none_db():
    """Should never raise when db is None."""
    async def _run():
        await log_fallback(None, service="x", primary="y", used=None,
                           result="error", reason="z")
        await record_primary_failure(None, service="x", primary="y", reason="z")
        await reset_primary_failure(None, service="x", primary="y")
    asyncio.run(_run())


def test_scout_logs_on_success():
    """End-to-end: scout_business writes a success log."""
    from services.business_scout import scout_business
    db = _db()

    async def _run():
        # marker we can clean up
        before = await db.fallback_usage_log.count_documents(
            {"service": "scout", "result": "success"})
        r = await scout_business("Starbucks", "Toronto")
        assert r.get("primary_source") == "google_places"
        after = await db.fallback_usage_log.count_documents(
            {"service": "scout", "result": "success"})
        assert after > before
    asyncio.run(_run())
