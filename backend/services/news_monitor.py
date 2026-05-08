"""
News Auto-Monitor — Scheduled News Intelligence
=================================================
Every 2 hours, fetches news via DuckDuckGo for target queries.
If news matches lead criteria, auto-adds to campaign pipeline.

Topics monitored:
  - "website SEO problems Canada"
  - "small business website broken"
  - "looking for web developer Canada"
"""

import os
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)

# Search topics — each one is a DuckDuckGo news query
MONITOR_TOPICS = [
    "website SEO problems Canada",
    "small business website broken",
    "looking for web developer Canada",
    "website down Canada small business",
    "need help with website Canada",
]

# Keywords that signal a potential lead
LEAD_SIGNAL_KEYWORDS = [
    "help", "need", "looking for", "hiring", "broken", "down",
    "fix", "redesign", "developer", "agency", "seo", "slow",
    "not working", "issues", "problems", "terrible",
]


def _article_hash(url: str) -> str:
    """Deterministic hash for dedup."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _matches_lead_criteria(title: str, body: str) -> bool:
    """Check if a news article matches lead acquisition criteria."""
    text = (title + " " + body).lower()
    return sum(1 for kw in LEAD_SIGNAL_KEYWORDS if kw in text) >= 2


async def fetch_news(db) -> Dict:
    """
    Fetch news from DuckDuckGo for all monitor topics.
    Saves to news_alerts collection. Deduplicates by URL hash.
    Returns count of new + lead-matched articles.
    """
    from ddgs import DDGS
    import asyncio as _aio

    now = datetime.now(timezone.utc).isoformat()
    new_articles = 0
    lead_matches = 0

    for topic in MONITOR_TOPICS:
        try:
            ddgs = DDGS()
            results = []

            # Try news endpoint first, fall back to text search
            # NOTE: DDGS is SYNC/blocking — run in thread so it doesn't starve
            # the uvicorn event loop.
            try:
                results = await _aio.to_thread(
                    lambda: list(ddgs.news(topic, max_results=8, region="ca-en"))
                )
            except Exception as news_err:
                logger.info(f"[NewsMonitor] News API unavailable for '{topic}': {news_err}. Trying text search.")
                try:
                    await _aio.sleep(2)
                    ddgs2 = DDGS()
                    text_results = await _aio.to_thread(
                        lambda: list(ddgs2.text(f"{topic} news 2026", max_results=8, region="ca-en"))
                    )
                    for tr in text_results:
                        results.append({
                            "url": tr.get("href", ""),
                            "title": tr.get("title", ""),
                            "body": tr.get("body", ""),
                            "source": tr.get("href", "").split("/")[2] if "/" in tr.get("href", "") else "",
                            "date": now,
                        })
                except Exception as text_err:
                    logger.warning(f"[NewsMonitor] Both search methods failed for '{topic}': {text_err}")
                    continue

            for article in results:
                url = article.get("url", article.get("href", ""))
                if not url:
                    continue

                article_id = _article_hash(url)

                # Dedup check
                existing = await db.news_alerts.find_one({"article_id": article_id})
                if existing:
                    continue

                title = article.get("title", "")
                body = article.get("body", "")
                source = article.get("source", "")
                published = article.get("date", "")

                is_lead = _matches_lead_criteria(title, body)

                doc = {
                    "article_id": article_id,
                    "topic": topic,
                    "title": title,
                    "body": body[:1000],
                    "url": url,
                    "source": source,
                    "published": published,
                    "is_lead_match": is_lead,
                    "lead_created": False,
                    "fetched_at": now,
                }
                await db.news_alerts.insert_one(doc)
                new_articles += 1

                # Auto-add to lead pipeline if matches
                if is_lead:
                    lead_matches += 1
                    await _create_lead_from_news(db, doc)

            # Rate limit courtesy — wait between topics
            await _aio.sleep(3)

        except Exception as e:
            logger.warning(f"[NewsMonitor] Error fetching '{topic}': {e}")

    logger.info(f"[NewsMonitor] Fetched {new_articles} new articles, {lead_matches} lead matches")
    return {"new_articles": new_articles, "lead_matches": lead_matches, "timestamp": now}


async def _create_lead_from_news(db, article: Dict):
    """Mark a news article as a lead signal (NO insertion into campaign_leads).

    News articles are ARTICLES, not businesses — they have no real contact info
    (no email, no phone, no website of a buyer). Polluting `campaign_leads` with
    them breaks CRM counters and wastes Auto-Blast cycles.

    We keep the signal in `news_alerts` with `is_lead_match=True` so admins can
    review them in the News Monitor dashboard. If an admin wants to convert an
    article into an actual lead, that becomes a manual UI action (future work).
    """
    title = article.get("title", "")
    await db.news_alerts.update_one(
        {"article_id": article["article_id"]},
        {"$set": {
            "is_lead_match": True,
            "lead_created": False,  # we no longer auto-create a campaign_lead
            "signal_only": True,
            "signalled_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    logger.info(f"[NewsMonitor] Lead signal recorded (no CRM pollution): '{title[:60]}'")


async def get_recent_alerts(db, limit: int = 20) -> List[Dict]:
    """Get recent news alerts."""
    cursor = db.news_alerts.find(
        {}, {"_id": 0}
    ).sort("fetched_at", -1).limit(limit)
    return await cursor.to_list(limit)


async def get_lead_matches(db, limit: int = 20) -> List[Dict]:
    """Get news articles that matched lead criteria."""
    cursor = db.news_alerts.find(
        {"is_lead_match": True}, {"_id": 0}
    ).sort("fetched_at", -1).limit(limit)
    return await cursor.to_list(limit)
