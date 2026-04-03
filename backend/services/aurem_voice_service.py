"""
AUREM Voice Service - Real Voice-to-Voice Conversation
Uses Vapi for true voice AI - speak and get instant voice responses
"""

import os
import uuid
import json
import logging
import aiohttp
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Vapi Configuration
VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
VAPI_BASE_URL = "https://api.vapi.ai"

# LLM Configuration for voice
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


class VoiceCallConfig(BaseModel):
    """Configuration for voice calls"""
    assistant_name: str = "AUREM"
    first_message: str = "Hello, I'm AUREM, your AI business partner. How can I help you today?"
    voice_id: str = "rachel"  # Vapi voice
    model: str = "gpt-4o"
    language: str = "en"


class AuremVoiceService:
    """
    AUREM Voice Service for real voice-to-voice conversations
    """
    
    def __init__(self, db=None):
        self.db = db
        self.vapi_key = VAPI_API_KEY
        self.llm_key = EMERGENT_LLM_KEY
        self.active_calls: Dict[str, Dict] = {}
        
        # AUREM Assistant System Prompt
        self.system_prompt = """You are AUREM, an advanced AI business intelligence assistant powered by a multi-agent system.

Your voice is professional, confident, and helpful. You speak naturally like a business consultant.

Your capabilities include:
- Business automation strategy and implementation
- Lead generation and qualification  
- Customer engagement and CRM optimization
- Data analysis and actionable insights
- Integration with email, WhatsApp, voice, and CRM systems

When speaking:
- Be concise but thorough
- Use natural conversational language
- Provide specific, actionable recommendations
- Reference your agent swarm when relevant (Scout, Architect, Envoy, Closer)

Always maintain a professional yet approachable tone. You are the user's intelligent business partner."""
    
    async def create_web_call(self, user_id: str, config: VoiceCallConfig = None) -> Dict[str, Any]:
        """
        Create a web-based voice call session
        Returns configuration for client-side Vapi SDK
        """
        if not self.vapi_key:
            return {
                "error": "Voice service not configured",
                "fallback": "text",
                "message": "Voice-to-voice requires Vapi API key. Please configure VAPI_API_KEY."
            }
        
        config = config or VoiceCallConfig()
        call_id = str(uuid.uuid4())
        
        try:
            # Create Vapi assistant configuration
            assistant_config = {
                "name": config.assistant_name,
                "firstMessage": config.first_message,
                "model": {
                    "provider": "openai",
                    "model": config.model,
                    "systemPrompt": self.system_prompt,
                    "temperature": 0.7
                },
                "voice": {
                    "provider": "11labs",
                    "voiceId": config.voice_id
                },
                "transcriber": {
                    "provider": "deepgram",
                    "model": "nova-2",
                    "language": config.language
                },
                "silenceTimeoutSeconds": 30,
                "maxDurationSeconds": 600,  # 10 minute max call
                "backgroundSound": "off",
                "recordingEnabled": True
            }
            
            # Store call info
            self.active_calls[call_id] = {
                "user_id": user_id,
                "config": assistant_config,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "ready"
            }
            
            # Save to database
            if self.db:
                await self.db.aurem_voice_calls.insert_one({
                    "call_id": call_id,
                    "user_id": user_id,
                    "config": assistant_config,
                    "status": "ready",
                    "created_at": datetime.now(timezone.utc)
                })
            
            return {
                "call_id": call_id,
                "vapi_key": self.vapi_key,  # Client uses this to init Vapi SDK
                "assistant_config": assistant_config,
                "status": "ready",
                "instructions": "Use Vapi Web SDK to start the call with this configuration"
            }
            
        except Exception as e:
            logger.error(f"Failed to create voice call: {e}")
            return {"error": str(e)}
    
    async def create_phone_call(
        self, 
        phone_number: str, 
        user_id: str,
        config: VoiceCallConfig = None
    ) -> Dict[str, Any]:
        """
        Initiate an outbound phone call
        """
        if not self.vapi_key:
            return {"error": "Voice service not configured"}
        
        config = config or VoiceCallConfig()
        
        try:
            headers = {
                "Authorization": f"Bearer {self.vapi_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "phoneNumberId": os.environ.get("VAPI_PHONE_NUMBER_ID", ""),
                "customer": {
                    "number": phone_number
                },
                "assistant": {
                    "name": config.assistant_name,
                    "firstMessage": config.first_message,
                    "model": {
                        "provider": "openai",
                        "model": config.model,
                        "systemPrompt": self.system_prompt
                    },
                    "voice": {
                        "provider": "11labs",
                        "voiceId": config.voice_id
                    }
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{VAPI_BASE_URL}/call/phone",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 201:
                        data = await response.json()
                        
                        # Save to database
                        if self.db:
                            await self.db.aurem_voice_calls.insert_one({
                                "call_id": data.get("id"),
                                "user_id": user_id,
                                "phone_number": phone_number,
                                "status": "initiated",
                                "type": "outbound",
                                "created_at": datetime.now(timezone.utc)
                            })
                        
                        return {
                            "call_id": data.get("id"),
                            "status": "initiated",
                            "phone_number": phone_number
                        }
                    else:
                        error = await response.text()
                        return {"error": f"Failed to initiate call: {error}"}
                        
        except Exception as e:
            logger.error(f"Phone call error: {e}")
            return {"error": str(e)}
    
    async def end_call(self, call_id: str) -> Dict[str, Any]:
        """End an active call"""
        if call_id in self.active_calls:
            self.active_calls[call_id]["status"] = "ended"
            self.active_calls[call_id]["ended_at"] = datetime.now(timezone.utc).isoformat()
        
        if self.db:
            await self.db.aurem_voice_calls.update_one(
                {"call_id": call_id},
                {"$set": {
                    "status": "ended",
                    "ended_at": datetime.now(timezone.utc)
                }}
            )
        
        return {"call_id": call_id, "status": "ended"}
    
    async def get_call_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get voice call history for a user"""
        if not self.db:
            return []
        
        calls = await self.db.aurem_voice_calls.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return calls
    
    async def handle_vapi_webhook(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle Vapi webhook events (call status, transcripts, etc.)
        """
        event_type = event.get("type")
        call_id = event.get("call", {}).get("id")
        
        logger.info(f"[Voice] Webhook event: {event_type} for call {call_id}")
        
        if event_type == "call-started":
            if self.db:
                await self.db.aurem_voice_calls.update_one(
                    {"call_id": call_id},
                    {"$set": {"status": "in_progress", "started_at": datetime.now(timezone.utc)}}
                )
                
        elif event_type == "call-ended":
            duration = event.get("call", {}).get("duration")
            if self.db:
                await self.db.aurem_voice_calls.update_one(
                    {"call_id": call_id},
                    {"$set": {
                        "status": "completed",
                        "duration": duration,
                        "ended_at": datetime.now(timezone.utc)
                    }}
                )
                
        elif event_type == "transcript":
            transcript = event.get("transcript")
            if self.db and transcript:
                await self.db.aurem_voice_calls.update_one(
                    {"call_id": call_id},
                    {"$push": {"transcripts": transcript}}
                )
        
        return {"status": "processed", "event_type": event_type}
    
    def get_client_sdk_config(self) -> Dict[str, Any]:
        """
        Get configuration for initializing Vapi on the client side
        """
        return {
            "api_key": self.vapi_key if self.vapi_key else None,
            "available": bool(self.vapi_key),
            "sdk_url": "https://cdn.vapi.ai/vapi-web-sdk.js",
            "instructions": """
To enable voice-to-voice:
1. Include Vapi SDK: <script src="https://cdn.vapi.ai/vapi-web-sdk.js"></script>
2. Initialize: const vapi = new Vapi(apiKey);
3. Start call: vapi.start(assistantConfig);
4. Listen for events: vapi.on('speech-start', ...), vapi.on('speech-end', ...), etc.
            """
        }


# Singleton instance
_voice_service = None

def get_voice_service(db=None) -> AuremVoiceService:
    global _voice_service
    if _voice_service is None:
        _voice_service = AuremVoiceService(db)
    elif db and _voice_service.db is None:
        _voice_service.db = db
    return _voice_service
