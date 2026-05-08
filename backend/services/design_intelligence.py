"""
AUREM Design Intelligence — Powered by UI UX Pro Max
=====================================================
161 reasoning rules, 67 styles, 161 color palettes, 57 font pairings.
Wire to Content Engine for auto-generating design systems for clients.
"""
import os
import csv
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

DATA_DIR = "/app/.claude/skills/ui-ux-pro-max/src/ui-ux-pro-max/data"
_cache = {}


def _load_csv(filename: str) -> List[Dict]:
    """Load a CSV file from UI UX Pro Max data directory."""
    if filename in _cache:
        return _cache[filename]
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [dict(r) for r in reader]
            _cache[filename] = rows
            return rows
    except Exception as e:
        logger.warning(f"[DESIGN] Failed to load {filename}: {e}")
        return []


def get_product_reasoning(product_type: str) -> Dict:
    """Get design reasoning rules for a product type (161 categories)."""
    rows = _load_csv("products.csv")
    product_type_lower = product_type.lower()
    query_words = [w.strip() for w in product_type_lower.replace(",", " ").split() if len(w.strip()) > 2]
    for row in rows:
        keywords = row.get("Keywords", "").lower()
        ptype = row.get("Product Type", "").lower()
        if product_type_lower in ptype or ptype in product_type_lower:
            return {
                "product_type": row.get("Product Type", ""),
                "primary_style": row.get("Primary Style Recommendation", ""),
                "secondary_styles": row.get("Secondary Styles", ""),
                "landing_pattern": row.get("Landing Page Pattern", ""),
                "dashboard_style": row.get("Dashboard Style (if applicable)", ""),
                "color_focus": row.get("Color Palette Focus", ""),
                "considerations": row.get("Key Considerations", ""),
            }
        # Check if any query word matches any keyword
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if any(qw in kw_list or qw in ptype for qw in query_words):
            return {
                "product_type": row.get("Product Type", ""),
                "primary_style": row.get("Primary Style Recommendation", ""),
                "secondary_styles": row.get("Secondary Styles", ""),
                "landing_pattern": row.get("Landing Page Pattern", ""),
                "dashboard_style": row.get("Dashboard Style (if applicable)", ""),
                "color_focus": row.get("Color Palette Focus", ""),
                "considerations": row.get("Key Considerations", ""),
            }
    return {"product_type": product_type, "error": "not_found"}


def get_color_palette(product_type: str) -> Dict:
    """Get color palette for a product type (161 palettes)."""
    rows = _load_csv("colors.csv")
    product_type_lower = product_type.lower()
    query_words = [w.strip() for w in product_type_lower.replace(",", " ").split() if len(w.strip()) > 2]
    for row in rows:
        ptype = row.get("Product Type", "").lower()
        if product_type_lower in ptype or ptype in product_type_lower or any(qw in ptype for qw in query_words):
            return {
                "product_type": row.get("Product Type", ""),
                "primary": row.get("Primary", ""),
                "on_primary": row.get("On Primary", ""),
                "secondary": row.get("Secondary", ""),
                "accent": row.get("Accent", ""),
                "background": row.get("Background", ""),
                "foreground": row.get("Foreground", ""),
                "card": row.get("Card", ""),
                "muted": row.get("Muted", ""),
                "border": row.get("Border", ""),
                "notes": row.get("Notes", ""),
            }
    return {"product_type": product_type, "error": "not_found"}


def get_style_info(style_name: str) -> Dict:
    """Get style details (67 styles)."""
    rows = _load_csv("styles.csv")
    style_lower = style_name.lower()
    for row in rows:
        name = row.get("Style", "").lower()
        if style_lower in name or name in style_lower:
            return {k: v for k, v in row.items() if v}
    return {"style": style_name, "error": "not_found"}


def get_typography(mood: str = "") -> List[Dict]:
    """Get font pairing recommendations."""
    rows = _load_csv("google-fonts.csv")
    if not mood:
        return rows[:10]
    mood_lower = mood.lower()
    matches = [r for r in rows if mood_lower in (r.get("Mood", "") + r.get("Best For", "")).lower()]
    return matches[:5] if matches else rows[:5]


def recommend_design_system(product_type: str, business_name: str = "") -> Dict:
    """
    Full design system recommendation for a product type.
    Combines reasoning rules + colors + style + typography.
    """
    reasoning = get_product_reasoning(product_type)
    colors = get_color_palette(product_type)
    style = get_style_info(reasoning.get("primary_style", "Flat Design"))
    mood = reasoning.get("color_focus", "").split("+")[0].strip() if reasoning.get("color_focus") else "modern"
    typography = get_typography(mood)

    return {
        "business": business_name or product_type,
        "reasoning": reasoning,
        "colors": colors,
        "style": style,
        "typography": typography[:3],
        "anti_patterns": ["AI purple/pink gradients", "Emoji as icons", "Missing hover states", "No focus states"],
        "checklist": [
            "No emojis as icons (use SVG: Lucide/Heroicons)",
            "cursor-pointer on all clickable elements",
            "Hover states with smooth transitions (150-300ms)",
            "Light mode: text contrast 4.5:1 minimum",
            "Focus states visible for keyboard nav",
            "Responsive: 375px, 768px, 1024px, 1440px",
        ],
    }


def search_styles(query: str, limit: int = 5) -> List[Dict]:
    """Search across all styles."""
    rows = _load_csv("styles.csv")
    query_lower = query.lower()
    matches = []
    for row in rows:
        score = sum(1 for v in row.values() if query_lower in str(v).lower())
        if score > 0:
            matches.append({"score": score, **{k: v for k, v in row.items() if v}})
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:limit]
