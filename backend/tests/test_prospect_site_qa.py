"""Tests for services.prospect_site_qa — Section 6 of growth-engine upgrade."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import prospect_site_qa as qa


# ── pure helpers ──────────────────────────────────────────────────────

def test_detect_name_phone_both_present():
    body = (
        '<html><head><title>Joe\'s Plumbing</title></head>'
        '<body><h1>Joe\'s Plumbing</h1>'
        '<a href="tel:+14165551234">Call</a></body></html>'
    )
    res = qa._detect_name_phone(body)
    assert res["phone_visible"] is True
    assert res["name_visible"] is True
    assert res["both_present"] is True


def test_detect_name_phone_missing_phone():
    body = '<html><h1>Some Biz</h1><body>no tel</body></html>'
    res = qa._detect_name_phone(body)
    assert res["phone_visible"] is False
    assert res["both_present"] is False


def test_detect_phone_formatted_number():
    body = '<html><h1>Biz</h1><p>Call us at (416) 555-1234</p></html>'
    res = qa._detect_name_phone(body)
    assert res["phone_visible"] is True


def test_pixel_regex_matches_snippet():
    snippet = '<script src="/api/pixel/aurem-pixel.js" data-aurem-key="x" defer></script>'
    assert qa.PIXEL_RE.search(snippet) is not None


def test_pixel_regex_no_match_random():
    snippet = '<script src="/random.js"></script>'
    assert qa.PIXEL_RE.search(snippet) is None


def test_viewport_regex_passes_real_meta():
    body = '<meta name="viewport" content="width=device-width, initial-scale=1">'
    assert qa.VIEWPORT_RE.search(body) is not None


def test_viewport_regex_fails_missing():
    body = '<meta name="viewport" content="initial-scale=1">'
    assert qa.VIEWPORT_RE.search(body) is None


# ── A2A check flow ────────────────────────────────────────────────────

def test_run_a2a_checks_passes_when_body_has_everything(monkeypatch):
    body = (
        '<!doctype html><html><head>'
        '<title>Joe\'s Plumbing — Toronto</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '</head><body>'
        '<h1>Joe\'s Plumbing</h1>'
        '<a href="tel:+14165551234">(416) 555-1234</a>'
        '<a href="https://aurem.live/signup?ref=L-1">Claim This Website — Free 7-Day Trial</a>'
        '<script src="https://aurem.live/api/pixel/aurem-pixel.js" data-aurem-key="x"></script>'
        '</body></html>'
    )
    class _R:
        status_code = 200
        text = body

    class _Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url):
            return _R()
        async def head(self, url):
            return _R()
    import services.prospect_site_qa as mod

    async def fake_check_images(b, base_url):
        return {"all_ok": True, "checked": 0, "broken": []}
    monkeypatch.setattr(mod, "_check_image_links", fake_check_images)
    monkeypatch.setattr("httpx.AsyncClient", _Client)

    res = asyncio.run(qa._run_a2a_checks("https://aurem.live/preview/L-1", "L-1"))
    assert res["checks"]["url_200"] is True
    assert res["checks"]["no_broken_images"] is True
    assert res["checks"]["mobile_renders"] is True
    assert res["checks"]["cta_href_valid"] is True
    assert res["checks"]["business_name_phone_visible"] is True
    assert res["checks"]["live_pixel_fires"] is True
    assert res["passed"] is True


def test_run_a2a_checks_fails_when_cta_ref_mismatch(monkeypatch):
    body = (
        '<html><head><title>Biz</title>'
        '<meta name="viewport" content="width=device-width">'
        '</head><body><h1>Biz</h1>'
        '<a href="tel:+14165551234">Call</a>'
        '<a href="https://aurem.live/signup?ref=DIFFERENT">Claim</a>'  # wrong ref
        '<script src="/api/pixel/aurem-pixel.js"></script>'
        '</body></html>'
    )
    class _R:
        status_code = 200
        text = body
    class _Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url): return _R()
        async def head(self, url): return _R()
    import services.prospect_site_qa as mod
    async def fake_check_images(b, base_url):
        return {"all_ok": True, "checked": 0, "broken": []}
    monkeypatch.setattr(mod, "_check_image_links", fake_check_images)
    monkeypatch.setattr("httpx.AsyncClient", _Client)

    res = asyncio.run(qa._run_a2a_checks("https://aurem.live/preview/L-1", "L-1"))
    assert res["checks"]["cta_href_valid"] is False
    assert res["passed"] is False


def test_run_a2a_checks_fails_when_url_404(monkeypatch):
    class _R:
        status_code = 404
        text = ""
    class _Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url): return _R()
        async def head(self, url): return _R()
    import services.prospect_site_qa as mod
    async def fake_check_images(b, base_url):
        return {"all_ok": True, "checked": 0, "broken": []}
    monkeypatch.setattr(mod, "_check_image_links", fake_check_images)
    monkeypatch.setattr("httpx.AsyncClient", _Client)
    res = asyncio.run(qa._run_a2a_checks("https://aurem.live/preview/L-1", "L-1"))
    assert res["checks"]["url_200"] is False
    assert res["passed"] is False
