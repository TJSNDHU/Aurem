"""
Social Presence Checker (iter 306) — Sherlock-style for Scout
==============================================================
Lightweight async social-profile detector. NO sherlock-project dep —
curated URL templates + httpx + concurrency cap.

Public:
  generate_usernames(business_name, city=None) -> List[str]
  await check_social_presence(business_name, city=None) -> Dict
      → {social_profiles: {platform: url|None}, social_score: int,
         usernames_tried: [], probes: int}
  classify_lead(has_website, social_score) -> "A" | "B" | "skip"

Stored on lead.campaign_leads:
  social_profiles, social_score, website_builder_eligible, social_audit_at
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Platform templates + detection signals ─────────────────────────────────
# Some platforms always 200 (instagram/yelp) — must inspect body for "not found"
# markers. Others reliably 404 the username.
PLATFORMS: Dict[str, Dict[str, Any]] = {
    "instagram": {
        "url": "https://www.instagram.com/{u}/",
        "method": "GET",
        "not_found_markers": ["Sorry, this page isn",
                               "Page Not Found",
                               '"/accounts/login/"'],
        "min_body": 5000,
    },
    "facebook": {
        "url": "https://www.facebook.com/{u}",
        "method": "GET",
        "not_found_markers": ["This page isn", "Page Not Found",
                               "content isn’t available"],
        "min_body": 5000,
    },
    "tiktok": {
        "url": "https://www.tiktok.com/@{u}",
        "method": "GET",
        "not_found_markers": ["Couldn't find this account",
                               "page-not-found", '"statusCode":10202'],
        "min_body": 4000,
    },
    "youtube": {
        "url": "https://www.youtube.com/@{u}",
        "method": "GET",
        "not_found_markers": ["This page isn", "404 Not Found",
                               "doesn't exist"],
        "min_body": 4000,
    },
    "yelp": {
        "url": "https://www.yelp.com/biz/{u}",
        "method": "GET",
        "not_found_markers": ["page not found", "We couldn",
                               "weren't able to find"],
        "min_body": 3000,
    },
    "linkedin_company": {
        "url": "https://www.linkedin.com/company/{u}/",
        "method": "GET",
        "not_found_markers": ["Page not found", "404",
                               "this page doesn"],
        "min_body": 2000,
    },
    "twitter": {
        "url": "https://x.com/{u}",
        "method": "GET",
        "not_found_markers": ["This account doesn", "page doesn",
                               "404 Not Found"],
        "min_body": 1500,
    },
}

CONCURRENCY = 5
INTER_BATCH_DELAY_S = 1.0
PER_REQUEST_TIMEOUT = 8
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
              "AUREM-Scout/1.0")


# ─── Username generator ─────────────────────────────────────────────────────
_APOSTROPHE_RE = re.compile(r"['\u2019\u02BC]")
_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")
STOP_TOKENS = {"the", "and", "ltd", "limited", "inc", "incorporated",
               "co", "corp", "corporation", "llc", "company", "&"}


def _tokens(name: str) -> List[str]:
    # Strip apostrophes BEFORE replacing punctuation so "Mike's" stays "Mikes"
    cleaned = _APOSTROPHE_RE.sub("", (name or "").lower())
    cleaned = _PUNCT_RE.sub(" ", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return [t for t in cleaned.split(" ")
            if t and t not in STOP_TOKENS and len(t) > 1]


def generate_usernames(business_name: str,
                        city: Optional[str] = None) -> List[str]:
    """Produce 3-5 plausible username variants. Order = priority."""
    toks = _tokens(business_name)
    if not toks:
        return []
    out: List[str] = []
    # 1. all joined no separator: "mikesplumbing"
    out.append("".join(toks))
    # 2. first two joined: "mikesplumbing" (same as 1 if 2 tokens) or core only
    if len(toks) >= 2:
        out.append("".join(toks[:2]))
    # 3. underscore separated: "mikes_plumbing"
    out.append("_".join(toks))
    # 4. dot separated: "mikes.plumbing"
    out.append(".".join(toks))
    # 5. with city suffix: "mikesplumbingbrampton"
    if city:
        city_clean = _tokens(city)
        if city_clean:
            out.append("".join(toks) + city_clean[0])
    # 6. drop possessive 's' on first token: "mike" + "plumbing"
    if toks[0].endswith("s") and len(toks[0]) > 3:
        out.append(toks[0][:-1] + ("".join(toks[1:]) if len(toks) > 1 else ""))
    # de-dup, strip too-short, cap to 5
    seen = set()
    final: List[str] = []
    for u in out:
        u = u.strip("._").lower()
        if 3 <= len(u) <= 30 and u not in seen:
            seen.add(u)
            final.append(u)
        if len(final) >= 5:
            break
    return final


# ─── Async checker ──────────────────────────────────────────────────────────
async def _probe_one(client, platform: str, url: str,
                     spec: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Return (platform, found_url_or_none)."""
    try:
        r = await client.request(spec.get("method", "GET"), url,
                                  timeout=PER_REQUEST_TIMEOUT,
                                  follow_redirects=True)
    except Exception as e:
        logger.debug(f"[social] {platform} {url} exception: {type(e).__name__}")
        return platform, None
    if r.status_code == 404:
        return platform, None
    if r.status_code >= 400:
        return platform, None
    body = r.text or ""
    if len(body) < int(spec.get("min_body", 1000)):
        return platform, None
    body_low = body.lower()
    for marker in spec.get("not_found_markers") or []:
        if marker.lower() in body_low:
            return platform, None
    # Resolved URL after redirects (e.g. fb canonicalises)
    return platform, str(r.url)


async def check_social_presence(business_name: str,
                                 city: Optional[str] = None) -> Dict[str, Any]:
    """Run all (platform × username) probes with concurrency cap."""
    usernames = generate_usernames(business_name, city)
    if not usernames:
        return {"social_profiles": {}, "social_score": 0,
                "usernames_tried": [], "probes": 0}

    sem = asyncio.Semaphore(CONCURRENCY)
    found: Dict[str, str] = {}
    probes = 0

    try:
        import httpx
    except Exception:
        logger.warning("[social] httpx missing — skipping")
        return {"social_profiles": {p: None for p in PLATFORMS},
                "social_score": 0, "usernames_tried": usernames, "probes": 0,
                "error": "httpx_unavailable"}

    headers = {"User-Agent": USER_AGENT,
               "Accept": "text/html,application/xhtml+xml",
               "Accept-Language": "en-US,en;q=0.9"}
    async with httpx.AsyncClient(headers=headers, http2=False) as client:
        # Walk usernames in priority order. Stop checking a platform once found.
        for u in usernames:
            tasks = []
            targets = [(p, spec) for p, spec in PLATFORMS.items() if p not in found]
            if not targets:
                break
            for p, spec in targets:
                url = spec["url"].format(u=u)

                async def _bound(p=p, spec=spec, url=url):
                    async with sem:
                        return await _probe_one(client, p, url, spec)

                tasks.append(asyncio.create_task(_bound()))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            probes += len(tasks)
            for r in results:
                if isinstance(r, tuple) and r[1]:
                    found[r[0]] = r[1]
            await asyncio.sleep(INTER_BATCH_DELAY_S)

    # Build full map (every platform key present, missing = None)
    profiles: Dict[str, Optional[str]] = {p: found.get(p) for p in PLATFORMS}
    return {
        "social_profiles": profiles,
        "social_score": sum(1 for v in profiles.values() if v),
        "usernames_tried": usernames,
        "probes": probes,
    }


def classify_lead(has_website: bool, social_score: int) -> str:
    """Priority:
      A  → social presence + no website  (hot Website Builder lead)
      B  → no social + no website        (cold lead)
      skip → has website (handled by repair pipeline instead)
    """
    if has_website:
        return "skip"
    return "A" if social_score >= 1 else "B"
