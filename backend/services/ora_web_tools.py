"""
ORA Web Tools — Tavily + Firecrawl + Brave wrapper
===================================================
Gives ORA (and the command center) real internet access.

Public surface:
    web_search(query, *, num=5, source="auto") → [{title, url, snippet}]
    news_search(query, *, num=5)               → [{title, url, snippet, date}]
    scrape_url(url)                             → {content, title, success}
    quick_answer(query)                         → str  (Tavily 'answer' field)

Silent on failures (returns empty list / string).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"


def _tavily_key() -> str:
    return os.environ.get("TAVILY_API_KEY", "").strip()


def _brave_key() -> str:
    return os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()


def _firecrawl_key() -> str:
    return os.environ.get("FIRECRAWL_API_KEY", "").strip()


async def _tavily_search(query: str, num: int = 5, topic: str = "general") -> List[Dict[str, Any]]:
    key = _tavily_key()
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                TAVILY_URL,
                json={
                    "api_key": key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": num,
                    "topic": topic,
                    "include_answer": True,
                },
            )
        if not resp.is_success:
            return []
        data = resp.json()
        return [
            {
                "title": r.get("title", "")[:200],
                "url": r.get("url", ""),
                "snippet": (r.get("content") or "")[:400],
                "date": r.get("published_date", ""),
                "source": "tavily",
            }
            for r in data.get("results", [])[:num]
        ]
    except Exception as e:
        logger.debug(f"[ORA-Web] Tavily failed: {e}")
        return []


async def _brave_search(query: str, num: int = 5) -> List[Dict[str, Any]]:
    key = _brave_key()
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                BRAVE_URL,
                headers={"X-Subscription-Token": key, "Accept": "application/json"},
                params={"q": query, "count": num},
            )
        if not resp.is_success:
            return []
        data = resp.json()
        return [
            {
                "title": r.get("title", "")[:200],
                "url": r.get("url", ""),
                "snippet": (r.get("description") or "")[:400],
                "source": "brave",
            }
            for r in (data.get("web", {}) or {}).get("results", [])[:num]
        ]
    except Exception as e:
        logger.debug(f"[ORA-Web] Brave failed: {e}")
        return []


async def web_search(query: str, *, num: int = 5, source: str = "auto") -> List[Dict[str, Any]]:
    """
    Search the web. Tries Tavily first, falls back to Brave.
    source=one of {"auto","tavily","brave"}.
    """
    query = (query or "").strip()
    if not query:
        return []
    if source in ("auto", "tavily"):
        results = await _tavily_search(query, num=num)
        if results:
            return results
    if source in ("auto", "brave"):
        return await _brave_search(query, num=num)
    return []


async def news_search(query: str, *, num: int = 5) -> List[Dict[str, Any]]:
    """News-specific search via Tavily 'news' topic."""
    return await _tavily_search(query, num=num, topic="news")


async def quick_answer(query: str) -> str:
    """Return Tavily's synthesized 'answer' field — a one-paragraph summary."""
    key = _tavily_key()
    if not key:
        return ""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                TAVILY_URL,
                json={
                    "api_key": key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 3,
                    "include_answer": True,
                },
            )
        if not resp.is_success:
            return ""
        return (resp.json().get("answer") or "").strip()
    except Exception as e:
        logger.debug(f"[ORA-Web] quick_answer failed: {e}")
        return ""


async def scrape_url(url: str, timeout: int = 20) -> Dict[str, Any]:
    """Scrape a URL via Firecrawl. Returns {content, title, success}."""
    key = _firecrawl_key()
    if not (key and url):
        return {"success": False, "error": "not_configured_or_empty_url"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                FIRECRAWL_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            )
        if not resp.is_success:
            return {"success": False, "error": f"firecrawl_{resp.status_code}"}
        data = resp.json()
        if not data.get("success"):
            return {"success": False, "error": data.get("error", "firecrawl_failed")}
        payload = (data.get("data") or {})
        return {
            "success": True,
            "url": url,
            "title": (payload.get("metadata") or {}).get("title", ""),
            "content": (payload.get("markdown") or "")[:5000],
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def format_results_for_context(results: List[Dict[str, Any]], max_chars: int = 1600) -> str:
    """Turn a list of results into a compact markdown block for injection into ORA's context."""
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r.get('title','')}**")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:250]}")
        if r.get("url"):
            lines.append(f"   {r['url']}")
    out = "\n".join(lines)
    return out[:max_chars]
