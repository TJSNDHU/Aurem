"""
tests/test_cto_codebase_d54.py — iter D-54

Real file + GitHub access for the CTO chat. Critical assertions:
  • sandbox: paths outside /app rejected
  • blocklist: .env, .git, *.pem rejected
  • happy path: line 43 of aurem_routes.py returns the REAL bytes
  • search: substring matches return real (path, line, text)
  • chat injection: "line 43 of routers/aurem_routes.py" injects a
    system message containing the actual file content
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


# ── Sandbox / blocklist ─────────────────────────────────────────────

def test_resolve_safe_rejects_path_traversal():
    from routers.cto_codebase_router import _resolve_safe
    with pytest.raises(HTTPException) as ei:
        _resolve_safe("../etc/passwd")
    assert ei.value.status_code == 403


def test_resolve_safe_rejects_absolute_outside_app():
    from routers.cto_codebase_router import _resolve_safe
    with pytest.raises(HTTPException) as ei:
        _resolve_safe("/etc/passwd")
    assert ei.value.status_code == 403


def test_resolve_safe_rejects_env_file():
    from routers.cto_codebase_router import _resolve_safe
    with pytest.raises(HTTPException) as ei:
        _resolve_safe("backend/.env")
    assert ei.value.status_code == 403


def test_resolve_safe_rejects_git_dir():
    from routers.cto_codebase_router import _resolve_safe
    # .git path itself may not exist as a file, but the glob rule fires
    # whenever the resolved path matches **/.git/**.
    from pathlib import Path
    if not Path("/app/.git/HEAD").exists():
        pytest.skip(".git/HEAD not present in this env")
    with pytest.raises(HTTPException) as ei:
        _resolve_safe(".git/HEAD")
    assert ei.value.status_code == 403


def test_resolve_safe_allows_app_file():
    from routers.cto_codebase_router import _resolve_safe
    p = _resolve_safe("backend/routers/aurem_routes.py")
    assert str(p).endswith("backend/routers/aurem_routes.py")


# ── Real read ───────────────────────────────────────────────────────

def test_read_file_returns_real_line_43():
    """Founder's smoke test — line 43 of aurem_routes.py must be the
    REAL bytes from disk, not a guess."""
    from routers.cto_codebase_router import read_file

    async def _fake_admin(_a): return "admin@aurem.live"
    from routers import cto_codebase_router as mod
    mod._require_admin = _fake_admin

    out = asyncio.run(read_file(
        path="backend/routers/aurem_routes.py",
        start_line=43, end_line=43, authorization="Bearer x",
    ))
    assert out["ok"]      is True
    assert out["returned"]["count"] == 1
    line43 = out["lines"][0]
    assert line43["n"] == 43

    # Ground-truth comparison — re-read the file directly and compare.
    with open("/app/backend/routers/aurem_routes.py",
                "r", encoding="utf-8") as f:
        raw_lines = f.read().split("\n")
    assert line43["text"] == raw_lines[42]


def test_read_file_404_for_missing():
    from routers import cto_codebase_router as mod

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    with pytest.raises(HTTPException) as ei:
        asyncio.run(mod.read_file(
            path="backend/does_not_exist.py",
            start_line=1, end_line=10, authorization="Bearer x",
        ))
    assert ei.value.status_code == 404


# ── Search ──────────────────────────────────────────────────────────

def test_search_returns_real_matches():
    from routers import cto_codebase_router as mod

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    out = asyncio.run(mod.search_codebase(
        q="aurem_scheduler", path_glob="backend/routers/registry.py",
        case_insensitive=True, authorization="Bearer x",
    ))
    assert out["ok"] is True
    # We know registry.py mentions aurem_scheduler in many places.
    assert len(out["matches"]) >= 1
    assert out["matches"][0]["path"].endswith("registry.py")
    assert "aurem_scheduler" in out["matches"][0]["text"].lower()


# ── Chat injection ──────────────────────────────────────────────────

def test_chat_injection_injects_real_file_content():
    """The user-message intent detector must:
      • catch "line N of <path>" phrasing
      • read the REAL file
      • inject a system message containing those exact lines

    This is what stops the CTO from "imagining" code.
    """
    from services.dev_cto_chat import _maybe_inject_codebase
    user_msg = "what is line 43 of backend/routers/aurem_routes.py?"
    full_messages = [
        {"role": "system", "content": "(big system prompt)"},
        {"role": "user",   "content": user_msg},
    ]
    out = asyncio.run(_maybe_inject_codebase(full_messages,
                                              [{"role": "user",
                                                 "content": user_msg}]))
    # Must have inserted ONE system message before the user turn
    assert len(out) == 3, out
    injected = out[-2]
    assert injected["role"] == "system"
    assert "Real file contents" in injected["content"]
    assert "aurem_routes.py"      in injected["content"]
    # Line 43 should be present (formatted "  43 | ...")
    assert "  43 |"               in injected["content"]


def test_chat_injection_handles_slash_file_command():
    from services.dev_cto_chat import _maybe_inject_codebase
    user_msg = "/file backend/routers/aurem_routes.py 40 50"
    full_messages = [
        {"role": "user", "content": user_msg},
    ]
    out = asyncio.run(_maybe_inject_codebase(full_messages,
                                              [{"role": "user",
                                                 "content": user_msg}]))
    assert len(out) == 2
    injected = out[-2]
    assert injected["role"] == "system"
    assert "lines 40–50" in injected["content"]


def test_chat_injection_silent_on_irrelevant_turn():
    from services.dev_cto_chat import _maybe_inject_codebase
    user_msg = "what's the weather today?"
    msgs = [{"role": "user", "content": user_msg}]
    out = asyncio.run(_maybe_inject_codebase(msgs, msgs))
    # No injection — return list unchanged
    assert out == msgs


def test_chat_injection_refuses_env_file():
    """The "show me <path>" pattern must NEVER let the LLM read .env."""
    from services.dev_cto_chat import _maybe_inject_codebase
    user_msg = "show me backend/.env"
    msgs = [{"role": "user", "content": user_msg}]
    out = asyncio.run(_maybe_inject_codebase(msgs, msgs))
    assert out == msgs   # no injection → no secret exposure


# ── Router wiring ───────────────────────────────────────────────────

def test_codebase_routes_registered():
    from routers import cto_codebase_router as mod
    paths = {r.path for r in mod.router.routes}
    assert "/api/developers/cto/file"             in paths
    assert "/api/developers/cto/file/search"      in paths
    assert "/api/developers/cto/github/commits"   in paths
