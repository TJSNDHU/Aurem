"""
AUREM Camofox Client — Anti-Detection Browser for Scout Agent
Calls the Camoufox REST API (port 9377) for scraping tasks
that require anti-detection (Google Maps, LinkedIn, blocked sites).
Falls back to simple httpx for public API calls.

Camoufox API flow: POST /tabs → POST /tabs/:id/navigate → GET /tabs/:id/snapshot → DELETE /tabs/:id
"""
import logging
import os
import httpx
import re

logger = logging.getLogger(__name__)

CAMOFOX_URL = os.environ.get("CAMOFOX_URL", "http://localhost:9377")
CAMOFOX_TIMEOUT = 40.0


async def is_camofox_available() -> bool:
    """Check if Camofox service is running."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{CAMOFOX_URL}/")
            data = r.json()
            return data.get("ok") and data.get("browserConnected")
    except Exception:
        return False


async def _create_tab(url: str = None) -> str:
    """Create a new browser tab with optional URL. Returns tab ID."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        payload = {"userId": "aurem", "sessionKey": "scout"}
        if url:
            payload["url"] = url
        r = await client.post(f"{CAMOFOX_URL}/tabs", json=payload)
        data = r.json()
        if data.get("error"):
            raise Exception(data["error"])
        return data.get("tabId") or data.get("id")


async def _navigate(tab_id: str, url: str, wait_ms: int = 3000):
    """Navigate a tab to URL."""
    async with httpx.AsyncClient(timeout=CAMOFOX_TIMEOUT) as client:
        await client.post(f"{CAMOFOX_URL}/tabs/{tab_id}/navigate", json={"url": url})
        await client.post(f"{CAMOFOX_URL}/tabs/{tab_id}/wait", json={"ms": wait_ms})


async def _snapshot(tab_id: str) -> dict:
    """Get page snapshot (text content + metadata)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{CAMOFOX_URL}/tabs/{tab_id}/snapshot")
        return r.json()


async def _get_links(tab_id: str) -> list:
    """Get all links on the page."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{CAMOFOX_URL}/tabs/{tab_id}/links")
        return r.json().get("links", [])


async def _scroll(tab_id: str, pixels: int = 500):
    """Scroll the page."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(f"{CAMOFOX_URL}/tabs/{tab_id}/scroll", json={"y": pixels})


async def _close_tab(tab_id: str):
    """Close a browser tab."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.delete(f"{CAMOFOX_URL}/tabs/{tab_id}")
    except Exception:
        pass


async def browse_url(url: str, scroll: bool = False, selector: str = None) -> dict:
    """Browse a URL with anti-detection. Fallback to simple fetch if Camofox is down."""
    # Try Camofox first
    try:
        available = await is_camofox_available()
        if available:
            tab_id = await _create_tab(url=url)
            if not tab_id:
                raise Exception("Failed to create tab")
            try:
                # Wait for page load
                import asyncio
                await asyncio.sleep(3)

                snap = await _snapshot(tab_id)
                links = await _get_links(tab_id)

                result = {
                    "success": True,
                    "url": url,
                    "title": snap.get("title", ""),
                    "text": snap.get("text", ""),
                    "links": links[:50],
                    "engine": "camofox",
                }
                logger.info(f"[Camofox] Browsed {url} ({len(result['text'])} chars)")
                return result
            finally:
                await _close_tab(tab_id)
    except Exception as e:
        logger.warning(f"[Camofox] Anti-detection browse failed: {e}")

    # Fallback: simple httpx fetch
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            text = resp.text
            clean = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.S)
            clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.S)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()
            return {
                "success": True,
                "url": str(resp.url),
                "text": clean[:10000],
                "title": "",
                "engine": "httpx_fallback",
            }
    except Exception as e2:
        return {"success": False, "url": url, "text": "", "engine": "failed", "error": str(e2)}


async def google_maps_leads(query: str, location: str) -> dict:
    """Extract leads from Google Maps via Camofox."""
    available = await is_camofox_available()
    if not available:
        return {"success": False, "leads": [], "error": "Camofox not available"}

    tab_id = None
    try:
        tab_id = await _create_tab()
        search_url = f"https://www.google.com/maps/search/{query}+{location}"
        await _navigate(tab_id, search_url, wait_ms=5000)

        # Scroll results for more listings
        for _ in range(5):
            await _scroll(tab_id, 400)
            import asyncio
            await asyncio.sleep(0.8)

        snap = await _snapshot(tab_id)
        text = snap.get("text", "")

        # Parse business listings from text
        leads = []
        lines = text.split("\n")
        current = {}
        for line in lines:
            line = line.strip()
            if not line:
                if current.get("name"):
                    leads.append(current)
                    current = {}
                continue
            if not current.get("name") and len(line) > 3 and len(line) < 80:
                current["name"] = line
            elif "·" in line:
                current["category"] = line

        if current.get("name"):
            leads.append(current)

        return {"success": True, "leads": leads[:20], "total": len(leads), "query": query, "location": location, "source": "google_maps"}
    except Exception as e:
        return {"success": False, "leads": [], "error": str(e)}
    finally:
        if tab_id:
            await _close_tab(tab_id)


async def linkedin_company(company_url: str) -> dict:
    """Scrape LinkedIn company page via Camofox."""
    result = await browse_url(company_url, scroll=True)
    if result.get("engine") == "camofox":
        result["source"] = "linkedin"
    return result


async def competitor_monitor(urls: list) -> list:
    """Monitor competitor websites for changes."""
    results = []
    for url in urls:
        data = await browse_url(url, scroll=True)
        results.append({
            "url": url,
            "title": data.get("title", ""),
            "text_length": len(data.get("text", "")),
            "engine": data.get("engine", "unknown"),
            "success": data.get("success", False),
        })
    return results
