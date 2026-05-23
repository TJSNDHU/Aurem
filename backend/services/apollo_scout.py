"""
Apollo.io DIY Credit-Saver Proxy — iter 287.0

Strategy (per Founder brief):
  • Use Apollo FREE endpoints to get: first_name, last_name, title,
    LinkedIn URL, company domain — NEVER spend credits on email reveal
  • Locally guess email patterns + SMTP verify (see email_guesser.py)
  • Fallback to LinkedIn DM via Vanguard Swarm (out of scope this iter)

Behavior:
  • NO key → function returns [] (caller treats as no-op, gracefully)
  • Key set → people search on org domain (people/search endpoint — no
    credit charge for name/title/linkedin — credits only burn on "reveal email")
  • Caches responses in db.apollo_people_cache by (domain, title_hash) for 24h
    so repeated hunts don't hit Apollo twice
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("apollo_scout")

APOLLO_BASE = "https://api.apollo.io/v1"
CACHE_COLLECTION = "apollo_people_cache"
CACHE_TTL_HOURS = 24

# B2B decision-maker titles — owner, founder, manager class
DEFAULT_TITLE_KEYWORDS = [
    "owner", "founder", "co-founder",
    "ceo", "president",
    "general manager", "manager", "managing director",
    "operations manager", "office manager",
    "marketing manager", "director",
]


def _titles_hash(titles: list[str]) -> str:
    return hashlib.sha1(",".join(sorted(t.lower() for t in titles)).encode()).hexdigest()[:12]


def _domain_from_url(url: str) -> str:
    """Extract bare domain from a URL (http://www.foo.ca/x → foo.ca)."""
    if not url:
        return ""
    s = url.strip().lower()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    s = s.split("/", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    # strip port
    s = s.split(":", 1)[0]
    return s.strip()


async def apollo_people_search(
    db: Any,
    *,
    domain: str,
    title_keywords: Optional[list[str]] = None,
    limit: int = 5,
) -> list[dict]:
    """Find up to `limit` decision-maker people at `domain`.

    Returns list of dicts with: first_name, last_name, title, linkedin_url,
    organization_name, domain. NO email (that would cost a credit).

    Cached 24h per (domain, titles_hash).
    """
    key = (os.environ.get("APOLLO_API_KEY") or "").strip()
    if not key:
        return []
    domain = _domain_from_url(domain)
    if not domain:
        return []
    titles = title_keywords or DEFAULT_TITLE_KEYWORDS
    th = _titles_hash(titles)

    # Cache check
    if db is not None:
        try:
            cached = await db[CACHE_COLLECTION].find_one(
                {"domain": domain, "titles_hash": th}, {"_id": 0}
            )
            if cached:
                try:
                    cached_ts = datetime.fromisoformat(cached["ts_iso"])
                except Exception:
                    cached_ts = None
                if cached_ts and (datetime.now(timezone.utc) - cached_ts) < timedelta(hours=CACHE_TTL_HOURS):
                    logger.info(f"[apollo_scout] cache hit for {domain}")
                    return cached.get("people") or []
        except Exception:
            pass

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "X-Api-Key": key,
    }
    payload: dict[str, Any] = {
        "q_organization_domains": domain,
        "person_titles": titles,
        "page": 1,
        "per_page": max(1, min(limit, 25)),
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{APOLLO_BASE}/mixed_people/search",
                headers=headers,
                json=payload,
            )
        if r.status_code == 429:
            # iter 330d — credential health watcher.
            try:
                from services.api_key_health_watcher import record_api_failure
                await record_api_failure(
                    provider="apollo", status_code=429,
                    body=r.text[:300],
                    key_hint=(os.environ.get("APOLLO_API_KEY") or "")[-6:],
                )
            except Exception:
                pass
            logger.warning(f"[apollo_scout] rate-limited on {domain}")
            return []
        if r.status_code != 200:
            # iter 330d — surface 401/403/suspended/inaccessible to Telegram.
            try:
                from services.api_key_health_watcher import record_api_failure
                await record_api_failure(
                    provider="apollo", status_code=r.status_code,
                    body=r.text[:300],
                    key_hint=(os.environ.get("APOLLO_API_KEY") or "")[-6:],
                )
            except Exception:
                pass
            logger.warning(f"[apollo_scout] http {r.status_code} on {domain}: {r.text[:150]}")
            return []
        body = r.json() or {}
    except Exception as e:
        logger.warning(f"[apollo_scout] error on {domain}: {e}")
        return []

    people_raw = body.get("people") or []
    out: list[dict] = []
    for p in people_raw[:limit]:
        org = p.get("organization") or {}
        org_domain = (org.get("primary_domain") or "").strip().lower() or domain
        out.append({
            "first_name":   (p.get("first_name") or "").strip(),
            "last_name":    (p.get("last_name") or "").strip(),
            "title":        (p.get("title") or "").strip(),
            "linkedin_url": (p.get("linkedin_url") or "").strip(),
            "organization": (org.get("name") or "").strip(),
            "domain":       org_domain,
            "apollo_id":    p.get("id"),
        })

    # Cache
    if db is not None:
        try:
            await db[CACHE_COLLECTION].update_one(
                {"domain": domain, "titles_hash": th},
                {"$set": {
                    "domain": domain,
                    "titles_hash": th,
                    "people": out,
                    "ts_iso": datetime.now(timezone.utc).isoformat(),
                    "pagination": body.get("pagination", {}),
                }},
                upsert=True,
            )
        except Exception:
            pass

    logger.info(f"[apollo_scout] {domain}: {len(out)} people found")
    return out
