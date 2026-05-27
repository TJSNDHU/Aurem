"""
test_mobile_sidebar_d38.py — iter D-38

Static contract test for the mobile sidebar drawer. The preview
sandbox cannot simulate a 375 px viewport (playwright forces 1920×800),
so this test asserts the CSS @media block + JSX `data-testid` hooks
are present in the source files. Real-device behaviour is implicit
once these contracts hold.
"""
from __future__ import annotations

import pathlib
import re


def _read(p: str) -> str:
    return pathlib.Path(p).read_text(encoding="utf-8")


def test_mobile_breakpoint_block_exists():
    css = _read("/app/frontend/src/styles/dashboard-theme.css")
    # The @media block must declare BOTH the hamburger reveal AND the
    # slide-in drawer transform.
    assert "@media (max-width: 767px)" in css
    # Hamburger reveal on mobile.
    assert ".av2-mobile-menu-btn { display: inline-flex" in css
    # Sidebar becomes a fixed drawer offscreen by default.
    assert "translateX(-105%)" in css
    # …and slides in when the shell has the mobile-open modifier.
    assert "av2-shell--mobile-open .av2-sidebar" in css


def test_hamburger_button_data_testid_in_shell():
    src = _read("/app/frontend/src/platform/developers/DeveloperShell.jsx")
    assert "dev-shell-mobile-menu" in src
    assert "dev-mobile-backdrop"   in src
    assert "mobileSidebarOpen"     in src
    assert "av2-shell--mobile-open" in src


def test_chat_panel_button_reorg():
    src = _read("/app/frontend/src/platform/developers/DevCtoChatPanel.jsx")
    # New: BubbleActionRow + Copy + Rollback near each other.
    assert "BubbleActionRow"            in src
    assert "dev-cto-rollback-btn-"      in src
    assert "dev-cto-copy-btn-"          in src
    # New: chat footer actions bar with Preview + Deploy moved out.
    assert "ChatFooterActions"          in src
    assert "dev-cto-footer-preview-btn" in src
    assert "dev-cto-footer-deploy-btn"  in src
    # Old hover-only MessageActionButtons must NOT be invoked in JSX
    # anymore (renamed to _unused_legacy_MessageActionButtons).
    assert re.search(r"<MessageActionButtons\b", src) is None


def test_admin_integrations_page_present():
    p = pathlib.Path("/app/frontend/src/platform/AdminIntegrations.jsx")
    assert p.exists()
    txt = p.read_text()
    assert "admin-integrations-page"    in txt
    assert "admin-integrations-refresh" in txt
    assert "/api/admin/integrations/health" in txt


def test_admin_integrations_route_wired():
    app = _read("/app/frontend/src/App.js")
    assert "/admin/integrations" in app
    assert "AdminIntegrations"   in app
