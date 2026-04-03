"""
ReRoots AI Translation Router
Multi-language translation for product content and customer communication
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import json

router = APIRouter(prefix="/api/translate", tags=["translation"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "ru": "Russian"
}

class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str
    context: Optional[str] = None  # product, email, ui, support

class BulkTranslateRequest(BaseModel):
    texts: List[str]
    source_lang: str = "en"
    target_lang: str
    context: Optional[str] = None


async def translate_text(text: str, source_lang: str, target_lang: str, context: str = "general") -> str:
    """Translate text using LLM"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Translation service not configured")
        
        import secrets
        chat = LlmChat(
            api_key=api_key,
            session_id=f"translate_{secrets.token_hex(6)}",
            system_message=f"""You are a professional translator for a luxury skincare brand.
Translate the following text from {SUPPORTED_LANGUAGES.get(source_lang, source_lang)} to {SUPPORTED_LANGUAGES.get(target_lang, target_lang)}.
Context: {context} content for a skincare e-commerce platform.
Maintain brand voice: sophisticated, scientific yet accessible.
Only respond with the translated text, no explanations."""
        ).with_model("openai", "gpt-5-mini")
        
        response = await chat.send_message(UserMessage(text=f"Translate this:\n{text}"))
        return response.strip()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@router.get("/languages")
async def get_supported_languages():
    """Get list of supported languages"""
    return {"languages": SUPPORTED_LANGUAGES}


@router.post("/text")
async def translate_single(data: TranslateRequest):
    """Translate a single text"""
    if data.target_lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported target language: {data.target_lang}")
    
    translated = await translate_text(
        data.text,
        data.source_lang,
        data.target_lang,
        data.context or "general"
    )
    
    # Cache translation
    await db.translations.insert_one({
        "source_text": data.text[:500],
        "translated_text": translated[:500],
        "source_lang": data.source_lang,
        "target_lang": data.target_lang,
        "context": data.context,
        "created_at": datetime.now(timezone.utc)
    })
    
    return {
        "original": data.text,
        "translated": translated,
        "source_lang": data.source_lang,
        "target_lang": data.target_lang
    }


@router.post("/bulk")
async def translate_bulk(data: BulkTranslateRequest):
    """Translate multiple texts"""
    if data.target_lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported target language: {data.target_lang}")
    
    results = []
    for text in data.texts[:20]:  # Limit to 20 texts
        try:
            translated = await translate_text(
                text,
                data.source_lang,
                data.target_lang,
                data.context or "general"
            )
            results.append({
                "original": text,
                "translated": translated,
                "success": True
            })
        except Exception as e:
            results.append({
                "original": text,
                "translated": None,
                "success": False,
                "error": str(e)
            })
    
    return {
        "total": len(data.texts),
        "translated": sum(1 for r in results if r["success"]),
        "results": results
    }


@router.post("/product/{product_id}")
async def translate_product(product_id: str, target_lang: str):
    """Translate all product content to target language"""
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    translated_fields = {}
    fields_to_translate = ["name", "description", "short_description", "how_to_use", "ingredients_text"]
    
    for field in fields_to_translate:
        if field in product and product[field]:
            translated_fields[field] = await translate_text(
                product[field],
                "en",
                target_lang,
                "product"
            )
    
    # Store translation
    await db.product_translations.update_one(
        {"product_id": product_id, "lang": target_lang},
        {"$set": {
            "translations": translated_fields,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    
    return {
        "product_id": product_id,
        "target_lang": target_lang,
        "translations": translated_fields
    }
