"""
tests/test_codebase_map_d55.py — iter D-55

  • /file/tree endpoint exists, walks the sandbox, returns real files
  • Tree respects max_depth + blocklist
  • Frontend wiring: CodebaseMap.jsx mounted, click-to-inject wired
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_tree_endpoint_registered():
    from routers import cto_codebase_router as mod
    paths = {r.path for r in mod.router.routes}
    assert "/api/developers/cto/file/tree" in paths


def test_tree_walks_backend_routers():
    """Default base 'backend' must return real files (registry.py etc)."""
    from routers import cto_codebase_router as mod

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    out = asyncio.run(mod.file_tree(
        path="backend/routers", max_depth=1, authorization="Bearer x"))
    assert out["ok"] is True
    assert out["base"] == "backend/routers"
    names = {f["name"] for f in out["files"]}
    assert "registry.py"             in names
    assert "cto_codebase_router.py"  in names
    assert "cto_tools_router.py"     in names


def test_tree_respects_max_depth():
    from routers import cto_codebase_router as mod

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    out_d1 = asyncio.run(mod.file_tree(path="backend", max_depth=1,
                                          authorization="Bearer x"))
    out_d3 = asyncio.run(mod.file_tree(path="backend", max_depth=3,
                                          authorization="Bearer x"))
    assert out_d3["count"]["files"] > out_d1["count"]["files"]


def test_tree_excludes_pycache_and_env():
    from routers import cto_codebase_router as mod

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    out = asyncio.run(mod.file_tree(path="backend", max_depth=2,
                                       authorization="Bearer x"))
    all_paths = {f["path"] for f in out["files"]}
    all_dirs  = {d["path"] for d in out["dirs"]}
    for p in all_paths | all_dirs:
        assert "__pycache__" not in p, p
        assert ".git/"       not in p, p
        # The bare .env file is blocked; .env.example is OK (it's a
        # template, not a secret).
        assert os.path.basename(p) != ".env", p


def test_tree_404_for_missing_dir():
    from routers import cto_codebase_router as mod

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    with pytest.raises(HTTPException) as ei:
        asyncio.run(mod.file_tree(path="backend/does_not_exist",
                                     max_depth=1, authorization="Bearer x"))
    assert ei.value.status_code == 404


# ── Frontend wiring ─────────────────────────────────────────────────

def _read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


FRONTEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "..", "frontend", "src", "platform", "developers")
)
MAP_FILE   = os.path.join(FRONTEND, "CodebaseMap.jsx")
PANEL_FILE = os.path.join(FRONTEND, "DevCtoChatPanel.jsx")


def test_codebase_map_component_exists():
    assert os.path.exists(MAP_FILE)
    src = _read(MAP_FILE)
    assert "/api/developers/cto/file/tree" in src
    assert "onPick" in src


def test_chat_panel_mounts_drawer_and_toggle():
    src = _read(PANEL_FILE)
    assert "import CodebaseMap" in src
    assert "showCodebaseMap" in src
    assert 'data-testid="dev-cto-chat-codebase-toggle"' in src
    assert 'data-testid="dev-cto-codebase-drawer"' in src


def test_click_to_inject_uses_slash_file():
    """Click handler must prepend `/file <path>` to the textarea so the
    D-54 chat injection fires on the next Send."""
    src = _read(PANEL_FILE)
    assert "/file ${path}" in src or "`/file ${path}`" in src
