"""
AUREM Commercial Platform - Customer Workspace Service
Multi-tenant isolation ensuring Customer A never sees Customer B's data

Features:
- Business ID tagging on all data
- Isolated conversation namespaces
- Per-customer AI context
- Usage tracking per workspace
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import logging
import secrets
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from .audit_service import AuditLogger, AuditAction, get_audit_logger

logger = logging.getLogger(__name__)


class SubscriptionPlan(str, Enum):
    """Available subscription plans"""
    STARTER = "starter"      # $49/mo - 500 AI messages
    PRO = "pro"              # $149/mo - 2500 AI messages
    ENTERPRISE = "enterprise"  # $399/mo - 10000 AI messages
    TRIAL = "trial"          # Free trial - 50 AI messages


class WorkspaceStatus(str, Enum):
    """Workspace status"""
    ACTIVE = "active"
    PAUSED = "paused"         # Payment issue
    SUSPENDED = "suspended"   # Compliance issue
    CANCELLED = "cancelled"


# Plan limits
PLAN_LIMITS = {
    SubscriptionPlan.TRIAL.value: {
        "ai_messages": 50,
        "users": 1,
        "channels": ["gmail"],
        "features": ["basic_ai"],
        "overage_rate": 0,  # No overage allowed
    },
    SubscriptionPlan.STARTER.value: {
        "ai_messages": 500,
        "users": 1,
        "channels": ["gmail", "whatsapp"],
        "features": ["basic_ai", "auto_reply"],
        "overage_rate": 0.08,
    },
    SubscriptionPlan.PRO.value: {
        "ai_messages": 2500,
        "users": 3,
        "channels": ["gmail", "whatsapp", "phone"],
        "features": ["basic_ai", "auto_reply", "actions", "api_access"],
        "overage_rate": 0.05,
    },
    SubscriptionPlan.ENTERPRISE.value: {
        "ai_messages": 10000,
        "users": -1,  # Unlimited
        "channels": ["gmail", "whatsapp", "phone", "sms"],
        "features": ["basic_ai", "auto_reply", "actions", "api_access", "custom_ai", "priority_support"],
        "overage_rate": 0.03,
    }
}


class CustomerWorkspace:
    """
    Manages customer workspaces with full isolation.
    """
    
    WORKSPACES_COLLECTION = "aurem_workspaces"
    USAGE_COLLECTION = "aurem_usage"
    CONTACTS_COLLECTION = "aurem_contacts"
    CONVERSATIONS_COLLECTION = "aurem_conversations"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.workspaces = db[self.WORKSPACES_COLLECTION]
        self.usage = db[self.USAGE_COLLECTION]
        self.contacts = db[self.CONTACTS_COLLECTION]
        self.conversations = db[self.CONVERSATIONS_COLLECTION]
        self.audit = get_audit_logger(db)
    
    async def ensure_indexes(self):
        """Create all required indexes - handles existing indexes gracefully"""
        async def safe_create_index(collection, keys, **kwargs):
            try:
                await collection.create_index(keys, **kwargs)
            except Exception:
                pass  # Index exists or conflict
        
        # Workspaces
        await safe_create_index(self.workspaces, "business_id", unique=True)
        await safe_create_index(self.workspaces, "owner_email")
        await safe_create_index(self.workspaces, "status")
        await safe_create_index(self.workspaces, "stripe_customer_id")
        
        # Usage (monthly tracking)
        await safe_create_index(self.usage, [("business_id", 1), ("billing_period", 1)], unique=True)
        
        # Contacts (per business)
        await safe_create_index(self.contacts, [("business_id", 1), ("contact_hash", 1)], unique=True)
        await safe_create_index(self.contacts, "business_id")
        
        # Conversations (per business)
        await self.conversations.create_index([
            ("business_id", 1),
            ("conversation_id", 1)
        ], unique=True)
        await self.conversations.create_index("business_id")
        await self.conversations.create_index([
            ("business_id", 1),
            ("last_message_at", -1)
        ])
        
        logger.info("[Workspace] Indexes created")
    
    def generate_business_id(self) -> str:
        """Generate a unique business ID"""
        return f"biz_{secrets.token_hex(8)}"
    
    async def create_workspace(
        self,
        owner_email: str,
        business_name: str,
        plan: SubscriptionPlan = SubscriptionPlan.TRIAL,
        owner_id: Optional[str] = None,
        business_type: Optional[str] = None,
        timezone: str = "America/Toronto",
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new customer workspace.
        
        Args:
            owner_email: Email of the business owner
            business_name: Name of the business
            plan: Subscription plan
            owner_id: User ID of owner
            business_type: Type of business (spa, auto, etc.)
            timezone: Business timezone
            ip_address: Request IP
            
        Returns:
            Created workspace document
        """
        
        business_id = self.generate_business_id()
        now = datetime.now(timezone.utc) if hasattr(timezone, 'utc') else datetime.utcnow()
        
        # Create workspace document
        workspace = {
            "business_id": business_id,
            "business_name": business_name,
            "business_type": business_type,
            "owner_email": owner_email.lower().strip(),
            "owner_id": owner_id,
            "timezone": timezone,
            "status": WorkspaceStatus.ACTIVE.value,
            
            # Subscription
            "plan": plan.value if isinstance(plan, SubscriptionPlan) else plan,
            "plan_started_at": now,
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            
            # Settings
            "settings": {
                "ai_mode": "auto",  # auto, manual, supervised
                "ai_personality": "professional",
                "working_hours": {
                    "enabled": False,
                    "start": "09:00",
                    "end": "18:00",
                    "days": [1, 2, 3, 4, 5]  # Mon-Fri
                },
                "auto_reply_delay_seconds": 5,
                "escalation_keywords": ["human", "manager", "speak to someone"],
                "language": "en"
            },
            
            # AI Context (per-business brain context)
            "ai_context": {
                "business_description": "",
                "services": [],
                "faq": [],
                "tone": "professional and friendly",
                "prohibited_topics": [],
                "custom_instructions": ""
            },
            
            # Timestamps
            "created_at": now,
            "updated_at": now,
            "last_activity_at": now
        }
        
        await self.workspaces.insert_one(workspace)
        
        # Initialize usage tracking for current period
        await self._init_usage_period(business_id)
        
        # Audit log
        await self.audit.log(
            action=AuditAction.ADMIN_ACTION,
            business_id=business_id,
            actor_id=owner_id,
            actor_type="user",
            resource_type="workspace",
            resource_id=business_id,
            details={
                "action": "workspace_created",
                "plan": workspace["plan"],
                "business_name": business_name
            },
            ip_address=ip_address,
            success=True
        )
        
        logger.info(f"[Workspace] Created workspace: {business_id} ({business_name})")
        
        workspace["_id"] = str(workspace.get("_id", ""))
        return workspace
    
    async def get_workspace(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Get workspace by business ID"""
        doc = await self.workspaces.find_one({"business_id": business_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    
    async def get_workspace_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get workspace by owner email"""
        doc = await self.workspaces.find_one({
            "owner_email": email.lower().strip()
        })
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    
    async def update_settings(
        self,
        business_id: str,
        settings: Dict[str, Any],
        actor_id: Optional[str] = None
    ) -> bool:
        """Update workspace settings"""
        result = await self.workspaces.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "settings": settings,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            await self.audit.log(
                action=AuditAction.SETTINGS_CHANGED,
                business_id=business_id,
                actor_id=actor_id,
                actor_type="user",
                resource_type="workspace",
                details={"updated_fields": list(settings.keys())},
                success=True
            )
            return True
        return False
    
    async def update_ai_context(
        self,
        business_id: str,
        ai_context: Dict[str, Any],
        actor_id: Optional[str] = None
    ) -> bool:
        """Update AI context for the business"""
        result = await self.workspaces.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "ai_context": ai_context,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    async def change_plan(
        self,
        business_id: str,
        new_plan: SubscriptionPlan,
        actor_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """Change subscription plan"""
        old_workspace = await self.get_workspace(business_id)
        old_plan = old_workspace.get("plan") if old_workspace else None
        
        result = await self.workspaces.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "plan": new_plan.value if isinstance(new_plan, SubscriptionPlan) else new_plan,
                    "plan_started_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            await self.audit.log(
                action=AuditAction.PLAN_CHANGED,
                business_id=business_id,
                actor_id=actor_id,
                actor_type="user",
                resource_type="workspace",
                details={
                    "old_plan": old_plan,
                    "new_plan": new_plan.value if isinstance(new_plan, SubscriptionPlan) else new_plan
                },
                ip_address=ip_address,
                success=True
            )
            return True
        return False
    
    async def pause_workspace(
        self,
        business_id: str,
        reason: str = "payment_issue",
        actor_id: Optional[str] = None
    ) -> bool:
        """Pause a workspace (e.g., for non-payment)"""
        result = await self.workspaces.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "status": WorkspaceStatus.PAUSED.value,
                    "paused_at": datetime.utcnow(),
                    "paused_reason": reason,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            await self.audit.log(
                action=AuditAction.ADMIN_ACTION,
                business_id=business_id,
                actor_id=actor_id or "system",
                actor_type="system",
                resource_type="workspace",
                details={
                    "action": "workspace_paused",
                    "reason": reason
                },
                success=True
            )
            logger.warning(f"[Workspace] Paused: {business_id} - {reason}")
            return True
        return False
    
    async def reactivate_workspace(
        self,
        business_id: str,
        actor_id: Optional[str] = None
    ) -> bool:
        """Reactivate a paused workspace"""
        result = await self.workspaces.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "status": WorkspaceStatus.ACTIVE.value,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "paused_at": "",
                    "paused_reason": ""
                }
            }
        )
        return result.modified_count > 0
    
    # ==================== USAGE TRACKING ====================
    
    async def _init_usage_period(self, business_id: str) -> Dict[str, Any]:
        """Initialize usage tracking for current billing period"""
        now = datetime.utcnow()
        period = now.strftime("%Y-%m")
        
        workspace = await self.get_workspace(business_id)
        plan = workspace.get("plan", SubscriptionPlan.TRIAL.value) if workspace else SubscriptionPlan.TRIAL.value
        plan_limits = PLAN_LIMITS.get(plan, PLAN_LIMITS[SubscriptionPlan.TRIAL.value])
        
        usage_doc = {
            "business_id": business_id,
            "billing_period": period,
            "plan": plan,
            "included_messages": plan_limits["ai_messages"],
            
            "usage": {
                "ai_messages": 0,
                "gmail_messages": 0,
                "whatsapp_messages": 0,
                "phone_minutes": 0,
                "actions_executed": 0
            },
            
            "quota_warning_sent": False,
            "quota_exceeded": False,
            "overage_messages": 0,
            "overage_cost": 0.0,
            
            "created_at": now,
            "updated_at": now
        }
        
        await self.usage.update_one(
            {"business_id": business_id, "billing_period": period},
            {"$setOnInsert": usage_doc},
            upsert=True
        )
        
        return usage_doc
    
    async def get_current_usage(self, business_id: str) -> Dict[str, Any]:
        """Get usage for current billing period"""
        period = datetime.utcnow().strftime("%Y-%m")
        
        doc = await self.usage.find_one({
            "business_id": business_id,
            "billing_period": period
        })
        
        if not doc:
            doc = await self._init_usage_period(business_id)
        
        if doc:
            doc["_id"] = str(doc.get("_id", ""))
            
            # Calculate remaining quota
            doc["quota_remaining"] = max(
                0, 
                doc.get("included_messages", 0) - doc.get("usage", {}).get("ai_messages", 0)
            )
        
        return doc
    
    async def increment_usage(
        self,
        business_id: str,
        usage_type: str = "ai_messages",
        count: int = 1
    ) -> Dict[str, Any]:
        """
        Increment usage counter.
        
        Args:
            business_id: The business
            usage_type: Type of usage (ai_messages, gmail_messages, etc.)
            count: Amount to increment
            
        Returns:
            Updated usage document
        """
        period = datetime.utcnow().strftime("%Y-%m")
        
        # Ensure period exists
        await self._init_usage_period(business_id)
        
        # Increment usage
        result = await self.usage.find_one_and_update(
            {"business_id": business_id, "billing_period": period},
            {
                "$inc": {f"usage.{usage_type}": count},
                "$set": {"updated_at": datetime.utcnow()}
            },
            return_document=True
        )
        
        if result:
            result["_id"] = str(result["_id"])
            
            # Check if quota exceeded
            ai_usage = result.get("usage", {}).get("ai_messages", 0)
            included = result.get("included_messages", 0)
            
            if ai_usage >= included and not result.get("quota_exceeded"):
                await self.usage.update_one(
                    {"_id": result["_id"]},
                    {"$set": {"quota_exceeded": True}}
                )
                logger.warning(f"[Workspace] Quota exceeded: {business_id}")
        
        return result
    
    async def check_quota(self, business_id: str) -> Dict[str, Any]:
        """
        Check if business has remaining quota.
        
        Returns:
            {
                "allowed": bool,
                "remaining": int,
                "overage_allowed": bool,
                "overage_rate": float
            }
        """
        usage = await self.get_current_usage(business_id)
        workspace = await self.get_workspace(business_id)
        
        if not usage or not workspace:
            return {"allowed": False, "remaining": 0, "reason": "workspace_not_found"}
        
        if workspace.get("status") != WorkspaceStatus.ACTIVE.value:
            return {"allowed": False, "remaining": 0, "reason": f"workspace_{workspace.get('status')}"}
        
        plan = workspace.get("plan", SubscriptionPlan.TRIAL.value)
        plan_limits = PLAN_LIMITS.get(plan, PLAN_LIMITS[SubscriptionPlan.TRIAL.value])
        
        ai_usage = usage.get("usage", {}).get("ai_messages", 0)
        included = usage.get("included_messages", 0)
        remaining = max(0, included - ai_usage)
        
        overage_allowed = plan_limits.get("overage_rate", 0) > 0
        
        return {
            "allowed": remaining > 0 or overage_allowed,
            "remaining": remaining,
            "overage_allowed": overage_allowed,
            "overage_rate": plan_limits.get("overage_rate", 0),
            "plan": plan
        }
    
    # ==================== AI CONTEXT ====================
    
    def build_system_prompt(self, workspace: Dict[str, Any]) -> str:
        """
        Build AI system prompt from workspace context.
        This ensures complete isolation between businesses.
        """
        ai_context = workspace.get("ai_context", {})
        settings = workspace.get("settings", {})
        
        prompt = f"""You are the AI assistant for {workspace.get('business_name', 'this business')}.

IMPORTANT: You ONLY have knowledge about {workspace.get('business_name')}. 
You must NEVER reference any other business, company, or external information.
If asked about something outside your knowledge, politely say you can only help with {workspace.get('business_name')}-related questions.

BUSINESS DESCRIPTION:
{ai_context.get('business_description', 'A professional business.')}

SERVICES OFFERED:
{', '.join(ai_context.get('services', ['General services']))}

TONE:
{ai_context.get('tone', 'Professional and friendly')}

FREQUENTLY ASKED QUESTIONS:
{self._format_faq(ai_context.get('faq', []))}

CUSTOM INSTRUCTIONS:
{ai_context.get('custom_instructions', 'None')}

PROHIBITED TOPICS (never discuss):
{', '.join(ai_context.get('prohibited_topics', ['Competitor information', 'Personal opinions on politics/religion']))}

LANGUAGE: Respond in {settings.get('language', 'English')}

Remember: You represent ONLY {workspace.get('business_name')}. Stay in character at all times."""
        
        return prompt
    
    def _format_faq(self, faq: List[Dict[str, str]]) -> str:
        """Format FAQ list for prompt"""
        if not faq:
            return "No specific FAQ provided."
        
        formatted = []
        for item in faq:
            q = item.get("question", "")
            a = item.get("answer", "")
            if q and a:
                formatted.append(f"Q: {q}\nA: {a}")
        
        return "\n\n".join(formatted) if formatted else "No specific FAQ provided."


# Singleton
_workspace_service: Optional[CustomerWorkspace] = None


def get_workspace_service(db: AsyncIOMotorDatabase) -> CustomerWorkspace:
    """Get or create the workspace service instance"""
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = CustomerWorkspace(db)
    return _workspace_service
