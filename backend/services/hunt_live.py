"""
Hunt Live Progress Orchestrator
================================
End-to-end Hunt pipeline with real-time SSE progress events.

Flow per business:
  SCOUT → VERIFY → WEBSITE → BLAST (email + whatsapp + sms + call)

Each step emits a `hunt_progress` SSE event so the ORA chat, Campaign HQ
banner, and Empire HUD can all react in real time.

Supports mock mode for safe testing without burning API quota / sending
real outreach. Mock mode is triggered by city=="TEST_CITY" or mock=True.

Usage:
    from services.hunt_live import start_hunt

    hunt_id = await start_hunt(db, city="Mississauga", industry="auto shops", count=20)
    # Returns immediately. Progress streams via push_sse_event().
    # Caller should redirect the user to the live progress UI.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# HUD node map — which FrameworkMap module should flash for each step
# These module IDs MUST match entries in /app/frontend/src/platform/FrameworkMap.jsx LAYERS[].modules[].id
STEP_TO_HUD_NODE = {
    "scout":    "deep_scout",       # L3 Intelligence — Deep Scout
    "verify":   "sentinel",         # L3 Intelligence — Sentinel Anomaly (cross-verification)
    "website":  "website_builder",  # L5 Commerce (if present) or fallback label
    "email":    "email_blast",      # L6 Outreach — Email
    "whatsapp": "whatsapp_channel", # L6 Outreach — WhatsApp
    "sms":      "sms_channel",      # L6 Outreach — SMS
    "call":     "voice_layer",      # L2 ORA — Voice Layer (voice agent)
    "campaign": "ora_dispatch",     # L2 ORA — Dispatcher (overall pipeline orchestrator)
}


# ──────────────────────────────────────────────────────────────
# Mock data — used when city=="TEST_CITY" or explicit mock=True
# ──────────────────────────────────────────────────────────────

_MOCK_BUSINESSES = [
    {"name": "Mike's Auto Care", "phone": "+14165551001", "rating": 4.8, "address": "100 King St, Mississauga, ON"},
    {"name": "Brampton Garage", "phone": "+14165551002", "rating": 4.6, "address": "250 Queen St, Mississauga, ON"},
    {"name": "Wheels & Deals", "phone": "+14165551003", "rating": 4.3, "address": "50 Lakeshore, Mississauga, ON"},
    {"name": "Apex Auto Works", "phone": "+14165551004", "rating": 4.9, "address": "700 Hurontario, Mississauga, ON"},
    {"name": "QuickFix Motors", "phone": "+14165551005", "rating": 4.1, "address": "320 Burnhamthorpe, Mississauga, ON"},
    {"name": "Precision Auto", "phone": "", "rating": 4.4, "address": "880 Eglinton Ave, Mississauga, ON"},  # no phone → will skip WA/SMS/Call
    {"name": "North Star Auto", "phone": "+14165551007", "rating": 3.9, "address": "60 Derry Rd, Mississauga, ON"},
    {"name": "Reliable Repairs", "phone": "+14165551008", "rating": 4.7, "address": "420 Dundas St, Mississauga, ON"},
]


async def _push(event_type: str, payload: Dict[str, Any]):
    """Push an event to SSE + recent_events deque (Empire HUD reads the same feed)."""
    try:
        from routers.server_misc_routes import push_sse_event
        await push_sse_event(event_type, payload)
    except Exception as e:
        logger.debug(f"[hunt_live] SSE push failed: {e}")


async def _flash_hud_node(hunt_id: str, step: str, business_name: str = ""):
    """Tell Empire HUD to flash a specific node for ~1 second."""
    node = STEP_TO_HUD_NODE.get(step)
    if not node:
        return
    await _push("hud_node_flash", {
        "hunt_id": hunt_id,
        "node": node,
        "step": step,
        "business": business_name,
    })


async def _emit_progress(
    hunt_id: str,
    step: str,
    status: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
):
    """Emit a single hunt_progress event — picked up by ORA chat, Campaign HQ, and HUD."""
    await _push("hunt_progress", {
        "hunt_id": hunt_id,
        "step": step,
        "status": status,       # "started" | "ok" | "fail" | "skipped"
        "message": message,
        "data": data or {},
    })


# ──────────────────────────────────────────────────────────────
# Individual step executors — return (success, info_dict)
# ──────────────────────────────────────────────────────────────

async def _run_scout(query: str, mock: bool) -> Optional[Dict[str, Any]]:
    """Return first Google Places hit for the query, or a mocked one."""
    if mock:
        await asyncio.sleep(0.3)  # simulate latency
        return {
            "business_name": _MOCK_BUSINESSES[0]["name"],
            "phone": _MOCK_BUSINESSES[0]["phone"],
            "rating": _MOCK_BUSINESSES[0]["rating"],
            "address": _MOCK_BUSINESSES[0]["address"],
            "website": "",
        }

    try:
        from services.business_scout import scout_business_full
        result = await scout_business_full(query, "")
        gp = (result.get("sources", {}) or {}).get("google_places") or {}
        if not gp.get("business_name"):
            return None
        return {
            "business_name": gp.get("business_name"),
            "phone": gp.get("phone", ""),
            "rating": gp.get("rating"),
            "address": gp.get("address", ""),
            "website": gp.get("website", ""),
            "others": gp.get("other_results", []),
        }
    except Exception as e:
        logger.warning(f"[hunt_live] scout failed: {e}")
        return None


async def _run_verify(business: Dict[str, Any], mock: bool) -> Dict[str, Any]:
    """Return {confidence: HIGH/MEDIUM/LOW, gating: {call, sms, whatsapp, email}}."""
    if mock:
        await asyncio.sleep(0.25)
        # Mock: alternate HIGH / MEDIUM based on rating
        rating = business.get("rating") or 4.0
        confidence = "HIGH" if rating >= 4.5 else ("MEDIUM" if rating >= 4.0 else "LOW")
        phone_ok = bool(business.get("phone"))
        return {
            "confidence": confidence,
            "gating": {
                "call": phone_ok and confidence != "LOW",
                "sms": phone_ok,
                "whatsapp": phone_ok,
                "email": True,  # we generate a contact email anyway
            },
        }

    # Real: plug into sentinel_verifier if available
    try:
        from services.sentinel_verifier import verify_business
        result = await verify_business(business.get("business_name", ""), business.get("address", ""))
        return result
    except Exception:
        # Fallback — permissive gating
        phone_ok = bool(business.get("phone"))
        return {
            "confidence": "MEDIUM",
            "gating": {"call": phone_ok, "sms": phone_ok, "whatsapp": phone_ok, "email": True},
        }


# ──────────────────────────────────────────────────────────────
# iter 324e — Listicle / SEO-page-title detector
# ──────────────────────────────────────────────────────────────
# When Tavily / DDG / SERP scraping leaks in, business_name ends up
# being an HTML <title> tag like:
#   "Dental Care That Feels Like Self-Care | Boston Dental"
#   "Buy a Well-established Spa And Salon - Eastern Canada"
#   "Top 10 Plumbers in Toronto (2025 Edition) - HomeStars"
# These are NOT businesses. This detector rejects them at the gate.
_LISTICLE_SEPARATORS = ("|", "—", " - ", " :: ", " » ", " › ")
_LISTICLE_KEYWORDS = (
    "top ", " top ", "best ", " best ",
    "list of", "the top", "guide to",
    "buy ", "buying ", "for sale", "businesses for sale",
    "how to", "what is", "why ", "should you",
    "cost of", "price of", "free ",
    "near me", "near you",
    "(20", "(2020", "(2021", "(2022", "(2023", "(2024", "(2025", "(2026",
    "edition)", "rated)",
    " | ", " — ", " :: ", " » ",
)
_SEO_SUFFIXES = (
    "yelp", "yellowpages", "yp.com", "bbb",
    "google reviews", "facebook", "instagram",
    "tripadvisor", "houzz", "homestars", "thumbtack",
    "businessesforsale", "near.com", "near.co.uk",
    "cylex", "findopen", "bleen",
    "wikipedia", "reddit", "quora",
)


def _is_listicle_title(business_name: str) -> tuple[bool, str]:
    """Return (True, reason) if the business name looks like an HTML
    page title / listicle / aggregator listing rather than an actual
    business name."""
    if not business_name:
        return (True, "empty")
    name = business_name.strip()
    if len(name) > 90:
        return (True, "too-long")
    name_l = name.lower()
    # Pipe / em-dash separators are the strongest signal — real
    # businesses don't have those in their names.
    for sep in _LISTICLE_SEPARATORS:
        if sep in name:
            return (True, f"title-separator:{sep!r}")
    # Listicle / SEO-content keywords
    for kw in _LISTICLE_KEYWORDS:
        if kw in name_l:
            return (True, f"listicle-keyword:{kw!r}")
    # Aggregator brand at the end (e.g. "Plumbing Co - Yelp")
    for suf in _SEO_SUFFIXES:
        if name_l.endswith(suf):
            return (True, f"aggregator-suffix:{suf!r}")
    return (False, "")


async def _run_website(db, lead_doc: Dict[str, Any], mock: bool) -> Optional[str]:
    """Generate (or reuse) a sample website. Returns the public URL slug."""
    slug = lead_doc.get("lead_id") or re.sub(r"[^a-z0-9]+", "-", lead_doc["business_name"].lower()).strip("-")[:60]
    if mock:
        await asyncio.sleep(0.2)
        return f"aurem.live/sample/{slug}"

    try:
        from routers.website_builder_router import auto_generate_if_missing
        if db is not None:
            await auto_generate_if_missing(db, lead_doc)
        return f"aurem.live/sample/{slug}"
    except Exception as e:
        logger.warning(f"[hunt_live] website gen failed for {slug}: {e}")
        return None


async def _run_blast_one(
    db,
    lead_doc: Dict[str, Any],
    gating: Dict[str, bool],
    mock: bool,
) -> Dict[str, Any]:
    """Run blast across all gated channels and return per-channel result map."""
    if mock:
        await asyncio.sleep(0.4)
        return {
            "email":    {"ok": gating.get("email", False), "mock": True},
            "whatsapp": {"ok": gating.get("whatsapp", False), "mock": True},
            "sms":      {"ok": gating.get("sms", False), "mock": True},
            "call":     {"ok": gating.get("call", False), "mock": True},
        }

    # Real: reuse existing blast_one logic but split per-channel so we can emit per-channel events
    try:
        from services.ora_command_center import _exec_blast_one
        res = await _exec_blast_one(db, {"business_name": lead_doc["business_name"]})
        data = res.get("data", {}) or {}
        return {
            "email":    data.get("email", {"ok": False}),
            "whatsapp": data.get("whatsapp", {"ok": False}),
            "sms":      data.get("sms", {"ok": False}),
            "call":     {"ok": False, "error": "call not wired in blast_one"},
        }
    except Exception as e:
        logger.warning(f"[hunt_live] blast failed: {e}")
        return {
            "email":    {"ok": False, "error": str(e)},
            "whatsapp": {"ok": False, "error": str(e)},
            "sms":      {"ok": False, "error": str(e)},
            "call":     {"ok": False, "error": str(e)},
        }


# ──────────────────────────────────────────────────────────────
# Main orchestrator
# ──────────────────────────────────────────────────────────────

async def _discover_businesses(query: str, limit: int) -> List[Dict[str, Any]]:
    """Discover a LIST of businesses matching a free-text query.

    iter 324e — Production data showed 100% of last-48h ingestion came
    from the Tavily/DDG web-fallback branches at the bottom of this
    function, producing leads like
        business_name: "Dental Benefits for Individuals & Groups - Delta Dental"
        email:         info@deltadentalma.com   (planted by apollo_enrichment)
    i.e. HTML page titles + role-email guesses, not real businesses.

    These two branches are now **disabled by default**. Set
    `HUNT_ENABLE_WEB_FALLBACK=1` in env to re-enable (NOT recommended).

    Order (post-324e):
      1. Google Places — official SMB pool, phone+website+address+rating
      2. Yelp Fusion   — 5000 free calls/day, phone+rating+review_count
      3. OSM Overpass  — community-maintained, free, fallback
      4. Tavily        — disabled by default (web titles → junk leads)
      5. DuckDuckGo    — disabled by default (web titles → junk leads)
    """
    import os
    import re
    import httpx
    results: List[Dict[str, Any]] = []

    # ── Parse "industry in city" / "industry near city" out of the query ──
    industry_for_lookup = query
    city_for_lookup = None
    if " in " in query:
        industry_for_lookup, _, city_for_lookup = query.partition(" in ")
    elif " near " in query:
        industry_for_lookup, _, city_for_lookup = query.partition(" near ")
    industry_for_lookup = industry_for_lookup.strip()
    city_for_lookup = (city_for_lookup or "").strip() or "Mississauga, ON"

    # ── 1. Apollo.io (PRIMARY — iter D-60b) ─────────────────────
    # Founder paid for Apollo $65/mo plan specifically for SMB
    # discovery. Returns real Canadian SMBs with verified
    # phone/website/city. Hits before Google Places because GP key
    # often has billing disabled on prod.
    apollo_key = (os.environ.get("APOLLO_API_KEY") or "").strip()
    if apollo_key:
        try:
            from services.apollo_discovery import discover_organizations
            apollo_leads = await discover_organizations(
                industry_keyword=industry_for_lookup,
                city=city_for_lookup.split(",")[0].strip() or "Mississauga",
                province="Ontario",
                country="Canada",
                per_page=min(limit, 25),
            )
            for lead in apollo_leads[:limit]:
                results.append({
                    "business_name": lead.get("business_name", ""),
                    "phone":         lead.get("phone", ""),
                    "address":       f"{lead.get('city','')}, {lead.get('province','')}".strip(", "),
                    "website":       lead.get("website", ""),
                    "rating":        4.0,
                    "review_count":  0,
                    "source":        "apollo_discovery",
                    "domain":        lead.get("domain", ""),
                    "industry":      lead.get("industry", ""),
                    "employees":     lead.get("employees", 0),
                    "linkedin_url":  lead.get("linkedin_url", ""),
                })
            if results:
                logger.info(f"[hunt_live] Apollo → {len(results)} businesses (primary, real SMBs)")
                return results
            else:
                logger.warning(f"[hunt_live] Apollo returned 0 for '{query}' — falling through to Google Places")
        except Exception as e:
            logger.warning(f"[hunt_live] Apollo discovery failed: {e}")

    # ── 2. Google Places (secondary fallback — iter 324e, demoted by D-60b)
    # Highest quality fallback when Apollo returns 0. Returns real business
    # names, not HTML page titles. Phone is canonical.
    gp_key = os.environ.get("GOOGLE_PLACES_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
    if gp_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    headers={
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": gp_key,
                        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount",
                    },
                    json={"textQuery": query, "pageSize": min(limit, 20)},
                )
                if resp.is_success:
                    for p in resp.json().get("places", [])[:limit]:
                        name = (p.get("displayName") or {}).get("text", "")
                        if not name:
                            continue
                        results.append({
                            "business_name": name,
                            "phone":   p.get("nationalPhoneNumber", ""),
                            "address": p.get("formattedAddress", ""),
                            "website": p.get("websiteUri", ""),
                            "rating":  p.get("rating") or 4.0,
                            "review_count": p.get("userRatingCount") or 0,
                            "source":  "google_places",
                        })
                    if results:
                        logger.info(f"[hunt_live] Google Places → {len(results)} businesses (primary)")
                        return results
                else:
                    logger.warning(f"[hunt_live] Google Places HTTP {resp.status_code}: {resp.text[:200]}")
                    # iter 330d — surface key issues to Telegram immediately.
                    try:
                        from services.api_key_health_watcher import record_api_failure
                        await record_api_failure(
                            provider="google_places",
                            status_code=resp.status_code,
                            body=resp.text[:400],
                            key_hint=(os.environ.get("GOOGLE_PLACES_API_KEY") or "")[-6:],
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"[hunt_live] Google Places discovery failed: {e}")

    # ── 2. Yelp Fusion (secondary — iter 324e) ─────────────────
    yelp_key = os.environ.get("YELP_API_KEY", "").strip()
    if yelp_key:
        try:
            from services.yelp_scout import yelp_leads
            yres = await yelp_leads(
                query=industry_for_lookup,
                location=city_for_lookup,
                limit=min(int(limit) * 2, 50),
                radius_m=15000,
            )
            if yres.get("success") and yres.get("leads"):
                for lead in yres["leads"][:limit]:
                    results.append({
                        "business_name": lead["business_name"],
                        "phone":   lead.get("phone") or "",
                        "address": lead.get("address") or lead.get("city") or "",
                        "website": lead.get("website") or "",
                        "rating":  lead.get("rating") or 4.0,
                        "review_count": lead.get("review_count") or 0,
                        "yelp_url": lead.get("yelp_url") or "",
                        "source":  "yelp_fusion",
                    })
                if results:
                    logger.info(f"[hunt_live] Yelp Fusion → {len(results)} businesses (secondary)")
                    return results
        except Exception as e:
            logger.warning(f"[hunt_live] Yelp Fusion discovery failed: {e}")

    # ── 3. OSM Overpass (tertiary — free fallback) ─────────────
    try:
        from services.osm_scout import osm_leads
        ores = await osm_leads(
            query=industry_for_lookup,
            location=city_for_lookup,
            limit=min(int(limit) * 2, 50),
            radius_m=15000,
        )
        if ores.get("success") and ores.get("leads"):
            for lead in ores["leads"][:limit]:
                results.append({
                    "business_name": lead["business_name"],
                    "phone":   lead.get("phone") or "",
                    "address": lead.get("address") or lead.get("city") or "",
                    "website": lead.get("website") or "",
                    "rating":  lead.get("rating") or 4.0,
                    "email":   lead.get("email") or "",
                    "osm_id":  lead.get("osm_id"),
                    "source":  "osm_overpass",
                })
            if results:
                logger.info(f"[hunt_live] OSM Overpass → {len(results)} businesses (tertiary)")
                return results
    except Exception as e:
        logger.warning(f"[hunt_live] OSM Overpass discovery failed: {e}")

    # ── 4 + 5. Tavily + DDG (disabled by default — iter 324e) ──
    # Set HUNT_ENABLE_WEB_FALLBACK=1 to re-enable. NOT RECOMMENDED.
    # Production data showed 100% of last-48h ingestion came from these
    # branches, producing HTML-page-title leads like
    #   "Dental Benefits for Individuals & Groups - Delta Dental"
    # paired with `info@deltadentalma.com` role-email fallbacks.
    if os.environ.get("HUNT_ENABLE_WEB_FALLBACK", "0").strip() not in ("1", "true", "yes"):
        logger.warning(
            f"[hunt_live] all 3 primary sources returned 0 for '{query}'. "
            "Web fallback disabled (HUNT_ENABLE_WEB_FALLBACK!=1). Returning empty."
        )
        return []

    # ── 2. Tavily ─────────────────────────────────────────────
    tv_key = os.environ.get("TAVILY_API_KEY")
    if tv_key:
        try:
            # Tavily returns general web results. Craft query to bias toward directory listings.
            tavily_query = f"top {query} list directory name phone address"
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": tv_key,
                        "query": tavily_query,
                        "search_depth": "advanced",
                        "max_results": min(limit * 2, 20),
                        "include_answer": True,
                    },
                )
                if resp.is_success:
                    data = resp.json()
                    tav_results = data.get("results", [])
                    # Parse each result's title + content for a business name + phone.
                    phone_re = re.compile(r"\+?1?\s*[\(\-]?(\d{3})[\)\-\s]*(\d{3})[\-\s]*(\d{4})")
                    seen_names = set()
                    for r in tav_results:
                        title = (r.get("title") or "").strip()
                        content = r.get("content") or ""
                        # Clean up title — strip common suffixes
                        cleaned = re.sub(r"\s*[-|–]\s*(Yelp|Google|Yellow Pages|BBB|Top \d+.*|Best.*|Reviews).*$", "", title, flags=re.I).strip()
                        if not cleaned or len(cleaned) < 3 or cleaned.lower() in seen_names:
                            continue
                        # Skip generic listicle titles
                        if re.match(r"^(top|best|list of|the \d+|\d+ best)", cleaned, re.I):
                            continue
                        seen_names.add(cleaned.lower())
                        m = phone_re.search(content) or phone_re.search(title)
                        phone = f"+1{m.group(1)}{m.group(2)}{m.group(3)}" if m else ""
                        results.append({
                            "business_name": cleaned[:100],
                            "phone":   phone,
                            "address": "",
                            "website": r.get("url", ""),
                            "rating":  4.2,   # default rating when unknown
                            "source":  "tavily",
                        })
                        if len(results) >= limit:
                            break
                    if results:
                        logger.info(f"[hunt_live] Tavily → {len(results)} businesses")
                        return results
        except Exception as e:
            logger.warning(f"[hunt_live] Tavily discovery failed: {e}")

    # ── 3. DuckDuckGo ─────────────────────────────────────────
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        phone_re = re.compile(r"\+?1?\s*[\(\-]?(\d{3})[\)\-\s]*(\d{3})[\-\s]*(\d{4})")
        for r in ddgs.text(f"{query} business directory", max_results=limit * 2):
            title = (r.get("title") or "").strip()
            body = r.get("body") or ""
            cleaned = re.sub(r"\s*[-|–]\s*.*(Yelp|Yellow|Top|Best|Reviews).*$", "", title, flags=re.I).strip()
            if not cleaned or len(cleaned) < 3:
                continue
            if re.match(r"^(top|best|list of|the \d+|\d+ best)", cleaned, re.I):
                continue
            m = phone_re.search(body)
            phone = f"+1{m.group(1)}{m.group(2)}{m.group(3)}" if m else ""
            results.append({
                "business_name": cleaned[:100],
                "phone":   phone,
                "address": "",
                "website": r.get("href", ""),
                "rating":  4.0,
                "source":  "duckduckgo",
            })
            if len(results) >= limit:
                break
        if results:
            logger.info(f"[hunt_live] DuckDuckGo → {len(results)} businesses")
            return results
    except Exception as e:
        logger.warning(f"[hunt_live] DuckDuckGo discovery failed: {e}")

    logger.warning(f"[hunt_live] No discovery backend returned results for '{query}'")
    return []


async def _run_hunt_pipeline(
    db,
    hunt_id: str,
    city: str,
    industry: str,
    count: int,
    mock: bool,
):
    """Runs the full Hunt pipeline for `count` businesses. Streams progress via SSE.

    Semantics:
      mock=True  → fully mocked data + no persist + no outreach (for TEST_CITY tests).
      mock=False → full live mode with real discovery + persist + outreach.
    """
    query = f"{industry} in {city}".strip()
    summary = {
        "total_requested": count,
        "scouted": 0, "verified_high": 0, "verified_medium": 0, "verified_low": 0,
        "websites_built": 0,
        "emails_sent": 0, "wa_sent": 0, "sms_sent": 0, "calls_made": 0,
        "failures": 0,
    }

    await _emit_progress(hunt_id, "hunt", "started",
                         f"Hunt started: {industry} in {city} (target {count})",
                         {"city": city, "industry": industry, "count": count, "mock": mock})

    # ── DISCOVERY: find N businesses up-front from Tavily/Google Places/DDG ──
    # (Previously the loop called _run_scout(query) every iteration and got the
    # same result N times — or None when no discovery backend was configured.)
    discovered: List[Dict[str, Any]] = []
    if not mock:
        discovered = await _discover_businesses(query, count)
        if not discovered:
            await _emit_progress(hunt_id, "hunt", "fail",
                                 f"Discovery failed: no businesses found for '{query}'. "
                                 "Check GOOGLE_PLACES_API_KEY or TAVILY_API_KEY in backend .env.",
                                 {"error": "no_discovery_backend"})
            return

    actual_count = len(discovered) if not mock else count
    for i in range(actual_count):
        business_label = f"#{i+1}/{actual_count}"

        # 1. SCOUT (now just picks from pre-discovered list)
        await _flash_hud_node(hunt_id, "scout")
        await _emit_progress(hunt_id, "scout", "started",
                             f"{business_label}: scouting {query}...")

        if mock:
            idx = i % len(_MOCK_BUSINESSES)
            business = {
                "business_name": _MOCK_BUSINESSES[idx]["name"],
                "phone":   _MOCK_BUSINESSES[idx]["phone"],
                "rating":  _MOCK_BUSINESSES[idx]["rating"],
                "address": _MOCK_BUSINESSES[idx]["address"],
                "website": "",
            }
            await asyncio.sleep(0.3)
        else:
            business = discovered[i]

        if not business or not business.get("business_name"):
            summary["failures"] += 1
            await _emit_progress(hunt_id, "scout", "fail",
                                 f"{business_label}: no result found, skipping")
            continue

        # ─── Directory/aggregator filter ──────────────────────────────────
        # Skip listings that are directory pages, not real businesses:
        #   - bbb.org, dandb.com, yellowpages, bing/google search fragments
        #   - generic place names (brampton-corners, orion-business-park)
        #   - anything without a phone AND a website that looks like a business
        biz_name_lower = (business.get("business_name") or "").lower()
        website_lower = (business.get("website") or "").lower()
        DIRECTORY_HOSTS = (
            "bbb.org", "dandb.com", "yellowpages", "manta.com",
            "us-business.info", "chamberofcommerce.com", "yelp.com/biz_photos",
            "directory/", "businessdirectory", "/category/",
            "find a ", "find-a-", "near me",
        )
        is_directory = any(h in website_lower for h in DIRECTORY_HOSTS) or \
                       any(h in biz_name_lower for h in ("near me", "directory", "better business bureau"))
        # iter 324b — also reject aggregator/social/SaaS domains (the root
        # cause of `info@facebook.com / info@reddit.com / info@youtube.com`
        # junk in the queue). One source-of-truth blocklist in
        # services/contact_quality.py.
        try:
            from services.contact_quality import is_aggregator_domain
            if business.get("website") and is_aggregator_domain(business["website"]):
                is_directory = True
        except Exception:
            pass
        # iter 324e — reject HTML page titles / SEO listicles. These come
        # from Tavily/DDG web fallback when no real-business source returned
        # results. 100% of last-48h junk had business_name like
        # "Dental Care That Feels Like Self-Care | Boston Dental".
        _bn_listicle, _bn_reason = _is_listicle_title(business.get("business_name", ""))
        if _bn_listicle:
            is_directory = True
            logger.debug(f"[hunt_live] rejected listicle title: {business.get('business_name', '')!r} ({_bn_reason})")
        no_contact = not business.get("phone") and not business.get("website")

        if is_directory or no_contact:
            summary["failures"] += 1
            await _emit_progress(
                hunt_id, "scout", "fail",
                f"{business_label}: skipping {'directory page' if is_directory else 'no-contact-info listing'} — {business.get('business_name','?')[:40]}",
                {"business": business.get("business_name"), "reason": "directory_or_no_contact"},
            )
            continue

        summary["scouted"] += 1
        biz_name = business["business_name"]
        slug = re.sub(r"[^a-z0-9]+", "-", biz_name.lower()).strip("-")[:60]
        rating = business.get("rating") or 0
        await _emit_progress(hunt_id, "scout", "ok",
                             f"Found: {biz_name} — {rating}⭐",
                             {"business": biz_name, "rating": rating, "slug": slug})

        # 2. VERIFY
        await _flash_hud_node(hunt_id, "verify", biz_name)
        await _emit_progress(hunt_id, "verify", "started",
                             f"{biz_name}: cross-verifying across sources...")
        verify = await _run_verify(business, mock=mock)
        confidence = verify.get("confidence", "UNKNOWN")
        gating = verify.get("gating", {})
        if confidence == "HIGH":
            summary["verified_high"] += 1
        elif confidence == "MEDIUM":
            summary["verified_medium"] += 1
        else:
            summary["verified_low"] += 1
        open_channels = [k for k, v in gating.items() if v]
        await _emit_progress(hunt_id, "verify", "ok",
                             f"{biz_name}: {confidence} confidence — channels: {', '.join(open_channels) or 'none'}",
                             {"business": biz_name, "confidence": confidence, "gating": gating})

        # Build lead document (insert-only fields; mutable fields go in $set below)
        # iter 324e — preserve the actual discovery source ("google_places",
        # "yelp_fusion", "osm_overpass", "tavily", "duckduckgo") instead of
        # collapsing everything to "ora_hunt_command". Without this signal,
        # quality audits can't tell which source is producing junk.
        _discovery_source = business.get("source") or "unknown"
        lead_doc = {
            "lead_id": slug,
            "tenant_id": "aurem_platform",
            "campaign_id": "aurem-acquisition-001",
            "business_name": biz_name,
            "phone": business.get("phone", ""),
            "website_url": business.get("website", ""),
            "category": industry,
            "city": city,
            "rating": rating,
            "score": int(float(rating or 4) * 20),
            "source": _discovery_source,             # ← real source now
            "ingest_origin": "ora_hunt_command",     # ← legacy "where ingestion happened"
            "discovery_source": _discovery_source,   # ← explicit alias for audits
            "hunt_id": hunt_id,
            "channel_gating": gating,
            "whatsapp_sent": False,
            "email_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist lead (skip only in fully mocked tests).
        if db is not None and not mock:
            try:
                await db.campaign_leads.update_one(
                    {"lead_id": slug},
                    {"$setOnInsert": lead_doc,
                     "$set": {"last_scouted_at": lead_doc["created_at"],
                              "verification_confidence": confidence,
                              "status": "new"}},
                    upsert=True,
                )
                # Adaptive ORA: seed initial conviction score on brand-new leads.
                try:
                    from services.adaptive_ora import init_lead_conviction
                    await init_lead_conviction(db, slug)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"[hunt_live] lead persist failed: {e}")

        # 2.5 APOLLO DIY ENRICHMENT (iter 287.0 — credit-saver)
        # Uses Apollo Free people/search + local email pattern guess + SMTP probe
        # to populate email on the lead if possible. Silently skipped if no
        # APOLLO_API_KEY or no website domain.
        if db is not None and not mock and business.get("website"):
            try:
                from services.apollo_enrichment import enrich_lead_with_apollo_diy
                enriched = await enrich_lead_with_apollo_diy(
                    db, slug, business.get("website", "")
                )
                if enriched.get("email"):
                    await _emit_progress(hunt_id, "scout", "ok",
                                         f"{biz_name}: enriched → {enriched['email']} "
                                         f"({enriched.get('status','?')})",
                                         {"business": biz_name, **enriched})
            except Exception as e:
                logger.debug(f"[hunt_live] apollo enrich skipped for {slug}: {e}")

        # 3. WEBSITE
        await _flash_hud_node(hunt_id, "website", biz_name)
        await _emit_progress(hunt_id, "website", "started",
                             f"{biz_name}: generating sample website...")
        site_url = await _run_website(db, lead_doc, mock=mock)
        if site_url:
            summary["websites_built"] += 1
            await _emit_progress(hunt_id, "website", "ok",
                                 f"{biz_name}: website ready → {site_url}",
                                 {"business": biz_name, "url": site_url})
        else:
            await _emit_progress(hunt_id, "website", "fail",
                                 f"{biz_name}: website gen failed",
                                 {"business": biz_name})

        # 4. BLAST (per-channel, only gated ones)
        await _flash_hud_node(hunt_id, "campaign", biz_name)
        blast = await _run_blast_one(db, lead_doc, gating, mock=mock)
        for channel in ("email", "whatsapp", "sms", "call"):
            if not gating.get(channel):
                await _emit_progress(hunt_id, channel, "skipped",
                                     f"{biz_name}: {channel} blocked by verifier")
                continue
            await _flash_hud_node(hunt_id, channel, biz_name)
            res = blast.get(channel, {"ok": False})
            if res.get("ok"):
                if channel == "email":
                    summary["emails_sent"] += 1
                if channel == "whatsapp":
                    summary["wa_sent"] += 1
                if channel == "sms":
                    summary["sms_sent"] += 1
                if channel == "call":
                    summary["calls_made"] += 1
                await _emit_progress(hunt_id, channel, "ok",
                                     f"{biz_name}: {channel} sent ✅",
                                     {"business": biz_name})
            else:
                await _emit_progress(hunt_id, channel, "fail",
                                     f"{biz_name}: {channel} failed",
                                     {"business": biz_name, "error": (res.get("error") or "")[:80]})

        # Progress heartbeat (hunt-level percent)
        await _emit_progress(hunt_id, "hunt", "progress",
                             f"Progress: {i+1}/{count}",
                             {"done": i + 1, "total": count, "summary": summary.copy()})

    # Final summary
    await _emit_progress(hunt_id, "hunt", "complete",
                         f"Hunt complete: {summary['scouted']}/{count} businesses found",
                         summary)


async def start_hunt(
    db,
    city: str,
    industry: str,
    count: int = 10,
    mock: bool = False,
) -> str:
    """
    Kick off a Hunt in the background. Returns hunt_id immediately.
    Progress streams via SSE — subscribe to /api/admin/events/{client_id}.
    """
    if city.strip().upper() == "TEST_CITY":
        mock = True
    count = max(1, min(count, 50))  # clamp to reasonable range
    hunt_id = f"hunt_{uuid.uuid4().hex[:10]}"

    # Run in background so the caller (ORA command) returns immediately
    asyncio.create_task(_run_hunt_pipeline(db, hunt_id, city, industry, count, mock))
    logger.info(f"[hunt_live] started hunt_id={hunt_id} city={city} industry={industry} count={count} mock={mock}")
    return hunt_id


async def run_hunt_live(
    query: str,
    limit: int = 20,
    location: str = "Canada",
    radius_km: Optional[float] = None,  # noqa: ARG001 (reserved for future Google Places radius filter)
    db=None,
) -> List[Dict[str, Any]]:
    """
    Public wrapper invoked by the ORA Command Console → agents_router.
    Parses the free-text `query` into (industry, city), kicks off a background
    hunt, and returns the freshly persisted leads for this hunt_id so the
    caller can echo them into the UI preview and into Active Campaigns.
    """
    # Parse "industry in city" pattern (produced by agents_router._do_hunt)
    industry = query
    city = location or "Canada"
    if " in " in query:
        industry, _, city_from_query = query.partition(" in ")
        industry = industry.strip()
        if city_from_query.strip():
            city = city_from_query.strip()
    elif " near " in query:
        industry, _, near_loc = query.partition(" near ")
        industry = industry.strip()
        if near_loc.strip():
            city = near_loc.strip()

    hunt_id = await start_hunt(
        db=db,
        city=city,
        industry=industry,
        count=int(limit),
        mock=False,
    )

    # Give the background task enough time to discover + persist at least
    # the first batch so the caller sees results immediately.
    if db is not None:
        # Wait up to 6s, polling every 0.5s for first lead to appear.
        for _ in range(12):
            await asyncio.sleep(0.5)
            try:
                n = await db.campaign_leads.count_documents({"hunt_id": hunt_id})
                if n > 0:
                    break
            except Exception:
                continue
        try:
            cursor = db.campaign_leads.find(
                {"hunt_id": hunt_id},
                {"_id": 0},
            ).sort("created_at", -1).limit(int(limit))
            leads = await cursor.to_list(int(limit))
            return [
                {
                    "name": r.get("business_name"),
                    "address": r.get("city"),
                    "phone": r.get("phone"),
                    "email": r.get("email"),
                    "score": r.get("score"),
                    "industry": r.get("category"),
                    "hunt_id": hunt_id,
                    "lead_id": r.get("lead_id"),
                }
                for r in (leads or [])
            ]
        except Exception as e:
            logger.warning(f"[run_hunt_live] failed to fetch persisted leads: {e}")
    return []
