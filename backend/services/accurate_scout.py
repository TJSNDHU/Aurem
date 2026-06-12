"""
AUREM Accurate Business Intelligence Scout
===========================================
Multi-source verification — runs ALL sources in parallel and computes
consensus-based confidence scoring per field (phone / email / address).

Channel gating: Campaign HQ uses `should_send_campaign()` to block
outreach on LOW-confidence fields (never call a wrong number).

Sources:
  ✅ Google Places       (services.business_scout — primary)
  ✅ Tavily              (web search)
  ✅ DuckDuckGo          (free fallback)
  ✅ Firecrawl           (official website contact-page scrape)
  ✅ YellowPages (CA/US) (directory scrape)
  ✅ 411 (CA/US)         (phone directory scrape)
  ⚠️  BBB (CA/US)         (directory — often 403, best-effort)
  ⚠️  Ontario Biz Registry (bot-protected — best-effort)

Output: a `VerifiedBusiness` dict + written to `verified_lead_profile`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import httpx

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
PHONE_RE = re.compile(r"\+?1?\s*[\(\-]?(\d{3})[\)\-\s\.]*(\d{3})[\-\s\.]*(\d{4})")
EMAIL_RE = re.compile(r"\b[\w\.\-]+@[\w\.\-]+\.\w+\b")

CONTACT_PATHS = [
    "/contact", "/contact-us", "/contact_us",
    "/about", "/about-us", "/reach-us", "/get-in-touch",
]


def _firecrawl_key() -> str:
    return os.environ.get("FIRECRAWL_API_KEY", "").strip()


def _tavily_key() -> str:
    return os.environ.get("TAVILY_API_KEY", "").strip()


def _normalize_phone(raw: str) -> str:
    """Normalize any phone string to +1NXXXXXXXXX E.164."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    return ""


def _extract_phone(text: str) -> Optional[str]:
    if not text:
        return None
    m = PHONE_RE.search(text)
    if m:
        return _normalize_phone("".join(m.groups()))
    return None


def _extract_email(text: str) -> Optional[str]:
    if not text:
        return None
    m = EMAIL_RE.search(text)
    if m:
        email = m.group(0).lower()
        # skip common image-url false positives
        if email.endswith((".png", ".jpg", ".gif", ".webp")):
            return None
        return email
    return None


# ─────────────────────────────────────────────────────────────
# SOURCE 1: Firecrawl website contact-page scrape
# ─────────────────────────────────────────────────────────────
async def _firecrawl_scrape(url: str, timeout: int = 20) -> Dict[str, Any]:
    """Scrape a single URL via Firecrawl. Returns {content, title, success}."""
    # iter 301: hard cap to SCOUT_TIMEOUT (default 30s) — prevents hangs on slow primary
    import os as _os
    _max_t = int(_os.environ.get("SCOUT_TIMEOUT", "30"))
    timeout = min(int(timeout), _max_t)
    key = _firecrawl_key()
    if not key:
        return {"error": "firecrawl_not_configured"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"url": url, "formats": ["markdown", "html"], "onlyMainContent": True},
            )
        if not resp.is_success:
            return {"error": f"firecrawl_{resp.status_code}"}
        data = resp.json()
        if not data.get("success"):
            return {"error": data.get("error", "firecrawl_failed")}
        return {
            "content": (data.get("data", {}) or {}).get("markdown", "")[:5000],
            "html": (data.get("data", {}) or {}).get("html", "")[:5000],
            "success": True,
        }
    except Exception as e:
        return {"error": str(e)[:200]}


async def verify_website_contact(website_url: str) -> Dict[str, Any]:
    """
    Walk common contact paths on the business website. Returns first-found
    phone/email. Confidence = HIGH when data appears on a /contact-style page.
    """
    if not website_url:
        return {"source": "website", "phone": "", "email": "", "address": "",
                "confidence": "none", "reason": "no_website"}
    website_url = website_url.rstrip("/")

    # Try homepage first (quickest), then contact paths
    pages_to_try = [website_url] + [website_url + p for p in CONTACT_PATHS]
    for page in pages_to_try:
        result = await _firecrawl_scrape(page, timeout=15)
        if result.get("error"):
            continue
        content = result.get("content", "") + " " + result.get("html", "")
        phone = _extract_phone(content)
        email = _extract_email(content)
        if phone or email:
            return {
                "source": "website",
                "url_used": page,
                "phone": phone or "",
                "email": email or "",
                "address": "",
                "confidence": "high",  # business's own site is ground truth
            }
    return {"source": "website", "phone": "", "email": "", "address": "",
            "confidence": "none", "reason": "no_contact_found"}


# ─────────────────────────────────────────────────────────────
# SOURCE 2: YellowPages (CA + US)
# ─────────────────────────────────────────────────────────────
async def _scrape_yellowpages(business_name: str, city: str, country: str = "ca") -> Dict[str, Any]:
    """Search yellowpages.ca or yellowpages.com and pull the first business card."""
    if country == "ca":
        search_url = (
            f"https://www.yellowpages.ca/search/si/1/"
            f"{quote_plus(business_name)}/{quote_plus(city)}"
        )
    else:
        search_url = (
            f"https://www.yellowpages.com/search?"
            f"search_terms={quote_plus(business_name)}"
            f"&geo_location_terms={quote_plus(city)}"
        )

    page = await _firecrawl_scrape(search_url, timeout=18)
    if page.get("error"):
        return {"source": f"yellowpages_{country}", "error": page["error"]}

    content = page.get("content", "") + " " + page.get("html", "")
    phone = _extract_phone(content)
    email = _extract_email(content)
    # Loose address extraction — first line containing a postal-ish pattern
    address_match = re.search(
        r"([0-9]{1,5}\s+[A-Za-z][^,\n]{3,50}"
        r"(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Boulevard|Blvd|Crescent|Cres|Way|Court|Ct|Place|Pl)\.?"
        r"[^,\n]{0,40})",
        content, re.IGNORECASE)
    address = address_match.group(1).strip() if address_match else ""

    return {
        "source": f"yellowpages_{country}",
        "phone": phone or "",
        "email": email or "",
        "address": address,
        "confidence": "high" if phone else "low",
    }


# ─────────────────────────────────────────────────────────────
# SOURCE 3: 411 (CA + US)
# ─────────────────────────────────────────────────────────────
async def _scrape_411(business_name: str, city: str, country: str = "ca") -> Dict[str, Any]:
    """Scrape 411.ca or 411.com search results."""
    base = "https://411.ca" if country == "ca" else "https://www.411.com"
    url = f"{base}/business/?q={quote_plus(business_name)}&location={quote_plus(city)}"
    page = await _firecrawl_scrape(url, timeout=15)
    if page.get("error"):
        return {"source": f"411_{country}", "error": page["error"]}
    content = page.get("content", "") + " " + page.get("html", "")
    phone = _extract_phone(content)
    return {
        "source": f"411_{country}",
        "phone": phone or "",
        "email": "",
        "address": "",
        "confidence": "medium" if phone else "low",
    }


# ─────────────────────────────────────────────────────────────
# SOURCE 4: BBB (best-effort, frequently blocked)
# ─────────────────────────────────────────────────────────────
async def _scrape_bbb(business_name: str, city: str, country: str = "ca") -> Dict[str, Any]:
    """BBB profile scrape. Often 403/Cloudflare — best effort."""
    base = "https://www.bbb.org/ca" if country == "ca" else "https://www.bbb.org"
    url = f"{base}/search?find_text={quote_plus(business_name)}&find_loc={quote_plus(city)}"
    page = await _firecrawl_scrape(url, timeout=15)
    if page.get("error"):
        return {"source": f"bbb_{country}", "error": page["error"]}
    content = page.get("content", "") + " " + page.get("html", "")
    phone = _extract_phone(content)
    rating = None
    m = re.search(r"\b(A\+|A-|A|B\+|B-|B|C\+|C-|C|F)\s*(?:Rating|BBB)", content)
    if m:
        rating = m.group(1)
    return {
        "source": f"bbb_{country}",
        "phone": phone or "",
        "email": "",
        "address": "",
        "bbb_rating": rating,
        "confidence": "medium" if phone else "low",
    }


# ─────────────────────────────────────────────────────────────
# SOURCE 5: Ontario Business Registry (best-effort)
# ─────────────────────────────────────────────────────────────
async def _verify_ontario_registry(business_name: str) -> Dict[str, Any]:
    """
    Attempt to verify registration via the public ONBIS search page.
    ONBIS is behind heavy anti-bot — this is best-effort; Firecrawl may fail.
    """
    url = (
        "https://www.appmybizaccount.gov.on.ca/onbis/businessnamesearch/"
        f"?initialSearch={quote_plus(business_name)}"
    )
    page = await _firecrawl_scrape(url, timeout=20)
    if page.get("error"):
        return {"source": "ontario_registry", "verified": False, "error": page["error"]}
    content = page.get("content", "")
    # Look for "Active" / "Inactive" / Business Identification Number (BIN)
    active = bool(re.search(r"\bActive\b", content, re.IGNORECASE))
    bin_match = re.search(r"\b(\d{9,10})\b", content)
    return {
        "source": "ontario_registry",
        "verified": active,
        "status": "Active" if active else "unknown",
        "registration_number": bin_match.group(1) if bin_match else None,
    }


# ─────────────────────────────────────────────────────────────
# PARALLEL ORCHESTRATOR
# ─────────────────────────────────────────────────────────────
async def full_business_verify(
    business_name: str,
    city: str,
    country: str = "ca",
    website_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run ALL sources in parallel and consolidate into a verified profile.

    Returns:
        {
          "business_name": str,
          "city": str,
          "verified_at": ISO datetime,
          "sources": [ ... raw per-source results ... ],
          "consolidated": {
            "phone": {"value": "+1...", "confidence": "HIGH", "sources": [...], "source_count": 3},
            "email": {...},
            "address": {...},
          },
          "government_verified": bool,
          "registration_number": str | None,
          "bbb_rating": str | None,
          "channel_gating": {
            "call": True/False,
            "sms": True/False,
            "email": True/False,
            "whatsapp": True/False,
          }
        }
    """
    started = datetime.now(timezone.utc)
    # Phase 1: Google Places + Tavily + DDG via existing business_scout
    from services.business_scout import scout_business_full
    scout_task = scout_business_full(business_name, city)

    # Phase 2: Directory/registry sources in parallel
    tasks = [
        scout_task,
        _scrape_yellowpages(business_name, city, country),
        _scrape_411(business_name, city, country),
        _scrape_bbb(business_name, city, country),
    ]
    if country == "ca":
        tasks.append(_verify_ontario_registry(business_name))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    scout = results[0] if not isinstance(results[0], Exception) else {"sources": {}}
    directory_results = [r for r in results[1:] if not isinstance(r, Exception)]

    sources: List[Dict[str, Any]] = []

    # Normalize scout sub-sources (Google Places / Tavily / DDG)
    gp = (scout.get("sources") or {}).get("google_places") or {}
    if gp:
        sources.append({
            "source": "google_places",
            "phone": _normalize_phone(gp.get("phone", "")),
            "email": gp.get("email", ""),
            "address": gp.get("address", ""),
            "website": gp.get("website", ""),
            "rating": gp.get("rating"),
            "confidence": "high",
        })
    tv = (scout.get("sources") or {}).get("tavily") or {}
    if tv:
        sources.append({
            "source": "tavily",
            "phone": _normalize_phone(tv.get("extracted_phone", "")),
            "email": tv.get("extracted_email", ""),
            "address": "",
            "confidence": "medium",
        })
    ddg = (scout.get("sources") or {}).get("duckduckgo") or {}
    if ddg:
        sources.append({
            "source": "duckduckgo",
            "phone": _normalize_phone(ddg.get("phone", "")),
            "email": ddg.get("email", ""),
            "address": ddg.get("address", ""),
            "confidence": "low",
        })
    # Directory sources
    for d in directory_results:
        if d.get("error"):
            continue  # keep silent on scrape errors (frequent)
        if d.get("source", "").startswith("ontario_registry"):
            continue  # handled separately
        sources.append({
            "source": d.get("source", ""),
            "phone": _normalize_phone(d.get("phone", "")),
            "email": d.get("email", ""),
            "address": d.get("address", ""),
            "bbb_rating": d.get("bbb_rating"),
            "confidence": d.get("confidence", "low"),
        })

    # Phase 3: Website contact-page scrape (highest trust when available)
    website = gp.get("website") or website_url or ""
    if website:
        site = await verify_website_contact(website)
        if not site.get("error"):
            sources.append({
                "source": "website",
                "phone": _normalize_phone(site.get("phone", "")),
                "email": site.get("email", ""),
                "address": "",
                "confidence": site.get("confidence", "none"),
                "url_used": site.get("url_used", ""),
            })

    # Government verification
    gov_result = next((r for r in directory_results
                       if isinstance(r, dict) and r.get("source") == "ontario_registry"), {})

    # Phase 4: consolidate each field
    consolidated = {
        "phone": _consolidate_field("phone", sources),
        "email": _consolidate_field("email", sources),
        "address": _consolidate_field("address", sources),
    }

    # Phase 5: channel gating
    channel_gating = _compute_channel_gating(consolidated)

    return {
        "business_name": business_name,
        "city": city,
        "country": country,
        "website": website,
        "verified_at": started.isoformat(),
        "elapsed_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        "sources_used": [s["source"] for s in sources],
        "sources": sources,
        "consolidated": consolidated,
        "government_verified": bool(gov_result.get("verified")),
        "registration_number": gov_result.get("registration_number"),
        "registration_status": gov_result.get("status", "unknown"),
        "bbb_rating": next((s.get("bbb_rating") for s in sources if s.get("bbb_rating")), None),
        "channel_gating": channel_gating,
    }


# ─────────────────────────────────────────────────────────────
# CONSENSUS ENGINE
# ─────────────────────────────────────────────────────────────
def _consolidate_field(field: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Consensus: group non-empty values, pick the one with most source agreement,
    weighted by source-level confidence.
    """
    values: Dict[str, Dict[str, Any]] = {}   # normalized_value → {count, sources, weight}
    CONF_W = {"high": 3, "medium": 2, "low": 1, "none": 0}

    for s in sources:
        raw = (s.get(field) or "").strip()
        if not raw:
            continue
        # Normalize keys — phone/email lowercase
        key = raw.lower() if field == "email" else raw
        w = CONF_W.get(s.get("confidence", "low"), 1)
        if key not in values:
            values[key] = {"value": raw, "count": 0, "sources": [], "weight": 0}
        values[key]["count"] += 1
        values[key]["sources"].append(s["source"])
        values[key]["weight"] += w

    if not values:
        return {"value": "", "confidence": "NONE", "sources": [], "source_count": 0}

    # Pick the winner: highest weight, tie-break on count
    winner = max(values.values(), key=lambda v: (v["weight"], v["count"]))
    total_sources = sum(1 for s in sources if s.get(field))
    agreement_ratio = winner["count"] / max(total_sources, 1)

    # Confidence classification
    if winner["count"] >= 3 or (winner["weight"] >= 6 and agreement_ratio >= 0.6):
        conf = "HIGH"
    elif winner["count"] >= 2 or agreement_ratio >= 0.5:
        conf = "MEDIUM"
    else:
        conf = "LOW"

    # Edge-case: single-source but came from website or google_places → promote to MEDIUM
    if conf == "LOW" and winner["count"] == 1:
        if "website" in winner["sources"] or "google_places" in winner["sources"]:
            conf = "MEDIUM"

    return {
        "value": winner["value"],
        "confidence": conf,
        "sources": winner["sources"],
        "source_count": winner["count"],
        "agreement_ratio": round(agreement_ratio, 2),
    }


def _compute_channel_gating(consolidated: Dict[str, Any]) -> Dict[str, bool]:
    """
    Campaign-gate rules (iter 295 — decoupled per-channel risk model):
      - call:     phone HIGH or MEDIUM (Twilio voice — no A2P required)
      - sms:      phone HIGH (US/CA carriers require A2P 10DLC for B2B SMS)
      - email:    email present at any confidence (CASL low-risk channel)
      - whatsapp: phone HIGH or MEDIUM (Meta-approved templates only)

    Email opens at LOW because:
      1. CASL implied-consent applies to publicly listed B2B contacts.
      2. Resend deliverability self-protects via reputation throttling.
      3. Hard-gating email kills 80%+ of cold outreach when only 1 source
         confirms the address.
    """
    phone_c = (consolidated.get("phone") or {}).get("confidence", "NONE")
    email_c = (consolidated.get("email") or {}).get("confidence", "NONE")
    email_value = ((consolidated.get("email") or {}).get("value") or "").strip()
    return {
        "call":     phone_c in ("HIGH", "MEDIUM"),
        "sms":      phone_c == "HIGH",
        "email":    bool(email_value) or email_c in ("HIGH", "MEDIUM", "LOW"),
        "whatsapp": phone_c in ("HIGH", "MEDIUM"),
    }


def should_send_campaign(channel: str, verified: Dict[str, Any]) -> bool:
    """Public helper — returns True only if this channel has sufficient confidence."""
    return bool((verified.get("channel_gating") or {}).get(channel, False))


# ─────────────────────────────────────────────────────────────
# PERSISTENCE
# ─────────────────────────────────────────────────────────────
async def save_verified_profile(db, lead_id: str, verified: Dict[str, Any]) -> None:
    """Persist to `verified_lead_profile` and stamp the lead."""
    if db is None:
        return
    try:
        doc = {**verified, "lead_id": lead_id}
        await db.verified_lead_profile.update_one(
            {"lead_id": lead_id}, {"$set": doc}, upsert=True
        )
        await db.campaign_leads.update_one(
            {"lead_id": lead_id, "business_id": FOUNDER_BIN},
            {"$set": {
                "verification": {
                    "verified_at": verified["verified_at"],
                    "phone_confidence": (verified.get("consolidated", {}).get("phone") or {}).get("confidence"),
                    "email_confidence": (verified.get("consolidated", {}).get("email") or {}).get("confidence"),
                    "channel_gating": verified.get("channel_gating"),
                    "government_verified": verified.get("government_verified"),
                    "source_count": len(verified.get("sources_used", [])),
                },
            }},
        )
        # Iter 304 — auto-fire real website audit if lead has a website.
        # Iter 306 — if NO website, fire social presence check instead.
        # Both fire-and-forget so verification isn't slowed down.
        try:
            lead = await db.campaign_leads.find_one(
                {"lead_id": lead_id, "business_id": FOUNDER_BIN},
                {"_id": 0, "website_url": 1, "website": 1, "audit_score": 1,
                 "business_name": 1, "city": 1, "social_score": 1},
            ) or {}
            site = (lead.get("website_url") or lead.get("website") or "").strip()
            if site and not lead.get("audit_score"):
                asyncio.create_task(_run_lead_audit(db, lead_id, site))
            elif not site and lead.get("social_score") is None:
                asyncio.create_task(_run_social_audit(
                    db, lead_id,
                    lead.get("business_name") or "",
                    lead.get("city") or "",
                ))
        except Exception as e:
            logger.warning(f"[AccurateScout] audit hook skipped: {e}")
    except Exception as e:
        logger.warning(f"[AccurateScout] Failed to persist verified profile: {e}")


async def _run_lead_audit(db, lead_id: str, website: str) -> None:
    """Background task: real audit + stamp lead with score + flags."""
    try:
        from services.website_audit_service import real_audit
        import uuid as _u
        audit = await real_audit(website)
        if not audit.get("ok"):
            return
        scan_id = f"scan_{_u.uuid4().hex[:12]}"
        doc = {
            "scan_id": scan_id, "lead_id": lead_id, "website": audit["url"],
            "ssl": audit["ssl"], "pagespeed": audit["pagespeed"],
            "mobile": audit["mobile"], "broken_links": audit["broken_links"],
            "contact_form": audit["contact_form"],
            "social_links": audit["social_links"],
            "copyright_year": audit["copyright_year"],
            "google_maps": audit["google_maps"],
            "score_breakdown": audit["score_breakdown"],
            "overall_score": audit["overall_score"],
            "score": audit["overall_score"],
            "issues": audit["issues"],
            "repair_recommended": audit["repair_recommended"],
            "rebuild_recommended": audit["rebuild_recommended"],
            "created_at": audit["finished_at"],
            "source": "scout_auto_audit",
        }
        await db.customer_scans.insert_one(doc)
        await db.campaign_leads.update_one(
            {"lead_id": lead_id, "business_id": FOUNDER_BIN},
            {"$set": {
                "audit_score": audit["overall_score"],
                "audit_id": scan_id,
                "audit_at": audit["finished_at"],
                "repair_recommended": audit["repair_recommended"],
                "rebuild_recommended": audit["rebuild_recommended"],
            }},
        )
        logger.info(f"[scout-audit] lead={lead_id} score={audit['overall_score']} "
                    f"repair={audit['repair_recommended']}")
        # Iter 307 — also extract design tokens for AWB visual continuity
        try:
            from services.design_extractor import extract_design
            design = await extract_design(audit["url"], db=db)
            if design.get("ok"):
                await db.campaign_leads.update_one(
                    {"lead_id": lead_id, "business_id": FOUNDER_BIN},
                    {"$set": {"design_tokens": {
                        "extraction_success": True,
                        "extracted_at": design["extracted_at"],
                        "source_url": design["source_url"],
                        "data": {k: v for k, v in design.items() if k != "raw_files"},
                    }}},
                )
                logger.info(f"[scout-design] lead={lead_id} score={design.get('score')}")
        except Exception as e:
            logger.warning(f"[scout-design] lead={lead_id} extract failed: {e}")
    except Exception as e:
        logger.warning(f"[scout-audit] lead={lead_id} failed: {e}")



async def _run_social_audit(db, lead_id: str, business_name: str,
                              city: str = "") -> None:
    """Iter 306 — Sherlock-style social presence check for website-less leads.
    Stamps lead with social_profiles, social_score, website_builder_eligible."""
    if not business_name:
        return
    try:
        from services.social_presence_checker import (
            check_social_presence, classify_lead,
        )
        from datetime import datetime as _dt, timezone as _tz
        res = await check_social_presence(business_name, city or None)
        priority = classify_lead(False, res["social_score"])
        await db.campaign_leads.update_one(
            {"lead_id": lead_id, "business_id": FOUNDER_BIN},
            {"$set": {
                "social_profiles": res["social_profiles"],
                "social_score": res["social_score"],
                "social_usernames_tried": res["usernames_tried"],
                "social_audit_at": _dt.now(_tz.utc).isoformat(),
                "website_builder_eligible": (priority == "A"),
                "lead_priority": priority,
            }},
        )
        logger.info(f"[scout-social] lead={lead_id} score={res['social_score']}/"
                    f"{len(res['social_profiles'])} priority={priority} "
                    f"probes={res['probes']}")
    except Exception as e:
        logger.warning(f"[scout-social] lead={lead_id} failed: {e}")
