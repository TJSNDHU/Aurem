"""iter 325p — V2 portal theme repalette to homepage colors.

Locks in:
  1. Homepage palette literally lives in dashboard-theme.css.
  2. Hardcoded Apple-style purple/blue/iOS-amber hex are gone from JSX.
  3. Both [data-theme='dark'] and [data-theme='light'] are updated.
  4. Backward-compat: the old --dash-purple/blue/etc. names still resolve
     (so existing components don't break) but point at the new palette.
  5. Audit trail — exact homepage hex values present in CSS.
"""
from __future__ import annotations

import os
import re

import pytest

CSS = "/app/frontend/src/styles/dashboard-theme.css"
LUXE_DIR = "/app/frontend/src/platform/luxe"

HOMEPAGE_PALETTE = {
    "void":   "#050508",
    "dark":   "#0A0A0F",
    "card":   "#0F0F1A",
    "orange": "#FF6B00",
    "orange2":"#FF8C35",
    "gold":   "#C9A84C",
    "gold2":  "#E8C86A",
    "white":  "#F0EDE8",
    "muted":  "#7A7590",
    "emerald":"#50C878",
    "red":    "#FF6060",
}


def _read(p):
    with open(p) as fh:
        return fh.read()


# 1. CSS contains every homepage hex
def test_homepage_palette_present_in_css():
    css = _read(CSS)
    for name, hex_ in HOMEPAGE_PALETTE.items():
        assert hex_ in css, f"Homepage color {name} ({hex_}) missing from CSS"


# 2. Old iOS-style accent hex are gone from the dark block
def test_no_legacy_purple_blue_ios_palette():
    css = _read(CSS)
    # Find the dark theme block
    start = css.find("[data-theme='dark']")
    end = css.find("[data-theme='light']")
    assert start > 0 and end > start
    dark_block = css[start:end]
    for stale in ("#5E54E8", "#0A84FF", "#34C759", "#FF9F0A", "#FF453A"):
        assert stale not in dark_block, \
            f"Legacy iOS hex {stale} still present in dark theme block"


# 3. Both theme blocks define the required surface vars
def test_both_themes_define_surface_vars():
    css = _read(CSS)
    for block in ("[data-theme='dark']", "[data-theme='light']"):
        start = css.find(block)
        end = css.find("}", start)
        assert start >= 0
        # Just check the first declaration block — vars must appear somewhere
        # after the marker; use the section up to the next selector
        next_section = css.find("[data-theme=", start + 1)
        section = css[start:next_section if next_section > 0 else len(css)]
        for var in ("--dash-bg", "--dash-card", "--dash-sidebar",
                    "--dash-text", "--dash-border",
                    "--dash-orange", "--dash-gold", "--dash-emerald"):
            assert var in section, f"{block} missing {var}"


# 4. Backward-compat: old var names still exist (so existing JSX doesn't break)
def test_backward_compat_var_names_retained():
    css = _read(CSS)
    for legacy in ("--dash-purple", "--dash-purple-soft", "--dash-blue",
                   "--dash-green", "--dash-amber", "--dash-red"):
        assert legacy in css, f"Backward-compat var {legacy} dropped — will break existing JSX"
    # And the *primary* alias maps to orange
    # Find a line like `--dash-purple:      #FF6B00;` in any block
    assert re.search(r"--dash-purple:\s*#FF6B00", css), \
        "--dash-purple must repoint to homepage orange #FF6B00"


# 5. Hardcoded Apple-style hex purged from JSX
def test_no_hardcoded_legacy_hex_in_jsx():
    bad_hex = ("#5E54E8", "#0A84FF", "#34C759")
    offenders = []
    for root, _, files in os.walk(LUXE_DIR):
        for fname in files:
            if not (fname.endswith(".jsx") or fname.endswith(".js")):
                continue
            p = os.path.join(root, fname)
            body = _read(p)
            for h in bad_hex:
                if h in body:
                    # Allow the Settings color-picker default value (user's
                    # *brand* primary_colour fallback, not a theme color).
                    # That literal lives in LuxeV2Pages.jsx and is intentional.
                    if h == "#5E54E8" and "primary_colour || '#5E54E8'" in body \
                            and body.count(h) == 1:
                        continue
                    offenders.append(f"{p}: {h}")
    assert not offenders, \
        f"Legacy iOS hex still hardcoded in JSX (use CSS vars instead): {offenders}"


# 6. Components use semantic CSS vars (not raw hex) for primary accents
@pytest.mark.parametrize("path", [
    f"{LUXE_DIR}/LuxeDashboardV2.jsx",
    f"{LUXE_DIR}/components/AgentBars.jsx",
    f"{LUXE_DIR}/components/PulseCard.jsx",
    f"{LUXE_DIR}/components/VanguardRing.jsx",
    f"{LUXE_DIR}/components/PipelineCard.jsx",
])
def test_components_use_css_vars(path):
    body = _read(path)
    # Each themed component must reference at least one --dash-* CSS var
    assert "var(--dash-" in body, f"{path}: no --dash-* CSS var references found"


# 7. Sidebar specifically uses the new orange nav-active bar
def test_active_nav_bar_is_orange():
    css = _read(CSS)
    # Dark block
    assert re.search(r"--dash-nav-active-bar:\s*#FF6B00", css), \
        "Nav active bar must be homepage orange #FF6B00"
