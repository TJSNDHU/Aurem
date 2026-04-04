"""
AUREM External Integration API
Handles chat widget, lead capture, webhooks, and third-party integrations
"""

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import secrets
import hashlib
import jwt
import os

router = APIRouter()

# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ChatMessage(BaseModel):
    message: str
    business_id: Optional[str] = None
    session_id: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None

class LeadCapture(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    message: Optional[str] = None
    source: str  # website, landing_page, form, etc.
    business_id: str

class BookingRequest(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    date: str
    time: str
    service: Optional[str] = None
    message: Optional[str] = None
    business_id: str

class WebhookEvent(BaseModel):
    event_type: str  # lead_created, message_sent, booking_made, etc.
    data: Dict[str, Any]
    business_id: str

# ═══════════════════════════════════════════════════════════════════════════════
# CHAT WIDGET API
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/chat/message")
async def handle_chat_message(request: ChatMessage):
    """
    Handle incoming chat messages from embedded widget
    Returns AI-generated response
    """
    try:
        from server import db
        
        # Store message in database
        message_doc = {
            "session_id": request.session_id,
            "business_id": request.business_id or "default",
            "message": request.message,
            "role": "user",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_email": request.user_email,
            "user_name": request.user_name
        }
        
        await db.chat_sessions.insert_one(message_doc)
        
        # Generate AI response (simple keyword matching for now)
        response_text = generate_chat_response(request.message)
        
        # Store AI response
        response_doc = {
            "session_id": request.session_id,
            "business_id": request.business_id or "default",
            "message": response_text,
            "role": "assistant",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await db.chat_sessions.insert_one(response_doc)
        
        return {
            "success": True,
            "response": response_text,
            "session_id": request.session_id
        }
        
    except Exception as e:
        print(f"[Chat Message] Error: {e}")
        return {
            "success": False,
            "response": "I apologize, but I'm experiencing technical difficulties. Please try again in a moment.",
            "error": str(e)
        }


def generate_chat_response(message: str) -> str:
    """Generate contextual AI response based on message content"""
    msg_lower = message.lower()
    
    # Greetings
    if any(word in msg_lower for word in ['hi', 'hello', 'hey', 'greetings']):
        return "Hello! I'm ORA, your AI business assistant. I can help you automate your operations, capture leads, schedule meetings, and grow your business. What would you like to know?"
    
    # Pricing
    elif any(word in msg_lower for word in ['price', 'pricing', 'cost', 'plan', 'subscription']):
        return "AUREM offers flexible pricing plans:\n\n📦 Starter: $299/month - Perfect for small businesses\n🚀 Professional: $799/month - Advanced automation\n⚡ Enterprise: Custom pricing - Full platform access\n\nAll plans include 24/7 AI support, lead capture, and WhatsApp integration. Would you like to schedule a demo?"
    
    # Booking/Demo
    elif any(word in msg_lower for word in ['book', 'meeting', 'schedule', 'demo', 'call', 'appointment']):
        return "I'd love to schedule a demo for you! Please share:\n\n1. Your name\n2. Email address\n3. Preferred date & time\n\nOr click the 'Book Meeting' button to use our scheduler."
    
    # Automation
    elif any(word in msg_lower for word in ['automat', 'ai', 'intelligent', 'bot']):
        return "AUREM automates your entire business workflow:\n\n✅ Lead Capture & Nurturing\n✅ Customer Communication (WhatsApp, Email, SMS)\n✅ Appointment Scheduling\n✅ Sales Qualification\n✅ Analytics & Insights\n\nOur AI agents work 24/7, handling customer conversations and converting leads while you focus on growth."
    
    # Features
    elif any(word in msg_lower for word in ['feature', 'capability', 'what can', 'how does']):
        return "AUREM provides:\n\n🤖 AI Conversation Agents\n📊 Real-time Analytics\n📅 Smart Booking System\n💬 WhatsApp Business Integration\n📧 Email Automation\n🎯 Lead Scoring & Qualification\n🔔 Panic Button (Human Takeover)\n🌍 Multilingual Support\n\nWhich feature interests you most?"
    
    # Contact/Support
    elif any(word in msg_lower for word in ['contact', 'support', 'help', 'talk', 'human']):
        return "I'm here to help! For immediate assistance:\n\n📧 Email: support@aurem.ai\n💬 WhatsApp: +1 (555) AUREM-AI\n📞 Phone: Schedule a call\n\nOr I can connect you with our team right now. What works best for you?"
    
    # Default
    else:
        return f"Great question! AUREM specializes in business automation and AI-powered growth. We help companies:\n\n• Automate customer communication\n• Capture and convert leads\n• Scale operations without hiring\n\nCould you tell me more about your business goals? I'll provide specific recommendations."


# ═══════════════════════════════════════════════════════════════════════════════
# LEAD CAPTURE API
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/leads/capture")
async def capture_lead(lead: LeadCapture):
    """
    Capture lead from external website forms
    Automatically creates lead in AUREM system
    """
    try:
        from server import db
        
        # Create lead document
        lead_doc = {
            "lead_id": f"lead_{secrets.token_urlsafe(12)}",
            "business_id": lead.business_id,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company,
            "message": lead.message,
            "source": lead.source,
            "status": "new",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await db.leads.insert_one(lead_doc)
        
        # Trigger automation (email, WhatsApp, etc.)
        # await trigger_lead_automation(lead_doc)
        
        return {
            "success": True,
            "lead_id": lead_doc["lead_id"],
            "message": "Lead captured successfully"
        }
        
    except Exception as e:
        print(f"[Lead Capture] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# BOOKING API
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/booking/create")
async def create_booking(booking: BookingRequest):
    """
    Create booking/appointment from external widget
    """
    try:
        from server import db
        
        booking_doc = {
            "booking_id": f"booking_{secrets.token_urlsafe(12)}",
            "business_id": booking.business_id,
            "name": booking.name,
            "email": booking.email,
            "phone": booking.phone,
            "date": booking.date,
            "time": booking.time,
            "service": booking.service,
            "message": booking.message,
            "status": "confirmed",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.bookings.insert_one(booking_doc)
        
        # Send confirmation email/SMS
        # await send_booking_confirmation(booking_doc)
        
        return {
            "success": True,
            "booking_id": booking_doc["booking_id"],
            "message": "Booking confirmed! You'll receive a confirmation email shortly."
        }
        
    except Exception as e:
        print(f"[Booking] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK API
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/webhook/receive")
async def receive_webhook(event: WebhookEvent, request: Request):
    """
    Receive webhooks from external services
    (Stripe, Zapier, Make.com, etc.)
    """
    try:
        from server import db
        
        # Verify webhook signature (if applicable)
        # signature = request.headers.get('X-Webhook-Signature')
        # if not verify_webhook_signature(signature, event):
        #     raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Store webhook event
        webhook_doc = {
            "event_id": f"evt_{secrets.token_urlsafe(12)}",
            "event_type": event.event_type,
            "data": event.data,
            "business_id": event.business_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "processed": False
        }
        
        await db.webhook_events.insert_one(webhook_doc)
        
        # Process webhook based on type
        await process_webhook_event(webhook_doc)
        
        return {
            "success": True,
            "event_id": webhook_doc["event_id"],
            "message": "Webhook received and processed"
        }
        
    except Exception as e:
        print(f"[Webhook] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_webhook_event(event: dict):
    """Process different webhook event types"""
    event_type = event["event_type"]
    
    # Handle different event types
    if event_type == "payment.success":
        # Update subscription, activate features
        pass
    elif event_type == "lead.created":
        # Trigger lead nurturing sequence
        pass
    elif event_type == "booking.cancelled":
        # Send cancellation notification
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# API KEY MANAGEMENT (Tenant-Based)
# ═══════════════════════════════════════════════════════════════════════════════

def get_current_user(authorization: str = Header(None)):
    """Extract user from JWT token and fetch full user details from database"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    token = authorization.replace("Bearer ", "")
    try:
        import jwt
        import os
        payload = jwt.decode(token, os.getenv("JWT_SECRET", "aurem-secret-key"), algorithms=["HS256"])
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token - no user_id")
        
        return {"user_id": user_id, "payload": payload}
    except Exception as e:
        print(f"[Auth Error] {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_user_from_db(user_id: str):
    """Fetch user details from database"""
    from server import db
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/api/integration/keys")
async def generate_api_key(authorization: str = Header(None)):
    """
    Generate new API key for current tenant
    """
    try:
        auth = get_current_user(authorization)
        user_id = auth["user_id"]
        
        # Fetch full user details from database
        user = await get_user_from_db(user_id)
        
        tenant_id = user.get("tenant_id")
        email = user.get("email", "unknown")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID not found for user")
        
        from server import db
        
        # Generate unique API key
        key_id = f"key_{secrets.token_urlsafe(12)}"
        api_key = f"sk_aurem_{secrets.token_urlsafe(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Store API key
        key_doc = {
            "key_id": key_id,
            "tenant_id": tenant_id,
            "email": email,
            "api_key_hash": api_key_hash,
            "key_preview": f"sk_aurem_{'•' * 20}{api_key[-8:]}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": None,
            "active": True,
            "usage_count": 0
        }
        
        await db.api_keys.insert_one(key_doc)
        
        return {
            "success": True,
            "key_id": key_id,
            "api_key": api_key,  # Only shown once!
            "message": "Save this API key securely - it won't be shown again."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Generate API Key] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/integration/keys")
async def list_api_keys(authorization: str = Header(None)):
    """
    List all API keys for current tenant
    """
    try:
        auth = get_current_user(authorization)
        user_id = auth["user_id"]
        
        # Fetch full user details from database
        user = await get_user_from_db(user_id)
        
        tenant_id = user.get("tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID not found for user")
        
        from server import db
        
        keys = await db.api_keys.find(
            {"tenant_id": tenant_id},
            {"_id": 0, "api_key_hash": 0}
        ).sort("created_at", -1).to_list(100)
        
        return {
            "success": True,
            "keys": keys,
            "count": len(keys)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[List API Keys] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/integration/keys/{key_id}")
async def revoke_api_key(key_id: str, authorization: str = Header(None)):
    """
    Revoke an API key
    """
    try:
        auth = get_current_user(authorization)
        user_id = auth["user_id"]
        
        # Fetch full user details from database
        user = await get_user_from_db(user_id)
        
        tenant_id = user.get("tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID not found for user")
        
        from server import db
        
        # Verify key belongs to tenant
        key = await db.api_keys.find_one({"key_id": key_id, "tenant_id": tenant_id})
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Mark as inactive
        await db.api_keys.update_one(
            {"key_id": key_id},
            {"$set": {"active": False, "revoked_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        return {
            "success": True,
            "message": "API key revoked successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Revoke API Key] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# API KEY VALIDATION (for widget requests)
# ═══════════════════════════════════════════════════════════════════════════════

async def validate_api_key(api_key: str) -> dict:
    """Validate API key and return tenant info"""
    try:
        from server import db
        
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        key_doc = await db.api_keys.find_one(
            {"api_key_hash": api_key_hash, "active": True},
            {"_id": 0}
        )
        
        if not key_doc:
            return None
        
        # Update last used timestamp
        await db.api_keys.update_one(
            {"key_id": key_doc["key_id"]},
            {
                "$set": {"last_used": datetime.now(timezone.utc).isoformat()},
                "$inc": {"usage_count": 1}
            }
        )
        
        return key_doc
        
    except Exception as e:
        print(f"[Validate API Key] Error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session"""
    try:
        from server import db
        
        messages = await db.chat_sessions.find(
            {"session_id": session_id},
            {"_id": 0}
        ).sort("timestamp", 1).to_list(100)
        
        return {
            "success": True,
            "messages": messages,
            "count": len(messages)
        }
        
    except Exception as e:
        print(f"[Chat History] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
