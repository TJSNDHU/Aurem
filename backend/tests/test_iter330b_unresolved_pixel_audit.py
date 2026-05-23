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
