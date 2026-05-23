"""
iter 326zz — git_log as Tier-1 read-only tool
==============================================

Founder need (verbatim):
  "ORA was getting stuck trying to answer 'is .env.production
   in git history?' — shell_exec is gated, council kept looping.
   Give ORA a Tier-1 read-only git_log tool so she can answer
   the question herself."

Public answer to the original question (proven by this test
running `git log` on the real repo):
  - frontend/.env.production IS committed in commit b67fb41
    (iter 323o, May 18 2026). Content: single line
    `REACT_APP_BACKEND_URL=https://aurem.live` — public URL, no
    secrets.
  - backend/.env.production is NOT committed (gitignored).

Tool surface:
  git_log({"path": "...", "limit": 5})  -- repo-rooted at /app
    → {ok, committed, last_commit_hash, last_commit_date,
       last_commit_msg, commits[], gitignored}
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# Function exists + registered
# ─────────────────────────────────────────────

def test_git_log_helper_defined():
    from services.ora_tools import _ora_git_log
    assert callable(_ora_git_log)


def test_git_log_registered_as_tier1_tool():
    from services.ora_tools import TOOL_REGISTRY
    assert "git_log" in TOOL_REGISTRY
    meta = TOOL_REGISTRY["git_log"]
    assert "fn" in meta and callable(meta["fn"])
    assert "args_spec" in meta and "path" in meta["args_spec"]
    assert "limit" in meta["args_spec"]
    assert "TIER 1" in meta["description"]


def test_system_prompt_lists_git_log_under_tier1():
    """ORA's brain must know git_log is auto-execute."""
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    idx = src.index("SYSTEM_PROMPT = ")
    block = src[idx: idx + 10000]
    t1_idx = block.index("TIER 1 (auto)")
    t1_end = block.index("TIER 2 (approve)")
    t1 = block[t1_idx:t1_end]
    assert "git_log" in t1, "git_log must be in the Tier 1 list"
    # And the prompt must hint at the use-case so the LLM picks it up
    assert "is this file committed" in t1.lower() or "committed?" in t1.lower()


# ─────────────────────────────────────────────
# Real run — invoke against this very repo
# ─────────────────────────────────────────────

def test_committed_file_returns_committed_true():
    """Run against this very test file — known to exist in tree.
    `committed` may be True (if already commit) or False (if not yet
    committed); either way the call must succeed with a real result."""
    from services.ora_tools import _ora_git_log
    r = asyncio.run(_ora_git_log(
        path="backend/services/ora_tools.py", limit=3))
    assert r["ok"] is True
    assert r["committed"] is True
    assert r["last_commit_hash"] is not None
    assert len(r["last_commit_hash"]) == 7
    assert r["last_commit_date"] is not None
    assert "T" in r["last_commit_date"]    # ISO 8601 has a T
    assert len(r["commits"]) > 0
    # Each commit must have the canonical shape
    for c in r["commits"]:
        for k in ("sha", "sha_full", "date", "author", "msg"):
            assert k in c, f"commit missing key {k}"


def test_uncommitted_file_returns_committed_false(tmp_path):
    """A file that exists nowhere in git history must return
    committed=False with no crash."""
    from services.ora_tools import _ora_git_log
    # Use a path that's definitely not in git
    r = asyncio.run(_ora_git_log(
        path="backend/this_file_definitely_does_not_exist_326zz.py",
        limit=5))
    assert r["ok"] is True
    assert r["committed"] is False
    assert r["last_commit_hash"] is None
    assert r["commits"] == []


def test_repo_root_overview_when_path_empty():
    """Empty path returns the latest N commits across the whole repo."""
    from services.ora_tools import _ora_git_log
    r = asyncio.run(_ora_git_log(path="", limit=3))
    assert r["ok"] is True
    assert len(r["commits"]) > 0
    assert r["path"] == "<repo root>"


def test_path_outside_repo_rejected():
    """Path must resolve inside /app — no /etc/passwd shenanigans."""
    from services.ora_tools import _ora_git_log
    r = asyncio.run(_ora_git_log(path="/etc/passwd", limit=1))
    assert r["ok"] is False
    assert "outside repo" in r["error"]


def test_shell_metachars_rejected():
    from services.ora_tools import _ora_git_log
    for hostile in ("a; rm -rf /", "x | cat", "y && id", "$(whoami)",
                     "`id`", "a\nb"):
        r = asyncio.run(_ora_git_log(path=hostile, limit=1))
        assert r["ok"] is False, f"should reject: {hostile!r}"
        assert "shell metachars" in r["error"]


def test_limit_capped_at_20():
    from services.ora_tools import _ora_git_log
    r = asyncio.run(_ora_git_log(path="", limit=999))
    assert r["ok"] is True
    assert len(r["commits"]) <= 20


def test_limit_floor_at_1():
    from services.ora_tools import _ora_git_log
    r = asyncio.run(_ora_git_log(path="", limit=0))
    assert r["ok"] is True
    # Floor to 1
    assert len(r["commits"]) >= 1


def test_limit_handles_non_int_gracefully():
    from services.ora_tools import _ora_git_log
    r = asyncio.run(_ora_git_log(path="", limit="not-a-number"))
    assert r["ok"] is True
    assert len(r["commits"]) > 0  # falls back to default 5


# ─────────────────────────────────────────────
# Real-world: answer the founder's exact question
# ─────────────────────────────────────────────

def test_real_question_is_frontend_env_production_in_git():
    """frontend/.env.production should come back as COMMITTED
    (per commit b67fb41 from iter 323o)."""
    from services.ora_tools import _ora_git_log
    r = asyncio.run(_ora_git_log(
        path="frontend/.env.production", limit=2))
    assert r["ok"] is True
    assert r["committed"] is True, \
        ("frontend/.env.production should be in git history "
         "(commit b67fb41 / iter 323o)")


# ─────────────────────────────────────────────
# Dispatcher-level: invoke_tool routes to git_log
# ─────────────────────────────────────────────

def test_invoke_tool_routes_git_log_as_tier1():
    """Going through the public dispatcher must NOT trip the gated-
    tool denylist or require council — git_log is plain Tier 1."""
    from services.ora_tools import invoke_tool
    r = asyncio.run(invoke_tool(
        "git_log",
        {"path": "backend/services/ora_tools.py", "limit": 2},
        actor="pytest:326zz",
    ))
    assert r["ok"] is True
    assert r["committed"] is True
    assert r["tool"] == "git_log"
    # Must NOT carry the auto-redirect tag (we're not gated)
    assert "_redirected_from" not in r


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_326zz_marker_present():
    src = (BACKEND / "services" / "ora_tools.py").read_text()
    assert "326zz" in src
