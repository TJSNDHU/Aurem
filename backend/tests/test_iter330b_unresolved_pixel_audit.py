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
