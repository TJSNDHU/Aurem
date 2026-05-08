"""
WhatsApp AI Test Endpoint
"""
import os
import time
import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
import httpx

from pinchtab_browser import RerootsBrowser, BrowserToolkit, detect_intent, Intent

router = APIRouter(tags=["WhatsApp Test"])

class WATestRequest(BaseModel):
    message: str
    customer_name: str = "Admin Test"

# Global browser toolkit
_wa_browser: Optional[RerootsBrowser] = None
_wa_toolkit: Optional[BrowserToolkit] = None

async def get_wa_toolkit() -> BrowserToolkit:
    global _wa_browser, _wa_toolkit
    if _wa_toolkit is None:
        _wa_browser = RerootsBrowser()
        await _wa_browser.start()
        _wa_toolkit = BrowserToolkit(_wa_browser)
    return _wa_toolkit

@router.post("/admin/whatsapp/test")
async def test_whatsapp_ai(req: WATestRequest):
    """
    Test endpoint for WhatsApp AI - simulates customer message processing.
    """
    start = time.time()
    REROOTS_BASE = "https://reroots.ca"
    
    intent, extracted = detect_intent(req.message)
    toolkit = await get_wa_toolkit()
    
    live_data = None
    fetch_url = None
    
    try:
        if intent == Intent.STOCK_CHECK:
            fetch_url = f"{REROOTS_BASE}/api/products"
            res = await toolkit.get_stock()
            live_data = res if not res.startswith("I'm having") else None
        elif intent == Intent.ORDER_STATUS:
            fetch_url = f"{REROOTS_BASE}/api/orders/track/{extracted or '?'}"
            res = await toolkit.get_order_status(extracted)
            live_data = res if res.startswith("[") else None
        elif intent == Intent.INGREDIENTS:
            fetch_url = f"{REROOTS_BASE}/api/products"
            res = await toolkit.get_ingredients()
            live_data = res if res.startswith("[") else None
        elif intent == Intent.PRODUCT_INFO:
            fetch_url = f"{REROOTS_BASE}/api/products"
            res = await toolkit.get_product_info()
            live_data = res if res.startswith("[") else None
        elif intent == Intent.SHIPPING_RATE:
            fetch_url = f"{REROOTS_BASE}/shipping"
            res = await toolkit.get_shipping_info()
            live_data = res if res.startswith("[") else None
    except Exception as e:
        logging.error(f"WhatsApp test toolkit error: {e}")
    
    system_prompt = """CRITICAL INSTRUCTION: You MUST always respond in English only, regardless of what language the user writes in. Never switch languages.

You are the ReRoots Aesthetics AI assistant on WhatsApp.
You represent the brand with a warm, knowledgeable, and concise tone.
Keep replies under 200 words for WhatsApp readability.
Brands: AURA-GEN (ACRC Rich Cream + ARC Serum combo at CAD $149), La Vela Bianca, OROÉ.
"""
    
    if live_data:
        system_prompt += f"\n\nLIVE DATA:\n{live_data}"
    
    try:
        reply = await generate_wa_reply(system_prompt, req.message, req.customer_name)
    except Exception as e:
        logging.error(f"WhatsApp test AI error: {e}")
        reply = f"I'd be happy to help! Based on your question about {intent.value.replace('_', ' ')}, please visit reroots.ca for the most current information."
    
    return {
        "intent": intent.value,
        "extracted_value": extracted,
        "fetch_url": fetch_url,
        "live_data": live_data,
        "reply": reply,
        "latency_ms": int((time.time() - start) * 1000),
        "browser_used": _wa_browser.available if _wa_browser else False,
        "fallback_used": live_data is not None,
    }

async def generate_wa_reply(system_prompt: str, message: str, customer_name: str) -> str:
    """Generate AI reply using OpenRouter."""
    try:
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if openrouter_key:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openrouter_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "openai/gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"{customer_name}: {message}"}
                        ],
                        "max_tokens": 300,
                        "temperature": 0.4
                    },
                    timeout=30
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"OpenRouter error: {e}")
    
    return "Thank you for reaching out! Please visit reroots.ca for product information."
