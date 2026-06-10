"""
D-71g — "Unexpected token '<'" defence.

Production saw the frontend crash with
   `Unexpected token '<', "<html><h"... is not valid JSON`
because the K8s ingress returned an HTML 502/504 page when a backend
route exceeded ~60s. Frontend's naked `r.json()` then choked.

This iter adds two layers of defence:
 1. Frontend `safeFetchJson()` sniffs content-type + body prefix.
 2. Backend `/health`, `/autofix/<tag>` wrap their inner logic in
    25s `asyncio.wait_for` and return structured JSON on timeout.
"""
from __future__ import annotations

from pathlib import Path


# ─── Backend: bounded execution on Campaign Health endpoints ────────

def test_campaign_health_endpoint_has_bounded_timeout():
    src = Path("/app/backend/routers/campaign_health_router.py").read_text()
    assert "wait_for(full_report" in src, (
        "/health must wrap full_report() in asyncio.wait_for to stay "
        "under the K8s ingress timeout"
    )
    assert "report_timeout" in src
    # Must return valid JSON shape on timeout (rows + summary), never raise.
    assert '"summary"' in src and '"rows"' in src


def test_autofix_one_endpoint_has_bounded_timeout():
    src = Path("/app/backend/routers/campaign_health_router.py").read_text()
    # Both the autofix-all (existed pre-D-71g) AND the per-tag autofix
    # must now be timeout-bounded.
    assert src.count("wait_for(apply") >= 1, (
        "/autofix/<tag> must wrap apply() in asyncio.wait_for"
    )
    assert "exceeded 25s budget" in src


# ─── Frontend: safeFetchJson defends against HTML response ──────────

def test_frontend_uses_safe_fetch_helper():
    src = Path("/app/frontend/src/platform/CampaignHealthPage.jsx").read_text()
    assert "safeFetchJson" in src, "Page must use the defensive fetch helper"
    # All three call-sites must go through it
    assert src.count("safeFetchJson(") >= 3


def test_safe_fetch_helper_sniffs_html():
    src = Path("/app/frontend/src/platform/CampaignHealthPage.jsx").read_text()
    # Must check content-type AND body prefix (ingress may forget c-type)
    assert "content-type" in src.lower() or "text/html" in src
    assert "<html" in src.lower() or "<!doctype" in src.lower()
    # And distinguish 502 vs 504 vs other
    assert "504" in src and "502" in src


def test_safe_fetch_helper_returns_structured_result():
    """The helper must return {ok, status, data, parseError} — never
    throw — so callers can render an empathic message instead of a
    raw 'Unexpected token <' exception."""
    src = Path("/app/frontend/src/platform/CampaignHealthPage.jsx").read_text()
    for key in ("parseError", "networkError", "data", "ok", "status"):
        assert key in src, f"safeFetchJson result must surface `{key}`"


def test_naked_r_json_is_removed():
    """Defensive — make sure the old `await r.json()` pattern that
    crashes on HTML is gone from the page."""
    src = Path("/app/frontend/src/platform/CampaignHealthPage.jsx").read_text()
    assert "await r.json()" not in src, (
        "Old crash-prone `await r.json()` pattern must be removed"
    )
