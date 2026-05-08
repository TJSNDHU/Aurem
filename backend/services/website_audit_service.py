"""
Website Audit Service (iter 304)
================================
Real probes — no mocks. Single entrypoint:

    await real_audit(url) -> dict

Probes (asyncio.gather):
  • SSL                  — stdlib ssl + socket
  • PageSpeed            — Google PSI v5 (key=GOOGLE_PAGESPEED_API_KEY)
  • Mobile               — Playwright 375×812 viewport
  • Broken links         — Firecrawl crawl depth 2 (cap 30 links)
  • Contact form         — HTML <form> with email/text/textarea fields
  • Social links         — instagram/facebook/linkedin/twitter/tiktok/yt
  • Copyright year       — regex scan of body text
  • Google Maps embed    — iframe src match

Score formula (max 100):
  SSL valid:        +20
  PageSpeed > 70:   +20
  Mobile ok:        +20
  No broken links:  +15
  Contact form:     +10
  Social links:     +10
  Copyright current: +5
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import socket
import ssl as _ssl
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

PROBE_TIMEOUT = 15
SOCIAL_HOSTS = ("instagram.com", "facebook.com", "linkedin.com", "twitter.com",
                "x.com", "tiktok.com", "youtube.com", "youtu.be")


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


# ─── SSL ────────────────────────────────────────────────────────────────────
async def check_ssl(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return {"valid": False, "issue": "invalid_url"}
    if parsed.scheme != "https":
        return {"valid": False, "issue": "no_https"}

    def _do() -> Dict[str, Any]:
        try:
            ctx = _ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=8) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
            not_after = cert.get("notAfter")
            try:
                exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                exp = exp.replace(tzinfo=timezone.utc)
            except Exception:
                exp = None
            days_left = int((exp - datetime.now(timezone.utc)).total_seconds() / 86400) if exp else None
            issue = None
            if days_left is not None and days_left < 14:
                issue = f"expires_in_{days_left}_days"
            return {"valid": True, "expires": exp.isoformat() if exp else None,
                    "days_left": days_left, "issuer": dict(x[0] for x in cert.get("issuer", [])).get("organizationName"),
                    "issue": issue}
        except _ssl.CertificateError as e:
            return {"valid": False, "issue": f"cert_error: {str(e)[:80]}"}
        except Exception as e:
            return {"valid": False, "issue": f"ssl_fail: {type(e).__name__}: {str(e)[:80]}"}

    return await asyncio.get_event_loop().run_in_executor(None, _do)


# ─── PageSpeed ──────────────────────────────────────────────────────────────
async def check_pagespeed(url: str) -> Dict[str, Any]:
    key = os.environ.get("GOOGLE_PAGESPEED_API_KEY", "").strip()
    if not key:
        return {"error": "pagespeed_key_missing", "score": None}
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as cli:
            r = await cli.get(
                "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                params={"url": url, "key": key, "strategy": "mobile",
                        "category": "performance"},
            )
        if not r.is_success:
            return {"error": f"psi_{r.status_code}", "score": None}
        data = r.json()
        cats = data.get("lighthouseResult", {}).get("categories", {})
        perf = cats.get("performance", {}).get("score")
        audits = data.get("lighthouseResult", {}).get("audits", {}) or {}
        lcp = audits.get("largest-contentful-paint", {}).get("displayValue")
        cls = audits.get("cumulative-layout-shift", {}).get("displayValue")
        return {
            "score": int((perf or 0) * 100) if perf is not None else None,
            "lcp": lcp, "cls": cls,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:80]}", "score": None}


# ─── Mobile (Playwright) ────────────────────────────────────────────────────
async def check_mobile(url: str) -> Dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return {"ok": None, "issues": ["playwright_unavailable"]}
    issues: List[str] = []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = await browser.new_context(viewport={"width": 375, "height": 812})
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(800)
                metrics = await page.evaluate("""
                    () => {
                      const docW = document.documentElement.scrollWidth;
                      const winW = window.innerWidth;
                      const overflow = docW > winW + 10;
                      const tinyText = Array.from(document.querySelectorAll('p,span,a,li,td'))
                        .slice(0, 200)
                        .filter(el => parseFloat(getComputedStyle(el).fontSize) < 12).length;
                      const smallTaps = Array.from(document.querySelectorAll('a,button'))
                        .slice(0, 200)
                        .filter(el => {
                          const r = el.getBoundingClientRect();
                          return (r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44));
                        }).length;
                      return {
                        doc_width: docW, win_width: winW,
                        has_horizontal_overflow: overflow,
                        tiny_text_count: tinyText,
                        small_tap_targets: smallTaps,
                        viewport_meta: !!document.querySelector('meta[name="viewport"]'),
                      };
                    }
                """)
            except Exception as e:
                issues.append(f"navigation_failed: {type(e).__name__}")
                metrics = {}
            await ctx.close()
            await browser.close()
        if metrics.get("has_horizontal_overflow"):
            issues.append("horizontal_overflow")
        if metrics.get("tiny_text_count", 0) > 5:
            issues.append(f"tiny_text_x{metrics['tiny_text_count']}")
        if metrics.get("small_tap_targets", 0) > 10:
            issues.append(f"small_tap_targets_x{metrics['small_tap_targets']}")
        if metrics.get("viewport_meta") is False:
            issues.append("missing_viewport_meta")
        return {"ok": len(issues) == 0, "issues": issues, "metrics": metrics}
    except Exception as e:
        return {"ok": None, "issues": [f"playwright_error: {type(e).__name__}"]}


# ─── Broken links (Firecrawl) ───────────────────────────────────────────────
async def check_broken_links(url: str) -> Dict[str, Any]:
    """Fetch homepage HTML, extract <a href>, HEAD-probe up to 30 internal+external links."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT, follow_redirects=True) as cli:
            r = await cli.get(url)
            html = r.text if r.is_success else ""
        if not html:
            return {"broken": [], "count": 0, "checked": 0,
                    "error": f"homepage_{r.status_code}" if not r.is_success else "empty_body"}
        hrefs = re.findall(r'href=[\'"]([^\'"]+)[\'"]', html, flags=re.I)
        # Resolve & filter
        seen, full = set(), []
        for h in hrefs:
            if h.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            absu = urljoin(url + "/", h)
            if absu in seen:
                continue
            seen.add(absu)
            full.append(absu)
            if len(full) >= 30:
                break
        broken: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as cli:
            async def _probe(link: str):
                try:
                    pr = await cli.head(link)
                    if pr.status_code in (405, 501):
                        pr = await cli.get(link)
                    if pr.status_code >= 400:
                        broken.append({"url": link, "status": pr.status_code})
                except Exception as e:
                    broken.append({"url": link, "error": type(e).__name__})
            await asyncio.gather(*[_probe(link) for link in full], return_exceptions=True)
        return {"broken": broken[:20], "count": len(broken), "checked": len(full)}
    except Exception as e:
        return {"broken": [], "count": 0, "checked": 0,
                "error": f"{type(e).__name__}: {str(e)[:80]}"}


# ─── HTML probes (one fetch shared across 4 checks) ─────────────────────────
async def _fetch_html(url: str) -> str:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0 (AUREM Audit)"}) as cli:
            r = await cli.get(url)
            return r.text if r.is_success else ""
    except Exception:
        return ""


def _parse_html_probes(html: str) -> Dict[str, Any]:
    if not html:
        return {"contact_form": False, "social_links": {"found": [], "missing": list(SOCIAL_HOSTS)},
                "copyright_year": None, "google_maps": False}
    h = html.lower()

    contact_form = False
    for m in re.finditer(r"<form\b[^>]*>(.*?)</form>", html, flags=re.I | re.S):
        block = m.group(1).lower()
        has_email = "type=\"email\"" in block or "type='email'" in block or "name=\"email\"" in block
        has_text = "<input" in block or "<textarea" in block
        if has_email and has_text:
            contact_form = True
            break
    if not contact_form and ('action="' in h or "action='" in h) and ("contact" in h or "mailto:" in h):
        contact_form = True

    found = sorted({host for host in SOCIAL_HOSTS if host in h})
    missing = [host for host in SOCIAL_HOSTS if host not in found]

    years = [int(y) for y in re.findall(r"©\s*(\d{4})", html)] \
        + [int(y) for y in re.findall(r"&copy;\s*(\d{4})", html, flags=re.I)] \
        + [int(y) for y in re.findall(r"copyright[^0-9]{0,12}(\d{4})", html, flags=re.I)]
    copyright_year = max(years) if years else None

    google_maps = bool(re.search(r"google\.com/maps|maps\.google\.com|embed/v1/place|/maps/embed",
                                  html, flags=re.I))
    return {
        "contact_form": contact_form,
        "social_links": {"found": found, "missing": missing},
        "copyright_year": copyright_year,
        "google_maps": google_maps,
    }


# ─── Score ──────────────────────────────────────────────────────────────────
def _score(parts: Dict[str, Any]) -> Dict[str, Any]:
    breakdown: Dict[str, int] = {}
    total = 0
    if (parts.get("ssl") or {}).get("valid"):
        breakdown["ssl"] = 20
        total += 20
    else:
        breakdown["ssl"] = 0
    ps = (parts.get("pagespeed") or {}).get("score")
    if ps is not None and ps >= 70:
        breakdown["pagespeed"] = 20
        total += 20
    elif ps is not None and ps >= 50:
        breakdown["pagespeed"] = 10
        total += 10
    else:
        breakdown["pagespeed"] = 0
    if (parts.get("mobile") or {}).get("ok") is True:
        breakdown["mobile"] = 20
        total += 20
    elif (parts.get("mobile") or {}).get("ok") is False:
        breakdown["mobile"] = 5
        total += 5
    else:
        breakdown["mobile"] = 0
    bl = (parts.get("broken_links") or {}).get("count", 0)
    if bl == 0:
        breakdown["broken_links"] = 15
        total += 15
    elif bl <= 3:
        breakdown["broken_links"] = 7
        total += 7
    else:
        breakdown["broken_links"] = 0
    if parts.get("contact_form"):
        breakdown["contact_form"] = 10
        total += 10
    sl = (parts.get("social_links") or {}).get("found") or []
    if len(sl) >= 2:
        breakdown["social_links"] = 10
        total += 10
    elif len(sl) >= 1:
        breakdown["social_links"] = 5
        total += 5
    cy = parts.get("copyright_year")
    cur_year = datetime.now(timezone.utc).year
    if cy is not None and cy >= cur_year - 1:
        breakdown["copyright_year"] = 5
        total += 5
    return {"overall": total, "breakdown": breakdown}


def _build_issues(parts: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    ssl = parts.get("ssl") or {}
    if not ssl.get("valid"):
        out.append({"kind": "ssl", "severity": "high",
                    "title": "SSL certificate problem",
                    "detail": ssl.get("issue") or "invalid_or_missing"})
    elif ssl.get("issue"):
        out.append({"kind": "ssl", "severity": "medium",
                    "title": "SSL expiring soon", "detail": ssl["issue"]})
    ps = parts.get("pagespeed") or {}
    if ps.get("score") is not None and ps["score"] < 50:
        out.append({"kind": "speed", "severity": "high",
                    "title": "Slow page load (mobile)",
                    "detail": f"PSI {ps['score']}/100 · LCP {ps.get('lcp','?')}"})
    mob = parts.get("mobile") or {}
    if mob.get("ok") is False:
        out.append({"kind": "mobile", "severity": "high",
                    "title": "Mobile responsiveness issues",
                    "detail": ", ".join(mob.get("issues") or [])[:140]})
    bl = parts.get("broken_links") or {}
    if bl.get("count", 0) > 0:
        out.append({"kind": "broken_links", "severity": "medium",
                    "title": f"{bl['count']} broken link(s)",
                    "detail": ", ".join((b.get("url") or "")[:60]
                                         for b in (bl.get("broken") or [])[:3])})
    if parts.get("contact_form") is False:
        out.append({"kind": "contact_form", "severity": "medium",
                    "title": "No working contact form",
                    "detail": "Visitors can't reach you in one click."})
    sl = parts.get("social_links") or {}
    if not sl.get("found"):
        out.append({"kind": "social_links", "severity": "low",
                    "title": "No social media links found",
                    "detail": "Add Instagram / Facebook / LinkedIn for trust."})
    cy = parts.get("copyright_year")
    cur = datetime.now(timezone.utc).year
    if cy and cy < cur - 1:
        out.append({"kind": "copyright_year", "severity": "low",
                    "title": f"Stale copyright year ({cy})",
                    "detail": f"Update footer to {cur}."})
    if not parts.get("google_maps"):
        out.append({"kind": "google_maps", "severity": "low",
                    "title": "No Google Maps embed",
                    "detail": "Local SEO + trust signal missing."})
    return out


# ─── Public API ─────────────────────────────────────────────────────────────
async def real_audit(url: str) -> Dict[str, Any]:
    """Run the full audit. Returns a self-contained dict ready to persist."""
    started = datetime.now(timezone.utc)
    url = _normalize_url(url)
    if not url:
        return {"ok": False, "error": "invalid_url", "url": url}

    html_task = asyncio.create_task(_fetch_html(url))
    ssl_t = asyncio.create_task(check_ssl(url))
    ps_t = asyncio.create_task(check_pagespeed(url))
    mob_t = asyncio.create_task(check_mobile(url))
    bl_t = asyncio.create_task(check_broken_links(url))

    html = await html_task
    parts: Dict[str, Any] = {}
    parts["ssl"] = await ssl_t
    parts["pagespeed"] = await ps_t
    parts["mobile"] = await mob_t
    parts["broken_links"] = await bl_t
    parts.update(_parse_html_probes(html))

    score = _score(parts)
    issues = _build_issues(parts)
    overall = score["overall"]
    return {
        "ok": True,
        "url": url,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 2),
        "ssl": parts["ssl"],
        "pagespeed": parts["pagespeed"],
        "mobile": parts["mobile"],
        "broken_links": parts["broken_links"],
        "contact_form": parts["contact_form"],
        "social_links": parts["social_links"],
        "copyright_year": parts["copyright_year"],
        "google_maps": parts["google_maps"],
        "score_breakdown": score["breakdown"],
        "overall_score": overall,
        "issues": issues,
        "repair_recommended": overall < 60,
        "rebuild_recommended": overall < 35,
    }
