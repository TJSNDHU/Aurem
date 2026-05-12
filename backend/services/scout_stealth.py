import asyncio
import logging
import random
from typing import Optional

from camoufox.async_api import AsyncCamoufox

logger = logging.getLogger(__name__)

_LOCALE_MAP = {
    "US": "en-US",
    "GB": "en-GB",
    "IN": "en-IN",
    "CA": "en-CA",
    "AU": "en-AU",
    "DE": "de-DE",
    "FR": "fr-FR",
    "ES": "es-ES",
    "IT": "it-IT",
    "BR": "pt-BR",
    "JP": "ja-JP",
    "CN": "zh-CN",
}

_DECOY_POOL = [
    "https://en.wikipedia.org/wiki/Special:Random",
    "https://news.ycombinator.com/",
    "https://www.reddit.com/",
    "https://www.bbc.com/news",
]


async def get_geo_from_ip(proxy_url: Optional[str]) -> dict:
    try:
        import httpx
        timeout = httpx.Timeout(5.0)
        proxies = {"http://": proxy_url, "https://": proxy_url} if proxy_url else None
        async with httpx.AsyncClient(proxies=proxies, timeout=timeout) as client:
            resp = await client.get("https://ipinfo.io/json")
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "ip": data.get("ip", ""),
                    "country": data.get("country", "US"),
                    "region": data.get("region", ""),
                    "city": data.get("city", ""),
                    "timezone": data.get("timezone", "America/New_York"),
                    "lat": data.get("loc", ",").split(",")[0],
                    "lng": data.get("loc", ",").split(",")[1] if "," in data.get("loc", "") else "",
                }
    except Exception as e:
        logger.debug(f"[scout_stealth] get_geo_from_ip failed: {e}")
    return {"timezone": "America/New_York", "country": "US"}


async def launch_stealth_browser(
    proxy: Optional[dict] = None,
    geoip: bool = True,
) -> tuple:
    proxy_url = None
    if proxy and proxy.get("server"):
        server = proxy["server"]
        username = proxy.get("username", "")
        password = proxy.get("password", "")
        if username and password:
            proto = "http://"
            if server.startswith("http://"):
                proto = "http://"
                server = server[7:]
            elif server.startswith("https://"):
                proto = "https://"
                server = server[8:]
            proxy_url = f"{proto}{username}:{password}@{server}"
        else:
            proxy_url = server

    geo = {"timezone": "America/New_York", "country": "US"}
    if geoip and proxy_url:
        geo = await get_geo_from_ip(proxy_url)

    tz = geo.get("timezone", "America/New_York")
    country = geo.get("country", "US")
    locale = _LOCALE_MAP.get(country, "en-US")

    config = {
        "humanize": True,
        "geoip": geoip and bool(proxy_url),
        "block_webrtc": True,
        "block_images": False,
        "locale": locale,
        "headless": True,  # iter 322ez — Emergent pod has no XServer
        "os": "windows",
    }
    if tz and tz != "America/New_York":
        # Camoufox accepts string timezones; only set when geoip gave us one.
        config["timezone"] = tz
    if proxy_url:
        config["proxy"] = {"server": proxy_url}

    # iter 322ez — use start() but DON'T await it twice (it returns the
    # browser directly; the camoufox instance must be kept for shutdown).
    camoufox = AsyncCamoufox(**config)
    browser = await camoufox.start()
    context = browser.contexts[0] if browser.contexts else await browser.new_context(
        viewport={"width": 1920, "height": 1080},
    )
    page = await context.new_page()

    return (camoufox, browser, context, page)


async def warmup_decoy(page, level: int = 2):
    if level < 1:
        return
    targets = random.sample(_DECOY_POOL, min(level, len(_DECOY_POOL)))
    for url in targets:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(random.uniform(0.8, 2.4))
            viewport_height = await page.evaluate("window.innerHeight")
            scroll_pct = random.uniform(0.3, 0.7)
            await page.evaluate(f"window.scrollTo(0, {int(viewport_height * scroll_pct)})")
            await asyncio.sleep(random.uniform(0.5, 1.2))
        except Exception as e:
            logger.debug(f"[scout_stealth] warmup_decoy {url} failed: {e}")


async def close_safely(camoufox, browser):
    try:
        if browser:
            await browser.close()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"[scout_stealth] browser.close error: {e}")
    try:
        if camoufox:
            await camoufox.stop()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"[scout_stealth] camoufox.stop error: {e}")