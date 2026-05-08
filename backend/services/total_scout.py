"""
AUREM Total-Scout Engine (iter 322n — Sovereign Discovery)
==========================================================

Unified, multi-source business discovery dispatcher. Replaces the
3-source `google_places_leads()` (Yelp + Places + OSM) with a 6-source
parallel fan-out plus per-source attribution telemetry that powers the
admin Source-Stats dashboard.

Source ladder (all run **in parallel**)
---------------------------------------
  T1  Yelp Fusion API           — primary SMB pool, phone+rating
  T1  Google Places API (New)   — top-up for richer detail (website)
  T2  OSM Overpass              — free no-key fallback
  T2  YellowPages list-scrape   — Firecrawl-powered, multi-card per page
  T3  Tavily web search         — keyword-targeted directory hits
  T3  DuckDuckGo HTML scrape    — zero-cost web search

Returned leads are deduplicated on a normalised
``(business_name, phone OR website)`` key — survivors retain all
sources that contributed (`source_chain: [yelp_fusion, places, ...]`)
so the consensus engine downstream can score "Sovereign-Gold" leads.

The dispatcher records its run summary to ``scout_source_runs`` so
``GET /api/admin/scout/source-stats`` can render real attribution.

Public API
----------
- ``discover_leads_total_scout(query, location, *, limit, db) -> dict``
- ``google_places_leads(query, location, limit) -> dict``  (back-compat alias)
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)


# ─── Tunables ───────────────────────────────────────────────────────────
SOURCE_TIMEOUT_S = float(os.environ.get("TOTAL_SCOUT_SOURCE_TIMEOUT_S", "12.0"))
DEFAULT_LIMIT = 20

# Sources can be individually disabled via env (handy for outages /
# rate-limit cooldowns) without code changes.
ENABLED_SOURCES = {
    "yelp":         os.environ.get("SCOUT_DISABLE_YELP")        != "1",
    "google_places": os.environ.get("SCOUT_DISABLE_GOOGLE_PLACES") != "1",
    "osm":          os.environ.get("SCOUT_DISABLE_OSM")         != "1",
    "yellowpages":  os.environ.get("SCOUT_DISABLE_YELLOWPAGES") != "1",
    "tavily":       os.environ.get("SCOUT_DISABLE_TAVILY")      != "1",
    "duckduckgo":   os.environ.get("SCOUT_DISABLE_DUCKDUCKGO")  != "1",
    # Forensic Miner is an ECOMMERCE-niche discovery tool — it costs an
    # external Tomba.io call per domain. We gate it behind niche-keyword
    # detection so it skips local-trades queries (HVAC / plumber / etc.)
    # automatically. Force-enable with `enabled={"forensic": True}`.
    "forensic":     os.environ.get("SCOUT_DISABLE_FORENSIC")    != "1",
}

# Niche keywords that flip Forensic Miner ON (ecommerce / DTC retail).
# Local-trades queries (HVAC, plumber, electrician, roofer, lawyer, etc.)
# don't match any of these, so Forensic Miner stays dormant — no API
# burn for the wrong tool.
_FORENSIC_NICHE_KEYWORDS = {
    "beauty", "skincare", "cosmetics", "makeup", "skin care",
    "fashion", "clothing", "apparel", "boutique",
    "wellness", "supplement", "vitamin",
    "fitness", "workout", "gym wear",
    "snacks", "gourmet", "organic food",
    "gadget", "electronics", "smart home",
    "petcare", "pet food", "pet supplies",
    "shopify", "dtc", "ecommerce", "e-commerce", "online store",
}

PHONE_RE = re.compile(r"\+?1?\s*[\(\-]?(\d{3})[\)\-\s\.]*(\d{3})[\-\s\.]*(\d{4})")


def _looks_like_ecommerce_niche(query: str) -> bool:
    """Cheap keyword test — returns True if the query smells like an
    ecommerce niche search (Forensic Miner's sweet spot)."""
    q = (query or "").lower()
    return any(kw in q for kw in _FORENSIC_NICHE_KEYWORDS)


# ─── Sovereign-Gold tier tagging ───────────────────────────────────────
# Consensus signal: more independent sources confirming a lead = higher
# trust tier. The Council uses these tiers downstream to (a) auto-fire
# deeper enrichment on `gold` only, (b) prioritise `gold` in outreach.
TIER_GOLD_MIN_SOURCES = 3
TIER_SILVER_MIN_SOURCES = 2


def classify_tier(source_chain: List[str]) -> str:
    """Return ``gold``/``silver``/``bronze`` based on distinct-source count."""
    distinct = len({s for s in (source_chain or []) if s})
    if distinct >= TIER_GOLD_MIN_SOURCES:
        return "gold"
    if distinct >= TIER_SILVER_MIN_SOURCES:
        return "silver"
    return "bronze"


def is_sovereign_gold(lead: Dict[str, Any]) -> bool:
    """Convenience helper — True iff the lead carries the gold tier."""
    return classify_tier(lead.get("source_chain") or []) == "gold"


# ─── Helpers ────────────────────────────────────────────────────────────
def _norm_phone(raw: str) -> str:
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    return ""


def _norm_name(raw: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace — for dedup keys."""
    if not raw:
        return ""
    s = re.sub(r"[^\w\s]", " ", raw.lower())
    return re.sub(r"\s+", " ", s).strip()


def _dedup_key(lead: Dict[str, Any]) -> str:
    """Build a stable dedup key. Prefer phone (most discriminating),
    fall back to website host, finally name+city."""
    name = _norm_name(lead.get("business_name") or "")
    phone = _norm_phone(lead.get("phone") or "")
    if phone:
        return f"{name}|p:{phone}"
    site = (lead.get("website") or "").lower().strip()
    if site:
        host = re.sub(r"^https?://(www\.)?", "", site).split("/")[0]
        return f"{name}|s:{host}"
    city = _norm_name(lead.get("city") or "")
    return f"{name}|c:{city}"


def _firecrawl_key() -> str:
    return os.environ.get("FIRECRAWL_API_KEY", "").strip()


def _tavily_key() -> str:
    return os.environ.get("TAVILY_API_KEY", "").strip()


# ─── Source 4: YellowPages list-page (multi-card discovery) ────────────
_YP_CARD_RE = re.compile(
    r"(?:business-name|listing-title)[^>]*>\s*<a[^>]*>([^<]{2,80})</a>",
    re.IGNORECASE,
)


async def _firecrawl_get(url: str, timeout: int = 18) -> Dict[str, Any]:
    key = _firecrawl_key()
    if not key:
        return {"error": "firecrawl_not_configured"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={"Authorization": f"Bearer {key}"},
                json={"url": url, "formats": ["markdown", "html"]},
            )
            if r.status_code != 200:
                return {"error": f"firecrawl_{r.status_code}"}
            data = r.json()
            if not data.get("success"):
                return {"error": data.get("error", "firecrawl_failed")}
            return {
                "content": (data.get("data") or {}).get("markdown", ""),
                "html": (data.get("data") or {}).get("html", ""),
            }
    except Exception as e:
        return {"error": f"firecrawl_exc:{str(e)[:80]}"}


async def _yellowpages_list(query: str, location: str, limit: int) -> List[Dict[str, Any]]:
    """Pull multiple cards from a YellowPages.ca search page (Firecrawl
    HTML+markdown). Best-effort — page layout changes may reduce yield;
    we extract names + nearby phones via regex chunking.
    """
    url = (
        "https://www.yellowpages.ca/search/si/1/"
        f"{quote_plus(query)}/{quote_plus(location)}"
    )
    page = await _firecrawl_get(url, timeout=18)
    if page.get("error"):
        return []

    html = page.get("html", "") or ""
    md = page.get("content", "") or ""

    # Extract listing names, then for each name capture the nearest phone
    leads: List[Dict[str, Any]] = []
    seen: set = set()
    for m in _YP_CARD_RE.finditer(html):
        name = m.group(1).strip()
        if len(name) < 3 or name.lower() in seen:
            continue
        seen.add(name.lower())
        # Take a ±400-char window around this match for phone extraction
        s = max(0, m.start() - 400)
        e = min(len(html), m.end() + 400)
        window = html[s:e]
        phone_m = PHONE_RE.search(window)
        phone = _norm_phone("".join(phone_m.groups())) if phone_m else ""
        leads.append({
            "business_name": name,
            "phone": phone,
            "website": "",
            "email": "",
            "address": "",
            "city": location,
            "source": "yellowpages_ca",
        })
        if len(leads) >= limit:
            break

    # Markdown fallback when HTML pattern misses (YP rotates classes)
    if not leads and md:
        for line in md.splitlines():
            if "[" in line and "](" in line and len(leads) < limit:
                m = re.match(r"\s*\[([^\]]{3,80})\]\(", line)
                if m:
                    nm = m.group(1).strip()
                    if not any(L["business_name"].lower() == nm.lower() for L in leads):
                        leads.append({
                            "business_name": nm,
                            "phone": "",
                            "website": "",
                            "email": "",
                            "address": "",
                            "city": location,
                            "source": "yellowpages_ca",
                        })

    return leads


# ─── Source 5: Tavily targeted directory search ────────────────────────
async def _tavily_discover(query: str, location: str, limit: int) -> List[Dict[str, Any]]:
    key = _tavily_key()
    if not key:
        return []
    # Bias the query toward Canadian directory pages
    q = (
        f"{query} {location} site:yellowpages.ca OR site:411.ca "
        f"OR site:canada411.ca OR site:cylex-canada.ca"
    )
    try:
        async with httpx.AsyncClient(timeout=SOURCE_TIMEOUT_S) as c:
            r = await c.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": key, "query": q,
                    "search_depth": "basic", "max_results": min(limit, 10),
                    "include_answer": False,
                },
            )
            if r.status_code != 200:
                return []
            results = (r.json() or {}).get("results", [])
    except Exception as e:
        logger.debug(f"[total-scout] tavily failed: {e}")
        return []

    leads: List[Dict[str, Any]] = []
    for item in results[:limit]:
        title = (item.get("title") or "").strip()
        # Strip directory suffixes from titles like "Foo Plumbing | YellowPages.ca"
        clean = re.split(r"\s*[\|\-\u2013]\s*(?:yellow|411|canada411|cylex)",
                          title, maxsplit=1, flags=re.I)[0].strip()
        if len(clean) < 3:
            continue
        snippet = item.get("content") or ""
        phone_m = PHONE_RE.search(snippet)
        phone = _norm_phone("".join(phone_m.groups())) if phone_m else ""
        leads.append({
            "business_name": clean,
            "phone": phone,
            "website": item.get("url") or "",
            "email": "",
            "address": "",
            "city": location,
            "source": "tavily",
        })
    return leads


# ─── Source 6: DuckDuckGo HTML scrape ──────────────────────────────────
async def _duckduckgo_discover(query: str, location: str, limit: int) -> List[Dict[str, Any]]:
    q = f"{query} {location} business phone"
    try:
        async with httpx.AsyncClient(
            timeout=SOURCE_TIMEOUT_S,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AUREM-Scout/1.0"},
            follow_redirects=True,
        ) as c:
            r = await c.get(f"https://html.duckduckgo.com/html/?q={quote_plus(q)}")
            if r.status_code != 200:
                return []
            html = r.text
    except Exception as e:
        logger.debug(f"[total-scout] ddg failed: {e}")
        return []

    leads: List[Dict[str, Any]] = []
    # DDG result titles live in <a class="result__a">…</a>
    for m in re.finditer(r'class="result__a"[^>]*>([^<]{3,140})</a>', html):
        title = m.group(1).strip()
        clean = re.split(r"\s*[\|\-\u2013]\s*(?:yellow|411|cylex|google|maps)",
                          title, maxsplit=1, flags=re.I)[0].strip()
        if len(clean) < 3:
            continue
        if any(L["business_name"].lower() == clean.lower() for L in leads):
            continue
        leads.append({
            "business_name": clean,
            "phone": "",
            "website": "",
            "email": "",
            "address": "",
            "city": location,
            "source": "duckduckgo",
        })
        if len(leads) >= limit:
            break
    return leads


# ─── Existing-source adapters (keep their imports cheap) ───────────────
async def _yelp_discover(query: str, location: str, limit: int) -> List[Dict[str, Any]]:
    try:
        from services.yelp_scout import yelp_leads
        out = await yelp_leads(query, location, limit=limit)
        return out.get("leads") or []
    except Exception as e:
        logger.debug(f"[total-scout] yelp failed: {e}")
        return []


async def _google_places_discover(query: str, location: str, limit: int) -> List[Dict[str, Any]]:
    """Uses the legacy `google_places_leads` BUT skips its Yelp/OSM tiers
    — we want JUST Google Places here so the dispatcher remains the
    parallel-orchestration layer.

    Falls back to an empty list when billing is disabled (the legacy
    helper logs the underlying error).
    """
    try:
        from services.google_places_scout import (
            _text_search, _place_details, _is_blocked_url, _strip_phone, is_valid_lead,
        )
    except Exception:
        return []
    try:
        raw = await _text_search(query, location, max_results=limit)
    except Exception as e:
        logger.debug(f"[total-scout] places search failed: {e}")
        return []
    if not raw:
        return []
    leads: List[Dict[str, Any]] = []
    for r in raw:
        try:
            place_id = r.get("place_id")
            if not place_id:
                continue
            det = await _place_details(place_id) or {}
            name = (det.get("name") or r.get("name") or "").strip()
            if not name:
                continue
            website = (det.get("website") or "").strip()
            if website and _is_blocked_url(website):
                continue
            phone = _strip_phone(
                det.get("formatted_phone_number")
                or det.get("international_phone_number") or ""
            )
            lead = {
                "business_name": name,
                "phone": phone,
                "website": website,
                "email": "",
                "address": det.get("formatted_address") or "",
                "city": location,
                "rating": det.get("rating"),
                "review_count": det.get("user_ratings_total"),
                "place_id": place_id,
                "source": "google_places",
            }
            if is_valid_lead(lead):
                leads.append(lead)
            if len(leads) >= limit:
                break
        except Exception:
            continue
    return leads


async def _osm_discover(query: str, location: str, limit: int) -> List[Dict[str, Any]]:
    try:
        from services.google_places_scout import _overpass_search, _is_blocked_url
        raw = await _overpass_search(query, location, max_results=limit)
    except Exception as e:
        logger.debug(f"[total-scout] osm failed: {e}")
        return []
    leads: List[Dict[str, Any]] = []
    for o in raw or []:
        site = (o.get("website") or "").strip()
        if site and _is_blocked_url(site):
            continue
        leads.append({
            "business_name": o.get("name") or "",
            "phone": _norm_phone(o.get("phone") or ""),
            "website": site,
            "email": (o.get("email") or "").strip(),
            "address": o.get("address", ""),
            "city": location,
            "source": "osm_overpass",
        })
    return leads


# ─── Source 7: Forensic Miner (ECOMMERCE-NICHE only) ───────────────────
async def _forensic_discover(query: str, location: str, limit: int) -> List[Dict[str, Any]]:
    """Adapter for `services.forensic_miner_service.scan_niche()`.

    Gated: returns ``[]`` immediately when the query does NOT look like
    an ecommerce-niche keyword. This keeps the (paid) Tomba.io email
    lookups dormant for local-trades queries that have no use for it.

    The adapter only consumes the **discovered domains** + emails — not
    the per-store outreach side effects of the full forensic flow. We
    do `_search_domains` then `_find_emails` directly.
    """
    if not _looks_like_ecommerce_niche(query):
        return []
    try:
        from services.forensic_miner_service import _search_domains, _find_emails
    except Exception as e:
        logger.debug(f"[total-scout] forensic import failed: {e}")
        return []

    # Pick a niche keyword from the query — first match wins.
    q = (query or "").lower()
    niche = next((kw for kw in _FORENSIC_NICHE_KEYWORDS if kw in q), q[:40])

    try:
        domains = await _search_domains(niche, limit=limit)
    except Exception as e:
        logger.debug(f"[total-scout] forensic search failed: {e}")
        return []
    if not domains:
        return []

    leads: List[Dict[str, Any]] = []
    for d in domains[:limit]:
        dom = (d.get("domain") or "").strip()
        if not dom:
            continue
        # Email lookup is best-effort and rate-limited at source.
        email = ""
        try:
            email_info = await _find_emails(dom)
            if isinstance(email_info, dict):
                em = email_info.get("primary_email") or email_info.get("email") or ""
                email = em.strip()
        except Exception:
            email = ""

        # Niche store names rarely have phone numbers — that's fine,
        # email IS the outreach channel here.
        leads.append({
            "business_name": (d.get("name") or dom).strip(),
            "phone": "",
            "website": f"https://{dom}" if not dom.startswith("http") else dom,
            "email": email,
            "address": "",
            "city": location,
            "source": "forensic_miner",
        })
    return leads


# ─── Telemetry: per-source attribution ─────────────────────────────────
async def _record_source_run(
    db, *, query: str, location: str,
    source_yields: Dict[str, int], total_after_dedup: int,
    elapsed_ms: int, errors: Dict[str, str],
) -> None:
    """Persist one orchestrator run summary to scout_source_runs.

    Schema:
      ts, query, location, source_yields:{...},
      total_after_dedup, elapsed_ms, errors:{...}
    """
    if db is None:
        return
    try:
        await db.scout_source_runs.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(),
            "query": (query or "")[:120],
            "location": (location or "")[:120],
            "source_yields": source_yields,
            "total_after_dedup": int(total_after_dedup),
            "elapsed_ms": int(elapsed_ms),
            "errors": errors,
        })
    except Exception as e:
        logger.debug(f"[total-scout] telemetry write failed: {e}")


async def get_source_stats(db, days: int = 7) -> Dict[str, Any]:
    """Aggregate the last `days` of `scout_source_runs` for the admin
    Source-Stats dashboard. Returns:

        {
          "since": "<ISO>", "runs": int, "total_leads": int,
          "by_source": [{"source": str, "leads": int, "share_pct": float}],
          "avg_elapsed_ms": int,
        }
    """
    if db is None:
        return {"since": None, "runs": 0, "total_leads": 0, "by_source": [], "avg_elapsed_ms": 0}
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).isoformat()
    runs = 0
    total_leads = 0
    by_source: Dict[str, int] = {}
    elapsed_total = 0
    try:
        cursor = db.scout_source_runs.find(
            {"ts": {"$gte": cutoff}},
            {"_id": 0, "source_yields": 1, "total_after_dedup": 1, "elapsed_ms": 1},
        ).limit(2000)
        async for d in cursor:
            runs += 1
            total_leads += int(d.get("total_after_dedup") or 0)
            elapsed_total += int(d.get("elapsed_ms") or 0)
            for src, n in (d.get("source_yields") or {}).items():
                by_source[src] = by_source.get(src, 0) + int(n or 0)
    except Exception as e:
        logger.debug(f"[total-scout] stats read failed: {e}")

    sum_yields = sum(by_source.values())
    by_source_list = [
        {
            "source": src,
            "leads": n,
            "share_pct": round((n / sum_yields) * 100, 2) if sum_yields else 0.0,
        }
        for src, n in sorted(by_source.items(), key=lambda kv: -kv[1])
    ]
    return {
        "since": cutoff,
        "runs": runs,
        "total_leads": total_leads,
        "by_source": by_source_list,
        "avg_elapsed_ms": int(elapsed_total / runs) if runs else 0,
    }


# ─── Public dispatcher ─────────────────────────────────────────────────
SourceFn = Callable[[str, str, int], Awaitable[List[Dict[str, Any]]]]

_SOURCES: Dict[str, SourceFn] = {
    "yelp":         _yelp_discover,
    "google_places": _google_places_discover,
    "osm":          _osm_discover,
    "yellowpages":  _yellowpages_list,
    "tavily":       _tavily_discover,
    "duckduckgo":   _duckduckgo_discover,
    "forensic":     _forensic_discover,
}


async def _run_source(
    name: str, fn: SourceFn, query: str, location: str, limit: int,
) -> tuple[str, List[Dict[str, Any]], Optional[str]]:
    """Run one source with a hard timeout. Returns (name, leads, err)."""
    try:
        leads = await asyncio.wait_for(
            fn(query, location, limit), timeout=SOURCE_TIMEOUT_S,
        )
        return name, list(leads or []), None
    except asyncio.TimeoutError:
        return name, [], "timeout"
    except Exception as e:
        return name, [], str(e)[:120]


async def discover_leads_total_scout(
    query: str,
    location: str,
    *,
    limit: int = DEFAULT_LIMIT,
    db=None,
    enabled: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Run every enabled source in parallel, dedup, return.

    Returned shape (back-compat with `google_places_leads`):
        {
          success: bool,
          leads: [...],
          total: int,
          query, location,
          source: 'total_scout',
          source_yields: {yelp: 12, places: 4, ...},   # NEW
          source_chains:  [...]                         # NEW (per-lead)
        }
    """
    started = datetime.now(timezone.utc)
    flags = {**ENABLED_SOURCES, **(enabled or {})}

    # Per-source per-call budget — we want each source to attempt up to
    # `limit` items so dedup doesn't starve out a high-volume tier.
    per_source_limit = max(5, limit)

    coros = []
    names: List[str] = []
    for name, fn in _SOURCES.items():
        if not flags.get(name, True):
            continue
        names.append(name)
        coros.append(_run_source(name, fn, query, location, per_source_limit))

    results = await asyncio.gather(*coros, return_exceptions=False)

    # Dedup with source-chain accumulation
    by_key: Dict[str, Dict[str, Any]] = {}
    source_yields: Dict[str, int] = {}
    errors: Dict[str, str] = {}
    for src_name, leads, err in results:
        source_yields[src_name] = len(leads)
        if err:
            errors[src_name] = err
        for lead in leads:
            k = _dedup_key(lead)
            if not k or k.startswith("|"):  # no name → useless
                continue
            existing = by_key.get(k)
            if existing is None:
                lead = dict(lead)
                lead["source_chain"] = [lead.get("source") or src_name]
                by_key[k] = lead
            else:
                # Merge: keep first non-empty values for phone/website/email/address
                for fld in ("phone", "website", "email", "address", "rating", "review_count"):
                    if not existing.get(fld) and lead.get(fld):
                        existing[fld] = lead[fld]
                chain = existing.setdefault("source_chain", [existing.get("source")])
                if (lead.get("source") or src_name) not in chain:
                    chain.append(lead.get("source") or src_name)

    final_leads = list(by_key.values())[:limit]

    # Sovereign-Gold tier tagging — assign tier per lead based on
    # distinct sources in its source_chain.
    tier_counts = {"gold": 0, "silver": 0, "bronze": 0}
    for L in final_leads:
        tier = classify_tier(L.get("source_chain") or [])
        L["tier"] = tier
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    # ═══ ITER 322p — Scout enrichment (Section 3) ═══
    # DB dedup (phone E.164 + name+postal) + dead-check + lead score
    # (1–10) + industry priority. Runs AFTER source-level dedup so we
    # only round-trip Mongo for truly novel candidates.
    try:
        from services.scout_enrichment import enrich_and_filter_leads
        final_leads = await enrich_and_filter_leads(final_leads, db=db)
    except Exception as e:
        # Never let enrichment break discovery — fall through with raw leads.
        logger.debug(f"[total-scout] enrichment skipped: {e}")

    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    await _record_source_run(
        db,
        query=query, location=location,
        source_yields=source_yields,
        total_after_dedup=len(final_leads),
        elapsed_ms=elapsed_ms,
        errors=errors,
    )

    # Phase 1 — emit LEADS_FOUND so Hunter ORA can qualify in parallel.
    # Fire-and-forget to keep scout latency unchanged.
    if final_leads:
        try:
            from services.agent_registry import heartbeat, log_action
            from services.a2a_bus import bus
            import asyncio as _asyncio
            top_industry = ""
            try:
                from collections import Counter
                inds = [l.get("industry") or l.get("niche") or ""
                        for l in final_leads]
                inds = [i for i in inds if i]
                if inds:
                    top_industry = Counter(inds).most_common(1)[0][0]
            except Exception:
                pass
            _asyncio.create_task(_asyncio.gather(
                heartbeat("scout"),
                log_action("scout", "LEADS_FOUND",
                           f"{len(final_leads)} leads",
                           metadata={"top_industry": top_industry,
                                     "elapsed_ms": elapsed_ms}),
                bus.emit("scout", "LEADS_FOUND", {
                    "count": len(final_leads),
                    "query": query,
                    "location": location,
                    "top_industry": top_industry,
                }),
                return_exceptions=True,
            ))
        except Exception:
            pass

    return {
        "success": True,
        "leads": final_leads,
        "total": len(final_leads),
        "query": query,
        "location": location,
        "source": "total_scout",
        "source_yields": source_yields,
        "tier_counts": tier_counts,
        "elapsed_ms": elapsed_ms,
        "errors": errors,
    }


# ─── Back-compat alias ─────────────────────────────────────────────────
async def google_places_leads(query: str, location: str, limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    """Legacy alias — kept so existing callers don't break.

    The function name is misleading (it always orchestrated multiple
    sources). The new `discover_leads_total_scout` is the canonical
    entrypoint and is wired to the same dispatcher PLUS three more
    discovery sources.
    """
    return await discover_leads_total_scout(query, location, limit=limit)
