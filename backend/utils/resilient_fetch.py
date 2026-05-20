"""
Resilient HTTP fetch — handles SSL failures, broken certs, DNS issues, hostile servers.
Used by all AUREM scanners (Customer Scanner, ORA Repair, Live Scanner).

NEVER crashes. Returns a response or a synthetic error response.
SSL/DNS issues are captured as metadata for scanner findings.
"""
import httpx
import ssl
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@dataclass
class FetchResult:
    """Wrapper around httpx.Response with extra metadata about fetch issues."""
    response: Optional[httpx.Response] = None
    ssl_error: bool = False
    ssl_error_detail: str = ""
    dns_error: bool = False
    dns_error_detail: str = ""
    used_http_fallback: bool = False
    final_url: str = ""
    success: bool = False

    @property
    def status_code(self):
        return self.response.status_code if self.response else 0

    @property
    def text(self):
        return self.response.text if self.response else ""

    @property
    def content(self):
        return self.response.content if self.response else b""

    @property
    def headers(self):
        return self.response.headers if self.response else httpx.Headers()

    @property
    def url(self):
        if self.response:
            return self.response.url
        return self.final_url


def _is_ssl_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in ["ssl", "certificate", "handshake", "tls", "cert_required"])


def _is_dns_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in ["name or service not known", "nodename nor servname", "getaddrinfo", "dns", "errno -2", "errno -3", "no address associated"])


async def resilient_fetch(url: str, timeout: float = 30.0) -> FetchResult:
    """
    Fetch a URL with automatic fallbacks. NEVER raises — always returns a FetchResult.
    
    Fallback chain:
      1. HTTPS with default SSL
      2. HTTPS with verify=False (captures SSL errors as findings)
      3. HTTP fallback with browser User-Agent
      4. HTTP with www prefix
      5. Lowercase domain variant
    
    SSL/DNS errors are captured as metadata, not exceptions.
    """
    result = FetchResult(final_url=url)
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    last_error = None

    # Strategy 1: Normal HTTPS with full verification
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code < 500:
                result.response = resp
                result.success = True
                result.final_url = str(resp.url)
                return result
    except Exception as e:
        last_error = e
        if _is_ssl_error(e):
            result.ssl_error = True
            result.ssl_error_detail = str(e)
            logger.info(f"[ResilientFetch] SSL error on {url}: {e}")
        elif _is_dns_error(e):
            result.dns_error = True
            result.dns_error_detail = str(e)
            logger.info(f"[ResilientFetch] DNS error on {url}: {e}")

    # SECURITY NOTE: verify=False is INTENTIONAL here.
    # This is a SCANNER that audits untrusted external customer websites.
    # Customer sites may have expired/self-signed certs — we capture SSL issues as findings.
    # This does NOT apply to AUREM's own API calls (those always use full verification).
    if not result.dns_error:
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code < 500:
                    result.response = resp
                    result.success = True
                    result.ssl_error = True  # Mark that SSL was broken
                    if not result.ssl_error_detail:
                        result.ssl_error_detail = "SSL certificate validation skipped — site has certificate issues"
                    result.final_url = str(resp.url)
                    return result
        except Exception as e:
            last_error = e
            if _is_dns_error(e):
                result.dns_error = True
                result.dns_error_detail = str(e)

    # Strategy 3: HTTP fallback (strip https, use http)
    http_url = url.replace("https://", "http://")
    if http_url == url and not url.startswith("http://"):
        http_url = "http://" + url.lstrip("https://").lstrip("http://")
    
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(http_url, headers=headers)
            if resp.status_code < 500:
                result.response = resp
                result.success = True
                result.used_http_fallback = True
                result.final_url = str(resp.url)
                return result
    except Exception as e:
        last_error = e
        if _is_dns_error(e):
            result.dns_error = True
            result.dns_error_detail = str(e)

    # Strategy 4: HTTP with www prefix
    if "://www." not in http_url:
        www_url = http_url.replace("http://", "http://www.")
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(www_url, headers=headers)
                if resp.status_code < 500:
                    result.response = resp
                    result.success = True
                    result.used_http_fallback = True
                    result.final_url = str(resp.url)
                    return result
        except Exception as e:
            last_error = e

    # Strategy 5: Lowercase domain (AUREM.ca → aurem.live)
    # INTENTIONAL: scanning untrusted external websites — not our servers
    lower_url = url.lower()
    if lower_url != url:
        for attempt_url in [lower_url, lower_url.replace("https://", "http://")]:
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
                    resp = await client.get(attempt_url, headers=headers)
                    if resp.status_code < 500:
                        result.response = resp
                        result.success = True
                        result.used_http_fallback = "http://" in attempt_url
                        result.final_url = str(resp.url)
                        return result
            except Exception as e:
                last_error = e

    # Strategy 6: Carbonyl headless browser (JS-heavy sites). Only if CARBONYL_URL set.
    # Skipped silently when unconfigured — zero overhead.
    try:
        from services.carbonyl_fetcher import is_configured as _carb_cfg, render as _carb_render
        if _carb_cfg() and not result.success and not result.dns_error:
            logger.info(f"[ResilientFetch] invoking Carbonyl headless for {url}")
            cr = await _carb_render(url)
            if cr.get("ok"):
                # Wrap the rendered HTML in a minimal httpx-like response.
                class _CarbonylResp:
                    def __init__(self, html: str, final_url: str, title: str):
                        self.text = html
                        self.status_code = 200
                        self.url = final_url
                        self.headers = {"content-type": "text/html", "x-rendered-by": "carbonyl"}
                        self.title = title
                result.response = _CarbonylResp(
                    cr.get("html") or "", cr.get("final_url") or url, cr.get("title") or "",
                )
                result.success = True
                result.final_url = cr.get("final_url") or url
                result.used_http_fallback = False
                return result
    except Exception as e:
        logger.warning(f"[ResilientFetch] Carbonyl fallback crashed: {e}")

    # All strategies failed — return the result with error metadata
    if result.dns_error:
        logger.warning(f"[ResilientFetch] All strategies failed for {url}: DNS error")
    elif result.ssl_error:
        logger.warning(f"[ResilientFetch] All strategies failed for {url}: SSL error")
    else:
        logger.warning(f"[ResilientFetch] All strategies failed for {url}: {last_error}")

    return result
