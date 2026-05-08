"""
Brand Injection — iter 282ae (Prompt 2).

Pure helpers for:
  1. Extracting brand fields (color, font, logo) from a webclaw scan result
  2. Building CSS variable strings with safe defaults when brand data missing
  3. Shaping the usage-log document persisted to db.webclaw_usage

Consumed by:
  • services/auto_website_builder.py  — merges brand into template style
  • services/webclaw_client.py         — writes log rows to Mongo
  • routers/webclaw_health_router.py   — pillars-map health chip

Every function is pure and never touches the DB. Never raises.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DEFAULT_BRAND_PRIMARY = "#1a1a1a"
DEFAULT_BRAND_FONT = "Inter, sans-serif"


def extract_brand_fields(scan_result: dict | None) -> dict:
    """Pull primary_color / font_family / logo_url from a webclaw brand blob.

    Accepts the full scan_website() result OR just the nested `brand` dict.
    Returns canonical dict with safe defaults for the template.
    """
    out = {
        "primary_color": DEFAULT_BRAND_PRIMARY,
        "font_family":   DEFAULT_BRAND_FONT,
        "logo_url":      None,
        "has_brand":     False,
    }
    if not isinstance(scan_result, dict):
        return out
    brand = scan_result.get("brand") if "brand" in scan_result else scan_result
    if not isinstance(brand, dict):
        return out

    # Colors — webclaw returns {"colors": [{"hex": "#123abc", ...}, ...]}
    # Other shapes we've seen in the wild: primary_color, colors[0]
    primary = None
    colors = brand.get("colors") or brand.get("palette")
    if isinstance(colors, list) and colors:
        c0 = colors[0]
        if isinstance(c0, dict):
            primary = c0.get("hex") or c0.get("value") or c0.get("color")
        elif isinstance(c0, str):
            primary = c0
    primary = primary or brand.get("primary_color") or brand.get("primary")
    if isinstance(primary, str) and primary.startswith("#") and len(primary) in (4, 7):
        out["primary_color"] = primary
        out["has_brand"] = True

    # Fonts
    font = None
    fonts = brand.get("fonts") or brand.get("typography")
    if isinstance(fonts, list) and fonts:
        f0 = fonts[0]
        if isinstance(f0, dict):
            font = f0.get("family") or f0.get("name")
        elif isinstance(f0, str):
            font = f0
    elif isinstance(fonts, dict):
        font = fonts.get("body") or fonts.get("primary")
    font = font or brand.get("font_family") or brand.get("font")
    if isinstance(font, str) and font.strip():
        out["font_family"] = f"{font.strip()}, sans-serif" if "," not in font else font.strip()
        out["has_brand"] = True

    # Logo
    logo = brand.get("logo_url") or brand.get("logo")
    if isinstance(logo, dict):
        logo = logo.get("url") or logo.get("src")
    if isinstance(logo, str) and logo.startswith(("http://", "https://")):
        out["logo_url"] = logo
        out["has_brand"] = True

    return out


def inject_brand_css(scan_result: dict | None) -> str:
    """Return a CSS-variable block derived from the scan result.

    Guaranteed to contain `--brand-primary` and `--brand-font` with safe
    defaults so downstream templates never break.
    """
    fields = extract_brand_fields(scan_result)
    return (
        ":root{"
        f"--brand-primary: {fields['primary_color']};"
        f"--brand-font: {fields['font_family']};"
        "}"
    )


def build_usage_doc(url: str, source: str, content: str,
                    brand_extracted: bool, contacts_extracted: bool) -> dict:
    """Shape the doc persisted to db.webclaw_usage.

    Never raises — caller may dump this straight into Mongo.
    """
    now = datetime.now(timezone.utc)
    return {
        "url":                url,
        "source":             source,
        "content_length":     len(content or ""),
        "brand_extracted":    bool(brand_extracted),
        "contacts_extracted": bool(contacts_extracted),
        "ts":                 now,
        "date":               now.strftime("%Y-%m-%d"),
    }


def brand_style_overrides(scan_result: dict | None) -> dict[str, Any]:
    """Translate webclaw brand → auto_website_builder `style` kwargs.

    Returns an empty dict when no brand data was extracted (caller then
    falls back to its own defaults). Keys intentionally match what
    `_render_html` already reads from `style`.
    """
    f = extract_brand_fields(scan_result)
    if not f["has_brand"]:
        return {}
    overrides: dict[str, Any] = {}
    if f["primary_color"] != DEFAULT_BRAND_PRIMARY:
        overrides["accent"] = f["primary_color"]
    # font_family → body_font (template adds heading fallback separately)
    if f["font_family"] != DEFAULT_BRAND_FONT:
        # Strip trailing `, sans-serif` for the body_font slot — template
        # appends its own fallback chain.
        overrides["body_font"] = f["font_family"].split(",")[0].strip()
    if f["logo_url"]:
        overrides["_logo_url"] = f["logo_url"]
    return overrides


__all__ = [
    "extract_brand_fields",
    "inject_brand_css",
    "build_usage_doc",
    "brand_style_overrides",
    "DEFAULT_BRAND_PRIMARY",
    "DEFAULT_BRAND_FONT",
]
