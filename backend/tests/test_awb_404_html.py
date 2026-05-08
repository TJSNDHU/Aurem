"""
Iter 305 — AWB public 404 HTML regression test.

Guards the deal-breaking bug where customers who clicked an AWB link
received raw JSON `{"detail":"Site not found"}` instead of a friendly
HTML page.
"""
import os

import httpx
import pytest


API_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"


@pytest.mark.asyncio
async def test_sites_slug_404_returns_html_not_json():
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{API_URL}/api/sites/definitely-nonexistent-slug-xyz-305")
    assert r.status_code == 404, f"expected 404 got {r.status_code}"
    ctype = r.headers.get("content-type", "")
    assert "text/html" in ctype, f"expected HTML, got content-type={ctype!r}"
    body = r.text
    assert "{" not in body[:5], "response must not start with JSON brace"
    assert "data-testid=\"awb-404-page\"" in body, "branded 404 marker missing"
    assert "AUREM" in body, "brand missing from 404 page"
    assert "detail" not in body[:200].lower() or "text/html" in ctype, (
        "must not leak raw FastAPI {detail:...} JSON"
    )


@pytest.mark.asyncio
async def test_sites_site_id_404_returns_html_not_json():
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{API_URL}/api/sites/site/nonexistent-site-id-xyz-305")
    assert r.status_code == 404
    assert "text/html" in r.headers.get("content-type", "")
    assert "data-testid=\"awb-404-page\"" in r.text


@pytest.mark.asyncio
async def test_sites_404_no_cache_headers():
    """404 pages must not be cached — a later successful build should be
    visible immediately."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{API_URL}/api/sites/cache-probe-slug-305")
    assert r.status_code == 404
    cache = r.headers.get("cache-control", "").lower()
    assert "no-store" in cache, f"expected no-store, got {cache!r}"
