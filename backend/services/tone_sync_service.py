"""
Tone Sync Service - Dynamic Personality for Vapi Voice AI
Real-time sentiment analysis for voice conversations with personality adjustment

Vibe Profiles:
- Mirror Mode: Match customer's energy level
- De-escalation Mode: Calm response to angry customers
- Concierge Mode: Soft, patient, detail-oriented
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ToneSyncService:
    """
    Manages dynamic tone adjustment for Vapi voice agents
    
    Analyzes live conversation transcripts and generates
    personality/tone adjustments without explicit announcement
    """
    
    def __init__(self, db=None):
        self.db = db
    
    async def analyze_voice_sentiment(
        self,
        tenant_id: str,
        conversation_id: str,
        transcript: str,
        speaker: str = "user"  # "user" or "assistant"
    ) -> Dict:
        """
        Analyze voice conversation sentiment and generate tone adjustment
        
        Args:
            tenant_id: Tenant identifier
            conversation_id: Voice conversation ID
            transcript: Latest transcript segment
            speaker: Who spoke (user or assistant)
        
        Returns:
            {
                "sentiment_score": float,
                "vibe_label": str,  # POSITIVE, NEUTRAL, CONCERNED, PANIC
                "recommended_tone": str,  # mirror, de-escalate, concierge
                "vapi_metadata": Dict,  # To send back to Vapi
                "should_alert": bool
            }
        """
        if self.db is None:
            logger.error("[ToneSync] Database not initialized")
            return {"error": "Database not initialized"}
        
        try:
            # Get tenant voice configuration
            tenant_config = await self._get_tenant_config(tenant_id)
            
            if not tenant_config:
                logger.warning(f"[ToneSync] Tenant not found: {tenant_id}")
                return {"error": "Tenant not found"}
            
            voice_config = tenant_config.get("voice_config", {})
            
            # Check if dynamic tone is enabled (default: yes)
            if not voice_config.get("dynamic_tone", True):
                return {"tone_adjustment": "disabled"}
            
            # Analyze sentiment using existing sentiment analyzer
            from services.sentiment_analyzer import analyze_message_sentiment
            
            sentiment_result = await analyze_message_sentiment(
                message=transcript,
                conversation_history=None,  # Voice is real-time, no history needed
                custom_keywords=tenant_config.get("panic_config", {}).get("custom_keywords", [])
            )
            
            # Map sentiment to vibe label
            sentiment_score = sentiment_result["sentiment_score"]
            
            if sentiment_score >= 0.5:
                vibe_label = "POSITIVE"
            elif sentiment_score >= -0.2:
                vibe_label = "NEUTRAL"
            elif sentiment_score >= -0.7:
                vibe_label = "CONCERNED"
            else:
                vibe_label = "PANIC"
            
            # Determine recommended tone based on vibe and preference
            vibe_preference = voice_config.get("vibe_preference", "mirror")
            recommended_tone = self._get_recommended_tone(
                vibe_label=vibe_label,
                preference=vibe_preference,
                emotion=sentiment_result["emotion"]
            )
            
            # Generate Vapi metadata for tone adjustment
            vapi_metadata = self._generate_vapi_instructions(
                tone=recommended_tone,
                vibe_label=vibe_label,
                emotion=sentiment_result["emotion"]
            )
            
            # Check if we should trigger panic alert for voice
            should_alert = (
                vibe_label == "PANIC" and 
                tenant_config.get("panic_config", {}).get("enabled", True)
            )
            
            # Log tone adjustment
            await self._log_tone_adjustment(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                sentiment_score=sentiment_score,
                vibe_label=vibe_label,
                recommended_tone=recommended_tone,
                transcript=transcript
            )
            
            logger.info(f"[ToneSync] {conversation_id}: {vibe_label} → {recommended_tone} (score: {sentiment_score:.2f})")
            
            return {
                "sentiment_score": sentiment_score,
                "vibe_label": vibe_label,
                "emotion": sentiment_result["emotion"],
                "recommended_tone": recommended_tone,
                "vapi_metadata": vapi_metadata,
                "should_alert": should_alert,
                "detected_keywords": sentiment_result.get("detected_keywords", []),
                "detected_language": sentiment_result.get("detected_language", "en"),
                "english_translation": sentiment_result.get("english_translation", transcript)
            }
        
        except Exception as e:
            logger.error(f"[ToneSync] Analysis error: {e}", exc_info=True)
            return {"error": str(e)}
    
    def _get_recommended_tone(
        self,
        vibe_label: str,
        preference: str,
        emotion: str
    ) -> str:
        """
        Determine recommended tone based on vibe and preference
        
        Args:
            vibe_label: POSITIVE, NEUTRAL, CONCERNED, PANIC
            preference: mirror, de-escalate, concierge
            emotion: Customer's detected emotion
        
        Returns:
            Tone instruction (mirror, calm, concierge)
        """
        # De-escalation mode: Always calm for negative vibes
        if preference == "de-escalate" and vibe_label in ["CONCERNED", "PANIC"]:
            return "calm"
        
        # Concierge mode: Always patient and detailed
        if preference == "concierge":
            return "concierge"
        
        # Mirror mode (default): Match customer's energy
        if vibe_label == "POSITIVE":
            return "mirror_energetic"
        elif vibe_label == "NEUTRAL":
            return "mirror_neutral"
        elif vibe_label == "CONCERNED":
            return "empathetic"
        else:  # PANIC
            return "calm"
    
    def _generate_vapi_instructions(
        self,
        tone: str,
        vibe_label: str,
        emotion: str
    ) -> Dict:
        """
        Generate metadata to send back to Vapi for tone adjustment
        
        This instructs Vapi's voice AI to adjust:
        - Speaking pace
        - Pitch
        - Pausing
        - Word choice
        
        WITHOUT explicitly announcing the change
        """
        
        tone_profiles = {
            "mirror_energetic": {
                "pace": "slightly faster",
                "pitch": "normal to slightly higher",
                "pause_duration": "brief",
                "personality_hint": "Match the customer's positive energy. Be enthusiastic but professional."
            },
            "mirror_neutral": {
                "pace": "moderate",
                "pitch": "normal",
                "pause_duration": "normal",
                "personality_hint": "Maintain a balanced, professional tone. Clear and efficient."
            },
            "empathetic": {
                "pace": "slightly slower",
                "pitch": "slightly lower, warmer",
                "pause_duration": "slightly longer",
                "personality_hint": "Show understanding and patience. Acknowledge concerns without being robotic."
            },
            "calm": {
                "pace": "slow and steady",
                "pitch": "lower and soothing",
                "pause_duration": "longer pauses",
                "personality_hint": "De-escalate with a calm, reassuring presence. Lower energy, higher patience."
            },
            "concierge": {
                "pace": "slow and deliberate",
                "pitch": "soft and pleasant",
                "pause_duration": "generous pauses",
                "personality_hint": "White-glove service mindset. Patient, detail-oriented, never rushed."
            }
        }
        
        profile = tone_profiles.get(tone, tone_profiles["mirror_neutral"])
        
        # Create system prompt update for Vapi
        system_prompt_addition = f"""
CURRENT CUSTOMER VIBE: {vibe_label}
TONE ADJUSTMENT: {tone.upper()}

Adjust your delivery naturally:
- Pace: {profile['pace']}
- Pitch: {profile['pitch']}
- Pauses: {profile['pause_duration']}

{profile['personality_hint']}

CRITICAL: Do NOT announce this adjustment. Do NOT say "I sense you're frustrated" or "Let me slow down for you." 
Simply embody the tone naturally as if it's your default personality.
"""
        
        return {
            "tone_profile": tone,
            "vibe_label": vibe_label,
            "system_prompt_addition": system_prompt_addition,
            "voice_settings": {
                "pace_modifier": profile["pace"],
                "pitch_modifier": profile["pitch"]
            }
        }
    
    async def _log_tone_adjustment(
        self,
        tenant_id: str,
        conversation_id: str,
        sentiment_score: float,
        vibe_label: str,
        recommended_tone: str,
        transcript: str
    ):
        """Log tone adjustment to database for analytics"""
        try:
            log_entry = {
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "sentiment_score": sentiment_score,
                "vibe_label": vibe_label,
                "recommended_tone": recommended_tone,
                "transcript_sample": transcript[:200],  # First 200 chars
                "timestamp": datetime.now(timezone.utc)
            }
            
            await self.db.tone_sync_log.insert_one(log_entry)
        except Exception as e:
            logger.warning(f"[ToneSync] Error logging adjustment: {e}")
    
    async def _get_tenant_config(self, tenant_id: str) -> Optional[Dict]:
        """Get tenant configuration from database"""
        try:
            tenant = await self.db.users.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0}
            )
            return tenant
        except Exception as e:
            logger.error(f"[ToneSync] Error fetching tenant: {e}")
            return None


# Singleton instance
_tone_sync_service = None


def get_tone_sync_service(db=None) -> ToneSyncService:
    """Get or create tone sync service instance"""
    global _tone_sync_service
    if _tone_sync_service is None or db is not None:
        _tone_sync_service = ToneSyncService(db)
    return _tone_sync_service
