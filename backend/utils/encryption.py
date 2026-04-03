"""
Data Encryption Utilities for Reroots
Provides Fernet symmetric encryption for sensitive customer data.
Uses ENCRYPTION_KEY from environment variables.
"""

import os
import base64
import logging
from typing import Optional, Any, Dict
from functools import lru_cache

logger = logging.getLogger(__name__)

# Lazy initialization to avoid startup failures
_fernet = None
_encryption_available = None


def _get_fernet():
    """Get or create Fernet instance."""
    global _fernet, _encryption_available
    
    if _encryption_available is False:
        return None
    
    if _fernet is not None:
        return _fernet
    
    try:
        from cryptography.fernet import Fernet
        
        key = os.environ.get("ENCRYPTION_KEY")
        
        if not key:
            logger.warning("[ENCRYPTION] ENCRYPTION_KEY not set - encryption disabled")
            _encryption_available = False
            return None
        
        # Validate key format (must be 32 url-safe base64-encoded bytes)
        try:
            # If key is not base64, generate one from it
            if len(key) == 32:
                # Raw 32-byte key - encode it
                key = base64.urlsafe_b64encode(key.encode()[:32]).decode()
            elif len(key) != 44:
                # Generate from hash of provided key
                import hashlib
                key_bytes = hashlib.sha256(key.encode()).digest()
                key = base64.urlsafe_b64encode(key_bytes).decode()
            
            _fernet = Fernet(key.encode())
            _encryption_available = True
            logger.info("[ENCRYPTION] Encryption initialized successfully")
            return _fernet
            
        except Exception as e:
            logger.error(f"[ENCRYPTION] Invalid ENCRYPTION_KEY format: {e}")
            _encryption_available = False
            return None
            
    except ImportError:
        logger.error("[ENCRYPTION] cryptography library not installed - pip install cryptography")
        _encryption_available = False
        return None


def encrypt_field(value: Optional[str]) -> Optional[str]:
    """
    Encrypt a string value using Fernet.
    
    Args:
        value: Plain text string to encrypt
        
    Returns:
        Base64-encoded encrypted string, or original value if encryption unavailable
    """
    if not value:
        return value
    
    fernet = _get_fernet()
    if not fernet:
        return value  # Pass through if encryption unavailable
    
    try:
        encrypted = fernet.encrypt(value.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"[ENCRYPTION] Encryption failed: {e}")
        return value


def decrypt_field(value: Optional[str]) -> Optional[str]:
    """
    Decrypt a Fernet-encrypted string.
    
    Args:
        value: Base64-encoded encrypted string
        
    Returns:
        Decrypted plain text, or original value if decryption fails
    """
    if not value:
        return value
    
    fernet = _get_fernet()
    if not fernet:
        return value  # Pass through if encryption unavailable
    
    try:
        decrypted = fernet.decrypt(value.encode())
        return decrypted.decode()
    except Exception:
        # Value might not be encrypted (legacy data)
        # Return as-is instead of failing
        return value


def encrypt_profile_fields(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt sensitive fields in a customer profile before storing.
    
    Encrypts: skin_concerns, allergies, skin_type, purchase_intent
    Leaves unchanged: session_id, customer_email, timestamp
    
    Args:
        profile: Customer profile dictionary
        
    Returns:
        Profile with sensitive fields encrypted
    """
    # Fields to encrypt
    sensitive_fields = ['skin_concerns', 'allergies', 'skin_type', 'purchase_intent']
    
    encrypted_profile = profile.copy()
    
    for field in sensitive_fields:
        if field in encrypted_profile and encrypted_profile[field]:
            value = encrypted_profile[field]
            # Handle both string and list values
            if isinstance(value, list):
                encrypted_profile[field] = [encrypt_field(str(v)) for v in value]
            else:
                encrypted_profile[field] = encrypt_field(str(value))
    
    return encrypted_profile


def decrypt_profile_fields(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt sensitive fields in a customer profile after reading.
    
    Args:
        profile: Customer profile dictionary with encrypted fields
        
    Returns:
        Profile with sensitive fields decrypted
    """
    # Fields that were encrypted
    sensitive_fields = ['skin_concerns', 'allergies', 'skin_type', 'purchase_intent']
    
    decrypted_profile = profile.copy()
    
    for field in sensitive_fields:
        if field in decrypted_profile and decrypted_profile[field]:
            value = decrypted_profile[field]
            # Handle both string and list values
            if isinstance(value, list):
                decrypted_profile[field] = [decrypt_field(str(v)) for v in value]
            else:
                decrypted_profile[field] = decrypt_field(str(value))
    
    return decrypted_profile


def is_encryption_available() -> bool:
    """Check if encryption is properly configured."""
    _get_fernet()  # Initialize if needed
    return _encryption_available is True


def generate_encryption_key() -> str:
    """
    Generate a new Fernet-compatible encryption key.
    Use this to create ENCRYPTION_KEY for .env file.
    
    Returns:
        Base64-encoded 32-byte key
    """
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()
