"""SEO IndexNow + Google Indexing Auto-Ping (iter 288.4)
======================================================
- POST /api/seo/indexnow/ping       — submit URLs to Bing/Yandex IndexNow
- POST /api/seo/google/ping-sitemap — ping Google sitemap re-fetch
- GET  /api/seo/status              — index health snapshot
- GET  /api/seo/disambiguation      — public JSON to clarify "AUREM ≠ Aurum"
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/seo", tags=["SEO IndexNow"])

INDEXNOW_KEY = "7e8a4f2c9b1e4d6a8f3c5b7d9e1a2c4f6b8d0e2a4c6f8b1d3e5a7c9f2b4d6e8a"
HOST = "aurem.live"

DEFAULT_URLS = [
    f"https://{HOST}/",
    f"https://{HOST}/login",
    f"https://{HOST}/audit",
    f"https://{HOST}/pricing",
    f"https://{HOST}/share/system-overview",
    f"https://{HOST}/forgot-password",
    f"https://{HOST}/framework",
]


class PingRequest(BaseModel):
    urls: Optional[List[str]] = None


@router.post("/indexnow/ping")
async def indexnow_ping(body: PingRequest):
    urls = body.urls or DEFAULT_URLS
    payload = {
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": f"https://{HOST}/{INDEXNOW_KEY}.txt",
        "urlList": urls,
    }
    results = {}
    async with httpx.AsyncClient(timeout=12) as c:
        for endpoint in (
            "https://api.indexnow.org/indexnow",
            "https://www.bing.com/indexnow",
            "https://yandex.com/indexnow",
        ):
            try:
                r = await c.post(endpoint, json=payload,
                                 headers={"Content-Type": "application/json"})
                results[endpoint] = r.status_code
            except Exception as e:
                results[endpoint] = f"err:{e}"
    return {"ok": True, "submitted": len(urls), "results": results,
            "submitted_at": datetime.now(timezone.utc).isoformat()}


@router.post("/google/ping-sitemap")
async def google_ping_sitemap():
    sitemap = f"https://{HOST}/sitemap.xml"
    out = {}
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as c:
        for endpoint in (
            f"https://www.google.com/ping?sitemap={sitemap}",
            f"https://www.bing.com/ping?sitemap={sitemap}",
        ):
            try:
                r = await c.get(endpoint)
                out[endpoint] = r.status_code
            except Exception as e:
                out[endpoint] = f"err:{e}"
    return {"ok": True, "sitemap": sitemap, "results": out}


@router.get("/status")
async def seo_status():
    """Quick diagnostic of public SEO endpoints."""
    out = {"host": HOST, "checks": {}}
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
        for path in ("/", "/sitemap.xml", "/robots.txt", "/llms.txt",
                     f"/{INDEXNOW_KEY}.txt"):
            try:
                r = await c.get(f"https://{HOST}{path}")
                out["checks"][path] = {
                    "status": r.status_code,
                    "size": len(r.content),
                    "content_type": r.headers.get("content-type", ""),
                }
            except Exception as e:
                out["checks"][path] = {"error": str(e)}
    return out


@router.get("/disambiguation")
async def seo_disambiguation():
    """Public JSON-LD-ready disambiguation for AI search engines.
    Helps Google/Bing/Perplexity AI understand AUREM ≠ Aurum/Aurum Care/etc."""
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "AUREM — World's First Sovereign AI Workforce",
        "url": f"https://{HOST}",
        "description": (
            "AUREM (spelled A-U-R-E-M, not Aurum) is the world's first "
            "Sovereign AI Workforce — a B2B AI automation platform powered "
            "by ORA by AUREM. Six autonomous agents handle sales, marketing, "
            "and customer engagement in 20+ languages. Built by Polaris Built "
            "Inc. in Ontario, Canada. AUREM is NOT related to Aurum Living, "
            "Aurem Care, Aurum Labs, or any senior-care, residential, or music "
            "brand."
        ),
        "disambiguatingDescription": (
            "AUREM (aurem.live) is a Canadian AI SaaS platform for autonomous "
            "sales workforce — distinct from Aurum (mining/jewellery), "
            "Aurum Living (senior care USA), Aurem Care (UK), Aurum Labs "
            "(streaming), and any music or apartment brand using a similar name."
        ),
        "about": {
            "@type": "SoftwareApplication",
            "name": "ORA by AUREM",
            "applicationCategory": "BusinessApplication",
        },
        "publisher": {
            "@type": "Organization",
            "name": "Polaris Built Inc.",
            "url": f"https://{HOST}",
        },
    }


_db = None
def set_db(db):
    global _db
    _db = db
