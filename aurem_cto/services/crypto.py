"""
aurem_cto.services.crypto — per-customer encryption + audit-logged vault.

iter D-31 — HKDF-derived per-customer key wrapped over Fernet.

Master key sits in `AUREM_CTO_MASTER_KEY` (env). Per-customer key =
HKDF-SHA256(master_key, info=user_id, length=32). Each customer gets a
distinct AES-256 key, so a leak of one customer's ciphertext bag never
exposes another's.

Backwards compatibility: if the env master key is unset we **fail
closed** — the vault refuses to operate rather than silently falling
back to weaker encryption. The host can still use the legacy
`services.byok_store` fernet path for non-AUREM-CTO secrets; only this
module is locked to AUREM_CTO_MASTER_KEY.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet, InvalidToken

from .db import get_db


def _master_key() -> bytes:
    raw = os.environ.get("AUREM_CTO_MASTER_KEY", "").strip()
    if not raw:
        # Production fail-closed for crypto OPERATIONS — but the import
        # of this module must never crash the host server. This guard
        # only fires when encrypt/decrypt is actually CALLED.
        raise RuntimeError(
            "AUREM_CTO_MASTER_KEY env var missing — vault refuses to "
            "operate without an explicit master key (fail-closed). "
            "Set this env var on the deployment to enable AUREM CTO "
            "vault features."
        )
    if len(raw) < 32:
        raise RuntimeError("AUREM_CTO_MASTER_KEY must be >= 32 chars")
    return raw.encode()


def is_vault_available() -> bool:
    """Cheap pre-flight check — callers can branch on this instead of
    catching RuntimeError after a failed crypto op."""
    raw = os.environ.get("AUREM_CTO_MASTER_KEY", "").strip()
    return bool(raw) and len(raw) >= 32


def _derive_customer_key(user_id: str) -> bytes:
    """HKDF-SHA256 → 32 bytes → Fernet-compatible base64."""
    if not user_id:
        raise ValueError("user_id required for key derivation")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"aurem_cto_v1",
        info=f"user:{user_id}".encode(),
    )
    raw = hkdf.derive(_master_key())
    return base64.urlsafe_b64encode(raw)


async def _audit(user_id: str, op: str, kind: str,
                  ok: bool, err: Optional[str] = None) -> None:
    """Write a row to aurem_cto_vault_audit_log. Never raises."""
    db = get_db()
    if db is None:
        return
    try:
        await db.aurem_cto_vault_audit_log.insert_one({
            "user_id": user_id,
            "op":      op,          # "encrypt" | "decrypt"
            "kind":    kind,        # "ssh_private_key" | "github_pat" | …
            "ok":      ok,
            "error":   err,
            "ts":      datetime.now(timezone.utc),
        })
    except Exception:
        pass  # audit failure must never break the surrounding op


async def encrypt(user_id: str, plaintext: str, kind: str = "secret") -> str:
    """Returns the ciphertext as a string. Audit-logged."""
    try:
        f = Fernet(_derive_customer_key(user_id))
        ct = f.encrypt(plaintext.encode()).decode()
        await _audit(user_id, "encrypt", kind, True)
        return f"v1:{ct}"
    except Exception as e:
        await _audit(user_id, "encrypt", kind, False, err=str(e)[:200])
        raise


async def decrypt(user_id: str, ciphertext: str, kind: str = "secret") -> str:
    """Returns the plaintext. Raises on tamper / wrong key."""
    if not ciphertext:
        return ""
    try:
        if not ciphertext.startswith("v1:"):
            raise ValueError("unsupported_ciphertext_version")
        f = Fernet(_derive_customer_key(user_id))
        pt = f.decrypt(ciphertext[3:].encode()).decode()
        await _audit(user_id, "decrypt", kind, True)
        return pt
    except InvalidToken:
        await _audit(user_id, "decrypt", kind, False, err="invalid_token")
        raise
    except Exception as e:
        await _audit(user_id, "decrypt", kind, False, err=str(e)[:200])
        raise
