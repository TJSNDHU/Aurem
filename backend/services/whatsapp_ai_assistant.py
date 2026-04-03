"""
WhatsApp AI Assistant Service
Combines WHAPI for WhatsApp messaging with AI (OpenAI/Claude) for intelligent auto-replies.
Learns from chat history, brand voice, and past conversations.
Now includes PinchTab browser integration for live data lookups.
"""

import os
import re
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ============= Browser Integration =============
from pinchtab_browser import (
    RerootsBrowser, 
    BrowserToolkit, 
    detect_intent, 
    Intent
)

# Global browser instance
_browser: Optional[RerootsBrowser] = None
_toolkit: Optional[BrowserToolkit] = None

async def get_browser_toolkit() -> BrowserToolkit:
    """Get or create the global browser toolkit instance."""
    global _browser, _toolkit
    
    if _toolkit is None:
        _browser = RerootsBrowser()
        await _browser.start()
        _toolkit = BrowserToolkit(_browser)
        logger.info("Browser toolkit initialized for WhatsApp AI")
    
    return _toolkit

async def shutdown_browser():
    """Shutdown browser on server exit."""
    global _browser
    if _browser:
        await _browser.stop()
        logger.info("Browser toolkit shutdown")

# ============= LLM Integration =============
from emergentintegrations.llm.chat import LlmChat, UserMessage

# Default configurations
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

# In-memory session store (production should use Redis/DB)
_chat_sessions: Dict[str, LlmChat] = {}


def get_llm_key():
    """Get the Emergent LLM key."""
    return os.environ.get("EMERGENT_LLM_KEY", "")


async def get_or_create_chat_session(
    session_id: str,
    system_message: str,
    provider: str = "openai",
    model: str = None
) -> LlmChat:
    """Get existing chat session or create a new one."""
    
    if session_id in _chat_sessions:
        return _chat_sessions[session_id]
    
    api_key = get_llm_key()
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY not configured")
    
    # Determine model based on provider
    if model is None:
        if provider == "openai":
            model = DEFAULT_OPENAI_MODEL
        elif provider == "anthropic":
            model = DEFAULT_CLAUDE_MODEL
        elif provider == "gemini":
            model = DEFAULT_GEMINI_MODEL
        else:
            model = DEFAULT_OPENAI_MODEL
    
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_message
    )
    
    # Set the model based on provider
    if provider == "anthropic":
        chat.with_model("anthropic", model)
    elif provider == "gemini":
        chat.with_model("gemini", model)
    else:
        chat.with_model("openai", model)
    
    _chat_sessions[session_id] = chat
    return chat


def clear_chat_session(session_id: str):
    """Clear a chat session from memory."""
    if session_id in _chat_sessions:
        del _chat_sessions[session_id]


# ============= Style Learning =============

class StyleAnalyzer:
    """Analyzes chat history to learn texting style patterns."""
    
    def __init__(self):
        self.patterns = {
            "avg_message_length": 0,
            "emoji_frequency": 0,
            "common_phrases": [],
            "greeting_style": "",
            "closing_style": "",
            "formality_level": "casual",  # casual, neutral, formal
            "response_speed_preference": "quick",  # quick, thoughtful
        }
        self.sample_messages: List[str] = []
    
    def analyze_chat_export(self, chat_text: str, is_closest_person: bool = False) -> Dict:
        """
        Analyze WhatsApp chat export to extract style patterns.
        
        Args:
            chat_text: Raw WhatsApp chat export text
            is_closest_person: If True, give extra weight to this style
        """
        # Parse WhatsApp format: [date, time] Sender: Message
        pattern = r'\[?(\d{1,2}/\d{1,2}/\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]?\s*-?\s*([^:]+):\s*(.+)'
        
        messages = []
        for match in re.finditer(pattern, chat_text, re.MULTILINE):
            sender = match.group(3).strip()
            message = match.group(4).strip()
            messages.append({"sender": sender, "message": message})
        
        if not messages:
            return self.patterns
        
        # Extract YOUR messages (assume you're the second most common sender)
        sender_counts = {}
        for msg in messages:
            sender_counts[msg["sender"]] = sender_counts.get(msg["sender"], 0) + 1
        
        # Get top 2 senders
        sorted_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_senders) < 2:
            return self.patterns
        
        your_name = sorted_senders[1][0]  # Assume you're the second sender
        your_messages = [m["message"] for m in messages if m["sender"] == your_name]
        
        if not your_messages:
            return self.patterns
        
        # Analyze patterns
        self.sample_messages = your_messages[:50]  # Keep samples for context
        
        # Average message length
        total_length = sum(len(m) for m in your_messages)
        self.patterns["avg_message_length"] = total_length // len(your_messages)
        
        # Emoji frequency
        emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF]')
        emoji_count = sum(len(emoji_pattern.findall(m)) for m in your_messages)
        self.patterns["emoji_frequency"] = emoji_count / len(your_messages)
        
        # Common phrases (2-3 word patterns)
        phrase_counts = {}
        for msg in your_messages:
            words = msg.lower().split()
            for i in range(len(words) - 1):
                phrase = " ".join(words[i:i+2])
                if len(phrase) > 4:
                    phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
        
        self.patterns["common_phrases"] = [p for p, c in sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
        
        # Greeting and closing styles
        greetings = [m for m in your_messages if any(g in m.lower() for g in ["hi", "hey", "hello", "yo", "sup"])]
        if greetings:
            self.patterns["greeting_style"] = greetings[0][:50]
        
        closings = [m for m in your_messages if any(c in m.lower() for c in ["bye", "later", "ttyl", "talk soon", "cya"])]
        if closings:
            self.patterns["closing_style"] = closings[0][:50]
        
        # Formality level
        formal_indicators = ["please", "thank you", "regards", "sincerely"]
        casual_indicators = ["lol", "haha", "omg", "bruh", "gonna", "wanna", "ya", "yep", "nope"]
        
        formal_count = sum(1 for m in your_messages for f in formal_indicators if f in m.lower())
        casual_count = sum(1 for m in your_messages for c in casual_indicators if c in m.lower())
        
        if formal_count > casual_count * 2:
            self.patterns["formality_level"] = "formal"
        elif casual_count > formal_count * 2:
            self.patterns["formality_level"] = "casual"
        else:
            self.patterns["formality_level"] = "neutral"
        
        # Give extra weight if closest person
        if is_closest_person:
            self.patterns["weight"] = 2.0
        else:
            self.patterns["weight"] = 1.0
        
        return self.patterns
    
    def generate_style_prompt(self) -> str:
        """Generate a system prompt that captures the learned style."""
        
        prompt_parts = [
            "You are an AI assistant that mimics a specific person's texting style.",
            f"Keep messages around {self.patterns['avg_message_length']} characters on average.",
        ]
        
        if self.patterns["emoji_frequency"] > 0.5:
            prompt_parts.append("Use emojis frequently in your responses.")
        elif self.patterns["emoji_frequency"] > 0.1:
            prompt_parts.append("Use emojis occasionally.")
        else:
            prompt_parts.append("Rarely use emojis.")
        
        if self.patterns["common_phrases"]:
            prompt_parts.append(f"Occasionally use phrases like: {', '.join(self.patterns['common_phrases'][:5])}")
        
        if self.patterns["formality_level"] == "casual":
            prompt_parts.append("Use casual, friendly language. Abbreviations and slang are okay.")
        elif self.patterns["formality_level"] == "formal":
            prompt_parts.append("Use professional, polite language. Avoid slang.")
        else:
            prompt_parts.append("Use a balanced, neutral tone.")
        
        if self.sample_messages:
            prompt_parts.append("\nExample messages from this person:\n" + "\n".join(f'- "{m}"' for m in self.sample_messages[:5]))
        
        return "\n".join(prompt_parts)


# ============= Brand Voice =============

class BrandVoice:
    """Manages brand voice configuration for business replies."""
    
    def __init__(self):
        self.config = {
            "brand_name": "ReRoots",
            "tone": "friendly and knowledgeable",
            "personality_traits": ["helpful", "skincare-expert", "warm"],
            "key_phrases": [],
            "avoid_phrases": [],
            "response_guidelines": [],
            "product_knowledge": "",
        }
    
    def set_config(self, config: Dict):
        """Update brand voice configuration."""
        self.config.update(config)
    
    def generate_system_prompt(self) -> str:
        """Generate system prompt for brand voice."""
        
        prompt = f"""You are {self.config['brand_name']}'s WhatsApp assistant.

Tone: {self.config['tone']}
Personality: {', '.join(self.config['personality_traits'])}

Guidelines:
- Always be helpful and respond promptly
- If asked about products, provide accurate information
- For order inquiries, ask for order ID if not provided
- For complaints, be empathetic and offer solutions
"""
        
        if self.config["key_phrases"]:
            prompt += f"\nKey phrases to use: {', '.join(self.config['key_phrases'])}"
        
        if self.config["avoid_phrases"]:
            prompt += f"\nAvoid: {', '.join(self.config['avoid_phrases'])}"
        
        if self.config["product_knowledge"]:
            prompt += f"\n\nProduct Knowledge:\n{self.config['product_knowledge']}"
        
        if self.config["response_guidelines"]:
            prompt += "\n\nResponse Guidelines:\n" + "\n".join(f"- {g}" for g in self.config["response_guidelines"])
        
        return prompt


# ============= WhatsApp AI Assistant =============

class WhatsAppAIAssistant:
    """Main class for WhatsApp AI auto-reply functionality."""
    
    def __init__(self, db=None):
        self.db = db
        self.style_analyzer = StyleAnalyzer()
        self.brand_voice = BrandVoice()
        self.whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
        self.whapi_url = os.environ.get("WHAPI_API_URL", "https://gate.whapi.cloud")
        
        # Settings
        self.settings = {
            "enabled": False,
            "mode": "brand",  # "brand" or "personal"
            "provider": "openai",  # "openai" or "anthropic"
            "model": None,  # None = use default
            "auto_reply_delay_ms": 1000,  # Simulate typing delay
            "excluded_contacts": [],  # Phone numbers to not auto-reply
            "business_hours_only": False,
            "business_hours": {"start": "09:00", "end": "18:00"},
        }
    
    async def initialize(self):
        """Initialize the assistant with data from database."""
        if self.db is None:
            return
        
        # Load settings from database
        settings_doc = await self.db.whatsapp_ai_settings.find_one({"_id": "settings"})
        if settings_doc:
            self.settings.update({k: v for k, v in settings_doc.items() if k != "_id"})
        
        # Load brand voice config
        brand_doc = await self.db.whatsapp_ai_settings.find_one({"_id": "brand_voice"})
        if brand_doc:
            self.brand_voice.set_config({k: v for k, v in brand_doc.items() if k != "_id"})
        
        # Load learned style patterns
        style_doc = await self.db.whatsapp_ai_settings.find_one({"_id": "style_patterns"})
        if style_doc:
            self.style_analyzer.patterns = {k: v for k, v in style_doc.items() if k != "_id"}
    
    async def save_settings(self):
        """Save current settings to database."""
        if self.db is None:
            return
        
        await self.db.whatsapp_ai_settings.update_one(
            {"_id": "settings"},
            {"$set": self.settings},
            upsert=True
        )
    
    async def save_brand_voice(self):
        """Save brand voice config to database."""
        if self.db is None:
            return
        
        await self.db.whatsapp_ai_settings.update_one(
            {"_id": "brand_voice"},
            {"$set": self.brand_voice.config},
            upsert=True
        )
    
    async def save_style_patterns(self):
        """Save learned style patterns to database."""
        if self.db is None:
            return
        
        await self.db.whatsapp_ai_settings.update_one(
            {"_id": "style_patterns"},
            {"$set": self.style_analyzer.patterns},
            upsert=True
        )
    
    def get_system_prompt(self) -> str:
        """Get the appropriate system prompt based on mode."""
        if self.settings["mode"] == "brand":
            return self.brand_voice.generate_system_prompt()
        else:
            return self.style_analyzer.generate_style_prompt()
    
    async def process_incoming_message(
        self,
        from_number: str,
        message_text: str,
        message_id: str = None
    ) -> Optional[str]:
        """
        Process an incoming WhatsApp message and generate a reply.
        
        Args:
            from_number: Sender's phone number
            message_text: The message content
            message_id: Optional message ID for tracking
            
        Returns:
            Generated reply text, or None if auto-reply is disabled
        """
        
        # Check if enabled
        if not self.settings["enabled"]:
            logger.info(f"WhatsApp AI: Disabled, skipping message from {from_number[:5]}***")
            return None
        
        # Check excluded contacts
        if from_number in self.settings["excluded_contacts"]:
            logger.info("WhatsApp AI: Contact excluded, skipping")
            return None
        
        # Check business hours
        if self.settings["business_hours_only"]:
            now = datetime.now()
            start = datetime.strptime(self.settings["business_hours"]["start"], "%H:%M").time()
            end = datetime.strptime(self.settings["business_hours"]["end"], "%H:%M").time()
            if not (start <= now.time() <= end):
                logger.info("WhatsApp AI: Outside business hours, skipping")
                return None
        
        try:
            # Create session ID based on phone number
            session_id = f"whatsapp_{from_number}"
            
            # ── Detect intent and fetch live data ──
            intent, extracted_value = detect_intent(message_text)
            live_context = ""
            
            try:
                toolkit = await get_browser_toolkit()
                
                if intent == Intent.ORDER_STATUS:
                    live_context = await toolkit.get_order_status(extracted_value)
                elif intent == Intent.STOCK_CHECK:
                    live_context = await toolkit.get_stock()
                elif intent == Intent.INGREDIENTS:
                    live_context = await toolkit.get_ingredients()
                elif intent == Intent.PRODUCT_INFO:
                    live_context = await toolkit.get_product_info()
                elif intent == Intent.SHIPPING_RATE:
                    live_context = await toolkit.get_shipping_info()
                # Intent.GENERAL → no browser call
                
                if live_context:
                    logger.info(f"WhatsApp AI: Fetched live data for intent {intent.value}")
            except Exception as e:
                logger.warning(f"WhatsApp AI: Browser toolkit error: {e}")
            
            # Build enhanced system prompt with live data AND RAG product context
            base_system_prompt = self.get_system_prompt()
            
            # ── RAG: Retrieve relevant product context with confidence ──
            rag_context = ""
            rag_confidence = 0.0
            web_search_context = ""
            
            try:
                from rag.retriever import retrieve_context_with_confidence, init_retriever, needs_web_search, CONFIDENCE_THRESHOLD
                # Ensure retriever is initialized
                if self.db is not None:
                    init_retriever(self.db)
                    rag_context, rag_confidence = await retrieve_context_with_confidence(message_text, top_k=3)
                    if rag_context:
                        logger.info(f"WhatsApp AI: RAG retrieved product context ({len(rag_context)} chars, confidence: {rag_confidence:.2f})")
                    
                    # ── Web Search Fallback when RAG confidence is low ──
                    if needs_web_search(rag_confidence):
                        logger.info(f"WhatsApp AI: RAG confidence {rag_confidence:.2f} < {CONFIDENCE_THRESHOLD}, triggering web search fallback")
                        try:
                            from services.web_search import search_web_for_reroots
                            web_search_context = await search_web_for_reroots(message_text)
                            if web_search_context:
                                logger.info(f"WhatsApp AI: Web search returned {len(web_search_context)} chars")
                        except ImportError:
                            logger.debug("WhatsApp AI: Web search module not available")
                        except Exception as e:
                            logger.warning(f"WhatsApp AI: Web search error: {e}")
                            
            except ImportError:
                logger.debug("WhatsApp AI: RAG module not available")
            except Exception as e:
                logger.warning(f"WhatsApp AI: RAG retrieval error: {e}")
            
            # Combine all context sources
            enhanced_prompt = base_system_prompt
            
            if rag_context:
                enhanced_prompt += f"\n\n--- RELEVANT PRODUCT INFORMATION ---\n{rag_context}\n\nIMPORTANT: Always answer based on this product data. Never invent product details, prices, or ingredients."
            
            if web_search_context:
                enhanced_prompt += f"\n\n{web_search_context}"
            
            if live_context:
                enhanced_prompt += f"\n\n--- LIVE DATA (use this to answer) ---\n{live_context}"
            
            # Get or create chat session
            chat = await get_or_create_chat_session(
                session_id=session_id,
                system_message=enhanced_prompt,
                provider=self.settings["provider"],
                model=self.settings["model"]
            )
            
            # Load conversation history from database
            if self.db is not None:
                history = await self.db.whatsapp_conversations.find(
                    {"phone": from_number}
                ).sort("timestamp", -1).limit(10).to_list(10)
                
                # Add history to context if this is a fresh session
                if history and session_id not in _chat_sessions:
                    context = "\n".join([
                        f"{'Customer' if h['direction'] == 'in' else 'You'}: {h['message']}"
                        for h in reversed(history)
                    ])
                    if context:
                        # Prepend context to first message
                        message_text = f"[Previous conversation context:\n{context}]\n\nNew message: {message_text}"
            
            # Generate reply
            user_message = UserMessage(text=message_text)
            reply = await chat.send_message(user_message)
            
            # Log conversation to database
            if self.db is not None:
                # Log incoming message
                await self.db.whatsapp_conversations.insert_one({
                    "phone": from_number,
                    "direction": "in",
                    "message": message_text,
                    "message_id": message_id,
                    "timestamp": datetime.now(timezone.utc)
                })
                
                # Log outgoing reply
                await self.db.whatsapp_conversations.insert_one({
                    "phone": from_number,
                    "direction": "out",
                    "message": reply,
                    "ai_generated": True,
                    "provider": self.settings["provider"],
                    "timestamp": datetime.now(timezone.utc)
                })
            
            logger.info(f"WhatsApp AI: Generated reply for {from_number[:5]}***")
            return reply
            
        except Exception as e:
            logger.error(f"WhatsApp AI error: {e}")
            return None
    
    async def send_whapi_message(self, to_number: str, message: str) -> Dict:
        """Send a message via WHAPI."""
        import httpx
        
        if not self.whapi_token:
            raise ValueError("WHAPI_API_TOKEN not configured")
        
        # Normalize phone number
        phone = to_number.lstrip("+").replace("-", "").replace(" ", "")
        
        url = f"{self.whapi_url}/messages/text"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.whapi_token}",
            "content-type": "application/json"
        }
        payload = {
            "to": f"{phone}@s.whatsapp.net",
            "body": message
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            return response.json()
    
    async def handle_webhook(self, webhook_data: Dict) -> Optional[str]:
        """
        Handle incoming WHAPI webhook for auto-reply.
        
        Args:
            webhook_data: The webhook payload from WHAPI
            
        Returns:
            Reply message if sent, None otherwise
        """
        try:
            # Parse webhook data
            messages = webhook_data.get("messages", [])
            
            for msg in messages:
                # Only process incoming text messages
                if msg.get("from_me", True):
                    continue
                
                msg_type = msg.get("type")
                if msg_type != "text":
                    continue
                
                from_number = msg.get("from", "").replace("@s.whatsapp.net", "")
                message_text = msg.get("text", {}).get("body", "")
                message_id = msg.get("id")
                
                if not from_number or not message_text:
                    continue
                
                # Generate reply
                reply = await self.process_incoming_message(
                    from_number=from_number,
                    message_text=message_text,
                    message_id=message_id
                )
                
                if reply:
                    # Add typing delay for realism
                    delay = self.settings["auto_reply_delay_ms"] / 1000
                    await asyncio.sleep(delay)
                    
                    # Send reply via WHAPI
                    await self.send_whapi_message(from_number, reply)
                    return reply
            
            return None
            
        except Exception as e:
            logger.error(f"Webhook handling error: {e}")
            return None


# ============= Singleton Instance =============
_assistant_instance: Optional[WhatsAppAIAssistant] = None


def get_whatsapp_assistant(db=None) -> WhatsAppAIAssistant:
    """Get or create the WhatsApp AI Assistant singleton."""
    global _assistant_instance
    
    if _assistant_instance is None:
        _assistant_instance = WhatsAppAIAssistant(db=db)
    elif db is not None and _assistant_instance.db is None:
        _assistant_instance.db = db
    
    return _assistant_instance


async def init_whatsapp_assistant(db) -> WhatsAppAIAssistant:
    """Initialize the WhatsApp AI Assistant with database."""
    assistant = get_whatsapp_assistant(db)
    await assistant.initialize()
    return assistant
