"""
iter 326ww — Tool credentials encrypted at rest (P0 fix)
=========================================================

Closes the long-standing P0 in `/app/backend/routers/ai_platform_router.py`
lines 609 / 622: third-party tool credentials (WhatsApp, Email, Twilio,
Stripe API keys, etc.) were stored PLAINTEXT in
`platform_users.tool_connections.{tool}.config`.

Fix:
  - NEW `services/credential_crypto.py` — Fernet (AES-128-CBC + HMAC)
    keyed off `AUREM_ENCRYPTION_KEY` (env), PBKDF2-derived 32 bytes
    with project salt "aurem-creds-v1".
  - `/api/ai-platform/tools/connect` now wraps `data.credentials` in an
    encrypted envelope `{v:1, _encrypted:True, ct:<base64>}` before
    writing to Mongo. Field renamed `config` → `config_envelope`.
  - If the encryption key is unavailable AND the tool is in the
    sensitive list (whatsapp/email/twilio/stripe/openai/gemini/claude/smtp),
    the endpoint returns HTTP 503 instead of silently writing plaintext.
  - Decryption helper provided for any future read path that genuinely
    needs the credentials back (tool invocation, etc.) — none today
    consume them, by design.

Non-goals (deferred):
  - Migration of existing rows. Old rows have `_encrypted: False` and
    a `config` field; new rows have `config_envelope`. Both shapes
    decrypt correctly via `decrypt_credentials()` (legacy passthrough).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# credential_crypto module
# ─────────────────────────────────────────────

def test_module_exports_three_helpers():
    from services import credential_crypto as cc
    assert callable(cc.encrypt_credentials)
    assert callable(cc.decrypt_credentials)
    assert callable(cc.is_encryption_available)


def test_encrypt_round_trip_with_real_key(monkeypatch):
    monkeypatch.setenv(
        "AUREM_ENCRYPTION_KEY",
        "test-key-iter326ww-some-passphrase-here",
    )
    # Reload to pick up the new env var
    import importlib
    from services import credential_crypto as cc
    importlib.reload(cc)
    assert cc.is_encryption_available() is True

    plain = {"api_key": "sk-live-secret-1234", "phone": "+16134000000"}
    envelope = cc.encrypt_credentials(plain)
    assert envelope["v"] == 1
    assert envelope["_encrypted"] is True
    assert "ct" in envelope
    # Ciphertext must not contain the plaintext anywhere
    assert "sk-live-secret-1234" not in envelope["ct"]
    assert "+16134000000" not in envelope["ct"]
    # Round-trip
    out = cc.decrypt_credentials(envelope)
    assert out == plain


def test_encrypt_fallback_when_key_missing(monkeypatch):
    monkeypatch.delenv("AUREM_ENCRYPTION_KEY", raising=False)
    import importlib
    from services import credential_crypto as cc
    importlib.reload(cc)
    assert cc.is_encryption_available() is False
    envelope = cc.encrypt_credentials({"x": 1})
    assert envelope["_encrypted"] is False
    assert envelope["v"] == 0
    assert envelope["config"] == {"x": 1}


def test_decrypt_handles_legacy_raw_dict():
    """Old rows that pre-date 326ww have a raw dict (no _encrypted
    flag). The decrypter must return them unchanged."""
    from services.credential_crypto import decrypt_credentials
    legacy = {"api_key": "legacy-key"}
    assert decrypt_credentials(legacy) == legacy


def test_decrypt_handles_v0_plaintext_envelope():
    """v0 envelopes (encryption unavailable at write-time) must
    return their `config` field."""
    from services.credential_crypto import decrypt_credentials
    env = {"v": 0, "_encrypted": False, "config": {"api_key": "x"}}
    assert decrypt_credentials(env) == {"api_key": "x"}


def test_decrypt_corrupt_ciphertext_returns_none(monkeypatch):
    monkeypatch.setenv(
        "AUREM_ENCRYPTION_KEY",
        "test-key-iter326ww-some-passphrase-here",
    )
    import importlib
    from services import credential_crypto as cc
    importlib.reload(cc)
    env = {"v": 1, "_encrypted": True, "ct": "not-a-real-fernet-token"}
    assert cc.decrypt_credentials(env) is None


def test_decrypt_none_returns_none():
    from services.credential_crypto import decrypt_credentials
    assert decrypt_credentials(None) is None


def test_same_passphrase_produces_same_key(monkeypatch):
    """A redeploy with the same env var must decrypt previous rows."""
    monkeypatch.setenv("AUREM_ENCRYPTION_KEY", "stable-passphrase-for-test")
    import importlib
    from services import credential_crypto as cc1
    importlib.reload(cc1)
    env1 = cc1.encrypt_credentials({"k": "v"})
    # Simulate redeploy by re-importing
    importlib.reload(cc1)
    out = cc1.decrypt_credentials(env1)
    assert out == {"k": "v"}


# ─────────────────────────────────────────────
# Router wire-up
# ─────────────────────────────────────────────

def test_connect_tool_imports_credential_crypto():
    src = (BACKEND / "routers" / "ai_platform_router.py").read_text()
    assert "from services.credential_crypto import" in src
    assert "encrypt_credentials" in src
    # Old plaintext line must be gone
    assert '"config": data.credentials' not in src
    assert "config_envelope" in src


def test_connect_tool_refuses_plaintext_for_sensitive_tools():
    src = (BACKEND / "routers" / "ai_platform_router.py").read_text()
    # 503 + tool_type membership check
    assert "Encryption key not configured" in src
    for sensitive in ("whatsapp", "email", "twilio", "stripe",
                      "openai", "gemini", "claude", "smtp"):
        assert f'"{sensitive}"' in src or f"'{sensitive}'" in src, \
            f"sensitive tool guard missing: {sensitive}"


def test_status_endpoint_does_not_leak_credentials():
    """`GET /tools/status` only exposes connected/status/connected_at —
    never the envelope or config."""
    src = (BACKEND / "routers" / "ai_platform_router.py").read_text()
    idx = src.index('@router.get("/tools/status")')
    block = src[idx: idx + 1200]
    # No reference to config, config_envelope, or credentials in the response
    assert '"config"' not in block
    assert '"config_envelope"' not in block
    assert "data.credentials" not in block


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_326ww_marker_present():
    src = (BACKEND / "services" / "credential_crypto.py").read_text()
    assert "326ww" in src
    src2 = (BACKEND / "routers" / "ai_platform_router.py").read_text()
    assert "326ww" in src2
