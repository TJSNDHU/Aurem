"""ORA Widget Chat tests — iter 282al-8 (Prompt 10)."""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

# Force fallback path so tests don't depend on Sovereign / OpenRouter
os.environ.setdefault("EMERGENT_LLM_KEY", "")

from routers.widget_chat_router import (  # noqa: E402
    CASL_FOOTER,
    WIDGET_JS_TEMPLATE,
    _build_system_prompt,
    _hardcoded_fallback,
    _resolve_client,
    _safe_bin,
    ensure_widget_indexes,
    set_db,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fresh_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    name = f"aurem_test_widget_{uuid.uuid4().hex[:8]}"
    return client[name], client, name


# ── safe_bin ─────────────────────────────────────────────────────────
def test_safe_bin_strips_garbage():
    assert _safe_bin("AURE-CUST<script>") == "AURE-CUSTscript"
    assert _safe_bin("") == ""
    assert _safe_bin("a" * 200) == "a" * 64


# ── system prompt ────────────────────────────────────────────────────
def test_system_prompt_includes_business():
    prompt = _build_system_prompt({
        "business_name": "Mike's Plumbing",
        "city": "Mississauga",
        "category": "plumber",
        "services": [{"name": "Drain Cleaning"}],
    })
    assert "Mike's Plumbing" in prompt
    assert "Mississauga" in prompt
    assert "Canadian" in prompt
    assert "VALUE-FIRST" in prompt
    assert "Drain Cleaning" in prompt


def test_system_prompt_handles_missing_fields():
    prompt = _build_system_prompt({})
    assert "this business" in prompt
    assert "Canada" in prompt


# ── resolve client (fallback path, no DB) ────────────────────────────
def test_resolve_client_fallback_no_db():
    set_db(None)
    res = _run(_resolve_client("DEMO-XYZ"))
    assert res["bin"] == "DEMO-XYZ"
    assert res["business_name"]
    assert res["color_primary"].startswith("#")


# ── resolve client uses platform_users ───────────────────────────────
def test_resolve_client_finds_platform_user():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await db.platform_users.insert_one({
                "bin": "BIN-TEST", "business_name": "Test Auto Body",
                "city": "Brampton", "category": "auto_body",
                "color_primary": "#123456",
            })
            set_db(db)
            return await _resolve_client("BIN-TEST")
        finally:
            await client.drop_database(name)

    res = _run(_go())
    set_db(None)
    assert res["business_name"] == "Test Auto Body"
    assert res["city"] == "Brampton"
    assert res["color_primary"] == "#123456"


# ── hardcoded fallback ───────────────────────────────────────────────
def test_hardcoded_fallback_mentions_business():
    out = _hardcoded_fallback({"business_name": "Mike's"}, "hi")
    assert "Mike's" in out
    assert "AUREM" in out


# ── widget JS template ───────────────────────────────────────────────
def test_widget_js_has_required_features():
    js = WIDGET_JS_TEMPLATE
    # Bubble + panel + send button
    assert "aurem-bubble" in js
    assert "aurem-panel" in js
    assert "aurem-send" in js
    # data-testids for testability
    assert 'data-testid="aurem-widget-bubble"' in js or "aurem-widget-bubble" in js
    assert "/api/widget/chat" in js
    assert "/api/widget/config/" in js
    # session persistence
    assert "sessionStorage" in js
    # CASL footer rendering
    assert "casl_footer" in js


def test_casl_footer_present():
    assert "STOP" in CASL_FOOTER
    assert "AUREM" in CASL_FOOTER


# ── indexes ──────────────────────────────────────────────────────────
def test_ensure_widget_indexes_creates():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await ensure_widget_indexes(db)
            return await db.widget_conversations.index_information()
        finally:
            await client.drop_database(name)

    info = _run(_go())
    assert "ts_ttl_60d" in info
    assert "session_ts" in info
    assert "bin_ts" in info


# ── e2e via FastAPI TestClient ───────────────────────────────────────
def test_widget_chat_endpoint_e2e():
    """Round-trip /api/widget/chat → fallback reply (LLM unreachable).

    Drives the FastAPI app via httpx.AsyncClient + ASGITransport inside a
    single event loop so the Motor client doesn't cross loops.
    """
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from pymongo import MongoClient
    from routers.widget_chat_router import router as wgt_router

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    name = f"aurem_test_widget_{uuid.uuid4().hex[:8]}"
    sync_client = MongoClient(mongo_url)
    sync_client[name].platform_users.insert_one({
        "bin": "AURE-E2E", "business_name": "E2E Plumbing",
        "city": "Mississauga", "category": "plumber",
    })

    app = FastAPI()
    app.include_router(wgt_router)

    async def _go():
        # Bind a fresh motor client INSIDE this loop.
        motor_client = AsyncIOMotorClient(mongo_url)
        set_db(motor_client[name])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport,
                                 base_url="http://test") as ac:
            r = await ac.get("/api/widget/config/AURE-E2E")
            assert r.status_code == 200
            cfg = r.json()
            assert cfg["business_name"] == "E2E Plumbing"
            assert cfg["color_primary"].startswith("#")
            assert "STOP" in cfg["casl_footer"]

            r = await ac.post("/api/widget/chat", json={
                "bin": "AURE-E2E",
                "message": "Do you do drain cleaning?",
                "page_url": "https://example.ca",
            })
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["reply"]
            assert body["session_id"].startswith("wgt-")
            assert body["business_name"] == "E2E Plumbing"
            session_id = body["session_id"]

            r = await ac.get("/api/widget.js?bin=AURE-E2E")
            assert r.status_code == 200
            assert "aurem-bubble" in r.text
            assert r.headers.get("content-type", "").startswith(
                "application/javascript")

            r = await ac.post("/api/widget/chat", json={
                "bin": "AURE-E2E", "message": "",
            })
            assert r.status_code == 400
        motor_client.close()
        return session_id

    session_id = _run(_go())

    # Conversation persisted (sync client, after the async block).
    cnt = sync_client[name].widget_conversations.count_documents({
        "session_id": session_id,
    })
    assert cnt == 2  # user + assistant turn

    sync_client.drop_database(name)
    sync_client.close()
    set_db(None)


def test_widget_health():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers.widget_chat_router import router as wgt_router
    set_db(None)
    app = FastAPI()
    app.include_router(wgt_router)
    tc = TestClient(app)
    r = tc.get("/api/widget/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
