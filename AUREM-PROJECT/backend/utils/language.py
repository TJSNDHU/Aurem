"""
Language Detection and Translation Utilities
═══════════════════════════════════════════════════════════════════
Multilingual AI support for global customer engagement.

Features:
- Auto-detect customer message language using langdetect
- Translate AI responses to detected language
- RTL language support (Arabic, Hebrew, Urdu, Farsi)
- Save preferred_language to customer profile
- Language-aware proactive outreach

Supported: 40+ languages including all RTL languages
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple, List
from langdetect import detect, detect_langs, LangDetectException
import pycountry

logger = logging.getLogger(__name__)

# Database reference
_db = None

def set_db(database):
    """Set database reference."""
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════
# LANGUAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# RTL (Right-to-Left) Languages
RTL_LANGUAGES = {
    "ar": "Arabic",
    "he": "Hebrew", 
    "fa": "Persian/Farsi",
    "ur": "Urdu",
    "yi": "Yiddish",
    "ps": "Pashto",
    "sd": "Sindhi",
}

# Full language mapping with native names
LANGUAGE_MAP = {
    "en": {"name": "English", "native": "English", "rtl": False},
    "es": {"name": "Spanish", "native": "Español", "rtl": False},
    "fr": {"name": "French", "native": "Français", "rtl": False},
    "de": {"name": "German", "native": "Deutsch", "rtl": False},
    "it": {"name": "Italian", "native": "Italiano", "rtl": False},
    "pt": {"name": "Portuguese", "native": "Português", "rtl": False},
    "nl": {"name": "Dutch", "native": "Nederlands", "rtl": False},
    "ru": {"name": "Russian", "native": "Русский", "rtl": False},
    "zh": {"name": "Chinese", "native": "中文", "rtl": False},
    "zh-cn": {"name": "Chinese (Simplified)", "native": "简体中文", "rtl": False},
    "zh-tw": {"name": "Chinese (Traditional)", "native": "繁體中文", "rtl": False},
    "ja": {"name": "Japanese", "native": "日本語", "rtl": False},
    "ko": {"name": "Korean", "native": "한국어", "rtl": False},
    "ar": {"name": "Arabic", "native": "العربية", "rtl": True},
    "he": {"name": "Hebrew", "native": "עברית", "rtl": True},
    "fa": {"name": "Persian", "native": "فارسی", "rtl": True},
    "ur": {"name": "Urdu", "native": "اردو", "rtl": True},
    "hi": {"name": "Hindi", "native": "हिन्दी", "rtl": False},
    "bn": {"name": "Bengali", "native": "বাংলা", "rtl": False},
    "ta": {"name": "Tamil", "native": "தமிழ்", "rtl": False},
    "te": {"name": "Telugu", "native": "తెలుగు", "rtl": False},
    "mr": {"name": "Marathi", "native": "मराठी", "rtl": False},
    "gu": {"name": "Gujarati", "native": "ગુજરાતી", "rtl": False},
    "pa": {"name": "Punjabi", "native": "ਪੰਜਾਬੀ", "rtl": False},
    "th": {"name": "Thai", "native": "ไทย", "rtl": False},
    "vi": {"name": "Vietnamese", "native": "Tiếng Việt", "rtl": False},
    "id": {"name": "Indonesian", "native": "Bahasa Indonesia", "rtl": False},
    "ms": {"name": "Malay", "native": "Bahasa Melayu", "rtl": False},
    "tl": {"name": "Filipino", "native": "Tagalog", "rtl": False},
    "tr": {"name": "Turkish", "native": "Türkçe", "rtl": False},
    "pl": {"name": "Polish", "native": "Polski", "rtl": False},
    "uk": {"name": "Ukrainian", "native": "Українська", "rtl": False},
    "cs": {"name": "Czech", "native": "Čeština", "rtl": False},
    "ro": {"name": "Romanian", "native": "Română", "rtl": False},
    "hu": {"name": "Hungarian", "native": "Magyar", "rtl": False},
    "el": {"name": "Greek", "native": "Ελληνικά", "rtl": False},
    "sv": {"name": "Swedish", "native": "Svenska", "rtl": False},
    "no": {"name": "Norwegian", "native": "Norsk", "rtl": False},
    "da": {"name": "Danish", "native": "Dansk", "rtl": False},
    "fi": {"name": "Finnish", "native": "Suomi", "rtl": False},
}

# Country to primary language mapping (for phone/voice routing)
COUNTRY_LANGUAGE_MAP = {
    "CA": "en",  # Canada - English (also French)
    "US": "en",  # United States
    "GB": "en",  # United Kingdom
    "AU": "en",  # Australia
    "FR": "fr",  # France
    "DE": "de",  # Germany
    "IN": "hi",  # India - Hindi (multilingual)
    "AE": "ar",  # UAE - Arabic
    "SA": "ar",  # Saudi Arabia - Arabic
    "SG": "en",  # Singapore - English
    "JP": "ja",  # Japan
    "BR": "pt",  # Brazil - Portuguese
    "MX": "es",  # Mexico - Spanish
}


# ═══════════════════════════════════════════════════════════════════
# LANGUAGE DETECTION
# ═══════════════════════════════════════════════════════════════════

def detect_language(text: str) -> Dict[str, Any]:
    """
    Detect the language of input text.
    
    Returns:
        {
            "language_code": "es",
            "language_name": "Spanish",
            "native_name": "Español",
            "is_rtl": False,
            "confidence": 0.95,
            "alternatives": [{"code": "pt", "confidence": 0.03}]
        }
    """
    if not text or len(text.strip()) < 3:
        return {
            "language_code": "en",
            "language_name": "English",
            "native_name": "English",
            "is_rtl": False,
            "confidence": 0.0,
            "alternatives": [],
            "detected": False
        }
    
    try:
        # Get all detected languages with probabilities
        detected_langs = detect_langs(text)
        
        if not detected_langs:
            return _default_language_result()
        
        # Primary detection
        primary = detected_langs[0]
        lang_code = primary.lang.lower()
        
        # Map to our language info
        lang_info = LANGUAGE_MAP.get(lang_code, {
            "name": lang_code.upper(),
            "native": lang_code.upper(),
            "rtl": lang_code in RTL_LANGUAGES
        })
        
        # Get alternatives
        alternatives = []
        for lang in detected_langs[1:4]:  # Top 3 alternatives
            alt_info = LANGUAGE_MAP.get(lang.lang.lower(), {"name": lang.lang})
            alternatives.append({
                "code": lang.lang.lower(),
                "name": alt_info.get("name", lang.lang),
                "confidence": round(lang.prob, 3)
            })
        
        logger.info(f"[LANG] Detected: {lang_code} ({lang_info['name']}) confidence={primary.prob:.2f}")
        
        return {
            "language_code": lang_code,
            "language_name": lang_info.get("name", lang_code),
            "native_name": lang_info.get("native", lang_code),
            "is_rtl": lang_info.get("rtl", False),
            "confidence": round(primary.prob, 3),
            "alternatives": alternatives,
            "detected": True
        }
        
    except LangDetectException as e:
        logger.warning(f"[LANG] Detection failed: {e}")
        return _default_language_result()
    except Exception as e:
        logger.error(f"[LANG] Unexpected error: {e}")
        return _default_language_result()


def _default_language_result() -> Dict[str, Any]:
    """Return default English result."""
    return {
        "language_code": "en",
        "language_name": "English",
        "native_name": "English",
        "is_rtl": False,
        "confidence": 0.0,
        "alternatives": [],
        "detected": False
    }


def is_rtl_language(language_code: str) -> bool:
    """Check if a language is RTL."""
    return language_code.lower() in RTL_LANGUAGES


def get_language_name(language_code: str) -> str:
    """Get the English name for a language code."""
    lang_info = LANGUAGE_MAP.get(language_code.lower(), {})
    return lang_info.get("name", language_code)


def get_native_name(language_code: str) -> str:
    """Get the native name for a language code."""
    lang_info = LANGUAGE_MAP.get(language_code.lower(), {})
    return lang_info.get("native", language_code)


# ═══════════════════════════════════════════════════════════════════
# AI TRANSLATION
# ═══════════════════════════════════════════════════════════════════

async def translate_text(
    text: str,
    target_language: str,
    source_language: Optional[str] = None,
    context: str = "skincare customer support"
) -> Dict[str, Any]:
    """
    Translate text to target language using AI.
    
    Args:
        text: Text to translate
        target_language: Target language code (e.g., "es", "ar")
        source_language: Optional source language (auto-detect if None)
        context: Context for better translation
    
    Returns:
        {
            "translated": "Translated text",
            "source_language": "en",
            "target_language": "es",
            "success": True
        }
    """
    if not text or not text.strip():
        return {
            "translated": text,
            "source_language": source_language or "en",
            "target_language": target_language,
            "success": True
        }
    
    # If source = target, return as-is
    if source_language and source_language == target_language:
        return {
            "translated": text,
            "source_language": source_language,
            "target_language": target_language,
            "success": True
        }
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            logger.warning("[LANG] No EMERGENT_LLM_KEY for translation")
            return {
                "translated": text,
                "error": "Translation service not configured",
                "success": False
            }
        
        target_name = get_language_name(target_language)
        target_native = get_native_name(target_language)
        
        # Build system prompt
        system_prompt = f"""You are a professional translator specializing in {context}.
Your task is to translate text to {target_name} ({target_native}).

RULES:
1. Maintain the same tone, style, and formatting
2. Keep brand names unchanged (AURA-GEN, Reroots, etc.)
3. Keep product names in English unless there's a standard translation
4. For skincare terms, use the commonly accepted local terminology
5. If the text is already in {target_name}, return it unchanged
6. Only output the translation, nothing else"""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"translate_{target_language}",
            system_message=system_prompt
        )
        chat.with_model("openai", "gpt-4o")
        
        user_msg = UserMessage(text=f"Translate:\n{text}")
        translated = await chat.send_message(user_msg)
        
        logger.info(f"[LANG] Translated to {target_language}: {len(text)} -> {len(translated)} chars")
        
        return {
            "translated": translated.strip(),
            "source_language": source_language or "auto",
            "target_language": target_language,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"[LANG] Translation error: {e}")
        return {
            "translated": text,
            "error": str(e),
            "success": False
        }


async def translate_ai_response(
    response: str,
    customer_language: str,
    brand_name: str = "Reroots"
) -> str:
    """
    Translate AI response to customer's language.
    Used by chat widget and proactive outreach.
    
    Args:
        response: AI response in English
        customer_language: Customer's detected/preferred language
        brand_name: Brand name to preserve
    
    Returns:
        Translated response string
    """
    # Skip translation for English
    if customer_language.lower() in ["en", "en-us", "en-gb", "en-ca", "en-au"]:
        return response
    
    result = await translate_text(
        text=response,
        target_language=customer_language,
        source_language="en",
        context=f"{brand_name} skincare customer support"
    )
    
    return result.get("translated", response)


# ═══════════════════════════════════════════════════════════════════
# CUSTOMER LANGUAGE PROFILE
# ═══════════════════════════════════════════════════════════════════

async def update_customer_language(
    customer_id: str,
    language_code: str,
    confidence: float = 1.0,
    source: str = "detection"
) -> bool:
    """
    Update customer's preferred language in profile.
    
    Args:
        customer_id: Customer email or session ID
        language_code: Detected/selected language code
        confidence: Detection confidence (0-1)
        source: How language was determined (detection, selection, voice)
    
    Returns:
        True if updated successfully
    """
    if _db is None:
        logger.warning("[LANG] No database connection for language update")
        return False
    
    try:
        from datetime import datetime, timezone
        
        # Update customer profile
        await _db.reroots_customer_profiles.update_one(
            {"customer_email": customer_id},
            {
                "$set": {
                    "preferred_language": language_code,
                    "language_confidence": confidence,
                    "language_source": source,
                    "language_updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        logger.info(f"[LANG] Updated language for {customer_id[:8]}...: {language_code} (source={source})")
        return True
        
    except Exception as e:
        logger.error(f"[LANG] Failed to update customer language: {e}")
        return False


async def get_customer_language(customer_id: str) -> str:
    """
    Get customer's preferred language from profile.
    
    Args:
        customer_id: Customer email or session ID
    
    Returns:
        Language code (defaults to "en")
    """
    if _db is None:
        return "en"
    
    try:
        profile = await _db.reroots_customer_profiles.find_one(
            {"customer_email": customer_id},
            {"preferred_language": 1}
        )
        
        if profile and profile.get("preferred_language"):
            return profile["preferred_language"]
        
        return "en"
        
    except Exception as e:
        logger.error(f"[LANG] Error getting customer language: {e}")
        return "en"


# ═══════════════════════════════════════════════════════════════════
# MULTILINGUAL CHAT SUPPORT
# ═══════════════════════════════════════════════════════════════════

async def process_multilingual_message(
    user_message: str,
    session_id: str,
    customer_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process incoming message with language detection and profile update.
    
    Args:
        user_message: Customer's message
        session_id: Chat session ID
        customer_email: Optional customer email
    
    Returns:
        {
            "detected_language": "es",
            "is_rtl": False,
            "should_translate_response": True,
            "customer_id": "..."
        }
    """
    # Detect language
    detection = detect_language(user_message)
    
    customer_id = customer_email or f"session_{session_id[:32]}"
    
    # Update customer profile if confident detection
    if detection["detected"] and detection["confidence"] > 0.7:
        await update_customer_language(
            customer_id=customer_id,
            language_code=detection["language_code"],
            confidence=detection["confidence"],
            source="chat_detection"
        )
    
    return {
        "detected_language": detection["language_code"],
        "language_name": detection["language_name"],
        "is_rtl": detection["is_rtl"],
        "should_translate_response": detection["language_code"] != "en",
        "customer_id": customer_id,
        "confidence": detection["confidence"]
    }


def get_multilingual_system_prompt_addon(language_code: str) -> str:
    """
    Get system prompt addition for multilingual response.
    
    Args:
        language_code: Customer's language code
    
    Returns:
        Additional system prompt text
    """
    if language_code.lower() in ["en", "en-us", "en-gb", "en-ca"]:
        return ""
    
    lang_name = get_language_name(language_code)
    native_name = get_native_name(language_code)
    is_rtl = is_rtl_language(language_code)
    
    rtl_note = ""
    if is_rtl:
        rtl_note = "\n- This is an RTL language - ensure proper formatting for right-to-left text."
    
    return f"""

═══════════════════════════════════════════════════════════════════
LANGUAGE REQUIREMENT: Respond in {lang_name} ({native_name})
═══════════════════════════════════════════════════════════════════
The customer is communicating in {lang_name}. You MUST:
1. Respond ENTIRELY in {lang_name} ({native_name})
2. Use natural, fluent {lang_name} - not robotic translation
3. Keep brand names in English: AURA-GEN, Reroots, etc.
4. Use locally appropriate skincare terminology
5. Match the customer's formality level{rtl_note}
═══════════════════════════════════════════════════════════════════"""


# ═══════════════════════════════════════════════════════════════════
# LANGUAGE ANALYTICS
# ═══════════════════════════════════════════════════════════════════

async def get_language_breakdown() -> Dict[str, Any]:
    """
    Get breakdown of customer languages for admin dashboard.
    
    Returns:
        {
            "total_customers": 150,
            "languages": [
                {"code": "en", "name": "English", "count": 100, "percentage": 66.7},
                {"code": "es", "name": "Spanish", "count": 25, "percentage": 16.7},
                ...
            ]
        }
    """
    if _db is None:
        return {"total_customers": 0, "languages": []}
    
    try:
        # Aggregate by language
        pipeline = [
            {"$match": {"preferred_language": {"$exists": True, "$ne": None}}},
            {"$group": {
                "_id": "$preferred_language",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        
        results = await _db.reroots_customer_profiles.aggregate(pipeline).to_list(20)
        
        # Calculate totals
        total = sum(r["count"] for r in results)
        
        # Include English default for customers without preference
        no_lang = await _db.reroots_customer_profiles.count_documents({
            "$or": [
                {"preferred_language": {"$exists": False}},
                {"preferred_language": None}
            ]
        })
        
        languages = []
        
        # Add detected languages
        for r in results:
            lang_code = r["_id"]
            count = r["count"]
            languages.append({
                "code": lang_code,
                "name": get_language_name(lang_code),
                "native_name": get_native_name(lang_code),
                "is_rtl": is_rtl_language(lang_code),
                "count": count,
                "percentage": round((count / (total + no_lang)) * 100, 1) if total + no_lang > 0 else 0
            })
        
        # Add default English for no-preference customers
        if no_lang > 0:
            languages.append({
                "code": "en",
                "name": "English (Default)",
                "native_name": "English",
                "is_rtl": False,
                "count": no_lang,
                "percentage": round((no_lang / (total + no_lang)) * 100, 1)
            })
        
        # Sort by count
        languages.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "total_customers": total + no_lang,
            "languages": languages
        }
        
    except Exception as e:
        logger.error(f"[LANG] Error getting language breakdown: {e}")
        return {"total_customers": 0, "languages": [], "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# COUNTRY/PHONE LANGUAGE UTILITIES
# ═══════════════════════════════════════════════════════════════════

def get_language_for_country(country_code: str) -> str:
    """
    Get primary language for a country code.
    Used for voice agent greetings.
    
    Args:
        country_code: ISO 2-letter country code (e.g., "CA", "FR")
    
    Returns:
        Language code (e.g., "en", "fr")
    """
    return COUNTRY_LANGUAGE_MAP.get(country_code.upper(), "en")


def get_country_name(country_code: str) -> str:
    """Get country name from code using pycountry."""
    try:
        country = pycountry.countries.get(alpha_2=country_code.upper())
        return country.name if country else country_code
    except Exception:
        return country_code


def get_voice_greeting(language_code: str, brand_name: str = "Reroots") -> str:
    """
    Get voice greeting in specified language.
    
    Args:
        language_code: Language code
        brand_name: Brand name for greeting
    
    Returns:
        Greeting text in specified language
    """
    greetings = {
        "en": f"Hello! I'm the {brand_name} AI assistant. How can I help you with your skincare today?",
        "es": f"¡Hola! Soy el asistente de inteligencia artificial de {brand_name}. ¿Cómo puedo ayudarte con el cuidado de tu piel hoy?",
        "fr": f"Bonjour! Je suis l'assistant IA de {brand_name}. Comment puis-je vous aider avec votre routine beauté aujourd'hui?",
        "de": f"Hallo! Ich bin der {brand_name} KI-Assistent. Wie kann ich Ihnen heute bei Ihrer Hautpflege helfen?",
        "ar": f"مرحباً! أنا مساعد {brand_name} الذكي. كيف يمكنني مساعدتك في العناية ببشرتك اليوم؟",
        "hi": f"नमस्ते! मैं {brand_name} का AI असिस्टेंट हूं। आज मैं आपकी स्किनकेयर में कैसे मदद कर सकता हूं?",
        "pt": f"Olá! Eu sou o assistente de IA da {brand_name}. Como posso ajudar com seus cuidados de pele hoje?",
        "ja": f"こんにちは！{brand_name}のAIアシスタントです。本日のスキンケアについてどのようにお手伝いできますか？",
        "zh": f"您好！我是{brand_name}的AI助手。今天我能为您的护肤提供什么帮助？",
        "ko": f"안녕하세요! {brand_name} AI 어시스턴트입니다. 오늘 스킨케어에 대해 어떻게 도와드릴까요?",
    }
    
    return greetings.get(language_code, greetings["en"])
