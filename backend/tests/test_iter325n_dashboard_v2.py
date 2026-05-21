"""iter 325n — Dashboard V2 contract tests.

Structural / source-grep tests that lock in the redesign spec without
needing a React test runner. Each test maps to a numbered requirement
from the spec prompt.
"""
from __future__ import annotations

import os
import re

import pytest

FRONTEND = "/app/frontend/src"
PLATFORM = f"{FRONTEND}/platform/luxe"
COMPONENTS = f"{PLATFORM}/components"
THEME_CSS = f"{FRONTEND}/styles/dashboard-theme.css"
MAIN = f"{PLATFORM}/LuxeDashboardV2.jsx"
HOOK = f"{PLATFORM}/useLuxeDashboardData.js"
THEME_HOOK = f"{PLATFORM}/useTheme.js"
APP_JS = f"{FRONTEND}/App.js"


def _read(p: str) -> str:
    with open(p) as fh:
        return fh.read()


# ─────────────────────────────────────────────────────────────────
# 1. Every spec file was created and lints clean
# ─────────────────────────────────────────────────────────────────

REQUIRED_FILES = [
    THEME_CSS,
    THEME_HOOK,
    MAIN,
    f"{COMPONENTS}/PulseCard.jsx",
    f"{COMPONENTS}/AgentBars.jsx",
    f"{COMPONENTS}/VanguardRing.jsx",
    f"{COMPONENTS}/PipelineCard.jsx",
    f"{COMPONENTS}/BottomTabBar.jsx",
    f"{COMPONENTS}/MetricRow.jsx",
    f"{COMPONENTS}/BusinessGrowthChart.jsx",
    f"{COMPONENTS}/WebsiteScanCard.jsx",
    f"{COMPONENTS}/InboxCard.jsx",
]


def test_all_spec_files_exist():
    missing = [p for p in REQUIRED_FILES if not os.path.exists(p)]
    assert not missing, f"Missing spec files: {missing}"


# ─────────────────────────────────────────────────────────────────
# 2. Desktop render contract — required testids in main shell
# ─────────────────────────────────────────────────────────────────

def test_desktop_render_contract_has_required_testids():
    src = _read(MAIN)
    # Literal testids
    literal = [
        "aurem-v2-root", "sidebar", "topbar", "page-content",
        "theme-toggle", "topbar-bell", "topbar-search",
        "user-avatar", "sidebar-logout",
    ]
    missing = [t for t in literal if f'"{t}"' not in src and f"'{t}'" not in src]
    assert not missing, f"Missing literal data-testid: {missing}"
    # Template-literal testid `nav-${k}` — verify pattern + every nav key.
    assert "data-testid={`nav-${k}`}" in src, "nav-${k} testid pattern missing"
    for key in ("home", "live-health", "security", "crm", "ora",
                "automation", "settings"):
        assert f"k: '{key}'" in src, f"Nav key missing in NAV_SECTIONS: {key}"


# ─────────────────────────────────────────────────────────────────
# 3. Mobile layout — bottom tab visible <768, sidebar hidden
# ─────────────────────────────────────────────────────────────────

def test_mobile_layout_css_contract():
    css = _read(THEME_CSS)
    # Extract the @media (max-width: 767px) block. Manual extraction
    # because regex with nested braces is fragile.
    start = css.find("@media (max-width: 767px)")
    assert start >= 0, "Missing @media (max-width: 767px) block"
    # Find matching close brace by counting depth
    depth = 0
    end = -1
    open_at = css.find("{", start)
    assert open_at > 0
    for i in range(open_at, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    block = css[start:end + 1]
    assert ".av2-sidebar { display: none" in block, \
        "Sidebar must be display:none inside the mobile media query"
    assert re.search(r"\.av2-bottom-tabs\s*\{\s*display:\s*flex", block), \
        "Bottom tab bar must become display:flex on mobile"
    # And default state on desktop must be display:none
    assert re.search(
        r"\.av2-bottom-tabs\s*\{[^@]*display:\s*none",
        css,
    ), "Bottom tab bar must default to display:none on desktop"


def test_bottom_tab_bar_has_5_tabs():
    bar = _read(f"{COMPONENTS}/BottomTabBar.jsx")
    # Template-literal testid + 5 tab keys
    assert "data-testid={`bottom-tab-${k}`}" in bar
    for k in ("home", "automation", "ora", "inbox", "settings"):
        assert f"k: '{k}'" in bar, f"Missing bottom tab key: {k}"


def test_safe_area_inset_respected():
    css = _read(THEME_CSS)
    assert "env(safe-area-inset-bottom)" in css, \
        "iPhone safe-area-inset-bottom must be in CSS for bottom tabs"


# ─────────────────────────────────────────────────────────────────
# 4. Theme toggle — dark / light / auto + localStorage persist
# ─────────────────────────────────────────────────────────────────

def test_theme_hook_contract():
    src = _read(THEME_HOOK)
    assert "prefers-color-scheme" in src
    assert "aurem_theme" in src         # localStorage key
    assert "data-theme" in src          # attribute applied on element
    assert "addEventListener" in src    # subscribes to OS change


def test_css_defines_both_theme_var_blocks():
    css = _read(THEME_CSS)
    assert "[data-theme='dark']" in css or '[data-theme="dark"]' in css
    assert "[data-theme='light']" in css or '[data-theme="light"]' in css
    # Required spec vars
    for var in ("--dash-bg", "--dash-card", "--dash-border",
                "--dash-sidebar", "--dash-text",
                "--dash-text-muted", "--dash-text-faint"):
        assert var in css, f"Missing CSS var: {var}"


def test_css_uses_exact_spec_brand_colors():
    css = _read(THEME_CSS)
    for color in ("#080810", "#06060d", "#5E54E8", "#0A84FF",
                  "#34C759", "#FF9F0A", "#FF453A", "#BF5AF2"):
        assert color in css, f"Spec brand color missing: {color}"


def test_css_uses_apple_font_stack():
    css = _read(THEME_CSS)
    assert "-apple-system" in css
    assert "BlinkMacSystemFont" in css
    assert "SF Pro Display" in css


# ─────────────────────────────────────────────────────────────────
# 5. Data binding — every spec endpoint flows into the V2 hook
# ─────────────────────────────────────────────────────────────────

def test_data_hook_surfaces_v2_fields():
    src = _read(HOOK)
    # Endpoints
    for ep in (
        "/api/me/home/dashboard",
        "/api/customer/vanguard/status",
        "/api/customer/results-summary",
        "/api/customer/results-pipeline",
        "/api/aurem/agents/status",
        "/api/customer/inbox/threads",
        "/api/repair/scores",
    ):
        assert ep in src, f"V2 hook must call {ep}"
    # Top-level surfaces consumed by new components
    for k in ("resultsSummary", "pipelineStages", "pipelineTotal",
              "inboxThreads", "inboxUnread", "lastUpdated"):
        assert k in src, f"Missing V2 surface: {k}"


def test_components_consume_hook_props():
    main = _read(MAIN)
    # Spec wiring map → exact prop pass-through
    assert "data?.totalRevenue" in main
    assert "data?.vanguard" in main
    assert "data?.websiteScan" in main
    assert "data?.agents" in main


# ─────────────────────────────────────────────────────────────────
# 6. Auto-refresh — 30s interval preserved
# ─────────────────────────────────────────────────────────────────

def test_30s_auto_refresh_interval():
    src = _read(HOOK)
    assert re.search(r"setInterval\(\s*refresh\s*,\s*30000", src), \
        "Auto-refresh interval must stay at 30000ms"


# ─────────────────────────────────────────────────────────────────
# 7. Responsive breakpoints — desktop / tablet / mobile all present
# ─────────────────────────────────────────────────────────────────

def test_three_responsive_breakpoints():
    css = _read(THEME_CSS)
    # Tablet: 768-1023 — sidebar collapses to 56px icon rail
    assert re.search(
        r"@media\s*\(\s*min-width:\s*768px\s*\)\s*and\s*\(\s*max-width:\s*1023px\s*\)",
        css,
    ), "Tablet breakpoint missing"
    assert "56px 1fr" in css, "Tablet sidebar must collapse to 56px"
    # Mobile already verified in test_mobile_layout_css_contract
    # Desktop default grid 210px 1fr per spec
    assert "210px 1fr" in css, "Desktop sidebar must be 210px"


# ─────────────────────────────────────────────────────────────────
# 8. Backward compatibility — /my route untouched, internal pages preserved
# ─────────────────────────────────────────────────────────────────

def test_my_route_points_to_v2_dashboard():
    app = _read(APP_JS)
    assert 'from \'./platform/luxe/LuxeDashboardV2\'' in app, \
        "App.js must import LuxeDashboardV2 (V2 redesign)"
    assert 'path="/my"' in app, "/my route must remain"


def test_internal_pages_still_routed():
    """CRM / Settings / ORA / etc. must still mount their LuxePages."""
    main = _read(MAIN)
    for page in ("LiveHealthPage", "SecurityPage", "AutomationPage",
                 "CRMPage", "ORAPage", "SettingsPage"):
        assert page in main, f"V2 shell must keep mounting {page}"


# ─────────────────────────────────────────────────────────────────
# 9. Spec card layout — Pulse / 4-metric / 3-col / 2-col / Inbox
# ─────────────────────────────────────────────────────────────────

def test_home_view_card_order():
    main = _read(MAIN)
    # Spec order: PulseCard → MetricRow → 3-col grid → 2-col grid → InboxCard
    pulse = main.find("<PulseCard")
    metric = main.find("<MetricRow")
    grid32 = main.find('className="av2-grid-3-2"')
    grid2 = main.find('className="av2-grid-2"')
    inbox = main.find("<InboxCard")
    order = [pulse, metric, grid32, grid2, inbox]
    assert all(o >= 0 for o in order), f"Missing card: {order}"
    assert order == sorted(order), f"Card order violates spec: {order}"


def test_pulse_card_accent_background():
    pulse = _read(f"{COMPONENTS}/PulseCard.jsx")
    assert 'className="av2-card-accent"' in pulse
    css = _read(THEME_CSS)
    # Spec accent gradient angles & alphas
    assert re.search(
        r"linear-gradient\(135deg,\s*rgba\(94,\s*84,\s*232,\s*0\.18\)",
        css,
    )


def test_card_primitive_radius_and_border():
    css = _read(THEME_CSS)
    assert re.search(r"\.av2-card\s*\{[^}]*border-radius:\s*14px", css, re.DOTALL)
    assert re.search(
        r"\.av2-card\s*\{[^}]*border:\s*1px solid var\(--dash-border\)",
        css, re.DOTALL,
    )
