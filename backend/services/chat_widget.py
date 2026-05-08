"""
Chat Widget Service
═══════════════════════════════════════════════════════════════════
Backend service for the embeddable chat widget.
Handles sessions, messages, rate limiting, and audit logging.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brands_config import (
    get_brand_config, 
    get_protected_system_prompt,
    get_response_watermark,
    is_valid_brand_key
)
from services.brand_guard import brand_guard
from services.customer_memory import get_customer_memory

logger = logging.getLogger(__name__)

# Rate limiting: 20 messages per session per hour
RATE_LIMIT_MAX_MESSAGES = 20
RATE_LIMIT_WINDOW_HOURS = 1


class ChatWidgetService:
    """Service for managing chat widget sessions and messages."""
    
    def __init__(self, db):
        self.db = db
        self._chat_sessions: Dict[str, Any] = {}
    
    # ═══════════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    async def create_session(
        self,
        brand_key: str,
        ip_address: str,
        user_agent: str
    ) -> Dict[str, Any]:
        """
        Create a new chat session with audit trail.
        """
        if not is_valid_brand_key(brand_key):
            raise ValueError(f"Invalid brand key: {brand_key}")
        
        config = get_brand_config(brand_key)
        
        # Generate session ID
        session_id = self._generate_session_id(brand_key, ip_address)
        
        # Create session document
        session_doc = {
            "session_id": session_id,
            "brand_key": brand_key,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.now(timezone.utc),
            "last_activity": datetime.now(timezone.utc),
            "message_count": 0,
            "status": "active"
        }
        
        # Store in MongoDB with brand-specific collection
        collection_name = f"{config.collection_prefix}chat_sessions"
        await self.db[collection_name].insert_one(session_doc)
        
        logger.info(f"Chat session created: {session_id[:16]}... for {brand_key}")
        
        return {
            "session_id": session_id,
            "brand_key": brand_key,
            "ai_name": config.ai_name,
            "primary_color": config.primary_color,
            "logo_path": config.logo_path,
            "powered_by_text": config.powered_by_text,
            "copyright_footer": config.copyright_footer
        }
    
    async def get_session(self, session_id: str, brand_key: str) -> Optional[Dict]:
        """Get session by ID, ensuring brand isolation."""
        config = get_brand_config(brand_key)
        if not config:
            return None
        
        collection_name = f"{config.collection_prefix}chat_sessions"
        session = await self.db[collection_name].find_one({
            "session_id": session_id,
            "brand_key": brand_key  # Enforce brand isolation
        })
        
        return session
    
    # ═══════════════════════════════════════════════════════════════
    # RATE LIMITING
    # ═══════════════════════════════════════════════════════════════
    
    async def check_rate_limit(self, session_id: str, brand_key: str) -> Dict[str, Any]:
        """
        Check if session has exceeded rate limit.
        Returns: {allowed: bool, remaining: int, reset_at: datetime}
        """
        config = get_brand_config(brand_key)
        if not config:
            return {"allowed": False, "remaining": 0, "error": "Invalid brand"}
        
        collection_name = f"{config.collection_prefix}chat_messages"
        
        # Count messages in the last hour
        window_start = datetime.now(timezone.utc) - timedelta(hours=RATE_LIMIT_WINDOW_HOURS)
        
        message_count = await self.db[collection_name].count_documents({
            "session_id": session_id,
            "direction": "user",
            "timestamp": {"$gte": window_start}
        })
        
        remaining = max(0, RATE_LIMIT_MAX_MESSAGES - message_count)
        allowed = remaining > 0
        
        # Calculate reset time (next hour boundary)
        reset_at = window_start + timedelta(hours=RATE_LIMIT_WINDOW_HOURS)
        
        return {
            "allowed": allowed,
            "remaining": remaining,
            "limit": RATE_LIMIT_MAX_MESSAGES,
            "reset_at": reset_at.isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════════
    # MESSAGE HANDLING
    # ═══════════════════════════════════════════════════════════════
    
    async def send_message(
        self,
        session_id: str,
        brand_key: str,
        user_message: str,
        ip_address: str,
        user_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process user message and generate AI response.
        Includes rate limiting, brand guard, and audit logging.
        
        CROSS-DEVICE MEMORY: If user_email is provided, the conversation
        memory is stored against the user's account, not just the session.
        """
        config = get_brand_config(brand_key)
        if not config:
            raise ValueError(f"Invalid brand key: {brand_key}")
        
        # Check rate limit
        rate_check = await self.check_rate_limit(session_id, brand_key)
        if not rate_check["allowed"]:
            return {
                "success": False,
                "error": "rate_limited",
                "message": "Please try again later or contact us directly.",
                "reset_at": rate_check["reset_at"]
            }
        
        # Verify session exists and belongs to this brand
        session = await self.get_session(session_id, brand_key)
        if not session:
            raise ValueError("Invalid session")
        
        collection_name = f"{config.collection_prefix}chat_messages"
        
        # Log user message with audit trail
        user_msg_doc = {
            "session_id": session_id,
            "brand_key": brand_key,
            "direction": "user",
            "content": user_message,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc)
        }
        # Track account email for cross-device queries
        if user_email:
            user_msg_doc["account_email"] = user_email.lower()
        await self.db[collection_name].insert_one(user_msg_doc)
        
        # Generate AI response
        ai_response = await self._generate_ai_response(
            session_id=session_id,
            brand_key=brand_key,
            user_message=user_message,
            user_email=user_email
        )
        
        # Apply brand guard
        sanitized_response, was_modified = brand_guard(ai_response, brand_key)
        
        # Get watermark
        watermark = get_response_watermark(brand_key)
        
        # Log AI response with watermark
        ai_msg_doc = {
            "session_id": session_id,
            "brand_key": brand_key,
            "direction": "assistant",
            "content": sanitized_response,
            "timestamp": datetime.now(timezone.utc),
            "generated_by": watermark,  # Hidden watermark field
            "brand_guard_modified": was_modified
        }
        # Track account email for cross-device queries
        if user_email:
            ai_msg_doc["account_email"] = user_email.lower()
        await self.db[collection_name].insert_one(ai_msg_doc)
        
        # Update session activity
        sessions_collection = f"{config.collection_prefix}chat_sessions"
        await self.db[sessions_collection].update_one(
            {"session_id": session_id},
            {
                "$set": {"last_activity": datetime.now(timezone.utc)},
                "$inc": {"message_count": 1}
            }
        )
        
        return {
            "success": True,
            "response": sanitized_response,
            "remaining_messages": rate_check["remaining"] - 1
        }
    
    async def _generate_ai_response(
        self,
        session_id: str,
        brand_key: str,
        user_message: str,
        user_email: Optional[str] = None
    ) -> str:
        """
        Generate AI response using LLM with brand-specific system prompt, 
        customer memory, and multilingual support.
        
        CROSS-DEVICE MEMORY: If user_email is provided, loads and updates
        the account-based profile for personalization across devices.
        """
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        config = get_brand_config(brand_key)
        base_system_prompt = get_protected_system_prompt(brand_key)
        
        # ═══════════════════════════════════════════════════════════════
        # MULTILINGUAL: Detect customer language
        # ═══════════════════════════════════════════════════════════════
        detected_language = "en"
        language_prompt_addon = ""
        
        try:
            from utils.language import process_multilingual_message, get_multilingual_system_prompt_addon
            
            lang_info = await process_multilingual_message(
                user_message=user_message,
                session_id=session_id,
                customer_email=user_email  # Enhanced with customer email for cross-device
            )
            
            detected_language = lang_info.get("detected_language", "en")
            # Note: is_rtl returned to frontend via separate detection endpoint
            
            # Get language-specific system prompt addition
            if lang_info.get("should_translate_response"):
                language_prompt_addon = get_multilingual_system_prompt_addon(detected_language)
                logger.info(f"ChatWidget: Multilingual mode - responding in {detected_language}")
        except Exception as e:
            logger.warning(f"ChatWidget: Language detection failed: {e}")
        
        # ═══════════════════════════════════════════════════════════════
        # CUSTOMER MEMORY: Load profile and personalize (with cross-device support)
        # ═══════════════════════════════════════════════════════════════
        customer_memory = get_customer_memory(self.db)
        
        # Use session_id as customer identifier
        customer_id = f"session_{session_id[:32]}"
        
        # Load existing customer profile (prioritizes account-based if email provided)
        customer_profile = await customer_memory.get_profile(customer_id, user_email)
        
        # Generate personalization context
        personalization = customer_memory.generate_personalization_context(customer_profile)
        
        # Add cross-device memory indicator to prompt if user is logged in
        cross_device_note = ""
        if user_email and customer_profile.get("account_email"):
            user_name = customer_profile.get("user_name")
            if user_name:
                cross_device_note = f"\n\nThis is a returning customer: {user_name}. Greet them warmly by name."
        
        # Combine base prompt with personalization AND language addon
        system_prompt = base_system_prompt
        if personalization:
            system_prompt = f"{system_prompt}\n\n{personalization}"
            logger.info(f"ChatWidget: Loaded customer profile for {customer_id[:16]}...")
        if cross_device_note:
            system_prompt = f"{system_prompt}{cross_device_note}"
        if language_prompt_addon:
            system_prompt = f"{system_prompt}\n\n{language_prompt_addon}"
        
        # Get or create chat session (recreate if language changed)
        session_key = f"{session_id}_{detected_language}"
        if session_key not in self._chat_sessions:
            api_key = os.environ.get("EMERGENT_LLM_KEY", "")
            if not api_key:
                raise ValueError("EMERGENT_LLM_KEY not configured")
            
            chat = LlmChat(
                api_key=api_key,
                session_id=f"widget_{session_id}",
                system_message=system_prompt
            )
            chat.with_model("openai", "gpt-4o")
            self._chat_sessions[session_key] = chat
        
        chat = self._chat_sessions[session_key]
        
        # Load conversation history from DB for context (available for extended context use)
        messages_collection = f"{config.collection_prefix}chat_messages"
        _ = await self.db[messages_collection].find({
            "session_id": session_id
        }).sort("timestamp", -1).limit(10).to_list(10)
        
        # Generate response
        user_msg = UserMessage(text=user_message)
        response = await chat.send_message(user_msg)
        
        # ═══════════════════════════════════════════════════════════════
        # CUSTOMER MEMORY: Extract and update profile after conversation
        # ═══════════════════════════════════════════════════════════════
        try:
            # Combine user message with AI response for full context
            conversation_text = f"Customer: {user_message}\nAssistant: {response}"
            
            # Extract and update profile (with cross-device support)
            await customer_memory.extract_and_update(
                customer_id=customer_id,
                conversation_text=conversation_text,
                session_id=session_id,
                user_email=user_email  # Pass email for cross-device memory
            )
        except Exception as e:
            # Don't fail the response if memory extraction fails
            logger.warning(f"ChatWidget: Memory extraction failed: {e}")
        
        return response
    
    async def get_conversation_history(
        self,
        session_id: str,
        brand_key: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get conversation history for a session."""
        config = get_brand_config(brand_key)
        if not config:
            return []
        
        collection_name = f"{config.collection_prefix}chat_messages"
        
        cursor = self.db[collection_name].find(
            {"session_id": session_id, "brand_key": brand_key},
            {"_id": 0, "ip_address": 0, "generated_by": 0}  # Exclude sensitive fields
        ).sort("timestamp", 1).limit(limit)
        
        return await cursor.to_list(limit)
    
    async def get_cross_device_history(
        self,
        user_email: str,
        brand_key: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get conversation history across all sessions for an account.
        
        CROSS-DEVICE MEMORY: Returns messages from all sessions linked
        to this email, sorted by timestamp, for seamless conversation
        continuity across devices.
        
        Args:
            user_email: User's email address
            brand_key: Brand key for isolation
            limit: Maximum messages to return (default 50)
            
        Returns:
            List of messages with role, content, timestamp
        """
        config = get_brand_config(brand_key)
        if not config:
            return []
        
        collection_name = f"{config.collection_prefix}chat_messages"
        email = user_email.lower()
        
        # Find all messages linked to this account email
        cursor = self.db[collection_name].find(
            {
                "account_email": email,
                "brand_key": brand_key
            },
            {
                "_id": 0,
                "ip_address": 0,
                "generated_by": 0,
                "brand_guard_modified": 0
            }
        ).sort("timestamp", -1).limit(limit)  # Most recent first
        
        messages = await cursor.to_list(limit)
        
        # Reverse to chronological order for display
        messages.reverse()
        
        # Format for frontend consumption
        formatted = []
        for msg in messages:
            formatted.append({
                "role": "user" if msg.get("direction") == "user" else "assistant",
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else None,
                "has_image": msg.get("has_image", False)
            })
        
        return formatted
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════
    
    def _generate_session_id(self, brand_key: str, ip_address: str) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now(timezone.utc).isoformat()
        raw = f"{brand_key}:{ip_address}:{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()


# Singleton instance
_widget_service: Optional[ChatWidgetService] = None


def get_chat_widget_service(db) -> ChatWidgetService:
    """Get or create the chat widget service singleton."""
    global _widget_service
    if _widget_service is None:
        _widget_service = ChatWidgetService(db)
    return _widget_service
