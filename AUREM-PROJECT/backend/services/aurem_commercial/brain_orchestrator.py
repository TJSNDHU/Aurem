"""
AUREM AI Brain Orchestrator - "The Handshake"
Master Controller for Autonomous AI Decision Making

This is the central intelligence layer that:
1. Receives messages via validated AUREM API Keys
2. Runs the OODA Loop (Observe → Orient → Decide → Act)
3. Selects and executes the correct MCP Tool from Action Engine
4. Pushes real-time updates to the WebSocket Hub

The Brain connects:
- Key Service (Authentication) → Brain → Action Engine (Execution)
- Brain → WebSocket Hub (Real-time Dashboard Updates)
- Brain → Semantic Cache (Intelligent Response Caching)
- Brain → Redis Memory (Conversation Context)

OODA Framework:
- OBSERVE: Gather context (user message, conversation history, business data)
- ORIENT: Analyze intent using LLM (classify, extract entities, determine urgency)
- DECIDE: Select best action (respond, book appointment, send email, etc.)
- ACT: Execute via Action Engine tools and push to WebSocket
"""

import logging
import json
import secrets
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
import os

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# BRAIN CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class IntentType(str, Enum):
    """Classified user intents"""
    CHAT = "chat"                           # General conversation
    BOOK_APPOINTMENT = "book_appointment"   # Schedule meeting
    CHECK_AVAILABILITY = "check_availability"  # Check calendar
    SEND_EMAIL = "send_email"               # Compose/send email
    SEND_WHATSAPP = "send_whatsapp"         # Send WhatsApp message
    CREATE_INVOICE = "create_invoice"       # Generate invoice
    CREATE_PAYMENT = "create_payment"       # Payment link
    QUERY_DATA = "query_data"               # Business intelligence query
    UNKNOWN = "unknown"                     # Fallback


class UrgencyLevel(str, Enum):
    """Action urgency classification"""
    IMMEDIATE = "immediate"   # Execute now
    HIGH = "high"             # Execute within minutes
    NORMAL = "normal"         # Execute when convenient
    LOW = "low"               # Can defer


class BrainPhase(str, Enum):
    """OODA Loop phases"""
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"
    COMPLETE = "complete"
    ERROR = "error"


# Intent → Action Engine tool mapping
INTENT_TO_TOOL = {
    IntentType.BOOK_APPOINTMENT: "book_appointment",
    IntentType.CHECK_AVAILABILITY: "check_calendar_availability",
    IntentType.SEND_EMAIL: "send_email",
    IntentType.SEND_WHATSAPP: "send_whatsapp",
    IntentType.CREATE_INVOICE: "create_invoice",
    IntentType.CREATE_PAYMENT: "create_payment_link",
}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class BrainInput(BaseModel):
    """Input to the Brain Orchestrator"""
    message: str
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None  # Additional context (customer data, etc.)


class ObserveResult(BaseModel):
    """Result of OBSERVE phase"""
    user_message: str
    conversation_history: List[Dict[str, str]]
    business_context: Dict[str, Any]
    timestamp: datetime


class OrientResult(BaseModel):
    """Result of ORIENT phase"""
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]  # Extracted entities (dates, emails, amounts, etc.)
    urgency: UrgencyLevel
    reasoning: str
    requires_action: bool


class DecideResult(BaseModel):
    """Result of DECIDE phase"""
    selected_tool: Optional[str]
    tool_parameters: Dict[str, Any]
    should_respond: bool
    response_draft: Optional[str]
    decision_reasoning: str


class ActResult(BaseModel):
    """Result of ACT phase"""
    action_id: Optional[str]
    action_status: str
    action_result: Optional[Dict[str, Any]]
    final_response: str
    pushed_to_dashboard: bool


class BrainOutput(BaseModel):
    """Complete Brain Orchestrator output"""
    thought_id: str
    business_id: str
    phases: Dict[str, Any]
    final_response: str
    actions_taken: List[str]
    duration_ms: int
    status: BrainPhase


# ═══════════════════════════════════════════════════════════════════════════════
# BRAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class AuremBrainOrchestrator:
    """
    The Master Controller - "The Handshake"
    
    Orchestrates the complete OODA loop:
    1. OBSERVE - Gather all relevant context
    2. ORIENT - Analyze intent and extract entities using LLM
    3. DECIDE - Select the appropriate action
    4. ACT - Execute via Action Engine and push to WebSocket
    """
    
    COLLECTION = "aurem_brain_thoughts"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION]
    
    async def think(
        self,
        business_id: str,
        input_data: BrainInput,
        api_key_info: Dict[str, Any],
        ip_address: Optional[str] = None
    ) -> BrainOutput:
        """
        Main entry point - Process a message through the OODA loop.
        
        Args:
            business_id: The AUREM business ID
            input_data: User message and context
            api_key_info: Validated API key information (includes scopes)
            ip_address: Client IP for audit logging
        
        Returns:
            BrainOutput with complete thought process and response
        """
        thought_id = f"thought_{secrets.token_hex(10)}"
        start_time = datetime.now(timezone.utc)
        phases = {}
        actions_taken = []
        
        # Initialize thought record
        await self.collection.insert_one({
            "thought_id": thought_id,
            "business_id": business_id,
            "input": input_data.dict(),
            "key_id": api_key_info.get("key_id"),
            "scopes": api_key_info.get("scopes", []),
            "status": BrainPhase.OBSERVE.value,
            "started_at": start_time,
            "ip_address": ip_address
        })
        
        try:
            # Push initial status to WebSocket
            await self._push_status(business_id, "Brain", "THINKING", thought_id)
            
            # ═══════════════════════════════════════════════════════════════
            # PHASE 1: OBSERVE
            # ═══════════════════════════════════════════════════════════════
            observe_result = await self._observe(business_id, input_data)
            phases["observe"] = observe_result.dict()
            await self._update_thought(thought_id, BrainPhase.ORIENT, {"observe": phases["observe"]})
            
            # ═══════════════════════════════════════════════════════════════
            # PHASE 2: ORIENT
            # ═══════════════════════════════════════════════════════════════
            orient_result = await self._orient(business_id, observe_result)
            phases["orient"] = orient_result.dict()
            await self._update_thought(thought_id, BrainPhase.DECIDE, {"orient": phases["orient"]})
            
            # ═══════════════════════════════════════════════════════════════
            # PHASE 3: DECIDE
            # ═══════════════════════════════════════════════════════════════
            decide_result = await self._decide(business_id, orient_result, api_key_info)
            phases["decide"] = decide_result.dict()
            await self._update_thought(thought_id, BrainPhase.ACT, {"decide": phases["decide"]})
            
            # ═══════════════════════════════════════════════════════════════
            # PHASE 4: ACT
            # ═══════════════════════════════════════════════════════════════
            act_result = await self._act(business_id, decide_result, orient_result, ip_address)
            phases["act"] = act_result.dict()
            
            if act_result.action_id:
                actions_taken.append(f"{decide_result.selected_tool}:{act_result.action_id}")
            
            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Final update
            await self._update_thought(thought_id, BrainPhase.COMPLETE, {
                "act": phases["act"],
                "duration_ms": duration_ms,
                "completed_at": end_time
            })
            
            # Push completion to WebSocket
            await self._push_status(business_id, "Brain", "COMPLETE", thought_id)
            await self._push_activity(
                business_id,
                f"Brain processed: {orient_result.intent.value}",
                "brain",
                {"thought_id": thought_id, "intent": orient_result.intent.value}
            )
            
            return BrainOutput(
                thought_id=thought_id,
                business_id=business_id,
                phases=phases,
                final_response=act_result.final_response,
                actions_taken=actions_taken,
                duration_ms=duration_ms,
                status=BrainPhase.COMPLETE
            )
            
        except Exception as e:
            logger.error(f"[Brain] Error in thought {thought_id}: {e}")
            await self._update_thought(thought_id, BrainPhase.ERROR, {"error": str(e)})
            await self._push_status(business_id, "Brain", "ERROR", thought_id)
            
            return BrainOutput(
                thought_id=thought_id,
                business_id=business_id,
                phases=phases,
                final_response="I encountered an issue processing your request. Please try again.",
                actions_taken=actions_taken,
                duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                status=BrainPhase.ERROR
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OODA PHASE IMPLEMENTATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _observe(self, business_id: str, input_data: BrainInput) -> ObserveResult:
        """
        OBSERVE Phase: Gather all relevant context
        - User message
        - Conversation history from Redis Memory
        - Business profile and settings
        """
        conversation_history = []
        business_context = {}
        
        try:
            # Get conversation history from Redis Memory
            from services.aurem_commercial import get_aurem_memory
            memory = await get_aurem_memory()
            
            conv_id = input_data.conversation_id or f"conv_{secrets.token_hex(6)}"
            history = await memory.get_context(business_id, conv_id)
            conversation_history = history.get("messages", []) if history else []
            
            # Add current message to history
            await memory.store_message(business_id, conv_id, "user", input_data.message)
            
            # Get business profile
            profile = await memory.get_business_profile(business_id)
            business_context = profile or {}
            
        except Exception as e:
            logger.warning(f"[Brain OBSERVE] Memory access failed: {e}")
        
        # Merge with provided context
        if input_data.context:
            business_context.update(input_data.context)
        
        return ObserveResult(
            user_message=input_data.message,
            conversation_history=conversation_history[-10:],  # Last 10 messages
            business_context=business_context,
            timestamp=datetime.now(timezone.utc)
        )
    
    async def _orient(self, business_id: str, observed: ObserveResult) -> OrientResult:
        """
        ORIENT Phase: Analyze intent using LLM
        - Classify intent type
        - Extract relevant entities (dates, emails, amounts)
        - Determine urgency level
        """
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            api_key = os.environ.get("EMERGENT_LLM_KEY")
            if not api_key:
                raise ValueError("EMERGENT_LLM_KEY not configured")
            
            chat = LlmChat(
                api_key=api_key,
                session_id=f"brain_orient_{secrets.token_hex(6)}",
                system_message="""You are the AUREM AI Brain's analysis module.
Your task is to analyze user messages and determine:
1. Intent - What does the user want?
2. Entities - Extract relevant data (dates, emails, phone numbers, amounts, names)
3. Urgency - How urgent is this request?

Available intents:
- chat: General conversation, questions, or information requests
- book_appointment: User wants to schedule a meeting/appointment
- check_availability: User wants to see available time slots
- send_email: User wants to send an email
- send_whatsapp: User wants to send a WhatsApp message
- create_invoice: User wants to generate an invoice
- create_payment: User wants to create a payment link
- query_data: User is asking about business data/analytics
- unknown: Cannot determine intent

Respond ONLY with valid JSON:
{
  "intent": "intent_type",
  "confidence": 0.0-1.0,
  "entities": {
    "date": "extracted date or null",
    "time": "extracted time or null",
    "email": "extracted email or null",
    "phone": "extracted phone or null",
    "amount": extracted_number_or_null,
    "name": "extracted name or null",
    "subject": "extracted subject or null",
    "message_content": "extracted message body or null"
  },
  "urgency": "immediate|high|normal|low",
  "reasoning": "brief explanation of classification",
  "requires_action": true/false
}"""
            ).with_model("openai", "gpt-4o-mini")
            
            # Build context for analysis
            context_summary = ""
            if observed.conversation_history:
                recent = observed.conversation_history[-3:]
                context_summary = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')[:100]}" for m in recent])
            
            analysis_prompt = f"""Analyze this user message:

User Message: "{observed.user_message}"

Recent Conversation:
{context_summary if context_summary else "No prior conversation"}

Business Context: {json.dumps(observed.business_context) if observed.business_context else "None"}

Determine the intent, extract entities, and assess urgency."""
            
            response = await chat.send_message(UserMessage(text=analysis_prompt))
            
            # Parse LLM response
            try:
                # Clean up response if wrapped in markdown
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0]
                
                analysis = json.loads(response.strip())
            except json.JSONDecodeError:
                logger.warning(f"[Brain ORIENT] Failed to parse LLM response: {response[:200]}")
                analysis = {
                    "intent": "chat",
                    "confidence": 0.5,
                    "entities": {},
                    "urgency": "normal",
                    "reasoning": "Failed to parse analysis, defaulting to chat",
                    "requires_action": False
                }
            
            return OrientResult(
                intent=IntentType(analysis.get("intent", "unknown")),
                confidence=float(analysis.get("confidence", 0.5)),
                entities=analysis.get("entities", {}),
                urgency=UrgencyLevel(analysis.get("urgency", "normal")),
                reasoning=analysis.get("reasoning", ""),
                requires_action=analysis.get("requires_action", False)
            )
            
        except Exception as e:
            logger.error(f"[Brain ORIENT] Analysis failed: {e}")
            return OrientResult(
                intent=IntentType.CHAT,
                confidence=0.3,
                entities={},
                urgency=UrgencyLevel.NORMAL,
                reasoning=f"Analysis error: {str(e)}",
                requires_action=False
            )
    
    async def _decide(
        self,
        business_id: str,
        oriented: OrientResult,
        api_key_info: Dict[str, Any]
    ) -> DecideResult:
        """
        DECIDE Phase: Select the best action
        - Map intent to Action Engine tool
        - Validate scope permissions
        - Prepare tool parameters
        """
        scopes = api_key_info.get("scopes", [])
        selected_tool = None
        tool_parameters = {}
        should_respond = True
        response_draft = None
        
        # Check if intent maps to an action
        if oriented.requires_action and oriented.intent in INTENT_TO_TOOL:
            tool_name = INTENT_TO_TOOL[oriented.intent]
            
            # Check scope permissions
            scope_required = self._get_required_scope(oriented.intent)
            has_permission = scope_required in scopes or "admin:keys" in scopes
            
            if has_permission:
                selected_tool = tool_name
                tool_parameters = self._prepare_tool_params(oriented)
                
                # If we have all required params, we'll execute
                if self._validate_tool_params(tool_name, tool_parameters):
                    decision_reasoning = f"Intent '{oriented.intent.value}' maps to tool '{tool_name}'. All parameters available. Executing."
                else:
                    # Need more info from user
                    selected_tool = None
                    response_draft = await self._generate_clarification(oriented)
                    decision_reasoning = "Intent identified but missing required parameters. Asking for clarification."
            else:
                decision_reasoning = f"Intent '{oriented.intent.value}' requires scope '{scope_required}' which is not available."
                response_draft = "I understand what you're asking, but your API key doesn't have permission for this action. Please contact your administrator to upgrade your key permissions."
        else:
            # Pure chat response
            decision_reasoning = "No action required. Generating conversational response."
            response_draft = await self._generate_chat_response(oriented)
        
        return DecideResult(
            selected_tool=selected_tool,
            tool_parameters=tool_parameters,
            should_respond=should_respond,
            response_draft=response_draft,
            decision_reasoning=decision_reasoning
        )
    
    async def _act(
        self,
        business_id: str,
        decided: DecideResult,
        oriented: OrientResult,
        ip_address: Optional[str]
    ) -> ActResult:
        """
        ACT Phase: Execute the decided action
        - Call Action Engine if tool selected
        - Generate final response
        - Push to WebSocket Hub
        """
        action_id = None
        action_status = "no_action"
        action_result = None
        pushed = False
        
        if decided.selected_tool:
            try:
                # Execute via Action Engine
                from services.aurem_commercial.action_engine import get_action_engine
                engine = get_action_engine(self.db)
                
                result = await engine.handle_tool_call(
                    business_id=business_id,
                    func=decided.selected_tool,
                    args=decided.tool_parameters,
                    ip=ip_address
                )
                
                action_id = result.get("action_id")
                action_status = result.get("status", "unknown")
                action_result = result.get("result")
                
                # Generate response based on action result
                if action_status == "success":
                    final_response = await self._generate_action_response(
                        oriented.intent, action_result
                    )
                else:
                    final_response = f"I tried to {oriented.intent.value.replace('_', ' ')} but encountered an issue: {result.get('error', 'Unknown error')}. Please try again."
                
            except Exception as e:
                logger.error(f"[Brain ACT] Action execution failed: {e}")
                action_status = "error"
                final_response = "I encountered an error while processing your request. Please try again."
        else:
            # Use pre-generated response
            final_response = decided.response_draft or "I'm not sure how to help with that. Could you please rephrase?"
        
        # Push to WebSocket
        try:
            from services.aurem_commercial import get_websocket_hub
            hub = await get_websocket_hub()
            
            if action_id:
                await hub.push_activity(
                    business_id,
                    "brain_action",
                    f"Brain executed: {decided.selected_tool}",
                    "brain",
                    {"action_id": action_id, "status": action_status}
                )
            
            pushed = True
        except Exception as e:
            logger.warning(f"[Brain ACT] WebSocket push failed: {e}")
        
        # Store assistant response in memory
        try:
            from services.aurem_commercial import get_aurem_memory
            memory = await get_aurem_memory()
            await memory.store_message(business_id, "conv_default", "assistant", final_response)
        except Exception:
            pass
        
        return ActResult(
            action_id=action_id,
            action_status=action_status,
            action_result=action_result,
            final_response=final_response,
            pushed_to_dashboard=pushed
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _get_required_scope(self, intent: IntentType) -> str:
        """Map intent to required API key scope"""
        scope_map = {
            IntentType.BOOK_APPOINTMENT: "actions:calendar",
            IntentType.CHECK_AVAILABILITY: "actions:calendar",
            IntentType.SEND_EMAIL: "actions:email",
            IntentType.SEND_WHATSAPP: "actions:whatsapp",
            IntentType.CREATE_INVOICE: "actions:payments",
            IntentType.CREATE_PAYMENT: "actions:payments",
            IntentType.CHAT: "chat:read",
            IntentType.QUERY_DATA: "chat:read",
        }
        return scope_map.get(intent, "chat:read")
    
    def _prepare_tool_params(self, oriented: OrientResult) -> Dict[str, Any]:
        """
        Extract tool parameters from oriented entities.
        
        Enhanced with Natural Language Date Parsing:
        - Parses "tomorrow at 3pm", "next Tuesday", "end of month"
        - Auto-timezone to Mississauga/Eastern
        - Fallback to raw extracted date if parsing fails
        """
        from services.aurem_commercial.date_parser import parse_date_for_tool
        
        entities = oriented.entities
        params = {}
        
        if oriented.intent == IntentType.BOOK_APPOINTMENT:
            # Use Natural Language Date Parser for intelligent date handling
            date_text = entities.get("date", "")
            time_text = entities.get("time", "")
            combined_datetime = f"{date_text} {time_text}".strip()
            
            if combined_datetime:
                parsed = parse_date_for_tool(combined_datetime)
                if parsed.get("success"):
                    params["start_time"] = parsed["datetime_iso"]
                    params["parsed_date_confidence"] = parsed["confidence"]
                    params["human_readable"] = parsed["human_readable"]
                    
                    # Flag if clarification might be needed
                    if parsed.get("clarification_needed"):
                        params["needs_confirmation"] = True
                        params["confirmation_text"] = f"Just to confirm, you'd like to book for {parsed['human_readable']}?"
                elif date_text and time_text:
                    # Fallback to raw concatenation
                    params["start_time"] = f"{date_text}T{time_text}:00"
                    
            params["title"] = entities.get("subject", "Meeting scheduled via AUREM")
            params["attendee_email"] = entities.get("email")
            
        elif oriented.intent == IntentType.CHECK_AVAILABILITY:
            date_text = entities.get("date", "")
            
            if date_text:
                parsed = parse_date_for_tool(date_text)
                if parsed.get("success"):
                    params["date"] = parsed["date"]
                    params["human_readable"] = parsed["human_readable"]
                else:
                    params["date"] = date_text
            else:
                params["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
        elif oriented.intent == IntentType.SEND_EMAIL:
            params["to"] = entities.get("email")
            params["subject"] = entities.get("subject", "Message from AUREM")
            params["body"] = entities.get("message_content", oriented.reasoning)
            
        elif oriented.intent == IntentType.SEND_WHATSAPP:
            params["phone"] = entities.get("phone")
            params["message"] = entities.get("message_content", "")
            
        elif oriented.intent == IntentType.CREATE_INVOICE:
            params["customer_email"] = entities.get("email")
            if entities.get("amount"):
                params["items"] = [{"description": "Service", "amount": entities["amount"]}]
                
        elif oriented.intent == IntentType.CREATE_PAYMENT:
            params["product_name"] = entities.get("subject", "Payment")
            params["amount"] = entities.get("amount", 0)
        
        return params
    
    def _validate_tool_params(self, tool_name: str, params: Dict) -> bool:
        """Check if we have all required parameters for a tool"""
        required = {
            "book_appointment": ["start_time", "attendee_email"],
            "check_calendar_availability": ["date"],
            "send_email": ["to", "subject", "body"],
            "send_whatsapp": ["phone", "message"],
            "create_invoice": ["customer_email", "items"],
            "create_payment_link": ["product_name", "amount"],
        }
        
        tool_required = required.get(tool_name, [])
        return all(params.get(r) for r in tool_required)
    
    async def _generate_clarification(self, oriented: OrientResult) -> str:
        """Generate a clarification request for missing information"""
        intent = oriented.intent
        entities = oriented.entities
        
        missing = []
        if intent == IntentType.BOOK_APPOINTMENT:
            if not entities.get("date"):
                missing.append("the date")
            if not entities.get("time"):
                missing.append("the time")
            if not entities.get("email"):
                missing.append("the attendee's email")
        elif intent == IntentType.SEND_EMAIL:
            if not entities.get("email"):
                missing.append("the recipient's email")
            if not entities.get("message_content"):
                missing.append("the message content")
        elif intent == IntentType.SEND_WHATSAPP:
            if not entities.get("phone"):
                missing.append("the phone number")
            if not entities.get("message_content"):
                missing.append("the message")
        elif intent in [IntentType.CREATE_INVOICE, IntentType.CREATE_PAYMENT]:
            if not entities.get("amount"):
                missing.append("the amount")
            if not entities.get("email"):
                missing.append("the customer's email")
        
        if missing:
            return f"I'd be happy to help you {intent.value.replace('_', ' ')}. Could you please provide {', '.join(missing)}?"
        return "Could you please provide more details?"
    
    async def _generate_chat_response(self, oriented: OrientResult) -> str:
        """Generate a conversational response using LLM"""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            api_key = os.environ.get("EMERGENT_LLM_KEY")
            if not api_key:
                return "I'm here to help! What would you like to know?"
            
            chat = LlmChat(
                api_key=api_key,
                session_id=f"brain_chat_{secrets.token_hex(6)}",
                system_message="""You are AUREM, an intelligent AI business assistant.
You help users with:
- Scheduling appointments
- Sending emails and WhatsApp messages
- Creating invoices and payment links
- Answering business questions

Be helpful, professional, and concise. If the user needs to take an action, 
guide them on what information you need."""
            ).with_model("openai", "gpt-4o-mini")
            
            response = await chat.send_message(UserMessage(
                text=f"User says: {oriented.reasoning}\n\nProvide a helpful response."
            ))
            
            return response
            
        except Exception as e:
            logger.error(f"[Brain] Chat generation failed: {e}")
            return "I'm here to help! Feel free to ask me about scheduling, emails, or payments."
    
    async def _generate_action_response(self, intent: IntentType, result: Dict) -> str:
        """Generate a natural response after successful action"""
        if intent == IntentType.BOOK_APPOINTMENT:
            meet_link = result.get("meet_link", "")
            return f"I've booked your appointment! {('Meeting link: ' + meet_link) if meet_link else 'A calendar invite has been sent to the attendee.'}"
        
        elif intent == IntentType.CHECK_AVAILABILITY:
            slots = result.get("available_slots", [])
            if slots:
                times = [s["time"] for s in slots[:5]]
                return f"Here are some available slots: {', '.join(times)}. Would you like to book one?"
            return "There are no available slots for that date. Would you like to try another day?"
        
        elif intent == IntentType.SEND_EMAIL:
            return f"Your email has been sent to {result.get('to', 'the recipient')}."
        
        elif intent == IntentType.SEND_WHATSAPP:
            return f"Your WhatsApp message has been sent to {result.get('to', 'the recipient')}."
        
        elif intent == IntentType.CREATE_INVOICE:
            url = result.get("url", "")
            return f"Invoice created for ${result.get('amount', 0):.2f}. {('View it here: ' + url) if url else ''}"
        
        elif intent == IntentType.CREATE_PAYMENT:
            return f"Payment link created: {result.get('url', 'Link generated')}"
        
        return "Action completed successfully!"
    
    async def _update_thought(self, thought_id: str, phase: BrainPhase, data: Dict):
        """Update thought record in database"""
        await self.collection.update_one(
            {"thought_id": thought_id},
            {"$set": {"status": phase.value, **data}}
        )
    
    async def _push_status(self, business_id: str, agent: str, status: str, thought_id: str):
        """Push agent status to WebSocket"""
        try:
            from services.aurem_commercial import get_websocket_hub
            hub = await get_websocket_hub()
            await hub.push_agent_status(business_id, agent, status, 0)
        except Exception:
            pass
    
    async def _push_activity(self, business_id: str, description: str, activity_type: str, metadata: Dict):
        """Push activity to WebSocket"""
        try:
            from services.aurem_commercial import get_websocket_hub
            hub = await get_websocket_hub()
            await hub.push_activity(business_id, activity_type, description, "brain", metadata)
        except Exception:
            pass
    
    async def get_thought(self, thought_id: str) -> Optional[Dict]:
        """Retrieve a thought record"""
        return await self.collection.find_one(
            {"thought_id": thought_id},
            {"_id": 0}
        )
    
    async def get_thoughts_for_business(
        self,
        business_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """Get recent thoughts for a business"""
        return await self.collection.find(
            {"business_id": business_id},
            {"_id": 0}
        ).sort("started_at", -1).limit(limit).to_list(limit)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_brain_orchestrator: Optional[AuremBrainOrchestrator] = None

def get_brain_orchestrator(db: AsyncIOMotorDatabase) -> AuremBrainOrchestrator:
    """Get or create the Brain Orchestrator singleton"""
    global _brain_orchestrator
    if _brain_orchestrator is None:
        _brain_orchestrator = AuremBrainOrchestrator(db)
    return _brain_orchestrator
