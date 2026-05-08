"""
iter 282al-22 — Scrapling client (single source of truth)
==========================================================
Wraps Scrapling's Async fetchers behind a small async API. Falls back
gracefully to plain httpx when Scrapling isn't installed (so cold-deploy
boots even before `pip install scrapling[fetchers]` finishes), and to
StealthySession when AsyncFetcher trips Cloudflare.

Public API (everything async, never raises)
-------------------------------------------
    scrapling_fetch(url, use_stealth=False, timeout=30000,
                    css_selector=None)               -> dict
    scrapling_extract_contacts(url, html=None)        -> dict
    scrapling_find_mentions(business_name, website_url,
                            max_pages=10)             -> list[dict]
    scrapling_health_check()                          -> dict
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Optional Scrapling import ─────────────────────────────────────
_SCRAPLING_OK = True
try:
    from scrapling.fetchers import AsyncFetcher  # type: ignore  # noqa: F401
except Exception:  # ImportError, browser missing, etc.
    _SCRAPLING_OK = False

# StealthySession is even more optional — needs Playwright + Chrome
_STEALTH_OK = True
try:
    from scrapling.fetchers import (  # type: ignore  # noqa: F401
        AsyncStealthySession,
    )
except Exception:
    _STEALTH_OK = False


# ─── Cached singleton stealthy session ─────────────────────────────
_stealthy_session = None
_session_lock = asyncio.Lock()


async def _get_stealthy_session():
    """Return cached `AsyncStealthySession` (creates one on first use)."""
    global _stealthy_session
    if not _STEALTH_OK:
        return None
    async with _session_lock:
        if _stealthy_session is None:
            try:
                from scrapling.fetchers import AsyncStealthySession  # type: ignore
                _stealthy_session = AsyncStealthySession(
                    headless=True, max_pages=3, solve_cloudflare=True,
                )
                logger.info("[scrapling] StealthySession created")
            except Exception as e:
                logger.warning(f"[scrapling] StealthySession failed: {e}")
                _stealthy_session = False  # negative cache (don't retry)
    return _stealthy_session if _stealthy_session is not False else None


# ─── httpx fallback (works without Scrapling) ───────────────────────
async def _httpx_fallback(url: str, timeout_ms: int) -> Dict[str, Any]:
    """Last-resort plain-HTTPS fetch when Scrapling isn't available."""
    try:
        import httpx
        async with httpx.AsyncClient(
            timeout=timeout_ms / 1000.0,
            follow_redirects=True,
            headers={
                "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/124.0 Safari/537.36"),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-CA,en;q=0.9",
            },
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return {
                "status":          "success",
                "content":         text[:8000],
                "html":            html[:50000],
                "url":             url,
                "fetcher":         "httpx_fallback",
                "selector_result": None,
                "error":           None,
            }
    except Exception as e:
        return {
            "status": "failed", "content": "", "html": "",
            "url": url, "fetcher": None, "selector_result": None,
            "error": str(e),
        }


# ─── Core fetch ─────────────────────────────────────────────────────
async def scrapling_fetch(
    url: str,
    use_stealth: bool = False,
    timeout: int = 30000,
    css_selector: Optional[str] = None,
) -> Dict[str, Any]:
    """Always returns a dict; never raises."""
    result: Dict[str, Any] = {
        "status":          "failed",
        "content":         "",
        "html":            "",
        "url":             url,
        "fetcher":         None,
        "selector_result": None,
        "error":           None,
    }

    # 1. AsyncFetcher
    if not use_stealth and _SCRAPLING_OK:
        try:
            from scrapling.fetchers import AsyncFetcher  # type: ignore
            page = await AsyncFetcher.async_fetch(
                url, stealthy_headers=True, timeout=timeout,
            )
            result["status"] = "success"
            result["content"] = page.get_all_text()[:8000]
            result["html"] = str(page.html)[:50000]
            result["fetcher"] = "AsyncFetcher"
            if css_selector:
                try:
                    result["selector_result"] = [
                        e.text for e in page.css(css_selector)
                    ]
                except Exception:
                    pass
            return result
        except Exception as e:
            logger.debug(f"[scrapling] AsyncFetcher failed for {url}: {e}")

    # 2. AsyncStealthySession
    if _STEALTH_OK:
        try:
            session = await _get_stealthy_session()
            if session is not None:
                page = await session.async_fetch(
                    url, headless=True, network_idle=True, timeout=timeout,
                )
                result["status"] = "success"
                result["content"] = page.get_all_text()[:8000]
                result["html"] = str(page.html)[:50000]
                result["fetcher"] = "AsyncStealthySession"
                if css_selector:
                    try:
                        result["selector_result"] = [
                            e.text for e in page.css(css_selector)
                        ]
                    except Exception:
                        pass
                return result
        except Exception as e:
            logger.debug(f"[scrapling] StealthySession failed for {url}: {e}")
            result["error"] = str(e)

    # 3. httpx fallback
    fb = await _httpx_fallback(url, timeout)
    if fb["status"] == "success":
        return fb
    result["error"] = result["error"] or fb["error"]
    return result


# ─── Contact extraction ─────────────────────────────────────────────
_PHONE_RE = re.compile(
    r"[\+]?[\(]?[0-9]{3}[\)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4}",
)
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)


async def scrapling_extract_contacts(
    url: str, html: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract phone / email / address / services / business_name from HTML."""
    out = {
        "phone": None, "email": None, "address": None,
        "services": [], "business_name": None,
    }
    if not html:
        fr = await scrapling_fetch(url)
        if fr.get("status") != "success":
            return out
        html = fr.get("html") or ""
    if not html:
        return out

    # Phone — first regex match anywhere on the page
    pm = _PHONE_RE.search(html)
    if pm:
        out["phone"] = pm.group().strip()
    # Email — prefer mailto: links, else first regex hit
    mailto = re.search(
        r'href=[\'"]mailto:([^\'"]+)[\'"]', html, re.IGNORECASE,
    )
    if mailto:
        out["email"] = mailto.group(1).strip().split("?")[0]
    else:
        em = _EMAIL_RE.search(html)
        if em:
            out["email"] = em.group().strip()

    # Business name — first <h1>
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if h1:
        biz = re.sub(r"<[^>]+>", "", h1.group(1)).strip()
        out["business_name"] = biz[:100] if biz else None

    # Services — list-item words near 'service' keyword
    service_blocks = re.findall(
        r"(?:services?|what\s+we\s+do)\s*[:<][\s\S]{0,1500}?</",
        html, re.IGNORECASE,
    )
    if service_blocks:
        chunk = service_blocks[0][:2000]
        services = [
            re.sub(r"<[^>]+>", "", li).strip()
            for li in re.findall(r"<li[^>]*>(.*?)</li>", chunk,
                                  re.IGNORECASE | re.DOTALL)
        ]
        services = [s for s in services if 4 < len(s) < 100]
        out["services"] = services[:8]

    # Address — first <address> tag, else itemprop=address
    addr = re.search(r"<address[^>]*>(.*?)</address>",
                      html, re.IGNORECASE | re.DOTALL)
    if not addr:
        addr = re.search(
            r'itemprop=[\'"]address[\'"][^>]*>([^<]{5,200})',
            html, re.IGNORECASE,
        )
    if addr:
        atxt = re.sub(r"<[^>]+>", " ", addr.group(1)).strip()
        atxt = re.sub(r"\s+", " ", atxt)
        out["address"] = atxt[:200] if atxt else None
    return out


# ─── Mentions search ────────────────────────────────────────────────
async def scrapling_find_mentions(
    business_name: str, website_url: str, max_pages: int = 10,
) -> List[Dict[str, Any]]:
    """DDG-html search for `"<biz>"`; returns up to `max_pages` external hits."""
    if not business_name or not website_url:
        return []
    domain = re.sub(r"^https?://", "", website_url).split("/")[0].lower()
    query = '"' + business_name + '"'
    search_url = (
        "https://html.duckduckgo.com/html/?q="
        + re.sub(r"\s+", "+", query)
    )
    fr = await scrapling_fetch(search_url, use_stealth=False, timeout=20000)
    if fr.get("status") != "success":
        return []
    html = fr.get("html") or ""

    mentions: List[Dict[str, Any]] = []
    # DDG-html result links live under `class="result__a"`
    for m in re.finditer(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html, re.IGNORECASE | re.DOTALL,
    ):
        link, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        ldom = re.sub(r"^https?://", "", link).split("/")[0].lower()
        if not ldom or ldom == domain:
            continue
        mentions.append({
            "url":     link,
            "domain":  ldom,
            "snippet": title[:200],
            "has_link": False,
        })
        if len(mentions) >= max_pages:
            break
    return mentions


# ─── Health check ───────────────────────────────────────────────────
async def scrapling_health_check() -> Dict[str, Any]:
    try:
        result = await scrapling_fetch(
            "https://example.com", use_stealth=False, timeout=10000,
        )
        if result.get("status") == "success" and len(result.get("content") or "") > 50:
            return {
                "ok":      True,
                "status":  "green",
                "fetcher": result.get("fetcher"),
                "scrapling_installed": _SCRAPLING_OK,
                "stealth_available":   _STEALTH_OK,
                "detail":  f"OK — {result.get('fetcher')} active",
            }
        return {
            "ok":      False,
            "status":  "yellow",
            "scrapling_installed": _SCRAPLING_OK,
            "stealth_available":   _STEALTH_OK,
            "detail":  "Scrapling reached host but response was empty",
        }
    except Exception as e:
        return {
            "ok":      False,
            "status":  "red",
            "scrapling_installed": _SCRAPLING_OK,
            "stealth_available":   _STEALTH_OK,
            "detail":  f"Scrapling error: {e}",
        }
