"""
AWB Theme Discovery (iter 300)
==============================
For a given business_type + city, find 3-5 similar real-world businesses with
public websites, capture screenshots via Playwright, extract dominant colors
+ font hints, return as `theme_options` for the customer/admin to pick from.

Sources (in priority):
  1. Google Places (have key) — best for local US/UK/AU
  2. Tavily search (have key) — global fallback / discovery
  3. DuckDuckGo (no-key fallback)

Screenshot:
  Playwright async, 1280×720 viewport, 8s timeout, JPEG quality 65 → R2 upload.

Style extract:
  Uses page.evaluate() to read getComputedStyle on document.body + first H1/H2.
  Returns {primary_color, accent_color, font_family, font_heading}.

Public API:
  await discover_themes(business_type, city, n=4) -> [
    {url, business_name, screenshot_url, style: {colors, fonts}}, ...
  ]
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCREENSHOT_TIMEOUT_MS = 8000
THUMBNAIL_KEY_PREFIX = "thumbs"


# ─── candidate URL discovery ────────────────────────────────────────────────
async def _candidates_google_places(business_type: str, city: str, n: int = 8) -> List[Dict[str, Any]]:
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return []
    try:
        import httpx
        query = f"{business_type} in {city}"
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={"query": query, "key": api_key},
            )
            data = r.json()
        out: List[Dict[str, Any]] = []
        for p in (data.get("results") or [])[:n * 2]:
            place_id = p.get("place_id")
            if not place_id:
                continue
            # Need Place Details for website URL
            async with httpx.AsyncClient(timeout=10.0) as cli2:
                d = await cli2.get(
                    "https://maps.googleapis.com/maps/api/place/details/json",
                    params={"place_id": place_id, "fields": "name,website,url",
                            "key": api_key},
                )
                detail = (d.json() or {}).get("result") or {}
            site = detail.get("website")
            if site and site.startswith("http"):
                out.append({"url": site, "business_name": detail.get("name") or p.get("name"),
                            "source": "google_places"})
            if len(out) >= n:
                break
        return out
    except Exception as e:
        logger.debug(f"[themes] google_places failed: {e}")
        return []


async def _candidates_tavily(business_type: str, city: str, n: int = 5) -> List[Dict[str, Any]]:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": f"top {business_type} businesses {city} website",
                    "search_depth": "basic", "max_results": n * 2,
                    "include_domains": [],
                    "exclude_domains": ["facebook.com", "instagram.com", "linkedin.com",
                                        "yelp.com", "tripadvisor.com", "yellowpages.com"],
                },
            )
            data = r.json()
        out: List[Dict[str, Any]] = []
        for res in (data.get("results") or [])[:n * 2]:
            url = res.get("url")
            if url and url.startswith("http"):
                out.append({"url": url, "business_name": res.get("title", "")[:80],
                            "source": "tavily"})
            if len(out) >= n:
                break
        return out
    except Exception as e:
        logger.debug(f"[themes] tavily failed: {e}")
        return []


async def _candidates_ddg(business_type: str, city: str, n: int = 6) -> List[Dict[str, Any]]:
    """Free fallback: DuckDuckGo search via ddgs package."""
    try:
        from ddgs import DDGS
    except Exception:
        return []
    EXCLUDE = ("facebook.com", "instagram.com", "linkedin.com", "yelp.com",
               "yellowpages.com", "tripadvisor.com", "youtube.com", "twitter.com",
               "x.com", "google.com", "maps.google.com", "wikipedia.org",
               "indeed.com", "glassdoor.com")
    try:
        loop = asyncio.get_event_loop()
        def _run():
            with DDGS() as d:
                return list(d.text(
                    f"{business_type} {city} site",
                    region="us-en", safesearch="off", max_results=n * 3,
                ))
        rows = await loop.run_in_executor(None, _run)
        out: List[Dict[str, Any]] = []
        for r in rows or []:
            url = r.get("href") or r.get("url") or ""
            if not url.startswith("http"):
                continue
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower().replace("www.", "")
            if any(host.endswith(x) for x in EXCLUDE):
                continue
            out.append({"url": url, "business_name": (r.get("title") or "")[:80],
                        "source": "ddg"})
            if len(out) >= n:
                break
        return out
    except Exception as e:
        logger.debug(f"[themes] ddg failed: {e}")
        return []


def _dedupe_candidates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        try:
            from urllib.parse import urlparse
            host = urlparse(it["url"]).netloc.lower().replace("www.", "")
            if host in seen or not host:
                continue
            seen.add(host)
            out.append(it)
        except Exception:
            continue
    return out


async def _gather_candidates(business_type: str, city: str, n: int) -> List[Dict[str, Any]]:
    results = await asyncio.gather(
        _candidates_google_places(business_type, city, n=n + 2),
        _candidates_tavily(business_type, city, n=n + 2),
        _candidates_ddg(business_type, city, n=n + 4),
        return_exceptions=True,
    )
    merged: List[Dict[str, Any]] = []
    for r in results:
        if isinstance(r, list):
            merged.extend(r)
    return _dedupe_candidates(merged)[:n + 2]


# ─── playwright screenshot + style extract ──────────────────────────────────
_STYLE_JS = """
() => {
    const get = (sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const cs = getComputedStyle(el);
        return {
            color: cs.color, bg: cs.backgroundColor,
            font: cs.fontFamily, weight: cs.fontWeight, size: cs.fontSize,
        };
    };
    return {
        body: get('body'),
        h1: get('h1') || get('h2'),
        a: get('a'),
        button: get('button') || get('.btn') || get('[role=button]'),
    };
};
"""


def _hex_from_rgb(rgb: Optional[str]) -> Optional[str]:
    if not rgb:
        return None
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", rgb)
    if not m:
        return None
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"#{r:02x}{g:02x}{b:02x}".upper()


def _extract_palette(style: Dict[str, Any]) -> Dict[str, Any]:
    body = style.get("body") or {}
    h1 = style.get("h1") or {}
    btn = style.get("button") or {}
    a = style.get("a") or {}
    return {
        "primary_bg": _hex_from_rgb(body.get("bg")) or "#FFFFFF",
        "primary_text": _hex_from_rgb(body.get("color")) or "#0A0A0A",
        "accent": (_hex_from_rgb(btn.get("bg")) or _hex_from_rgb(a.get("color")) or "#C9A227"),
        "heading_color": _hex_from_rgb(h1.get("color")) or "#0A0A0A",
        "body_font": (body.get("font") or "system-ui, sans-serif").split(",")[0].strip().strip('"\''),
        "heading_font": (h1.get("font") or body.get("font") or "serif").split(",")[0].strip().strip('"\''),
    }


async def _capture_one(browser, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = candidate["url"]
    ctx = await browser.new_context(viewport={"width": 1280, "height": 720},
                                     user_agent="Mozilla/5.0 (AUREM ThemeBot/1.0)")
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded",
                        timeout=SCREENSHOT_TIMEOUT_MS)
        await page.wait_for_timeout(500)
        png = await page.screenshot(full_page=False, type="jpeg", quality=65)
        try:
            style = await page.evaluate(_STYLE_JS)
        except Exception:
            style = {}
        palette = _extract_palette(style)
    except Exception as e:
        logger.debug(f"[themes] capture {url} failed: {e}")
        await ctx.close()
        return None
    await ctx.close()

    # Upload thumbnail to R2
    thumb_url = await _upload_thumb_bytes(png, src_url=url)

    return {
        "url": url,
        "business_name": candidate.get("business_name"),
        "source": candidate.get("source"),
        "screenshot_url": thumb_url,
        "screenshot_bytes": len(png),
        "style": palette,
    }


async def scrape_one_url(url: str) -> Optional[Dict[str, Any]]:
    """Public helper: scrape a single user-submitted URL → returns
    a theme dict {url, business_name, screenshot_url, style} or None.
    Used by Theme Picker 'Email your favorite site URL' flow."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
            cand = {"url": url, "business_name": url, "source": "user-supplied"}
            result = await _capture_one(browser, cand)
            await browser.close()
            return result
    except Exception as e:
        logger.warning(f"[themes] scrape_one_url failed: {e}")
        return None


async def discover_themes(business_type: str, city: str, n: int = 4) -> List[Dict[str, Any]]:
    """Returns up to `n` real-business theme candidates with screenshots + style hints.
    Falls back to curated catalog when external search APIs are unavailable.
    Curated entries get an on-the-fly playwright preview thumbnail."""
    cands = await _gather_candidates(business_type, city, n=n)
    if not cands:
        from services.awb_theme_catalog import get_curated_themes
        curated = get_curated_themes(business_type)[:n]
        return await _attach_curated_thumbs(business_type, curated)

    try:
        from playwright.async_api import async_playwright
    except Exception:
        logger.warning("[themes] playwright not available — curated fallback")
        from services.awb_theme_catalog import get_curated_themes
        curated = get_curated_themes(business_type)[:n]
        return await _attach_curated_thumbs(business_type, curated)

    out: List[Dict[str, Any]] = []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
            tasks = [_capture_one(browser, c) for c in cands]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict):
                    out.append(r)
                if len(out) >= n:
                    break
            await browser.close()
    except Exception as e:
        logger.warning(f"[themes] playwright run failed: {e}")

    if not out:
        from services.awb_theme_catalog import get_curated_themes
        curated = get_curated_themes(business_type)[:n]
        return await _attach_curated_thumbs(business_type, curated)

    if len(out) < n:
        from services.awb_theme_catalog import get_curated_themes
        cur = get_curated_themes(business_type)
        cur_with_thumbs = await _attach_curated_thumbs(business_type, cur[:n - len(out)])
        out.extend(cur_with_thumbs)
    return out[:n]


async def _attach_curated_thumbs(business_type: str,
                                  themes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """For curated themes, render a sample HTML via playwright and upload jpg.
    GUARANTEES every theme returns with a non-null `screenshot_url` — falls
    back to an inline SVG data-URL preview built from the theme's own palette
    when playwright/R2 are unavailable. Customers MUST never see a broken
    image icon (this kills conversion)."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
            for t in themes:
                if t.get("screenshot_url"):
                    continue
                html = _sample_html_for_theme(business_type, t["style"])
                ctx = await browser.new_context(viewport={"width": 1280, "height": 720})
                page = await ctx.new_page()
                try:
                    await page.set_content(html, wait_until="domcontentloaded",
                                           timeout=SCREENSHOT_TIMEOUT_MS)
                    png = await page.screenshot(full_page=False, type="jpeg", quality=70)
                except Exception:
                    png = None
                await ctx.close()
                if png:
                    uploaded = await _upload_thumb_bytes(png, src_url=None)
                    if uploaded:
                        t["screenshot_url"] = uploaded
                        t["screenshot_bytes"] = len(png)
            await browser.close()
    except Exception as e:
        logger.warning(f"[themes] curated thumb render failed: {e}")
    # Final guarantee: any theme still without a screenshot gets an inline
    # SVG data-URL preview so the UI never shows a broken-image icon.
    for t in themes:
        if not t.get("screenshot_url"):
            t["screenshot_url"] = _svg_preview_data_url(business_type, t.get("style") or {},
                                                        title=t.get("name") or t.get("business_name"))
            t["screenshot_kind"] = "svg_inline"
    return themes


def _svg_preview_data_url(business_type: str, style: Dict[str, Any],
                          title: Optional[str] = None) -> str:
    """Return a data:image/svg+xml;utf8 preview built from the theme palette.
    Always succeeds — no network, no playwright, no R2."""
    import html as _html
    from urllib.parse import quote
    bg = style.get("primary_bg") or "#FFFFFF"
    fg = style.get("primary_text") or "#0A0A0A"
    accent = style.get("accent") or "#C9A227"
    heading_color = style.get("heading_color") or fg
    heading_font = (style.get("heading_font") or "serif").split(",")[0].strip().strip('"\'')
    body_font = (style.get("body_font") or "system-ui, sans-serif").split(",")[0].strip().strip('"\'')
    label = _html.escape((title or business_type or "Preview")[:40])
    sub = _html.escape((business_type or "Your Business").title()[:50])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
        f'<rect width="1280" height="720" fill="{bg}"/>'
        f'<rect x="0" y="0" width="1280" height="80" fill="{accent}" opacity="0.10"/>'
        f'<text x="60" y="55" font-family="{body_font}" font-size="22" '
        f'fill="{fg}" opacity="0.7">{sub}</text>'
        f'<text x="60" y="240" font-family="{heading_font}" font-size="84" '
        f'font-weight="700" fill="{heading_color}">{label}</text>'
        f'<rect x="60" y="280" width="120" height="4" fill="{accent}"/>'
        f'<text x="60" y="340" font-family="{body_font}" font-size="22" '
        f'fill="{fg}" opacity="0.78">Crafted with care · Book a visit today</text>'
        f'<rect x="60" y="400" width="200" height="58" rx="6" fill="{accent}"/>'
        f'<text x="160" y="437" font-family="{body_font}" font-size="20" '
        f'font-weight="700" fill="#0A0A0A" text-anchor="middle">Get a Quote</text>'
        f'<g fill="{accent}" opacity="0.10">'
        f'<rect x="60" y="520" width="360" height="160" rx="8"/>'
        f'<rect x="460" y="520" width="360" height="160" rx="8"/>'
        f'<rect x="860" y="520" width="360" height="160" rx="8"/>'
        f'</g>'
        f'</svg>'
    )
    return f"data:image/svg+xml;utf8,{quote(svg, safe=':/?#[]@!$&()*+,;=')}"


def _sample_html_for_theme(business_type: str, style: Dict[str, Any]) -> str:
    """Tiny canonical preview to showcase a theme's color/font system."""
    bt = (business_type or "Your Business").title()
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
body{{margin:0;font:16px/1.6 '{style['body_font']}',system-ui,sans-serif;
  background:{style['primary_bg']};color:{style['primary_text']}}}
.hero{{padding:80px 40px 60px;border-bottom:1px solid {style['accent']}33}}
h1{{font:400 56px/1.05 '{style['heading_font']}',serif;margin:0 0 16px;
  color:{style['heading_color']}}}
p.sub{{font-size:18px;max-width:620px;opacity:.78}}
.cta{{display:inline-block;margin-top:24px;padding:14px 30px;border-radius:6px;
  background:{style['accent']};color:#0A0A0A;text-decoration:none;font-weight:700;
  letter-spacing:.5px}}
.row{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;
  padding:48px 40px;border-bottom:1px solid {style['accent']}22}}
.card{{padding:20px;background:{style['accent']}11;border-radius:8px;
  border:1px solid {style['accent']}22}}
.card h3{{margin:0 0 8px;color:{style['accent']};font-size:15px}}
</style></head><body>
<div class="hero"><h1>{bt}</h1>
<p class="sub">Crafted with care, powered by trusted local expertise. Book a visit today.</p>
<a class="cta" href="#">Get a Quote</a></div>
<div class="row">
<div class="card"><h3>Service One</h3><p>Reliable, fast, on time.</p></div>
<div class="card"><h3>Service Two</h3><p>Backed by 5-star reviews.</p></div>
<div class="card"><h3>Service Three</h3><p>Insured & local since day one.</p></div>
</div></body></html>"""


async def _upload_thumb_bytes(data: bytes, src_url: Optional[str] = None,
                               db=None) -> Optional[str]:
    """Upload a thumbnail to R2 and return the public proxy URL."""
    try:
        from services.cloudflare_r2 import _client, is_configured
        if not is_configured():
            return None
        cli = _client()
        thumb_id = uuid.uuid4().hex[:14]
        key = f"{THUMBNAIL_KEY_PREFIX}/{thumb_id}.jpg"
        cli.put_object(
            Bucket=os.environ.get("R2_BUCKET_NAME", "aurem-sites"),
            Key=key, Body=data, ContentType="image/jpeg",
            CacheControl="public, max-age=86400",
        )
        try:
            if db is None:
                import server
                db = getattr(server, "db", None)
            if db is not None:
                await db.awb_thumb_index.update_one(
                    {"thumb_id": thumb_id},
                    {"$set": {"thumb_id": thumb_id, "r2_key": key, "src_url": src_url}},
                    upsert=True,
                )
        except Exception as e:
            logger.warning(f"[themes] thumb index write failed: {e}")
        return f"/api/sites/_thumb/{thumb_id}"
    except Exception as e:
        logger.warning(f"[themes] thumb upload failed: {e}")
        return None


# ─── thumb retrieval helper ─────────────────────────────────────────────────
async def get_thumb_bytes(db, thumb_id: str) -> Optional[bytes]:
    if db is None:
        return None
    row = await db.awb_thumb_index.find_one({"thumb_id": thumb_id}, {"_id": 0, "r2_key": 1})
    if not row:
        return None
    try:
        from services.cloudflare_r2 import _client, is_configured
        if not is_configured():
            return None
        cli = _client()
        resp = cli.get_object(Bucket=os.environ.get("R2_BUCKET_NAME", "aurem-sites"),
                              Key=row["r2_key"])
        return resp["Body"].read()
    except Exception as e:
        logger.debug(f"[themes] thumb fetch failed: {e}")
        return None
