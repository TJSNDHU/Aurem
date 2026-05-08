"""
Iter 305b — Rebuild request regression tests.

Covers the POST /api/sites/{slug}/rebuild-request endpoint wired onto
the public 404 page. Must:
  1. Log to db.rebuild_requests with slug, ts, ip, user_agent.
  2. Always return 200 {"status": "requested"} — never raises.
  3. Have a 90-day TTL index on `ts`.
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


API_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.mark.asyncio
async def test_rebuild_request_logs_to_db():
    slug = "test-rebuild-slug-305b"
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        await db.rebuild_requests.delete_many({"slug": slug})

        async with httpx.AsyncClient(timeout=15) as hc:
            r = await hc.post(f"{API_URL}/api/sites/{slug}/rebuild-request")
        assert r.status_code == 200
        assert r.json() == {"status": "requested"}

        doc = await db.rebuild_requests.find_one({"slug": slug})
        assert doc is not None, "rebuild_requests doc not logged"
        assert doc["slug"] == slug
        assert "ts" in doc
        assert "user_agent" in doc
        # ip can legitimately be None behind a proxy layer, but the key
        # must still be present in the stored doc
        assert "ip" in doc
    finally:
        await db.rebuild_requests.delete_many({"slug": slug})
        client.close()


@pytest.mark.asyncio
async def test_rebuild_request_never_raises_on_any_slug():
    """Even with an unknown/garbage slug, endpoint returns 200."""
    async with httpx.AsyncClient(timeout=15) as hc:
        for bad in ["xyz", "does-not-exist", "a" * 250]:
            r = await hc.post(f"{API_URL}/api/sites/{bad}/rebuild-request")
            assert r.status_code == 200, (
                f"slug={bad!r} returned {r.status_code}"
            )
            assert r.json().get("status") == "requested"


@pytest.mark.asyncio
async def test_rebuild_request_ttl_index_exists():
    """Confirm the 90-day TTL index was created."""
    slug = "ttl-probe-slug-305b"
    # Trigger at least one write so the TTL ensure runs
    async with httpx.AsyncClient(timeout=15) as hc:
        await hc.post(f"{API_URL}/api/sites/{slug}/rebuild-request")

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        idxs = await db.rebuild_requests.index_information()
        ttl_match = [
            (name, spec) for name, spec in idxs.items()
            if spec.get("expireAfterSeconds") is not None
        ]
        assert ttl_match, f"no TTL index found on rebuild_requests, got {idxs!r}"
        # 90 days
        expected = 60 * 60 * 24 * 90
        assert any(
            spec.get("expireAfterSeconds") == expected for _, spec in ttl_match
        ), f"expected TTL {expected}s, got {ttl_match!r}"
    finally:
        await db.rebuild_requests.delete_many({"slug": slug})
        client.close()


@pytest.mark.asyncio
async def test_404_page_contains_rebuild_button():
    """The customer-facing 404 page must expose the rebuild CTA."""
    async with httpx.AsyncClient(timeout=15) as hc:
        r = await hc.get(f"{API_URL}/api/sites/definitely-nonexistent-for-rebuild-btn")
    assert r.status_code == 404
    body = r.text
    assert 'data-testid="awb-404-rebuild"' in body, "rebuild button missing"
    assert "requestRebuild" in body, "rebuild JS missing"
    assert "/rebuild-request" in body, "rebuild endpoint path missing from JS"
