"""
Shortlink service — iter 282al.

SMS carriers filter messages with long /report/<uuid> URLs. Shorten to
`aurem.live/r/<slug>` before handing off to Twilio. Backed by Mongo with
a 30-day TTL. Click telemetry lives in `shortlink_clicks`.

Public surface:
  • create_shortlink(db, lead_id, target_url, expires_days=30)
  • get_or_create_shortlink(db, lead_id, target_url)
  • resolve_shortlink(db, slug)
  • shortlink_stats(db, lead_id)
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

SHORTLINK_RETENTION_SECONDS = 30 * 24 * 3600  # 30 days
CLICK_RETENTION_SECONDS     = 90 * 24 * 3600  # 90 days
_ALPHABET = string.ascii_lowercase + string.digits
SHORTLINK_BASE = "https://aurem.live"


def _gen_slug(n: int = 6) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


async def create_shortlink(db, lead_id: str, target_url: str,
                            expires_days: int = 30) -> dict:
    """Mint a new shortlink. Never raises."""
    if db is None or not target_url:
        return {"slug": "", "short_url": target_url}
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=expires_days)
    for _ in range(8):
        slug = _gen_slug()
        try:
            await db.shortlinks.insert_one({
                "slug":        slug,
                "target_url":  target_url,
                "lead_id":     lead_id,
                "clicks":      0,
                "created_at":  now,
                "expires_at":  expires_at,
                "ts":          now,   # for TTL index
            })
            return {"slug": slug, "short_url": f"{SHORTLINK_BASE}/r/{slug}"}
        except Exception as e:
            # Most likely a slug collision on unique index — retry.
            logger.debug(f"[shortlink] collision: {e}")
            continue
    return {"slug": "", "short_url": target_url}


async def get_or_create_shortlink(db, lead_id: str, target_url: str) -> str:
    """Return an existing non-expired shortlink for (lead_id, target_url)
    or mint a new one. Returns the fully-qualified short URL."""
    if db is None:
        return target_url
    try:
        doc = await db.shortlinks.find_one(
            {"lead_id": lead_id, "target_url": target_url,
             "expires_at": {"$gt": datetime.now(timezone.utc)}},
            projection={"_id": 0, "slug": 1},
        )
        if doc and doc.get("slug"):
            return f"{SHORTLINK_BASE}/r/{doc['slug']}"
    except Exception as e:
        logger.debug(f"[shortlink] lookup failed: {e}")
    minted = await create_shortlink(db, lead_id, target_url)
    return minted.get("short_url") or target_url


async def resolve_shortlink(db, slug: str) -> str:
    """Return target URL for slug or `aurem.live` fallback. Never raises."""
    if db is None or not slug:
        return SHORTLINK_BASE
    try:
        doc = await db.shortlinks.find_one({"slug": slug},
                                            projection={"_id": 0, "target_url": 1,
                                                         "expires_at": 1, "lead_id": 1})
        if not doc:
            return SHORTLINK_BASE
        exp = doc.get("expires_at")
        # Mongo strips tz on retrieval — re-attach UTC before comparing.
        if isinstance(exp, datetime):
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= datetime.now(timezone.utc):
                return SHORTLINK_BASE
        # Increment + log asynchronously (best-effort)
        try:
            await db.shortlinks.update_one({"slug": slug}, {"$inc": {"clicks": 1}})
            await db.shortlink_clicks.insert_one({
                "slug":    slug,
                "lead_id": doc.get("lead_id"),
                "ts":      datetime.now(timezone.utc),
            })
        except Exception:
            pass
        return doc.get("target_url") or SHORTLINK_BASE
    except Exception as e:
        logger.debug(f"[shortlink] resolve failed: {e}")
        return SHORTLINK_BASE


async def shortlink_stats(db, lead_id: str) -> dict:
    if db is None:
        return {"clicks": 0, "last_click": None, "short_url": None}
    try:
        sl = await db.shortlinks.find_one(
            {"lead_id": lead_id},
            sort=[("created_at", -1)],
            projection={"_id": 0, "slug": 1, "clicks": 1},
        )
        last_click = await db.shortlink_clicks.find_one(
            {"lead_id": lead_id},
            sort=[("ts", -1)],
            projection={"_id": 0, "ts": 1},
        )
        return {
            "clicks":     (sl or {}).get("clicks", 0),
            "last_click": (last_click or {}).get("ts"),
            "short_url":  f"{SHORTLINK_BASE}/r/{sl['slug']}" if sl and sl.get("slug") else None,
        }
    except Exception as e:
        logger.debug(f"[shortlink] stats failed: {e}")
        return {"clicks": 0, "last_click": None, "short_url": None}


async def ensure_shortlink_indexes(db) -> None:
    """TTL on shortlinks.expires_at (natural), unique on slug, TTL on clicks.ts."""
    if db is None:
        return
    try:
        await db.shortlinks.create_index(
            [("expires_at", 1)], expireAfterSeconds=0, name="expires_ttl",
        )
        await db.shortlinks.create_index([("slug", 1)], unique=True, name="slug_uniq")
        await db.shortlinks.create_index([("lead_id", 1)], name="lead_id")
        await db.shortlink_clicks.create_index(
            [("ts", 1)], expireAfterSeconds=CLICK_RETENTION_SECONDS,
            name="ts_ttl_90d",
        )
    except Exception as e:
        logger.debug(f"[shortlink] index skipped: {e}")


# Sync helpers for pytest
def create_shortlink_sync(db, lead_id: str, target_url: str) -> dict:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(create_shortlink(db, lead_id, target_url))).result()
    except RuntimeError:
        pass
    return asyncio.run(create_shortlink(db, lead_id, target_url))


def resolve_shortlink_sync(db, slug: str) -> str:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(resolve_shortlink(db, slug))).result()
    except RuntimeError:
        pass
    return asyncio.run(resolve_shortlink(db, slug))


__all__ = [
    "create_shortlink",
    "get_or_create_shortlink",
    "resolve_shortlink",
    "shortlink_stats",
    "ensure_shortlink_indexes",
    "create_shortlink_sync",
    "resolve_shortlink_sync",
    "SHORTLINK_BASE",
]
