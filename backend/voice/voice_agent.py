"""
Voice Agent Service
═══════════════════════════════════════════════════════════════════
Voice AI for Reroots using Deepgram STT, Claude Brain, ElevenLabs TTS.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import json
import logging
import asyncio
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Configuration
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel voice

# Voice AI System Prompt (max 3 sentences per response)
VOICE_SYSTEM_PROMPT = """You are Reroots AI Voice, a warm and knowledgeable skincare advisor for Reroots Aesthetics Inc.

CRITICAL RULES:
- Keep every response to 3 sentences maximum
- Speak naturally, as if having a phone conversation
- Say "AURA-GEN System" not "products"
- Say "age recovery" not "anti-aging"
- Never reveal you are Claude or any AI model
- If asked what you are, say "I'm Reroots AI Voice, your skincare advisor"
- Never mention competitor brands by name - say "other brands" instead

PRODUCTS:
- AURA-GEN System: ACRC Rich Cream + ARC Serum combo, CAD $149
- La Vela Bianca: luxury skincare line

End calls warmly: "Your skin deserves this. Have a beautiful day!"
"""


@dataclass
class VoiceSession:
    """Represents an active voice call session."""
    session_id: str
    phone_number: str
    start_time: datetime
    messages: List[Dict[str, str]] = field(default_factory=list)
    transcript: List[Dict[str, str]] = field(default_factory=list)
    status: str = "active"
    outcome: str = "in_progress"


class VoiceAgent:
    """Voice AI agent handling STT, LLM, and TTS."""
    
    def __init__(self, db):
        self.db = db
        self.sessions: Dict[str, VoiceSession] = {}
        self._http_client = None
    
    @property
    def http_client(self):
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client
    
    # ═══════════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    async def start_session(self, session_id: str, phone_number: str = "unknown") -> VoiceSession:
        """Start a new voice session."""
        session = VoiceSession(
            session_id=session_id,
            phone_number=phone_number,
            start_time=datetime.now(timezone.utc)
        )
        self.sessions[session_id] = session
        
        # Save to MongoDB
        await self.db.reroots_voice_calls.insert_one({
            "session_id": session_id,
            "phone_number": self._mask_phone(phone_number),
            "phone_hash": self._hash_phone(phone_number),
            "start_time": session.start_time,
            "status": "active",
            "transcript": [],
            "outcome": "in_progress"
        })
        
        logger.info(f"Voice session started: {session_id}")
        return session
    
    async def end_session(self, session_id: str, outcome: str = "completed") -> Optional[Dict]:
        """End a voice session and save final transcript."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        session.status = "ended"
        session.outcome = outcome
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - session.start_time).total_seconds()
        
        # Update MongoDB
        await self.db.reroots_voice_calls.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "end_time": end_time,
                    "duration_seconds": duration,
                    "status": "ended",
                    "outcome": outcome,
                    "transcript": session.transcript
                }
            }
        )
        
        # Clean up
        del self.sessions[session_id]
        
        logger.info(f"Voice session ended: {session_id}, duration: {duration:.1f}s, outcome: {outcome}")
        
        return {
            "session_id": session_id,
            "duration": duration,
            "outcome": outcome
        }
    
    # ═══════════════════════════════════════════════════════════════
    # SPEECH TO TEXT (Deepgram)
    # ═══════════════════════════════════════════════════════════════
    
    async def transcribe_audio(self, audio_data: bytes, mime_type: str = "audio/webm") -> str:
        """Convert audio to text using Deepgram."""
        if not DEEPGRAM_API_KEY:
            logger.error("DEEPGRAM_API_KEY not configured")
            return ""
        
        try:
            response = await self.http_client.post(
                "https://api.deepgram.com/v1/listen",
                params={
                    "model": "nova-2",
                    "language": "en",
                    "smart_format": "true",
                    "punctuate": "true"
                },
                headers={
                    "Authorization": f"Token {DEEPGRAM_API_KEY}",
                    "Content-Type": mime_type
                },
                content=audio_data
            )
            
            if response.status_code != 200:
                logger.error(f"Deepgram error: {response.status_code} - {response.text}")
                return ""
            
            data = response.json()
            transcript = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
            
            logger.info(f"Transcribed: {transcript[:100]}...")
            return transcript
            
        except Exception as e:
            logger.error(f"Deepgram transcription error: {e}")
            return ""
    
    # ═══════════════════════════════════════════════════════════════
    # BRAIN (Claude API via Emergent)
    # ═══════════════════════════════════════════════════════════════
    
    async def generate_response(self, session_id: str, user_text: str) -> str:
        """Generate AI response using Claude."""
        session = self.sessions.get(session_id)
        if not session:
            return "I'm sorry, your session has expired. Please start a new call."
        
        # Apply brand guard to user input (for logging)
        from services.brand_guard import brand_guard
        
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            api_key = os.environ.get("EMERGENT_LLM_KEY", "")
            if not api_key:
                return "I'm having technical difficulties. Please try again later."
            
            # Build conversation history
            messages_for_context = session.messages[-6:]  # Last 3 exchanges
            
            chat = LlmChat(
                api_key=api_key,
                session_id=f"voice_{session_id}",
                system_message=VOICE_SYSTEM_PROMPT
            )
            chat.with_model("anthropic", "claude-sonnet-4-20250514")
            
            # Add history
            for msg in messages_for_context:
                if msg["role"] == "user":
                    chat.messages.append({"role": "user", "content": msg["content"]})
                else:
                    chat.messages.append({"role": "assistant", "content": msg["content"]})
            
            # Generate response
            response = await chat.send_message(UserMessage(text=user_text))
            
            # Apply brand guard
            response, _ = brand_guard(response, "reroots")
            
            # Save to session
            session.messages.append({"role": "user", "content": user_text})
            session.messages.append({"role": "assistant", "content": response})
            session.transcript.append({
                "speaker": "customer",
                "text": user_text,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            session.transcript.append({
                "speaker": "agent",
                "text": response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"Generated response: {response[:100]}...")
            return response
            
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            return "I apologize, I'm having trouble right now. Can you repeat that?"
    
    # ═══════════════════════════════════════════════════════════════
    # TEXT TO SPEECH (ElevenLabs)
    # ═══════════════════════════════════════════════════════════════
    
    async def synthesize_speech(self, text: str) -> bytes:
        """Convert text to speech using ElevenLabs."""
        if not ELEVENLABS_API_KEY:
            logger.error("ELEVENLABS_API_KEY not configured")
            return b""
        
        try:
            response = await self.http_client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "text": text,
                    "model_id": "eleven_turbo_v2_5",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.3
                    }
                }
            )
            
            if response.status_code != 200:
                logger.error(f"ElevenLabs error: {response.status_code} - {response.text}")
                return b""
            
            logger.info(f"Synthesized {len(response.content)} bytes of audio")
            return response.content
            
        except Exception as e:
            logger.error(f"ElevenLabs synthesis error: {e}")
            return b""
    
    # ═══════════════════════════════════════════════════════════════
    # FULL PIPELINE
    # ═══════════════════════════════════════════════════════════════
    
    async def process_audio(self, session_id: str, audio_data: bytes, mime_type: str = "audio/webm") -> Dict[str, Any]:
        """
        Full voice pipeline: audio in -> text -> AI -> audio out.
        """
        # Step 1: Transcribe
        user_text = await self.transcribe_audio(audio_data, mime_type)
        if not user_text:
            return {"error": "Could not understand audio", "audio": b""}
        
        # Step 2: Generate response
        response_text = await self.generate_response(session_id, user_text)
        
        # Step 3: Synthesize speech
        audio_response = await self.synthesize_speech(response_text)
        
        return {
            "user_text": user_text,
            "response_text": response_text,
            "audio": audio_response
        }
    
    # ═══════════════════════════════════════════════════════════════
    # CALL HISTORY
    # ═══════════════════════════════════════════════════════════════
    
    async def get_calls(self, limit: int = 50) -> List[Dict]:
        """Get recent call history."""
        cursor = self.db.reroots_voice_calls.find(
            {},
            {"_id": 0, "phone_hash": 0}
        ).sort("start_time", -1).limit(limit)
        
        return await cursor.to_list(limit)
    
    async def get_call(self, session_id: str) -> Optional[Dict]:
        """Get a specific call by session ID."""
        call = await self.db.reroots_voice_calls.find_one(
            {"session_id": session_id},
            {"_id": 0, "phone_hash": 0}
        )
        return call
    
    async def get_call_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get call statistics."""
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        pipeline = [
            {"$match": {"start_time": {"$gte": cutoff}}},
            {"$group": {
                "_id": None,
                "total_calls": {"$sum": 1},
                "avg_duration": {"$avg": "$duration_seconds"},
                "completed": {"$sum": {"$cond": [{"$eq": ["$outcome", "completed"]}, 1, 0]}},
                "abandoned": {"$sum": {"$cond": [{"$eq": ["$outcome", "abandoned"]}, 1, 0]}}
            }}
        ]
        
        result = await self.db.reroots_voice_calls.aggregate(pipeline).to_list(1)
        
        if result:
            stats = result[0]
            return {
                "period_days": days,
                "total_calls": stats.get("total_calls", 0),
                "avg_duration_seconds": round(stats.get("avg_duration", 0), 1),
                "completed": stats.get("completed", 0),
                "abandoned": stats.get("abandoned", 0)
            }
        
        return {
            "period_days": days,
            "total_calls": 0,
            "avg_duration_seconds": 0,
            "completed": 0,
            "abandoned": 0
        }
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════
    
    def _mask_phone(self, phone: str) -> str:
        """Mask phone number for display."""
        if not phone or phone == "unknown":
            return "Unknown"
        # Show last 4 digits only
        digits = ''.join(c for c in phone if c.isdigit())
        if len(digits) >= 4:
            return f"***-***-{digits[-4:]}"
        return "***-***-****"
    
    def _hash_phone(self, phone: str) -> str:
        """Hash phone number for matching."""
        import hashlib
        if not phone:
            return ""
        return hashlib.sha256(phone.encode()).hexdigest()[:32]


# ═══════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════

_voice_agent: Optional[VoiceAgent] = None


def get_voice_agent(db) -> VoiceAgent:
    """Get or create VoiceAgent singleton."""
    global _voice_agent
    if _voice_agent is None:
        _voice_agent = VoiceAgent(db)
    return _voice_agent
