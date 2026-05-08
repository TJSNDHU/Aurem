"""
Apollo Organizations Enrichment (FREE tier) — iter 287.2

Apollo's free tier ONLY permits:
  • GET /v1/organizations/enrich?domain={domain}

This gives us RICH company data (industry, LinkedIn, phone, employee count,
technologies) for any domain Apollo has indexed. For small local SMBs
(Toronto dentists, home services), Apollo often has no record → returns
sparse data. That's fine — we fall back to website_scraper.

No credits spent on this endpoint; hard rate-limit is 60 req/min per key.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger("apollo_org_enrich")

APOLLO_BASE = "https://api.apollo.io/v1"
CACHE_COLLECTION = "apollo_org_cache"
CACHE_TTL_HOURS = 24 * 7  # 7 days — company data changes slowly


async def apollo_enrich_org(db: Any, domain: str) -> dict:
    """Enrich a company by its primary domain. Returns dict with
    available fields (may be mostly empty for SMBs)."""
    key = (os.environ.get("APOLLO_API_KEY") or "").strip()
    if not key or not domain:
        return {}

    # Cache check
    if db is not None:
        try:
            cached = await db[CACHE_COLLECTION].find_one(
                {"domain": domain}, {"_id": 0},
            )
            if cached:
                try:
                    cached_ts = datetime.fromisoformat(cached.get("ts_iso", ""))
                except Exception:
                    cached_ts = None
                if cached_ts and (datetime.now(timezone.utc) - cached_ts) < timedelta(hours=CACHE_TTL_HOURS):
                    return cached.get("data") or {}
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{APOLLO_BASE}/organizations/enrich",
                params={"domain": domain},
                headers={"X-Api-Key": key, "Cache-Control": "no-cache"},
            )
        if r.status_code != 200:
            logger.info(f"[apollo_org_enrich] {domain}: http {r.status_code}")
            return {}
        body = r.json() or {}
    except Exception as e:
        logger.warning(f"[apollo_org_enrich] error on {domain}: {e}")
        return {}

    org = body.get("organization") or {}
    out = {
        "name":          org.get("name"),
        "industry":      org.get("industry"),
        "employees":     org.get("estimated_num_employees"),
        "founded_year":  org.get("founded_year"),
        "phone":         org.get("sanitized_phone") or org.get("phone"),
        "linkedin_url":  org.get("linkedin_url"),
        "twitter_url":   org.get("twitter_url"),
        "facebook_url":  org.get("facebook_url"),
        "technologies":  (org.get("technology_names") or [])[:20],
        "keywords":      (org.get("keywords") or [])[:10],
        "website":       org.get("website_url"),
        "apollo_org_id": org.get("id"),
    }
    # Drop None values
    out = {k: v for k, v in out.items() if v}

    # Cache
    if db is not None and out:
        try:
            await db[CACHE_COLLECTION].update_one(
                {"domain": domain},
                {"$set": {
                    "domain": domain,
                    "data": out,
                    "ts_iso": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )
        except Exception:
            pass

    return out
