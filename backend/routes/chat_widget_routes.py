"""
Chat Widget API Routes
═══════════════════════════════════════════════════════════════════
REST API endpoints for the embeddable chat widget.
Includes brand isolation middleware and cross-device memory support.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brands_config import is_valid_brand_key, get_brand_config, get_enabled_brand_keys
from services.chat_widget import get_chat_widget_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat-widget", tags=["Chat Widget"])

# Database reference - will be set from server.py
_db = None

def set_db(database):
    """Set database reference from server.py startup."""
    global _db
    _db = database
    logger.info("Chat widget routes: Database reference set")


# ═══════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════

class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""
    pass  # brand_key comes from header


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    session_id: str
    message: str


class SessionResponse(BaseModel):
    """Response with session details."""
    session_id: str
    brand_key: str
    ai_name: str
    primary_color: str
    logo_path: str
    powered_by_text: str
    copyright_footer: str


class MessageResponse(BaseModel):
    """Response after sending a message."""
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    remaining_messages: Optional[int] = None
    reset_at: Optional[str] = None
    cross_device_memory: Optional[bool] = None


# ═══════════════════════════════════════════════════════════════════
# BRAND ISOLATION HELPER
# ═══════════════════════════════════════════════════════════════════

def validate_brand_key(brand_key: Optional[str]) -> str:
    """
    Validate brand_key header.
    Raises 403 if missing or invalid.
    """
    if not brand_key:
        raise HTTPException(
            status_code=403,
            detail="Missing brand_key header"
        )
    
    if not is_valid_brand_key(brand_key):
        raise HTTPException(
            status_code=403,
            detail=f"Invalid brand_key: {brand_key}"
        )
    
    return brand_key


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    # Check X-Forwarded-For for proxied requests
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    # Fall back to direct client
    return request.client.host if request.client else "unknown"


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.get("/config")
async def get_widget_config(
    request: Request,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key")
):
    """
    Get widget configuration for a brand.
    Used by frontend to initialize the widget.
    """
    brand_key = validate_brand_key(brand_key)
    config = get_brand_config(brand_key)
    
    return {
        "brand_key": brand_key,
        "ai_name": config.ai_name,
        "primary_color": config.primary_color,
        "logo_path": config.logo_path,
        "powered_by_text": config.powered_by_text,
        "copyright_footer": config.copyright_footer
    }


@router.post("/session", response_model=SessionResponse)
async def create_session(
    request: Request,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key")
):
    """
    Create a new chat session.
    Logs IP address and user agent for audit trail.
    """
    brand_key = validate_brand_key(brand_key)
    
    # Get client info for audit
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Get service with database
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    service = get_chat_widget_service(_db)
    
    try:
        session = await service.create_session(
            brand_key=brand_key,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Auto-detect location from IP in background
        try:
            from services.geolocation import detect_and_store_location
            import asyncio
            asyncio.create_task(detect_and_store_location(
                session_id=session["session_id"],
                ip_address=ip_address
            ))
        except Exception as e:
            logger.warning(f"[GEO] Auto-detect failed: {e}")
        
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# GEOLOCATION ENDPOINT - For browser location
# ═══════════════════════════════════════════════════════════════════

class LocationUpdateRequest(BaseModel):
    """Request to update location from browser geolocation."""
    session_id: str
    lat: float
    lon: float
    customer_email: Optional[str] = None


@router.post("/location")
async def update_session_location(
    request: Request,
    body: LocationUpdateRequest,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key")
):
    """
    Update session with browser geolocation coordinates.
    
    Called when user grants location permission in the chat widget.
    Provides highest accuracy location for weather-based recommendations.
    """
    brand_key = validate_brand_key(brand_key)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        from services.geolocation import detect_and_store_location
        
        location = await detect_and_store_location(
            session_id=body.session_id,
            lat=body.lat,
            lon=body.lon,
            customer_email=body.customer_email
        )
        
        if location.get("error"):
            return {
                "success": False,
                "error": location["error"]
            }
        
        return {
            "success": True,
            "city": location.get("city"),
            "region": location.get("region"),
            "country": location.get("country"),
            "source": location.get("source")
        }
        
    except Exception as e:
        logger.error(f"[GEO] Location update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update location")


@router.post("/message", response_model=MessageResponse)
async def send_message(
    request: Request,
    body: SendMessageRequest,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key"),
    authorization: Optional[str] = Header(None)
):
    """
    Send a message and get AI response.
    Includes enhanced rate limiting, brand guard, and cross-device memory.
    
    Rate Limits:
    - Unauthenticated: 10 requests per hour per IP
    - Authenticated: 50 requests per hour per IP
    - 5+ identical messages in 1 hour: 24 hour block
    
    CROSS-DEVICE MEMORY: If Authorization header is provided with a valid
    JWT token, the conversation memory is tied to the user's account,
    enabling personalization across all their devices.
    """
    brand_key = validate_brand_key(brand_key)
    ip_address = get_client_ip(request)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    # Check if user is authenticated and extract email for cross-device memory
    is_authenticated = bool(authorization and authorization.startswith("Bearer "))
    user_email = None
    
    if is_authenticated:
        try:
            import jwt
            from config import JWT_SECRET, JWT_ALGORITHM
            
            token = authorization.replace("Bearer ", "")
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("user_id")
            
            if user_id:
                user = await _db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
                if user:
                    user_email = user.get("email")
        except Exception as e:
            # Log but don't fail - just continue without cross-device memory
            logger.warning(f"JWT validation failed for cross-device memory: {e}")
    
    # Enhanced rate limiting
    from services.ai_rate_limiter import get_ai_rate_limiter
    rate_limiter = get_ai_rate_limiter(_db)
    
    allowed, rate_info = await rate_limiter.check_rate_limit(
        ip_address=ip_address,
        is_authenticated=is_authenticated,
        message=body.message
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=rate_info.get("message", "Rate limit exceeded. For urgent help WhatsApp us at +14168869408"),
            headers={
                "Retry-After": str(rate_info.get("retry_after_seconds", 3600)),
                "X-RateLimit-Limit": str(rate_info.get("limit", 10)),
                "X-RateLimit-Remaining": "0"
            }
        )
    
    service = get_chat_widget_service(_db)
    
    try:
        result = await service.send_message(
            session_id=body.session_id,
            brand_key=brand_key,
            user_message=body.message,
            ip_address=ip_address,
            user_email=user_email  # Pass email for cross-device memory
        )
        
        # Add rate limit info and cross-device status to response
        result["remaining_messages"] = rate_info.get("remaining", 0)
        result["cross_device_memory"] = user_email is not None
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# SKIN ANALYSIS WITH IMAGE - Multimodal AI
# ═══════════════════════════════════════════════════════════════════

class SkinAnalysisRequest(BaseModel):
    """Request for skin analysis with image."""
    session_id: str
    message: str = "Please analyze my skin from this photo and recommend products"
    image: str  # Base64 encoded image


@router.post("/analyze-skin", response_model=MessageResponse)
async def analyze_skin_image(
    request: Request,
    body: SkinAnalysisRequest,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key"),
    authorization: Optional[str] = Header(None)
):
    """
    Analyze skin from uploaded image using multimodal AI.
    
    Accepts a base64-encoded image and analyzes skin condition,
    then recommends appropriate products from the brand's catalog.
    
    Rate Limits: Same as message endpoint.
    """
    import os
    import base64
    from datetime import datetime, timezone
    
    brand_key = validate_brand_key(brand_key)
    ip_address = get_client_ip(request)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    # Check if user is authenticated
    is_authenticated = bool(authorization and authorization.startswith("Bearer "))
    
    # Enhanced rate limiting
    from services.ai_rate_limiter import get_ai_rate_limiter
    rate_limiter = get_ai_rate_limiter(_db)
    
    allowed, rate_info = await rate_limiter.check_rate_limit(
        ip_address=ip_address,
        is_authenticated=is_authenticated,
        message=body.message
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=rate_info.get("message", "Rate limit exceeded. For urgent help WhatsApp us at +14168869408"),
            headers={
                "Retry-After": str(rate_info.get("retry_after_seconds", 3600)),
                "X-RateLimit-Limit": str(rate_info.get("limit", 10)),
                "X-RateLimit-Remaining": "0"
            }
        )
    
    try:
        # Validate and extract base64 image
        image_data = body.image
        if image_data.startswith('data:'):
            # Remove data URL prefix (data:image/jpeg;base64,)
            image_data = image_data.split(',', 1)[1]
        
        # Validate it's valid base64
        try:
            decoded = base64.b64decode(image_data)
            if len(decoded) > 5 * 1024 * 1024:  # 5MB limit
                raise HTTPException(status_code=400, detail="Image too large. Maximum 5MB allowed.")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image data")
        
        # Get brand config for system prompt
        config = get_brand_config(brand_key)
        
        # Create skin analysis prompt
        skin_analysis_prompt = f"""You are {config.ai_name}, a professional skincare advisor with expertise in analyzing skin conditions.

A customer has shared a photo of their skin. Analyze the image and provide:

1. **Skin Assessment**: Describe what you observe (skin type, visible concerns, texture, hydration level, any notable features)

2. **Personalized Recommendations**: Based on your analysis, recommend specific {config.company_name} products that would benefit this skin type/condition.

3. **Usage Tips**: Provide brief guidance on how to use the recommended products.

IMPORTANT GUIDELINES:
- Be warm, encouraging, and professional
- Never diagnose medical conditions - recommend seeing a dermatologist for serious concerns
- Focus on the AURA-GEN product line when making recommendations
- Be specific about which products address which concerns
- If the image quality is poor, politely ask for a clearer photo

Customer's message: {body.message}"""

        # Use emergentintegrations for multimodal chat
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            raise HTTPException(status_code=503, detail="AI service not configured")
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"skin_analysis_{body.session_id}",
            system_message=skin_analysis_prompt
        )
        
        # Use GPT-4o for vision capabilities
        chat.with_model("openai", "gpt-4o")
        
        # Create message with image using ImageContent
        image_content = ImageContent(image_base64=image_data)
        user_msg = UserMessage(
            text=body.message,
            file_contents=[image_content]
        )
        
        response = await chat.send_message(user_msg)
        
        # Log the interaction
        collection_name = f"{config.collection_prefix}chat_messages"
        
        # Log user message with image flag
        await _db[collection_name].insert_one({
            "session_id": body.session_id,
            "brand_key": brand_key,
            "direction": "user",
            "content": body.message,
            "has_image": True,
            "image_analysis": True,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc)
        })
        
        # Log AI response
        await _db[collection_name].insert_one({
            "session_id": body.session_id,
            "brand_key": brand_key,
            "direction": "assistant",
            "content": response,
            "image_analysis": True,
            "timestamp": datetime.now(timezone.utc)
        })
        
        logger.info(f"Skin analysis completed for session {body.session_id[:16]}...")
        
        return {
            "success": True,
            "response": response,
            "remaining_messages": rate_info.get("remaining", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Skin analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to analyze image. Please try again.")


@router.get("/history/{session_id}")
async def get_history(
    request: Request,
    session_id: str,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key")
):
    """
    Get conversation history for a session.
    Only returns messages for the authenticated brand.
    """
    brand_key = validate_brand_key(brand_key)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    service = get_chat_widget_service(_db)
    
    history = await service.get_conversation_history(
        session_id=session_id,
        brand_key=brand_key
    )
    
    return {"messages": history}


@router.get("/rate-limit/{session_id}")
async def check_rate_limit(
    request: Request,
    session_id: str,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key")
):
    """
    Check rate limit status for a session.
    """
    brand_key = validate_brand_key(brand_key)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    service = get_chat_widget_service(_db)
    
    return await service.check_rate_limit(session_id, brand_key)


# ═══════════════════════════════════════════════════════════════════
# LANGUAGE DETECTION & ANALYTICS
# ═══════════════════════════════════════════════════════════════════

class LanguageDetectRequest(BaseModel):
    """Request to detect language from text."""
    text: str


@router.post("/detect-language")
async def detect_language_endpoint(
    request: Request,
    body: LanguageDetectRequest,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key")
):
    """
    Detect the language of input text.
    
    Returns language code, name, RTL flag, and confidence.
    Used by frontend to apply RTL styles and inform the user.
    """
    brand_key = validate_brand_key(brand_key)
    
    try:
        from utils.language import detect_language
        
        result = detect_language(body.text)
        return result
        
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        return {
            "language_code": "en",
            "language_name": "English",
            "native_name": "English",
            "is_rtl": False,
            "confidence": 0,
            "detected": False,
            "error": str(e)
        }


@router.get("/languages")
async def get_supported_languages():
    """
    Get all supported languages for chat widget.
    
    Returns list of languages with RTL info for UI rendering.
    """
    from utils.language import LANGUAGE_MAP
    
    languages = []
    for code, info in LANGUAGE_MAP.items():
        languages.append({
            "code": code,
            "name": info.get("name", code),
            "native_name": info.get("native", code),
            "is_rtl": info.get("rtl", False)
        })
    
    # Sort by name
    languages.sort(key=lambda x: x["name"])
    
    return {
        "languages": languages,
        "rtl_languages": ["ar", "he", "fa", "ur", "yi", "ps", "sd"]
    }


@router.get("/language-analytics")
async def get_language_analytics(
    request: Request,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key")
):
    """
    Get language breakdown for admin dashboard.
    
    Returns count and percentage of customers by preferred language.
    """
    brand_key = validate_brand_key(brand_key)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        from utils.language import get_language_breakdown
        
        result = await get_language_breakdown()
        return result
        
    except Exception as e:
        logger.error(f"Language analytics error: {e}")
        return {
            "total_customers": 0,
            "languages": [],
            "error": str(e)
        }


class SetLanguageRequest(BaseModel):
    """Request to manually set language preference."""
    session_id: str
    language_code: str
    language_name: str
    is_manual_override: bool = True


@router.post("/set-language")
async def set_language_preference(
    request: Request,
    body: SetLanguageRequest,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key")
):
    """
    Manually set customer's language preference.
    
    Called when customer selects a language from the dropdown.
    Manual override takes priority over auto-detection.
    """
    brand_key = validate_brand_key(brand_key)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        from datetime import datetime, timezone
        from utils.language import is_rtl_language
        
        customer_id = f"session_{body.session_id[:32]}"
        
        # Update customer profile with manual language preference
        await _db.reroots_customer_profiles.update_one(
            {"customer_email": customer_id},
            {
                "$set": {
                    "preferred_language": body.language_code,
                    "language_name": body.language_name,
                    "language_source": "manual_override",
                    "language_confidence": 1.0,
                    "language_updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        logger.info(f"[LANG] Manual language set: {body.language_code} for session {body.session_id[:8]}...")
        
        return {
            "success": True,
            "language_code": body.language_code,
            "language_name": body.language_name,
            "is_rtl": is_rtl_language(body.language_code)
        }
        
    except Exception as e:
        logger.error(f"Set language error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ═══════════════════════════════════════════════════════════════════
# CROSS-DEVICE MEMORY - Account Linking
# ═══════════════════════════════════════════════════════════════════

class LinkSessionRequest(BaseModel):
    """Request to link chat session to user account."""
    session_id: str


@router.post("/link-account")
async def link_session_to_account(
    request: Request,
    body: LinkSessionRequest,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key"),
    authorization: Optional[str] = Header(None)
):
    """
    Link a chat session to a logged-in user account.
    
    CROSS-DEVICE MEMORY: When a user logs in, this endpoint merges their
    current session's conversation memory with their account-based profile.
    This allows users to access their AI conversation history and preferences
    from any device.
    
    Requires: Valid JWT token in Authorization header
    Returns: Merged customer profile with cross-device memory
    """
    brand_key = validate_brand_key(brand_key)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    # Validate JWT token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        import jwt
        from config import JWT_SECRET, JWT_ALGORITHM
        
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get user details from database
        user = await _db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_email = user.get("email")
        user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or None
        
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found")
        
        # Link session to account using customer memory service
        from services.customer_memory import get_customer_memory
        
        customer_memory = get_customer_memory(_db)
        merged_profile = await customer_memory.link_session_to_account(
            session_id=body.session_id,
            user_email=user_email,
            user_id=user_id,
            user_name=user_name
        )
        
        logger.info(f"[CROSS-DEVICE] Session {body.session_id[:8]}... linked to {user_email}")
        
        # Return safe profile data (exclude internal fields)
        return {
            "success": True,
            "cross_device_memory_enabled": True,
            "profile": {
                "skin_type": merged_profile.get("skin_type"),
                "skin_concerns": merged_profile.get("skin_concerns", []),
                "products_interested": merged_profile.get("products_interested", []),
                "purchase_intent": merged_profile.get("purchase_intent"),
                "interaction_count": merged_profile.get("interaction_count", 0),
                "first_seen": merged_profile.get("first_seen").isoformat() if isinstance(merged_profile.get("first_seen"), datetime) else merged_profile.get("first_seen"),
            }
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Link account error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile")
async def get_customer_profile(
    request: Request,
    session_id: str,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key"),
    authorization: Optional[str] = Header(None)
):
    """
    Get customer profile for cross-device memory.
    
    If user is authenticated, returns account-based profile (cross-device).
    Otherwise, returns session-based profile (single device).
    
    Returns: Customer profile with personalization data
    """
    brand_key = validate_brand_key(brand_key)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    from services.customer_memory import get_customer_memory
    
    customer_memory = get_customer_memory(_db)
    user_email = None
    
    # Try to get user email from JWT if provided
    if authorization and authorization.startswith("Bearer "):
        try:
            import jwt
            from config import JWT_SECRET, JWT_ALGORITHM
            
            token = authorization.replace("Bearer ", "")
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("user_id")
            
            if user_id:
                user = await _db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
                if user:
                    user_email = user.get("email")
        except Exception as e:
            logger.warning(f"JWT validation failed: {e}")
    
    # Get profile (prioritizes account-based if email available)
    customer_id = f"session_{session_id[:32]}"
    profile = await customer_memory.get_profile(customer_id, user_email)
    
    # Return safe profile data
    return {
        "success": True,
        "cross_device_memory": user_email is not None,
        "profile": {
            "skin_type": profile.get("skin_type"),
            "skin_concerns": profile.get("skin_concerns", []),
            "allergies": profile.get("allergies", []),
            "products_interested": profile.get("products_interested", []),
            "products_mentioned": profile.get("products_mentioned", []),
            "purchase_intent": profile.get("purchase_intent"),
            "age_range": profile.get("age_range"),
            "interaction_count": profile.get("interaction_count", 0),
            "user_name": profile.get("user_name"),
        }
    }



@router.get("/cross-device-history")
async def get_cross_device_conversation_history(
    request: Request,
    brand_key: Optional[str] = Header(None, alias="X-Brand-Key"),
    authorization: Optional[str] = Header(None),
    limit: int = 10
):
    """
    Get conversation history across all sessions for cross-device sync.
    
    CROSS-DEVICE MEMORY: Returns the last N messages from all sessions
    linked to the authenticated user's email. This allows customers to
    pick up exactly where they left off on any device.
    
    Requires: Valid JWT token in Authorization header
    Returns: List of messages with role, content, timestamp
    """
    brand_key = validate_brand_key(brand_key)
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    # Require authentication for cross-device history
    if not authorization or not authorization.startswith("Bearer "):
        return {"success": False, "messages": [], "error": "Authentication required"}
    
    try:
        import jwt
        from config import JWT_SECRET, JWT_ALGORITHM
        
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        
        if not user_id:
            return {"success": False, "messages": [], "error": "Invalid token"}
        
        # Get user email
        user = await _db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "first_name": 1})
        if not user or not user.get("email"):
            return {"success": False, "messages": [], "error": "User not found"}
        
        user_email = user.get("email")
        user_name = user.get("first_name", "")
        
        # Get cross-device conversation history
        service = get_chat_widget_service(_db)
        messages = await service.get_cross_device_history(
            user_email=user_email,
            brand_key=brand_key,
            limit=limit
        )
        
        logger.info(f"[CROSS-DEVICE] Loaded {len(messages)} messages for {user_email[:8]}...")
        
        return {
            "success": True,
            "messages": messages,
            "user_name": user_name,
            "message_count": len(messages)
        }
        
    except jwt.ExpiredSignatureError:
        return {"success": False, "messages": [], "error": "Token expired"}
    except jwt.InvalidTokenError:
        return {"success": False, "messages": [], "error": "Invalid token"}
    except Exception as e:
        logger.error(f"Cross-device history error: {e}", exc_info=True)
        return {"success": False, "messages": [], "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════

@router.get("/health")
async def widget_health():
    """Health check for chat widget service."""
    return {
        "status": "ok",
        "service": "chat-widget",
        "enabled_brands": get_enabled_brand_keys()
    }
