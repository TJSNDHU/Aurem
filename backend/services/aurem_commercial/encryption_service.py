"""
AUREM Commercial Platform - Encryption Service
AES-256 encryption for sensitive data (tokens, PII)
PIPEDA Compliant - Canada Privacy Law

Usage:
    from services.aurem_commercial.encryption_service import EncryptionService
    
    enc = EncryptionService()
    encrypted = enc.encrypt("my_secret_token")
    decrypted = enc.decrypt(encrypted)
"""

import os
import base64
import hashlib
import secrets
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    AES-256 encryption service for sensitive data.
    Key is derived from environment variable AUREM_ENCRYPTION_KEY.
    """
    
    def __init__(self):
        self._master_key = self._get_or_create_master_key()
        self._fernet = Fernet(self._derive_fernet_key())
    
    def _get_or_create_master_key(self) -> bytes:
        """Get encryption key from env or create one"""
        key_str = os.environ.get("AUREM_ENCRYPTION_KEY")
        
        if not key_str:
            # Generate a new key if not set (for development)
            # In production, this MUST be set in environment
            logger.warning(
                "[Encryption] AUREM_ENCRYPTION_KEY not set! "
                "Generating temporary key. SET THIS IN PRODUCTION!"
            )
            key_str = secrets.token_hex(32)  # 256 bits
            os.environ["AUREM_ENCRYPTION_KEY"] = key_str
        
        # Ensure key is proper length (32 bytes for AES-256)
        return hashlib.sha256(key_str.encode()).digest()
    
    def _derive_fernet_key(self) -> bytes:
        """Derive Fernet-compatible key from master key"""
        # Fernet requires base64-encoded 32-byte key
        return base64.urlsafe_b64encode(self._master_key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string using AES-256.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""
        
        try:
            encrypted = self._fernet.encrypt(plaintext.encode('utf-8'))
            return encrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"[Encryption] Encrypt error: {e}")
            raise ValueError("Encryption failed")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an AES-256 encrypted string.
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ""
        
        try:
            decrypted = self._fernet.decrypt(ciphertext.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"[Encryption] Decrypt error: {e}")
            raise ValueError("Decryption failed - invalid key or corrupted data")
    
    def encrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing data
            fields: List of field names to encrypt
            
        Returns:
            Dictionary with specified fields encrypted
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.encrypt(str(result[field]))
        return result
    
    def decrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            fields: List of field names to decrypt
            
        Returns:
            Dictionary with specified fields decrypted
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                try:
                    result[field] = self.decrypt(str(result[field]))
                except:
                    # Field might not be encrypted (legacy data)
                    pass
        return result
    
    def hash_for_lookup(self, value: str) -> str:
        """
        Create a searchable hash of a value.
        Use this for indexed lookups (e.g., finding user by email)
        without storing plaintext.
        
        Args:
            value: Value to hash
            
        Returns:
            Hex-encoded hash
        """
        if not value:
            return ""
        
        # Use HMAC with master key for consistent hashing
        import hmac
        return hmac.new(
            self._master_key,
            value.lower().strip().encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def generate_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure random token"""
        return secrets.token_urlsafe(length)


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get the singleton encryption service instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
