"""
AUREM Commercial Platform - Token Vault Service
Secure storage and retrieval of OAuth tokens and API credentials
AES-256 encrypted at rest

Features:
- Encrypted storage of access/refresh tokens
- Automatic token refresh before expiry
- Token revocation
- Audit logging of all access
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from .encryption_service import get_encryption_service
from .audit_service import AuditLogger, AuditAction, get_audit_logger

logger = logging.getLogger(__name__)


class IntegrationProvider(str, Enum):
    """Supported integration providers"""
    GOOGLE = "google"           # Gmail, Calendar, etc.
    META = "meta"               # WhatsApp, Facebook
    SHOPIFY = "shopify"
    SQUARE = "square"
    STRIPE = "stripe"
    TWILIO = "twilio"
    CALENDLY = "calendly"


class IntegrationStatus(str, Enum):
    """Status of an integration"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"
    PENDING = "pending"


# Fields that must be encrypted
ENCRYPTED_FIELDS = [
    "access_token",
    "refresh_token",
    "api_key",
    "api_secret",
    "webhook_secret"
]


class TokenVault:
    """
    Secure token storage with encryption and audit logging.
    """
    
    COLLECTION_NAME = "aurem_integrations"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION_NAME]
        self.encryption = get_encryption_service()
        self.audit = get_audit_logger(db)
    
    async def ensure_indexes(self):
        """Create database indexes - handles existing indexes gracefully"""
        indexes = [
            {"keys": "business_id"},
            {"keys": "provider"},
            {"keys": [("business_id", 1), ("provider", 1)], "unique": True},
            {"keys": "status"},
            {"keys": "expires_at"}
        ]
        for idx in indexes:
            try:
                if "unique" in idx:
                    await self.collection.create_index(idx["keys"], unique=True)
                else:
                    await self.collection.create_index(idx["keys"])
            except Exception:
                pass  # Index exists or conflict
        logger.info("[TokenVault] Indexes verified")
    
    async def store_integration(
        self,
        business_id: str,
        provider: IntegrationProvider,
        credentials: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        scopes: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None,
        actor_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        Store or update integration credentials.
        
        Args:
            business_id: The business this integration belongs to
            provider: Integration provider (google, meta, etc.)
            credentials: Dict containing tokens/keys to store
            metadata: Provider-specific data (email, phone_number_id, etc.)
            scopes: OAuth scopes granted
            expires_at: When the access token expires
            actor_id: Who is storing this (for audit)
            ip_address: Request IP (for audit)
            
        Returns:
            Integration document ID
        """
        
        # Encrypt sensitive fields
        encrypted_credentials = self.encryption.encrypt_dict(
            credentials, 
            ENCRYPTED_FIELDS
        )
        
        now = datetime.now(timezone.utc)
        
        integration_doc = {
            "business_id": business_id,
            "provider": provider.value if isinstance(provider, IntegrationProvider) else provider,
            "status": IntegrationStatus.ACTIVE.value,
            "credentials": encrypted_credentials,
            "metadata": metadata or {},
            "scopes": scopes or [],
            "expires_at": expires_at,
            "connected_at": now,
            "last_used_at": now,
            "last_refreshed_at": now,
            "error_count": 0,
            "last_error": None
        }
        
        # Upsert (update if exists, insert if not)
        result = await self.collection.update_one(
            {
                "business_id": business_id,
                "provider": integration_doc["provider"]
            },
            {"$set": integration_doc},
            upsert=True
        )
        
        # Get the document ID
        if result.upserted_id:
            doc_id = str(result.upserted_id)
            action = AuditAction.INTEGRATION_CONNECTED
        else:
            doc = await self.collection.find_one({
                "business_id": business_id,
                "provider": integration_doc["provider"]
            })
            doc_id = str(doc["_id"])
            action = AuditAction.TOKEN_REFRESHED
        
        # Audit log
        await self.audit.log(
            action=action,
            business_id=business_id,
            actor_id=actor_id,
            actor_type="user",
            resource_type="integration",
            resource_id=doc_id,
            details={
                "provider": integration_doc["provider"],
                "scopes": scopes,
                "has_refresh_token": "refresh_token" in credentials
            },
            ip_address=ip_address,
            success=True
        )
        
        logger.info(f"[TokenVault] Stored {provider} integration for {business_id}")
        return doc_id
    
    async def get_credentials(
        self,
        business_id: str,
        provider: IntegrationProvider,
        actor_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        purpose: str = "api_call"
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve decrypted credentials for an integration.
        
        Args:
            business_id: The business
            provider: Which integration
            actor_id: Who is accessing (for audit)
            ip_address: Request IP (for audit)
            purpose: Why accessing (for audit)
            
        Returns:
            Decrypted credentials dict or None if not found
        """
        
        doc = await self.collection.find_one({
            "business_id": business_id,
            "provider": provider.value if isinstance(provider, IntegrationProvider) else provider
        })
        
        if not doc:
            logger.warning(f"[TokenVault] No {provider} integration for {business_id}")
            return None
        
        # Check if expired
        if doc.get("expires_at") and doc["expires_at"] < datetime.now(timezone.utc):
            # Try to refresh if we have a refresh token
            if doc.get("credentials", {}).get("refresh_token"):
                logger.info(f"[TokenVault] Token expired, refresh needed for {business_id}/{provider}")
                # Mark as expired - caller should trigger refresh
                await self.collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"status": IntegrationStatus.EXPIRED.value}}
                )
            doc["status"] = IntegrationStatus.EXPIRED.value
        
        # Check status
        if doc.get("status") == IntegrationStatus.REVOKED.value:
            logger.warning(f"[TokenVault] Integration revoked: {business_id}/{provider}")
            return None
        
        # Decrypt credentials
        decrypted_credentials = self.encryption.decrypt_dict(
            doc.get("credentials", {}),
            ENCRYPTED_FIELDS
        )
        
        # Update last used
        await self.collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"last_used_at": datetime.now(timezone.utc)}}
        )
        
        # Audit log
        await self.audit.log(
            action=AuditAction.TOKEN_ACCESSED,
            business_id=business_id,
            actor_id=actor_id,
            actor_type="system" if not actor_id else "user",
            resource_type="integration",
            resource_id=str(doc["_id"]),
            details={
                "provider": doc["provider"],
                "purpose": purpose,
                "status": doc.get("status")
            },
            ip_address=ip_address,
            success=True
        )
        
        return {
            "credentials": decrypted_credentials,
            "metadata": doc.get("metadata", {}),
            "scopes": doc.get("scopes", []),
            "status": doc.get("status"),
            "expires_at": doc.get("expires_at"),
            "connected_at": doc.get("connected_at")
        }
    
    async def revoke_integration(
        self,
        business_id: str,
        provider: IntegrationProvider,
        actor_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        reason: str = "user_requested"
    ) -> bool:
        """
        Revoke an integration (soft delete - keeps audit trail).
        
        Args:
            business_id: The business
            provider: Which integration to revoke
            actor_id: Who is revoking
            ip_address: Request IP
            reason: Why revoking
            
        Returns:
            True if revoked, False if not found
        """
        
        result = await self.collection.update_one(
            {
                "business_id": business_id,
                "provider": provider.value if isinstance(provider, IntegrationProvider) else provider
            },
            {
                "$set": {
                    "status": IntegrationStatus.REVOKED.value,
                    "revoked_at": datetime.now(timezone.utc),
                    "revoked_reason": reason,
                    # Clear sensitive data but keep record
                    "credentials": {}
                }
            }
        )
        
        if result.modified_count > 0:
            await self.audit.log(
                action=AuditAction.INTEGRATION_DISCONNECTED,
                business_id=business_id,
                actor_id=actor_id,
                actor_type="user" if actor_id else "system",
                resource_type="integration",
                details={
                    "provider": provider.value if isinstance(provider, IntegrationProvider) else provider,
                    "reason": reason
                },
                ip_address=ip_address,
                success=True
            )
            logger.info(f"[TokenVault] Revoked {provider} for {business_id}")
            return True
        
        return False
    
    async def get_all_integrations(
        self,
        business_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all integrations for a business (without credentials).
        
        Args:
            business_id: The business
            
        Returns:
            List of integration summaries (no sensitive data)
        """
        
        cursor = self.collection.find(
            {"business_id": business_id},
            {
                "credentials": 0,  # Exclude credentials
                "webhook_secret": 0
            }
        )
        
        integrations = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            integrations.append(doc)
        
        return integrations
    
    async def record_error(
        self,
        business_id: str,
        provider: IntegrationProvider,
        error_message: str
    ):
        """Record an error for an integration"""
        
        await self.collection.update_one(
            {
                "business_id": business_id,
                "provider": provider.value if isinstance(provider, IntegrationProvider) else provider
            },
            {
                "$set": {
                    "last_error": error_message,
                    "last_error_at": datetime.now(timezone.utc)
                },
                "$inc": {"error_count": 1}
            }
        )
        
        # Check if too many errors
        doc = await self.collection.find_one({
            "business_id": business_id,
            "provider": provider.value if isinstance(provider, IntegrationProvider) else provider
        })
        
        if doc and doc.get("error_count", 0) >= 10:
            # Auto-disable after 10 errors
            await self.collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": IntegrationStatus.ERROR.value}}
            )
            
            await self.audit.log(
                action=AuditAction.INTEGRATION_ERROR,
                business_id=business_id,
                actor_id="system",
                actor_type="system",
                resource_type="integration",
                details={
                    "provider": provider.value if isinstance(provider, IntegrationProvider) else provider,
                    "error_count": doc.get("error_count", 0),
                    "auto_disabled": True
                },
                success=False,
                error_message="Too many errors - integration disabled"
            )
    
    async def get_expiring_tokens(
        self,
        within_hours: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Find tokens that will expire soon (for proactive refresh).
        
        Args:
            within_hours: Find tokens expiring within this many hours
            
        Returns:
            List of integrations needing refresh
        """
        
        expiry_threshold = datetime.now(timezone.utc) + timedelta(hours=within_hours)
        
        cursor = self.collection.find({
            "status": IntegrationStatus.ACTIVE.value,
            "expires_at": {"$lt": expiry_threshold},
            "credentials.refresh_token": {"$exists": True}
        })
        
        integrations = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            # Don't include actual credentials
            doc.pop("credentials", None)
            integrations.append(doc)
        
        return integrations


# Singleton
_token_vault: Optional[TokenVault] = None


def get_token_vault(db: AsyncIOMotorDatabase) -> TokenVault:
    """Get or create the token vault instance"""
    global _token_vault
    if _token_vault is None:
        _token_vault = TokenVault(db)
    return _token_vault
