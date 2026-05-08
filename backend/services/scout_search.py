"""
AUREM Scout Search — Zero-Cost Web Search Service
===================================================

Replaces Perplexity ($$$) with a free search stack:
  Tier 1: DuckDuckGo (free, no API key, fast)
  Tier 2: SmartSearch fallback (Google → DDG)
  Tier 3: OpenRouter free model with context

Returns max 800 tokens of formatted search results.
Logs search source to Sentinel for monitoring.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None
_search_stats = {
    "total_searches": 0,
    "duckduckgo_hits": 0,
    "smartsearch_hits": 0,
    "openrouter_hits": 0,
    "failures": 0,
    "avg_response_ms": 0,
    "last_source": "none",
    "last_search_at": None,
}


def set_db(database):
    global _db
    _db = database


def get_search_stats() -> dict:
    return {**_search_stats}


class ScoutSearch:
    """Zero-cost web search with 3-tier fallback."""

    def __init__(self, db=None):
        self.db = db or _db

    async def search(self, query: str, max_results: int = 5) -> str:
        """
        Search the web for free. Returns formatted text (max ~800 tokens).
        Fallback: DuckDuckGo → SmartSearch → OpenRouter free model.
        """
        global _search_stats
        start = time.time()
        _search_stats["total_searches"] += 1

        # Tier 1: DuckDuckGo (free, no API key)
        try:
            results = await self._duckduckgo_search(query, max_results)
            if results:
                _search_stats["duckduckgo_hits"] += 1
                _search_stats["last_source"] = "duckduckgo"
                _update_timing(start)
                await self._log_search(query, "duckduckgo", len(results))
                return self._format(results)
        except Exception as e:
            logger.warning(f"[ScoutSearch] DuckDuckGo failed: {e}")

        # Tier 2: SmartSearch (Google → DDG)
        try:
            results = await self._smart_search(query, max_results)
            if results:
                _search_stats["smartsearch_hits"] += 1
                _search_stats["last_source"] = "smartsearch"
                _update_timing(start)
                await self._log_search(query, "smartsearch", len(results))
                return self._format(results)
        except Exception as e:
            logger.warning(f"[ScoutSearch] SmartSearch failed: {e}")

        # Tier 3: OpenRouter free model (answers from training data)
        try:
            result = await self._openrouter_answer(query)
            if result:
                _search_stats["openrouter_hits"] += 1
                _search_stats["last_source"] = "openrouter_free"
                _update_timing(start)
                await self._log_search(query, "openrouter_free", 1)
                return result
        except Exception as e:
            logger.warning(f"[ScoutSearch] OpenRouter fallback failed: {e}")

        _search_stats["failures"] += 1
        _search_stats["last_source"] = "none"
        _update_timing(start)
        return "Search unavailable — answering from knowledge"

    async def _duckduckgo_search(self, query: str, max_results: int) -> list:
        """Tier 1: DuckDuckGo — free, no API key needed."""
        import asyncio
        from ddgs import DDGS

        def _sync_search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        results = await asyncio.get_event_loop().run_in_executor(None, _sync_search)
        if not results:
            return []

        formatted = []
        for r in results:
            formatted.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "url": r.get("href", ""),
            })
        return formatted

    async def _smart_search(self, query: str, max_results: int) -> list:
        """Tier 2: SmartSearch (Google → DuckDuckGo fallback)."""
        from services.smart_search import SmartSearchService

        ss = SmartSearchService(db=self.db)
        results = await ss.search(query, limit=max_results)

        if not results or not isinstance(results, list):
            return []

        formatted = []
        for r in results:
            if isinstance(r, dict):
                formatted.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", r.get("description", "")),
                    "url": r.get("link", r.get("url", "")),
                })
        return formatted

    async def _openrouter_answer(self, query: str) -> str:
        """Tier 3: Use a free OpenRouter model to answer from training data."""
        from services.openrouter_client import call_ora_brain

        result = await call_ora_brain(
            system_prompt="Web search assistant. Answer concisely from training data. Unknown → say so. Max 300 words.",
            user_message=query,
            max_tokens=400,
            temperature=0.3,
        )
        content = result.get("content", "")
        if content:
            return f"[Source: AI Knowledge ({result.get('model', 'free')})]\n\n{content}"
        return ""

    def _format(self, results: list) -> str:
        """Format search results into max ~800 tokens text."""
        if not results:
            return "No results found."

        lines = []
        for i, r in enumerate(results[:5], 1):
            title = r.get("title", "Untitled")
            snippet = r.get("snippet", "")[:200]
            url = r.get("url", "")
            lines.append(f"[{i}] {title}")
            if snippet:
                lines.append(f"    {snippet}")
            if url:
                lines.append(f"    Source: {url}")
            lines.append("")

        text = "\n".join(lines)
        # Truncate to ~800 tokens (~3200 chars)
        if len(text) > 3200:
            text = text[:3200] + "\n... (truncated)"
        return text

    async def _log_search(self, query: str, source: str, result_count: int):
        """Log search to MongoDB for Sentinel monitoring."""
        db = self.db or _db
        if db is None:
            return
        try:
            await db.scout_search_log.insert_one({
                "query": query[:200],
                "source": source,
                "result_count": result_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass


def _update_timing(start: float):
    elapsed_ms = int((time.time() - start) * 1000)
    total = _search_stats["total_searches"]
    old_avg = _search_stats["avg_response_ms"]
    _search_stats["avg_response_ms"] = int(((old_avg * (total - 1)) + elapsed_ms) / total) if total > 0 else elapsed_ms
    _search_stats["last_search_at"] = datetime.now(timezone.utc).isoformat()


# Convenience function for direct import
async def scout_search(query: str, max_results: int = 5) -> str:
    """Quick search function. Usage: from services.scout_search import scout_search"""
    s = ScoutSearch()
    return await s.search(query, max_results)
