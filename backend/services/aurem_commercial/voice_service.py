"""
AUREM Commercial Platform - Voice Service (Phase 8)
"No-Key" Developer Brief Implementation

The Voice Gateway that translates Vapi AI webhooks into AUREM's OODA format.
Pre-wired for Vapi AI + Vobiz SIP Trunk + ElevenLabs TTS.

Architecture:
1. Vapi AI → Webhook → voice_service.py → Brain Orchestrator (OODA telemetry)
2. Voice Service → Action Engine (Calendar/Stripe tools during calls)
3. Voice Service → Unified Inbox (Call transcripts as messages)
4. Voice Service → WebSocket Hub (Live call feed for dashboard)

Persona Templates:
- AUREM Skincare: PDRN Technology Expert (Sophisticated, Clinical, High-End)
- AUREM Auto: Technical Service Advisor (Knowledgeable, Efficient, Premium)

Environment Variables (to be configured later):
- VAPI_API_KEY: Vapi AI platform API key
- VAPI_PHONE_NUMBER_ID: The Vapi phone number ID
- VOBIZ_TRUNK_SIP_URI: Vobiz SIP trunk URI
- ELEVENLABS_API_KEY: ElevenLabs voice API key (optional, Vapi has built-in voices)
"""

import logging
import secrets
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
import os

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class CallStatus(str, Enum):
    """Voice call lifecycle states"""
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"


class VapiEventType(str, Enum):
    """Vapi webhook event types"""
    CALL_STARTED = "call.started"
    CALL_ENDED = "call.ended"
    SPEECH_UPDATE = "speech.update"
    TRANSCRIPT = "transcript"
    TOOL_CALL = "tool.call"
    TRANSFER = "transfer"
    HANG = "hang"
    FUNCTION_CALL = "function-call"
    FUNCTION_CALL_RESULT = "function-call-result"
    ASSISTANT_REQUEST = "assistant-request"  # VIP Recognition webhook
    CALL_FORWARDING = "call.forwarding"  # Silent Context Handoff


class PersonaType(str, Enum):
    """Voice AI persona templates"""
    SKINCARE_LUXE = "skincare_luxe"
    SKINCARE_LUXE_VIP = "skincare_luxe_vip"  # VIP tier with premium LLM
    AUTO_ADVISOR = "auto_advisor"
    AUTO_ADVISOR_VIP = "auto_advisor_vip"  # VIP tier
    GENERAL_ASSISTANT = "general_assistant"


class CustomerTier(str, Enum):
    """Customer tier levels for VIP Recognition"""
    STANDARD = "standard"
    PREMIUM = "premium"
    VIP = "vip"
    ENTERPRISE = "enterprise"


# Persona system prompts for Vapi Assistant
PERSONA_PROMPTS = {
    PersonaType.SKINCARE_LUXE: """You are AUREM, a sophisticated AI concierge for a premium PDRN skincare brand.

Voice Personality: Warm, knowledgeable, and elegant. Speak with confidence about advanced skincare science.

Expertise Areas:
- PDRN (Polydeoxyribonucleotide) technology and its skin regeneration benefits
- Luxury skincare routines and product recommendations
- Appointment scheduling for consultations and treatments
- Order status inquiries and product availability

Communication Style:
- Use refined, clinical vocabulary without being cold
- Ask clarifying questions to understand the customer's skin concerns
- Always recommend booking a consultation for personalized advice
- Reference scientific backing while remaining approachable

Available Actions:
- Book appointments for skincare consultations
- Check product availability and pricing
- Process payments and create invoices
- Transfer to human specialist when requested""",

    PersonaType.AUTO_ADVISOR: """You are AUREM, a technical service advisor for a premium automotive service center.

Voice Personality: Professional, efficient, and technically competent. Inspire trust in vehicle care expertise.

Expertise Areas:
- Vehicle maintenance schedules and service recommendations
- Diagnostic inquiry (symptoms, warning lights, sounds)
- Service appointment booking and availability
- Cost estimates and payment processing

Communication Style:
- Use clear, jargon-appropriate language for car owners
- Ask diagnostic questions to understand the issue
- Provide time and cost estimates when possible
- Emphasize safety and preventive maintenance

Available Actions:
- Book service appointments with technician availability check
- Provide service cost estimates
- Process payments and create invoices
- Transfer to service manager for complex issues""",

    PersonaType.GENERAL_ASSISTANT: """You are AUREM, a professional AI business assistant.

Voice Personality: Friendly, helpful, and efficient. Handle inquiries with warmth and competence.

Expertise Areas:
- Appointment scheduling
- General inquiries and information
- Payment processing
- Message taking and follow-up scheduling

Communication Style:
- Be concise but personable
- Confirm understanding before taking action
- Offer alternatives when the requested time isn't available
- Always confirm details before booking or processing

Available Actions:
- Book appointments and check calendar availability
- Create invoices and payment links
- Send follow-up emails
- Transfer to human agent when needed""",

    # ═══════════════════════════════════════════════════════════════════════════
    # VIP TIER PERSONAS (Upgraded LLM + Personalized Greetings)
    # ═══════════════════════════════════════════════════════════════════════════
    
    PersonaType.SKINCARE_LUXE_VIP: """You are AUREM, a senior AI concierge exclusively serving VIP clients of our premium PDRN skincare brand.

Voice Personality: Exceptionally warm, deeply knowledgeable, and personally attentive. You remember this client.

IMPORTANT: This is a VIP client. Use their name frequently. Reference their history if provided in context.
If their recent purchase/treatment history is available, mention it naturally: "I see you recently tried our PDRN serum—how has your skin been responding?"

Expertise Areas:
- Deep knowledge of PDRN technology and advanced regenerative treatments
- Personalized skincare regimen recommendations based on client history
- Priority appointment scheduling with preferred specialists
- Exclusive product access and VIP pricing

Communication Style:
- Address the client by name
- Reference their history to show continuity
- Offer exclusive benefits and priority scheduling
- Provide more detailed scientific explanations when asked
- Express genuine appreciation for their loyalty

Available Actions:
- Priority booking with preferred specialists
- VIP-tier product recommendations
- Exclusive pricing and offers
- Direct escalation to senior specialists""",

    PersonaType.AUTO_ADVISOR_VIP: """You are AUREM, a senior technical advisor exclusively serving VIP clients at our premium automotive service center.

Voice Personality: Highly knowledgeable, personally attentive, and remembers the client's vehicle history.

IMPORTANT: This is a VIP client. Use their name and reference their vehicle specifically.
If vehicle history is provided: "Hello [Name], I see your [Vehicle] was in for [service]—how has it been running since then?"

Expertise Areas:
- Comprehensive knowledge of the client's vehicle service history
- Priority diagnostic assessment and scheduling
- VIP loaner vehicle arrangements
- Direct line to master technicians

Communication Style:
- Address by name, reference their specific vehicle
- Proactively mention recommended services based on history
- Offer priority scheduling and VIP amenities
- Provide detailed technical explanations

Available Actions:
- Priority service scheduling
- VIP loaner vehicle arrangement
- Direct escalation to service manager
- Exclusive maintenance packages"""
}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class VapiWebhookPayload(BaseModel):
    """Incoming Vapi webhook payload"""
    type: str
    call_id: Optional[str] = Field(None, alias="callId")
    phone_number: Optional[str] = Field(None, alias="phoneNumber")
    timestamp: Optional[str] = None
    
    # For speech/transcript events
    role: Optional[str] = None  # "user" or "assistant"
    text: Optional[str] = None
    is_final: Optional[bool] = Field(None, alias="isFinal")
    
    # For tool calls
    function_name: Optional[str] = Field(None, alias="functionName")
    arguments: Optional[Dict[str, Any]] = None
    tool_call_id: Optional[str] = Field(None, alias="toolCallId")
    
    # For call events
    ended_reason: Optional[str] = Field(None, alias="endedReason")
    duration_seconds: Optional[int] = Field(None, alias="durationSeconds")
    cost: Optional[float] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = Field(None, alias="recordingUrl")
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class VoiceCall(BaseModel):
    """Tracked voice call record"""
    call_id: str
    business_id: str
    phone_number: str
    direction: str  # "inbound" or "outbound"
    status: CallStatus
    persona: PersonaType
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    transcript: List[Dict[str, str]] = []  # [{role: "user", text: "..."}, ...]
    ooda_thoughts: List[str] = []  # thought_ids from Brain
    actions_taken: List[str] = []  # action_ids from Action Engine
    recording_url: Optional[str] = None
    cost: Optional[float] = None
    ended_reason: Optional[str] = None


class OutboundCallRequest(BaseModel):
    """Request to initiate an outbound call"""
    phone_number: str
    persona: PersonaType = PersonaType.GENERAL_ASSISTANT
    context: Optional[Dict[str, Any]] = None
    scheduled_for: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class AuremVoiceService:
    """
    Voice Gateway Service
    
    Handles:
    1. Vapi webhook processing (call events, transcripts, tool calls)
    2. OODA telemetry integration (every utterance → Brain Orchestrator)
    3. Action Engine bridging (calendar/stripe tools during calls)
    4. Live dashboard updates via WebSocket
    """
    
    COLLECTION = "aurem_voice_calls"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION]
        self._vapi_configured = bool(os.environ.get("VAPI_API_KEY"))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WEBHOOK PROCESSING
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def process_webhook(
        self,
        business_id: str,
        payload: VapiWebhookPayload,
        raw_body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main webhook handler - routes Vapi events to appropriate processors.
        
        This is the entry point for all Vapi webhooks:
        - call.started → Create call record, push to dashboard
        - transcript → Store transcript, send to Brain for OODA
        - tool.call → Execute via Action Engine
        - call.ended → Finalize call, create Inbox message
        """
        event_type = payload.type
        call_id = payload.call_id or raw_body.get("call", {}).get("id")
        
        logger.info(f"[Voice] Processing webhook: {event_type} for call {call_id}")
        
        try:
            if event_type == VapiEventType.CALL_STARTED.value:
                return await self._handle_call_started(business_id, call_id, payload, raw_body)
            
            elif event_type == VapiEventType.CALL_ENDED.value:
                return await self._handle_call_ended(business_id, call_id, payload, raw_body)
            
            elif event_type in [VapiEventType.TRANSCRIPT.value, VapiEventType.SPEECH_UPDATE.value]:
                return await self._handle_transcript(business_id, call_id, payload)
            
            elif event_type in [VapiEventType.TOOL_CALL.value, VapiEventType.FUNCTION_CALL.value]:
                return await self._handle_tool_call(business_id, call_id, payload)
            
            elif event_type == VapiEventType.TRANSFER.value:
                return await self._handle_transfer(business_id, call_id, payload)
            
            elif event_type == VapiEventType.HANG.value:
                return await self._handle_hang(business_id, call_id, payload)
            
            # VIP Recognition - Dynamic Assistant Selection
            elif event_type == VapiEventType.ASSISTANT_REQUEST.value:
                return await self._handle_assistant_request(business_id, payload, raw_body)
            
            # Silent Context Handoff - Transfer with transcript
            elif event_type == VapiEventType.CALL_FORWARDING.value:
                return await self._handle_call_forwarding(business_id, call_id, payload, raw_body)
            
            else:
                logger.warning(f"[Voice] Unhandled event type: {event_type}")
                return {"status": "ignored", "event": event_type}
                
        except Exception as e:
            logger.error(f"[Voice] Webhook processing error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_call_started(
        self,
        business_id: str,
        call_id: str,
        payload: VapiWebhookPayload,
        raw_body: Dict
    ) -> Dict:
        """Handle call.started event - create call record"""
        call_data = raw_body.get("call", {})
        phone_number = (
            payload.phone_number or 
            call_data.get("customer", {}).get("number") or 
            "unknown"
        )
        
        # Determine direction
        direction = "inbound" if call_data.get("type") == "inboundPhoneCall" else "outbound"
        
        # Get persona from assistant config or default
        persona = PersonaType.GENERAL_ASSISTANT
        assistant = call_data.get("assistant", {})
        if assistant:
            name = assistant.get("name", "").lower()
            if "skincare" in name or "luxe" in name:
                persona = PersonaType.SKINCARE_LUXE
            elif "auto" in name or "service" in name:
                persona = PersonaType.AUTO_ADVISOR
        
        # Create call record
        call_record = {
            "call_id": call_id,
            "business_id": business_id,
            "phone_number": phone_number,
            "direction": direction,
            "status": CallStatus.IN_PROGRESS.value,
            "persona": persona.value,
            "started_at": datetime.now(timezone.utc),
            "transcript": [],
            "ooda_thoughts": [],
            "actions_taken": [],
            "raw_start_event": raw_body
        }
        
        await self.collection.insert_one(call_record)
        
        # Push to WebSocket for live dashboard
        await self._push_call_update(business_id, call_id, "started", {
            "phone_number": phone_number,
            "direction": direction,
            "persona": persona.value
        })
        
        logger.info(f"[Voice] Call started: {call_id} from {phone_number}")
        
        return {
            "status": "ok",
            "call_id": call_id,
            "message": "Call tracking started"
        }
    
    async def _handle_call_ended(
        self,
        business_id: str,
        call_id: str,
        payload: VapiWebhookPayload,
        raw_body: Dict
    ) -> Dict:
        """Handle call.ended event - finalize call and create inbox message"""
        call_data = raw_body.get("call", {})
        
        # Update call record
        update_data = {
            "status": CallStatus.ENDED.value,
            "ended_at": datetime.now(timezone.utc),
            "duration_seconds": payload.duration_seconds or call_data.get("duration"),
            "ended_reason": payload.ended_reason or call_data.get("endedReason"),
            "recording_url": payload.recording_url or call_data.get("recordingUrl"),
            "cost": payload.cost or call_data.get("cost"),
            "raw_end_event": raw_body
        }
        
        # Get final transcript if provided
        final_transcript = payload.transcript or call_data.get("transcript")
        if final_transcript:
            update_data["full_transcript"] = final_transcript
        
        await self.collection.update_one(
            {"call_id": call_id},
            {"$set": update_data}
        )
        
        # Get full call record for inbox message
        call_record = await self.collection.find_one({"call_id": call_id})
        
        # Create Unified Inbox message with call summary
        if call_record:
            await self._create_inbox_message(business_id, call_record, update_data)
        
        # Push to WebSocket
        await self._push_call_update(business_id, call_id, "ended", {
            "duration_seconds": update_data.get("duration_seconds"),
            "ended_reason": update_data.get("ended_reason")
        })
        
        logger.info(f"[Voice] Call ended: {call_id}, duration: {update_data.get('duration_seconds')}s")
        
        return {
            "status": "ok",
            "call_id": call_id,
            "message": "Call finalized"
        }
    
    async def _handle_transcript(
        self,
        business_id: str,
        call_id: str,
        payload: VapiWebhookPayload
    ) -> Dict:
        """
        Handle transcript event - store and send to Brain for OODA telemetry.
        
        Every user utterance triggers an OODA thought for live debugging.
        """
        if not payload.text:
            return {"status": "ignored", "reason": "empty_text"}
        
        # Only process final transcripts to avoid duplicates
        if payload.is_final is False:
            return {"status": "ignored", "reason": "interim_transcript"}
        
        transcript_entry = {
            "role": payload.role or "user",
            "text": payload.text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Append to call transcript
        await self.collection.update_one(
            {"call_id": call_id},
            {"$push": {"transcript": transcript_entry}}
        )
        
        # Send to Brain Orchestrator for OODA telemetry (user messages only)
        thought_id = None
        if payload.role == "user" and payload.text:
            thought_id = await self._send_to_brain(business_id, call_id, payload.text)
            
            if thought_id:
                await self.collection.update_one(
                    {"call_id": call_id},
                    {"$push": {"ooda_thoughts": thought_id}}
                )
        
        # Push live transcript to WebSocket
        await self._push_call_update(business_id, call_id, "transcript", {
            "role": payload.role,
            "text": payload.text,
            "thought_id": thought_id
        })
        
        return {
            "status": "ok",
            "call_id": call_id,
            "thought_id": thought_id
        }
    
    async def _handle_tool_call(
        self,
        business_id: str,
        call_id: str,
        payload: VapiWebhookPayload
    ) -> Dict:
        """
        Handle tool.call event - execute via Action Engine.
        
        This is where Vapi's function calling connects to AUREM's Action Engine.
        Supported tools: book_appointment, check_availability, create_invoice, etc.
        """
        func_name = payload.function_name
        args = payload.arguments or {}
        tool_call_id = payload.tool_call_id
        
        logger.info(f"[Voice] Tool call: {func_name} with args: {args}")
        
        try:
            from services.aurem_commercial.action_engine import get_action_engine
            engine = get_action_engine(self.db)
            
            # Execute the tool via Action Engine
            result = await engine.handle_tool_call(
                business_id=business_id,
                func=func_name,
                args=args,
                ip="voice_channel"
            )
            
            # Track action in call record
            if result.get("action_id"):
                await self.collection.update_one(
                    {"call_id": call_id},
                    {"$push": {"actions_taken": result["action_id"]}}
                )
            
            # Push to WebSocket
            await self._push_call_update(business_id, call_id, "tool_call", {
                "function": func_name,
                "result": result
            })
            
            # Return result for Vapi to continue conversation
            return {
                "status": "ok",
                "tool_call_id": tool_call_id,
                "result": result.get("result", {}),
                "message": self._format_tool_result_message(func_name, result)
            }
            
        except Exception as e:
            logger.error(f"[Voice] Tool call failed: {e}")
            return {
                "status": "error",
                "tool_call_id": tool_call_id,
                "error": str(e),
                "message": "I encountered an issue processing that request. Let me help you another way."
            }
    
    async def _handle_transfer(self, business_id: str, call_id: str, payload: VapiWebhookPayload) -> Dict:
        """Handle transfer event - log transfer attempt"""
        await self.collection.update_one(
            {"call_id": call_id},
            {"$push": {"events": {"type": "transfer", "timestamp": datetime.now(timezone.utc).isoformat()}}}
        )
        return {"status": "ok", "message": "Transfer logged"}
    
    async def _handle_hang(self, business_id: str, call_id: str, payload: VapiWebhookPayload) -> Dict:
        """Handle hang event - customer hung up"""
        await self.collection.update_one(
            {"call_id": call_id},
            {"$set": {"status": CallStatus.ENDED.value, "ended_reason": "customer_hangup"}}
        )
        return {"status": "ok", "message": "Hangup logged"}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # VIP RECOGNITION (Dynamic Assistant Routing)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _handle_assistant_request(
        self,
        business_id: str,
        payload: VapiWebhookPayload,
        raw_body: Dict
    ) -> Dict[str, Any]:
        """
        VIP Recognition Webhook - Dynamic Assistant Selection
        
        When a call hits Vobiz gateway, AUREM performs a "Pre-Call Intelligence" check:
        1. Look up caller in Redis Hydrated Memory (< 2 seconds)
        2. If VIP/Premium tier, swap to upgraded persona with GPT-4o
        3. Return personalized greeting with customer context
        
        Commercial Value:
        - "Hello Tejinder, I see your Yukon was just in for service—how can I help?"
        """
        call_data = raw_body.get("call", {})
        phone_number = (
            payload.phone_number or
            call_data.get("customer", {}).get("number") or
            raw_body.get("phoneNumber")
        )
        
        logger.info(f"[Voice] VIP Recognition check for {phone_number}")
        
        # Perform VIP lookup
        customer_profile = await self._lookup_customer_profile(business_id, phone_number)
        
        if customer_profile:
            tier = customer_profile.get("tier", CustomerTier.STANDARD.value)
            name = customer_profile.get("name", "")
            
            # Determine persona based on tier and business type
            persona, model, greeting = self._select_vip_assistant(
                tier=tier,
                name=name,
                business_type=customer_profile.get("business_type", "general"),
                history=customer_profile.get("recent_history", [])
            )
            
            logger.info(f"[Voice] VIP tier '{tier}' - using {persona.value} with {model}")
            
            # Return dynamic assistant configuration
            return {
                "assistant": {
                    "name": f"AUREM {persona.value}",
                    "model": {
                        "provider": "openai",
                        "model": model,
                        "systemPrompt": PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS[PersonaType.GENERAL_ASSISTANT])
                    },
                    "voice": {
                        "provider": "11labs",
                        "voiceId": "rachel" if tier in [CustomerTier.VIP.value, CustomerTier.ENTERPRISE.value] else "alloy"
                    },
                    "firstMessage": greeting,
                    "metadata": {
                        "customer_name": name,
                        "customer_tier": tier,
                        "customer_id": customer_profile.get("customer_id")
                    }
                }
            }
        
        # No VIP profile - use default assistant
        return {
            "assistant": None  # Vapi uses default assistant
        }
    
    async def _lookup_customer_profile(
        self,
        business_id: str,
        phone_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Look up customer in Redis Hydrated Memory for VIP Recognition.
        
        Returns customer profile with:
        - tier: standard/premium/vip/enterprise
        - name: Customer name
        - recent_history: Recent transactions/visits
        - business_type: skincare/auto/general
        """
        try:
            import redis.asyncio as redis
            
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            r = redis.from_url(redis_url)
            
            # Normalize phone number
            phone_key = phone_number.replace("+", "").replace("-", "").replace(" ", "")
            
            # Look up in Redis
            cache_key = f"aurem:customer:{business_id}:{phone_key}"
            cached = await r.get(cache_key)
            
            if cached:
                import json
                return json.loads(cached)
            
            # Fall back to MongoDB lookup
            customers = self.db["customers"]
            customer = await customers.find_one(
                {
                    "business_id": business_id,
                    "$or": [
                        {"phone": phone_number},
                        {"phone": phone_key},
                        {"phone": f"+{phone_key}"}
                    ]
                },
                {"_id": 0}
            )
            
            if customer:
                # Hydrate into Redis for next time (5 min TTL)
                await r.setex(cache_key, 300, json.dumps(customer))
                return customer
            
            await r.close()
            
        except Exception as e:
            logger.warning(f"[Voice] Customer lookup failed: {e}")
        
        return None
    
    def _select_vip_assistant(
        self,
        tier: str,
        name: str,
        business_type: str,
        history: List[Dict]
    ) -> Tuple[PersonaType, str, str]:
        """
        Select persona, model, and greeting based on customer tier.
        
        Returns: (persona, model, greeting)
        """
        # Default
        model = "gpt-4o-mini"
        persona = PersonaType.GENERAL_ASSISTANT
        greeting = "Hello! Thank you for calling. How may I assist you today?"
        
        # VIP/Enterprise get GPT-4o and personalized greeting
        if tier in [CustomerTier.VIP.value, CustomerTier.ENTERPRISE.value]:
            model = "gpt-4o"
            
            if business_type == "skincare":
                persona = PersonaType.SKINCARE_LUXE_VIP
                if name and history:
                    last_item = history[0] if history else {}
                    greeting = f"Hello {name}! It's wonderful to hear from you. I see you recently tried our {last_item.get('product', 'PDRN treatment')}—how has your skin been responding?"
                elif name:
                    greeting = f"Hello {name}! Thank you for being such a valued client. How may I assist you today?"
                    
            elif business_type == "auto":
                persona = PersonaType.AUTO_ADVISOR_VIP
                if name and history:
                    vehicle = history[0].get("vehicle", "vehicle") if history else "vehicle"
                    service = history[0].get("service", "service") if history else "service"
                    greeting = f"Hello {name}! Great to hear from you. I see your {vehicle} was in for {service}—how has it been running?"
                elif name:
                    greeting = f"Hello {name}! Thank you for your continued trust in our service. How can I help you today?"
        
        elif tier == CustomerTier.PREMIUM.value:
            model = "gpt-4o-mini"
            if business_type == "skincare":
                persona = PersonaType.SKINCARE_LUXE
            elif business_type == "auto":
                persona = PersonaType.AUTO_ADVISOR
            
            if name:
                greeting = f"Hello {name}! Thank you for calling. How may I assist you today?"
        
        return persona, model, greeting
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SILENT CONTEXT HANDOFF (Human-in-the-Loop)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _handle_call_forwarding(
        self,
        business_id: str,
        call_id: str,
        payload: VapiWebhookPayload,
        raw_body: Dict
    ) -> Dict[str, Any]:
        """
        Silent Context Handoff - Transfer with live transcript.
        
        When AI transfers to human:
        1. Transfer happens silently (no "please hold" message)
        2. Live transcript pushed to Unified Inbox via WebSocket
        3. Human sees full context before picking up
        
        Commercial Value:
        - No customer repetition
        - Instant context for human agent
        """
        logger.info(f"[Voice] Silent handoff for call {call_id}")
        
        # Get full call record with transcript
        call_record = await self.collection.find_one({"call_id": call_id})
        
        if not call_record:
            return {"status": "error", "message": "Call not found"}
        
        # Build context packet for human agent
        transcript_summary = self._build_transcript_summary(call_record.get("transcript", []))
        actions_taken = call_record.get("actions_taken", [])
        customer_intent = await self._extract_customer_intent(call_record)
        
        context_packet = {
            "call_id": call_id,
            "phone_number": call_record.get("phone_number"),
            "duration_so_far": self._calculate_duration(call_record.get("started_at")),
            "customer_tier": raw_body.get("call", {}).get("metadata", {}).get("customer_tier", "standard"),
            "customer_name": raw_body.get("call", {}).get("metadata", {}).get("customer_name"),
            "transcript_summary": transcript_summary,
            "full_transcript": call_record.get("transcript", [])[-10:],  # Last 10 exchanges
            "actions_taken": actions_taken,
            "customer_intent": customer_intent,
            "handoff_reason": raw_body.get("transferReason", "Customer requested human"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Push to WebSocket for Unified Inbox popup
        await self._push_handoff_context(business_id, context_packet)
        
        # Also create an urgent inbox message
        await self._create_handoff_inbox_message(business_id, context_packet)
        
        # Update call record
        await self.collection.update_one(
            {"call_id": call_id},
            {"$set": {
                "handoff_initiated": True,
                "handoff_context": context_packet,
                "handoff_at": datetime.now(timezone.utc)
            }}
        )
        
        return {
            "status": "ok",
            "message": "Silent handoff context delivered",
            "destination": {
                "message": ""  # Empty = silent transfer
            }
        }
    
    def _build_transcript_summary(self, transcript: List[Dict]) -> str:
        """Build a quick summary of the conversation for human agent"""
        if not transcript:
            return "No conversation yet"
        
        # Get key points
        customer_messages = [t.get("text", "") for t in transcript if t.get("role") == "user"]
        
        if len(customer_messages) <= 2:
            return " | ".join(customer_messages)
        
        # Summarize longer conversations
        first = customer_messages[0]
        last = customer_messages[-1]
        return f"Started: '{first[:50]}...' | Latest: '{last[:50]}...'"
    
    def _calculate_duration(self, started_at) -> int:
        """Calculate call duration in seconds"""
        if not started_at:
            return 0
        
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        
        now = datetime.now(timezone.utc)
        return int((now - started_at).total_seconds())
    
    async def _extract_customer_intent(self, call_record: Dict) -> str:
        """Extract primary customer intent from transcript"""
        transcript = call_record.get("transcript", [])
        if not transcript:
            return "Unknown"
        
        # Simple extraction - look for key phrases
        customer_text = " ".join([
            t.get("text", "") for t in transcript if t.get("role") == "user"
        ]).lower()
        
        if any(word in customer_text for word in ["book", "appointment", "schedule", "come in"]):
            return "Booking appointment"
        elif any(word in customer_text for word in ["price", "cost", "how much", "payment"]):
            return "Pricing inquiry"
        elif any(word in customer_text for word in ["problem", "issue", "not working", "broken"]):
            return "Support issue"
        elif any(word in customer_text for word in ["cancel", "refund", "return"]):
            return "Cancellation/Refund"
        else:
            return "General inquiry"
    
    async def _push_handoff_context(self, business_id: str, context: Dict) -> None:
        """Push handoff context to WebSocket for live dashboard popup"""
        try:
            from services.aurem_commercial import get_websocket_hub
            hub = await get_websocket_hub()
            
            await hub.push_activity(
                business_id,
                "voice_handoff",
                f"🔴 INCOMING CALL TRANSFER from {context.get('customer_name', 'Customer')}",
                "phone_forwarded",
                {
                    "priority": "urgent",
                    "context": context
                }
            )
            
        except Exception as e:
            logger.warning(f"[Voice] Handoff WebSocket push failed: {e}")
    
    async def _create_handoff_inbox_message(self, business_id: str, context: Dict) -> None:
        """Create urgent Unified Inbox message for handoff"""
        try:
            from services.aurem_commercial.unified_inbox_service import (
                get_unified_inbox_service, ChannelType
            )
            
            inbox = get_unified_inbox_service(self.db)
            
            # Build message body
            body = f"""🔴 LIVE CALL TRANSFER

**Caller:** {context.get('customer_name', 'Unknown')} ({context.get('phone_number', 'Unknown')})
**Duration:** {context.get('duration_so_far', 0)} seconds
**Customer Tier:** {context.get('customer_tier', 'standard').upper()}
**Intent:** {context.get('customer_intent', 'Unknown')}
**Handoff Reason:** {context.get('handoff_reason', 'Customer requested')}

**Conversation Summary:**
{context.get('transcript_summary', 'No summary available')}

**Actions Taken by AI:**
{', '.join(context.get('actions_taken', [])) or 'None'}
"""
            
            await inbox.ingest_message(
                business_id=business_id,
                channel=ChannelType.PHONE if hasattr(ChannelType, 'PHONE') else ChannelType.WEB_CHAT,
                external_id=f"handoff_{context.get('call_id')}",
                sender={
                    "name": context.get("customer_name", "Voice Call Transfer"),
                    "phone": context.get("phone_number"),
                    "avatar_url": None
                },
                content={
                    "subject": f"🔴 LIVE: {context.get('customer_name', 'Customer')} - {context.get('customer_intent', 'Transfer')}",
                    "body": body,
                    "text": body
                },
                metadata={
                    "call_id": context.get("call_id"),
                    "is_handoff": True,
                    "priority": "urgent",
                    "full_context": context
                },
                auto_suggest=False
            )
            
        except Exception as e:
            logger.error(f"[Voice] Handoff inbox message failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BRAIN INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _send_to_brain(self, business_id: str, call_id: str, message: str) -> Optional[str]:
        """
        Send user utterance to Brain Orchestrator for OODA telemetry.
        
        This creates a "thought" record that shows up in the Brain Debugger,
        allowing developers to see AI reasoning in real-time during calls.
        """
        try:
            from services.aurem_commercial.brain_orchestrator import (
                get_brain_orchestrator, BrainInput
            )
            
            brain = get_brain_orchestrator(self.db)
            
            # Create a minimal API key info for voice channel
            api_key_info = {
                "key_id": f"voice_{call_id}",
                "scopes": ["chat:read", "chat:write", "actions:calendar", "actions:payments"],
                "is_voice_channel": True
            }
            
            brain_input = BrainInput(
                message=message,
                conversation_id=f"voice_{call_id}",
                context={"channel": "voice", "call_id": call_id}
            )
            
            result = await brain.think(
                business_id=business_id,
                input_data=brain_input,
                api_key_info=api_key_info,
                ip_address="voice_channel"
            )
            
            return result.thought_id
            
        except Exception as e:
            logger.error(f"[Voice] Brain integration failed: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UNIFIED INBOX INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _create_inbox_message(
        self,
        business_id: str,
        call_record: Dict,
        end_data: Dict
    ) -> None:
        """
        Create a Unified Inbox message from a completed call.
        
        This allows voice calls to appear in the omnichannel inbox with
        a summary and any actions taken during the call.
        """
        try:
            from services.aurem_commercial.unified_inbox_service import (
                get_unified_inbox_service, ChannelType
            )
            
            inbox_service = get_unified_inbox_service(self.db)
            
            # Build call summary
            duration = end_data.get("duration_seconds", 0)
            transcript_count = len(call_record.get("transcript", []))
            actions_count = len(call_record.get("actions_taken", []))
            
            summary = f"Voice call ({duration}s) - {transcript_count} exchanges"
            if actions_count > 0:
                summary += f", {actions_count} action(s) taken"
            
            # Build transcript as message body
            transcript_text = ""
            for entry in call_record.get("transcript", [])[:20]:  # Limit to 20 entries
                role = "Customer" if entry.get("role") == "user" else "AUREM"
                transcript_text += f"[{role}]: {entry.get('text', '')}\n"
            
            await inbox_service.ingest_message(
                business_id=business_id,
                channel=ChannelType.PHONE if hasattr(ChannelType, 'PHONE') else ChannelType.WEB_CHAT,
                external_id=call_record["call_id"],
                sender={
                    "name": "Voice Call",
                    "phone": call_record.get("phone_number"),
                    "avatar_url": None
                },
                content={
                    "subject": summary,
                    "body": transcript_text or "No transcript available",
                    "text": transcript_text
                },
                metadata={
                    "call_id": call_record["call_id"],
                    "duration_seconds": duration,
                    "direction": call_record.get("direction"),
                    "persona": call_record.get("persona"),
                    "actions_taken": call_record.get("actions_taken", []),
                    "recording_url": end_data.get("recording_url")
                },
                auto_suggest=False  # Don't auto-suggest for completed calls
            )
            
        except Exception as e:
            logger.error(f"[Voice] Inbox creation failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WEBSOCKET INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _push_call_update(
        self,
        business_id: str,
        call_id: str,
        event: str,
        data: Dict
    ) -> None:
        """Push call updates to WebSocket for live dashboard"""
        try:
            from services.aurem_commercial import get_websocket_hub
            hub = await get_websocket_hub()
            
            await hub.push_activity(
                business_id,
                "voice_call",
                f"Voice: {event}",
                "phone",
                {"call_id": call_id, "event": event, **data}
            )
            
        except Exception as e:
            logger.warning(f"[Voice] WebSocket push failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OUTBOUND CALLS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def initiate_outbound_call(
        self,
        business_id: str,
        request: OutboundCallRequest
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call via Vapi API.
        
        NOTE: This is scaffolded for "No-Key" mode. When VAPI_API_KEY is
        provided, this will make actual API calls to Vapi.
        """
        if not self._vapi_configured:
            return {
                "status": "mock",
                "message": "Vapi API key not configured. Call simulated.",
                "call_id": f"mock_{secrets.token_hex(8)}",
                "phone_number": request.phone_number,
                "persona": request.persona.value
            }
        
        try:
            import httpx
            
            vapi_key = os.environ.get("VAPI_API_KEY")
            phone_number_id = os.environ.get("VAPI_PHONE_NUMBER_ID")
            
            # Get persona prompt
            system_prompt = PERSONA_PROMPTS.get(request.persona, PERSONA_PROMPTS[PersonaType.GENERAL_ASSISTANT])
            
            # Vapi outbound call API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.vapi.ai/call/phone",
                    headers={
                        "Authorization": f"Bearer {vapi_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "phoneNumberId": phone_number_id,
                        "customer": {
                            "number": request.phone_number
                        },
                        "assistant": {
                            "name": f"AUREM {request.persona.value}",
                            "model": {
                                "provider": "openai",
                                "model": "gpt-4o",
                                "systemPrompt": system_prompt
                            },
                            "voice": {
                                "provider": "11labs",
                                "voiceId": "rachel"  # Default ElevenLabs voice
                            }
                        },
                        "metadata": {
                            "business_id": business_id,
                            "persona": request.persona.value,
                            "context": request.context
                        }
                    },
                    timeout=30.0
                )
                
                if response.status_code == 201:
                    data = response.json()
                    return {
                        "status": "initiated",
                        "call_id": data.get("id"),
                        "phone_number": request.phone_number,
                        "persona": request.persona.value
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Vapi API error: {response.status_code}",
                        "details": response.text
                    }
                    
        except Exception as e:
            logger.error(f"[Voice] Outbound call failed: {e}")
            return {"status": "error", "message": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # VAPI ASSISTANT CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_vapi_assistant_config(self, persona: PersonaType, customer_tier: str = "standard") -> Dict[str, Any]:
        """
        Generate Vapi assistant configuration with Action Engine tools.
        
        Includes Smart Endpointing & Natural Interruption settings:
        - 750-900ms latency for thoughtful, professional feel
        - Immediate stop on customer interruption
        - OODA loop pivot on mid-sentence questions
        
        This can be used to create/update a Vapi assistant with AUREM's
        tool definitions for calendar, payments, etc.
        """
        from services.aurem_commercial.action_engine import TOOL_DEFINITIONS
        
        # Convert Action Engine tools to Vapi format
        vapi_functions = []
        for tool in TOOL_DEFINITIONS:
            func = tool.get("function", {})
            vapi_functions.append({
                "name": func.get("name"),
                "description": func.get("description"),
                "parameters": func.get("parameters")
            })
        
        # Select model based on tier
        model = "gpt-4o" if customer_tier in ["vip", "enterprise"] else "gpt-4o-mini"
        
        # Select voice based on tier (premium voices for VIP)
        voice_config = {
            "provider": "11labs",
            "voiceId": "rachel" if customer_tier in ["vip", "enterprise"] else "alloy"
        }
        
        return {
            "name": f"AUREM {persona.value}",
            "model": {
                "provider": "openai",
                "model": model,
                "systemPrompt": PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS[PersonaType.GENERAL_ASSISTANT]),
                "functions": vapi_functions,
                "temperature": 0.7  # Balanced creativity
            },
            "voice": voice_config,
            "firstMessage": "Hello, thank you for calling. How may I assist you today?",
            
            # ═══════════════════════════════════════════════════════════════════
            # SMART ENDPOINTING & NATURAL INTERRUPTION SETTINGS
            # ═══════════════════════════════════════════════════════════════════
            # These settings make the AI feel like a thoughtful professional
            # that listens and responds naturally without monologuing.
            
            "startSpeakingPlan": {
                # Wait time before AI starts speaking after user stops
                # 750-900ms = professional, thoughtful feel
                # Too short = interrupts user; Too long = awkward pause
                "waitSeconds": 0.8,
                
                # Enable smart endpointing (detect natural pause vs thinking)
                "smartEndpointingEnabled": True,
                
                # Transcription threshold - confidence before responding
                "transcriptionEndpointingPlan": {
                    "onPunctuationSeconds": 0.5,  # Faster after clear sentence end
                    "onNoPunctuationSeconds": 1.2,  # Longer wait if unclear
                    "onNumberSeconds": 0.8  # Wait after numbers (phone, amounts)
                }
            },
            
            "stopSpeakingPlan": {
                # Number of words before AI can be interrupted
                # Lower = more interruptible (natural conversation)
                "numWords": 2,
                
                # Voice activity detection sensitivity
                "voiceSeconds": 0.2,  # Quick detection of user speech
                
                # Backoff after interruption (don't repeat)
                "backoffSeconds": 0.5
            },
            
            # Background sound settings for professional feel
            "backgroundSound": "off",
            
            # Call recording (for quality & training)
            "recordingEnabled": True,
            
            # Webhook configuration
            "serverUrl": "${WEBHOOK_URL}/api/aurem-voice/webhook",
            "serverUrlSecret": "${WEBHOOK_SECRET}",
            
            # Metadata pass-through
            "metadata": {
                "customer_tier": customer_tier,
                "persona": persona.value
            }
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _format_tool_result_message(self, func_name: str, result: Dict) -> str:
        """Format tool result as natural language for voice response"""
        status = result.get("status")
        data = result.get("result", {})
        
        if status == "success":
            if func_name == "book_appointment":
                return f"I've booked your appointment. {data.get('title', 'Meeting')} is confirmed."
            elif func_name == "check_calendar_availability":
                slots = data.get("available_slots", [])
                if slots:
                    times = [s.get("time") for s in slots[:3]]
                    return f"I have availability at {', '.join(times)}. Would any of those work for you?"
                return "I don't see any available slots for that date. Would you like to try another day?"
            elif func_name == "create_invoice":
                return f"I've created an invoice for ${data.get('amount', 0):.2f}. You'll receive it by email shortly."
            elif func_name == "create_payment_link":
                return f"I've created a payment link for ${data.get('amount', 0):.2f}. I can text it to you if you'd like."
            else:
                return "Done! Is there anything else I can help you with?"
        else:
            return "I wasn't able to complete that request. Let me try to help you another way."
    
    async def get_active_calls(self, business_id: str) -> List[Dict]:
        """Get all active (in-progress) calls for a business"""
        calls = await self.collection.find(
            {"business_id": business_id, "status": CallStatus.IN_PROGRESS.value},
            {"_id": 0}
        ).to_list(100)
        return calls
    
    async def get_call_history(
        self,
        business_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get call history for a business"""
        total = await self.collection.count_documents({"business_id": business_id})
        
        calls = await self.collection.find(
            {"business_id": business_id},
            {"_id": 0, "raw_start_event": 0, "raw_end_event": 0}
        ).sort("started_at", -1).skip(offset).limit(limit).to_list(limit)
        
        return {
            "calls": calls,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    async def get_call(self, call_id: str) -> Optional[Dict]:
        """Get a single call record"""
        return await self.collection.find_one(
            {"call_id": call_id},
            {"_id": 0}
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_voice_service: Optional[AuremVoiceService] = None


def get_voice_service(db: AsyncIOMotorDatabase) -> AuremVoiceService:
    """Get or create the Voice Service singleton"""
    global _voice_service
    if _voice_service is None:
        _voice_service = AuremVoiceService(db)
    return _voice_service
