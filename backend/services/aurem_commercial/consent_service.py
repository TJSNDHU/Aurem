"""
AUREM Commercial Platform - Consent Tracking Service
PIPEDA Compliant consent management

Tracks:
- Business owner ToS acceptance
- End-user AI interaction consent
- Data processing consent
- Marketing consent
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

from .audit_service import AuditLogger, AuditAction, get_audit_logger

logger = logging.getLogger(__name__)


class ConsentType(str, Enum):
    """Types of consent we track"""
    TOS_ACCEPTANCE = "tos_acceptance"              # Terms of Service
    PRIVACY_POLICY = "privacy_policy"              # Privacy Policy
    AI_DATA_PROCESSING = "ai_data_processing"      # AI processes their data
    MARKETING_COMMUNICATIONS = "marketing"          # Marketing emails
    END_USER_AI_CONSENT = "end_user_ai"            # End-user agrees to AI


class ConsentStatus(str, Enum):
    """Status of consent"""
    GRANTED = "granted"
    REVOKED = "revoked"
    PENDING = "pending"


class ConsentTracker:
    """
    Track consent for PIPEDA compliance.
    All consent records are immutable - revocation creates new record.
    """
    
    COLLECTION_NAME = "aurem_consent_records"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION_NAME]
        self.audit = get_audit_logger(db)
    
    async def ensure_indexes(self):
        """Create indexes - handles existing indexes gracefully"""
        indexes = [
            "business_id",
            "consent_type",
            [("business_id", 1), ("consent_type", 1), ("consented_at", -1)],
            "contact_id"
        ]
        for idx in indexes:
            try:
                await self.collection.create_index(idx)
            except Exception:
                pass  # Index exists or conflict
        logger.info("[Consent] Indexes verified")
    
    async def record_consent(
        self,
        business_id: str,
        consent_type: ConsentType,
        granted: bool = True,
        contact_id: Optional[str] = None,  # For end-user consent
        consent_text_version: str = "v1.0",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a consent grant or revocation.
        
        Args:
            business_id: The business
            consent_type: Type of consent
            granted: True for grant, False for revoke
            contact_id: For end-user consent, the contact's ID
            consent_text_version: Version of the consent text shown
            ip_address: IP address of the user
            user_agent: Browser/client info
            metadata: Additional context
            
        Returns:
            Consent record ID
        """
        
        now = datetime.now(timezone.utc)
        
        consent_record = {
            "business_id": business_id,
            "consent_type": consent_type.value if isinstance(consent_type, ConsentType) else consent_type,
            "status": ConsentStatus.GRANTED.value if granted else ConsentStatus.REVOKED.value,
            "contact_id": contact_id,
            "consent_text_version": consent_text_version,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "metadata": metadata or {},
            "consented_at": now,
            # Immutability marker
            "_immutable": True
        }
        
        result = await self.collection.insert_one(consent_record)
        
        # Audit log
        await self.audit.log(
            action=AuditAction.CONSENT_GRANTED if granted else AuditAction.CONSENT_REVOKED,
            business_id=business_id,
            actor_id=contact_id or "business_owner",
            actor_type="user",
            resource_type="consent",
            resource_id=str(result.inserted_id),
            details={
                "consent_type": consent_record["consent_type"],
                "consent_text_version": consent_text_version
            },
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )
        
        logger.info(
            f"[Consent] {'Granted' if granted else 'Revoked'}: "
            f"{consent_type} for {business_id}"
        )
        
        return str(result.inserted_id)
    
    async def has_consent(
        self,
        business_id: str,
        consent_type: ConsentType,
        contact_id: Optional[str] = None
    ) -> bool:
        """
        Check if valid consent exists.
        
        Args:
            business_id: The business
            consent_type: Type of consent to check
            contact_id: For end-user consent
            
        Returns:
            True if consent is currently granted
        """
        
        query = {
            "business_id": business_id,
            "consent_type": consent_type.value if isinstance(consent_type, ConsentType) else consent_type
        }
        
        if contact_id:
            query["contact_id"] = contact_id
        
        # Get most recent consent record
        cursor = self.collection.find(query).sort("consented_at", -1).limit(1)
        
        async for record in cursor:
            return record.get("status") == ConsentStatus.GRANTED.value
        
        return False
    
    async def get_consent_history(
        self,
        business_id: str,
        consent_type: Optional[ConsentType] = None,
        contact_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get consent history for audit purposes.
        """
        
        query = {"business_id": business_id}
        
        if consent_type:
            query["consent_type"] = consent_type.value if isinstance(consent_type, ConsentType) else consent_type
        
        if contact_id:
            query["contact_id"] = contact_id
        
        cursor = self.collection.find(query).sort("consented_at", -1)
        
        records = []
        async for record in cursor:
            record["_id"] = str(record["_id"])
            records.append(record)
        
        return records
    
    async def record_business_signup_consent(
        self,
        business_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Record all required consents for business signup.
        Called when a new business signs up.
        """
        
        required_consents = [
            ConsentType.TOS_ACCEPTANCE,
            ConsentType.PRIVACY_POLICY,
            ConsentType.AI_DATA_PROCESSING
        ]
        
        for consent_type in required_consents:
            await self.record_consent(
                business_id=business_id,
                consent_type=consent_type,
                granted=True,
                consent_text_version="v1.0",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"source": "signup_flow"}
            )
    
    async def record_end_user_consent(
        self,
        business_id: str,
        contact_id: str,
        contact_identifier: str,  # Phone or email
        channel: str,  # whatsapp, email, etc.
        ip_address: Optional[str] = None
    ):
        """
        Record end-user consent for AI interaction.
        Called when an end-user first interacts with the AI.
        """
        
        await self.record_consent(
            business_id=business_id,
            consent_type=ConsentType.END_USER_AI_CONSENT,
            granted=True,
            contact_id=contact_id,
            consent_text_version="v1.0",
            ip_address=ip_address,
            metadata={
                "contact_identifier": contact_identifier[-4:],  # Last 4 chars only
                "channel": channel,
                "consent_method": "implicit_first_message"
            }
        )
    
    async def check_required_consents(
        self,
        business_id: str
    ) -> Dict[str, bool]:
        """
        Check if business has all required consents.
        """
        
        required = [
            ConsentType.TOS_ACCEPTANCE,
            ConsentType.PRIVACY_POLICY,
            ConsentType.AI_DATA_PROCESSING
        ]
        
        results = {}
        all_granted = True
        
        for consent_type in required:
            has = await self.has_consent(business_id, consent_type)
            results[consent_type.value] = has
            if not has:
                all_granted = False
        
        results["all_granted"] = all_granted
        return results


# Singleton
_consent_tracker: Optional[ConsentTracker] = None


def get_consent_tracker(db: AsyncIOMotorDatabase) -> ConsentTracker:
    """Get or create the consent tracker instance"""
    global _consent_tracker
    if _consent_tracker is None:
        _consent_tracker = ConsentTracker(db)
    return _consent_tracker
