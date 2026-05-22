"""
credential_crypto.py — iter 326ww

Symmetric encryption for third-party tool credentials stored in
Mongo (`platform_users.tool_connections.{tool}.config`). Closes P0
TODO from /app/backend/routers/ai_platform_router.py:609 / 622
(plaintext credentials at rest).

Design choices
--------------
1. Fernet (AES-128-CBC + HMAC-SHA256, authenticated) from the
   `cryptography` package — vetted, no nonce-reuse footguns.
2. The env var `AUREM_ENCRYPTION_KEY` is a human-friendly passphrase
   (~30 chars, mixed-case). We derive a stable 32-byte Fernet key
   from it ONCE at import time via PBKDF2-HMAC-SHA256 with a fixed
   project salt ("aurem-creds-v1"). Same passphrase → same key
   forever, so existing ciphertexts always decrypt.
3. Encrypted payloads are tagged with a version prefix ("v1:") so a
   future key-rotation migration can branch on it.
4. Failures NEVER raise — encrypt returns the plaintext envelope on
   missing/bad key (with `_encrypted: False`) so connect_tool never
   500s on a config issue. Decrypt swallows errors and returns
   `None` so a corrupt ciphertext can't break the status page.

Public API
----------
    encrypt_credentials(plain: dict) -> dict
        → {"v": 1, "_encrypted": True, "ct": "<base64>"} on success
        → {"v": 0, "_encrypted": False, "config": plain} on no-key

    decrypt_credentials(envelope: dict) -> dict | None
        → original dict or None on failure

    is_encryption_available() -> bool
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_FERNET = None  # lazy-init singleton
_INIT_TRIED = False
_PROJECT_SALT = b"aurem-creds-v1"


def _init_fernet():
    """Build the module-level Fernet from AUREM_ENCRYPTION_KEY.

    Returns the Fernet instance, or None if key missing / cryptography
    not importable. Safe to call multiple times — caches the result.
    """
    global _FERNET, _INIT_TRIED
    if _FERNET is not None or _INIT_TRIED:
        return _FERNET
    _INIT_TRIED = True

    passphrase = os.environ.get("AUREM_ENCRYPTION_KEY", "").strip()
    if not passphrase:
        logger.warning(
            "[cred-crypto] AUREM_ENCRYPTION_KEY missing — tool credentials "
            "will be written PLAINTEXT until the env var is set"
        )
        return None
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as e:
        logger.warning(f"[cred-crypto] cryptography lib unavailable: {e}")
        return None

    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_PROJECT_SALT,
            iterations=200_000,
        )
        key_bytes = kdf.derive(passphrase.encode("utf-8"))
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        _FERNET = Fernet(key_b64)
        logger.info("[cred-crypto] Fernet initialised (PBKDF2-derived from AUREM_ENCRYPTION_KEY)")
    except Exception as e:
        logger.exception(f"[cred-crypto] Fernet init failed: {e}")
        _FERNET = None
    return _FERNET


def is_encryption_available() -> bool:
    """True iff we can encrypt at rest right now."""
    return _init_fernet() is not None


def encrypt_credentials(plain: Any) -> dict:
    """Wrap `plain` in an encrypted envelope.

    `plain` may be any JSON-serialisable structure (typically the
    dict of credentials a user posted to /tools/connect). The
    envelope shape is:

        {"v": 1, "_encrypted": True, "ct": "<base64-fernet-token>"}

    If encryption isn't available (no key / no lib), we fall back to:

        {"v": 0, "_encrypted": False, "config": <plain>}

    Callers that care about at-rest safety should refuse to persist
    rows where `_encrypted` is False — log + alert instead.
    """
    f = _init_fernet()
    if f is None:
        return {"v": 0, "_encrypted": False, "config": plain}
    try:
        raw = json.dumps(plain, default=str, separators=(",", ":")).encode("utf-8")
        token = f.encrypt(raw).decode("ascii")
        return {"v": 1, "_encrypted": True, "ct": token}
    except Exception as e:
        logger.exception(f"[cred-crypto] encrypt failed, falling back to plaintext: {e}")
        return {"v": 0, "_encrypted": False, "config": plain}


def decrypt_credentials(envelope: Any) -> Any:
    """Inverse of encrypt_credentials.

    Accepts:
      - the v1 encrypted envelope → returns the decrypted dict
      - the v0 plaintext envelope → returns its `config` field
      - any other shape (legacy raw dict from before iter 326ww) →
        returns it unchanged so existing rows still work
      - None → returns None
    """
    if envelope is None:
        return None
    if not isinstance(envelope, dict):
        return envelope
    if envelope.get("_encrypted") is True and envelope.get("ct"):
        f = _init_fernet()
        if f is None:
            logger.warning("[cred-crypto] decrypt called with no key — returning None")
            return None
        try:
            raw = f.decrypt(envelope["ct"].encode("ascii"))
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            logger.warning(f"[cred-crypto] decrypt failed: {e}")
            return None
    if "_encrypted" in envelope:
        return envelope.get("config")
    # Legacy raw dict — return as-is for backward compatibility.
    return envelope


__all__ = [
    "encrypt_credentials",
    "decrypt_credentials",
    "is_encryption_available",
]
