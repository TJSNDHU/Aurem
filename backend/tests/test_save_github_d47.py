"""
tests/test_save_github_d47.py — iter D-47

Tests Save-to-GitHub backend + security alerts + per-turn model badge
wiring.
"""
from __future__ import annotations

import asyncio
import base64
import json
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
    def find(self, q=None, p=None):
        class _C:
            def __init__(s, rs): s._rs = rs
            def sort(s, k, d):    return s
            async def to_list(s, length=None): return list(s._rs)
        return _C(list(self._rows))
    async def find_one(self, q, p=None):
        for r in self._rows:
            if all(r.get(k) == v for k, v in q.items()):
                return dict(r)
        return None
    async def insert_one(self, doc):
        self._rows.append(dict(doc))
        return type("R", (), {"inserted_id": "x"})


class _DB:
    def __init__(self):
        self.developer_github_links = _Coll()
        self.onboarding_projects    = _Coll()
        self.dev_cto_chats          = _Coll()


@pytest.fixture
def db(monkeypatch):
    from routers import github_save_router as gsr
    d = _DB()
    monkeypatch.setattr(gsr, "_db", d)
    yield d


@pytest.fixture
def user():
    return {"user_id": "u-test-1", "email": "tester@aurem.test"}


# ──────────────────────────────────────────────────────────────────
# /github/repos — auth + token lookup
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_repos_401_when_user_not_linked(db, user):
    from fastapi import HTTPException
    from routers.github_save_router import list_repos
    with pytest.raises(HTTPException) as exc:
        await list_repos(user=user)
    assert exc.value.status_code == 401
    assert "github_not_linked" in str(exc.value.detail)


def _stub_token_lookup(monkeypatch, token="ghu_test_token"):
    """Make `_get_user_token` return a known plaintext token."""
    from routers import github_save_router as gsr
    async def _fake(uid):
        return token if uid else None
    monkeypatch.setattr(gsr, "_get_user_token", _fake)


@pytest.mark.asyncio
async def test_repos_happy_path(db, user, monkeypatch):
    _stub_token_lookup(monkeypatch)
    # Stub httpx.AsyncClient via the module-level _gh_get used in code.
    from routers import github_save_router as gsr

    async def _fake_gh_get(token, path, **params):
        assert token == "ghu_test_token"
        assert path == "/user/repos"
        class R:
            status_code = 200
            def json(self_inner):
                return [
                    {"name": "aurem-platform",
                     "full_name": "tej/aurem-platform",
                     "default_branch": "main",
                     "private": False,
                     "owner": {"login": "tej"},
                     "updated_at": "2026-02-01"},
                    {"name": "side-project",
                     "full_name": "tej/side-project",
                     "default_branch": "develop",
                     "private": True,
                     "owner": {"login": "tej"},
                     "updated_at": "2026-01-20"},
                ]
        return R()
    monkeypatch.setattr(gsr, "_gh_get", _fake_gh_get)

    out = await gsr.list_repos(user=user)
    assert out["total"] == 2
    assert out["items"][0]["full_name"] == "tej/aurem-platform"
    assert out["items"][0]["owner"]     == "tej"
    assert out["items"][1]["private"]   is True


@pytest.mark.asyncio
async def test_branches_happy_path(db, user, monkeypatch):
    _stub_token_lookup(monkeypatch)
    from routers import github_save_router as gsr

    async def _fake_gh_get(token, path, **params):
        assert path == "/repos/tej/aurem-platform/branches"
        class R:
            status_code = 200
            def json(self_inner):
                return [
                    {"name": "main",    "commit": {"sha": "abc123"}},
                    {"name": "develop", "commit": {"sha": "def456"}},
                ]
        return R()
    monkeypatch.setattr(gsr, "_gh_get", _fake_gh_get)
    out = await gsr.list_branches("tej", "aurem-platform", user=user)
    assert out["owner"] == "tej" and out["repo"] == "aurem-platform"
    names = [b["name"] for b in out["items"]]
    assert names == ["main", "develop"]


# ──────────────────────────────────────────────────────────────────
# /github/commit — full happy path
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_commit_writes_two_files(db, user, monkeypatch):
    _stub_token_lookup(monkeypatch)
    # Seed project + chat.
    await db.onboarding_projects.insert_one({
        "project_id": "p-1", "user_id": user["user_id"],
        "title": "AUREM Platform", "stack": "React+FastAPI",
        "domain": "aurem.live",
    })
    await db.dev_cto_chats.insert_one({
        "project_id": "p-1", "user_id": user["user_id"],
        "messages": [
            {"role": "user",      "content": "build me a SaaS"},
            {"role": "assistant", "content": "Sure — here's the plan…"},
        ],
    })

    from routers import github_save_router as gsr

    puts: list[dict] = []

    async def _fake_gh_existing_sha(token, owner, repo, branch, path):
        return None  # New files on every call.
    async def _fake_gh_put_file(token, owner, repo, branch,
                                  path, content_b64, message, existing_sha):
        puts.append({
            "path": path, "content_b64": content_b64,
            "branch": branch, "message": message,
        })
        return {
            "status_code": 201,
            "body": {"commit": {"sha": "deadbeef0001",
                                  "html_url": "https://github.com/tej/aurem-platform/commit/deadbeef0001"}},
        }
    monkeypatch.setattr(gsr, "_gh_existing_sha", _fake_gh_existing_sha)
    monkeypatch.setattr(gsr, "_gh_put_file",     _fake_gh_put_file)

    out = await gsr.commit_project(
        gsr.CommitBody(owner="tej", repo="aurem-platform",
                        branch="main", project_id="p-1",
                        message="snapshot from chat"),
        authorization=None, user=user,
    )
    assert out["ok"] is True
    assert out["owner"] == "tej" and out["repo"] == "aurem-platform"
    assert len(out["files"]) == 2
    assert out["files"] == ["aurem/p-1/manifest.json", "aurem/p-1/aurem-chat.md"]
    assert out["commit_sha"] == "deadbeef0001"
    assert "github.com" in out["view_url"]
    # Both files were PUT
    assert {p["path"] for p in puts} == set(out["files"])
    # Manifest content is valid JSON with title
    manifest_path = next(p for p in puts if p["path"].endswith("manifest.json"))
    manifest = json.loads(base64.b64decode(manifest_path["content_b64"]))
    assert manifest["project_id"] == "p-1"
    assert manifest["title"]      == "AUREM Platform"
    # Chat history is human-readable markdown
    chat_path = next(p for p in puts if p["path"].endswith("aurem-chat.md"))
    chat_md = base64.b64decode(chat_path["content_b64"]).decode("utf-8")
    assert "AUREM Platform" in chat_md
    assert "USER"      in chat_md
    assert "ASSISTANT" in chat_md
    assert "build me a SaaS" in chat_md


@pytest.mark.asyncio
async def test_commit_401_when_not_linked(db, user):
    from fastapi import HTTPException
    from routers.github_save_router import commit_project, CommitBody
    with pytest.raises(HTTPException) as exc:
        await commit_project(
            CommitBody(owner="x", repo="y", branch="main", project_id="p-1"),
            authorization=None, user=user,
        )
    assert exc.value.status_code == 401


# ──────────────────────────────────────────────────────────────────
# Security alerts
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alerts_noop_when_unconfigured(monkeypatch):
    for v in ("SECURITY_ALERT_SLACK_WEBHOOK", "SECURITY_ALERT_EMAIL",
               "RESEND_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    from services.security_alerts import notify_key_rotation
    out = await notify_key_rotation(
        event_type="self_rotated", user_id="u-1",
    )
    assert out["slack_attempted"] is False
    assert out["email_attempted"] is False
    assert out["ok"] is True  # silent success when no channels set


@pytest.mark.asyncio
async def test_alerts_fire_slack_when_webhook_set(monkeypatch):
    monkeypatch.setenv("SECURITY_ALERT_SLACK_WEBHOOK",
                        "https://hooks.slack.com/fake")
    monkeypatch.delenv("SECURITY_ALERT_EMAIL", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    posted = {}
    class _AC:
        async def __aenter__(self): return self
        async def __aexit__(self, *a, **k): return False
        async def post(self, url, **kw):
            posted["url"] = url
            posted["payload"] = kw.get("json")
            class R:
                status_code = 200
            return R()
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _AC())

    from services.security_alerts import notify_key_rotation
    out = await notify_key_rotation(
        event_type="admin_force_rotated", user_id="u-1",
        email="tester@aurem.test", reason="suspected leak",
        ip_address="1.2.3.4",
    )
    assert out["slack_attempted"] is True
    assert out["slack_ok"]        is True
    assert posted["url"] == "https://hooks.slack.com/fake"
    text = posted["payload"]["text"]
    assert "rotated"          in text.lower()
    assert "tester@aurem.test" in text
    assert "suspected leak"   in text
    assert "1.2.3.4"          in text
