"""
iter 332b D-15 — Streaming chat (Server-Sent Events).

Backend exposes POST /api/developers/cto/chat/stream which returns a
text/event-stream of JSON events:
    meta → token (1..n) → done
or a single error event on failure.

Frontend reads the stream, appends token text to the trailing assistant
bubble as it arrives — feels 10× faster than the blocking endpoint
even when total latency is identical.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.developer_portal_core import set_db as _set_dev_db
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    _set_dev_db(database)
    yield database
    await database.developer_accounts.delete_many(
        {"email": {"$regex": "^pytest_d15_"}}
    )
    client.close()


def _parse_sse(payload: str) -> list[dict]:
    """Pull JSON events from an SSE blob."""
    out = []
    for line in payload.split("\n\n"):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            out.append(json.loads(line[5:].strip()))
        except Exception:
            continue
    return out


# ───────────────────────── Streaming dispatcher ──────────────────────

@pytest.mark.asyncio
async def test_stream_emits_meta_then_tokens_then_done(db, monkeypatch):
    """Happy path: meta + N token events + final done event,
    in that order, with no error events in between."""
    from services import dev_cto_chat as svc
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    async def _fake_stream(api_key, model, messages):
        for chunk in ["Hello ", "world", "!"]:
            yield chunk

    monkeypatch.setattr(svc, "_stream_openrouter", _fake_stream)

    user_id = f"pytest_d15_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d15_{uuid.uuid4().hex[:8]}@x.test"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "D15 Tester",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0},
    )

    out = ""
    async for chunk in svc.cto_chat_stream(
        account=acct, messages=[{"role": "user", "content": "hi"}],
    ):
        out += chunk

    evts = _parse_sse(out)
    types = [e["type"] for e in evts]
    assert types[0] == "meta", f"first event must be meta, got {types[0]!r}"
    assert "done" in types, "missing terminating done event"
    assert "error" not in types, f"unexpected error in happy path: {evts}"
    tokens = [e["content"] for e in evts if e["type"] == "token"]
    assert "".join(tokens) == "Hello world!"
    meta = next(e for e in evts if e["type"] == "meta")
    assert meta["tier"] == "free"
    assert meta["provider"] == "deepseek"


@pytest.mark.asyncio
async def test_stream_falls_through_to_next_rung(db, monkeypatch):
    """If primary model errors out, the stream should silently move to
    the next rung and start emitting tokens from there."""
    from services import dev_cto_chat as svc
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    calls: list[str] = []

    async def _fake_stream(api_key, model, messages):
        calls.append(model)
        if "deepseek" in model:
            raise RuntimeError("openrouter HTTP 429: rate limited")
        for chunk in ["llama-", "speaks"]:
            yield chunk

    monkeypatch.setattr(svc, "_stream_openrouter", _fake_stream)

    user_id = f"pytest_d15_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d15_{uuid.uuid4().hex[:8]}@x.test"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "D15 Fallback",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0},
    )

    out = ""
    async for chunk in svc.cto_chat_stream(
        account=acct, messages=[{"role": "user", "content": "hi"}],
    ):
        out += chunk

    evts = _parse_sse(out)
    # We expect TWO meta events — one for deepseek (failed), one for llama
    metas = [e for e in evts if e["type"] == "meta"]
    assert len(metas) == 2, f"expected 2 meta events, got {len(metas)}"
    providers = [m["provider"] for m in metas]
    assert providers == ["deepseek", "llama"]
    # Final tokens should come from the llama rung
    tokens = "".join(e["content"] for e in evts if e["type"] == "token")
    assert tokens == "llama-speaks"
    # And the stream ends cleanly
    assert any(e["type"] == "done" for e in evts)


@pytest.mark.asyncio
async def test_stream_emits_error_event_on_token_wall(db, monkeypatch):
    """Out-of-tokens must emit a single error event with add_byok action,
    NEVER any token events."""
    from services import dev_cto_chat as svc
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    async def _never(*_a, **_kw):
        raise AssertionError("must not be called on token wall")
        yield  # pragma: no cover — keeps it an async generator

    monkeypatch.setattr(svc, "_stream_openrouter", _never)

    user_id = f"pytest_d15_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d15_{uuid.uuid4().hex[:8]}@x.test"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "Broke",
        "plan": "free", "tokens_remaining": 0,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0},
    )

    out = ""
    async for chunk in svc.cto_chat_stream(
        account=acct, messages=[{"role": "user", "content": "hi"}],
    ):
        out += chunk

    evts = _parse_sse(out)
    types = [e["type"] for e in evts]
    assert types == ["error"], f"unexpected event sequence: {evts}"
    assert evts[0]["error"] == "token_wall"
    assert evts[0]["action_required"] == "add_byok"


@pytest.mark.asyncio
async def test_stream_emits_error_when_all_rungs_fail(db, monkeypatch):
    """Every rung errors → single trailing error event, no done."""
    from services import dev_cto_chat as svc
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    async def _always_fail(api_key, model, messages):
        raise RuntimeError(f"openrouter HTTP 503 on {model}")
        yield  # pragma: no cover

    monkeypatch.setattr(svc, "_stream_openrouter", _always_fail)

    user_id = f"pytest_d15_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d15_{uuid.uuid4().hex[:8]}@x.test"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "All-fail",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0},
    )

    out = ""
    async for chunk in svc.cto_chat_stream(
        account=acct, messages=[{"role": "user", "content": "hi"}],
    ):
        out += chunk

    evts = _parse_sse(out)
    types = [e["type"] for e in evts]
    assert types.count("error") == 1
    assert "token" not in types
    assert "done" not in types
    err = next(e for e in evts if e["type"] == "error")
    assert err["error"] == "llm_failed"


# ───────────────────────── Frontend wiring guards ────────────────────

def test_chat_panel_calls_stream_endpoint():
    src = open(
        "/app/frontend/src/platform/developers/DevCtoChatPanel.jsx"
    ).read()
    assert "/api/developers/cto/chat/stream" in src, (
        "Chat panel must POST to the streaming endpoint."
    )
    # Hard guard: streaming requires a reader; if absent, panel is
    # secretly back on the blocking endpoint.
    assert "r.body.getReader()" in src, (
        "Streaming reader missing — panel will not progressively render tokens."
    )
    assert "TextDecoder" in src
    # And event-type dispatch is wired
    for evt in ("meta", "token", "done", "error"):
        assert f'"{evt}"' in src or f"'{evt}'" in src, (
            f"Missing event-type branch for {evt!r} in chat panel."
        )


def test_router_exposes_stream_route_with_streaming_response():
    src = open(
        "/app/backend/routers/developer_portal_router.py"
    ).read()
    assert "/api/developers/cto/chat/stream" in src
    assert "StreamingResponse" in src
    assert "text/event-stream" in src
    # nginx buffering disabled so chunks reach the client immediately
    assert "X-Accel-Buffering" in src
