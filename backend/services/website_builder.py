"""
AUREM Auto Website Builder
==========================
Generates a production-ready sample website for any scouted business.
Fully automatic — triggered when Scout finds a business without a website.

Pipeline:
  1. Theme Auto-Select (7 industries + default)
  2. Content Generation (6 sections from Google Places data + AI tagline)
  3. A2A Quality Check (rule-based Shannon simulation)
  4. Persist to MongoDB (`aurem_websites` collection)
  5. Auto-campaign trigger (WhatsApp + SMS + Email + Voice via existing blast)

CASL + privacy compliance baked in: every site includes demo banner, privacy
page text, terms text, unsubscribe link, AUREM attribution.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# INDUSTRY THEMES (7 + default)
# ─────────────────────────────────────────────────────────────
THEMES: Dict[str, Dict[str, Any]] = {
    "auto_shop":    {"bg": "#1A1A1A", "accent": "#FF6B00", "text": "#F5F5F5", "font": "Rajdhani",           "hero_anim": "gears"},
    "beauty_salon": {"bg": "#FFF5F7", "accent": "#D4A0A7", "text": "#2B1219", "font": "Playfair Display",   "hero_anim": "petals"},
    "restaurant":   {"bg": "#1C1008", "accent": "#D4920A", "text": "#F9ECD3", "font": "Cormorant Garamond", "hero_anim": "foodwave"},
    "medical":      {"bg": "#F0F7FF", "accent": "#0066CC", "text": "#0A1A30", "font": "Inter",              "hero_anim": "pulse"},
    "dental":       {"bg": "#FFFFFF", "accent": "#00B4D8", "text": "#0A1A30", "font": "Nunito",             "hero_anim": "pulse"},
    "fitness":      {"bg": "#0A0A0A", "accent": "#FF3300", "text": "#FFFFFF", "font": "Oswald",             "hero_anim": "rings"},
    "real_estate":  {"bg": "#0D0D0D", "accent": "#C9A227", "text": "#EDEDED", "font": "Cinzel",             "hero_anim": "orbital"},
    "default":      {"bg": "#0A0A0A", "accent": "#C9A227", "text": "#EDEDED", "font": "Jost",               "hero_anim": "orbital"},
}


def detect_industry(category: str) -> str:
    c = (category or "").lower()
    if any(k in c for k in ("auto", "mechanic", "body shop", "tire", "garage")):
        return "auto_shop"
    if any(k in c for k in ("hair", "salon", "beauty", "nail", "spa", "barber")):
        return "beauty_salon"
    if any(k in c for k in ("restaurant", "cafe", "food", "bakery", "pizza")):
        return "restaurant"
    if any(k in c for k in ("dental", "dentist", "orthod")):
        return "dental"
    if any(k in c for k in ("medical", "clinic", "doctor", "physician", "chiropract")):
        return "medical"
    if any(k in c for k in ("gym", "fitness", "yoga", "crossfit", "training")):
        return "fitness"
    if any(k in c for k in ("real estate", "realtor", "realty", "property")):
        return "real_estate"
    return "default"


# ─────────────────────────────────────────────────────────────
# CONTENT GENERATION
# ─────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60] or "business"


TAGLINE_TEMPLATES = {
    "auto_shop":    "Expert auto care you can trust — right here in {city}.",
    "beauty_salon": "Where beauty meets excellence in {city}.",
    "restaurant":   "Fresh flavours, warm hospitality — the best of {city}.",
    "medical":      "Compassionate care for the {city} community.",
    "dental":       "Healthy smiles start here in {city}.",
    "fitness":      "Train hard. Get stronger. Built for {city}.",
    "real_estate":  "Your home. Your journey. Your {city} expert.",
    "default":      "Serving {city} with pride and passion.",
}


SERVICE_HINTS = {
    "auto_shop":    [
        ("Oil Change", "Fast, professional oil changes using premium lubricants.", "droplet"),
        ("Brake Service", "Complete brake inspection, repair, and replacement.", "disc"),
        ("Tire Services", "Rotation, alignment, balancing, and new tire installation.", "circle"),
        ("Engine Diagnostics", "Computer diagnostics to identify issues fast.", "cpu"),
        ("Transmission", "Expert transmission service, repair, and replacement.", "settings"),
        ("General Repair", "All-make, all-model repairs from certified technicians.", "wrench"),
    ],
    "beauty_salon": [
        ("Hair Styling", "Cuts, colours, treatments by expert stylists.", "scissors"),
        ("Colour & Highlights", "Balayage, ombré, custom colour.", "palette"),
        ("Hair Treatments", "Deep conditioning, keratin, repair.", "droplet"),
        ("Makeup", "Bridal, event, everyday makeup.", "brush"),
        ("Nails", "Manicure, pedicure, gel, art.", "hand"),
        ("Facials", "Relaxing, rejuvenating skincare.", "sun"),
    ],
    "restaurant": [
        ("Dine-In", "Warm, welcoming atmosphere for the whole family.", "utensils"),
        ("Takeout", "Fast, fresh meals ready when you are.", "package"),
        ("Delivery", "Hot meals delivered to your door.", "truck"),
        ("Catering", "Events big and small — we handle the food.", "gift"),
        ("Private Events", "Host your celebration with us.", "star"),
        ("Reservations", "Book your table online.", "calendar"),
    ],
    "medical": [
        ("General Consultation", "Complete health check-ups.", "heart"),
        ("Chronic Care", "Ongoing support for long-term conditions.", "activity"),
        ("Preventive Care", "Vaccines, screenings, wellness.", "shield"),
        ("Urgent Care", "Same-day appointments when you need us.", "clock"),
        ("Lab Services", "On-site testing and fast results.", "beaker"),
        ("Telehealth", "Virtual visits from your home.", "video"),
    ],
    "dental": [
        ("Check-Ups", "Regular exams and professional cleaning.", "smile"),
        ("Fillings", "Tooth-coloured restorations.", "droplet"),
        ("Crowns & Bridges", "Restore your smile's strength.", "shield"),
        ("Teeth Whitening", "Professional brightening treatments.", "sun"),
        ("Orthodontics", "Braces, Invisalign, straightening.", "align-justify"),
        ("Emergency Care", "Same-day dental emergencies.", "alert-circle"),
    ],
    "fitness": [
        ("Personal Training", "One-on-one coaching tailored to your goals.", "zap"),
        ("Group Classes", "HIIT, yoga, bootcamp, cycling.", "users"),
        ("Strength Training", "Barbells, dumbbells, machines.", "dumbbell"),
        ("Nutrition Coaching", "Custom meal plans and guidance.", "apple"),
        ("Recovery", "Stretching, massage, cold plunge.", "heart"),
        ("Member Support", "24/7 access, app tracking.", "smartphone"),
    ],
    "real_estate": [
        ("Buy", "Find your dream home with expert guidance.", "home"),
        ("Sell", "Market your property for top dollar.", "trending-up"),
        ("Rent", "Short and long-term rental solutions.", "key"),
        ("Investment Properties", "Build wealth with real estate.", "bar-chart"),
        ("Relocation", "Moving to {city}? We'll help.", "map-pin"),
        ("Free Valuation", "Know what your home is worth today.", "dollar-sign"),
    ],
    "default": [
        ("Our Services", "Quality service you can count on.", "star"),
        ("Expert Team", "Trained professionals ready to help.", "users"),
        ("Customer Care", "We go the extra mile for you.", "heart"),
        ("Fast Response", "Quick turnaround on every request.", "zap"),
        ("Fair Pricing", "Transparent quotes, no surprises.", "dollar-sign"),
        ("Local Trusted", "Serving {city} with pride.", "map-pin"),
    ],
}


def _generate_why_points(lead: Dict[str, Any], city: str) -> List[Dict[str, str]]:
    rating = lead.get("rating") or "5.0"
    try:
        rating_str = f"{float(rating):.1f}"
    except Exception:
        rating_str = "5.0"
    reviews = lead.get("reviews_count") or "dozens of"
    return [
        {"icon": "home",   "text": "Locally owned and operated"},
        {"icon": "check",  "text": "Google-verified business"},
        {"icon": "star",   "text": f"{rating_str}★ rated by {reviews} customers"},
        {"icon": "map",    "text": f"Proudly serving {city}"},
    ]


def _generate_reviews(lead: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return Google reviews if present; then Birdeye reviews if cached on
    the lead under `birdeye_reviews`; otherwise a clearly-marked placeholder.

    iter 322ar — added Birdeye path. The async wrapper
    `generate_website_async()` populates `lead['birdeye_reviews']` by
    calling `services.birdeye_scraper.pull_real_reviews()` before
    invoking this sync helper, so this function never needs to await."""
    api_reviews = lead.get("google_reviews") or []
    if api_reviews:
        return [
            {
                "author": r.get("author_name", "Anonymous"),
                "rating": r.get("rating", 5),
                "text": r.get("text", "")[:260],
                "source": "google",
            }
            for r in api_reviews[:6]
        ]
    birdeye_reviews = lead.get("birdeye_reviews") or []
    if birdeye_reviews:
        return [
            {
                "author": r.get("author") or r.get("reviewer") or "Birdeye reviewer",
                "rating": r.get("rating", 5),
                "text": (r.get("text") or "")[:260],
                "source": "birdeye",
            }
            for r in birdeye_reviews[:6]
        ]
    # Synthesized fallback clearly marked as placeholder
    return [
        {"author": "— Placeholder —", "rating": 5,
         "text": f"Real Google reviews for {lead.get('business_name','this business')} will appear here automatically once the site goes live.",
         "source": "placeholder"},
    ]


def _generate_legal() -> Dict[str, str]:
    year = datetime.now().year
    return {
        "demo_banner": "DEMO PREVIEW — Sample website created by AUREM Intelligence AI for demonstration purposes only.",
        "footer_copy": f"© {year} — Powered by AUREM Intelligence AI · aurem.live",
        "unsubscribe_note": "Reply STOP or email opt-out@aurem.live to unsubscribe from AUREM communications.",
        "privacy_url": "/legal/privacy",
        "terms_url": "/legal/terms",
        "unsubscribe_url": "/legal/unsubscribe",
        "disclaimer": "Results are not guaranteed. Estimates based on industry averages. Up-to language only.",
    }


# ─────────────────────────────────────────────────────────────
# A2A QUALITY CHECK (Shannon-simulated, rule-based)
# ─────────────────────────────────────────────────────────────
def a2a_quality_check(website: Dict[str, Any]) -> Dict[str, Any]:
    """Shannon + Architect rule-based validation before the site is sent to the client."""
    issues: List[str] = []
    checks: Dict[str, bool] = {}

    b = website.get("business", {})
    checks["business_name_present"] = bool(b.get("name"))
    checks["phone_or_email_present"] = bool(b.get("phone") or b.get("email"))
    checks["services_count_ok"] = 3 <= len(website.get("services", [])) <= 8
    checks["why_points_count_ok"] = len(website.get("why_points", [])) >= 3
    checks["legal_footer_present"] = all(
        website.get("legal", {}).get(k) for k in ("demo_banner", "footer_copy", "unsubscribe_note")
    )
    checks["theme_valid"] = website.get("theme", {}).get("accent", "").startswith("#")
    checks["no_placeholder_name"] = b.get("name", "") and "placeholder" not in b.get("name", "").lower()
    checks["tagline_present"] = bool(website.get("tagline"))
    checks["casl_footer_has_stop"] = "stop" in website.get("legal", {}).get("unsubscribe_note", "").lower()

    # Architect — grammar / offensive-content heuristics
    text_blob = " ".join([
        website.get("tagline", ""),
        " ".join(s.get("description", "") for s in website.get("services", [])),
        " ".join(w.get("text", "") for w in website.get("why_points", [])),
    ]).lower()
    banned = ["fuck", "shit", "click here", "guaranteed income", "get rich"]
    checks["no_offensive_content"] = not any(b in text_blob for b in banned)

    for k, v in checks.items():
        if not v:
            issues.append(k)

    return {
        "passed": len(issues) == 0,
        "checks_passed": sum(1 for v in checks.values() if v),
        "checks_total": len(checks),
        "issues": issues,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def auto_repair(website: Dict[str, Any], issues: List[str]) -> Dict[str, Any]:
    """Repair agent — idempotent fixes for common issues before re-check."""
    if "tagline_present" in issues and not website.get("tagline"):
        city = website.get("business", {}).get("city", "your city")
        website["tagline"] = TAGLINE_TEMPLATES["default"].format(city=city)
    if "legal_footer_present" in issues:
        website["legal"] = _generate_legal()
    if "casl_footer_has_stop" in issues:
        website.setdefault("legal", _generate_legal())["unsubscribe_note"] = \
            "Reply STOP or email opt-out@aurem.live to unsubscribe from AUREM communications."
    if "why_points_count_ok" in issues:
        city = website.get("business", {}).get("city", "your city")
        website["why_points"] = _generate_why_points(website.get("business", {}), city)
    return website


# ─────────────────────────────────────────────────────────────
# MAIN GENERATOR
# ─────────────────────────────────────────────────────────────
def generate_website(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a complete sample website spec from a scout lead document."""
    category = lead.get("category", "")
    industry = detect_industry(category)
    theme = THEMES.get(industry, THEMES["default"])

    city = _extract_city(lead.get("location", ""))
    business_name = lead.get("business_name", "Your Business")
    slug = slugify(business_name)

    services_src = SERVICE_HINTS.get(industry, SERVICE_HINTS["default"])
    services = [
        {"name": n, "description": d.replace("{city}", city), "icon": i}
        for (n, d, i) in services_src
    ]

    website = {
        "slug": slug,
        "lead_id": lead.get("lead_id", slug),
        "industry": industry,
        "theme": theme,
        "business": {
            "name": business_name,
            "city": city,
            "location": lead.get("location", ""),
            "phone": lead.get("phone", ""),
            "email": lead.get("email", ""),
            "rating": lead.get("rating", "5.0"),
            "reviews_count": lead.get("reviews_count", 0),
            "hours": lead.get("hours", {}),
            "category": category,
        },
        "tagline": TAGLINE_TEMPLATES.get(industry, TAGLINE_TEMPLATES["default"]).format(city=city),
        "services": services,
        "why_points": _generate_why_points(lead, city),
        "reviews": _generate_reviews(lead),
        "legal": _generate_legal(),
        "status": "draft",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # A2A quality check + auto-repair loop (max 2 iterations)
    for _ in range(2):
        qc = a2a_quality_check(website)
        website["quality_check"] = qc
        if qc["passed"]:
            website["status"] = "approved"
            break
        website = auto_repair(website, qc["issues"])
    else:
        website["status"] = "needs_review"

    return website


def _extract_city(location: str) -> str:
    if not location:
        return "your area"
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2:
        return parts[1].title() if len(parts[1]) <= 30 else parts[0].title()
    return parts[0].title() if parts else "your area"


# ─────────────────────────────────────────────────────────────
# ASYNC WRAPPER — pulls real Birdeye reviews before generation
# ─────────────────────────────────────────────────────────────
async def generate_website_async(lead: Dict[str, Any]) -> Dict[str, Any]:
    """iter 322ar — async generator that enriches the lead with real
    Birdeye reviews (free, zero-key) before falling through to the sync
    `generate_website()`. If Birdeye lookup fails for any reason the
    sync path still produces a complete site spec with the placeholder
    review — no regressions."""
    if not lead.get("google_reviews") and not lead.get("birdeye_reviews"):
        try:
            from services.birdeye_scraper import pull_real_reviews
            city = _extract_city(lead.get("location", ""))
            biz = lead.get("business_name", "")
            if biz and city:
                pulled = await pull_real_reviews(biz, city, limit=6)
                if pulled.get("found") and pulled.get("reviews"):
                    lead = {**lead, "birdeye_reviews": pulled["reviews"]}
                    if pulled.get("aggregate_rating"):
                        lead.setdefault("rating", pulled["aggregate_rating"])
                    if pulled.get("total_count"):
                        lead.setdefault("reviews_count", pulled["total_count"])
        except Exception:
            # Silent fallback — synced generator still produces a valid site
            pass
    return generate_website(lead)
