"""
tests/test_github_oauth_d42.py — iter D-42

Tests for the one-click GitHub OAuth flow that replaces manual PAT
pasting.

Coverage:
  - /github/oauth/start: requires dev auth, requires GITHUB_CLIENT_ID
    + GITHUB_CLIENT_SECRET in env, returns a well-formed authorize URL
    with state + PKCE, persists state to MongoDB.
  - /github/oauth/callback: rejects missing/invalid state, exchanges
    code via stubbed httpx, fetches /user, upserts the encrypted
    access_token into developer_github_links, returns a self-closing
    HTML page that posts back to the opener.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ──────────────────────────────────────────────────────────────────
# Async in-memory MongoDB stub — just enough for the OAuth routes.
# ──────────────────────────────────────────────────────────────────

class _AsyncCollectionStub:
    def __init__(self):
        self._rows: list[dict] = []

    async def insert_one(self, doc):
        # Attach an _id like MongoDB does.
        doc = dict(doc)
        doc.setdefault("_id", f"id_{len(self._rows)}")
        self._rows.append(doc)
        return type("R", (), {"inserted_id": doc["_id"]})

    async def find_one(self, query):
        for r in self._rows:
            if all(r.get(k) == v for k, v in query.items()):
                return dict(r)
        return None

    async def update_one(self, query, update, upsert=False):
        for r in self._rows:
            if all(r.get(k) == v for k, v in query.items()):
                for k, v in (update.get("$set") or {}).items():
                    r[k] = v
                return type("R", (), {"matched_count": 1, "upserted_id": None})
        if upsert:
            new_row = dict(update.get("$set") or {})
            new_row["_id"] = f"id_{len(self._rows)}"
            self._rows.append(new_row)
            return type("R", (), {"matched_count": 0,
                                   "upserted_id": new_row["_id"]})
        return type("R", (), {"matched_count": 0, "upserted_id": None})

    async def delete_one(self, query):
        for i, r in enumerate(self._rows):
            if all(r.get(k) == v for k, v in query.items()):
                self._rows.pop(i)
                return type("R", (), {"deleted_count": 1})
        return type("R", (), {"deleted_count": 0})


class _AsyncDBStub:
    def __init__(self):
        self.developer_github_oauth_states = _AsyncCollectionStub()
        self.developer_github_links        = _AsyncCollectionStub()


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def stub_env(monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID",     "test-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-client-secret")
    yield


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("GITHUB_CLIENT_ID",     raising=False)
    monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GITHUB_OAUTH_REDIRECT_URI", raising=False)
    yield


@pytest.fixture
def db_stub(monkeypatch):
    from routers import developer_portal_router as dpr
    db = _AsyncDBStub()
    monkeypatch.setattr(dpr, "_db", db)
    yield db


@pytest.fixture
def fake_dev(monkeypatch):
    """Bypass auth — _current_dev returns a fixed dev account."""
    from routers import developer_portal_router as dpr

    async def _fake(authorization):  # noqa: ARG001
        return {"user_id": "u-test-1", "email": "tester@aurem.test"}

    monkeypatch.setattr(dpr, "_current_dev", _fake)
    yield


# ──────────────────────────────────────────────────────────────────
# /github/oauth/start
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_returns_503_when_credentials_unset(
    clean_env, db_stub, fake_dev,
):
    from fastapi import HTTPException
    from routers.developer_portal_router import github_oauth_start

    class _Req:
        base_url = "https://api.aurem.test/"

    with pytest.raises(HTTPException) as exc:
        await github_oauth_start(_Req(), authorization="Bearer x")  # type: ignore[arg-type]
    assert exc.value.status_code == 503
    assert "github_oauth_not_configured" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_start_returns_authorize_url_and_persists_state(
    stub_env, db_stub, fake_dev,
):
    from routers.developer_portal_router import github_oauth_start

    class _Req:
        base_url = "https://api.aurem.test/"

    out = await github_oauth_start(_Req(), authorization="Bearer x")  # type: ignore[arg-type]
    assert "auth_url" in out
    parsed = urlparse(out["auth_url"])
    assert parsed.netloc == "github.com"
    assert parsed.path   == "/login/oauth/authorize"
    qs = parse_qs(parsed.query)
    assert qs["client_id"]              == ["test-client-id"]
    assert qs["scope"]                  == ["repo read:user"]
    assert qs["code_challenge_method"]  == ["S256"]
    assert "state" in qs and len(qs["state"][0]) >= 20
    assert "code_challenge" in qs and len(qs["code_challenge"][0]) >= 20
    # State row persisted, tied to the test user.
    rows = db_stub.developer_github_oauth_states._rows
    assert len(rows) == 1
    assert rows[0]["user_id"] == "u-test-1"
    assert rows[0]["state"]   == qs["state"][0]


@pytest.mark.asyncio
async def test_start_respects_env_redirect_uri(
    stub_env, db_stub, fake_dev, monkeypatch,
):
    monkeypatch.setenv(
        "GITHUB_OAUTH_REDIRECT_URI",
        "https://custom.aurem.test/api/developers/github/oauth/callback",
    )
    from routers.developer_portal_router import github_oauth_start

    class _Req:
        base_url = "https://ignored.test/"

    out = await github_oauth_start(_Req(), authorization="Bearer x")  # type: ignore[arg-type]
    qs = parse_qs(urlparse(out["auth_url"]).query)
    assert qs["redirect_uri"] == [
        "https://custom.aurem.test/api/developers/github/oauth/callback"
    ]


# ──────────────────────────────────────────────────────────────────
# /github/oauth/callback
# ──────────────────────────────────────────────────────────────────

class _FakeHttpResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


class _FakeAsyncClient:
    """Replaces httpx.AsyncClient for the duration of one callback."""
    def __init__(self, post_response=None, get_response=None,
                  *, raise_on_post=False):
        self._post_response = post_response
        self._get_response  = get_response
        self._raise_on_post = raise_on_post

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a, **kw):
        return False

    async def post(self, *a, **kw):
        if self._raise_on_post:
            raise RuntimeError("network down")
        return self._post_response

    async def get(self, *a, **kw):
        return self._get_response


def _patch_httpx(monkeypatch, *, post=None, get=None, raise_on_post=False):
    import httpx

    def _factory(*a, **kw):
        return _FakeAsyncClient(
            post_response=post, get_response=get,
            raise_on_post=raise_on_post,
        )

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


@pytest.mark.asyncio
async def test_callback_rejects_missing_code(stub_env, db_stub):
    from routers.developer_portal_router import github_oauth_callback

    class _Req:
        base_url = "https://api.aurem.test/"

    resp = await github_oauth_callback(_Req(), code=None, state="x")  # type: ignore[arg-type]
    body = resp.body.decode()
    assert "Missing code or state" in body
    assert "aurem-github-oauth" in body  # postMessage payload baked in


@pytest.mark.asyncio
async def test_callback_rejects_invalid_state(stub_env, db_stub):
    from routers.developer_portal_router import github_oauth_callback

    class _Req:
        base_url = "https://api.aurem.test/"

    resp = await github_oauth_callback(_Req(),
                                       code="abc", state="nonexistent")  # type: ignore[arg-type]
    assert "Invalid or expired state" in resp.body.decode()


@pytest.mark.asyncio
async def test_callback_propagates_github_error(stub_env, db_stub):
    from routers.developer_portal_router import github_oauth_callback

    class _Req:
        base_url = "https://api.aurem.test/"

    resp = await github_oauth_callback(
        _Req(), code=None, state=None,
        error="access_denied", error_description="user denied",
    )  # type: ignore[arg-type]
    body = resp.body.decode()
    assert "user denied" in body or "access_denied" in body


@pytest.mark.asyncio
async def test_callback_happy_path_persists_token(
    stub_env, db_stub, monkeypatch,
):
    """End-to-end happy path with stubbed GitHub HTTP calls."""
    from datetime import datetime, timezone
    from routers.developer_portal_router import github_oauth_callback

    # Seed a valid state row first.
    await db_stub.developer_github_oauth_states.insert_one({
        "state":        "good-state-1",
        "code_verifier": "v" * 50,
        "user_id":      "u-test-1",
        "redirect_uri": "https://api.aurem.test/api/developers/github/oauth/callback",
        "created_at":   datetime.now(timezone.utc),
    })

    _patch_httpx(
        monkeypatch,
        post=_FakeHttpResponse(200, {
            "access_token": "ghu_realtoken",
            "scope":        "repo,read:user",
            "token_type":   "bearer",
        }),
        get=_FakeHttpResponse(200, {
            "id":           42,
            "login":        "octouser",
            "avatar_url":   "https://gh.test/avatar.png",
            "public_repos": 7,
        }),
    )

    class _Req:
        base_url = "https://api.aurem.test/"

    resp = await github_oauth_callback(_Req(),
                                       code="real-code", state="good-state-1")  # type: ignore[arg-type]
    body = resp.body.decode()
    assert "GitHub connected" in body
    assert "octouser" in body

    # State row consumed.
    states = db_stub.developer_github_oauth_states._rows
    assert states == []

    # Token persisted.
    links = db_stub.developer_github_links._rows
    assert len(links) == 1
    link = links[0]
    assert link["user_id"]     == "u-test-1"
    assert link["login"]       == "octouser"
    assert link["repos_count"] == 7
    assert link["auth_method"] == "oauth"
    # Stored token is NOT plaintext.
    assert "ghu_realtoken" not in link["pat_enc"]


@pytest.mark.asyncio
async def test_callback_rejects_expired_state(stub_env, db_stub):
    from datetime import datetime, timezone, timedelta
    from routers.developer_portal_router import github_oauth_callback

    await db_stub.developer_github_oauth_states.insert_one({
        "state":        "old-state",
        "code_verifier": "v" * 50,
        "user_id":      "u-test-1",
        "created_at":   datetime.now(timezone.utc) - timedelta(minutes=15),
    })

    class _Req:
        base_url = "https://api.aurem.test/"

    resp = await github_oauth_callback(
        _Req(), code="x", state="old-state",
    )  # type: ignore[arg-type]
    assert "expired" in resp.body.decode().lower()


@pytest.mark.asyncio
async def test_callback_handles_token_exchange_failure(
    stub_env, db_stub, monkeypatch,
):
    from datetime import datetime, timezone
    from routers.developer_portal_router import github_oauth_callback

    await db_stub.developer_github_oauth_states.insert_one({
        "state":        "good-state-2",
        "code_verifier": "v" * 50,
        "user_id":      "u-test-1",
        "created_at":   datetime.now(timezone.utc),
    })
    _patch_httpx(
        monkeypatch,
        post=_FakeHttpResponse(400, {"error": "bad_verification_code"}),
        get=None,
    )

    class _Req:
        base_url = "https://api.aurem.test/"

    resp = await github_oauth_callback(_Req(),
                                       code="bad", state="good-state-2")  # type: ignore[arg-type]
    body = resp.body.decode()
    assert "token exchange failed" in body.lower()
    # Link row NOT created.
    assert db_stub.developer_github_links._rows == []
