"""Quick Website Scanner — fuels /demo viral lead capture.

Lightweight, no-headless-browser scoring of:
  - meta tags    (title, description, og:image, viewport)
  - schema       (JSON-LD presence + count)
  - page speed   (page weight, render-blocking JS estimate, image-without-lazy)
  - broken links (HEAD top-10 anchor hrefs)
  - mobile       (viewport meta + responsive css hints)

Returns 5 cards with severity (red/yellow/green) + an aggregated score.
"""
from __future__ import annotations

import asyncio
import re
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import httpx

UA = "Mozilla/5.0 (compatible; AUREM-QuickScan/1.0; +https://aurem.live)"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
HEAD_LIMIT = 10  # broken-link sampling


def _normalize_domain(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if not raw.startswith("http"):
        raw = "https://" + raw.lstrip("/")
    return raw


def _severity(value: bool, weight: str = "medium") -> str:
    """Map presence to severity color."""
    if value:
        return "green"
    return "red" if weight == "high" else "yellow"


async def _check_links(client: httpx.AsyncClient, base: str, hrefs: List[str]) -> Dict:
    sample = hrefs[:HEAD_LIMIT]
    if not sample:
        return {"checked": 0, "broken": 0, "broken_urls": []}

    async def _one(u: str) -> tuple[str, int]:
        try:
            r = await client.head(u, follow_redirects=True, timeout=8)
            return u, r.status_code
        except Exception:
            try:
                r = await client.get(u, follow_redirects=True, timeout=8)
                return u, r.status_code
            except Exception:
                return u, 0

    results = await asyncio.gather(*[_one(u) for u in sample])
    broken = [u for u, code in results if code == 0 or code >= 400]
    return {"checked": len(sample), "broken": len(broken), "broken_urls": broken[:5]}


async def quick_scan(domain: str) -> Dict:
    """Run the 5-card scan against a domain. Always returns a dict shape, even on failure."""
    url = _normalize_domain(domain)
    if not url:
        return {"ok": False, "error": "empty domain"}

    parsed = urlparse(url)
    if not parsed.netloc:
        return {"ok": False, "error": "invalid domain"}

    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=TIMEOUT, follow_redirects=True) as c:
        try:
            r = await c.get(url)
        except Exception as e:
            return {"ok": False, "error": f"unreachable: {str(e)[:80]}"}

        if r.status_code >= 400:
            return {"ok": False, "error": f"site returned HTTP {r.status_code}"}

        html = r.text
        size_kb = len(html) // 1024
        low = html.lower()

        # ── Card 1: META TAGS ──
        title_m = re.search(r"<title[^>]*>(.+?)</title>", html, re.S | re.I)
        desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.I)
        og_m = re.search(r'<meta[^>]+property=["\']og:image["\']', html, re.I)
        viewport_m = re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.I)
        canonical_m = re.search(r'<link[^>]+rel=["\']canonical["\']', html, re.I)
        meta_score = sum(bool(x) for x in [title_m, desc_m, og_m, viewport_m, canonical_m])
        title_text = title_m.group(1).strip() if title_m else ""

        meta_card = {
            "id": "meta",
            "title": "SEO Meta Tags",
            "severity": "green" if meta_score == 5 else ("yellow" if meta_score >= 3 else "red"),
            "score": meta_score,
            "max": 5,
            "findings": [
                f"Title tag: {'✓ ' + title_text[:60] if title_text else '✗ MISSING'}",
                f"Meta description: {'✓ present' if desc_m else '✗ MISSING'}",
                f"Open Graph image: {'✓ present' if og_m else '✗ MISSING (poor social-share previews)'}",
                f"Viewport meta: {'✓ present' if viewport_m else '✗ MISSING (mobile broken)'}",
                f"Canonical URL: {'✓ present' if canonical_m else '✗ MISSING (duplicate-content risk)'}",
            ],
            "fix": "AUREM auto-rewrites missing meta tags + ships fix to live site.",
        }

        # ── Card 2: SCHEMA / STRUCTURED DATA ──
        jsonld_count = len(re.findall(r'<script[^>]+type=["\']application/ld\+json["\']', html, re.I))
        schema_card = {
            "id": "schema",
            "title": "Structured Data (JSON-LD)",
            "severity": "green" if jsonld_count >= 2 else ("yellow" if jsonld_count == 1 else "red"),
            "findings": [
                f"JSON-LD scripts: {jsonld_count}",
                "Used by Google Rich Results, ChatGPT, Perplexity AI",
                "Missing schema = invisible in AI search" if jsonld_count == 0 else
                ("Single schema — add Organization + LocalBusiness for max visibility" if jsonld_count == 1 else
                 "Strong AI-search visibility"),
            ],
            "fix": "AUREM generates Organization + LocalBusiness + Service schema and injects it.",
        }

        # ── Card 3: PAGE SPEED ──
        scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)', html, re.I)
        styles = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)', html, re.I)
        images = re.findall(r'<img[^>]+', html, re.I)
        lazy_imgs = sum(1 for tag in images if 'loading="lazy"' in tag or "loading='lazy'" in tag)
        non_lazy = max(0, len(images) - lazy_imgs)
        speed_problems = []
        if size_kb > 1500:
            speed_problems.append(f"HTML payload {size_kb} KB (target <1.5 MB)")
        if len(scripts) > 15:
            speed_problems.append(f"{len(scripts)} JS files (target <15)")
        if non_lazy > 5:
            speed_problems.append(f"{non_lazy} images NOT lazy-loaded")
        speed_sev = "green" if not speed_problems else ("yellow" if len(speed_problems) == 1 else "red")
        speed_card = {
            "id": "speed",
            "title": "Page Speed",
            "severity": speed_sev,
            "findings": [
                f"HTML weight: {size_kb} KB",
                f"JavaScript files: {len(scripts)} · Stylesheets: {len(styles)}",
                f"Images lazy-loaded: {lazy_imgs}/{len(images)}",
            ] + (["Issues: " + " · ".join(speed_problems)] if speed_problems else ["No major bottlenecks detected"]),
            "fix": "AUREM compresses images, lazy-loads, defers JS, ships speed patch live.",
        }

        # ── Card 4: BROKEN LINKS ──
        anchors = re.findall(r'<a[^>]+href=["\']([^"\']+)', html, re.I)
        # Resolve to absolute, strip fragments / mailto / tel / javascript
        absolute = []
        for h in anchors:
            if h.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            absolute.append(urljoin(url, h.split("#")[0]))
        # Deduplicate, prefer same-domain
        same_domain = list(dict.fromkeys([u for u in absolute if urlparse(u).netloc == parsed.netloc]))
        link_result = await _check_links(c, url, same_domain)
        link_sev = "green" if link_result["broken"] == 0 else ("yellow" if link_result["broken"] <= 2 else "red")
        link_card = {
            "id": "links",
            "title": "Broken Links",
            "severity": link_sev,
            "findings": [
                f"Sampled: {link_result['checked']} same-domain links",
                f"Broken: {link_result['broken']}",
            ] + (["Examples: " + ", ".join(u[:50] for u in link_result["broken_urls"])] if link_result["broken_urls"] else ["All sampled links healthy"]),
            "fix": "AUREM monitors links 24/7, auto-fixes redirects, removes 404 anchors.",
        }

        # ── Card 5: MOBILE-FRIENDLY ──
        has_viewport = bool(viewport_m)
        has_responsive = bool(re.search(r"@media[^{]*\(", low)) or "responsive" in low
        has_touch_target = bool(re.search(r"font-size\s*:\s*([0-9]+)", low))
        mobile_score = sum([has_viewport, has_responsive, has_touch_target])
        mobile_card = {
            "id": "mobile",
            "title": "Mobile-Friendly",
            "severity": "green" if mobile_score == 3 else ("yellow" if mobile_score == 2 else "red"),
            "findings": [
                f"Viewport meta: {'✓' if has_viewport else '✗'}",
                f"Responsive CSS detected: {'✓' if has_responsive else '✗'}",
                f"Readable font sizes: {'✓' if has_touch_target else '✗'}",
            ],
            "fix": "AUREM rewrites viewport, injects responsive CSS, fixes touch targets.",
        }

        cards = [meta_card, schema_card, speed_card, link_card, mobile_card]

        # Aggregate score
        sev_pts = {"green": 100, "yellow": 60, "red": 20}
        avg = round(sum(sev_pts[c["severity"]] for c in cards) / len(cards))
        critical = sum(1 for c in cards if c["severity"] == "red")

        return {
            "ok": True,
            "domain": parsed.netloc,
            "scanned_url": url,
            "score": avg,
            "critical_issues": critical,
            "cards": cards,
        }
