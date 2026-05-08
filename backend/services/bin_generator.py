"""
BIN Generator — AUREM Business Intelligence Number (Login Credential)
=====================================================================
Format: {INDUSTRY}-{CITY}-{4CHARS}
Examples:
    AUT-MSS-7K92   (Auto shop, Mississauga)
    SAL-TOR-3M41   (Salon, Toronto)
    RST-VAN-9P55   (Restaurant, Vancouver)

NOTE: This is distinct from services/bin_service.py which aggregates Business
Intelligence Node metrics. Here, "BIN" = the human-readable login identifier
stored on user_doc.business_id.
"""

import re
import random
import string
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# Industry prefix mapping (3-letter codes)
# ═══════════════════════════════════════════════════════════════
INDUSTRY_CODES = {
    # Auto / Transport
    "automotive": "AUT", "auto repair": "AUT", "mechanic": "AUT", "body shop": "AUT",
    "car wash": "CWS", "detailing": "CWS",
    "tow": "TOW", "towing": "TOW",
    # Beauty / Personal care
    "salon": "SAL", "hair": "SAL", "barber": "BRB",
    "spa": "SPA", "massage": "SPA", "nail": "NLS", "nails": "NLS",
    "tattoo": "TAT", "tattoo parlor": "TAT",
    # Food & Beverage
    "restaurant": "RST", "cafe": "CAF", "coffee": "CAF",
    "bar": "BAR", "pub": "BAR", "brewery": "BRW",
    "bakery": "BKY", "catering": "CAT",
    # Retail
    "retail": "RTL", "store": "RTL", "boutique": "RTL",
    "pharmacy": "PHM", "grocery": "GRY",
    # Health & Medical
    "medical": "MED", "doctor": "MED", "clinic": "MED",
    "dental": "DNT", "dentist": "DNT",
    "chiropractor": "CHR", "chiropractic": "CHR",
    "physio": "PHY", "physiotherapy": "PHY",
    "optometry": "OPT", "eye": "OPT",
    "vet": "VET", "veterinary": "VET",
    # Fitness
    "fitness": "FIT", "gym": "FIT", "yoga": "YOG", "pilates": "YOG",
    "martial arts": "MRT", "dance": "DNC",
    # Professional
    "legal": "LGL", "law": "LGL", "lawyer": "LGL", "attorney": "LGL",
    "accounting": "ACC", "accountant": "ACC", "cpa": "ACC", "tax": "ACC",
    "consulting": "CNS", "consultant": "CNS",
    "real estate": "REA", "realtor": "REA", "realestate": "REA",
    "insurance": "INS", "broker": "BRK",
    "finance": "FIN", "financial": "FIN", "mortgage": "MTG",
    # Trades / Home services
    "plumbing": "PLB", "plumber": "PLB",
    "electrical": "ELC", "electrician": "ELC",
    "hvac": "HVC", "heating": "HVC", "cooling": "HVC",
    "cleaning": "CLN", "janitorial": "CLN",
    "landscaping": "LND", "lawn": "LND",
    "roofing": "ROF", "roofer": "ROF",
    "construction": "CON", "contractor": "CON", "builder": "CON",
    "painting": "PNT", "painter": "PNT",
    "moving": "MOV", "movers": "MOV",
    "pest": "PST", "pest control": "PST",
    # Tech / Creative
    "tech": "TCH", "software": "SOF", "it": "TCH",
    "marketing": "MKT", "agency": "AGY",
    "photography": "PHT", "photographer": "PHT",
    "design": "DES", "graphic design": "DES",
    "web": "WEB", "webdesign": "WEB",
    "media": "MDA", "video": "VID", "production": "PRD",
    # Education
    "education": "EDU", "school": "EDU", "tutoring": "TUT", "tutor": "TUT",
    "daycare": "DAY", "childcare": "DAY", "preschool": "DAY",
    # Hospitality / Events
    "hotel": "HTL", "motel": "HTL", "bnb": "BNB",
    "event": "EVT", "wedding": "WED", "dj": "DJS",
    "florist": "FLR", "flowers": "FLR",
    # Misc
    "petcare": "PET", "pet": "PET", "groomer": "PET", "dog": "PET",
    "security": "SEC", "locksmith": "LCK",
    "jewelry": "JWL", "jeweler": "JWL",
    "funeral": "FNR",
    # Shopify / E-commerce
    "shopify": "SHP", "ecommerce": "SHP", "e-commerce": "SHP", "online store": "SHP",
}

# ═══════════════════════════════════════════════════════════════
# City / Region code mapping (3-letter codes — airport-style)
# ═══════════════════════════════════════════════════════════════
CITY_CODES = {
    # Canada — Ontario
    "toronto": "TOR", "mississauga": "MSS", "brampton": "BRM",
    "markham": "MKM", "vaughan": "VGN", "richmond hill": "RHL",
    "oakville": "OAK", "burlington": "BRL", "hamilton": "HAM",
    "london": "LDN", "ottawa": "OTT", "kitchener": "KIT",
    "waterloo": "WAT", "guelph": "GLP", "windsor": "WDS",
    "barrie": "BAR", "kingston": "KGN", "sudbury": "SUD",
    "thunder bay": "THB", "oshawa": "OSH", "peterborough": "PTB",
    "niagara": "NIA", "st catharines": "STC",
    # Canada — Quebec
    "montreal": "MTL", "quebec": "QBC", "laval": "LAV",
    "gatineau": "GAT", "sherbrooke": "SHB", "trois-rivieres": "TRR",
    # Canada — West
    "vancouver": "VAN", "surrey": "SUR", "burnaby": "BNB",
    "richmond": "RCH", "calgary": "CAL", "edmonton": "EDM",
    "red deer": "RDD", "winnipeg": "WPG", "saskatoon": "SAS",
    "regina": "REG", "kelowna": "KEL", "victoria": "VIC",
    "abbotsford": "ABB",
    # Canada — Atlantic / North
    "halifax": "HFX", "moncton": "MON", "fredericton": "FRE",
    "saint john": "SJN", "st johns": "YYT", "charlottetown": "CHT",
    "yellowknife": "YZF", "whitehorse": "YXY", "iqaluit": "IQA",
    # USA — Major
    "new york": "NYC", "los angeles": "LAX", "chicago": "CHI",
    "houston": "HOU", "phoenix": "PHX", "philadelphia": "PHL",
    "san antonio": "SAT", "san diego": "SAN", "dallas": "DAL",
    "san jose": "SJC", "austin": "AUS", "jacksonville": "JAX",
    "fort worth": "FTW", "columbus": "CMH", "charlotte": "CLT",
    "indianapolis": "IND", "seattle": "SEA", "denver": "DEN",
    "washington": "WSH", "boston": "BOS", "el paso": "ELP",
    "nashville": "NAS", "detroit": "DET", "portland": "PDX",
    "memphis": "MEM", "oklahoma city": "OKC", "las vegas": "LAS",
    "louisville": "LOU", "baltimore": "BAL", "milwaukee": "MKE",
    "albuquerque": "ABQ", "tucson": "TUS", "fresno": "FRE",
    "sacramento": "SAC", "atlanta": "ATL", "miami": "MIA",
    "orlando": "ORL", "tampa": "TPA", "pittsburgh": "PIT",
    "cincinnati": "CIN", "cleveland": "CLE", "minneapolis": "MSP",
    "saint paul": "STP", "kansas city": "KCY", "new orleans": "MSY",
    "raleigh": "RAL", "omaha": "OMA", "long beach": "LGB",
    "virginia beach": "VIB", "mesa": "MES", "tulsa": "TUL",
    "arlington": "ARL", "honolulu": "HNL", "anchorage": "ANC",
    "salt lake city": "SLC", "st louis": "STL",
    # Fallback international hubs
    "london uk": "LON", "london england": "LON",
    "manchester": "MAN", "birmingham": "BMG",
    "paris": "PAR", "sydney": "SYD", "melbourne": "MEL",
    "dubai": "DXB", "mumbai": "BOM", "delhi": "DEL",
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


def industry_code(industry: Optional[str]) -> str:
    """Resolve industry string to 3-letter code. Falls back to first 3 letters of input, else BIZ."""
    slug = _slug(industry)
    if not slug:
        return "BIZ"
    # Exact match
    if slug in INDUSTRY_CODES:
        return INDUSTRY_CODES[slug]
    # Substring match (longest key wins)
    matches = [(k, v) for k, v in INDUSTRY_CODES.items() if k in slug or slug in k]
    if matches:
        matches.sort(key=lambda x: -len(x[0]))
        return matches[0][1]
    # Fallback: first 3 alpha chars uppercased
    alpha = re.sub(r"[^A-Za-z]", "", industry or "")[:3].upper()
    return alpha.ljust(3, "X") if alpha else "BIZ"


def city_code(city: Optional[str]) -> str:
    """Resolve city string to 3-letter code. Falls back to first 3 letters of input, else GEN."""
    slug = _slug(city)
    if not slug:
        return "GEN"
    if slug in CITY_CODES:
        return CITY_CODES[slug]
    matches = [(k, v) for k, v in CITY_CODES.items() if k in slug or slug in k]
    if matches:
        matches.sort(key=lambda x: -len(x[0]))
        return matches[0][1]
    alpha = re.sub(r"[^A-Za-z]", "", city or "")[:3].upper()
    return alpha.ljust(3, "X") if alpha else "GEN"


def generate_bin(industry: Optional[str] = None, city: Optional[str] = None) -> str:
    """Generate a BIN of format INDUSTRY-CITY-XXXX (no ambiguous chars)."""
    ind = industry_code(industry)
    cty = city_code(city)
    # Omit ambiguous chars (0/O, 1/I/L)
    safe_chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    suffix = "".join(random.choices(safe_chars, k=4))
    return f"{ind}-{cty}-{suffix}"


# Regex to validate/detect BIN format in login inputs
# Accept TWO BIN formats platform-wide:
#   • 3+3+4 (new): RST-TOR-9K82   — city-scoped BIN-Auth identifier
#   • 4+4   (legacy): RERO-DMYE   — short business reference used by tenant_customers
BIN_REGEX = re.compile(
    r"^(?:[A-Z]{3}-[A-Z]{3}-[A-Z0-9]{4}|[A-Z]{4}-[A-Z0-9]{4})$",
    re.IGNORECASE,
)


def is_bin(value: str) -> bool:
    """Check if input matches BIN format (case-insensitive)."""
    if not value or not isinstance(value, str):
        return False
    return bool(BIN_REGEX.match(value.strip()))


def normalize_bin(value: str) -> str:
    """Uppercase + strip — canonical BIN form for DB lookup."""
    return (value or "").strip().upper()
