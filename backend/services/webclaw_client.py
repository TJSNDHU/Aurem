"""
Webclaw client wrapper — iter 282ad (Scout upgrade).

Single source of truth for calling the webclaw SDK from AUREM. Gives
the rest of the codebase an opinionated, never-raises async facade:

    from services.webclaw_client import get_client, is_configured

    cli = get_client()                # returns None if no API key
    if cli:
        resp = await cli.scrape(url, formats=["markdown"])

Exposes:
    • get_client()         — cached AsyncWebclaw instance or None
    • is_configured()      — True if WEBCLAW_API_KEY is set
    • health_check()       — quick ping used by pillars map (returns dict)

WEBCLAW_API_KEY is OPTIONAL. If unset we operate in "local-first" skip mode
— every scan falls back to the existing httpx-based website_scraper. This
keeps preview environments from burning credits.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

try:
    from webclaw import AsyncWebclaw  # type: ignore
except Exception:  # pragma: no cover — SDK missing
    AsyncWebclaw = None  # type: ignore

logger = logging.getLogger(__name__)

_client: Optional["AsyncWebclaw"] = None


def is_configured() -> bool:
    return bool(os.environ.get("WEBCLAW_API_KEY", "").strip()) and AsyncWebclaw is not None


def get_client() -> Optional["AsyncWebclaw"]:
    global _client
    if _client is not None:
        return _client
    if not is_configured():
        return None
    key = os.environ["WEBCLAW_API_KEY"].strip()
    _client = AsyncWebclaw(api_key=key, timeout=15.0)
    return _client


async def health_check() -> dict:
    """Quick live probe — scrapes example.com in markdown. ~1-2s typical.

    Returns: {ok: bool, status: "green"|"red"|"skipped", detail: str}
    """
    if not is_configured():
        return {"ok": True, "status": "skipped", "detail": "WEBCLAW_API_KEY not set (local-first mode)"}
    cli = get_client()
    if cli is None:
        return {"ok": False, "status": "red", "detail": "AsyncWebclaw client unavailable"}
    try:
        resp = await cli.scrape("https://example.com", formats=["markdown"])
        body = getattr(resp, "markdown", None) or getattr(resp, "content", None) or ""
        if body and len(str(body)) > 50:
            return {"ok": True, "status": "green", "detail": f"scraped {len(str(body))} chars"}
        return {"ok": False, "status": "red", "detail": "empty scrape response"}
    except Exception as e:
        return {"ok": False, "status": "red", "detail": f"scrape error: {type(e).__name__}: {str(e)[:120]}"}


async def brand_injection_health() -> dict:
    """Cheap sanity probe for the pillars-map second chip.

    GREEN iff `services.brand_injection` imports cleanly and its pure helpers
    produce the expected CSS shape. No network, no DB.
    """
    try:
        from services import brand_injection as _bi
        css = _bi.inject_brand_css(None)
        if "--brand-primary" in css and "--brand-font" in css:
            return {"ok": True, "status": "green",
                    "detail": "brand_injection module loaded; default CSS shape valid"}
        return {"ok": False, "status": "red", "detail": "brand_injection CSS shape mismatch"}
    except Exception as e:
        return {"ok": False, "status": "red",
                "detail": f"brand_injection import failed: {type(e).__name__}: {str(e)[:120]}"}


async def log_usage(db, url: str, source: str, content: str,
                    brand_extracted: bool, contacts_extracted: bool) -> None:
    """Append one row to db.webclaw_usage. Never raises — fire-and-forget.

    Skipped for `legacy_httpx` fallback (no credits spent). Caller decides
    which rows matter by passing `source` explicitly.
    """
    if db is None or source == "legacy_httpx":
        return
    try:
        from services.brand_injection import build_usage_doc
        doc = build_usage_doc(url, source, content, brand_extracted, contacts_extracted)
        await db.webclaw_usage.insert_one(dict(doc))
    except Exception as e:
        logger.debug(f"[webclaw] usage log failed: {e}")


__all__ = ["get_client", "is_configured", "health_check",
           "brand_injection_health", "log_usage"]
