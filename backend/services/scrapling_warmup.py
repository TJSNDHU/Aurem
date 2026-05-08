"""
iter 282al-23 — Scrapling Warmup
================================
Pre-fetches the top-100 most-frequently-scanned domains so subsequent
Scout / repair / outreach scans hit a warm Scrapling cache (~ms instead
of seconds). Runs once on backend startup (background task) and again
every 6 h via the aurem_scheduler.

Source of "top-100": existing `webclaw_usage` collection (URL log) plus
recent `campaign_leads` websites. Falls back gracefully if the
`webclaw_usage` collection doesn't exist.

Mongo collection used: `scrapling_warmup_log` (TTL 30d) — records each
warmup run for observability + the Pillars chip.

Public API
----------
    run_scrapling_warmup(db, max_domains=100,
                         concurrency=4)        -> dict
    get_top_domains(db, limit=100)             -> list[str]
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _domain_of(url: str) -> str:
    if not url:
        return ""
    u = url.strip()
    u = re.sub(r"^https?://", "", u, flags=re.IGNORECASE)
    return u.split("/")[0].lower().strip()


async def get_top_domains(db, limit: int = 100) -> List[str]:
    """Return the top-`limit` domains by scan frequency. Never raises."""
    counts: Counter = Counter()
    if db is None:
        return []
    # 1) webclaw_usage (most authoritative — historical scan log)
    try:
        rows = await db.webclaw_usage.find(
            {}, {"_id": 0, "url": 1},
        ).limit(20000).to_list(length=20000)
        for r in rows:
            d = _domain_of(r.get("url") or "")
            if d:
                counts[d] += 1
    except Exception as e:
        logger.debug(f"[warmup] webclaw_usage query: {e}")

    # 2) campaign_leads.website (most recent funnel)
    try:
        since = datetime.now(timezone.utc) - timedelta(days=30)
        rows = await db.campaign_leads.find(
            {"created_at": {"$gte": since},
             "website": {"$exists": True, "$nin": [None, ""]}},
            {"_id": 0, "website": 1},
        ).limit(5000).to_list(length=5000)
        for r in rows:
            d = _domain_of(r.get("website") or "")
            if d:
                counts[d] += 1
    except Exception as e:
        logger.debug(f"[warmup] campaign_leads query: {e}")

    return [d for d, _ in counts.most_common(limit)]


async def _warm_one(domain: str) -> Dict[str, Any]:
    """Fetch a single domain through scrapling_fetch. Always returns a dict."""
    from services.scrapling_client import scrapling_fetch
    url = f"https://{domain}"
    try:
        r = await scrapling_fetch(url, use_stealth=False, timeout=15000)
        return {
            "domain":  domain,
            "ok":      r.get("status") == "success",
            "fetcher": r.get("fetcher"),
            "bytes":   len(r.get("content") or ""),
        }
    except Exception as e:
        return {"domain": domain, "ok": False, "fetcher": None,
                "bytes": 0, "error": str(e)}


async def run_scrapling_warmup(
    db, max_domains: int = 100, concurrency: int = 4,
) -> Dict[str, Any]:
    """Warm the Scrapling cache for the top-`max_domains` scanned hosts."""
    started = datetime.now(timezone.utc)
    domains = await get_top_domains(db, limit=max_domains)
    if not domains:
        out = {"ok": False, "reason": "no_domains", "warmed": 0,
               "considered": 0, "ts": started}
        return out

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _bounded(d: str) -> Dict[str, Any]:
        async with sem:
            return await _warm_one(d)

    results = await asyncio.gather(*[_bounded(d) for d in domains],
                                    return_exceptions=False)

    warmed = sum(1 for r in results if r.get("ok"))
    fetcher_breakdown: Counter = Counter(r.get("fetcher") for r in results if r.get("ok"))
    finished = datetime.now(timezone.utc)

    summary = {
        "ok":          True,
        "warmed":      warmed,
        "considered":  len(domains),
        "fetcher_breakdown": dict(fetcher_breakdown),
        "duration_s":  round((finished - started).total_seconds(), 2),
        "ts":          finished,
    }
    if db is not None:
        try:
            await db.scrapling_warmup_log.insert_one(dict(summary))
        except Exception as e:
            logger.debug(f"[warmup] log persist: {e}")
    return summary


async def ensure_warmup_indexes(db) -> None:
    """TTL 30d on scrapling_warmup_log. Never raises."""
    if db is None:
        return
    try:
        await db.scrapling_warmup_log.create_index(
            [("ts", 1)], expireAfterSeconds=60 * 60 * 24 * 30,
            background=True, name="ttl_30d",
        )
    except Exception as e:
        logger.debug(f"[warmup] index ensure skipped: {e}")
