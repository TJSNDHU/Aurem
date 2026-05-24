"""
iter 332b D-11 — Dev-portal CTO chat now routes free tier through
OpenRouter (one key, three-model fallback ladder).

Covers:
  • _free_tier_key() returns OPENROUTER_API_KEY (or None)
  • _dispatch_free_tier walks the 3-model ladder and surfaces the label
    of whichever model actually replied
  • End-to-end happy path (free tier) returns tier=free + correct model
  • Token wall still returns action_required="add_byok"
  • BYOK preference and overrides unchanged
  • No Emergent LLM key reference anywhere on the chat path
  • Env file contains OPENROUTER_API_KEY, no longer DEEPSEEK_API_KEY
    or GROQ_API_KEY
"""
from __future__ import annotations

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
        {"email": {"$regex": "^pytest_d11_"}}
    )
    client.close()


# ───────────────────────── Free-tier key + dispatch ──────────────────

def test_free_tier_key_reads_openrouter_env(monkeypatch):
    from services import dev_cto_chat
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert dev_cto_chat._free_tier_key() == "sk-or-test"


def test_free_tier_key_returns_none_when_unset(monkeypatch):
    from services import dev_cto_chat
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    assert dev_cto_chat._free_tier_key() is None


def test_free_tier_model_ladder_is_three_deep():
    """Founder spec: 1) deepseek-chat → 2) llama-3.3-70b:free →
    3) mistral-7b:free. Order matters."""
    from services.dev_cto_chat import FREE_TIER_MODELS
    assert len(FREE_TIER_MODELS) == 3
    assert FREE_TIER_MODELS[0][0] == "deepseek/deepseek-chat"
    assert FREE_TIER_MODELS[1][0] == \
        "meta-llama/llama-3.3-70b-instruct:free"
    assert FREE_TIER_MODELS[2][0] == "mistralai/mistral-7b-instruct:free"


@pytest.mark.asyncio
async def test_dispatch_free_tier_returns_first_success(monkeypatch):
    """If the primary model replies, the fallback isn't called."""
    from services import dev_cto_chat as svc
    calls = []

    async def _fake_or(api_key, model, msgs):
        calls.append(model)
        return f"reply from {model}"

    monkeypatch.setattr(svc, "_call_openrouter", _fake_or)
    reply, label = await svc._dispatch_free_tier("sk-or", [
        {"role": "user", "content": "ping"},
    ])
    assert reply.startswith("reply from deepseek/deepseek-chat")
    assert label == "deepseek"
    assert len(calls) == 1  # no fallback


@pytest.mark.asyncio
async def test_dispatch_free_tier_falls_through_to_llama(monkeypatch):
    """If DeepSeek raises, the Llama free fallback fires."""
    from services import dev_cto_chat as svc
    calls = []

    async def _fake_or(api_key, model, msgs):
        calls.append(model)
        if "deepseek" in model:
            raise RuntimeError("openrouter HTTP 429: rate limit")
        return "llama replied"

    monkeypatch.setattr(svc, "_call_openrouter", _fake_or)
    reply, label = await svc._dispatch_free_tier("sk-or", [
        {"role": "user", "content": "ping"},
    ])
    assert reply == "llama replied"
    assert label == "llama"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_dispatch_free_tier_falls_through_to_mistral(monkeypatch):
    from services import dev_cto_chat as svc
    calls = []

    async def _fake_or(api_key, model, msgs):
        calls.append(model)
        if "deepseek" in model or "llama" in model:
            raise RuntimeError(f"sim fail {model}")
        return "mistral saved the day"

    monkeypatch.setattr(svc, "_call_openrouter", _fake_or)
    reply, label = await svc._dispatch_free_tier("sk-or", [
        {"role": "user", "content": "ping"},
    ])
    assert "mistral" in reply.lower()
    assert label == "mistral"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_dispatch_free_tier_raises_when_all_fail(monkeypatch):
    from services import dev_cto_chat as svc

    async def _fake_or(api_key, model, msgs):
        raise RuntimeError("openrouter HTTP 503")

    monkeypatch.setattr(svc, "_call_openrouter", _fake_or)
    with pytest.raises(RuntimeError) as ei:
        await svc._dispatch_free_tier("sk-or", [
            {"role": "user", "content": "ping"},
        ])
    assert "all free-tier models failed" in str(ei.value)


# ───────────────────────── BYOK selection (regression) ───────────────

def test_byok_preference_order_picks_anthropic_first():
    from services import dev_cto_chat
    picked = dev_cto_chat._pick_byok_provider({
        "deepseek": "sk-deepseek",
        "anthropic": "sk-anthropic",
        "openai": "sk-openai",
    })
    assert picked == ("anthropic", "sk-anthropic")


def test_byok_preference_falls_through_to_deepseek():
    from services import dev_cto_chat
    picked = dev_cto_chat._pick_byok_provider({
        "deepseek": "sk-deepseek",
        "groq": "gsk-groq",
    })
    assert picked == ("deepseek", "sk-deepseek")


def test_byok_preference_handles_empty_dict():
    from services import dev_cto_chat
    assert dev_cto_chat._pick_byok_provider({}) is None
    assert dev_cto_chat._pick_byok_provider(None) is None


# ───────────────────────── No Emergent LLM dependency ────────────────

def test_dev_chat_service_never_imports_emergent_llm():
    src = open("/app/backend/services/dev_cto_chat.py").read()
    forbidden = (
        "EMERGENT_LLM_KEY", "emergent_llm", "emergent_integrations",
        "EmergentLLM", "from emergentintegrations",
    )
    for bad in forbidden:
        assert bad not in src, (
            f"dev chat path references {bad!r} — founder forbade "
            "Emergent LLM key in dev portal."
        )


# ───────────────────────── End-to-end (mocked) ───────────────────────

@pytest.mark.asyncio
async def test_cto_chat_happy_path_free_tier_openrouter(db, monkeypatch):
    """A signed-up dev with no BYOK and OPENROUTER_API_KEY configured
    should get a reply and 1 token deducted; provider label reflects
    whichever model actually answered."""
    from services import dev_cto_chat as svc
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    async def _fake_or(api_key, model, msgs):
        return f"answer from {model}"

    monkeypatch.setattr(svc, "_call_openrouter", _fake_or)

    user_id = f"pytest_d11_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d11_{uuid.uuid4().hex[:8]}@x.test"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "D11 Tester",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0},
    )

    r = await svc.cto_chat(account=acct, messages=[
        {"role": "user", "content": "Lazy-import xmlsec?"},
    ])
    assert r["ok"] is True
    assert "deepseek/deepseek-chat" in r["reply"]
    assert r["tier"] == "free"
    assert r["provider"] == "deepseek"
    assert r["tokens_remaining"] == 499


@pytest.mark.asyncio
async def test_cto_chat_token_wall_returns_add_byok(db, monkeypatch):
    from services import dev_cto_chat as svc
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    async def _fake_or(api_key, model, msgs):
        return "should-not-be-called"

    monkeypatch.setattr(svc, "_call_openrouter", _fake_or)

    user_id = f"pytest_d11_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d11_{uuid.uuid4().hex[:8]}@x.test"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "Broke Dev",
        "plan": "free", "tokens_remaining": 0,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0},
    )

    r = await svc.cto_chat(account=acct, messages=[
        {"role": "user", "content": "Hello"},
    ])
    assert r["ok"] is False
    assert r["error"] == "token_wall"
    assert r["action_required"] == "add_byok"


@pytest.mark.asyncio
async def test_cto_chat_byok_overrides_free_tier(db, monkeypatch):
    """Even when OPENROUTER_API_KEY is set, a configured Anthropic BYOK
    must win. We patch the byok dispatcher to assert it actually fires."""
    from services import dev_cto_chat as svc
    from services.developer_portal_core import encrypt_byok
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = {}

    async def _fake_byok(provider, key, msgs):
        captured["provider"] = provider
        captured["key_prefix"] = key[:11]
        return "BYOK reply"

    async def _fake_or(api_key, model, msgs):
        raise AssertionError("OpenRouter must NOT be called when BYOK is set")

    monkeypatch.setattr(svc, "_dispatch_byok", _fake_byok)
    monkeypatch.setattr(svc, "_call_openrouter", _fake_or)

    user_id = f"pytest_d11_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d11_{uuid.uuid4().hex[:8]}@x.test"
    envelope = encrypt_byok({"anthropic": "sk-ant-userskey"})
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "BYOK Dev",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": envelope,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0},
    )

    r = await svc.cto_chat(account=acct, messages=[
        {"role": "user", "content": "hi"},
    ])
    assert r["ok"] is True
    assert r["tier"] == "byok"
    assert r["provider"] == "anthropic"
    assert captured["provider"] == "anthropic"
    assert captured["key_prefix"] == "sk-ant-user"


@pytest.mark.asyncio
async def test_cto_chat_no_openrouter_key_returns_add_byok(db, monkeypatch):
    from services import dev_cto_chat as svc
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    user_id = f"pytest_d11_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d11_{uuid.uuid4().hex[:8]}@x.test"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "Unconf Dev",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one(
        {"user_id": user_id}, {"_id": 0},
    )
    r = await svc.cto_chat(account=acct, messages=[
        {"role": "user", "content": "hi"},
    ])
    assert r["ok"] is False
    assert r["error"] == "no_llm_configured"
    assert r["action_required"] == "add_byok"


# ───────────────────────── Env-file shape ────────────────────────────

def test_env_has_openrouter_and_no_legacy_deepseek_groq():
    """OPENROUTER_API_KEY is now the only LLM key the free tier needs.
    The standalone DEEPSEEK_API_KEY / GROQ_API_KEY env vars were
    removed per founder directive."""
    env = open("/app/backend/.env").read()
    assert "OPENROUTER_API_KEY=" in env
    # The legacy vars must not be set on the platform anymore.
    assert "DEEPSEEK_API_KEY=" not in env, (
        "Legacy DEEPSEEK_API_KEY still set — founder removed this."
    )
    assert "GROQ_API_KEY=" not in env, (
        "Legacy GROQ_API_KEY still set — founder removed this."
    )


# ───────────────────────── Frontend wiring guards ────────────────────

def test_chat_panel_label_reflects_openrouter_strategy():
    src = open(
        "/app/frontend/src/platform/developers/DevCtoChatPanel.jsx"
    ).read()
    assert "OpenRouter" in src
    assert "DeepSeek + Groq fallback" not in src


def test_connect_banner_mentions_openrouter():
    src = open(
        "/app/frontend/src/platform/developers/DevConnect.jsx"
    ).read()
    assert "OpenRouter" in src
    assert "Groq Llama 3.3 as" not in src  # old copy gone
