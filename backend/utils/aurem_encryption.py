"""
AUREM Security - Fernet Encryption Layer
Company: Polaris Built Inc.

Encrypts sensitive prospect data before MongoDB storage.
Decrypts transparently on read.

Encrypted fields: prospect_email, prospect_phone, outreach_message_body, company_hook
Never encrypted: mission_id, timestamp, status (lookup keys)
"""

import os
import logging
from typing import Any, Dict, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Try to import cryptography - install if needed
try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    logger.warning("[AUREM ENCRYPTION] cryptography not installed - encryption disabled")
    Fernet = None
    InvalidToken = Exception


# Fields that should be encrypted in MongoDB
ENCRYPTED_FIELDS = [
    "prospect_email",
    "prospect_phone", 
    "outreach_message_body",
    "company_hook",
    "contact_hint",
    "message",  # In outreach plans
]

# Fields that should NEVER be encrypted (lookup keys)
NEVER_ENCRYPT = [
    "mission_id",
    "timestamp",
    "status",
    "phase",
    "_id",
    "created_at",
    "completed_at",
]


@lru_cache(maxsize=1)
def get_fernet() -> Optional[Fernet]:
    """Get Fernet cipher instance (cached)"""
    if Fernet is None:
        return None
    
    key = os.environ.get("AUREM_ENCRYPTION_KEY")
    if not key:
        # Generate dev key
        key = Fernet.generate_key().decode()
        os.environ["AUREM_ENCRYPTION_KEY"] = key
        logger.warning("[AUREM ENCRYPTION] Generated development key")
    
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        logger.error(f"[AUREM ENCRYPTION] Invalid key: {e}")
        return None


def encrypt_value(value: str) -> str:
    """Encrypt a string value"""
    if not value or not isinstance(value, str):
        return value
    
    fernet = get_fernet()
    if not fernet:
        return value
    
    try:
        encrypted = fernet.encrypt(value.encode('utf-8'))
        return f"ENC:{encrypted.decode('utf-8')}"
    except Exception as e:
        logger.error(f"[AUREM ENCRYPTION] Encrypt error: {e}")
        return value


def decrypt_value(value: str) -> str:
    """Decrypt a string value"""
    if not value or not isinstance(value, str):
        return value
    
    if not value.startswith("ENC:"):
        return value  # Not encrypted
    
    fernet = get_fernet()
    if not fernet:
        return value
    
    try:
        encrypted = value[4:].encode('utf-8')  # Remove "ENC:" prefix
        decrypted = fernet.decrypt(encrypted)
        return decrypted.decode('utf-8')
    except InvalidToken:
        logger.warning("[AUREM ENCRYPTION] Invalid token - possibly different key")
        return "[ENCRYPTED]"
    except Exception as e:
        logger.error(f"[AUREM ENCRYPTION] Decrypt error: {e}")
        return value


def encrypt_document(doc: Dict[str, Any], fields: List[str] = None) -> Dict[str, Any]:
    """Encrypt specified fields in a document before MongoDB insert"""
    if not doc:
        return doc
    
    fields_to_encrypt = fields or ENCRYPTED_FIELDS
    encrypted_doc = doc.copy()
    
    for key, value in doc.items():
        if key in NEVER_ENCRYPT:
            continue
        
        if key in fields_to_encrypt and isinstance(value, str):
            encrypted_doc[key] = encrypt_value(value)
        elif isinstance(value, dict):
            encrypted_doc[key] = encrypt_document(value, fields_to_encrypt)
        elif isinstance(value, list):
            encrypted_doc[key] = [
                encrypt_document(item, fields_to_encrypt) if isinstance(item, dict) 
                else encrypt_value(item) if isinstance(item, str) and key in fields_to_encrypt
                else item
                for item in value
            ]
    
    return encrypted_doc


def decrypt_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypt all encrypted fields in a document after MongoDB read"""
    if not doc:
        return doc
    
    decrypted_doc = doc.copy()
    
    for key, value in doc.items():
        if isinstance(value, str) and value.startswith("ENC:"):
            decrypted_doc[key] = decrypt_value(value)
        elif isinstance(value, dict):
            decrypted_doc[key] = decrypt_document(value)
        elif isinstance(value, list):
            decrypted_doc[key] = [
                decrypt_document(item) if isinstance(item, dict)
                else decrypt_value(item) if isinstance(item, str) and item.startswith("ENC:")
                else item
                for item in value
            ]
    
    return decrypted_doc


def mask_phone(phone: str) -> str:
    """Mask phone number for display (show last 4 digits only)"""
    if not phone:
        return ""
    clean = phone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    if len(clean) >= 4:
        return f"***-***-{clean[-4:]}"
    return "***"


def mask_email(email: str) -> str:
    """Mask email for display"""
    if not email or "@" not in email:
        return "***@***.***"
    parts = email.split("@")
    username = parts[0]
    domain = parts[1]
    masked_user = username[0] + "***" if len(username) > 1 else "***"
    return f"{masked_user}@{domain}"


# ═══════════════════════════════════════════════════════════════════════════════
# API KEY ENCRYPTION (for Admin Mission Control)
# ═══════════════════════════════════════════════════════════════════════════════

def encrypt_api_key(plain_key: str) -> str:
    """
    Encrypt an API key for secure storage
    Uses same Fernet cipher as prospect encryption
    """
    return encrypt_value(plain_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an API key from secure storage
    Uses same Fernet cipher as prospect encryption
    """
    return decrypt_value(encrypted_key)
