"""
tests/test_platform_secrets_d43.py — iter D-43

Tests for the founder-controlled platform-secrets endpoints used by
/developers/settings → PlatformCredentialsBlock.

Coverage:
  - Whitelist enforced (reject unknown secret names)
  - Save writes encrypted envelope to DB + applies plaintext to env
  - List never returns plaintext (only key_tail)
  - Delete removes DB row + clears env
  - apply_platform_secrets_to_env loads DB into env on boot
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class _Cursor:
    def __init__(self, rows):
        self._rows = rows
    async def to_list(self, length=None):
        return list(self._rows)


class _Coll:
    def __init__(self):
        self._rows = []
    def find(self, query=None, projection=None):
        # Ignore projection — tests don't rely on field-stripping.
        return _Cursor(self._rows)
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
                return type("R", (), {"matched_count": 1})
        if upsert:
            new = dict(update.get("$set") or {})
            self._rows.append(new)
        return type("R", (), {"matched_count": 0})
    async def delete_one(self, query):
        for i, r in enumerate(self._rows):
            if all(r.get(k) == v for k, v in query.items()):
                self._rows.pop(i)
                return type("R", (), {"deleted_count": 1})
        return type("R", (), {"deleted_count": 0})


class _DB:
    def __init__(self):
        self.platform_secrets = _Coll()


@pytest.fixture
def db_stub(monkeypatch):
    from routers import platform_secrets_router as psr
    db = _DB()
    monkeypatch.setattr(psr, "_db", db)
    yield db


@pytest.fixture
def crypt_key(monkeypatch):
    """Enable real Fernet so the envelope round-trips."""
    monkeypatch.setenv("AUREM_ENCRYPTION_KEY", "test-passphrase-d43" + "x" * 12)
    # Force the credential_crypto singleton to re-init for this test.
    from services import credential_crypto as cc
    cc._FERNET = None
    cc._INIT_TRIED = False
    yield


@pytest.mark.asyncio
async def test_save_rejects_non_whitelisted_name(db_stub, crypt_key):
    from fastapi import HTTPException
    from routers.platform_secrets_router import save_secret, SecretSaveBody
    with pytest.raises(HTTPException) as exc:
        await save_secret("MY_RANDOM_KEY", SecretSaveBody(value="abc"))
    assert exc.value.status_code == 400
    assert "allow-list" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_save_persists_and_applies_to_env(
    db_stub, crypt_key, monkeypatch,
):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from routers.platform_secrets_router import save_secret, SecretSaveBody
    out = await save_secret(
        "ANTHROPIC_API_KEY",
        SecretSaveBody(value="sk-ant-test-1234567890"),
    )
    assert out["ok"] is True
    assert out["key_tail"] == "7890"
    # Live env applied.
    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-test-1234567890"
    # DB row has encrypted envelope, not plaintext.
    rows = db_stub.platform_secrets._rows
    assert len(rows) == 1
    env = rows[0]["ct_envelope"]
    assert env.get("_encrypted") is True
    assert "sk-ant-test-1234567890" not in str(env)


@pytest.mark.asyncio
async def test_list_never_returns_plaintext(db_stub, crypt_key, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from routers.platform_secrets_router import (
        save_secret, SecretSaveBody, list_secrets,
    )
    await save_secret("OPENAI_API_KEY",
                      SecretSaveBody(value="sk-test-ABCDEF7890"))
    out = await list_secrets()
    row = next(r for r in out["items"] if r["name"] == "OPENAI_API_KEY")
    assert row["has_value"] is True
    assert row["key_tail"] == "7890"
    assert row["source"] == "db"
    # Confirm no field anywhere on the row leaks the full value.
    flat = " ".join(str(v) for v in row.values())
    assert "ABCDEF" not in flat


@pytest.mark.asyncio
async def test_delete_removes_db_and_env(db_stub, crypt_key, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    from routers.platform_secrets_router import (
        save_secret, SecretSaveBody, delete_secret,
    )
    await save_secret("RESEND_API_KEY",
                      SecretSaveBody(value="re_test_12345"))
    assert os.environ.get("RESEND_API_KEY") == "re_test_12345"
    out = await delete_secret("RESEND_API_KEY")
    assert out["ok"] is True
    assert "RESEND_API_KEY" not in os.environ
    assert db_stub.platform_secrets._rows == []


@pytest.mark.asyncio
async def test_apply_platform_secrets_to_env(db_stub, crypt_key, monkeypatch):
    monkeypatch.delenv("HETZNER_API_TOKEN", raising=False)
    from routers.platform_secrets_router import (
        save_secret, SecretSaveBody, apply_platform_secrets_to_env,
    )
    await save_secret("HETZNER_API_TOKEN",
                      SecretSaveBody(value="hetzner-fake-token"))
    # Wipe env and re-apply from DB.
    del os.environ["HETZNER_API_TOKEN"]
    n = await apply_platform_secrets_to_env()
    assert n >= 1
    assert os.environ.get("HETZNER_API_TOKEN") == "hetzner-fake-token"


@pytest.mark.asyncio
async def test_list_reports_env_only_secrets(db_stub, crypt_key, monkeypatch):
    """A secret set via .env but not via DB should still show up as
    has_value=True with source='env'."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_env_only_999")
    from routers.platform_secrets_router import list_secrets
    out = await list_secrets()
    row = next(r for r in out["items"] if r["name"] == "STRIPE_SECRET_KEY")
    assert row["has_value"] is True
    assert row["source"] == "env"
    assert row["key_tail"] == "_999"
