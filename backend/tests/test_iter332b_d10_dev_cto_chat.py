"""
iter 332b D-10 — Developer-portal CTO chat + expanded BYOK.

Covers:
  • POST /api/developers/cto/chat
      - free tier picks DeepSeek when DEEPSEEK_API_KEY is set
      - free tier falls back to Groq if DeepSeek raises
      - BYOK preference order (anthropic > openai > deepseek > gemini ...)
      - token wall returns action_required="add_byok"
      - no Emergent LLM key is referenced anywhere in the chat path
  • POST /api/developers/byok now accepts the expanded provider set
      (openai, groq, mistral, custom_*)
  • Frontend testid surface guards:
      - DevDashboard mounts the chat panel
      - DevConnect shows the free-tier banner + provider rows
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime, timezone

import jwt
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
        {"email": {"$regex": "^pytest_d10_"}}
    )
    client.close()


def _mint_dev_jwt(user_id: str, email: str) -> str:
    from services.developer_portal_core import JWT_SECRET, JWT_TTL_DAYS
    return jwt.encode(
        {"sub": user_id, "email": email, "tier": "dev",
         "exp": int(time.time()) + 60 * 60 * 24 * JWT_TTL_DAYS},
        JWT_SECRET, algorithm="HS256",
    )


# ───────────────────────── Free-tier provider picker ─────────────────

@pytest.mark.asyncio
async def test_free_tier_prefers_deepseek_when_configured(monkeypatch):
    from services import dev_cto_chat
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("GROQ_API_KEY", "")
    picked = dev_cto_chat._free_tier_provider()
    assert picked is not None
    assert picked[0] == "deepseek"
    assert picked[1] == "sk-deepseek-test"


@pytest.mark.asyncio
async def test_free_tier_falls_back_to_groq(monkeypatch):
    from services import dev_cto_chat
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-groq-test")
    picked = dev_cto_chat._free_tier_provider()
    assert picked is not None
    assert picked[0] == "groq"


@pytest.mark.asyncio
async def test_free_tier_returns_none_when_no_keys(monkeypatch):
    from services import dev_cto_chat
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    assert dev_cto_chat._free_tier_provider() is None


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
    """Hard guard: the developer chat path must not call the Emergent
    LLM key. That key is reserved for the founder's ORA pipeline."""
    src = open("/app/backend/services/dev_cto_chat.py").read()
    forbidden = (
        "EMERGENT_LLM_KEY", "emergent_llm", "emergent_integrations",
        "EmergentLLM", "from emergentintegrations",
    )
    for bad in forbidden:
        assert bad not in src, (
            f"developer-portal chat path references {bad!r} — "
            "founder forbade Emergent LLM key in dev portal."
        )


# ───────────────────────── End-to-end chat (mocked LLM) ──────────────

@pytest.mark.asyncio
async def test_cto_chat_happy_path_free_tier(db, monkeypatch):
    """A signed-up developer with no BYOK and DEEPSEEK_API_KEY configured
    on the platform should get a reply and have 1 token deducted."""
    from services import dev_cto_chat as svc
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    # Mock the actual HTTP dispatch
    captured = {}
    async def _fake_dispatch(provider, key, msgs):
        captured["provider"] = provider
        captured["msg_count"] = len(msgs)
        return "Use a try/except around the import."
    monkeypatch.setattr(svc, "_dispatch", _fake_dispatch)

    user_id = f"pytest_d10_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d10_{uuid.uuid4().hex[:8]}@x.test"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "D10 Tester",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one({"user_id": user_id}, {"_id": 0})

    r = await svc.cto_chat(account=acct, messages=[
        {"role": "user", "content": "How do I lazy-import xmlsec?"},
    ])
    assert r["ok"] is True
    assert "try/except" in r["reply"]
    assert r["tier"] == "free"
    assert r["provider"] == "deepseek"
    assert r["tokens_remaining"] == 499  # 500 - 1 chat cost
    assert captured["provider"] == "deepseek"


@pytest.mark.asyncio
async def test_cto_chat_token_wall_triggers_byok_prompt(db, monkeypatch):
    """When a dev has 0 tokens the response must include action_required
    so the frontend shows the upgrade modal."""
    from services import dev_cto_chat as svc
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    async def _fake_dispatch(provider, key, msgs):
        return "should-not-be-called"
    monkeypatch.setattr(svc, "_dispatch", _fake_dispatch)

    user_id = f"pytest_d10_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d10_{uuid.uuid4().hex[:8]}@x.test"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "Broke Dev",
        "plan": "free", "tokens_remaining": 0,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one({"user_id": user_id}, {"_id": 0})

    r = await svc.cto_chat(account=acct, messages=[
        {"role": "user", "content": "Hello"},
    ])
    assert r["ok"] is False
    assert r["error"] == "token_wall"
    assert r["action_required"] == "add_byok"
    assert "Connect page" in r["message"]


@pytest.mark.asyncio
async def test_cto_chat_byok_overrides_free_tier(db, monkeypatch):
    """If the dev has an Anthropic key in their BYOK envelope, that
    should be used — NOT DeepSeek — even when DEEPSEEK_API_KEY is set."""
    from services import dev_cto_chat as svc
    from services.developer_portal_core import encrypt_byok
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    captured = {}
    async def _fake_dispatch(provider, key, msgs):
        captured["provider"] = provider
        captured["key_starts"] = key[:11]
        return "BYOK answer"
    monkeypatch.setattr(svc, "_dispatch", _fake_dispatch)

    user_id = f"pytest_d10_u_{uuid.uuid4().hex[:8]}"
    email   = f"pytest_d10_{uuid.uuid4().hex[:8]}@x.test"
    envelope = encrypt_byok({"anthropic": "sk-ant-userskey"})
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": email, "name": "BYOK Dev",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
        "byok_keys": envelope,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acct = await db.developer_accounts.find_one({"user_id": user_id}, {"_id": 0})

    r = await svc.cto_chat(account=acct, messages=[
        {"role": "user", "content": "hi"},
    ])
    assert r["ok"] is True
    assert r["tier"] == "byok"
    assert r["provider"] == "anthropic"
    assert captured["provider"] == "anthropic"
    assert captured["key_starts"] == "sk-ant-user"


# ───────────────────────── BYOK schema expansion ─────────────────────

@pytest.mark.asyncio
async def test_byok_save_accepts_openai_groq_mistral(db):
    from services.developer_portal_core import save_byok_keys
    user_id = f"pytest_d10_u_{uuid.uuid4().hex[:8]}"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": f"pytest_d10_{user_id}@x.test",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
    })
    r = await save_byok_keys(user_id, {
        "openai":  "sk-openai-key",
        "groq":    "gsk-groq-key",
        "mistral": "sk-mistral-key",
    })
    assert r["ok"] is True
    assert set(r["providers"]) == {"openai", "groq", "mistral"}


@pytest.mark.asyncio
async def test_byok_save_accepts_custom_endpoint(db):
    from services.developer_portal_core import save_byok_keys
    user_id = f"pytest_d10_u_{uuid.uuid4().hex[:8]}"
    await db.developer_accounts.insert_one({
        "user_id": user_id, "email": f"pytest_d10_{user_id}@x.test",
        "plan": "free", "tokens_remaining": 500,
        "email_verified": True, "abuse_flagged": False,
    })
    r = await save_byok_keys(user_id, {
        "custom_url":     "https://api.together.xyz/v1",
        "custom_model":   "meta-llama/Llama-3-70b",
        "custom_api_key": "tg-secret",
    })
    assert r["ok"] is True


@pytest.mark.asyncio
async def test_byok_save_rejects_empty_payload(db):
    from services.developer_portal_core import save_byok_keys
    r = await save_byok_keys("nobody", {})
    assert r["ok"] is False


# ───────────────────────── Frontend wiring guards ────────────────────

def test_dev_dashboard_mounts_chat_panel():
    src = open(
        "/app/frontend/src/platform/developers/DevDashboard.jsx"
    ).read()
    assert "DevCtoChatPanel" in src
    assert 'import DevCtoChatPanel' in src
    assert "setLiveTokens" in src


def test_chat_panel_uses_dev_cto_endpoint():
    src = open(
        "/app/frontend/src/platform/developers/DevCtoChatPanel.jsx"
    ).read()
    assert "/api/developers/cto/chat" in src
    for tid in ("dev-cto-chat-panel", "dev-cto-chat-input",
                "dev-cto-chat-send", "dev-cto-chat-messages",
                "dev-cto-chat-tier",
                "dev-cto-low-tokens-modal", "dev-cto-low-tokens-cta",
                "dev-cto-low-tokens-dismiss"):
        assert tid in src, f"Missing testid {tid}"


def test_connect_page_shows_free_tier_banner_and_all_providers():
    src = open(
        "/app/frontend/src/platform/developers/DevConnect.jsx"
    ).read()
    assert "connect-free-tier-banner" in src
    assert "Free tier active" in src
    # All six providers present
    for prov in ("deepseek", "groq", "openai", "anthropic",
                 "gemini", "mistral"):
        assert f"byok-{prov}-input" in src, (
            f"Provider {prov!r} missing input testid"
        )
    # Custom toggle + fields
    assert "byok-custom-toggle" in src
    assert "byok-custom-url-input" in src
    assert "byok-custom-model-input" in src
    assert "byok-custom-key-input" in src
    # Cost-per-1M labels
    assert "$0.27" in src   # DeepSeek
    assert "Free tier" in src
    # GitHub + VS Code clearly marked optional
    assert "GitHub (optional)" in src
    assert "VS Code (optional)" in src


def test_env_vars_present_for_deepseek_and_groq():
    """The platform must ship the env-var slots, even if empty."""
    env = open("/app/backend/.env").read()
    assert "DEEPSEEK_API_KEY=" in env
    assert "GROQ_API_KEY=" in env
