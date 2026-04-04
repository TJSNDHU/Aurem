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
# BUSINESS ID GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/api/integration/generate-key")
async def generate_integration_key(email: str):
    """
    Generate business ID and API key for integration
    """
    try:
        from server import db
        
        # Generate unique business ID
        business_id = f"biz_{secrets.token_urlsafe(12)}"
        api_key = f"sk_aurem_{secrets.token_urlsafe(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Store integration credentials
        integration_doc = {
            "business_id": business_id,
            "email": email,
            "api_key_hash": api_key_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
            "features": {
                "chat_widget": True,
                "lead_capture": True,
                "booking": True,
                "webhooks": True,
                "whatsapp": True
            }
        }
        
        await db.integrations.insert_one(integration_doc)
        
        return {
            "success": True,
            "business_id": business_id,
            "api_key": api_key,  # Only shown once!
            "message": "Save this API key securely - it won't be shown again."
        }
        
    except Exception as e:
        print(f"[Generate Key] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
