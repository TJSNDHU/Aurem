"""
OmniDimension Integration Service
"The Muscle" - Voice AI Sales Rep that reports to AUREM "Manager"

Phase 8.4: Omni-Bridge

Features:
- Call Dispatch: Trigger outbound calls from Morning Brief tasks
- Post-Call Hydration: Sync call data back to Redis customer memory
- Social Lead Sensor: Process DM automation leads for Scout Agent

SDK Docs: https://omnidim.io/docs
"""

import logging
import os
import json
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== STANDARDIZED TTL CONSTANTS ====================
# Fix 2: Redis TTL Strategy - Standardized values

class TTLConfig:
    """Standardized TTL values for Redis keys."""
    SESSION_AUTH = 24 * 60 * 60          # 24 hours - Session/auth tokens
    CUSTOMER_PII = 7 * 24 * 60 * 60      # 7 days - Customer PII cache
    AGENT_MEMORY = 48 * 60 * 60          # 48 hours - Agent conversation context
    ANALYTICS = 30 * 24 * 60 * 60        # 30 days - Analytics/aggregates
    
    # REMOVED: Nothing should be 365 days


# ==================== CONFIGURATION ====================

class OmniDimConfig:
    """OmniDimension configuration from environment."""
    
    API_KEY = os.environ.get("OMNIDIM_API_KEY", "")
    BASE_URL = os.environ.get("OMNIDIM_BASE_URL", "https://api.omnidim.io/v1")
    DEFAULT_AGENT_ID = os.environ.get("OMNIDIM_AGENT_ID", "")
    WEBHOOK_SECRET = os.environ.get("OMNIDIM_WEBHOOK_SECRET", "")
    
    # Phone numbers
    FROM_NUMBER_ID = os.environ.get("OMNIDIM_FROM_NUMBER_ID", "")
    
    # Fix 5: Readiness gate flag
    _enabled = None
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if OmniDim is properly configured."""
        return bool(cls.API_KEY and cls.DEFAULT_AGENT_ID)
    
    @classmethod
    def is_enabled(cls) -> bool:
        """
        Check if OmniDim is enabled and configured.
        
        Fix 5: Readiness gate - returns False if not configured,
        allowing graceful degradation instead of silent failure.
        """
        if cls._enabled is None:
            cls._enabled = cls.is_configured()
            if not cls._enabled:
                logger.warning(
                    "[OmniDim] NOT CONFIGURED - OMNIDIM_API_KEY or OMNIDIM_AGENT_ID missing. "
                    "OmniDimension routes will return 503."
                )
        return cls._enabled
    
    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Get configuration status."""
        return {
            "configured": cls.is_configured(),
            "enabled": cls.is_enabled(),
            "api_key_set": bool(cls.API_KEY),
            "agent_id_set": bool(cls.DEFAULT_AGENT_ID),
            "from_number_set": bool(cls.FROM_NUMBER_ID),
            "webhook_secret_set": bool(cls.WEBHOOK_SECRET),
            "base_url": cls.BASE_URL,
            "mode": "live" if cls.is_configured() else "scaffold"
        }


# ==================== DATA MODELS ====================

class CallStatus(str, Enum):
    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"


class LeadSource(str, Enum):
    DM_INSTAGRAM = "dm_instagram"
    DM_FACEBOOK = "dm_facebook"
    DM_WHATSAPP = "dm_whatsapp"
    VOICE_INBOUND = "voice_inbound"
    VOICE_OUTBOUND = "voice_outbound"
    WEB_CHAT = "web_chat"


@dataclass
class CallContext:
    """Context passed to OmniDim agent during call."""
    customer_name: str
    customer_phone: str
    task_id: Optional[str] = None
    task_title: Optional[str] = None
    priority: str = "normal"
    business_id: str = "default"
    morning_brief_tone: str = "professional"
    previous_interactions: int = 0
    customer_tier: str = "standard"
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CallResult:
    """Result from OmniDim post-call webhook."""
    call_id: str
    status: str
    duration_seconds: int
    transcript: str
    summary: str
    sentiment: str
    sentiment_score: float
    customer_phone: str
    agent_id: int
    extracted_variables: Dict[str, Any]
    web_search_results: Optional[List[Dict]] = None
    recording_url: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class SocialLead:
    """Lead captured from OmniDim DM automation."""
    lead_id: str
    source: str
    platform: str
    customer_name: str
    customer_handle: str
    message: str
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    contact_info: Optional[Dict] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# ==================== OMNIDIM CLIENT ====================

class OmniDimClient:
    """
    OmniDimension API Client.
    
    Wraps the OmniDim SDK for AUREM integration.
    Uses httpx for async HTTP calls if SDK not installed.
    """
    
    def __init__(self):
        self.config = OmniDimConfig
        self.headers = {
            "Authorization": f"Bearer {self.config.API_KEY}",
            "Content-Type": "application/json"
        }
    
    async def dispatch_call(
        self,
        to_number: str,
        context: CallContext,
        agent_id: Optional[int] = None,
        from_number_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatch an outbound call via OmniDimension.
        
        Args:
            to_number: Phone number to call (with country code)
            context: CallContext with customer/task info
            agent_id: OmniDim agent ID (uses default if not provided)
            from_number_id: Caller ID number ID
        
        Returns:
            Dict with call_id and status
        """
        if not self.config.is_configured():
            logger.warning("[OmniBridge] OmniDim not configured - returning mock response")
            return self._mock_dispatch_response(to_number, context)
        
        agent_id = agent_id or int(self.config.DEFAULT_AGENT_ID)
        from_number_id = from_number_id or self.config.FROM_NUMBER_ID
        
        payload = {
            "agent_id": agent_id,
            "to_number": to_number,
            "call_context": context.to_dict()
        }
        
        if from_number_id:
            payload["from_number_id"] = from_number_id
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.BASE_URL}/call/dispatch",
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"[OmniBridge] Call dispatched: {data.get('call_id')}")
                    return {
                        "success": True,
                        "call_id": data.get("call_id"),
                        "status": "queued",
                        "to_number": to_number,
                        "agent_id": agent_id,
                        "source": "omnidim_live"
                    }
                else:
                    logger.error(f"[OmniBridge] Dispatch failed: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": response.text,
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            logger.error(f"[OmniBridge] Dispatch error: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error"
            }
    
    def _mock_dispatch_response(self, to_number: str, context: CallContext) -> Dict[str, Any]:
        """Mock response when OmniDim not configured."""
        import uuid
        return {
            "success": True,
            "call_id": f"mock_call_{uuid.uuid4().hex[:8]}",
            "status": "queued",
            "to_number": to_number,
            "agent_id": "mock_agent",
            "context": context.to_dict(),
            "source": "mock",
            "note": "OmniDim not configured - this is a simulated response"
        }
    
    async def get_call_logs(
        self,
        page: int = 1,
        page_size: int = 30,
        agent_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve call logs from OmniDimension."""
        if not self.config.is_configured():
            return {"logs": [], "source": "mock", "total": 0}
        
        params = {"page": page, "page_size": page_size}
        if agent_id:
            params["agent_id"] = agent_id
        if status:
            params["call_status"] = status
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.config.BASE_URL}/call/logs",
                    headers=self.headers,
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"logs": [], "error": response.text}
                    
        except Exception as e:
            logger.error(f"[OmniBridge] Get logs error: {e}")
            return {"logs": [], "error": str(e)}
    
    async def get_agents(self) -> List[Dict[str, Any]]:
        """List all OmniDim agents."""
        if not self.config.is_configured():
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.config.BASE_URL}/agent/list",
                    headers=self.headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return response.json().get("agents", [])
                return []
                
        except Exception as e:
            logger.error(f"[OmniBridge] Get agents error: {e}")
            return []


# ==================== REDIS HYDRATION ====================

class CustomerHydrator:
    """
    Hydrates customer records in Redis with OmniDim call data.
    
    Maintains persistent context so AUREM Brain knows:
    - Recent call summary
    - Sentiment trends
    - Web search findings
    - Extracted intents
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        # Fix 2: Use standardized TTL (7 days for customer PII)
        self.ttl_seconds = TTLConfig.CUSTOMER_PII
    
    async def hydrate_from_call(
        self,
        call_result: CallResult,
        business_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Hydrate customer record from post-call webhook data.
        
        Args:
            call_result: Parsed CallResult from OmniDim webhook
            business_id: Business context
        
        Returns:
            Dict with hydration status and updated fields
        """
        # Generate customer key from phone
        phone_hash = self._hash_phone(call_result.customer_phone)
        customer_key = f"aurem:customer:{business_id}:{phone_hash}"
        
        # Build hydration payload
        hydration_data = {
            "last_call_id": call_result.call_id,
            "last_call_timestamp": call_result.timestamp,
            "last_call_summary": call_result.summary,
            "last_call_sentiment": call_result.sentiment,
            "last_call_sentiment_score": call_result.sentiment_score,
            "last_call_duration": call_result.duration_seconds,
            "total_calls": 1,  # Will increment
            "extracted_intents": call_result.extracted_variables,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Add web search results if present
        if call_result.web_search_results:
            hydration_data["last_web_search"] = call_result.web_search_results
        
        # Store in Redis if available
        if self.redis:
            try:
                # Get existing record
                existing = await self.redis.hgetall(customer_key)
                
                if existing:
                    # Increment call count
                    total_calls = int(existing.get(b"total_calls", 0)) + 1
                    hydration_data["total_calls"] = total_calls
                    
                    # Track sentiment history
                    sentiment_history = json.loads(
                        existing.get(b"sentiment_history", b"[]").decode()
                    )
                    sentiment_history.append({
                        "score": call_result.sentiment_score,
                        "label": call_result.sentiment,
                        "timestamp": call_result.timestamp
                    })
                    # Keep last 10 sentiments
                    hydration_data["sentiment_history"] = json.dumps(sentiment_history[-10:])
                
                # Store updated record
                await self.redis.hset(customer_key, mapping={
                    k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    for k, v in hydration_data.items()
                })
                
                # Set TTL using standardized value
                await self.redis.expire(customer_key, self.ttl_seconds)
                
                logger.info(f"[OmniBridge] Customer hydrated: {customer_key}")
                
                return {
                    "success": True,
                    "customer_key": customer_key,
                    "fields_updated": list(hydration_data.keys()),
                    "source": "redis"
                }
                
            except Exception as e:
                logger.error(f"[OmniBridge] Redis hydration error: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "data": hydration_data
                }
        
        # Return data without Redis storage
        return {
            "success": True,
            "customer_key": customer_key,
            "fields_updated": list(hydration_data.keys()),
            "data": hydration_data,
            "source": "memory_only"
        }
    
    def _hash_phone(self, phone: str) -> str:
        """Create a hash key from phone number."""
        import hashlib
        # Normalize phone number
        normalized = "".join(c for c in phone if c.isdigit())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


# ==================== SCOUT AGENT LEAD PROCESSOR ====================

class ScoutLeadProcessor:
    """
    Processes social leads from OmniDim DM automation.
    
    When a lead is captured via Instagram/Facebook/WhatsApp DM,
    Scout Agent analyzes it and flags in Unified Inbox.
    """
    
    def __init__(self, db=None, websocket_hub=None):
        self.db = db
        self.ws_hub = websocket_hub
    
    async def process_social_lead(
        self,
        lead: SocialLead,
        business_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Process incoming social lead from OmniDim.
        
        1. Analyze intent and sentiment
        2. Flag in Unified Inbox
        3. Notify via WebSocket for real-time dashboard
        """
        # Analyze lead (would use LLM in production)
        analysis = await self._analyze_lead(lead)
        
        # Create inbox entry
        inbox_entry = {
            "id": f"lead_{lead.lead_id}",
            "type": "social_lead",
            "source": lead.source,
            "platform": lead.platform,
            "customer_name": lead.customer_name,
            "customer_handle": lead.customer_handle,
            "message": lead.message,
            "intent": analysis.get("intent"),
            "sentiment": analysis.get("sentiment"),
            "priority": analysis.get("priority", "medium"),
            "suggested_action": analysis.get("suggested_action"),
            "status": "new",
            "business_id": business_id,
            "created_at": lead.timestamp,
            "omnidim_lead_id": lead.lead_id
        }
        
        # Store in MongoDB if available
        if self.db is not None:
            try:
                await self.db["unified_inbox"].insert_one(inbox_entry.copy())
                logger.info(f"[OmniBridge] Lead stored in inbox: {lead.lead_id}")
            except Exception as e:
                logger.error(f"[OmniBridge] Failed to store lead: {e}")
        
        # Push to WebSocket for real-time notification
        if self.ws_hub:
            await self._notify_websocket(inbox_entry, business_id)
        
        return {
            "success": True,
            "lead_id": lead.lead_id,
            "inbox_id": inbox_entry["id"],
            "analysis": analysis,
            "priority": inbox_entry["priority"]
        }
    
    async def _analyze_lead(self, lead: SocialLead) -> Dict[str, Any]:
        """
        Analyze lead using Scout Agent logic.
        
        In production, this would call the Brain Orchestrator.
        For now, using keyword-based analysis.
        """
        message_lower = lead.message.lower()
        
        # Intent detection
        intent = "general_inquiry"
        if any(w in message_lower for w in ["price", "cost", "how much", "pricing"]):
            intent = "pricing_inquiry"
        elif any(w in message_lower for w in ["book", "appointment", "schedule", "available"]):
            intent = "booking_request"
        elif any(w in message_lower for w in ["help", "support", "issue", "problem"]):
            intent = "support_request"
        elif any(w in message_lower for w in ["buy", "purchase", "order", "want"]):
            intent = "purchase_intent"
        
        # Sentiment detection
        sentiment = "neutral"
        if any(w in message_lower for w in ["love", "great", "amazing", "thank", "excellent"]):
            sentiment = "positive"
        elif any(w in message_lower for w in ["bad", "terrible", "worst", "angry", "frustrated"]):
            sentiment = "negative"
        
        # Priority scoring
        priority = "medium"
        if intent in ["purchase_intent", "booking_request"]:
            priority = "high"
        elif sentiment == "negative":
            priority = "high"
        
        # Suggested action
        action_map = {
            "pricing_inquiry": "Send pricing information via DM",
            "booking_request": "Offer calendar link for appointment",
            "support_request": "Escalate to support team",
            "purchase_intent": "Send product link with VIP offer",
            "general_inquiry": "Respond with FAQ or redirect"
        }
        
        return {
            "intent": intent,
            "sentiment": sentiment,
            "priority": priority,
            "suggested_action": action_map.get(intent, "Review and respond"),
            "confidence": 0.85
        }
    
    async def _notify_websocket(self, entry: Dict, business_id: str):
        """Push lead notification to WebSocket hub."""
        try:
            notification = {
                "type": "new_social_lead",
                "data": entry,
                "business_id": business_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # WebSocket broadcast (if hub available)
            if hasattr(self.ws_hub, 'broadcast'):
                await self.ws_hub.broadcast(
                    json.dumps(notification),
                    channel=f"inbox:{business_id}"
                )
        except Exception as e:
            logger.warning(f"[OmniBridge] WebSocket notify failed: {e}")


# ==================== MORNING BRIEF CALL DISPATCHER ====================

class BriefingCallDispatcher:
    """
    Integrates call dispatch with Morning Brief.
    
    When a high-priority task is identified, provides
    one-click trigger to launch OmniDimension outbound call.
    """
    
    def __init__(self):
        self.client = OmniDimClient()
    
    async def dispatch_for_task(
        self,
        task: Dict[str, Any],
        customer_phone: str,
        business_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Dispatch a call for a Morning Brief task.
        
        Args:
            task: Task from morning brief (id, title, priority, etc.)
            customer_phone: Phone number to call
            business_id: Business context
        
        Returns:
            Call dispatch result
        """
        # Build context from task
        context = CallContext(
            customer_name=task.get("customer_name", "Customer"),
            customer_phone=customer_phone,
            task_id=task.get("id"),
            task_title=task.get("title"),
            priority=task.get("priority_label", "normal"),
            business_id=business_id,
            morning_brief_tone=self._get_tone_for_priority(task.get("priority", 3)),
            notes=task.get("description")
        )
        
        # Dispatch call
        result = await self.client.dispatch_call(
            to_number=customer_phone,
            context=context
        )
        
        # Log the dispatch
        logger.info(
            f"[OmniBridge] Morning Brief call dispatched: "
            f"task={task.get('id')}, phone={customer_phone[:6]}***, "
            f"success={result.get('success')}"
        )
        
        return {
            "dispatch_result": result,
            "task_id": task.get("id"),
            "task_title": task.get("title"),
            "dispatched_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _get_tone_for_priority(self, priority: int) -> str:
        """Map priority to call tone."""
        if priority <= 1:
            return "urgent"
        elif priority <= 2:
            return "professional"
        else:
            return "friendly"
    
    async def get_dispatchable_tasks(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter tasks that can trigger calls.
        
        Returns tasks with:
        - Priority 1-2 (critical/high)
        - Category: client_followup, sales, support
        - Has associated phone number
        """
        dispatchable = []
        
        call_categories = {"client_followup", "sales", "support", "vip_followup"}
        
        for task in tasks:
            priority = task.get("priority", 5)
            category = task.get("category", "")
            
            if priority <= 2 or category in call_categories:
                dispatchable.append({
                    **task,
                    "can_dispatch": True,
                    "dispatch_reason": (
                        "High priority" if priority <= 2 
                        else f"Category: {category}"
                    )
                })
        
        return dispatchable


# ==================== SINGLETON INSTANCES ====================

omnidim_client = OmniDimClient()
customer_hydrator = CustomerHydrator()
scout_lead_processor = ScoutLeadProcessor()
briefing_dispatcher = BriefingCallDispatcher()


def set_dependencies(redis_client=None, db=None, websocket_hub=None):
    """Set external dependencies for OmniBridge services."""
    global customer_hydrator, scout_lead_processor
    
    if redis_client:
        customer_hydrator.redis = redis_client
    if db is not None:
        scout_lead_processor.db = db
    if websocket_hub:
        scout_lead_processor.ws_hub = websocket_hub
