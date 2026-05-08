"""
PRD Auto-Fill — iter 282al-8 (Prompt 11).

Given a lead, produce a structured PRD that the Auto Website Builder uses to
generate a *highly personalised* demo site. The PRD merges three signal
sources:

  1. Lead data already in `campaign_leads` (Yelp/Google/OSM scout dump).
  2. Industry slang context (`services/industry_slang.py`) — pain points,
     services, trust signals, customer search terms.
  3. Webclaw scan / OG metadata (when present in `lead.scan` / `lead.og`).

Output schema (kept stable so the builder can rely on it):

    {
      "business_name":   str,
      "tagline":         str,
      "city":            str,
      "province":        str,
      "phone":           str,
      "email":           str,
      "category":        str,
      "services":        [{"name": str, "description": str}, ...],
      "hours":           str | None,
      "trust_bullets":   [str, str, str],
      "color_scheme":    {"primary": "#...", "accent": "#..."},
      "industry_terms":  [str, ...],
      "canadian_signals":[str, ...],
      "search_terms":    [str, ...],
      "urgency_hook":    str,
      "credibility_note":str,
      "source_signals":  {"used_industry": bool, "used_scan": bool, ...}
    }

Pure Python — no LLM call. The builder feeds this PRD into its existing
LLM prompt as additional grounding so the LLM stops inventing services and
starts using *real* trade-specific language.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Canadian per-category color schemes
# ─────────────────────────────────────────────────────────────────────
CATEGORY_COLOR_SCHEMES: dict[str, dict[str, str]] = {
    "plumber":     {"primary": "#0E7CCC", "accent": "#FFB800"},
    "hvac":        {"primary": "#D63B1F", "accent": "#1F2937"},
    "electrician": {"primary": "#1F2937", "accent": "#FFB800"},
    "roofer":      {"primary": "#5B3A1A", "accent": "#C9A84C"},
    "auto":        {"primary": "#0F0F0F", "accent": "#E63946"},
    "salon":       {"primary": "#8B1E5B", "accent": "#F0C0D0"},
    "dental":      {"primary": "#0E9488", "accent": "#F5F5F5"},
    "law":         {"primary": "#1A2B4A", "accent": "#C9A84C"},
    "restaurant":  {"primary": "#A23919", "accent": "#F2C57C"},
    "general":     {"primary": "#FF6B00", "accent": "#C9A84C"},
}


CANADIAN_TRUST_BANK = [
    "Licensed & insured in Ontario",
    "WSIB-covered crew",
    "Family-owned, locally operated",
    "Transparent flat-rate pricing",
    "Same-day & emergency service available",
    "Backed by a written labour warranty",
    "Canadian-trained technicians",
    "TSSA-certified work where applicable",
]


def _norm_phone(p: str) -> str:
    if not p:
        return ""
    digits = re.sub(r"\D+", "", str(p))
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return str(p).strip()


def _category_key(cat: str) -> str:
    c = (cat or "").lower()
    for key in CATEGORY_COLOR_SCHEMES:
        if key in c:
            return key
    return "general"


def _build_tagline(biz: str, city: str, cat: str) -> str:
    cat = (cat or "").lower()
    if "plumb" in cat:
        return f"Trusted plumbing in {city or 'your neighbourhood'} — fast, fair, fully insured."
    if "hvac" in cat or "heating" in cat or "cooling" in cat:
        return f"{city or 'Local'} HVAC done right — same-day service, no surprises."
    if "electric" in cat:
        return f"Licensed electricians serving {city or 'the area'} — code-compliant, on-time, on-budget."
    if "roof" in cat:
        return f"{city or 'Local'} roofing you can trust — written warranty, transparent quote."
    if "auto" in cat or "mechanic" in cat or "collision" in cat:
        return f"{city or 'Local'} auto care — honest diagnostics, factory-spec repairs."
    if "salon" in cat or "hair" in cat or "beauty" in cat:
        return f"{biz or 'Your local salon'} — modern style with a neighbourhood feel."
    if "dental" in cat or "dentist" in cat:
        return f"Gentle, modern dentistry in {city or 'your community'} — direct insurance billing."
    if "law" in cat:
        return "Local counsel you can talk to — flat-fee transparency, fast turnaround."
    if "restaurant" in cat or "cafe" in cat or "bistro" in cat:
        return f"{biz or 'Where {city} eats'} — fresh daily, locally sourced."
    return f"{biz or 'Local experts'} in {city or 'your area'} — Canadian-built, trades-trusted."


def _build_services(biz: str, category: str,
                     industry: dict[str, Any]) -> list[dict[str, str]]:
    """Use industry_slang services if it provides 3+ entries, else fall
    back to the category library. Returns 3-6 entries shaped for the
    builder."""
    raw = industry.get("services") if industry else None
    if raw and isinstance(raw, list) and len(raw) >= 3:
        out = []
        for s in raw[:6]:
            if isinstance(s, dict) and s.get("name"):
                out.append({
                    "name": s["name"],
                    "description": s.get("description")
                                    or f"Professional {s['name'].lower()} for "
                                       f"{biz or 'your home'}.",
                })
            elif isinstance(s, str):
                out.append({
                    "name": s,
                    "description": (
                        f"Professional {s.lower()} for {biz or 'your home'}."
                    ),
                })
        if len(out) >= 3:
            return out

    cat = (category or "").lower()
    if "plumb" in cat:
        return [
            {"name": "Emergency Plumbing", "description": "24/7 burst-pipe, leak, and drain response — same-day arrival."},
            {"name": "Drain Cleaning", "description": "Camera-inspected, root-cause cleared, no recurring callbacks."},
            {"name": "Fixture Installation", "description": "Faucets, toilets, and water heaters — manufacturer-spec installs."},
            {"name": "Renovation Rough-In", "description": "Permit-ready plumbing for kitchen and bath remodels."},
            {"name": "Inspection Reports", "description": "Pre-purchase and insurance-grade plumbing inspections."},
        ]
    if "hvac" in cat or "heating" in cat:
        return [
            {"name": "Furnace Repair", "description": "No-heat emergencies handled same-day, all major brands."},
            {"name": "AC Installation", "description": "ENERGY STAR units sized to your home — zero-pressure quote."},
            {"name": "Heat Pump Conversion", "description": "Greener Homes-eligible installs with rebate paperwork done."},
            {"name": "Tune-up & Maintenance", "description": "Seasonal check-ups that stop breakdowns before they start."},
            {"name": "Indoor Air Quality", "description": "HEPA, UV, and humidifier solutions for healthier homes."},
        ]
    if "electric" in cat:
        return [
            {"name": "Panel Upgrades", "description": "100A → 200A swaps with ESA inspection coordinated."},
            {"name": "EV Charger Install", "description": "Level-2 home chargers, rebate paperwork included."},
            {"name": "Lighting Retrofit", "description": "LED conversions and pot-light installs that pass inspection."},
            {"name": "Emergency Service", "description": "No-power and burning-smell calls answered around the clock."},
            {"name": "Renovation Wiring", "description": "Permit-pulled rough-in for additions and basements."},
        ]
    return [
        {"name": "Quality Service",  "description": "Craftsmanship and attention to detail on every job."},
        {"name": "Local Expertise",  "description": "Family-owned and operated in the community we serve."},
        {"name": "Transparent Pricing", "description": "Upfront quotes — no surprises, no hidden fees."},
        {"name": "Free Estimates",   "description": "Bring us your project — we'll price it for free."},
    ]


def _trust_bullets(industry: dict[str, Any]) -> list[str]:
    pool = list(CANADIAN_TRUST_BANK)
    sigs = (industry or {}).get("trust_signals") or []
    if isinstance(sigs, list):
        for s in sigs:
            if isinstance(s, str) and s and s not in pool:
                pool.insert(0, s)
    return pool[:3]


# ─────────────────────────────────────────────────────────────────────
# Public — auto_fill_prd
# ─────────────────────────────────────────────────────────────────────
def auto_fill_prd(lead: dict[str, Any]) -> dict[str, Any]:
    """Build a full PRD for one lead. Pure function — no I/O, no LLM."""
    lead = lead or {}

    biz = (lead.get("business_name") or "").strip() or "Local Business"
    city = (lead.get("city") or "").strip()
    province = (lead.get("province") or "ON").strip() or "ON"
    category = (lead.get("category") or "general").strip() or "general"
    phone = _norm_phone(lead.get("phone") or "")
    email = (lead.get("email") or "").strip()
    hours = lead.get("hours") or lead.get("opening_hours") or None

    industry: dict[str, Any] = {}
    try:
        from services.industry_slang import get_industry_context
        industry = get_industry_context(category) or {}
    except Exception as e:
        logger.debug(f"[prd_autofill] industry_slang skipped: {e}")
        industry = {}

    services = _build_services(biz, category, industry)
    trust = _trust_bullets(industry)
    color = CATEGORY_COLOR_SCHEMES[_category_key(category)]
    tagline = _build_tagline(biz, city, category)

    industry_terms: list[str] = []
    for k in ("pain_points", "services", "search_terms"):
        v = industry.get(k) or []
        if isinstance(v, list):
            for item in v[:5]:
                if isinstance(item, str) and item:
                    industry_terms.append(item)
                elif isinstance(item, dict) and item.get("name"):
                    industry_terms.append(item["name"])
    # Cap at 12 unique terms.
    seen: set[str] = set()
    industry_terms = [
        t for t in industry_terms
        if not (t.lower() in seen or seen.add(t.lower()))
    ][:12]

    canadian_signals = [
        "Canadian-owned & operated",
        f"Serving {city or 'Ontario'} since 2024",
        "CASL-compliant outreach",
    ]

    prd = {
        "business_name": biz,
        "tagline": tagline,
        "city": city,
        "province": province,
        "phone": phone,
        "email": email,
        "category": category,
        "services": services,
        "hours": hours,
        "trust_bullets": trust,
        "color_scheme": color,
        "industry_terms": industry_terms,
        "canadian_signals": canadian_signals,
        "search_terms": (industry.get("search_terms") or [])[:5],
        "urgency_hook": industry.get("urgency_hook") or "",
        "credibility_note": industry.get("credibility_note") or "",
        "source_signals": {
            "used_industry": bool(industry),
            "used_scan": bool(lead.get("scan") or lead.get("og")),
            "has_phone": bool(phone),
            "has_email": bool(email),
        },
    }
    return prd


def prd_summary_for_llm(prd: dict[str, Any]) -> str:
    """Render the PRD as a compact, LLM-friendly text block. Used by the
    Auto Website Builder to ground the LLM in real lead data instead of
    hallucinating services."""
    if not prd:
        return ""
    svc_list = "; ".join(
        f"{s['name']} — {s['description']}"
        for s in (prd.get("services") or [])[:6]
        if isinstance(s, dict) and s.get("name")
    )
    trust = "; ".join(prd.get("trust_bullets") or [])
    terms = ", ".join(prd.get("industry_terms") or [])
    return (
        "AUTO-FILLED PRD (use these as ground truth — do NOT invent):\n"
        f"  • Business: {prd.get('business_name')}\n"
        f"  • Tagline: {prd.get('tagline')}\n"
        f"  • Location: {prd.get('city')}, {prd.get('province')}\n"
        f"  • Category: {prd.get('category')}\n"
        f"  • Phone: {prd.get('phone') or 'n/a'} | Email: {prd.get('email') or 'n/a'}\n"
        f"  • Services: {svc_list or 'category defaults'}\n"
        f"  • Trust signals: {trust}\n"
        f"  • Industry terms (weave naturally): {terms}\n"
        f"  • Urgency angle: {prd.get('urgency_hook') or 'standard'}\n"
        f"  • Insider note: {prd.get('credibility_note') or 'n/a'}\n"
        f"  • Brand colours: primary {prd.get('color_scheme', {}).get('primary')} "
        f"/ accent {prd.get('color_scheme', {}).get('accent')}\n"
        f"  • Canadian signals: {', '.join(prd.get('canadian_signals') or [])}"
    )


__all__ = [
    "auto_fill_prd",
    "prd_summary_for_llm",
    "CATEGORY_COLOR_SCHEMES",
    "CANADIAN_TRUST_BANK",
]
