"""
Rendered HTML fetcher using Playwright.
Launches headless Chromium to get JS-rendered DOM for SPA sites.
Falls back to raw httpx if Playwright fails.
"""
import logging
import httpx

logger = logging.getLogger("aurem.rendered_fetch")

# Reusable browser instance (lazy init)
_browser = None
_playwright = None


async def _get_browser():
    global _browser, _playwright
    if _browser and _browser.is_connected():
        return _browser
    try:
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
        )
        logger.info("[RenderedFetch] Chromium browser launched")
        return _browser
    except Exception as e:
        logger.warning(f"[RenderedFetch] Failed to launch Chromium: {e}")
        return None


async def fetch_rendered_html(url: str, timeout_ms: int = 15000) -> tuple:
    """
    Fetch fully rendered HTML from a URL using headless Chromium.
    Returns (rendered_html, raw_headers_dict).
    Falls back to raw httpx if Playwright is unavailable.
    """
    browser = await _get_browser()
    if browser:
        page = None
        try:
            page = await browser.new_page()
            response = await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            headers = dict(response.headers) if response else {}
            rendered = await page.content()
            logger.info(f"[RenderedFetch] Rendered {url} — {len(rendered)} chars")
            return rendered, headers
        except Exception as e:
            logger.warning(f"[RenderedFetch] Playwright render failed for {url}: {e}")
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    # Fallback: resilient fetch (handles SSL failures, broken certs, DNS, etc.)
    logger.info(f"[RenderedFetch] Falling back to resilient fetch for {url}")
    try:
        from utils.resilient_fetch import resilient_fetch
        result = await resilient_fetch(url)
        if result.success and result.response:
            return result.text, dict(result.headers)
        else:
            logger.warning(f"[RenderedFetch] Resilient fetch failed for {url}: dns={result.dns_error} ssl={result.ssl_error}")
            return "", {}
    except Exception as e:
        logger.error(f"[RenderedFetch] Resilient fetch error for {url}: {e}")
        return "", {}
