"""
AUREM Business Scout Service — Google Places PRIMARY + Fallback Chain
=====================================================================
Priority chain for business discovery:
  1. Google Places API (New) — 100% accurate phone/address/rating
  2. Tavily Search — web scraping fallback
  3. DuckDuckGo — free fallback

Used by: Scout Agent, Forensic Miner, Lead Enrichment, ORA commands
"""
import os
import logging
import httpx
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PLACES_BASE = "https://places.googleapis.com/v1"
FIELD_MASK = ",".join([
    "places.displayName", "places.formattedAddress", "places.nationalPhoneNumber",
    "places.internationalPhoneNumber", "places.websiteUri", "places.rating",
    "places.userRatingCount", "places.currentOpeningHours", "places.businessStatus",
    "places.googleMapsUri", "places.types", "places.primaryType",
])


def _places_key() -> str:
    return os.environ.get("GOOGLE_PLACES_API_KEY", "")


def _tavily_key() -> str:
    return os.environ.get("TAVILY_API_KEY", "")


def _get_db():
    """Best-effort DB handle for fallback logging."""
    try:
        from server import db as _db
        if _db is not None:
            return _db
    except Exception:
        pass
    # Fallback: build a motor client directly from env (async safe, singleton not needed)
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        db_name = os.environ.get("DB_NAME", "aurem_db").strip().strip('"').strip("'")
        if mongo_url:
            return AsyncIOMotorClient(mongo_url)[db_name]
    except Exception:
        pass
    return None


async def _google_places_search(query: str) -> Dict:
    """Search Google Places API (New) for a business."""
    key = _places_key()
    if not key:
        return {"error": "GOOGLE_PLACES_API_KEY not configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{PLACES_BASE}/places:searchText",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": key,
                    "X-Goog-FieldMask": FIELD_MASK,
                },
                json={"textQuery": query},
            )
            data = resp.json()

            if data.get("error"):
                code = data["error"].get("code", 0)
                msg = data["error"].get("message", "")
                if code == 403 and "not been used" in msg:
                    return {"error": "Places API not enabled. Enable at: https://console.developers.google.com/apis/api/places.googleapis.com/overview?project=412081368460"}
                return {"error": f"Google Places: {msg[:200]}"}

            places = data.get("places", [])
            if not places:
                return {"error": "No results found on Google Places"}

            p = places[0]
            result = {
                "source": "google_places",
                "business_name": p.get("displayName", {}).get("text", ""),
                "address": p.get("formattedAddress", ""),
                "phone": p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber", ""),
                "website": p.get("websiteUri", ""),
                "rating": p.get("rating"),
                "review_count": p.get("userRatingCount"),
                "business_status": p.get("businessStatus", ""),
                "google_maps_url": p.get("googleMapsUri", ""),
                "types": p.get("types", []),
                "primary_type": p.get("primaryType", ""),
            }

            hours = p.get("currentOpeningHours", {})
            if hours:
                weekday_text = hours.get("weekdayDescriptions", [])
                result["hours"] = weekday_text
                result["open_now"] = hours.get("openNow")

            # Additional places if multiple results
            if len(places) > 1:
                result["other_results"] = [
                    {"name": pl.get("displayName", {}).get("text", ""), "address": pl.get("formattedAddress", "")}
                    for pl in places[1:4]
                ]

            return result

    except Exception as e:
        return {"error": f"Google Places error: {e}"}


async def _tavily_search(query: str) -> Dict:
    """Fallback: Search via Tavily API."""
    key = _tavily_key()
    if not key:
        return {"error": "TAVILY_API_KEY not configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_answer": True,
                },
            )
            if not resp.is_success:
                return {"error": f"Tavily: {resp.status_code}"}

            data = resp.json()
            results = data.get("results", [])
            answer = data.get("answer", "")

            return {
                "source": "tavily",
                "answer": answer,
                "results": [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")[:300]}
                    for r in results
                ],
            }
    except Exception as e:
        return {"error": f"Tavily error: {e}"}


async def _ddg_search(query: str) -> Dict:
    """Fallback: DuckDuckGo search (free, no API key)."""
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=5))
        return {
            "source": "duckduckgo",
            "results": [{"title": r.get("title", ""), "url": r.get("href", ""), "body": r.get("body", "")[:300]} for r in results],
        }
    except Exception as e:
        return {"error": f"DuckDuckGo error: {e}"}


async def scout_business(name: str, location: str = "") -> Dict:
    """
    Scout a business using the full fallback chain:
    Google Places (PRIMARY) → Tavily → DuckDuckGo
    
    Returns comprehensive business info: phone, email, website, rating, hours, etc.
    """
    query = f"{name} {location}".strip()
    report = {"query": query, "sources_tried": [], "found": {}}

    # 1. Google Places (PRIMARY — most accurate)
    logger.info(f"[Scout] Google Places: {query}")
    gp = await _google_places_search(query)
    report["sources_tried"].append("google_places")

    if not gp.get("error"):
        report["found"] = gp
        report["primary_source"] = "google_places"
        report["confidence"] = "high"
        logger.info(f"[Scout] Google Places found: {gp.get('business_name')} | Phone: {gp.get('phone')}")
        await _fb_log_scout(used="google_places", result="success", reason=None)
        try:
            from services.fallback_monitor import reset_primary_failure
            await reset_primary_failure(_get_db(), service="scout", primary="google_places")
        except Exception:
            pass
        return report
    else:
        report["google_places_error"] = gp["error"]
        try:
            from services.fallback_monitor import record_primary_failure
            await record_primary_failure(_get_db(), service="scout",
                                         primary="google_places",
                                         reason=gp["error"][:200])
        except Exception:
            pass

    # 2. Tavily (FALLBACK — web search)
    logger.info(f"[Scout] Tavily fallback: {query}")
    tv = await _tavily_search(f"{query} phone number email address hours reviews")
    report["sources_tried"].append("tavily")

    if not tv.get("error"):
        # Parse phone/email from Tavily answer
        answer = tv.get("answer", "")
        import re
        phones = re.findall(r'\+?1?\s*[\(\-]?\d{3}[\)\-\s]*\d{3}[\-\s]*\d{4}', answer)
        emails = re.findall(r'[\w\.\-]+@[\w\.\-]+\.\w+', answer)
        tv["extracted_phone"] = phones[0] if phones else ""
        tv["extracted_email"] = emails[0] if emails else ""
        # Also scan result contents
        for r in tv.get("results", []):
            content = r.get("content", "")
            if not tv["extracted_phone"]:
                p = re.findall(r'\+?1?\s*[\(\-]?\d{3}[\)\-\s]*\d{3}[\-\s]*\d{4}', content)
                if p:
                    tv["extracted_phone"] = p[0]
            if not tv["extracted_email"]:
                e = re.findall(r'[\w\.\-]+@[\w\.\-]+\.\w+', content)
                if e:
                    tv["extracted_email"] = e[0]
        report["found"] = tv
        report["primary_source"] = "tavily"
        report["confidence"] = "medium"
        return report
    else:
        report["tavily_error"] = tv["error"]

    # 3. DuckDuckGo (FREE FALLBACK)
    logger.info(f"[Scout] DuckDuckGo fallback: {query}")
    ddg = await _ddg_search(f"{query} phone number email website")
    report["sources_tried"].append("duckduckgo")

    if not ddg.get("error"):
        report["found"] = ddg
        report["primary_source"] = "duckduckgo"
        report["confidence"] = "low"
        return report
    else:
        report["ddg_error"] = ddg["error"]

    report["error"] = "All scout sources failed"
    report["confidence"] = "none"

    # 4. Dark Scout fallback — deep OSINT investigation when primary chain fails.
    # Triggered only when confidence would be < 0.7 ('low' or 'none').
    try:
        from services.dark_scout_service import run_investigation
        logger.info(f"[Scout] Dark Scout OSINT fallback for: {query}")
        report["sources_tried"].append("dark_scout")
        ds = await run_investigation(query=query, preset="brand_monitor", max_results=10)
        if ds and not ds.get("error"):
            report["found"] = {
                "source": "dark_scout",
                "business_name": name,
                "summary": (ds.get("analysis") or {}).get("summary", "")[:500],
                "urls": [r.get("url") for r in (ds.get("results") or [])[:5] if r.get("url")],
                "raw": ds,
            }
            report["primary_source"] = "dark_scout"
            report["confidence"] = "medium"
            report.pop("error", None)
            # Log fallback usage
            await _fb_log_scout(used="dark_scout", result="fallback", reason="primary_chain_low_confidence")
    except Exception as e:
        logger.warning(f"[Scout] Dark Scout fallback error: {e}")
        report["dark_scout_error"] = str(e)[:200]

    return report


async def _fb_log_scout(used: str, result: str = "fallback", reason: str = None) -> None:
    """Log scout fallback to fallback_usage_log (silent)."""
    try:
        from services.fallback_monitor import log_fallback
        db = _get_db()
        await log_fallback(db, service="scout", primary="google_places",
                           used=used, result=result, reason=reason)
    except Exception:
        pass


async def scout_business_full(name: str, location: str = "") -> Dict:
    """
    Full scout: run ALL sources and merge results for maximum coverage.
    """
    query = f"{name} {location}".strip()
    report = {"query": query, "sources": {}}

    # Run all in parallel
    import asyncio
    gp_task = _google_places_search(query)
    tv_task = _tavily_search(f"{query} phone number email website hours")
    ddg_task = _ddg_search(f"{query} phone email website reviews")

    gp, tv, ddg = await asyncio.gather(gp_task, tv_task, ddg_task, return_exceptions=True)

    if not isinstance(gp, Exception) and not gp.get("error"):
        report["sources"]["google_places"] = gp
    if not isinstance(tv, Exception) and not tv.get("error"):
        # Extract phone/email from Tavily answer
        import re
        answer = tv.get("answer", "")
        all_content = answer + " ".join(r.get("content", "") for r in tv.get("results", []))
        phones = re.findall(r'\+?1?\s*[\(\-]?\d{3}[\)\-\s]*\d{3}[\-\s]*\d{4}', all_content)
        emails = re.findall(r'[\w\.\-]+@[\w\.\-]+\.\w+', all_content)
        tv["extracted_phone"] = phones[0] if phones else ""
        tv["extracted_email"] = emails[0] if emails else ""
        report["sources"]["tavily"] = tv
    if not isinstance(ddg, Exception) and not ddg.get("error"):
        report["sources"]["duckduckgo"] = ddg

    # Merge: Google Places is ground truth, augment with Tavily/DDG
    merged = {}
    if "google_places" in report["sources"]:
        merged = {**report["sources"]["google_places"]}
        merged["confidence"] = "high"
    elif "tavily" in report["sources"]:
        tv_data = report["sources"]["tavily"]
        merged = {
            "source": "tavily",
            "answer": tv_data.get("answer", ""),
            "phone": tv_data.get("extracted_phone", ""),
            "email": tv_data.get("extracted_email", ""),
            "confidence": "medium",
        }
    elif "duckduckgo" in report["sources"]:
        merged = {**report["sources"]["duckduckgo"]}
        merged["confidence"] = "low"

    report["merged"] = merged
    report["sources_count"] = len(report["sources"])
    return report
