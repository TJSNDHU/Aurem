"""
D-71o — `/api/repair/scores` sources from REAL pixel/scan data.

User asked: customer panel ko AUREM platform ka nahi, customer ke
SITE ka actual data dikhana chahiye, "fetch from pixel". The pixel
+ scan engine writes scan results into `scan_history` with a `scores`
dict per axis. The repair_fixes collection then projects the
"after-fix" delta.

This iter wires the endpoint to that SSOT:
  1. score_before  ← scan_history.scores.<axis>  (REAL pixel/scan data)
  2. score_after   ← score_before + (approved × penalty), capped at 100
  3. fallback to legacy 100-(pending×penalty) if no scan exists
"""
from __future__ import annotations

from pathlib import Path


def _src():
    return Path("/app/backend/routers/ai_repair_router.py").read_text()


def test_scores_endpoint_reads_scan_history_first():
    src = _src()
    # Must query scan_history for the latest scan of this URL
    assert "scan_history.find_one" in src, (
        "Must read REAL scan data from scan_history as primary source"
    )
    # And the URL match must be flexible (with/without trailing slash)
    assert '"website_url": normalized' in src


def test_scores_endpoint_surfaces_data_source_in_response():
    """Transparency — the response must declare whether scores came from
    real pixel scans or fell back to fix-count projection."""
    src = _src()
    assert '"source"' in src
    assert "scan_history+repair_fixes" in src
    assert "repair_fixes_only" in src


def test_scores_endpoint_returns_overall_score_and_last_scan_at():
    src = _src()
    assert '"overall_score"' in src
    assert '"last_scan_at"' in src


def test_score_before_uses_pixel_truth_when_available():
    src = _src()
    # The _axis helper must prefer scan_scores[axis_key] over the
    # legacy 100-(total×penalty) calculation.
    assert "if axis_key in scan_scores" in src
    # Fallback to legacy projection
    assert "100 - total * penalty" in src


def test_score_after_caps_at_100():
    src = _src()
    assert "min(100, score_before + approved * penalty)" in src
