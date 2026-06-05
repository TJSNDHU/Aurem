"""Tavily web search + URL content extraction skill.

The primary "search the internet" skill for ORA / CTO. Two modes:

  - `web_search`     → query  → ranked results with snippets + URLs
  - `fetch_url`      → URL    → cleaned article text + title + favicon
  - `web_search_and_summarize` → query → results + LLM-condensed answer
"""
from __future__ import annotations

import os
import logging
from typing import Any, Optional

import httpx

from .registry import skill

logger = logging.getLogger(__name__)

_TAVILY_BASE = "https://api.tavily.com"


def _key() -> str:
    return os.environ.get("TAVILY_API_KEY", "").strip()


def _require_key() -> str:
    k = _key()
    if not k:
        raise RuntimeError(
            "TAVILY_API_KEY not set. Add it to backend/.env to enable web search."
        )
    return k


@skill(
    name="web_search",
    description=(
        "Search the live internet via Tavily. Returns ranked results with "
        "title, URL, snippet, and a short relevance score. Use when the "
        "user asks anything time-sensitive, mentions news/2026 events, or "
        "explicitly says 'search' / 'google' / 'look up'."
    ),
    requires_keys=["TAVILY_API_KEY"],
)
async def web_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Live web search via Tavily API.

    Args:
        query: natural language search query.
        max_results: 1..20.
        search_depth: "basic" (cheap, fast) or "advanced" (deeper crawl).
        include_domains / exclude_domains: optional allow / block lists.
    """
    if not query or not query.strip():
        raise ValueError("query is required")
    api_key = _require_key()
    n = max(1, min(int(max_results), 20))
    depth = "advanced" if str(search_depth).lower() == "advanced" else "basic"

    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": query.strip(),
        "search_depth": depth,
        "max_results": n,
    }
    if include_domains:
        payload["include_domains"] = list(include_domains)
    if exclude_domains:
        payload["exclude_domains"] = list(exclude_domains)

    async with httpx.AsyncClient(timeout=15.0) as cli:
        r = await cli.post(f"{_TAVILY_BASE}/search", json=payload)
    if r.status_code >= 400:
        raise RuntimeError(f"tavily_http_{r.status_code}: {r.text[:200]}")
    data = r.json()
    results = []
    for res in (data.get("results") or [])[:n]:
        results.append({
            "title":   res.get("title") or "",
            "url":     res.get("url"),
            "snippet": (res.get("content") or "")[:600],
            "score":   res.get("score"),
            "source":  "tavily",
        })
    return {
        "query":   query,
        "depth":   depth,
        "count":   len(results),
        "answer":  data.get("answer"),    # Tavily's own one-liner summary, when available
        "results": results,
    }


@skill(
    name="fetch_url",
    description=(
        "Fetch and clean a single URL's content (text, title, meta) so the "
        "LLM can summarise it. Use whenever the user pastes a link or asks "
        "'what does this page say'. Strips ads, nav, scripts."
    ),
    requires_keys=["TAVILY_API_KEY"],
)
async def fetch_url(
    url: str,
    extract_depth: str = "basic",
) -> dict[str, Any]:
    """Extract clean content from a URL via Tavily Extract API."""
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("url must start with http:// or https://")
    api_key = _require_key()
    depth = "advanced" if str(extract_depth).lower() == "advanced" else "basic"

    payload = {
        "api_key": api_key,
        "urls":    [url],
        "extract_depth": depth,
    }
    async with httpx.AsyncClient(timeout=30.0) as cli:
        r = await cli.post(f"{_TAVILY_BASE}/extract", json=payload)
    if r.status_code >= 400:
        raise RuntimeError(f"tavily_extract_http_{r.status_code}: {r.text[:200]}")
    data = r.json()
    results = data.get("results") or []
    failed = data.get("failed_results") or []
    if not results and failed:
        raise RuntimeError(
            f"could_not_fetch: {failed[0].get('error', 'unknown')[:200]}"
        )
    if not results:
        raise RuntimeError("no_content_extracted")

    top = results[0]
    return {
        "url":        top.get("url") or url,
        "title":      "",   # extract API doesn't return title — caller can derive
        "content":    (top.get("raw_content") or top.get("content") or "")[:8000],
        "char_count": len((top.get("raw_content") or top.get("content") or "")),
        "depth":      depth,
        "source":     "tavily_extract",
    }


@skill(
    name="web_search_and_summarize",
    description=(
        "Convenience wrapper: do a web_search AND ask Tavily for its own "
        "one-line answer. Use when the user just wants a quick factual "
        "answer with citations (no manual snippet reading)."
    ),
    requires_keys=["TAVILY_API_KEY"],
)
async def web_search_and_summarize(
    query: str,
    max_results: int = 5,
) -> dict[str, Any]:
    out = await web_search(query=query, max_results=max_results, search_depth="advanced")
    return {
        "query":    query,
        "answer":   out.get("answer") or "(Tavily did not return a synthesized answer)",
        "citations": [
            {"title": r["title"], "url": r["url"]}
            for r in out.get("results", [])
        ],
    }
