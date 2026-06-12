"""
Tests for Customer Portal Tier-1 + Council Repair (iter D-84).
Pure-logic coverage (deterministic, fast). Live endpoints proven via curl
(200 + 401 guards); bin-scoping is server-derived so cross-bin is structural.

Run: cd /app/backend && python -m pytest tests/test_customer_portal_tier1.py -v
"""
from routers import customer_portal_tier1_router as t1
from routers import customer_repair_council_router as cr


def test_stage_map_covers_real_statuses():
    # statuses verified present in live campaign_leads
    assert t1._stage_of("new") == "found"
    assert t1._stage_of("queued") == "found"
    assert t1._stage_of("scanned") == "found"
    assert t1._stage_of("emailed") == "contacted"
    assert t1._stage_of("contacted") == "contacted"
    assert t1._stage_of("whatsapp_sent") == "contacted"
    assert t1._stage_of("replied") == "replied"
    assert t1._stage_of("booked") == "booked"
    # unknown / blank → safe default
    assert t1._stage_of("internal_test") == "found"
    assert t1._stage_of(None) == "found"
    assert t1._stage_of("") == "found"


def test_funnel_order_stable():
    assert t1._FUNNEL_ORDER == ["found", "contacted", "replied", "booked"]


def test_iso_handles_str_and_none():
    assert t1._iso(None) == ""
    assert t1._iso("2026-06-12T00:00:00+00:00") == "2026-06-12T00:00:00+00:00"


def test_fix_to_patch_safe_types_only():
    bin_id = "AUR-TEST-001"
    meta = cr._fix_to_patch({"fixed": True, "fix_type": "add_meta_description", "fix_value": "Best plumber in Toronto"}, bin_id)
    assert meta["type"] == "meta" and meta["tenant_id"] == bin_id
    assert meta["attrs"]["name"] == "description"
    assert meta["status"] == "pending" and meta["source"] == "council_repair"

    title = cr._fix_to_patch({"fixed": True, "fix_type": "add_page_title", "fix_value": "Acme Plumbing"}, bin_id)
    assert title["type"] == "title" and title["content"] == "Acme Plumbing"

    vp = cr._fix_to_patch({"fixed": True, "fix_type": "add_viewport"}, bin_id)
    assert vp["type"] == "meta" and vp["attrs"]["name"] == "viewport"

    # unsupported fix → NOT auto-applied (stays in plan)
    assert cr._fix_to_patch({"fixed": True, "fix_type": "rewrite_homepage_copy"}, bin_id) is None


def test_repair_rate_limit_constant():
    assert cr.RATE_LIMIT == 3 and cr.RATE_WINDOW_H == 24


def test_repair_phases_ordered():
    names = [p[0] for p in cr.PHASES]
    assert names == ["queued", "analyzing", "council_review", "applying", "verifying", "done"]
