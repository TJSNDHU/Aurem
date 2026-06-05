"""
test_d68_sidebar_dedupe.py — iter D-68
=======================================
Locks in the removal of 3 confirmed sidebar duplicates whose
functionality already exists as embedded panels / tabs elsewhere.

Removed from sidebar (but routes still mounted in App.js for bookmarks):
  • /admin/console      → "Console" tab inside /admin/ora
  • /admin/stem-fix     → PendingCodeFixesPanel in /admin/pillars-map
  • /admin/self-repair  → AutonomousRepairPanel in /admin/pillars-map
"""
from __future__ import annotations


def _shell_src():
    return open("/app/frontend/src/platform/AdminShell.jsx").read()


def _pillars_map_src():
    return open("/app/frontend/src/platform/AdminPillarsMap.jsx").read()


def _ora_unified_src():
    return open("/app/frontend/src/platform/admin/OraAdminUnified.jsx").read()


def _app_js_src():
    return open("/app/frontend/src/App.js").read()


# ─── 1 · Removed entries don't appear in AdminShell's SIDEBAR_TREE ─
def test_founders_console_removed_from_sidebar():
    src = _shell_src()
    assert "to: '/admin/console'" not in src, (
        "Founders Console still in sidebar; it duplicates the Console "
        "tab inside /admin/ora."
    )


def test_stem_fix_removed_from_sidebar():
    src = _shell_src()
    assert "to: '/admin/stem-fix'" not in src, (
        "Stem-Fix still in sidebar; PendingCodeFixesPanel renders "
        "the same data inside Pillars Map."
    )


def test_self_repair_removed_from_sidebar():
    src = _shell_src()
    assert "to: '/admin/self-repair'" not in src, (
        "Self-Repair still in sidebar; AutonomousRepairPanel renders "
        "inside Pillars Map."
    )


# ─── 2 · Routes still mounted in App.js (no dead bookmarks) ────────
def test_console_route_still_mounted():
    src = _app_js_src()
    assert 'path="/admin/console"' in src, (
        "Removed from sidebar but route should remain for bookmarks."
    )


def test_stem_fix_route_still_mounted():
    src = _app_js_src()
    assert 'path="/admin/stem-fix"' in src


def test_self_repair_route_still_mounted():
    src = _app_js_src()
    assert 'path="/admin/self-repair"' in src


# ─── 3 · Duplicated functionality IS present at the new home ──────
def test_pillars_map_embeds_pending_code_fixes_panel():
    src = _pillars_map_src()
    assert "PendingCodeFixesPanel" in src, (
        "Pillars Map must embed the stem-fix queue panel — otherwise "
        "removing /admin/stem-fix orphans the feature."
    )


def test_pillars_map_embeds_autonomous_repair_panel():
    src = _pillars_map_src()
    assert "AutonomousRepairPanel" in src, (
        "Pillars Map must embed the self-repair panel."
    )


def test_ora_unified_contains_console_tab():
    """Console tab must exist inside ORA · Unified for the removed
    /admin/console to have a working replacement."""
    src = _ora_unified_src()
    # The component imports AdminConsole as the inner Console tab.
    assert "AdminConsole" in src or "Console" in src


# ─── 4 · Migration breadcrumb in source ───────────────────────────
def test_sidebar_comment_documents_removals():
    """The reason for removal is documented in the source so the next
    refactor doesn't accidentally re-add the duplicates."""
    src = _shell_src()
    assert "iter D-68" in src
    assert "removed" in src.lower()
