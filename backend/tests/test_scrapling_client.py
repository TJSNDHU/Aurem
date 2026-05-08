"""
iter 282al-22 — Tests for services.scrapling_client
"""
from __future__ import annotations

import pytest
from services.scrapling_client import (
    scrapling_extract_contacts,
    scrapling_health_check,
)


# ─────────── extract contacts (no network) ───────────
@pytest.mark.asyncio
async def test_extract_contacts_phone():
    html = """<html><body>
      <p>Call us: (905) 555-0142</p>
      <h1>Mike's Plumbing</h1>
    </body></html>"""
    out = await scrapling_extract_contacts("https://example.com", html)
    assert out["phone"] is not None
    assert "905" in out["phone"]


@pytest.mark.asyncio
async def test_extract_contacts_business_name():
    html = "<html><body><h1>Elite HVAC Solutions</h1></body></html>"
    out = await scrapling_extract_contacts("https://example.com", html)
    assert out["business_name"] == "Elite HVAC Solutions"


@pytest.mark.asyncio
async def test_extract_contacts_email_via_mailto():
    html = '<html><body><a href="mailto:hi@acme.ca">Email</a></body></html>'
    out = await scrapling_extract_contacts("https://example.com", html)
    assert out["email"] == "hi@acme.ca"


@pytest.mark.asyncio
async def test_extract_contacts_email_via_regex():
    html = "<html><body><p>Reach us at info@example.ca anytime.</p></body></html>"
    out = await scrapling_extract_contacts("https://example.com", html)
    assert out["email"] == "info@example.ca"


@pytest.mark.asyncio
async def test_extract_contacts_address():
    html = """<html><body>
      <address>123 Main St, Toronto, ON M5V 2T1</address>
    </body></html>"""
    out = await scrapling_extract_contacts("https://example.com", html)
    assert out["address"] is not None
    assert "Toronto" in out["address"]


@pytest.mark.asyncio
async def test_extract_contacts_empty_html_safe():
    out = await scrapling_extract_contacts("https://example.com", "")
    # Note: _httpx_fallback may run for the URL. Just verify shape.
    assert "phone" in out
    assert "email" in out
    assert "business_name" in out


@pytest.mark.asyncio
async def test_extract_contacts_services_list():
    html = """<html><body>
      <h2>Services</h2>
      <ul>
        <li>Drain cleaning</li>
        <li>Water heater repair</li>
        <li>Emergency plumbing</li>
      </ul>
    </body></html>"""
    out = await scrapling_extract_contacts("https://example.com", html)
    assert isinstance(out["services"], list)


# ─────────── fetch — fail path returns dict (no raise) ───────────
@pytest.mark.asyncio
async def test_scrapling_fetch_returns_dict_on_unknown_host():
    from services.scrapling_client import scrapling_fetch
    out = await scrapling_fetch(
        "https://this-does-not-exist-xyz-1234.invalid",
        use_stealth=False, timeout=3000,
    )
    assert isinstance(out, dict)
    assert "status" in out
    assert out["status"] == "failed"


# ─────────── health — always returns valid status ───────────
@pytest.mark.asyncio
async def test_health_check_returns_status():
    out = await scrapling_health_check()
    assert "status" in out
    assert out["status"] in ("green", "yellow", "red")
    assert "scrapling_installed" in out
    assert "stealth_available" in out


# ─────────── import sanity ───────────
def test_scrapling_client_module_loads():
    """Module must import even when scrapling itself isn't installed."""
    from services import scrapling_client as sc
    assert hasattr(sc, "scrapling_fetch")
    assert hasattr(sc, "scrapling_extract_contacts")
    assert hasattr(sc, "scrapling_find_mentions")
    assert hasattr(sc, "scrapling_health_check")


# ─────────── scan_website wired through scrapling ───────────
@pytest.mark.asyncio
async def test_scan_website_returns_correct_shape(monkeypatch):
    """Stub scrapling_fetch → confirm scan_website returns canonical shape."""
    import services.scrapling_client as sc
    import services.website_scraper as ws

    async def _fake_fetch(url, use_stealth=False, timeout=30000, css_selector=None):
        return {
            "status":  "success",
            "content": "Some long body text " * 20,
            "html":    "<h1>ACME</h1><p>Phone: (416) 555-0100</p>",
            "url":     url,
            "fetcher": "AsyncFetcher",
            "selector_result": None,
            "error":   None,
        }

    monkeypatch.setattr(sc, "scrapling_fetch", _fake_fetch, raising=False)
    monkeypatch.setattr(ws, "scrape_website", _fake_fetch, raising=False)
    out = await ws.scan_website("https://example.com")
    for key in ("status", "content", "brand", "contacts",
                "source_url", "source"):
        assert key in out, f"missing {key}"
    assert out["status"] == "success"
    assert out["source"] in ("AsyncFetcher", "scrapling")


@pytest.mark.asyncio
async def test_scan_website_never_raises_on_total_failure(monkeypatch):
    """Even when every fetcher fails, scan_website returns a dict."""
    import services.scrapling_client as sc
    import services.website_scraper as ws

    async def _fail(*a, **kw):
        return {"status": "failed", "content": "", "html": "",
                "url": a[0] if a else "?", "fetcher": None,
                "selector_result": None, "error": "boom"}

    async def _legacy_fail(url):
        raise RuntimeError("legacy down")

    monkeypatch.setattr(sc, "scrapling_fetch", _fail, raising=False)
    monkeypatch.setattr(ws, "scrape_website", _legacy_fail, raising=False)
    out = await ws.scan_website("https://example.com")
    assert isinstance(out, dict)
    assert out["status"] in ("failed", "skipped")
