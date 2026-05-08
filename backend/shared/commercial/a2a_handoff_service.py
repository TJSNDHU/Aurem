"""
AUREM A2A (Agent-to-Agent) Handoff Service
"The Hiring Protocol" - Enables agents to delegate tasks to specialists

Phase 8.4: A2A Skeleton

Architecture:
┌─────────────────────────────────────────────────────────────────────┐
│                    A2A HANDOFF PROTOCOL                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────────┐                      ┌─────────────────┐     │
│   │  SKINCARE       │                      │  FINANCE        │     │
│   │  AGENT          │──── "Hire" ─────────▶│  AGENT          │     │
│   │                 │                      │                 │     │
│   │  "Customer needs│                      │  "Generate      │     │
│   │   payment link" │◀─── Result ──────────│   Stripe link"  │     │
│   └─────────────────┘                      └─────────────────┘     │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    HANDOFF TYPES                             │  │
│   │  ──────────────────────────────────────────────────────────  │  │
│   │  1. DELEGATE    - "Do this for me" (async, returns result)   │  │
│   │  2. TRANSFER    - "Take over" (sync, full context handoff)   │  │
│   │  3. CONSULT     - "Advise me" (sync, returns recommendation) │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Use Cases:
- Sales Agent needs payment → Delegates to Finance Agent
- Support call becomes sales → Transfers to Sales Agent
- Auto Agent needs pricing → Consults Finance Agent
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


# ==================== A2A PROTOCOL TYPES ====================

class HandoffType(str, Enum):
    """Types of agent-to-agent handoffs."""
    DELEGATE = "delegate"    # Async task delegation
    TRANSFER = "transfer"    # Full context transfer
    CONSULT = "consult"      # Advisory request


class HandoffStatus(str, Enum):
    """Status of a handoff request."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HandoffPriority(str, Enum):
    """Priority levels for handoffs."""
    CRITICAL = "critical"    # Immediate, interrupt current task
    HIGH = "high"            # Next in queue
    NORMAL = "normal"        # Standard queue
    LOW = "low"              # Background task


@dataclass
class HandoffRequest:
    """
    A2A Handoff Request.
    
    Represents a request from one agent to another for task execution.
    """
    request_id: str = field(default_factory=lambda: f"a2a_{uuid.uuid4().hex[:12]}")
    
    # Source agent
    from_agent: str = ""
    from_business_id: str = ""
    
    # Target agent
    to_agent: str = ""
    to_business_id: str = ""
    
    # Task details
    task: str = ""
    task_type: str = ""  # payment, booking, email, research, etc.
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Handoff config
    handoff_type: HandoffType = HandoffType.DELEGATE
    priority: HandoffPriority = HandoffPriority.NORMAL
    timeout_ms: int = 30000  # 30 second default
    
    # Context for the receiving agent
    context: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict] = field(default_factory=list)
    customer_info: Dict[str, Any] = field(default_factory=dict)
    
    # Callback
    callback_url: Optional[str] = None
    callback_method: str = "POST"
    
    # Metadata
    status: HandoffStatus = HandoffStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["handoff_type"] = self.handoff_type.value
        data["priority"] = self.priority.value
        data["status"] = self.status.value
        return data


@dataclass
class HandoffResult:
    """Result from an A2A handoff execution."""
    request_id: str
    status: HandoffStatus
    from_agent: str
    to_agent: str
    
    # Result data
    success: bool = False
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # Execution metrics
    execution_time_ms: int = 0
    
    # Timestamps
    started_at: Optional[str] = None
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


# ==================== TASK HANDLERS ====================

class A2ATaskRegistry:
    """
    Registry of tasks that can be delegated via A2A.
    
    Each task type has a handler function that executes the work.
    """
    
    def __init__(self):
        self._handlers: Dict[str, Callable[[Dict], Awaitable[Dict]]] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register built-in task handlers."""
        
        # Payment tasks
        self.register("create_payment_link", self._handle_payment_link)
        self.register("create_invoice", self._handle_invoice)
        self.register("check_payment_status", self._handle_payment_status)
        
        # Booking tasks
        self.register("book_appointment", self._handle_booking)
        self.register("check_availability", self._handle_availability)
        
        # Communication tasks
        self.register("send_email", self._handle_email)
        self.register("send_sms", self._handle_sms)
        
        # Research tasks
        self.register("web_search", self._handle_web_search)
        self.register("lookup_customer", self._handle_customer_lookup)
    
    def register(self, task_type: str, handler: Callable[[Dict], Awaitable[Dict]]):
        """Register a task handler."""
        self._handlers[task_type] = handler
        logger.info(f"[A2A] Registered handler for task: {task_type}")
    
    async def execute(self, task_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task via its registered handler."""
        handler = self._handlers.get(task_type)
        if not handler:
            return {"success": False, "error": f"Unknown task type: {task_type}"}
        
        try:
            return await handler(params)
        except Exception as e:
            logger.error(f"[A2A] Task execution error: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== DEFAULT HANDLERS ====================
    
    async def _handle_payment_link(self, params: Dict) -> Dict:
        """Create a Stripe payment link."""
        # In production, this would call the Action Engine
        amount = params.get("amount", 0)
        description = params.get("description", "Payment")
        
        # Mock response (would use Stripe in production)
        return {
            "success": True,
            "payment_link": f"https://pay.stripe.com/c/pay/{uuid.uuid4().hex[:8]}",
            "amount": amount,
            "currency": params.get("currency", "CAD"),
            "description": description,
            "customer_email": params.get("customer_email"),
            "expires_at": "2026-04-09T23:59:59Z"
        }
    
    async def _handle_invoice(self, params: Dict) -> Dict:
        """Create an invoice."""
        return {
            "success": True,
            "invoice_id": f"inv_{uuid.uuid4().hex[:8]}",
            "amount": params.get("amount", 0),
            "customer_email": params.get("customer_email"),
            "status": "draft"
        }
    
    async def _handle_payment_status(self, params: Dict) -> Dict:
        """Check payment status."""
        return {
            "success": True,
            "payment_id": params.get("payment_id"),
            "status": "paid",
            "amount": params.get("amount", 0)
        }
    
    async def _handle_booking(self, params: Dict) -> Dict:
        """Book an appointment."""
        return {
            "success": True,
            "booking_id": f"appt_{uuid.uuid4().hex[:8]}",
            "datetime": params.get("datetime"),
            "service": params.get("service"),
            "confirmation_sent": True
        }
    
    async def _handle_availability(self, params: Dict) -> Dict:
        """Check calendar availability."""
        return {
            "success": True,
            "available_slots": [
                "2026-04-03T10:00:00",
                "2026-04-03T14:00:00",
                "2026-04-04T09:00:00"
            ]
        }
    
    async def _handle_email(self, params: Dict) -> Dict:
        """Send an email."""
        return {
            "success": True,
            "message_id": f"msg_{uuid.uuid4().hex[:8]}",
            "to": params.get("to"),
            "subject": params.get("subject"),
            "status": "sent"
        }
    
    async def _handle_sms(self, params: Dict) -> Dict:
        """Send an SMS."""
        return {
            "success": True,
            "message_id": f"sms_{uuid.uuid4().hex[:8]}",
            "to": params.get("to"),
            "status": "delivered"
        }
    
    async def _handle_web_search(self, params: Dict) -> Dict:
        """Perform web search via Agent-Reach."""
        return {
            "success": True,
            "query": params.get("query"),
            "results": [
                {"title": "Result 1", "snippet": "..."},
                {"title": "Result 2", "snippet": "..."}
            ]
        }
    
    async def _handle_customer_lookup(self, params: Dict) -> Dict:
        """Look up customer information."""
        return {
            "success": True,
            "customer_id": params.get("customer_id"),
            "found": True,
            "tier": "vip",
            "lifetime_value": 2500.00
        }


# ==================== A2A HANDOFF SERVICE ====================

class A2AHandoffService:
    """
    The A2A Handoff Orchestrator.
    
    Manages the lifecycle of agent-to-agent task delegation,
    from request to execution to result delivery.
    """
    
    def __init__(self, db=None):
        self.db = db
        self.task_registry = A2ATaskRegistry()
        self._pending_requests: Dict[str, HandoffRequest] = {}
        self._callbacks: Dict[str, Callable] = {}
    
    async def create_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        task_type: str,
        params: Dict[str, Any],
        handoff_type: HandoffType = HandoffType.DELEGATE,
        priority: HandoffPriority = HandoffPriority.NORMAL,
        context: Dict[str, Any] = None,
        customer_info: Dict[str, Any] = None,
        conversation_history: List[Dict] = None,
        from_business_id: str = "",
        to_business_id: str = "",
        callback_url: Optional[str] = None
    ) -> HandoffRequest:
        """
        Create a new A2A handoff request.
        
        Example:
            handoff = await service.create_handoff(
                from_agent="reroots_skincare",
                to_agent="finance_agent",
                task="create_payment_link",
                task_type="payment",
                params={"amount": 299.00, "description": "PDRN Treatment"},
                handoff_type=HandoffType.DELEGATE
            )
        """
        request = HandoffRequest(
            from_agent=from_agent,
            from_business_id=from_business_id,
            to_agent=to_agent,
            to_business_id=to_business_id,
            task=task,
            task_type=task_type,
            params=params,
            handoff_type=handoff_type,
            priority=priority,
            context=context or {},
            customer_info=customer_info or {},
            conversation_history=conversation_history or [],
            callback_url=callback_url
        )
        
        # Store pending request
        self._pending_requests[request.request_id] = request
        
        # Log to database
        if self.db is not None:
            await self.db["a2a_handoffs"].insert_one(request.to_dict())
        
        logger.info(
            f"[A2A] Handoff created: {request.request_id} "
            f"({from_agent} → {to_agent}, task={task_type})"
        )
        
        return request
    
    async def execute_handoff(self, request: HandoffRequest) -> HandoffResult:
        """
        Execute an A2A handoff request.
        
        Routes to the appropriate task handler and returns the result.
        """
        start_time = datetime.now(timezone.utc)
        request.status = HandoffStatus.IN_PROGRESS
        
        try:
            # Execute task via registry
            task_result = await self.task_registry.execute(
                request.task_type,
                {
                    **request.params,
                    "context": request.context,
                    "customer_info": request.customer_info
                }
            )
            
            # Build result
            end_time = datetime.now(timezone.utc)
            execution_ms = int((end_time - start_time).total_seconds() * 1000)
            
            if task_result.get("success"):
                result = HandoffResult(
                    request_id=request.request_id,
                    status=HandoffStatus.COMPLETED,
                    from_agent=request.from_agent,
                    to_agent=request.to_agent,
                    success=True,
                    result=task_result,
                    execution_time_ms=execution_ms,
                    started_at=start_time.isoformat()
                )
            else:
                result = HandoffResult(
                    request_id=request.request_id,
                    status=HandoffStatus.FAILED,
                    from_agent=request.from_agent,
                    to_agent=request.to_agent,
                    success=False,
                    error=task_result.get("error", "Unknown error"),
                    execution_time_ms=execution_ms,
                    started_at=start_time.isoformat()
                )
            
            # Update request status
            request.status = result.status
            request.completed_at = result.completed_at
            
            # Update database
            if self.db is not None:
                await self.db["a2a_handoffs"].update_one(
                    {"request_id": request.request_id},
                    {"$set": {
                        "status": result.status.value,
                        "completed_at": result.completed_at,
                        "result": result.to_dict()
                    }}
                )
            
            # Execute callback if specified
            if request.callback_url:
                await self._send_callback(request.callback_url, result)
            
            # Clean up pending
            self._pending_requests.pop(request.request_id, None)
            
            logger.info(
                f"[A2A] Handoff completed: {request.request_id} "
                f"(success={result.success}, time={execution_ms}ms)"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[A2A] Handoff execution error: {e}")
            
            result = HandoffResult(
                request_id=request.request_id,
                status=HandoffStatus.FAILED,
                from_agent=request.from_agent,
                to_agent=request.to_agent,
                success=False,
                error=str(e)
            )
            
            request.status = HandoffStatus.FAILED
            
            return result
    
    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        task_type: str,
        params: Dict[str, Any],
        **kwargs
    ) -> HandoffResult:
        """
        Convenience method: Create and execute a DELEGATE handoff.
        
        Used when one agent needs another to perform a task and return the result.
        
        Example:
            result = await a2a.delegate(
                from_agent="reroots_skincare",
                to_agent="finance_agent",
                task_type="create_payment_link",
                params={"amount": 299.00}
            )
            payment_url = result.result["payment_link"]
        """
        request = await self.create_handoff(
            from_agent=from_agent,
            to_agent=to_agent,
            task=f"Delegate {task_type}",
            task_type=task_type,
            params=params,
            handoff_type=HandoffType.DELEGATE,
            **kwargs
        )
        
        return await self.execute_handoff(request)
    
    async def transfer(
        self,
        from_agent: str,
        to_agent: str,
        context: Dict[str, Any],
        conversation_history: List[Dict],
        customer_info: Dict[str, Any],
        reason: str = "Context transfer",
        **kwargs
    ) -> HandoffResult:
        """
        Convenience method: Create and execute a TRANSFER handoff.
        
        Used when an agent needs to hand off the entire conversation
        to a specialist (e.g., sales → support).
        
        Example:
            result = await a2a.transfer(
                from_agent="skincare_standard",
                to_agent="skincare_vip",
                context={"current_topic": "PDRN pricing"},
                conversation_history=messages,
                customer_info={"tier": "vip"},
                reason="Customer identified as VIP"
            )
        """
        request = await self.create_handoff(
            from_agent=from_agent,
            to_agent=to_agent,
            task=reason,
            task_type="transfer",
            params={"reason": reason},
            handoff_type=HandoffType.TRANSFER,
            context=context,
            conversation_history=conversation_history,
            customer_info=customer_info,
            **kwargs
        )
        
        # For transfers, we just log the handoff - the actual
        # conversation routing happens at the platform level
        request.status = HandoffStatus.COMPLETED
        
        result = HandoffResult(
            request_id=request.request_id,
            status=HandoffStatus.COMPLETED,
            from_agent=from_agent,
            to_agent=to_agent,
            success=True,
            result={
                "transfer_type": "full_context",
                "to_agent": to_agent,
                "context_preserved": True,
                "history_length": len(conversation_history)
            }
        )
        
        if self.db is not None:
            await self.db["a2a_handoffs"].update_one(
                {"request_id": request.request_id},
                {"$set": {"status": "completed", "result": result.to_dict()}}
            )
        
        return result
    
    async def consult(
        self,
        from_agent: str,
        to_agent: str,
        question: str,
        context: Dict[str, Any] = None,
        **kwargs
    ) -> HandoffResult:
        """
        Convenience method: Create and execute a CONSULT handoff.
        
        Used when an agent needs advice from a specialist without
        transferring the conversation.
        
        Example:
            result = await a2a.consult(
                from_agent="auto_advisor",
                to_agent="finance_agent",
                question="What's the financing rate for a $5000 repair?",
                context={"vehicle": "2018 GMC Yukon"}
            )
            recommendation = result.result["recommendation"]
        """
        request = await self.create_handoff(
            from_agent=from_agent,
            to_agent=to_agent,
            task=question,
            task_type="consult",
            params={"question": question},
            handoff_type=HandoffType.CONSULT,
            context=context or {},
            **kwargs
        )
        
        # For consultations, we return an advisory response
        result = HandoffResult(
            request_id=request.request_id,
            status=HandoffStatus.COMPLETED,
            from_agent=from_agent,
            to_agent=to_agent,
            success=True,
            result={
                "consultation_type": "advisory",
                "question": question,
                "recommendation": f"Advisory response for: {question}",
                "confidence": 0.85
            }
        )
        
        request.status = HandoffStatus.COMPLETED
        
        if self.db is not None:
            await self.db["a2a_handoffs"].update_one(
                {"request_id": request.request_id},
                {"$set": {"status": "completed", "result": result.to_dict()}}
            )
        
        return result
    
    async def _send_callback(self, url: str, result: HandoffResult):
        """Send callback with handoff result."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(url, json=result.to_dict(), timeout=10)
        except Exception as e:
            logger.warning(f"[A2A] Callback failed: {e}")
    
    async def get_handoff_history(
        self,
        business_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get handoff history from database."""
        if self.db is None:
            return []
        
        query = {}
        if business_id:
            query["$or"] = [
                {"from_business_id": business_id},
                {"to_business_id": business_id}
            ]
        if agent_id:
            query["$or"] = [
                {"from_agent": agent_id},
                {"to_agent": agent_id}
            ]
        
        cursor = self.db["a2a_handoffs"].find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(limit)


# ==================== SINGLETON ====================

_a2a_service: Optional[A2AHandoffService] = None


def get_a2a_service(db=None) -> A2AHandoffService:
    """Get or create the A2A Handoff Service singleton."""
    global _a2a_service
    if _a2a_service is None:
        _a2a_service = A2AHandoffService(db)
    elif db is not None and _a2a_service.db is None:
        _a2a_service.db = db
    return _a2a_service


def set_a2a_handoff_db(db):
    """Set database for the A2A service."""
    service = get_a2a_service(db)
    service.db = db
