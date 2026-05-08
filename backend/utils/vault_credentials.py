"""
AUREM Vault Credential Fetcher
Utility to retrieve decrypted API keys from the Secret Vault for service integrations.
Used by enrichment_service.py, crm_sync_engine.py, and other integration routers.
"""
import os
import base64
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

ENCRYPTION_KEY = os.environ.get("AUREM_ENCRYPTION_KEY", "aurem32characterencryptionkey!")


def _get_aes_key():
    key_bytes = ENCRYPTION_KEY.encode("utf-8")
    if len(key_bytes) < 32:
        key_bytes = key_bytes.ljust(32, b'\0')
    return key_bytes[:32]


def _decrypt(encrypted_b64: str) -> str:
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encrypted_b64)
    nonce = raw[:12]
    ciphertext = raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


async def get_vault_credentials(db, user_id: str, provider: str) -> dict:
    """
    Fetch decrypted credentials from the secret vault for a given provider.
    Returns dict of decrypted key-value pairs, or empty dict if not found.
    
    Usage:
        creds = await get_vault_credentials(db, user_id, "apollo")
        api_key = creds.get("api_key", "")
    """
    doc = await db.secret_vault.find_one(
        {"user_id": user_id, "provider": provider},
        {"_id": 0}
    )
    if not doc:
        return {}

    credentials = {}
    for key, encrypted_value in doc.get("encrypted_credentials", {}).items():
        try:
            credentials[key] = _decrypt(encrypted_value)
        except Exception:
            logger.warning(f"Failed to decrypt vault key '{key}' for provider '{provider}'")
            credentials[key] = ""
    return credentials
