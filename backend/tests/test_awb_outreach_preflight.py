"""
Iter 305 — Outreach preflight regression test.

Guards against sending customer emails/SMS with AWB preview links that
would resolve to the public 404 page. The fix ensures
`_trigger_lead_outreach` refuses to dispatch if `rendered_html` is empty
or the site status is not in a live state.
"""
import os
import sys
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

# Make backend importable when running via pytest from /app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.auto_website_builder import _trigger_lead_outreach  # noqa: E402


MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client, client[DB_NAME]


@pytest.mark.asyncio
async def test_outreach_blocked_when_rendered_html_missing():
    client, db = _db()
    site_id = "test-preflight-no-html-305"
    slug = "test-preflight-no-html-305"
    # Seed a half-built site with no rendered_html
    await db.auto_built_sites.update_one(
        {"site_id": site_id},
        {"$set": {"site_id": site_id, "slug": slug, "status": "draft"}},
        upsert=True,
    )
    try:
        lead = {
            "lead_id": "lead-test-preflight-305",
            "business_name": "Preflight Test Biz",
            "verification": {
                "channel_gating": {"email": True, "sms": True},
                "email": {"value": "noreply@aurem.live"},
            },
        }
        out = await _trigger_lead_outreach(db, site_id, slug, lead)
        assert out.get("sent") == [] or out.get("sent") is None
        skipped = out.get("skipped") or []
        assert any(
            "preflight_failed" in (s.get("reason") or "") for s in skipped
        ), f"expected preflight block, got {out!r}"
    finally:
        await db.auto_built_sites.delete_one({"site_id": site_id})
        client.close()


@pytest.mark.asyncio
async def test_outreach_blocked_when_status_is_draft():
    client, db = _db()
    site_id = "test-preflight-draft-305"
    slug = "test-preflight-draft-305"
    await db.auto_built_sites.update_one(
        {"site_id": site_id},
        {"$set": {
            "site_id": site_id, "slug": slug,
            "status": "draft",
            "rendered_html": "<html><body>x</body></html>",
        }},
        upsert=True,
    )
    try:
        lead = {
            "lead_id": "lead-draft-305",
            "business_name": "Draft Biz",
            "verification": {
                "channel_gating": {"email": True},
                "email": {"value": "noreply@aurem.live"},
            },
        }
        out = await _trigger_lead_outreach(db, site_id, slug, lead)
        skipped = out.get("skipped") or []
        assert any(
            "preflight_failed" in (s.get("reason") or "") for s in skipped
        ), f"expected preflight block on draft, got {out!r}"
    finally:
        await db.auto_built_sites.delete_one({"site_id": site_id})
        client.close()
