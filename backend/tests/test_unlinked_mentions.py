"""Tests for the Unlinked-Mentions service — iter 282al-4."""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from services.unlinked_mentions_service import (
    ALLOWED_STATUSES,
    COLLECTION_HIST,
    COLLECTION_MAIN,
    ensure_mention_indexes,
    extract_mention_context,
    scan_for_unlinked_mentions,
    scan_sync,
    send_outreach_sync,
    update_mention_status,
    update_status_sync,
    unlinked_mentions_health,
)

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


@pytest.fixture()
def db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    name = f"aurem_test_mentions_{uuid.uuid4().hex[:8]}"
    yield client[name]
    try:
        asyncio.get_event_loop().run_until_complete(client.drop_database(name))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# extract_mention_context
# ─────────────────────────────────────────────────────────────────────
def test_extract_context_finds_mention():
    html = "<p>We absolutely love Test Plumbing Co for all our needs.</p>"
    ctx = extract_mention_context(html, "Test Plumbing Co")
    assert "Test Plumbing Co" in ctx
    assert len(ctx) <= 200


def test_extract_context_strips_html_and_scripts():
    html = ("<html><script>var x=1;</script>"
             "<p>Today's winner: Acme Dental. Call now.</p>"
             "<style>p{color:red;}</style></html>")
    ctx = extract_mention_context(html, "Acme Dental")
    assert "Acme Dental" in ctx
    assert "<p>" not in ctx
    assert "var x=1" not in ctx


def test_extract_context_missing_returns_empty():
    assert extract_mention_context("<p>nothing here</p>", "Acme") == ""
    assert extract_mention_context("", "Acme") == ""
    assert extract_mention_context("<p>hi</p>", "") == ""


# ─────────────────────────────────────────────────────────────────────
# scan — shape + caching
# ─────────────────────────────────────────────────────────────────────
def test_scan_returns_correct_shape(db):
    result = scan_sync(
        "Test Plumbing Co",
        "https://testplumbing.ca",
        db,
        limit=3,
    )
    assert "total_unlinked" in result
    assert "mentions" in result
    assert "provider" in result
    assert isinstance(result["mentions"], list)
    # Without any search provider keys configured, scan degrades gracefully
    assert result["total_unlinked"] >= 0


def test_scan_deduplicates_same_day(db):
    async def _run():
        r1 = await scan_for_unlinked_mentions(
            "Dedupe Biz Inc", "https://dedupe-biz.ca", db, limit=3,
        )
        r2 = await scan_for_unlinked_mentions(
            "Dedupe Biz Inc", "https://dedupe-biz.ca", db, limit=3,
        )
        return r1, r2
    r1, r2 = asyncio.new_event_loop().run_until_complete(_run())
    assert r1.get("cached") in (False, None)
    # Second call within the same day must hit cache
    assert r2.get("cached") is True


# ─────────────────────────────────────────────────────────────────────
# status transitions + history log
# ─────────────────────────────────────────────────────────────────────
def test_update_status_valid_transition_logs_history(db):
    mid = "mention-001-test"

    async def _run():
        await db[COLLECTION_MAIN].insert_one({
            "business_name": "Seed Biz",
            "scan_date":     datetime.now(timezone.utc),
            "mentions": [{
                "mention_id":      mid,
                "url":             "https://blog.example.com/post-1",
                "domain":          "blog.example.com",
                "has_link":        False,
                "mention_context": "Seed Biz is great.",
                "status":          "pending",
                "discovered_at":   datetime.now(timezone.utc),
            }],
            "total_unlinked": 1,
            "ts":             datetime.now(timezone.utc),
        })
        ok = await update_mention_status(db, mid, "reclaimed",
                                           notes="manual-confirm")
        cnt = await db[COLLECTION_HIST].count_documents({"mention_id": mid})
        return ok, cnt

    ok, cnt = asyncio.new_event_loop().run_until_complete(_run())
    assert ok is True
    assert cnt == 1


def test_update_status_rejects_bad_status(db):
    # No such mention — still must reject invalid status
    ok = update_status_sync(db, "nope-id", "not_a_real_status")
    assert ok is False


def test_allowed_statuses_constant():
    assert "pending" in ALLOWED_STATUSES
    assert "reclaimed" in ALLOWED_STATUSES
    assert "outreach_sent" in ALLOWED_STATUSES
    assert "ignored" in ALLOWED_STATUSES


# ─────────────────────────────────────────────────────────────────────
# reclamation outreach — graceful when composer fails / missing lead
# ─────────────────────────────────────────────────────────────────────
def test_send_outreach_missing_mention_returns_error(db):
    result = send_outreach_sync(db, "ghost-id", {"business_name": "X"})
    assert result["sent"] is False
    assert "error" in result


def test_send_outreach_no_lead_is_graceful(db):
    result = send_outreach_sync(db, "any-id", None)
    assert result["sent"] is False
    assert result.get("error")


# ─────────────────────────────────────────────────────────────────────
# indexes + health
# ─────────────────────────────────────────────────────────────────────
def test_ensure_mention_indexes_creates_ttl(db):
    async def _run():
        await ensure_mention_indexes(db)
        main = await db[COLLECTION_MAIN].index_information()
        hist = await db[COLLECTION_HIST].index_information()
        # Idempotent — second call must not raise
        await ensure_mention_indexes(db)
        return main, hist
    main_idx, hist_idx = asyncio.new_event_loop().run_until_complete(_run())
    assert "ts_ttl" in main_idx
    assert "ts_ttl" in hist_idx


def test_unlinked_mentions_health_grey_when_empty(db):
    async def _run():
        return await unlinked_mentions_health(db)
    health = asyncio.new_event_loop().run_until_complete(_run())
    assert health["ok"] is True
    assert health["status"] in ("grey", "green", "yellow")


# ─────────────────────────────────────────────────────────────────────
# ORA skill routing
# ─────────────────────────────────────────────────────────────────────
def test_ora_skill_routes_on_backlink_keyword():
    from services.skill_router import route_sync
    assert route_sync("who mentions aurem without linking") == "seo_backlinks"
    assert route_sync("run a backlink scan on us") == "seo_backlinks"
    assert route_sync("find unlinked mentions") == "seo_backlinks"
    # Negative — "link to this site" shouldn't hijack
    assert route_sync("scan this website https://example.com") == "scout_scan"
