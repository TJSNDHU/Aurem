"""
D-71n — Customer panel Home vs Live Health mismatch fix.

Root cause: the two pages queried `/api/repair/scores` with DIFFERENT
URLs:
  • Home Dashboard  → repairLeaderboard.sites[0].url   (CUSTOMER's site)
  • Live Health     → window.location.origin           (AUREM platform URL)

Different URLs → different repair_fixes docs → different scores → the
customer saw two inconsistent panels showing the same axes with
different numbers.

Fix: Live Health now uses the same leaderboard-first-site resolution as
Home so both panels point at the customer's actual site. Falls back to
`window.location.origin` only when the leaderboard is empty (i.e. user
hasn't connected a site yet).
"""
from __future__ import annotations

from pathlib import Path


def _src():
    return Path("/app/frontend/src/platform/luxe/LuxeV2Pages.jsx").read_text()


def test_live_health_uses_customer_site_not_platform_url():
    """The old `_ownUrl = window.location.origin` pattern must be gone."""
    src = _src()
    # The leaderboard-first-site resolution must be present
    assert "/api/repair/scoreboard?limit=1" in src, (
        "Live Health must pull the customer site from the scoreboard, "
        "not default to window.location.origin"
    )
    assert "leaderboard?.sites?.[0]?.url" in src or "leaderboard?.[0]?.url" in src


def test_live_health_still_falls_back_when_no_leaderboard():
    """If the customer hasn't connected a site yet (leaderboard empty),
    the page must NOT crash — falls back to platform URL gracefully."""
    src = _src()
    assert "REACT_APP_PUBLIC_BASE_URL" in src
    assert "window.location.origin" in src  # fallback chain still present


def test_scores_call_uses_customer_site_var():
    """The actual fetch URL must read `_customerSite` not the old `_ownUrl`."""
    src = _src()
    assert "encodeURIComponent(_customerSite)" in src, (
        "Score fetch must use the customer-site variable"
    )
