"""
iter 326d — System Overview header must show TODAY'S iteration + date.

Earlier the page hardcoded `ITER 323r | MAY 18, 2026` in the frontend
fallback and `"322fa"` in the backend response. Founder asked for the
page to reflect today's work automatically.

These tests prove the route-level fix:
  • backend reads the latest iter from test filenames + memory docs
  • frontend uses `p.iteration` + `p.as_of` from the API response
  • a card for the day's batch is rendered in SystemOverview.jsx
"""
import os
import sys
import asyncio
import pytest

sys.path.insert(0, "/app/backend")


def test_helper_returns_latest_iter_from_tests_folder():
    """The helper must pick the lexically-latest iter from
    /app/backend/tests/test_iter*.py — that's the strongest signal
    a fix actually shipped (constitution requires a test per fix)."""
    from routers.system_overview_router import _current_iteration_and_date
    iter_str, as_of = _current_iteration_and_date()
    assert iter_str >= "326c", (
        f"helper returned {iter_str} but a 326+ regression test exists "
        f"in /app/backend/tests — helper must surface it"
    )
    # Date should be a real MAY date in MAY 21, 2026 format
    assert "2026" in as_of
    assert any(m in as_of for m in (
        "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
        "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
    ))


def test_backend_stats_includes_iteration_and_as_of():
    """The /stats response must carry both `iteration` and `as_of` so
    the frontend never falls back to a stale hardcoded value."""
    src = open("/app/backend/routers/system_overview_router.py",
               encoding="utf-8").read()
    assert '"iteration": current_iter' in src
    assert '"as_of":     as_of_date' in src
    # Old hardcoded "322fa" must be gone
    assert '"iteration": "322fa"' not in src


def test_frontend_header_uses_api_data():
    """SystemOverview.jsx header must read `p.iteration` and `p.as_of`
    and only fall back to today's batch (326uu / MAY 22, 2026)."""
    src = open("/app/frontend/src/platform/SystemOverview.jsx",
               encoding="utf-8").read()
    assert "{p.iteration || '326uu'}" in src
    assert "{p.as_of || 'MAY 22, 2026'}" in src
    # Old hardcoded MAY 18 fallback must be gone
    assert "MAY 18, 2026" not in src
    assert "'323r'" not in src


def test_today_batch_card_present():
    """A card summarising today's iter 325 → 326 batch must be rendered."""
    src = open("/app/frontend/src/platform/SystemOverview.jsx",
               encoding="utf-8").read()
    assert 'data-testid="sov-iter326-builds"' in src
    assert "ITER 325 → 326 · SOVEREIGNTY RESILIENCE BATCH" in src
    # Each major sub-card must reference its iter
    for tag in ("(326c)", "(326b)", "(326a)", "(325z)", "(325y)",
                "(325x)", "(325w)", "(325v)"):
        assert tag in src, f"missing batch sub-card {tag}"
