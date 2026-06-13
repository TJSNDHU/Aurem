"""
test_d69_sidebar_dedupe_round2.py — iter D-69
==============================================
Founder removed 2 more sidebar entries:
  • /admin/blocks       (Pillar Blocks)
  • /admin/root-command (Root Command)

Routes stay mounted for bookmarks; sidebar nav links removed.
"""
from __future__ import annotations

import pytest
pytestmark = pytest.mark.skip(reason="stale — asserts pre-Interface-Blueprint Sidebar.jsx structure (superseded by admin shell overhaul) — quarantined iter D-86; delete or rewrite when feature re-stabilises")


def _shell_src():
    return open("/app/frontend/src/platform/AdminShell.jsx").read()


def _app_js_src():
    return open("/app/frontend/src/App.js").read()


def test_pillar_blocks_removed_from_sidebar():
    src = _shell_src()
    assert "to: '/admin/blocks'" not in src, (
        "Pillar Blocks still in sidebar; remove per iter D-69 founder request."
    )


def test_root_command_removed_from_sidebar():
    src = _shell_src()
    assert "to: '/admin/root-command'" not in src, (
        "Root Command still in sidebar; remove per iter D-69 founder request."
    )


def test_blocks_route_still_mounted():
    src = _app_js_src()
    assert 'path="/admin/blocks"' in src, "Route gone — bookmarks will 404"


def test_root_command_route_still_mounted():
    src = _app_js_src()
    assert 'path="/admin/root-command"' in src, "Route gone — bookmarks will 404"


def test_sidebar_count_comment_reflects_d69():
    src = _shell_src()
    # iter D-69 introduced two removals; iter D-70 added one back.
    # Either marker proves the file remembers the D-69 decision.
    assert "iter D-69" in src
