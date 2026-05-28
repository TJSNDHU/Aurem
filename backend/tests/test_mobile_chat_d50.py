"""
tests/test_mobile_chat_d50.py — iter D-50

Static-asset assertions for the mobile composer fix. Pure offline tests —
we don't spin up a browser; we verify the source contains the exact
selectors / classNames / media-queries that the fix relies on. This
guards against accidental removal during future refactors.
"""
from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSX = os.path.join(
    ROOT, "..", "frontend", "src", "platform", "developers",
    "DevCtoChatPanel.jsx",
)
CSS = os.path.join(
    ROOT, "..", "frontend", "src", "platform", "developers",
    "DevCtoChatPanel.mobile.css",
)
WIDGET = os.path.join(
    ROOT, "..", "frontend", "src", "components", "ORAWidget.jsx",
)


def _read(p: str) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def test_mobile_css_exists_and_targets_768px():
    src = _read(CSS)
    assert "@media (max-width: 768px)" in src


def test_mobile_css_stacks_composer():
    src = _read(CSS)
    # Composer becomes column on mobile so textarea sits ABOVE buttons.
    assert ".dev-cto-composer" in src
    assert "flex-direction: column" in src
    # Actions row reformatted as a flex row on mobile.
    assert ".dev-cto-composer-actions" in src


def test_mobile_css_planning_chips_horizontal_scroll():
    src = _read(CSS)
    assert '[data-testid="dev-cto-planning-bar"]' in src
    assert "flex-wrap: nowrap" in src
    assert "overflow-x: auto"  in src


def test_mobile_css_safe_area_padding():
    src = _read(CSS)
    # iPhone notch / home-indicator safe-area padding.
    assert "env(safe-area-inset-bottom" in src


def test_mobile_css_input_min_height_44px():
    src = _read(CSS)
    assert "min-height: 44px" in src


def test_jsx_imports_mobile_css():
    src = _read(JSX)
    assert "DevCtoChatPanel.mobile.css" in src


def test_jsx_has_composer_classname():
    src = _read(JSX)
    assert 'className="dev-cto-composer"' in src
    assert 'className="dev-cto-composer-actions"' in src


def test_widget_hides_on_mobile_via_media_query():
    src = _read(WIDGET)
    # iter D-50 — short-circuit return on hidden + matchMedia listener.
    assert "if (hidden) return null" in src
    assert "matchMedia('(max-width: 768px)')" in src
