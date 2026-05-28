"""
tests/test_cto_verify_d52.py — iter D-52

Covers the 3-layer auto-verification surface:
  /api/developers/cto/verify/code     (offline syntax check)
  /api/developers/cto/verify/github   (real commits API, stubbed httpx)
  /api/developers/cto/verify/deploy   (polls /api/version, stubbed httpx)
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ──────────────────────────────────────────────────────────────────
# Stubs
# ──────────────────────────────────────────────────────────────────

class _Coll:
    def __init__(self):
        self._rows = []
    async def insert_one(self, doc):
        self._rows.append(dict(doc))
        return type("R", (), {"inserted_id": "x"})
    async def find_one(self, q, p=None, sort=None):
        return self._rows[0] if self._rows else None


class _DB:
    def __init__(self):
        self.developer_github_links = _Coll()
        self.cto_verify_runs        = _Coll()


# ──────────────────────────────────────────────────────────────────
# CODE verification
# ──────────────────────────────────────────────────────────────────

def test_code_python_valid():
    from routers.cto_verify_router import _verify_python
    ok, err = _verify_python("def f(x):\n    return x + 1\n")
    assert ok is True
    assert err == ""


def test_code_python_invalid():
    from routers.cto_verify_router import _verify_python
    ok, err = _verify_python("def broken(:\n  pass")
    assert ok is False
    assert "line" in err


def test_code_js_valid():
    from routers.cto_verify_router import _verify_js
    ok, err = _verify_js("function f(x) { return x + 1; }")
    assert ok is True
    assert err == ""


def test_code_js_unbalanced():
    from routers.cto_verify_router import _verify_js
    ok, err = _verify_js("function f() { return 1;")  # missing }
    assert ok is False
    assert "unclosed" in err


def test_code_js_unfinished_placeholder():
    from routers.cto_verify_router import _verify_js
    ok, err = _verify_js("<unfinished>\nconst x = 1;\n")
    assert ok is False
    assert "placeholder" in err


def test_code_js_handles_strings_and_comments():
    from routers.cto_verify_router import _verify_js
    src = """
      // not really { unbalanced
      const s = "a { b";
      /* still ok ( */
      const t = `template ${x ? 1 : 2}`;
      function g(){ return 1; }
    """
    ok, err = _verify_js(src)
    assert ok is True, err


def test_code_endpoint_audit():
    """Verify endpoint writes to cto_verify_runs."""
    from routers import cto_verify_router as mod
    db = _DB()
    mod.set_db(db)

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    body = mod.CodeBody(language="python", source="x = 1\n")
    out = asyncio.run(mod.verify_code(body, authorization="Bearer x"))
    assert out["valid"] is True
    assert len(db.cto_verify_runs._rows) == 1
    assert db.cto_verify_runs._rows[0]["tool"] == "verify_code"


# ──────────────────────────────────────────────────────────────────
# GITHUB verification — stub httpx
# ──────────────────────────────────────────────────────────────────

class _MockResp:
    def __init__(self, status_code, payload, text=""):
        self.status_code = status_code
        self._payload    = payload
        self.text        = text or str(payload)
    def json(self): return self._payload


class _MockAsyncClient:
    def __init__(self, *_args, **_kw): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *_a): return None
    # set_response is monkey-patched per-test
    _resp: _MockResp = _MockResp(200, [])
    async def get(self, url, headers=None):
        return type(self)._resp


def test_github_no_token_returns_red(monkeypatch):
    from routers import cto_verify_router as mod
    db = _DB()
    mod.set_db(db)
    monkeypatch.setenv("GITHUB_BOT_PAT", "")
    monkeypatch.setenv("GITHUB_TOKEN", "")

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    body = mod.GithubBody(owner="TJSNDHU", repo="Aurem")
    out = asyncio.run(mod.verify_github(body, authorization="Bearer x"))
    assert out["found"] is False
    assert out["error"] == "no_github_token"


def test_github_found_real_commit(monkeypatch):
    from routers import cto_verify_router as mod
    db = _DB()
    db.developer_github_links._rows = [{"access_token": "gho_test"}]
    mod.set_db(db)

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    _MockAsyncClient._resp = _MockResp(200, [{
        "sha": "abc1234deadbeef",
        "html_url": "https://github.com/TJSNDHU/Aurem/commit/abc1234",
        "commit": {"message": "iter D-52 — verification",
                    "committer": {"date": "2026-05-28T04:30:00Z"}},
    }])
    monkeypatch.setattr(mod.httpx, "AsyncClient", _MockAsyncClient)

    body = mod.GithubBody(owner="TJSNDHU", repo="Aurem")
    out = asyncio.run(mod.verify_github(body, authorization="Bearer x"))
    assert out["found"]    is True
    assert out["short_sha"] == "abc1234"
    assert "D-52" in out["message"]


def test_github_no_commit_returns_red(monkeypatch):
    from routers import cto_verify_router as mod
    db = _DB()
    db.developer_github_links._rows = [{"access_token": "gho_test"}]
    mod.set_db(db)

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    _MockAsyncClient._resp = _MockResp(200, [])  # empty
    monkeypatch.setattr(mod.httpx, "AsyncClient", _MockAsyncClient)

    body = mod.GithubBody(owner="TJSNDHU", repo="Aurem")
    out = asyncio.run(mod.verify_github(body, authorization="Bearer x"))
    assert out["found"] is False
    assert out["error"] == "no_recent_commit"


def test_github_sha_mismatch_returns_red(monkeypatch):
    from routers import cto_verify_router as mod
    db = _DB()
    db.developer_github_links._rows = [{"access_token": "gho_test"}]
    mod.set_db(db)

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    _MockAsyncClient._resp = _MockResp(200, [{
        "sha": "abc1234deadbeef",
        "html_url": "x", "commit": {"committer": {"date": ""}},
    }])
    monkeypatch.setattr(mod.httpx, "AsyncClient", _MockAsyncClient)

    body = mod.GithubBody(owner="TJSNDHU", repo="Aurem",
                           expected_sha="zzzz999")
    out = asyncio.run(mod.verify_github(body, authorization="Bearer x"))
    assert out["found"] is False
    assert out["error"] == "sha_mismatch"


# ──────────────────────────────────────────────────────────────────
# DEPLOY verification — stub httpx
# ──────────────────────────────────────────────────────────────────

def test_deploy_found_on_first_poll(monkeypatch):
    from routers import cto_verify_router as mod
    db = _DB()
    mod.set_db(db)

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    _MockAsyncClient._resp = _MockResp(200, {"iter": "D-52",
                                              "commit_sha": "abc1234"})
    monkeypatch.setattr(mod.httpx, "AsyncClient", _MockAsyncClient)

    body = mod.DeployBody(target_url="https://aurem.live",
                           expected_iter="D-52", timeout_s=10,
                           poll_every_s=2)
    out = asyncio.run(mod.verify_deploy(body, authorization="Bearer x"))
    assert out["found"] is True
    assert out["iter"]  == "D-52"


def test_deploy_timeout_returns_red(monkeypatch):
    from routers import cto_verify_router as mod
    db = _DB()
    mod.set_db(db)

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    # Stale version forever
    _MockAsyncClient._resp = _MockResp(200, {"iter": "D-49"})
    monkeypatch.setattr(mod.httpx, "AsyncClient", _MockAsyncClient)

    body = mod.DeployBody(target_url="https://aurem.live",
                           expected_iter="D-52", timeout_s=5,
                           poll_every_s=2)
    out = asyncio.run(mod.verify_deploy(body, authorization="Bearer x"))
    assert out["found"]    is False
    assert out["iter"]     == "D-49"
    assert out["expected"] == "D-52"


# ──────────────────────────────────────────────────────────────────
# Router wiring
# ──────────────────────────────────────────────────────────────────

def test_verify_routes_registered():
    from routers import cto_verify_router as mod
    paths = {r.path for r in mod.router.routes}
    assert "/api/developers/cto/verify/code"   in paths
    assert "/api/developers/cto/verify/github" in paths
    assert "/api/developers/cto/verify/deploy" in paths
