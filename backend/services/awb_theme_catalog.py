"""
Curated Theme Catalog (iter 300)
================================
Hand-picked theme presets per niche. Used by AWB Theme Picker as the
zero-API fallback when Tavily/Google Places quotas are exhausted.

Each preset has a complete `style` dict matching what playwright-extracted
real-site styles would look like, so the AWB renderer can swap them in
without changes.

Update strategy: when search APIs come back online, real-business themes
will MERGE on top of these (curated remains as fallback for niches with
fewer hits).
"""
from __future__ import annotations

from typing import Any, Dict, List

# Catalog: keys are normalized niche tokens (lowercased).
# Each entry: list of theme presets.
_PRESETS: Dict[str, List[Dict[str, Any]]] = {
    "auto": [
        {"name": "Pit Crew", "tags": ["bold", "industrial", "trust"],
         "style": {"primary_bg": "#0F1419", "primary_text": "#F2F2F2",
                   "accent": "#FF6B35", "heading_color": "#FFFFFF",
                   "body_font": "Inter", "heading_font": "Bebas Neue"}},
        {"name": "Garage Classic", "tags": ["clean", "professional", "blue"],
         "style": {"primary_bg": "#FFFFFF", "primary_text": "#1A1A1A",
                   "accent": "#1E5BFF", "heading_color": "#0A2540",
                   "body_font": "Roboto", "heading_font": "Roboto Slab"}},
        {"name": "Heritage Auto", "tags": ["warm", "family", "trust"],
         "style": {"primary_bg": "#F5F1E8", "primary_text": "#2D1F0F",
                   "accent": "#8B2C0E", "heading_color": "#3A1F0A",
                   "body_font": "Lora", "heading_font": "Playfair Display"}},
        {"name": "Speed Lab", "tags": ["dark", "tech", "performance"],
         "style": {"primary_bg": "#0A0A0A", "primary_text": "#E5E5E5",
                   "accent": "#FFE600", "heading_color": "#FFFFFF",
                   "body_font": "JetBrains Mono", "heading_font": "Space Grotesk"}},
    ],
    "coffee": [
        {"name": "Slow Pour", "tags": ["warm", "artisanal", "minimal"],
         "style": {"primary_bg": "#F4EAD9", "primary_text": "#3A2818",
                   "accent": "#8B4513", "heading_color": "#2D1810",
                   "body_font": "Lora", "heading_font": "Playfair Display"}},
        {"name": "Third Wave", "tags": ["modern", "minimal", "monochrome"],
         "style": {"primary_bg": "#FFFFFF", "primary_text": "#1A1A1A",
                   "accent": "#1A1A1A", "heading_color": "#000000",
                   "body_font": "Inter", "heading_font": "Inter"}},
        {"name": "Espresso Bar", "tags": ["dark", "italian", "rich"],
         "style": {"primary_bg": "#1C1410", "primary_text": "#E8DCC8",
                   "accent": "#C9A227", "heading_color": "#F2EDE4",
                   "body_font": "DM Sans", "heading_font": "Cormorant Garamond"}},
        {"name": "Brunch House", "tags": ["bright", "fresh", "local"],
         "style": {"primary_bg": "#FFF8EE", "primary_text": "#2A2520",
                   "accent": "#E07A5F", "heading_color": "#3D405B",
                   "body_font": "DM Sans", "heading_font": "Fraunces"}},
    ],
    "restaurant": [
        {"name": "Trattoria", "tags": ["warm", "italian", "family"],
         "style": {"primary_bg": "#FAF3E0", "primary_text": "#2A1F0F",
                   "accent": "#A52A2A", "heading_color": "#1F1108",
                   "body_font": "Lora", "heading_font": "Playfair Display"}},
        {"name": "Modern Plate", "tags": ["dark", "fine dining", "luxury"],
         "style": {"primary_bg": "#0A0A0A", "primary_text": "#E5E5E5",
                   "accent": "#C9A227", "heading_color": "#FFFFFF",
                   "body_font": "DM Sans", "heading_font": "Cormorant Garamond"}},
        {"name": "Neighborhood Bistro", "tags": ["bright", "neighborhood", "fresh"],
         "style": {"primary_bg": "#FFFFFF", "primary_text": "#1A1A1A",
                   "accent": "#5B8A4E", "heading_color": "#2D3E2A",
                   "body_font": "Inter", "heading_font": "Fraunces"}},
    ],
    "salon": [
        {"name": "Soft Studio", "tags": ["pastel", "feminine", "calm"],
         "style": {"primary_bg": "#FDF6F1", "primary_text": "#3A2828",
                   "accent": "#C49A8A", "heading_color": "#5C3A3A",
                   "body_font": "Inter", "heading_font": "DM Serif Display"}},
        {"name": "Sharp Cut", "tags": ["bold", "modern", "edgy"],
         "style": {"primary_bg": "#0A0A0A", "primary_text": "#E5E5E5",
                   "accent": "#FF1744", "heading_color": "#FFFFFF",
                   "body_font": "Inter", "heading_font": "Bebas Neue"}},
        {"name": "Spa Calm", "tags": ["serene", "natural", "wellness"],
         "style": {"primary_bg": "#F0EDE4", "primary_text": "#2D3A2D",
                   "accent": "#7A8B68", "heading_color": "#3D4F3D",
                   "body_font": "DM Sans", "heading_font": "Fraunces"}},
    ],
    "fitness": [
        {"name": "Iron Lab", "tags": ["bold", "intense", "dark"],
         "style": {"primary_bg": "#0A0A0A", "primary_text": "#FFFFFF",
                   "accent": "#FFE600", "heading_color": "#FFE600",
                   "body_font": "Inter", "heading_font": "Bebas Neue"}},
        {"name": "Studio Class", "tags": ["clean", "modern", "energetic"],
         "style": {"primary_bg": "#FFFFFF", "primary_text": "#1A1A1A",
                   "accent": "#FF3366", "heading_color": "#000000",
                   "body_font": "Inter", "heading_font": "Inter"}},
        {"name": "Performance", "tags": ["tech", "data", "athletic"],
         "style": {"primary_bg": "#0F1A2A", "primary_text": "#E5F0FF",
                   "accent": "#00D4FF", "heading_color": "#FFFFFF",
                   "body_font": "JetBrains Mono", "heading_font": "Space Grotesk"}},
    ],
    "dental": [
        {"name": "Calm Care", "tags": ["soft", "trust", "professional"],
         "style": {"primary_bg": "#F4F8FB", "primary_text": "#1F2A3A",
                   "accent": "#4A90E2", "heading_color": "#1A2540",
                   "body_font": "Inter", "heading_font": "Inter"}},
        {"name": "Family Dental", "tags": ["warm", "family", "approachable"],
         "style": {"primary_bg": "#FFFFFF", "primary_text": "#2A2A2A",
                   "accent": "#22A06B", "heading_color": "#1A4D2E",
                   "body_font": "DM Sans", "heading_font": "DM Serif Display"}},
        {"name": "Premium Smile", "tags": ["luxury", "modern", "minimal"],
         "style": {"primary_bg": "#FAFAFA", "primary_text": "#1A1A1A",
                   "accent": "#C9A227", "heading_color": "#0A0A0A",
                   "body_font": "Inter", "heading_font": "Cormorant Garamond"}},
    ],
    "law": [
        {"name": "Counsel Classic", "tags": ["traditional", "trust", "serif"],
         "style": {"primary_bg": "#F8F5F0", "primary_text": "#1A1A1A",
                   "accent": "#7B0E13", "heading_color": "#0F0F0F",
                   "body_font": "Lora", "heading_font": "Playfair Display"}},
        {"name": "Modern Firm", "tags": ["clean", "professional", "blue"],
         "style": {"primary_bg": "#FFFFFF", "primary_text": "#1A1A1A",
                   "accent": "#0A2540", "heading_color": "#0A2540",
                   "body_font": "Inter", "heading_font": "Inter"}},
        {"name": "Boutique Practice", "tags": ["luxury", "dark", "premium"],
         "style": {"primary_bg": "#0F1419", "primary_text": "#E5E5E5",
                   "accent": "#C9A227", "heading_color": "#FFFFFF",
                   "body_font": "DM Sans", "heading_font": "Cormorant Garamond"}},
    ],
    "real_estate": [
        {"name": "Editorial", "tags": ["luxury", "magazine", "serif"],
         "style": {"primary_bg": "#FFFFFF", "primary_text": "#1A1A1A",
                   "accent": "#C9A227", "heading_color": "#0A0A0A",
                   "body_font": "Inter", "heading_font": "Cormorant Garamond"}},
        {"name": "Modern Listings", "tags": ["clean", "tech", "minimal"],
         "style": {"primary_bg": "#FAFAFA", "primary_text": "#1A1A1A",
                   "accent": "#1E5BFF", "heading_color": "#000000",
                   "body_font": "Inter", "heading_font": "Inter"}},
        {"name": "Heritage Homes", "tags": ["warm", "established", "trust"],
         "style": {"primary_bg": "#F5F0E8", "primary_text": "#2D2018",
                   "accent": "#5C4033", "heading_color": "#3A2818",
                   "body_font": "Lora", "heading_font": "Playfair Display"}},
    ],
    "default": [
        {"name": "AUREM Signature", "tags": ["dark", "premium", "gold"],
         "style": {"primary_bg": "#0A0A0B", "primary_text": "#F2EDE4",
                   "accent": "#C9A227", "heading_color": "#F2EDE4",
                   "body_font": "DM Sans", "heading_font": "Cormorant Garamond"}},
        {"name": "Modern Light", "tags": ["bright", "clean", "modern"],
         "style": {"primary_bg": "#FFFFFF", "primary_text": "#1A1A1A",
                   "accent": "#0A2540", "heading_color": "#0A2540",
                   "body_font": "Inter", "heading_font": "Inter"}},
        {"name": "Editorial Serif", "tags": ["warm", "editorial", "trust"],
         "style": {"primary_bg": "#F8F5F0", "primary_text": "#1A1A1A",
                   "accent": "#5B8A4E", "heading_color": "#0F0F0F",
                   "body_font": "Lora", "heading_font": "Playfair Display"}},
        {"name": "Tech Lab", "tags": ["dark", "tech", "innovative"],
         "style": {"primary_bg": "#0F1419", "primary_text": "#E5E5E5",
                   "accent": "#00D4FF", "heading_color": "#FFFFFF",
                   "body_font": "JetBrains Mono", "heading_font": "Space Grotesk"}},
    ],
}


def _normalize(niche: str) -> str:
    n = (niche or "").lower().strip()
    if not n:
        return "default"
    if any(w in n for w in ["auto", "mechanic", "tire", "brake", "muffler", "oil change"]):
        return "auto"
    if any(w in n for w in ["coffee", "café", "cafe", "espresso", "roaster"]):
        return "coffee"
    if any(w in n for w in ["restaurant", "bistro", "diner", "kitchen", "eatery", "food"]):
        return "restaurant"
    if any(w in n for w in ["salon", "barber", "spa", "stylist", "hair", "nail"]):
        return "salon"
    if any(w in n for w in ["gym", "fitness", "yoga", "pilates", "crossfit", "trainer"]):
        return "fitness"
    if any(w in n for w in ["dental", "dentist", "orthodontic", "smile"]):
        return "dental"
    if any(w in n for w in ["law", "attorney", "lawyer", "legal"]):
        return "law"
    if any(w in n for w in ["real estate", "realtor", "property", "homes"]):
        return "real_estate"
    return "default"


def get_curated_themes(niche: str) -> List[Dict[str, Any]]:
    """Returns curated theme list for a niche, falling back to 'default'."""
    key = _normalize(niche)
    presets = _PRESETS.get(key) or _PRESETS["default"]
    out: List[Dict[str, Any]] = []
    for p in presets:
        out.append({
            "url": None,
            "business_name": p["name"],
            "source": "curated",
            "tags": p.get("tags") or [],
            "screenshot_url": None,  # rendered live preview will substitute
            "style": p["style"],
            "niche_key": key,
        })
    return out


# ─────────────────────────────────────────────────────────────────────
# iter 282al-36 — style_hint → rendered HTML bridge
# ─────────────────────────────────────────────────────────────────────
def get_theme_colors(style_hint) -> Dict[str, Any]:
    """Resolve a style_hint (name string or dict with 'style') to a flat
    color/font dict. Returns {} if unresolvable — caller should skip injection.

    Accepts:
      - str theme name ("Pit Crew", "garage classic")
      - dict with "name" or "style" or direct keys
      - dict already looking like {"accent":..., "bg":..., "font":...}
    """
    if not style_hint:
        return {}

    # Case 1: already in flat shape
    if isinstance(style_hint, dict):
        flat = style_hint.get("style") or style_hint
        # direct keys win
        if "accent" in flat or "primary_bg" in flat:
            return {
                "accent":      flat.get("accent") or "",
                "bg":          flat.get("bg") or flat.get("primary_bg") or "",
                "text":        flat.get("primary_text") or flat.get("text") or "",
                "heading":     flat.get("heading_color") or "",
                "body_font":   flat.get("body_font") or "",
                "font":        flat.get("heading_font") or flat.get("body_font") or flat.get("font") or "",
            }
        # fall through to lookup by name
        style_hint = flat.get("name") or ""

    if not isinstance(style_hint, str) or not style_hint.strip():
        return {}

    needle = style_hint.lower().strip()
    for niche_presets in _PRESETS.values():
        for p in niche_presets:
            if p["name"].lower() == needle or p["name"].lower() in needle:
                s = p["style"]
                return {
                    "accent":    s["accent"],
                    "bg":        s["primary_bg"],
                    "text":      s["primary_text"],
                    "heading":   s["heading_color"],
                    "body_font": s["body_font"],
                    "font":      s["heading_font"],
                }
    return {}


def _font_url(family: str) -> str:
    """Build a Google-Fonts CSS url for a family name. Safe for any input."""
    if not family:
        return ""
    fam = family.replace(" ", "+")
    # Request regular + bold
    return f"https://fonts.googleapis.com/css2?family={fam}:wght@400;700&display=swap"


def inject_theme_css(html: str, style_hint) -> str:
    """Post-process generated HTML: extract theme colors from style_hint and
    inject them as CSS variables + body/accent rules directly before
    ``</head>``. Idempotent — double-calls are safe (checks marker).

    Returns HTML unchanged if style_hint is unresolvable or HTML is malformed.
    """
    colors = get_theme_colors(style_hint)
    if not colors or not html:
        return html
    if "<!--AUREM_THEME_INJECTED-->" in html:
        return html

    accent    = colors.get("accent") or ""
    bg        = colors.get("bg") or ""
    text      = colors.get("text") or ""
    heading   = colors.get("heading") or ""
    body_font = colors.get("body_font") or "system-ui"
    font      = colors.get("font") or body_font

    font_urls = []
    for f in {body_font, font}:
        u = _font_url(f)
        if u:
            font_urls.append(f'<link rel="stylesheet" href="{u}">')

    css_block = f"""<!--AUREM_THEME_INJECTED-->
{''.join(font_urls)}
<style id="aurem-theme-override">
:root {{
  --aurem-accent: {accent};
  --aurem-bg: {bg};
  --aurem-text: {text};
  --aurem-heading: {heading};
  --aurem-font: '{body_font}', system-ui, sans-serif;
  --aurem-heading-font: '{font}', '{body_font}', system-ui, sans-serif;
}}
html, body {{
  background: var(--aurem-bg) !important;
  color: var(--aurem-text) !important;
  font-family: var(--aurem-font) !important;
}}
h1, h2, h3, h4, h5, h6, .heading {{
  color: var(--aurem-heading) !important;
  font-family: var(--aurem-heading-font) !important;
}}
a, .accent, .text-accent {{ color: var(--aurem-accent) !important; }}
.cta, button.primary, .btn-primary, .bg-accent {{
  background: var(--aurem-accent) !important;
  color: #fff !important;
  border-color: var(--aurem-accent) !important;
}}
button.primary:hover, .btn-primary:hover {{ filter: brightness(1.08); }}
</style>
"""
    # Inject just before </head>, falling back to top-of-body, then top-of-HTML.
    if "</head>" in html:
        return html.replace("</head>", css_block + "</head>", 1)
    if "<body" in html:
        # Insert after opening body tag
        import re
        return re.sub(r"(<body[^>]*>)", r"\1" + css_block, html, count=1)
    return css_block + html
