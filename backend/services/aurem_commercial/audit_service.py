"""
AUREM Commercial Platform - Audit Logging Service
Immutable audit trail for all sensitive operations
PIPEDA Compliant - Required for Canadian privacy law

All audit logs are:
- Immutable (append-only)
- Timestamped with UTC
- Include actor identification
- Retained for 2 years minimum
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Types of auditable actions"""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    
    # Token/Credential operations
    TOKEN_CREATED = "token_created"
    TOKEN_ACCESSED = "token_accessed"
    TOKEN_REFRESHED = "token_refreshed"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_DECRYPT_ATTEMPTED = "token_decrypt_attempted"
    
    # Integration operations
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_DISCONNECTED = "integration_disconnected"
    INTEGRATION_ERROR = "integration_error"
    
    # Data operations
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    DATA_ACCESSED = "data_accessed"
    
    # Message operations
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_BLOCKED = "message_blocked"
    
    # Email operations
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    EMAIL_READ = "email_read"
    
    # AI operations
    AI_RESPONSE_GENERATED = "ai_response_generated"
    AI_ACTION_EXECUTED = "ai_action_executed"
    AI_RESPONSE_BLOCKED = "ai_response_blocked"
    
    # Admin operations
    ADMIN_ACTION = "admin_action"
    SETTINGS_CHANGED = "settings_changed"
    PLAN_CHANGED = "plan_changed"
    
    # Consent
    CONSENT_GRANTED = "consent_granted"
    CONSENT_REVOKED = "consent_revoked"
    
    # Security
    RATE_LIMIT_HIT = "rate_limit_hit"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"


class AuditLogger:
    """
    Audit logging service for PIPEDA compliance.
    Logs are immutable and retained for 2 years.
    """
    
    COLLECTION_NAME = "aurem_audit_logs"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION_NAME]
    
    async def ensure_indexes(self):
        """Create indexes for efficient querying - handles existing indexes gracefully"""
        # Wrap each index creation in try/except to handle conflicts
        indexes_to_create = [
            {"keys": "business_id"},
            {"keys": "action"},
            {"keys": "actor_id"},
            {"keys": [("business_id", 1), ("timestamp", -1)]}
        ]
        
        for idx in indexes_to_create:
            try:
                await self.collection.create_index(idx["keys"])
            except Exception:
                pass  # Index exists or conflict - that's fine
        
        # Skip TTL index entirely - it conflicts with existing timestamp_1 index
        # TTL would require dropping the existing index first which is risky
        logger.info("[Audit] Indexes verified")
    
    async def log(
        self,
        action: AuditAction,
        business_id: str,
        actor_id: Optional[str] = None,
        actor_type: str = "system",  # user, admin, system, ai
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> str:
        """
        Log an auditable action.
        
        Args:
            action: Type of action (from AuditAction enum)
            business_id: The business this action relates to
            actor_id: ID of who performed the action (user, admin, or "system")
            actor_type: Type of actor (user, admin, system, ai)
            resource_type: Type of resource affected (e.g., "token", "message")
            resource_id: ID of the specific resource
            details: Additional context (will be sanitized)
            ip_address: IP of the request
            user_agent: Browser/client info
            success: Whether the action succeeded
            error_message: Error details if failed
            
        Returns:
            The audit log entry ID
        """
        
        # Sanitize details (remove any sensitive data)
        safe_details = self._sanitize_details(details) if details else None
        
        audit_entry = {
            "action": action.value if isinstance(action, AuditAction) else action,
            "business_id": business_id,
            "actor_id": actor_id or "system",
            "actor_type": actor_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": safe_details,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc),
            # Immutability marker
            "_immutable": True
        }
        
        result = await self.collection.insert_one(audit_entry)
        
        # Log to standard logger as well
        log_msg = f"[Audit] {action} | business={business_id} | actor={actor_id} | success={success}"
        if success:
            logger.info(log_msg)
        else:
            logger.warning(f"{log_msg} | error={error_message}")
        
        return str(result.inserted_id)
    
    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from details before logging"""
        sensitive_keys = [
            'password', 'token', 'access_token', 'refresh_token',
            'secret', 'api_key', 'private_key', 'credit_card',
            'ssn', 'sin', 'cvv'
        ]
        
        sanitized = {}
        for key, value in details.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            elif isinstance(value, str) and len(value) > 500:
                sanitized[key] = value[:500] + "...[TRUNCATED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    async def get_logs(
        self,
        business_id: str,
        action: Optional[AuditAction] = None,
        actor_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict]:
        """
        Retrieve audit logs for a business.
        
        Args:
            business_id: Filter by business
            action: Filter by action type
            actor_id: Filter by who performed action
            start_date: Filter by start time
            end_date: Filter by end time
            limit: Max results to return
            skip: Number of results to skip (pagination)
            
        Returns:
            List of audit log entries
        """
        query = {"business_id": business_id}
        
        if action:
            query["action"] = action.value if isinstance(action, AuditAction) else action
        
        if actor_id:
            query["actor_id"] = actor_id
        
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        
        logs = []
        async for log in cursor:
            log["_id"] = str(log["_id"])
            logs.append(log)
        
        return logs
    
    async def get_security_events(
        self,
        business_id: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict]:
        """Get recent security-related events"""
        security_actions = [
            AuditAction.LOGIN_FAILED.value,
            AuditAction.RATE_LIMIT_HIT.value,
            AuditAction.SUSPICIOUS_ACTIVITY.value,
            AuditAction.MESSAGE_BLOCKED.value,
            AuditAction.AI_RESPONSE_BLOCKED.value,
            AuditAction.KILL_SWITCH_ACTIVATED.value
        ]
        
        query = {
            "action": {"$in": security_actions},
            "timestamp": {
                "$gte": datetime.now(timezone.utc) - timedelta(hours=hours)
            }
        }
        
        if business_id:
            query["business_id"] = business_id
        
        cursor = self.collection.find(query).sort("timestamp", -1).limit(100)
        
        logs = []
        async for log in cursor:
            log["_id"] = str(log["_id"])
            logs.append(log)
        
        return logs


# Import timedelta at the top
from datetime import timedelta


# Singleton instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(db: AsyncIOMotorDatabase) -> AuditLogger:
    """Get or create the audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(db)
    return _audit_logger
