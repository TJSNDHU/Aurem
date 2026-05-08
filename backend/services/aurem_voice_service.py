"""
AUREM DIY Voice Service — Real Voice-to-Voice Conversation
Uses browser-native Web Speech API (STT) + Emergent LLM for AI responses
+ optional browser SpeechSynthesis (TTS) on the client side.

No Vapi dependency. Fully self-hosted voice engine.
"""

import os
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# LLM Configuration for voice AI responses
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


class VoiceCallConfig(BaseModel):
    """Configuration for DIY voice calls"""
    assistant_name: str = "AUREM"
    first_message: str = "Hello, I'm AUREM, your AI business partner. How can I help you today?"
    language: str = "en-US"
    voice_name: str = "Google UK English Female"  # Browser SpeechSynthesis voice
    speech_rate: float = 1.0
    pitch: float = 1.0


class AuremVoiceService:
    """
    AUREM DIY Voice Service for real voice-to-voice conversations.
    Architecture:
      - Client: Web Speech API (SpeechRecognition for STT, SpeechSynthesis for TTS)
      - Backend: Emergent LLM Key for AI response generation + Tone Sync engine
    """

    def __init__(self, db=None):
        self.db = db
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
        Create a web-based voice call session.
        Returns configuration for the client-side DIY voice engine
        (Web Speech API for STT/TTS + backend AI for responses).
        """
        config = config or VoiceCallConfig()
        call_id = str(uuid.uuid4())

        try:
            # DIY assistant configuration — processed client-side
            assistant_config = {
                "name": config.assistant_name,
                "firstMessage": config.first_message,
                "systemPrompt": self.system_prompt,
                "language": config.language,
                "voice": {
                    "provider": "browser",
                    "name": config.voice_name,
                    "rate": config.speech_rate,
                    "pitch": config.pitch,
                },
                "stt": {
                    "provider": "browser",
                    "continuous": True,
                    "interimResults": True,
                    "language": config.language,
                },
                "maxDurationSeconds": 600,
            }

            self.active_calls[call_id] = {
                "user_id": user_id,
                "config": assistant_config,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "ready",
            }

            if self.db is not None:
                await self.db.aurem_voice_calls.insert_one({
                    "call_id": call_id,
                    "user_id": user_id,
                    "config": assistant_config,
                    "provider": "aurem_diy",
                    "status": "ready",
                    "created_at": datetime.now(timezone.utc),
                })

            return {
                "call_id": call_id,
                "assistant_config": assistant_config,
                "available": True,
                "status": "ready",
                "engine": "aurem_diy",
                "instructions": "Uses browser Web Speech API for STT/TTS. AI responses via AUREM backend.",
            }

        except Exception as e:
            logger.error(f"Failed to create voice call: {e}")
            return {"error": str(e)}

    async def generate_ai_response(self, call_id: str, user_message: str, conversation_history: list = None) -> Dict[str, Any]:
        """
        Generate an AI voice response using Emergent LLM Key.
        Called by the client after each user speech turn.
        """
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage

            # Build conversation context
            context_parts = []
            for msg in (conversation_history or []):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context_parts.append(f"{'User' if role == 'user' else 'Assistant'}: {content}")
            context_parts.append(f"User: {user_message}")
            full_context = "\n".join(context_parts[-10:])

            llm = LlmChat(
                api_key=self.llm_key,
                session_id=call_id or "voice_session",
                system_message=self.system_prompt,
            ).with_model("openai", "gpt-4o")

            ai_text = await llm.send_message(UserMessage(text=full_context))

            return {"success": True, "response": ai_text, "call_id": call_id}

        except Exception as e:
            logger.error(f"AI voice response error: {e}")
            return {"error": str(e), "response": "I apologize, I'm having trouble responding right now. Could you repeat that?"}

    async def end_call(self, call_id: str) -> Dict[str, Any]:
        """End an active call"""
        if call_id in self.active_calls:
            self.active_calls[call_id]["status"] = "ended"
            self.active_calls[call_id]["ended_at"] = datetime.now(timezone.utc).isoformat()

        if self.db is not None:
            await self.db.aurem_voice_calls.update_one(
                {"call_id": call_id},
                {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc)}},
            )

        return {"call_id": call_id, "status": "ended"}

    async def get_call_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get voice call history for a user"""
        if self.db is None:
            return []

        calls = await self.db.aurem_voice_calls.find(
            {"user_id": user_id},
            {"_id": 0},
        ).sort("created_at", -1).limit(limit).to_list(limit)

        return calls

    async def handle_voice_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle voice events from the DIY engine"""
        event_type = event.get("type")
        call_id = event.get("call", {}).get("id")

        logger.info(f"[Voice] Event: {event_type} for call {call_id}")

        if event_type == "call-started":
            if self.db is not None:
                await self.db.aurem_voice_calls.update_one(
                    {"call_id": call_id},
                    {"$set": {"status": "in_progress", "started_at": datetime.now(timezone.utc)}},
                )

        elif event_type == "call-ended":
            duration = event.get("call", {}).get("duration")
            if self.db is not None:
                await self.db.aurem_voice_calls.update_one(
                    {"call_id": call_id},
                    {"$set": {"status": "completed", "duration": duration, "ended_at": datetime.now(timezone.utc)}},
                )

        elif event_type == "transcript":
            transcript = event.get("transcript")
            if self.db is not None and transcript:
                await self.db.aurem_voice_calls.update_one(
                    {"call_id": call_id},
                    {"$push": {"transcripts": transcript}},
                )

        return {"status": "processed", "event_type": event_type}

    def get_client_config(self) -> Dict[str, Any]:
        """
        Get configuration for the AUREM DIY Voice Engine on the client.
        No external SDK needed — uses browser-native APIs.
        """
        return {
            "available": True,
            "engine": "aurem_diy",
            "stt": {"provider": "browser", "api": "SpeechRecognition"},
            "tts": {"provider": "browser", "api": "SpeechSynthesis"},
            "ai": {"provider": "aurem_backend", "endpoint": "/api/aurem/voice/respond"},
            "instructions": "AUREM DIY Voice Engine — browser Web Speech API for STT/TTS, AUREM backend for AI responses.",
        }


# Singleton instance
_voice_service = None


def get_voice_service(db=None) -> AuremVoiceService:
    global _voice_service
    if _voice_service is None:
        _voice_service = AuremVoiceService(db)
    elif db is not None and _voice_service.db is None:
        _voice_service.db = db
    return _voice_service
