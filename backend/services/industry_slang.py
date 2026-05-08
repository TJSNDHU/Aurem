"""
Industry-specific language pack — iter 282al-6.

ORA's outreach quality jumps when the LLM has the right vocabulary for
the lead's trade. Each entry exposes pain points, real services, trust
signals, search terms, and a single high-impact urgency hook.

Public API:
    get_industry_context(category: str) -> dict
"""
from __future__ import annotations

INDUSTRY_SLANG = {
    "plumber": {
        "pain_points": [
            "burst pipe calls going to voicemail at 2AM",
            "emergency dispatch not showing online",
            "losing jobs to HomeStars listings",
            "no-shows from tire-kicker leads",
            "slow February drying up the schedule",
        ],
        "services": [
            "emergency dispatch", "drain snaking", "water heater replacement",
            "backflow prevention", "sump pump", "pipe relining", "leak detection",
        ],
        "trust_signals": [
            "licensed and insured", "same-day service",
            "no-dig solutions", "Mississauga-based",
        ],
        "search_terms": [
            "plumber near me", "emergency plumber Mississauga",
            "burst pipe repair",
        ],
        "competitor_context": "HomeStars and Google Maps listings",
        "urgency_hook": (
            "burst pipe calls happen at 2AM — if you're not showing up "
            "online, that job goes to whoever is"
        ),
    },
    "hvac": {
        "pain_points": [
            "furnace calls in January going elsewhere",
            "AC tune-up season missed",
            "no online booking for service calls",
            "losing maintenance contracts",
            "HVAC emergencies at midnight",
        ],
        "services": [
            "furnace installation", "AC tune-up", "heat pump", "duct cleaning",
            "emergency HVAC", "maintenance contract", "refrigerant recharge",
            "thermostat install",
        ],
        "trust_signals": [
            "TSSA certified", "gas licensed", "same-day emergency",
            "financing available",
        ],
        "search_terms": [
            "HVAC repair Mississauga", "furnace not working",
            "emergency AC repair",
        ],
        "urgency_hook": (
            "January furnace failures don't wait — homeowners call whoever "
            "shows up first on Google"
        ),
    },
    "auto_body": {
        "pain_points": [
            "insurance jobs going to dealerships",
            "no online estimates",
            "losing referrals from insurance adjusters",
            "customers not knowing you do paintless dent repair",
        ],
        "services": [
            "collision repair", "paintless dent repair", "insurance claims",
            "paint correction", "frame straightening", "bumper repair",
            "ceramic coating", "rust proofing",
        ],
        "trust_signals": [
            "insurance approved", "OEM parts",
            "lifetime warranty on paint", "courtesy car available",
        ],
        "search_terms": [
            "auto body shop near me", "collision repair Mississauga",
            "paintless dent repair",
        ],
        "urgency_hook": (
            "Insurance adjusters recommend shops they find online — if "
            "you're not there, that claim goes somewhere else"
        ),
    },
    "electrician": {
        "pain_points": [
            "ESA inspection jobs going to others",
            "panel upgrade inquiries unanswered",
            "EV charger installs missed",
            "no online presence for commercial bids",
        ],
        "services": [
            "panel upgrade", "ESA inspection", "EV charger installation",
            "pot light installation", "commercial wiring", "generator hookup",
            "smart home wiring", "knob and tube removal",
        ],
        "trust_signals": [
            "ESA certified", "licensed master electrician", "permit pulled",
            "ECRA/ESA licensed",
        ],
        "search_terms": [
            "licensed electrician Mississauga", "panel upgrade cost",
            "EV charger installation",
        ],
        "urgency_hook": (
            "EV charger installs are exploding — contractors who aren't "
            "showing up online are missing $800-1200 jobs daily"
        ),
    },
    "landscaper": {
        "pain_points": [
            "losing spring cleanup contracts",
            "snow removal route not full",
            "no recurring maintenance clients",
            "interlock jobs going to competition",
        ],
        "services": [
            "spring cleanup", "snow removal", "interlock installation",
            "sod laying", "irrigation system", "tree trimming",
            "lawn maintenance contract", "landscape design",
        ],
        "trust_signals": [
            "CNLA certified", "fully insured",
            "Landscape Ontario member", "free estimates",
        ],
        "search_terms": [
            "landscaping company Mississauga", "snow removal contract",
            "interlock patio",
        ],
        "urgency_hook": (
            "Spring cleanup contracts get locked in February — if "
            "homeowners can't find you online now, those contracts are gone"
        ),
    },
    "skincare_clinic": {
        "pain_points": [
            "patient retention dropping after first visit",
            "PDRN and biostimulator results not being showcased",
            "losing clients to med spas with better Instagram",
            "no online booking for consultations",
            "treatment results not documented",
        ],
        "services": [
            "PDRN therapy", "polynucleotide treatment", "biostimulator",
            "filler", "skin booster", "chemical peel", "microneedling",
            "laser resurfacing", "acne treatment protocol",
            "anti-aging consultation",
        ],
        "trust_signals": [
            "medical-grade products", "licensed injector",
            "Health Canada compliant", "before/after documentation",
            "personalized skin protocol",
        ],
        "search_terms": [
            "PDRN treatment Toronto", "skin booster near me",
            "acne clinic Mississauga",
        ],
        "urgency_hook": (
            "Patients researching PDRN and biostimulators book the first "
            "clinic that shows up with real before/after results — not "
            "the best one"
        ),
        # iter 282al-6 — Reroots Aesthetics (BIN: BEA-MSS-WZ48) is
        # AUREM Client #1. Don't name them — but use the insider tone.
        "credibility_note": (
            "AUREM works with leading Canadian skincare clinics, including "
            "one specializing in PDRN and advanced biostimulator protocols. "
            "Speak as an industry insider."
        ),
    },
    "dental": {
        "pain_points": [
            "new patient acquisition cost too high",
            "Invisalign consultations not converting",
            "no-shows killing schedule",
            "losing patients to corporate dental chains",
        ],
        "services": [
            "Invisalign", "teeth whitening", "dental implants",
            "emergency extraction", "root canal", "veneers",
            "family dentistry", "night guards",
        ],
        "trust_signals": [
            "RCDSO licensed", "accepting new patients",
            "direct billing insurance", "same-day emergency",
        ],
        "search_terms": [
            "Invisalign Mississauga", "emergency dentist near me",
            "family dentist accepting new patients",
        ],
        "urgency_hook": (
            "Patients searching Invisalign consultations book within "
            "24 hours — whoever shows up first with reviews gets the consult"
        ),
    },
    "real_estate": {
        "pain_points": [
            "listings not getting enough showings",
            "leads going cold before follow-up",
            "no personal brand online",
            "buyers choosing other agents",
        ],
        "services": [
            "buyer representation", "listing agent", "pre-construction",
            "investment properties", "first-time buyer", "downsizing",
            "commercial leasing",
        ],
        "trust_signals": [
            "OREA registered", "top producer",
            "neighbourhood specialist", "negotiation certified",
        ],
        "search_terms": [
            "realtor Mississauga", "best real estate agent", "first-time buyer",
        ],
        "urgency_hook": (
            "Buyers interview 3 agents online before calling one — if "
            "your Google presence is weak, you're not in that interview"
        ),
    },
    "restaurant": {
        "pain_points": [
            "Uber Eats taking 30% margin",
            "no direct online ordering",
            "Google reviews not responded to",
            "catering inquiries going unanswered",
        ],
        "services": [
            "dine-in", "takeout", "catering", "private events",
            "meal prep", "delivery (direct)", "weekly specials",
        ],
        "trust_signals": [
            "family-owned", "locally-sourced", "Halal-certified",
            "10+ years in the neighbourhood",
        ],
        "search_terms": [
            "best restaurant Mississauga", "catering near me",
            "online ordering",
        ],
        "urgency_hook": (
            "Every Uber Eats order costs you 30% — direct online "
            "ordering pays for itself in the first week"
        ),
    },
    "general": {
        "pain_points": [
            "not showing up on Google",
            "losing customers to competitors online",
            "no way for customers to find you after hours",
        ],
        "services": ["professional services"],
        "trust_signals": ["licensed", "insured", "locally owned"],
        "search_terms": ["near me"],
        "urgency_hook": (
            "93% of customers search online before calling — if you're "
            "not there, they call someone who is"
        ),
    },
}


# Fuzzy keyword → industry mapping, longest-keyword-first to avoid
# `auto body` matching `auto`.
_CATEGORY_MAP = [
    ("air condition", "hvac"),
    ("auto body", "auto_body"),
    ("body shop", "auto_body"),
    ("collision", "auto_body"),
    ("electric", "electrician"),
    ("landscape", "landscaper"),
    ("real estate", "real_estate"),
    ("realtor", "real_estate"),
    ("skin care", "skincare_clinic"),
    ("aesthetic", "skincare_clinic"),
    ("med spa", "skincare_clinic"),
    ("furnace", "hvac"),
    ("heating", "hvac"),
    ("cooling", "hvac"),
    ("plumb", "plumber"),
    ("drain", "plumber"),
    ("dental", "dental"),
    ("teeth", "dental"),
    ("orthodon", "dental"),
    ("clinic", "skincare_clinic"),
    ("pdrn", "skincare_clinic"),
    ("wiring", "electrician"),
    ("panel", "electrician"),
    ("lawn", "landscaper"),
    ("snow", "landscaper"),
    ("garden", "landscaper"),
    ("agent", "real_estate"),
    ("restaurant", "restaurant"),
    ("food", "restaurant"),
    ("cafe", "restaurant"),
    ("hvac", "hvac"),
    ("paint", "auto_body"),
    ("auto", "auto_body"),
    ("pipe", "plumber"),
    ("skin", "skincare_clinic"),
]


def get_industry_context(category: str) -> dict:
    """Return the slang dict for the closest matching industry. Falls
    back to `general` for unknown categories."""
    if not category:
        return INDUSTRY_SLANG["general"]
    cat = category.lower().strip()
    if cat in INDUSTRY_SLANG:
        return INDUSTRY_SLANG[cat]
    for keyword, industry in _CATEGORY_MAP:
        if keyword in cat:
            return INDUSTRY_SLANG[industry]
    return INDUSTRY_SLANG["general"]


__all__ = ["INDUSTRY_SLANG", "get_industry_context"]
