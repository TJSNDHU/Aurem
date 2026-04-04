"""
Contact Extractor Service
LLM-powered extraction of phone numbers and emails from natural conversation

Supports:
- Standard formats (regex): "555-1234", "john@email.com"
- Conversational formats (LLM): "my number is four-one-six..."
- Channel auto-capture: WhatsApp, Vapi, Email
"""

import re
import logging
import os
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)

# Emergent LLM Key
EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY", "sk-emergent-0D2C22421Cb5436270")

# Regex patterns for standard formats
EMAIL_REGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
PHONE_REGEX = r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'


class ContactExtractor:
    """Extract contact information from natural conversation"""
    
    def __init__(self):
        self.openai_client = None
        self._init_openai()
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        try:
            from openai import OpenAI
            self.openai_client = OpenAI(api_key=EMERGENT_LLM_KEY)
            logger.info("[ContactExtractor] Initialized with Emergent LLM Key")
        except ImportError:
            logger.error("[ContactExtractor] OpenAI library not installed")
        except Exception as e:
            logger.error(f"[ContactExtractor] Init error: {e}")
    
    async def extract_from_message(
        self,
        message: str,
        channel: Optional[str] = None,
        channel_metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Extract contact info from message
        
        Args:
            message: Customer's message
            channel: Source channel (whatsapp, vapi, email, web)
            channel_metadata: Channel-specific data (from_number, caller_id, etc.)
        
        Returns:
            {
                "email": str | None,
                "phone": str | None,
                "extraction_method": "regex" | "llm" | "channel",
                "confidence": float,
                "channel_preference": str | None
            }
        """
        result = {
            "email": None,
            "phone": None,
            "extraction_method": None,
            "confidence": 0.0,
            "channel_preference": None
        }
        
        # Step 1: Try channel auto-capture first (highest confidence)
        channel_data = self._extract_from_channel(channel, channel_metadata)
        if channel_data["phone"] or channel_data["email"]:
            result.update(channel_data)
            result["extraction_method"] = "channel"
            result["confidence"] = 1.0
            logger.info(f"[ContactExtractor] Channel auto-capture: {channel_data}")
            return result
        
        # Step 2: Try regex (fast, high confidence)
        regex_data = self._extract_with_regex(message)
        if regex_data["phone"] or regex_data["email"]:
            result.update(regex_data)
            result["extraction_method"] = "regex"
            result["confidence"] = 0.95
            logger.info(f"[ContactExtractor] Regex extraction: {regex_data}")
            return result
        
        # Step 3: Try LLM (conversational, medium confidence)
        if self.openai_client:
            llm_data = await self._extract_with_llm(message)
            if llm_data["phone"] or llm_data["email"]:
                result.update(llm_data)
                result["extraction_method"] = "llm"
                result["confidence"] = 0.85
                logger.info(f"[ContactExtractor] LLM extraction: {llm_data}")
                return result
        
        # No contact info found
        return result
    
    def _extract_from_channel(
        self,
        channel: Optional[str],
        metadata: Optional[Dict]
    ) -> Dict:
        """Extract from channel metadata (auto-capture)"""
        
        if not channel or not metadata:
            return {"email": None, "phone": None, "channel_preference": None}
        
        email = None
        phone = None
        preference = channel
        
        if channel == "whatsapp":
            # WhatsApp provides from_number
            phone = metadata.get("from_number") or metadata.get("from")
            preference = "whatsapp"
        
        elif channel == "vapi" or channel == "voice":
            # Vapi provides caller_id
            phone = metadata.get("caller_id") or metadata.get("phone_number")
            preference = "voice"
        
        elif channel == "email":
            # Email provides sender address
            email = metadata.get("sender") or metadata.get("from_email")
            preference = "email"
        
        elif channel == "sms":
            # SMS provides from_number
            phone = metadata.get("from_number") or metadata.get("from")
            preference = "sms"
        
        return {
            "email": email,
            "phone": self._format_phone(phone) if phone else None,
            "channel_preference": preference
        }
    
    def _extract_with_regex(self, message: str) -> Dict:
        """Extract using regex patterns (standard formats)"""
        
        # Find email
        email_matches = re.findall(EMAIL_REGEX, message)
        email = email_matches[0] if email_matches else None
        
        # Find phone
        phone_matches = re.findall(PHONE_REGEX, message)
        phone = self._format_phone(phone_matches[0]) if phone_matches else None
        
        # Detect channel preference from context
        preference = None
        if "whatsapp" in message.lower():
            preference = "whatsapp"
        elif "email" in message.lower() or "send" in message.lower():
            preference = "email"
        elif "text" in message.lower() or "sms" in message.lower():
            preference = "sms"
        
        return {
            "email": email,
            "phone": phone,
            "channel_preference": preference
        }
    
    async def _extract_with_llm(self, message: str) -> Dict:
        """Extract using GPT-4o (conversational formats)"""
        
        prompt = f"""Extract contact information from this customer message. They may have written phone/email in a conversational way.

Customer Message:
"{message}"

Extract and return JSON:
{{
  "email": "<email address if found, else null>",
  "phone": "<phone number in E.164 format if found, else null>",
  "channel_preference": "<whatsapp|email|sms|voice if mentioned, else null>"
}}

Examples of conversational formats to handle:
- "My number is four-one-six, five-five-five, twelve-thirty-four" → "phone": "+14165551234"
- "Email is john dot smith at gmail" → "email": "john.smith@gmail.com"
- "Text me at five-five-five, one-two-three-four" → "phone": "+15551234"
- "Reach me on WhatsApp - 555 1234" → "phone": "+15551234", "channel_preference": "whatsapp"

Rules:
- Format phone as E.164 (+1XXXXXXXXXX for US/Canada)
- Lowercase email addresses
- If no contact info found, return null for both
- Detect preferred channel from context

Respond ONLY with valid JSON, no other text."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a contact information extraction expert. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            return {
                "email": result.get("email"),
                "phone": result.get("phone"),
                "channel_preference": result.get("channel_preference")
            }
        
        except Exception as e:
            logger.error(f"[ContactExtractor] LLM extraction error: {e}")
            return {"email": None, "phone": None, "channel_preference": None}
    
    def _format_phone(self, phone: str) -> Optional[str]:
        """Format phone number to E.164 standard"""
        if not phone:
            return None
        
        # Remove all non-digits
        digits = re.sub(r'\D', '', phone)
        
        # Assume US/Canada (+1) if 10 digits
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith('1'):
            return f"+{digits}"
        elif len(digits) > 10:
            return f"+{digits}"
        else:
            return digits  # Return as-is if format unclear
    
    def detect_ask_triggers(self, message: str) -> Dict:
        """
        Detect if customer is asking for something that requires contact info
        
        Returns:
            {
                "should_ask": bool,
                "trigger_type": str,
                "context": str
            }
        """
        message_lower = message.lower()
        
        # Trigger phrases
        send_triggers = ["send me", "email me", "text me", "can you send", "send it to"]
        booking_triggers = ["book", "appointment", "schedule", "reserve"]
        pricing_triggers = ["price", "cost", "how much", "pricing", "quote"]
        follow_up_triggers = ["follow up", "get back to me", "contact me", "reach out"]
        
        # Check triggers
        if any(trigger in message_lower for trigger in send_triggers):
            return {
                "should_ask": True,
                "trigger_type": "send_request",
                "context": "Customer wants something sent"
            }
        
        if any(trigger in message_lower for trigger in booking_triggers):
            return {
                "should_ask": True,
                "trigger_type": "booking",
                "context": "Customer wants to book/schedule"
            }
        
        if any(trigger in message_lower for trigger in pricing_triggers):
            # Only ask if they want it sent, not just asking price
            if any(word in message_lower for word in ["send", "email", "share"]):
                return {
                    "should_ask": True,
                    "trigger_type": "pricing_request",
                    "context": "Customer wants pricing sent"
                }
        
        if any(trigger in message_lower for trigger in follow_up_triggers):
            return {
                "should_ask": True,
                "trigger_type": "follow_up",
                "context": "Customer wants follow-up contact"
            }
        
        # No trigger detected
        return {
            "should_ask": False,
            "trigger_type": None,
            "context": None
        }


# Singleton instance
_contact_extractor = None


def get_contact_extractor() -> ContactExtractor:
    """Get or create contact extractor instance"""
    global _contact_extractor
    if _contact_extractor is None:
        _contact_extractor = ContactExtractor()
    return _contact_extractor


# Convenience function
async def extract_contact_info(
    message: str,
    channel: Optional[str] = None,
    channel_metadata: Optional[Dict] = None
) -> Dict:
    """Extract contact info from message (convenience wrapper)"""
    extractor = get_contact_extractor()
    return await extractor.extract_from_message(message, channel, channel_metadata)
