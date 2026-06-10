"""
D-79 — `.aurem-rules.md` per-customer rules + Plan/Execute toggle.

Proves end-to-end against real Mongo + real JWT:

  GET    /api/cto/rules
  PUT    /api/cto/rules           (round-trip persistence)
  DELETE /api/cto/rules
  POST   /api/developers/cto/chat with mode=plan suppresses skill exec

The chat-mode test uses monkeypatched OpenRouter so we don't hit the
real LLM, but the rest of the chat pipeline (auth, mode injection,
skill suppression) is real code.
"""
from __future__ import annotations

import os
import uuid

import httpx
import jwt
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

API_BASE = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "aurem_db")


def _user_token(user_id: str, email: str = "rules-test@aurem.live") -> str:
    return jwt.encode(
        {"user_id": user_id, "email": email, "role": "customer"},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )


@pytest_asyncio.fixture
async def db():
    cli = AsyncIOMotorClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest_asyncio.fixture
async def fresh_user(db):
    uid = f"d79_rules_user_{uuid.uuid4().hex[:8]}"
    yield uid
    await db.aurem_user_rules.delete_one({"user_id": uid})


# ── Rules CRUD ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rules_requires_bearer():
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(f"{API_BASE}/api/cto/rules")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_rules_default_empty_for_new_user(fresh_user):
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(
            f"{API_BASE}/api/cto/rules",
            headers={"Authorization": f"Bearer {_user_token(fresh_user)}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["rules_md"] == ""
    assert body["updated_at"] is None
    assert body["version"] == 0


@pytest.mark.asyncio
async def test_rules_put_then_get_roundtrip(fresh_user, db):
    md = "# my house style\n- use yarn\n- never write to root\n"
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.put(
            f"{API_BASE}/api/cto/rules",
            headers={"Authorization": f"Bearer {_user_token(fresh_user)}"},
            json={"rules_md": md},
        )
        assert r.status_code == 200, r.text
        saved = r.json()
        assert saved["rules_md"] == md
        assert saved["version"] == 1
        assert saved["truncated"] is False

        # Re-read confirms persistence
        r2 = await cli.get(
            f"{API_BASE}/api/cto/rules",
            headers={"Authorization": f"Bearer {_user_token(fresh_user)}"},
        )
        assert r2.json()["rules_md"] == md

    # Real Mongo state too
    doc = await db.aurem_user_rules.find_one({"user_id": fresh_user})
    assert doc is not None
    assert doc["rules_md"] == md
    assert doc["version"] == 1


@pytest.mark.asyncio
async def test_rules_version_increments_on_each_put(fresh_user):
    headers = {"Authorization": f"Bearer {_user_token(fresh_user)}"}
    async with httpx.AsyncClient(timeout=10) as cli:
        for v in (1, 2, 3):
            r = await cli.put(
                f"{API_BASE}/api/cto/rules",
                headers=headers, json={"rules_md": f"v{v}"},
            )
            assert r.status_code == 200
            assert r.json()["version"] == v


@pytest.mark.asyncio
async def test_rules_truncation_signal(fresh_user):
    """Rules over 16KB get truncated; flag must be surfaced."""
    big = "x" * (16 * 1024 + 500)
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.put(
            f"{API_BASE}/api/cto/rules",
            headers={"Authorization": f"Bearer {_user_token(fresh_user)}"},
            json={"rules_md": big},
        )
    body = r.json()
    assert body["truncated"] is True
    assert body["size_bytes"] == 16 * 1024


@pytest.mark.asyncio
async def test_rules_delete(fresh_user, db):
    headers = {"Authorization": f"Bearer {_user_token(fresh_user)}"}
    async with httpx.AsyncClient(timeout=10) as cli:
        await cli.put(
            f"{API_BASE}/api/cto/rules", headers=headers,
            json={"rules_md": "to be deleted"},
        )
        r = await cli.delete(f"{API_BASE}/api/cto/rules", headers=headers)
    assert r.status_code == 200
    assert r.json()["removed"] is True
    assert await db.aurem_user_rules.find_one({"user_id": fresh_user}) is None


@pytest.mark.asyncio
async def test_rules_cross_user_isolation(db):
    """User A cannot see or affect User B's rules — the user_id always
    comes from the JWT, never from the request body."""
    uid_a = f"d79_iso_a_{uuid.uuid4().hex[:6]}"
    uid_b = f"d79_iso_b_{uuid.uuid4().hex[:6]}"
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            await cli.put(
                f"{API_BASE}/api/cto/rules",
                headers={"Authorization": f"Bearer {_user_token(uid_a)}"},
                json={"rules_md": "A_PRIVATE"},
            )
            await cli.put(
                f"{API_BASE}/api/cto/rules",
                headers={"Authorization": f"Bearer {_user_token(uid_b)}"},
                json={"rules_md": "B_PRIVATE"},
            )
            r_a = await cli.get(
                f"{API_BASE}/api/cto/rules",
                headers={"Authorization": f"Bearer {_user_token(uid_a)}"},
            )
            r_b = await cli.get(
                f"{API_BASE}/api/cto/rules",
                headers={"Authorization": f"Bearer {_user_token(uid_b)}"},
            )
        assert r_a.json()["rules_md"] == "A_PRIVATE"
        assert r_b.json()["rules_md"] == "B_PRIVATE"
    finally:
        await db.aurem_user_rules.delete_many({"user_id": {"$in": [uid_a, uid_b]}})


# ── build_rules_prompt_block ────────────────────────────────────────

def test_build_block_empty_returns_empty_string():
    from services.aurem_rules import build_rules_prompt_block
    assert build_rules_prompt_block("") == ""
    assert build_rules_prompt_block("   \n") == ""
    assert build_rules_prompt_block(None) == ""


def test_build_block_wraps_rules_with_authority_markers():
    from services.aurem_rules import build_rules_prompt_block
    out = build_rules_prompt_block("use yarn not npm")
    assert "[CUSTOMER .aurem-rules.md" in out
    assert "use yarn not npm" in out
    assert out.rstrip().endswith("[END .aurem-rules.md]")


# ── Plan/Execute mode (unit-level on cto_chat) ──────────────────────

@pytest.mark.asyncio
async def test_plan_mode_skips_skill_execution(monkeypatch):
    """In plan mode, even if the LLM emits a skill tag, the server
    must NOT invoke it. We patch the LLM call to return a string
    containing a [[SKILL: ...]] tag and confirm no skill ran."""
    import services.dev_cto_chat as cm

    async def _fake_call_openrouter(api_key, model, messages, **kw):
        # Imitate LLM output that *would* trigger skill execution in
        # execute mode.
        return {
            "ok": True,
            "content": "I plan to do the thing.\n[[SKILL: run_scrape]]",
            "model_used": "fake-d79",
            "provider": "fake",
            "tier": "cheap",
        }

    monkeypatch.setattr(cm, "_call_openrouter", _fake_call_openrouter)

    invoked: list[str] = []
    real_invoke = cm._maybe_invoke_skill

    async def _spy(reply):
        invoked.append(reply)
        return await real_invoke(reply)
    monkeypatch.setattr(cm, "_maybe_invoke_skill", _spy)

    # Build a minimal account
    account = {
        "user_id": f"d79_plan_{uuid.uuid4().hex[:6]}",
        "email": "plan@aurem.live",
        "tokens": 100,
        "wallet_id": None,
    }
    res = await cm.cto_chat(
        account=account,
        messages=[{"role": "user", "content": "Plan a scrape"}],
        mode="plan",
    )
    assert res["ok"] is True
    # Critical assertion: skill was NEVER invoked in plan mode
    assert invoked == [], (
        f"plan mode invoked a skill ({invoked!r}) — must be propose-only"
    )
    # And the reply should be unmodified (no "Skill executed:" suffix)
    assert "Skill executed" not in res["reply"]


@pytest.mark.asyncio
async def test_execute_mode_still_invokes_skill(monkeypatch):
    """Inverse of above — execute mode must still call the skill
    invocation pipeline, so we don't accidentally kill the feature."""
    import services.dev_cto_chat as cm

    async def _fake_call_openrouter(api_key, model, messages, **kw):
        return {
            "ok": True,
            "content": "doing the thing now\n[[SKILL: run_scrape]]",
            "model_used": "fake-d79",
            "provider": "fake",
            "tier": "cheap",
        }
    monkeypatch.setattr(cm, "_call_openrouter", _fake_call_openrouter)

    invoked: list[str] = []

    async def _spy(reply):
        invoked.append(reply)
        return None  # don't actually run the skill in the test
    monkeypatch.setattr(cm, "_maybe_invoke_skill", _spy)

    account = {
        "user_id": f"d79_exec_{uuid.uuid4().hex[:6]}",
        "email": "exec@aurem.live",
        "tokens": 100,
        "wallet_id": None,
    }
    res = await cm.cto_chat(
        account=account,
        messages=[{"role": "user", "content": "Run scrape now"}],
        mode="execute",
    )
    assert res["ok"] is True
    assert len(invoked) == 1, (
        f"execute mode should call skill invoker once, called {len(invoked)}"
    )
