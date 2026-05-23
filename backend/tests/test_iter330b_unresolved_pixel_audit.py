"""
tests/test_iter330b_unresolved_pixel_audit.py — iter 330b

The pixel webhook used to spam `WARNING [Webhook] Unresolved tenant...`
on every untagged hit. We now persist these to a dedicated audit
collection (`unmatched_pixel_events`) so the founder can review in one
place instead of grepping logs.
"""
from pathlib import Path


def test_warning_removed_and_replaced_by_audit_write():
    src = Path("/app/backend/routers/universal_connector_router.py").read_text()
    # No more raw warning for this code path.
    assert "Unresolved tenant for {platform}" not in src
    # New audit-collection write is present.
    assert "unmatched_pixel_events" in src
    assert "iter 330" in src


def test_unmatched_pixels_admin_endpoint_present():
    src = Path("/app/backend/routers/outreach_admin_router.py").read_text()
    assert "/unmatched-pixels" in src
    assert "list_unmatched_pixels" in src
    assert "count_24h" in src


def test_outreach_card_renders_unmatched_pixel_block():
    src = Path("/app/frontend/src/platform/admin/OutreachHealthCard.jsx").read_text()
    assert "outreach-unmatched-pixels" in src
    assert "outreach-unmatched-toggle" in src
    assert "unmatched-pixels?limit=" in src


# ── iter 330c — Link to tenant inline action ─────────────────────────


def test_resolver_module_exists():
    from services import pixel_referer_resolver as r
    assert callable(r.resolve_tenant_from_referer)
    assert callable(r.link_referer_to_tenant)


def test_resolver_host_extraction():
    from services.pixel_referer_resolver import _host_of
    assert _host_of("https://shop.example.ca/checkout") == "shop.example.ca"
    assert _host_of("http://Example.com/") == "example.com"
    assert _host_of("") is None
    assert _host_of(None) is None
    # Bare string fallback when not a URL.
    assert _host_of("shop.example.ca") == "shop.example.ca"


import pytest


@pytest.mark.asyncio
async def test_link_referer_to_tenant_upserts_and_validates():
    from services.pixel_referer_resolver import link_referer_to_tenant

    class Tenants:
        async def find_one(self, q, p=None):
            return {"bin_id": q.get("bin_id")} if q.get("bin_id") == "T1" else None

    class MapColl:
        def __init__(self): self.upserts = []
        async def update_one(self, q, u, upsert=False):
            self.upserts.append((q, u, upsert))

    class UnmatchedColl:
        async def update_many(self, q, u): pass

    class DB:
        def __init__(self):
            self.tenants = Tenants()
            self.pixel_referer_map = MapColl()
            self.unmatched_pixel_events = UnmatchedColl()

    db = DB()
    # Bad tenant rejected.
    bad = await link_referer_to_tenant(db, referer="https://x.com/", tenant_id="BAD")
    assert not bad["ok"]
    # Empty inputs rejected.
    e1 = await link_referer_to_tenant(db, referer="", tenant_id="T1")
    assert not e1["ok"]
    # Happy path.
    ok = await link_referer_to_tenant(db, referer="https://shop.example.ca/x", tenant_id="T1")
    assert ok["ok"] is True
    assert ok["host"] == "shop.example.ca"
    assert ok["tenant_id"] == "T1"
    assert len(db.pixel_referer_map.upserts) == 1


@pytest.mark.asyncio
async def test_resolve_tenant_from_referer_uses_host_match():
    from services.pixel_referer_resolver import resolve_tenant_from_referer

    class MapColl:
        async def find_one(self, q):
            return {"_id": q["_id"], "tenant_id": "T7"} if q["_id"] == "shop.example.ca" else None

    class DB:
        pixel_referer_map = MapColl()

    db = DB()
    assert await resolve_tenant_from_referer(db, "https://shop.example.ca/cart") == "T7"
    assert await resolve_tenant_from_referer(db, "https://other.com/") is None
    assert await resolve_tenant_from_referer(db, "") is None


def test_link_endpoint_present_in_router():
    src = Path("/app/backend/routers/outreach_admin_router.py").read_text()
    assert "/unmatched-pixels/link" in src
    assert "/tenants" in src
    assert "LinkRefererBody" in src


def test_resolver_wired_into_universal_router():
    src = Path("/app/backend/routers/universal_connector_router.py").read_text()
    assert "resolve_tenant_from_referer" in src
    assert "iter 330c" in src


def test_frontend_card_has_inline_link_ui():
    src = Path("/app/frontend/src/platform/admin/OutreachHealthCard.jsx").read_text()
    # New inline-row component + its key testids.
    assert "UnmatchedPixelRow" in src
    assert "unmatched-link-btn-" in src
    assert "unmatched-tenant-select-" in src
    assert "unmatched-link-save-" in src
    assert "/api/admin/outreach/tenants" in src
    assert "/api/admin/outreach/unmatched-pixels/link" in src
