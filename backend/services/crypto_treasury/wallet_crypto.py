"""
AUREM Wallet Crypto
===================
Fernet-based symmetric encryption for sensitive wallet material
(private keys) stored in MongoDB. All new writes are ENCRYPTED;
reads transparently decrypt.

Key source:
  1. WALLET_ENCRYPTION_KEY env var (urlsafe base64, 32 bytes raw)
  2. If missing at boot, a one-time key is derived from
     JWT_SECRET via HKDF (so even without explicit config, wallets
     are never stored plaintext on new nodes).

Format written to DB:
  "fernet:v1:<token>"        — encrypted
  "0x..."  / hex             — legacy plaintext (still read for
                               backward compat; re-encrypted on next
                               write via `migrate_plaintext_to_encrypted`).

`encrypt` is idempotent: if input already carries the `fernet:v1:`
prefix, it is returned as-is.
"""
from __future__ import annotations

import os
import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_PREFIX = "fernet:v1:"
_fernet: Optional[Fernet] = None


def _derive_key_from_jwt_secret() -> bytes:
    """Fallback: derive a stable 32-byte Fernet key from JWT_SECRET."""
    jwt_secret = os.environ.get("JWT_SECRET", "").encode("utf-8")
    if not jwt_secret:
        # Last-resort: the container is completely unconfigured. Use a
        # random in-memory key — wallets written this boot are still
        # encrypted but will become unreadable on pod restart. This
        # surfaces the misconfiguration loudly rather than storing
        # plaintext.
        logger.error("[wallet-crypto] JWT_SECRET missing — using EPHEMERAL key; "
                     "new wallets will not survive pod restart. Set WALLET_ENCRYPTION_KEY.")
        return base64.urlsafe_b64encode(os.urandom(32))
    digest = hashlib.sha256(b"aurem-wallet-v1|" + jwt_secret).digest()  # 32 bytes
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    raw = os.environ.get("WALLET_ENCRYPTION_KEY", "").strip()
    if raw:
        try:
            _fernet = Fernet(raw.encode("utf-8") if isinstance(raw, str) else raw)
            logger.info("[wallet-crypto] loaded WALLET_ENCRYPTION_KEY from env")
            return _fernet
        except Exception as e:
            logger.warning(f"[wallet-crypto] WALLET_ENCRYPTION_KEY invalid ({e}) — falling back to JWT-derived key")
    _fernet = Fernet(_derive_key_from_jwt_secret())
    logger.info("[wallet-crypto] using JWT-derived fallback key")
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a private key string. Idempotent."""
    if not plaintext:
        return plaintext
    if plaintext.startswith(_PREFIX):
        return plaintext  # already encrypted
    token = _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{token}"


def decrypt(stored: str) -> str:
    """Decrypt a stored string; transparently handles legacy plaintext."""
    if not stored:
        return stored
    if not stored.startswith(_PREFIX):
        # Legacy plaintext row — return as-is. Caller can opt in to
        # migrate by calling `migrate_plaintext_to_encrypted`.
        return stored
    token = stored[len(_PREFIX):]
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("wallet key decryption failed — wrong WALLET_ENCRYPTION_KEY?")


async def migrate_plaintext_to_encrypted(db, collection: str = "crypto_wallets") -> dict:
    """One-shot migration: encrypt every row whose private_key is still
    plaintext. Safe to re-run; idempotent."""
    if db is None:
        return {"migrated": 0, "already_encrypted": 0, "error": "no_db"}
    migrated = 0
    already = 0
    cursor = db[collection].find({}, {"_id": 1, "private_key": 1})
    async for row in cursor:
        pk = row.get("private_key") or ""
        if not pk:
            continue
        if pk.startswith(_PREFIX):
            already += 1
            continue
        enc = encrypt(pk)
        await db[collection].update_one({"_id": row["_id"]}, {"$set": {"private_key": enc}})
        migrated += 1
    logger.info(f"[wallet-crypto] migration complete — migrated={migrated} already_encrypted={already}")
    return {"migrated": migrated, "already_encrypted": already}


__all__ = ["encrypt", "decrypt", "migrate_plaintext_to_encrypted"]
