"""
iter 282al-36 — style_hint → rendered HTML CSS injection tests.
"""
from __future__ import annotations

import pytest


# ─────────────── get_theme_colors ───────────────
def test_theme_colors_by_name_pit_crew():
    from services.awb_theme_catalog import get_theme_colors
    c = get_theme_colors("Pit Crew")
    assert c["accent"] == "#FF6B35"
    assert c["bg"]     == "#0F1419"
    assert c["font"]   == "Bebas Neue"


def test_theme_colors_case_insensitive():
    from services.awb_theme_catalog import get_theme_colors
    assert get_theme_colors("pit crew")["accent"] == "#FF6B35"
    assert get_theme_colors("GARAGE CLASSIC")["accent"] == "#1E5BFF"


def test_theme_colors_all_four_auto_themes():
    from services.awb_theme_catalog import get_theme_colors
    assert get_theme_colors("Pit Crew")["accent"]       == "#FF6B35"
    assert get_theme_colors("Garage Classic")["accent"] == "#1E5BFF"
    assert get_theme_colors("Heritage Auto")["accent"]  == "#8B2C0E"
    assert get_theme_colors("Speed Lab")["accent"]      == "#FFE600"


def test_theme_colors_cross_niche():
    from services.awb_theme_catalog import get_theme_colors
    assert get_theme_colors("Slow Pour")["accent"]    == "#8B4513"   # coffee
    assert get_theme_colors("Iron Lab")["accent"]     == "#FFE600"   # fitness
    assert get_theme_colors("Sharp Cut")["accent"]    == "#FF1744"   # salon


def test_theme_colors_unknown_returns_empty():
    from services.awb_theme_catalog import get_theme_colors
    assert get_theme_colors("Made Up Theme") == {}
    assert get_theme_colors("") == {}
    assert get_theme_colors(None) == {}


def test_theme_colors_accepts_direct_dict():
    """AWB callers pass {"style": {...}} — should resolve directly."""
    from services.awb_theme_catalog import get_theme_colors
    raw = {"style": {
        "primary_bg": "#000",   "primary_text": "#fff",
        "accent": "#FF0000",    "heading_color": "#eee",
        "body_font": "Inter",   "heading_font": "Bebas Neue",
    }}
    c = get_theme_colors(raw)
    assert c["accent"] == "#FF0000"
    assert c["bg"]     == "#000"
    assert c["font"]   == "Bebas Neue"


# ─────────────── inject_theme_css ───────────────
def test_inject_css_adds_marker_and_accent():
    from services.awb_theme_catalog import inject_theme_css
    html = "<html><head><title>T</title></head><body>Hi</body></html>"
    out = inject_theme_css(html, "Pit Crew")
    assert "AUREM_THEME_INJECTED" in out
    assert "#FF6B35" in out               # accent
    assert "#0F1419" in out               # bg
    assert "Bebas Neue" in out            # font
    assert "</head>" in out               # still valid
    assert out.count("AUREM_THEME_INJECTED") == 1


def test_inject_css_is_idempotent():
    from services.awb_theme_catalog import inject_theme_css
    html = "<html><head></head><body></body></html>"
    once = inject_theme_css(html, "Pit Crew")
    twice = inject_theme_css(once, "Pit Crew")
    assert once == twice
    assert twice.count("AUREM_THEME_INJECTED") == 1


def test_inject_css_no_head_falls_back_to_body():
    from services.awb_theme_catalog import inject_theme_css
    html = "<html><body>no head</body></html>"
    out = inject_theme_css(html, "Pit Crew")
    assert "#FF6B35" in out
    assert "AUREM_THEME_INJECTED" in out


def test_inject_css_empty_hint_returns_original():
    from services.awb_theme_catalog import inject_theme_css
    html = "<html><head></head></html>"
    assert inject_theme_css(html, None) == html
    assert inject_theme_css(html, "") == html
    assert inject_theme_css(html, {}) == html


def test_inject_css_unknown_theme_returns_original():
    from services.awb_theme_catalog import inject_theme_css
    html = "<html><head></head></html>"
    assert inject_theme_css(html, "Not A Real Theme") == html


def test_inject_css_includes_google_fonts_link():
    from services.awb_theme_catalog import inject_theme_css
    html = "<html><head></head></html>"
    out = inject_theme_css(html, "Pit Crew")
    assert "fonts.googleapis.com" in out
    # Space-encoded as +
    assert "Bebas+Neue" in out


def test_inject_css_cta_selectors_present():
    from services.awb_theme_catalog import inject_theme_css
    html = "<html><head></head></html>"
    out = inject_theme_css(html, "Pit Crew")
    # The CTA/button rules must be in the injected CSS
    assert ".cta" in out
    assert ".btn-primary" in out
    assert "background: var(--aurem-accent)" in out


def test_inject_css_accepts_flat_dict():
    from services.awb_theme_catalog import inject_theme_css
    html = "<html><head></head></html>"
    hint = {"style": {"primary_bg": "#000", "primary_text": "#fff",
                      "accent": "#ABC123",  "heading_color": "#FFF",
                      "body_font": "Inter", "heading_font": "Inter"}}
    out = inject_theme_css(html, hint)
    assert "#ABC123" in out
