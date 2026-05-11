"""
AUREM Multi-Modal Message Processor
Handles text, audio, images, and video intelligently
Tier 3 Premium Feature
"""

import os
import logging
import aiohttp
import base64
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Supported message types"""
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"


class MultiModalProcessor:
    """
    Intelligent Multi-Modal Message Processing
    - Auto-detects message type (text, audio, image, video)
    - Routes to appropriate processing pipeline
    - Converts non-text to text for AI processing
    - Maintains context across modalities
    """
    
    def __init__(self):
        self.api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        self.max_image_size = 20 * 1024 * 1024  # 20MB
        self.max_audio_duration = 300  # 5 minutes in seconds
    
    def detect_message_type(self, message_data: Dict[str, Any]) -> MessageType:
        """Auto-detect message type from WhatsApp/channel data"""
        
        # WhatsApp message type field
        if "type" in message_data:
            type_map = {
                "text": MessageType.TEXT,
                "audio": MessageType.AUDIO,
                "image": MessageType.IMAGE,
                "video": MessageType.VIDEO,
                "document": MessageType.DOCUMENT,
                "ptt": MessageType.AUDIO,  # Push-to-talk voice note
                "voice": MessageType.AUDIO
            }
            return type_map.get(message_data["type"], MessageType.TEXT)
        
        # Fallback - check for content type
        if "content_type" in message_data:
            content_type = message_data["content_type"].lower()
            if content_type.startswith("image/"):
                return MessageType.IMAGE
            elif content_type.startswith("audio/"):
                return MessageType.AUDIO
            elif content_type.startswith("video/"):
                return MessageType.VIDEO
        
        # Default to text
        return MessageType.TEXT
    
    async def process_message(
        self,
        message_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Main processing entry point
        Routes message to appropriate handler based on type
        """
        message_type = self.detect_message_type(message_data)
        
        logger.info(f"Processing {message_type.value} message")
        
        # Route to appropriate processor
        if message_type == MessageType.TEXT:
            return await self._process_text(message_data, context)
        elif message_type == MessageType.AUDIO:
            return await self._process_audio(message_data, context)
        elif message_type == MessageType.IMAGE:
            return await self._process_image(message_data, context)
        elif message_type == MessageType.VIDEO:
            return await self._process_video(message_data, context)
        elif message_type == MessageType.DOCUMENT:
            return await self._process_document(message_data, context)
        
        return {
            "type": MessageType.TEXT.value,
            "text": message_data.get("content", ""),
            "processed": False
        }
    
    async def _process_text(
        self,
        message_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process text message (passthrough)"""
        return {
            "type": MessageType.TEXT.value,
            "text": message_data.get("content", ""),
            "processed": True,
            "metadata": {}
        }
    
    async def _process_audio(
        self,
        message_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process audio message
        - Downloads audio file
        - Transcribes using OpenAI Whisper
        - Returns text transcript
        """
        audio_url = message_data.get("media_url") or message_data.get("url")
        
        if not audio_url:
            return {
                "type": MessageType.AUDIO.value,
                "text": "[Audio message received but URL unavailable]",
                "processed": False,
                "error": "No audio URL provided"
            }
        
        try:
            # Download audio file
            audio_data = await self._download_media(audio_url)
            
            # Transcribe using Whisper via Emergent LLM
            transcript = await self._transcribe_audio(audio_data)
            
            return {
                "type": MessageType.AUDIO.value,
                "text": transcript,
                "processed": True,
                "metadata": {
                    "original_url": audio_url,
                    "transcription_engine": "whisper"
                }
            }
            
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return {
                "type": MessageType.AUDIO.value,
                "text": "[Audio message - transcription failed]",
                "processed": False,
                "error": str(e)
            }
    
    async def _process_image(
        self,
        message_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process image message
        - Downloads image
        - Analyzes using GPT-4o Vision
        - Returns description as text hint for AI
        """
        image_url = message_data.get("media_url") or message_data.get("url")
        
        if not image_url:
            return {
                "type": MessageType.IMAGE.value,
                "text": "[Image received but URL unavailable]",
                "processed": False,
                "error": "No image URL provided"
            }
        
        try:
            # Download image
            image_data = await self._download_media(image_url)
            
            # Analyze using Vision
            description = await self._analyze_image(image_data, context)
            
            # Format as system hint for AI
            text_hint = f"[Customer sent an image. Vision analysis: {description}]"
            
            return {
                "type": MessageType.IMAGE.value,
                "text": text_hint,
                "processed": True,
                "metadata": {
                    "original_url": image_url,
                    "vision_description": description,
                    "analysis_engine": "gpt-4o-vision"
                }
            }
            
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return {
                "type": MessageType.IMAGE.value,
                "text": "[Image received - analysis unavailable]",
                "processed": False,
                "error": str(e)
            }
    
    async def _process_video(
        self,
        message_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process video message - extract first frame and analyze"""
        return {
            "type": MessageType.VIDEO.value,
            "text": "[Video message received - analysis coming soon]",
            "processed": False,
            "metadata": {}
        }
    
    async def _process_document(
        self,
        message_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process document - extract text if PDF"""
        return {
            "type": MessageType.DOCUMENT.value,
            "text": "[Document received - processing coming soon]",
            "processed": False,
            "metadata": {}
        }
    
    async def _download_media(self, url: str) -> bytes:
        """Download media file from URL"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download media: HTTP {response.status}")
                return await response.read()
    
    async def _transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio using OpenAI Whisper via Emergent LLM"""
        try:
            from emergentintegrations.llm.openai.audio_transcription import OpenAIAudioTranscription
            
            transcriber = OpenAIAudioTranscription(api_key=self.api_key)
            
            # Whisper expects file-like object or path
            # For now, we'll use a simple approach
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name
            
            try:
                result = await transcriber.transcribe(tmp_path)
                transcript = result.get("text", "")
            finally:
                import os
                os.unlink(tmp_path)
            
            return transcript or "[Transcription returned empty]"
            
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            raise
    
    async def _analyze_image(
        self,
        image_data: bytes,
        context: Dict[str, Any]
    ) -> str:
        """Analyze image using GPT-4o Vision via emergentintegrations.

        iter 322ar — real vision call (was returning a hard-coded placeholder).
        Passes the base64 image as an `ImageContent` part on a `UserMessage`,
        which the emergentintegrations LlmChat wraps into OpenAI's
        multimodal `content` array."""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

            image_base64 = base64.b64encode(image_data).decode("utf-8")
            business_context = (context or {}).get("business_name", "our business")
            prompt = (
                f"You are analyzing an image sent by a customer to {business_context}.\n\n"
                "Describe this image in detail, focusing on:\n"
                "1. What is shown in the image\n"
                "2. Any text visible in the image\n"
                "3. Potential customer intent (e.g., showing damage, asking about a product, sharing results)\n"
                "4. Any actionable information\n\n"
                "Be concise but thorough. This description will be used to help an AI assistant respond appropriately."
            )

            chat = LlmChat(
                api_key=self.api_key,
                session_id="vision_analysis",
                system_message="You are a multimodal customer-support analyst.",
            ).with_model("openai", "gpt-4o")

            msg = UserMessage(
                text=prompt,
                file_contents=[ImageContent(image_base64=image_base64)],
            )
            response = await chat.send_message(msg)
            # emergentintegrations may return a string OR an object with .content
            return str(response) if response is not None else "[Vision returned no content]"

        except Exception as e:
            logger.error(f"Vision analysis error: {e}")
            return f"Image received but analysis failed: {str(e)[:160]}"


# Singleton
_multimodal_processor = None

def get_multimodal_processor():
    global _multimodal_processor
    if _multimodal_processor is None:
        _multimodal_processor = MultiModalProcessor()
    return _multimodal_processor
