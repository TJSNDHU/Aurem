"""
Analytics, QR tracking, customer chat
Extracted from server.py during modularization.
"""

import os
try:
    import resend
except ImportError:
    resend = None
import asyncio
import logging
import json
import hashlib
import secrets
import time
import uuid
import re
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Query, Body, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
try:
    from models.server_models import (
        CustomerChatMessage, CustomerChatRequest, CustomerConversation,
        Referral, User
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
def get_claude_api_key():
    return os.environ.get('EMERGENT_LLM_KEY', '')

# Environment variables
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@aurem.live')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')


# Common imports from server.py scope
import bcrypt
import jwt
try:
    import stripe
except ImportError:
    stripe = None

try:
    from performance_patch import limiter
except ImportError:
    limiter = type('obj', (object,), {'limit': lambda self, *a, **kw: lambda f: f})()

from middleware.security import sanitize_input, validate_email

try:
    from middleware.websocket_manager import WebSocketConnectionManager
    manager = WebSocketConnectionManager()
except ImportError:
    manager = None

from config import JWT_SECRET
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
SITE_URL = os.environ.get("SITE_URL", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# MongoDB client reference (set at startup)
client = None

def set_client(c):
    global client
    client = c

# Helpers from server.py scope
ROOT_DIR = __import__("pathlib").Path(os.path.dirname(os.path.abspath(__file__)))

async def get_current_user(request: Request):
    """Extract user from JWT token in request."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        token = auth.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except Exception:
        return None

async def require_admin(request: Request):
    """Verify admin role from JWT."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ("admin", "founder", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def generate_jwt_token(user_data: dict, expires_hours: int = 24):
    """Generate JWT token."""
    import time as _time
    payload = {
        **user_data,
        "exp": int(_time.time()) + (expires_hours * 3600),
        "iat": int(_time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")



# Shared state — set by server.py at startup
db = None
api_router = None

def set_db(database):
    global db
    db = database

def set_router(router):
    global api_router
    api_router = router

def get_db():
    return db

router = APIRouter()

# ============= ANALYTICS / QR CODE TRACKING =============


class AnalyticsEvent(BaseModel):
    event: str
    source: Optional[str] = None
    medium: Optional[str] = None
    campaign: Optional[str] = None
    page: Optional[str] = None
    timestamp: Optional[str] = None
    data: Optional[dict] = None


@router.post("/analytics/track")
async def track_analytics_event(event: AnalyticsEvent):
    """Track analytics events (QR scans, page views, etc.)"""
    analytics_entry = {
        "id": str(uuid.uuid4()),
        "event": event.event,
        "source": event.source,
        "medium": event.medium,
        "campaign": event.campaign,
        "page": event.page,
        "data": event.data,
        "timestamp": event.timestamp or datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.analytics_events.insert_one(analytics_entry)

    return {"success": True, "event_id": analytics_entry["id"]}


@router.get("/admin/analytics/qr-scans")
async def get_qr_scan_analytics(request: Request):
    """Get QR code scan analytics for admin dashboard"""
    await require_admin(request)

    # Get scan counts by source/campaign
    pipeline = [
        {"$match": {"event": "qr_code_scan"}},
        {
            "$group": {
                "_id": {"source": "$source", "campaign": "$campaign"},
                "count": {"$sum": 1},
                "last_scan": {"$max": "$timestamp"},
            }
        },
        {"$sort": {"count": -1}},
    ]

    results = await db.analytics_events.aggregate(pipeline).to_list(100)

    # Total scans
    total_scans = await db.analytics_events.count_documents({"event": "qr_code_scan"})

    # Scans by day (last 30 days)
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    daily_pipeline = [
        {"$match": {"event": "qr_code_scan", "timestamp": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": {"$substr": ["$timestamp", 0, 10]}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]

    daily_results = await db.analytics_events.aggregate(daily_pipeline).to_list(30)

    return {
        "total_scans": total_scans,
        "by_source": results,
        "daily_scans": daily_results,
    }


class ContactFormRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    subject: str
    message: str


@router.post("/contact")
async def submit_contact_form(data: ContactFormRequest):
    """Public endpoint for contact form submissions"""
    contact = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "email": data.email,
        "phone": data.phone,
        "subject": data.subject,
        "message": data.message,
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.contact_messages.insert_one(contact)

    # Send notification email to admin (if Resend is configured)
    if RESEND_API_KEY:
        try:
            params = {
                "from": SENDER_EMAIL,
                "to": ["admin@reroots.ca"],
                "subject": f"New Contact Form: {data.subject} - {data.name}",
                "html": f"""
                <h2>New Contact Form Submission</h2>
                <p><strong>Name:</strong> {data.name}</p>
                <p><strong>Email:</strong> {data.email}</p>
                <p><strong>Phone:</strong> {data.phone or 'Not provided'}</p>
                <p><strong>Subject:</strong> {data.subject}</p>
                <p><strong>Message:</strong></p>
                <p>{data.message}</p>
                """,
            }
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as e:
            logging.error(f"Failed to send contact notification: {e}")

    return {"message": "Thank you! Your message has been received."}


@router.get("/admin/contact-messages")
async def get_contact_messages(request: Request):
    """Get all contact form submissions"""
    await require_admin(request)
    messages = (
        await db.contact_messages.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return messages


@router.put("/admin/contact-messages/{message_id}/status")
async def update_contact_status(message_id: str, data: dict, request: Request):
    """Update contact message status"""
    await require_admin(request)
    await db.contact_messages.update_one(
        {"id": message_id}, {"$set": {"status": data.get("status", "read")}}
    )
    return {"message": "Status updated"}


# ============= CUSTOMER CHAT SYSTEM =============


@router.post("/chat/customer")
async def customer_chat(req: CustomerChatRequest):
    """Public endpoint for customer chat - AI responds automatically"""

    # Get or create conversation
    conversation_id = req.conversation_id
    if not conversation_id:
        # Create new conversation
        conversation = CustomerConversation(
            customer_name=req.customer_name or "Guest",
            customer_email=req.customer_email,
        )
        conv_dict = conversation.model_dump()
        conv_dict["created_at"] = conv_dict["created_at"].isoformat()
        conv_dict["updated_at"] = conv_dict["updated_at"].isoformat()
        await db.customer_conversations.insert_one(conv_dict)
        conversation_id = conversation.id

    # Save customer message with translation for admin
    translated_content = req.message
    detected_lang = "en"

    # Auto-translate non-English messages for admin viewing
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        llm_key = get_claude_api_key()
        chat = LlmChat(
            api_key=llm_key,
            session_id="chat-translate",
            system_message="You are a language detection and translation assistant.",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        detect_prompt = f"""Detect the language and translate this message to English if it's not already in English.
Respond in JSON format only:
{{"detected_lang": "language_code", "translated": "english translation"}}

Message: {req.message}"""

        response = await chat.send_message_async(
            prompt=detect_prompt, model="gpt-4o-mini"
        )
        import json

        try:
            result = json.loads(response.strip())
            detected_lang = result.get("detected_lang", "en")
            if detected_lang != "en":
                translated_content = result.get("translated", req.message)
        except:
            pass
    except Exception as e:
        logging.error(f"Translation error: {e}")

    customer_msg = CustomerChatMessage(
        conversation_id=conversation_id,
        sender="customer",
        customer_name=req.customer_name,
        customer_email=req.customer_email,
        content=req.message,
    )
    msg_dict = customer_msg.model_dump()
    msg_dict["created_at"] = msg_dict["created_at"].isoformat()
    msg_dict["original_content"] = req.message
    msg_dict["translated_content"] = translated_content
    msg_dict["detected_lang"] = detected_lang
    await db.customer_chat_messages.insert_one(msg_dict)

    # Get store settings for AI configuration
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    live_chat = settings.get("live_chat", {}) if settings else {}
    ai_enabled = live_chat.get("ai_enabled", True)
    ai_model = live_chat.get("ai_model", "gpt-4o")
    escalation_keywords = live_chat.get(
        "escalation_keywords", ["human", "agent", "speak to someone"]
    )

    # Check for escalation keywords
    needs_escalation = any(
        keyword.lower() in req.message.lower() for keyword in escalation_keywords
    )

    ai_response = None
    if ai_enabled and not needs_escalation:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            # Get conversation history for context
            history = (
                await db.customer_chat_messages.find(
                    {"conversation_id": conversation_id}, {"_id": 0}
                )
                .sort("created_at", 1)
                .to_list(20)
            )

            history_text = ""
            for msg in history[-10:]:
                role = "Customer" if msg["sender"] == "customer" else "Assistant"
                history_text += f"{role}: {msg['content']}\n"

            system_prompt = """You are a helpful customer support assistant for ReRoots Aesthetics Inc., a Canadian biotech skincare company based in Toronto.

**OUR FLAGSHIP PRODUCT - AURA-GEN:**
- Full Name: AURA-GEN PDRN + TXA + ARGIRELINE 17.0% Active Recovery Complex
- Price: $99 CAD (often with discounts around $72-75 USD)
- Key Ingredients:
  • PDRN (Polydeoxyribonucleotide) - Salmon-derived DNA fragments for cellular regeneration
  • Tranexamic Acid (TXA) - Brightens skin, reduces hyperpigmentation
  • Argireline - Peptide that reduces expression lines (botox-like effect)
  • Hyaluronic Acid - Deep hydration
  • Niacinamide - Pore minimizing, brightening
  • Total 17.0% active concentration

- Benefits:
  • Anti-aging & wrinkle reduction
  • Skin brightening & even tone
  • Cellular repair & regeneration
  • Deep hydration
  • Reduces fine lines and expression marks
  
- How to Use: Apply 3-4 drops to clean face morning and night. Follow with moisturizer.
- Suitable for: All skin types, especially mature, dull, or hyperpigmented skin
- Made in: Toronto, Canada 🇨🇦
- Cruelty-Free: Yes 🐰

**SHIPPING:**
- Free shipping on orders over $50 CAD in Canada
- International shipping available with calculated rates
- Ships via FlagShip courier

**RETURNS:**
- 30-day return policy for unopened products
- Full refund for defective products

Be friendly, professional, and concise. If customers ask about products, enthusiastically recommend AURA-GEN.
If you cannot help with something specific (like accessing account details or processing refunds), 
politely let them know that a team member will assist them shortly.

Keep responses brief and helpful. Don't mention that you're an AI unless directly asked."""

            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"customer_chat_{conversation_id}",
                system_message=system_prompt,
            ).with_model("openai", ai_model)

            full_message = (
                f"Previous conversation:\n{history_text}\n\nCustomer: {req.message}"
            )
            user_message = UserMessage(text=full_message)

            ai_response = await chat.send_message(user_message)

            # Save AI response
            ai_msg = CustomerChatMessage(
                conversation_id=conversation_id, sender="ai", content=ai_response
            )
            ai_msg_dict = ai_msg.model_dump()
            ai_msg_dict["created_at"] = ai_msg_dict["created_at"].isoformat()
            await db.customer_chat_messages.insert_one(ai_msg_dict)

        except Exception as e:
            logging.error(f"AI chat error: {e}")
            needs_escalation = True

    # Update conversation
    update_data = {
        "last_message": req.message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if needs_escalation:
        update_data["needs_attention"] = True
        update_data["status"] = "escalated"
        ai_response = live_chat.get(
            "offline_message",
            "Thanks for reaching out! A team member will assist you shortly.",
        )

        # Save escalation message
        escalation_msg = CustomerChatMessage(
            conversation_id=conversation_id, sender="ai", content=ai_response
        )
        esc_dict = escalation_msg.model_dump()
        esc_dict["created_at"] = esc_dict["created_at"].isoformat()
        await db.customer_chat_messages.insert_one(esc_dict)

    await db.customer_conversations.update_one(
        {"id": conversation_id}, {"$set": update_data, "$inc": {"message_count": 1}}
    )

    return {
        "conversation_id": conversation_id,
        "response": ai_response,
        "needs_human": needs_escalation,
    }


@router.get("/chat/customer/{conversation_id}")
async def get_customer_chat_history(conversation_id: str):
    """Get chat history for a conversation"""
    messages = (
        await db.customer_chat_messages.find(
            {"conversation_id": conversation_id}, {"_id": 0}
        )
        .sort("created_at", 1)
        .to_list(100)
    )
    return messages


# Admin endpoints for customer chat management
@router.get("/admin/customer-chats")
async def get_all_customer_chats(request: Request, status: Optional[str] = None):
    """Get all customer conversations for admin"""
    await require_admin(request)
    query = {}
    if status:
        query["status"] = status

    conversations = (
        await db.customer_conversations.find(query, {"_id": 0})
        .sort("updated_at", -1)
        .to_list(100)
    )
    return conversations


@router.get("/admin/customer-chats/{conversation_id}")
async def get_customer_chat_detail(conversation_id: str, request: Request):
    """Get detailed chat with messages for admin"""
    await require_admin(request)
    conversation = await db.customer_conversations.find_one(
        {"id": conversation_id}, {"_id": 0}
    )
    messages = (
        await db.customer_chat_messages.find(
            {"conversation_id": conversation_id}, {"_id": 0}
        )
        .sort("created_at", 1)
        .to_list(100)
    )

    # Mark as read
    await db.customer_chat_messages.update_many(
        {"conversation_id": conversation_id, "sender": "customer"},
        {"$set": {"is_read": True}},
    )

    return {"conversation": conversation, "messages": messages}


@router.post("/admin/customer-chats/{conversation_id}/reply")
async def admin_reply_to_chat(conversation_id: str, reply_data: dict, request: Request):
    """Admin reply to customer chat"""
    user = await require_admin(request)

    message = CustomerChatMessage(
        conversation_id=conversation_id,
        sender="admin",
        content=reply_data.get("message", ""),
    )
    msg_dict = message.model_dump()
    msg_dict["created_at"] = msg_dict["created_at"].isoformat()
    await db.customer_chat_messages.insert_one(msg_dict)

    # Update conversation
    await db.customer_conversations.update_one(
        {"id": conversation_id},
        {
            "$set": {
                "last_message": reply_data.get("message"),
                "needs_attention": False,
                "status": "active",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Reply sent"}


@router.put("/admin/customer-chats/{conversation_id}/status")
async def update_chat_status(conversation_id: str, status_data: dict, request: Request):
    """Update conversation status"""
    await require_admin(request)
    await db.customer_conversations.update_one(
        {"id": conversation_id},
        {
            "$set": {
                "status": status_data.get("status", "resolved"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    return {"message": "Status updated"}


# ============= VOICE AI CHAT =============


class VoiceChatRequest(BaseModel):
    message: str
    system_prompt: Optional[str] = None
    conversation_history: Optional[List[dict]] = []


@router.post("/chat/voice")
async def voice_chat(req: VoiceChatRequest):
    """Voice AI chat endpoint - optimized for voice conversations"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        llm_key = get_claude_api_key()
        if not llm_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        # Build conversation context
        system_message = (
            req.system_prompt
            or """You are Alex, a friendly and helpful AI customer support agent for ReRoots, a premium biotech skincare e-commerce store based in Canada. Your role is to:
- Answer questions about ReRoots products (PDRN serums, skincare, etc.)
- Help with order status inquiries (ask for order number or email)
- Explain return and refund policies (30-day returns, refunds within 5-7 days)
- Provide skincare advice
- Be warm, professional, and concise
- Keep responses under 2-3 sentences for voice conversations
- If you don't know something specific, offer to connect them with email support at support@reroots.ca

Store info:
- ReRoots specializes in PDRN (Polydeoxyribonucleotide) biotech skincare
- Free shipping on orders over $50 CAD
- 30-day return policy
- Based in Canada, ships worldwide"""
        )

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"voice-{uuid.uuid4()}",
            system_message=system_message,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        # Build prompt with conversation history
        prompt = req.message
        if req.conversation_history and len(req.conversation_history) > 0:
            history_text = "\n".join(
                [
                    f"{'Customer' if m.get('role') == 'user' else 'You'}: {m.get('content', '')}"
                    for m in req.conversation_history[
                        -4:
                    ]  # Last 4 messages for context
                ]
            )
            prompt = f"Previous conversation:\n{history_text}\n\nCustomer's new message: {req.message}\n\nRespond naturally and helpfully in 1-2 sentences:"

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)

        # Clean up response for voice
        clean_response = response.strip()
        # Remove markdown or special characters that don't work well in speech
        clean_response = (
            clean_response.replace("**", "").replace("*", "").replace("#", "")
        )

        return {"response": clean_response}

    except Exception as e:
        logging.error(f"Voice chat error: {e}")
        return {
            "response": "I'm having a little trouble right now. Please try again or email us at support@reroots.ca for help."
        }


# ============= CUSTOMER MANAGEMENT =============


@router.get("/admin/customers")
async def get_all_customers(request: Request, brand: Optional[str] = None):
    await require_admin(request)
    
    # Base query excludes admin users
    query = {"is_admin": {"$ne": True}}
    
    # Brand filtering for customers
    if brand and brand != "all":
        if brand == "lavela":
            # Customers who have ordered La Vela products or registered via La Vela
            query["$or"] = [
                {"registered_brand": "lavela"},
                {"tags": {"$in": ["lavela", "teen"]}},
            ]
        elif brand == "reroots":
            # ReRoots customers (exclude La Vela registrations)
            query["registered_brand"] = {"$ne": "lavela"}
    
    customers = (
        await db.users.find(query, {"_id": 0, "password": 0})
        .sort("created_at", -1)
        .to_list(500)
    )

    # Enrich with order data
    for customer in customers:
        order_count = await db.orders.count_documents({"user_id": customer["id"]})
        order_pipeline = [
            {"$match": {"user_id": customer["id"], "payment_status": "paid"}},
            {"$group": {"_id": None, "total": {"$sum": "$total"}}},
        ]
        total_spent = await db.orders.aggregate(order_pipeline).to_list(1)
        customer["order_count"] = order_count
        customer["total_spent"] = total_spent[0]["total"] if total_spent else 0

    return customers


@router.get("/admin/customers/{customer_id}")
async def get_customer_details(customer_id: str, request: Request):
    await require_admin(request)
    customer = await db.users.find_one({"id": customer_id}, {"_id": 0, "password": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get customer orders
    orders = (
        await db.orders.find({"user_id": customer_id}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )

    # Get customer reviews
    reviews = await db.reviews.find({"user_id": customer_id}, {"_id": 0}).to_list(50)

    return {"customer": customer, "orders": orders, "reviews": reviews}


@router.delete("/admin/customers/{customer_id}")
async def delete_customer(customer_id: str, request: Request):
    await require_admin(request)
    await db.users.delete_one({"id": customer_id})
    return {"message": "Customer deleted"}


@router.get("/admin/customers/export")
async def export_customers(request: Request):
    await require_admin(request)
    customers = await db.users.find(
        {"is_admin": {"$ne": True}},
        {
            "_id": 0,
            "password": 0,
            "id": 1,
            "email": 1,
            "first_name": 1,
            "last_name": 1,
            "created_at": 1,
        },
    ).to_list(10000)
    return {"customers": customers, "count": len(customers)}


# ============= SEND OFFER TO CUSTOMERS =============


class SendOfferRequest(BaseModel):
    emails: List[str]
    subject: str
    title: Optional[str] = ""
    message: str
    discount_code: Optional[str] = ""
    discount_percent: Optional[str] = ""
    is_exclusive: Optional[bool] = (
        True  # Default to exclusive (only for selected customers)
    )
    expires_at: Optional[str] = None  # Expiry date for the discount code


@router.post("/admin/send-offer")
async def send_offer_to_customers(offer_data: SendOfferRequest, request: Request):
    """Send promotional offer to selected customers"""
    await require_admin(request)

    if not offer_data.emails:
        raise HTTPException(status_code=400, detail="No customers selected")

    if not offer_data.subject or not offer_data.message:
        raise HTTPException(status_code=400, detail="Subject and message are required")

    # If there's a discount code, store it
    if offer_data.discount_code:
        discount_data = {
            "code": offer_data.discount_code.upper(),
            "discount_percent": (
                float(offer_data.discount_percent) if offer_data.discount_percent else 0
            ),
            "is_exclusive": offer_data.is_exclusive,
            "is_active": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Add expiry date if provided
        if offer_data.expires_at:
            discount_data["expires_at"] = offer_data.expires_at + "T23:59:59+00:00"

        if offer_data.is_exclusive:
            # Store exclusive discount code with eligible emails
            await db.exclusive_discounts.update_one(
                {"code": offer_data.discount_code.upper()},
                {
                    "$set": discount_data,
                    "$addToSet": {
                        "eligible_emails": {
                            "$each": [e.lower() for e in offer_data.emails]
                        }
                    },
                },
                upsert=True,
            )
            logging.info(
                f"Exclusive discount code {offer_data.discount_code} created for {len(offer_data.emails)} customers"
            )
        else:
            # Store regular discount code
            await db.discount_codes.update_one(
                {"code": offer_data.discount_code.upper()},
                {"$set": discount_data},
                upsert=True,
            )

    # Format expiry for email
    expiry_text = ""
    if offer_data.expires_at:
        try:
            expiry_date = datetime.strptime(offer_data.expires_at, "%Y-%m-%d")
            expiry_text = f'<p style="color: rgba(255,255,255,0.9); font-size: 12px; margin-top: 5px;">⏰ Expires: {expiry_date.strftime("%B %d, %Y")}</p>'
        except:
            pass

    # Build email HTML
    discount_section = ""
    if offer_data.discount_code:
        exclusive_note = (
            '<p style="color: rgba(255,255,255,0.9); font-size: 12px; margin-top: 10px;">🔒 This code is exclusive to you</p>'
            if offer_data.is_exclusive
            else ""
        )
        discount_section = f"""
        <div style="background: linear-gradient(135deg, #F8A5B8 0%, #C9A86C 100%); padding: 20px; border-radius: 10px; text-align: center; margin: 20px 0;">
            <p style="color: white; font-size: 14px; margin: 0;">Your exclusive code:</p>
            <p style="color: white; font-size: 28px; font-weight: bold; margin: 10px 0; letter-spacing: 3px;">{offer_data.discount_code.upper()}</p>
            {f'<p style="color: white; font-size: 18px; margin: 0;">Get {offer_data.discount_percent}% OFF</p>' if offer_data.discount_percent else ''}
            {exclusive_note}
            {expiry_text}
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ text-align: center; padding: 30px 0; background: linear-gradient(135deg, #FDF9F9 0%, #fff 100%); }}
            .logo {{ font-size: 32px; font-weight: bold; color: #2D2A2E; }}
            .content {{ padding: 30px; background: #fff; }}
            .title {{ font-size: 24px; color: #2D2A2E; font-weight: bold; margin-bottom: 20px; }}
            .message {{ font-size: 16px; color: #5A5A5A; line-height: 1.8; }}
            .cta-button {{ display: inline-block; background: linear-gradient(135deg, #C9A86C 0%, #B8956A 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 30px; font-weight: bold; margin: 25px 0; }}
            .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #888; background: #f9f9f9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">ReRoots</div>
                <p style="color: #5A5A5A; margin: 10px 0 0 0;">Premium Biotech Skincare</p>
            </div>
            <div class="content">
                {f'<h1 class="title">{offer_data.title}</h1>' if offer_data.title else ''}
                <div class="message">{offer_data.message.replace(chr(10), "<br>")}</div>
                {discount_section}
                <p style="text-align: center;">
                    <a href="https://reroots.ca/shop" class="cta-button">Shop Now</a>
                </p>
            </div>
            <div class="footer">
                <p>© 2025 ReRoots. All rights reserved.</p>
                <p>Premium Biotech Skincare | Canada</p>
            </div>
        </div>
    </body>
    </html>
    """

    sent_count = 0
    failed_emails = []

    # Send emails
    if RESEND_API_KEY:
        for email in offer_data.emails:
            try:
                params = {
                    "from": SENDER_EMAIL,
                    "to": [email],
                    "subject": offer_data.subject,
                    "html": html_content,
                }
                await asyncio.to_thread(resend.Emails.send, params)
                sent_count += 1
                logging.info(f"Offer email sent to: {email}")
            except Exception as e:
                logging.error(f"Failed to send offer to {email}: {e}")
                failed_emails.append(email)
    else:
        # Log if email not configured
        logging.warning("Email service not configured. Offers logged but not sent.")
        sent_count = len(offer_data.emails)

    # Store offer in database for records
    await db.sent_offers.insert_one(
        {
            "id": str(uuid.uuid4()),
            "subject": offer_data.subject,
            "title": offer_data.title,
            "message": offer_data.message,
            "discount_code": (
                offer_data.discount_code.upper() if offer_data.discount_code else ""
            ),
            "discount_percent": offer_data.discount_percent,
            "is_exclusive": offer_data.is_exclusive,
            "recipients": offer_data.emails,
            "sent_count": sent_count,
            "failed_emails": failed_emails,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    return {
        "message": f"Offer sent to {sent_count} customer(s)",
        "sent_count": sent_count,
        "failed_count": len(failed_emails),
    }


# Validate exclusive discount code
@router.post("/validate-discount")
async def validate_discount_code_v2(data: dict, request: Request):
    """Validate a discount code - checks partner codes, exclusive codes, and regular codes"""
    code = data.get("code", "").upper().strip()
    email = data.get("email", "").lower().strip()
    user_referral_count = data.get(
        "referral_count", 0
    )  # User's referral count for voucher gate

    if not code:
        raise HTTPException(status_code=400, detail="Discount code required")

    # FIRST: Check if it's a partner/influencer code (VOUCHER GATE applies)
    partner = await db.influencer_applications.find_one(
        {"partner_code": code, "status": "approved"}, {"_id": 0}
    )

    if partner:
        # Get customer discount from store settings
        store_settings = await db.store_settings.find_one(
            {"id": "store_settings"}, {"_id": 0}
        )
        influencer_program = (
            store_settings.get("influencer_program", {}) if store_settings else {}
        )
        customer_discount = influencer_program.get("customer_discount_value", 50.0)
        voucher_gate_threshold = influencer_program.get(
            "voucher_gate_threshold", 10
        )  # Default: 10 referrals needed

        # VOUCHER GATE: Check if user has enough referrals to unlock influencer discount
        # If user came through this partner's link, check the partner's referral count
        partner_referral_count = partner.get("total_referrals", 0)

        # Also check if the user themselves has referrals (if they're a referrer)
        if email:
            user_as_referrer = await db.referrals.count_documents(
                {
                    "referrer_email": email,
                    "status": {"$in": ["signed_up", "purchased", "rewarded"]},
                }
            )
            user_referral_count = max(user_referral_count, user_as_referrer)

        # The voucher gate checks if THIS USER has 10+ referrals to unlock the 50% influencer discount
        voucher_unlocked = user_referral_count >= voucher_gate_threshold

        if voucher_unlocked:
            return {
                "valid": True,
                "code": code,
                "discount_percent": customer_discount,
                "is_partner_code": True,
                "voucher_unlocked": True,
                "referral_count": user_referral_count,
                "threshold": voucher_gate_threshold,
                "partner_name": partner.get(
                    "full_name", partner.get("name", "Partner")
                ),
                "type": "influencer_referral",
                "message": f"🎉 {customer_discount}% Influencer Voucher UNLOCKED! You have {user_referral_count} referrals.",
            }
        else:
            # Voucher is valid but NOT unlocked yet - user needs more referrals
            referrals_needed = voucher_gate_threshold - user_referral_count
            return {
                "valid": True,
                "code": code,
                "discount_percent": 0,  # No discount until threshold reached
                "is_partner_code": True,
                "voucher_unlocked": False,
                "voucher_locked": True,
                "referral_count": user_referral_count,
                "threshold": voucher_gate_threshold,
                "referrals_needed": referrals_needed,
                "partner_name": partner.get(
                    "full_name", partner.get("name", "Partner")
                ),
                "type": "influencer_referral_locked",
                "message": f"🔒 Influencer Voucher requires {voucher_gate_threshold} referrals. You have {user_referral_count}. Get {referrals_needed} more to unlock 50% off!",
            }

    # SECOND: Check if it's the first purchase code (AUTO-APPLIED for first-time buyers)
    store_settings = await db.store_settings.find_one(
        {"id": "store_settings"}, {"_id": 0}
    )
    fp_code = (
        store_settings.get("first_purchase_code", "FIRSTPROTOCOL").upper()
        if store_settings
        else "FIRSTPROTOCOL"
    )
    fp_percent = (
        store_settings.get("first_purchase_code_percent", 25.0)
        if store_settings
        else 25.0
    )
    fp_enabled = (
        store_settings.get("first_purchase_code_enabled", True)
        if store_settings
        else True
    )

    if fp_enabled and code == fp_code:
        # Check if customer is first-time buyer
        if email:
            previous_orders = await db.orders.count_documents(
                {"customer_email": email, "status": {"$nin": ["cancelled", "refunded"]}}
            )
            if previous_orders > 0:
                raise HTTPException(
                    status_code=400,
                    detail="This code is only valid for first-time buyers",
                )

        return {
            "valid": True,
            "code": code,
            "discount_percent": fp_percent,
            "is_first_purchase": True,
            "auto_applied": True,
            "type": "first_purchase",
            "message": f"🎉 {fp_percent}% First-Time Protocol Access discount applied!",
        }

    # THIRD: Check exclusive discounts
    exclusive = await db.exclusive_discounts.find_one({"code": code}, {"_id": 0})

    if exclusive:
        # Check if code is active
        if not exclusive.get("is_active", True):
            raise HTTPException(status_code=400, detail="This code is no longer active")

        # Check expiry
        if exclusive.get("expires_at"):
            try:
                expiry = datetime.fromisoformat(
                    exclusive["expires_at"].replace("Z", "+00:00")
                )
                if datetime.now(timezone.utc) > expiry:
                    raise HTTPException(status_code=400, detail="This code has expired")
            except ValueError:
                pass

        # This is an exclusive code - check if user is eligible
        if exclusive.get("is_exclusive") and email:
            eligible_emails = [e.lower() for e in exclusive.get("eligible_emails", [])]
            if email not in eligible_emails:
                raise HTTPException(
                    status_code=400, detail="This code is not valid for your account"
                )
        elif exclusive.get("is_exclusive") and not email:
            raise HTTPException(
                status_code=400, detail="Please log in to use this exclusive code"
            )

        return {
            "valid": True,
            "code": code,
            "discount_percent": exclusive.get("discount_percent", 0),
            "is_exclusive": True,
            "expires_at": exclusive.get("expires_at"),
            "message": f"🎉 Exclusive {exclusive.get('discount_percent', 0)}% discount applied!",
        }

    # Check regular discount codes
    regular = await db.discount_codes.find_one(
        {"code": code, "is_active": True}, {"_id": 0}
    )

    if regular:
        # Check usage limits
        if regular.get("max_uses") and regular.get("used_count", 0) >= regular.get(
            "max_uses"
        ):
            raise HTTPException(
                status_code=400, detail="This code has reached its usage limit"
            )

        # Check expiry
        if regular.get("expires_at"):
            try:
                expiry_str = regular["expires_at"]
                # Handle both ISO format with and without timezone
                if isinstance(expiry_str, str):
                    expiry_str = expiry_str.replace("Z", "+00:00")
                    if "+" not in expiry_str and "T" in expiry_str:
                        expiry_str = expiry_str + "+00:00"
                    expiry = datetime.fromisoformat(expiry_str)
                else:
                    expiry = expiry_str

                # Make comparison timezone-aware
                now = datetime.now(timezone.utc)
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)

                if now > expiry:
                    raise HTTPException(status_code=400, detail="This code has expired")
            except (ValueError, TypeError):
                pass

        return {
            "valid": True,
            "code": code,
            "discount_percent": (
                regular.get("discount_value", 0)
                if regular.get("discount_type") == "percentage"
                else 0
            ),
            "discount_value": regular.get("discount_value", 0),
            "discount_type": regular.get("discount_type", "percentage"),
            "discount_amount": (
                regular.get("discount_value", 0)
                if regular.get("discount_type") == "fixed"
                else 0
            ),
            "is_exclusive": False,
            "expires_at": regular.get("expires_at"),
            "message": f"✓ {regular.get('discount_value', 0)}{'%' if regular.get('discount_type') == 'percentage' else ' CAD'} discount applied!",
        }
    
    # FOURTH: Check offers collection (SMS/Email offer codes)
    offer_code = await db.offers.find_one(
        {"code": code, "is_active": True}, {"_id": 0}
    )
    
    if offer_code:
        # Check usage limits
        if offer_code.get("max_uses") and offer_code.get("uses_count", 0) >= offer_code.get("max_uses"):
            raise HTTPException(
                status_code=400, detail="This code has reached its usage limit"
            )
        
        discount_pct = offer_code.get("discount_percent") or offer_code.get("discount_value", 0)
        
        return {
            "valid": True,
            "code": code,
            "discount_percent": discount_pct,
            "discount_value": discount_pct,
            "discount_type": "percentage",
            "is_sms_offer": offer_code.get("is_sms_offer", False),
            "is_email_offer": offer_code.get("is_email_offer", False),
            "message": f"🎉 {discount_pct}% discount applied!",
        }
    
    # FIFTH: Check coupons collection
    coupon = await db.coupons.find_one(
        {"code": code, "is_active": True}, {"_id": 0}
    )
    
    if coupon:
        discount_pct = coupon.get("discount_percent") or coupon.get("discount_value", 0)
        
        return {
            "valid": True,
            "code": code,
            "discount_percent": discount_pct,
            "discount_value": discount_pct,
            "discount_type": "percentage",
            "message": f"🎉 {discount_pct}% coupon discount applied!",
        }

    raise HTTPException(status_code=400, detail="Invalid discount code")


@router.post("/checkout/pricing")
async def get_checkout_pricing(data: dict, request: Request):
    """
    Get checkout pricing with auto-applied discounts (Voucher Gate logic).

    Pricing Calculation:
    1. Start with product's RETAIL price (product.price)
    2. Apply product-level discount if any (product.discount_percent)
    3. Apply Founder's Launch Subsidy (50%)
    4. Apply First-Time Protocol Access (25%) if first-time buyer
    5. Apply Influencer Voucher (50%) if 10+ referrals (VOUCHER GATE)
    6. Tax: Always calculated on RETAIL price (original_subtotal)
    7. Total = Final discounted price + Tax
    """
    email = data.get("email", "").lower().strip()
    partner_code = data.get("partner_code", "").upper().strip()
    cart_items = data.get("cart_items", [])

    # Get store settings
    store_settings = (
        await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0}) or {}
    )
    influencer_program = store_settings.get("influencer_program", {})

    # Calculate original subtotal from cart (RETAIL prices, before any discounts)
    original_subtotal = 0
    product_discount_total = 0

    for item in cart_items:
        product_id = item.get("product_id")
        # Support both UUID and slug
        product = await db.products.find_one(
            {"$or": [{"id": product_id}, {"slug": product_id}]}, {"_id": 0}
        )
        if product:
            quantity = item.get("quantity", 1)
            retail_price = product.get("price", 0) or 0
            product_discount_percent = product.get("discount_percent") or 0

            # Calculate retail value (before product discount)
            original_subtotal += retail_price * quantity

            # Calculate product-level discount
            if product_discount_percent and product_discount_percent > 0:
                product_discount_total += (
                    retail_price * (product_discount_percent / 100)
                ) * quantity

    if original_subtotal == 0:
        original_subtotal = data.get("original_subtotal", 100.0)  # Default for testing

    # Start with price after product discount
    running_subtotal = original_subtotal - product_discount_total

    # AUTO-APPLIED DISCOUNTS (only if enabled in admin settings)
    discounts_applied = []

    # Check if auto-discounts are enabled in admin settings
    founder_discount_enabled = store_settings.get("founder_discount_enabled", True)
    first_purchase_discount_enabled = store_settings.get(
        "first_purchase_discount_enabled", True
    )

    # Add product discount to the list if any (product-level discounts always apply)
    if product_discount_total > 0:
        discounts_applied.append(
            {
                "name": "Founder's Launch Subsidy",
                "percent": (
                    round((product_discount_total / original_subtotal) * 100, 1)
                    if original_subtotal > 0
                    else 0
                ),
                "amount": round(product_discount_total, 2),
                "auto_applied": True,
                "type": "founder",
            }
        )
    elif founder_discount_enabled:
        # 1. Founder's Launch Subsidy (50%) - Only applied if enabled and no product discount
        founder_subsidy = store_settings.get("founder_subsidy", {})
        founder_discount_percent = founder_subsidy.get("discount_percent") or 50.0
        founder_discount_amount = round(
            running_subtotal * (founder_discount_percent / 100), 2
        )
        running_subtotal -= founder_discount_amount
        discounts_applied.append(
            {
                "name": founder_subsidy.get("label", "Founder's Launch Subsidy"),
                "percent": founder_discount_percent,
                "amount": founder_discount_amount,
                "auto_applied": True,
                "type": "founder",
            }
        )

    # 2. First-Time Protocol Access (25%) - Only applied if enabled
    is_first_time = True
    if email:
        previous_orders = await db.orders.count_documents(
            {"customer_email": email, "status": {"$nin": ["cancelled", "refunded"]}}
        )
        is_first_time = previous_orders == 0

    if is_first_time and first_purchase_discount_enabled:
        first_time_percent = store_settings.get("first_purchase_discount_percent", 10.0)
        first_time_amount = round(running_subtotal * (first_time_percent / 100), 2)
        running_subtotal -= first_time_amount
        discounts_applied.append(
            {
                "name": "First-Time Protocol Access",
                "percent": first_time_percent,
                "amount": first_time_amount,
                "auto_applied": True,
                "type": "first_time",
            }
        )

    # Base price after auto-applied discounts ($37.50 for $100 product)
    base_price = running_subtotal

    # 3. VOUCHER GATE: Influencer Referral (50%) - Only if enabled and user has 10+ referrals
    voucher_gate_enabled = influencer_program.get("voucher_gate_enabled", True)
    voucher_gate_threshold = influencer_program.get("voucher_gate_threshold", 10)
    influencer_discount_percent = influencer_program.get(
        "customer_discount_value", 50.0
    )

    # Check user's referral count
    user_referral_count = 0
    if email and voucher_gate_enabled:
        user_referral_count = await db.referrals.count_documents(
            {
                "referrer_email": email,
                "status": {"$in": ["signed_up", "purchased", "rewarded"]},
            }
        )
        logger.info(
            f"Voucher Gate: {email} has {user_referral_count} referrals (threshold: {voucher_gate_threshold})"
        )

    voucher_unlocked = (
        voucher_gate_enabled and user_referral_count >= voucher_gate_threshold
    )
    referrals_needed = (
        max(0, voucher_gate_threshold - user_referral_count)
        if voucher_gate_enabled
        else 0
    )

    influencer_voucher = {
        "name": "Influencer Referral Voucher",
        "percent": influencer_discount_percent,
        "amount": 0,
        "unlocked": voucher_unlocked,
        "locked": not voucher_unlocked,
        "referral_count": user_referral_count,
        "threshold": voucher_gate_threshold,
        "referrals_needed": referrals_needed,
        "type": "influencer_voucher",
        "enabled": voucher_gate_enabled,
    }

    if voucher_unlocked:
        influencer_amount = round(
            running_subtotal * (influencer_discount_percent / 100), 2
        )
        running_subtotal -= influencer_amount
        influencer_voucher["amount"] = influencer_amount
        influencer_voucher["applied"] = True
        discounts_applied.append(influencer_voucher)

    # 4. MANUAL DISCOUNT CODE: Apply if provided and valid
    discount_code = data.get("discount_code", "").upper().strip()
    manual_discount_applied = None
    
    if discount_code:
        # Validate the discount code - check multiple collections
        code_data = await db.discount_codes.find_one(
            {"code": discount_code, "is_active": True}, {"_id": 0}
        )
        
        # Also check offers collection (for SMS/Email offer codes)
        if not code_data:
            code_data = await db.offers.find_one(
                {"code": discount_code, "is_active": True}, {"_id": 0}
            )
        
        # Also check coupons collection
        if not code_data:
            code_data = await db.coupons.find_one(
                {"code": discount_code, "is_active": True}, {"_id": 0}
            )
        
        # Also check exclusive_discounts collection
        if not code_data:
            code_data = await db.exclusive_discounts.find_one(
                {"code": discount_code, "is_active": {"$ne": False}}, {"_id": 0}
            )
            # For exclusive codes, verify email eligibility
            if code_data and code_data.get("is_exclusive"):
                eligible_emails = [e.lower() for e in code_data.get("eligible_emails", [])]
                if email and email not in eligible_emails:
                    code_data = None  # Not eligible
                elif not email:
                    code_data = None  # Email required for exclusive codes
        
        if code_data:
            code_discount_percent = code_data.get("discount_percent") or code_data.get("discount_value", 0)
            min_order = code_data.get("min_order_amount", 0)
            
            # Check minimum order requirement against original subtotal
            if original_subtotal >= min_order:
                discount_amount = round(running_subtotal * (code_discount_percent / 100), 2)
                running_subtotal -= discount_amount
                
                manual_discount_applied = {
                    "name": discount_code,
                    "type": "discount_code",
                    "percent": code_discount_percent,
                    "amount": discount_amount,
                    "applied": True,
                }
                discounts_applied.append(manual_discount_applied)
                logger.info(f"Manual discount code applied: {discount_code} - {code_discount_percent}% = ${discount_amount}")
            else:
                logger.info(f"Discount code {discount_code} not applied - min order ${min_order} not met (subtotal: ${original_subtotal})")

    final_subtotal = round(running_subtotal, 2)

    # TAX CALCULATION
    # If no discounts were applied, tax is calculated on the actual selling price
    # If discounts were applied, tax is still on the actual amount being charged (final_subtotal)
    tax_rate = store_settings.get("tax_rate", 13.0)  # Default 13% HST
    tax_enabled = store_settings.get("tax_enabled", True)
    tax_name = store_settings.get("tax_name", "HST")

    if tax_enabled:
        # Tax is calculated on the actual amount being charged (final_subtotal)
        tax_amount = round(final_subtotal * (tax_rate / 100), 2)
        tax_note = f"Tax calculated on ${final_subtotal:.2f} selling price"
    else:
        tax_amount = 0.0
        tax_note = "Tax disabled"

    # Total savings
    total_savings = round(original_subtotal - final_subtotal, 2)
    savings_percent = (
        round((total_savings / original_subtotal) * 100, 1)
        if original_subtotal > 0
        else 0
    )

    # Final total = discounted price + tax (no shipping in this endpoint)
    final_total = round(final_subtotal + tax_amount, 2)

    # Determine pricing tier
    pricing_tier = (
        "premium_clinical"
        if not discounts_applied
        else (
            "founding_member_unlocked" if voucher_unlocked else "founding_member_base"
        )
    )

    return {
        "original_subtotal": original_subtotal,
        "base_price": base_price,  # Price after auto-applied discounts
        "final_subtotal": final_subtotal,  # Final price after all discounts
        "discounts_applied": discounts_applied,
        "influencer_voucher": influencer_voucher if voucher_gate_enabled else None,
        "voucher_unlocked": voucher_unlocked,
        "referral_count": user_referral_count,
        "referrals_needed": referrals_needed,
        "voucher_gate_threshold": voucher_gate_threshold,
        "tax": {
            "rate": tax_rate if tax_enabled else 0,
            "amount": tax_amount,
            "name": tax_name,
            "calculated_on": "selling_price",
            "note": tax_note,
        },
        "total": final_total,
        "savings": {"amount": total_savings, "percent": savings_percent},
        "is_first_time_buyer": is_first_time,
        "pricing_tier": pricing_tier,
    }


# Get all exclusive offers (admin)
@router.get("/admin/exclusive-offers")
async def get_exclusive_offers(request: Request):
    """Get all exclusive discount codes and their recipients"""
    await require_admin(request)

    offers = (
        await db.exclusive_discounts.find({}, {"_id": 0})
        .sort("updated_at", -1)
        .to_list(100)
    )
    return {"offers": offers}


# Delete exclusive discount code (admin)
@router.delete("/admin/exclusive-offers/{code}")
async def delete_exclusive_offer(code: str, request: Request):
    """Delete an exclusive discount code"""
    await require_admin(request)

    result = await db.exclusive_discounts.delete_one({"code": code.upper()})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Code not found")

    return {"message": "Exclusive code deleted"}


# Toggle exclusive offer ON/OFF (admin)
@router.put("/admin/exclusive-offers/{code}/toggle")
async def toggle_exclusive_offer(code: str, request: Request):
    """Toggle an exclusive discount code ON/OFF"""
    await require_admin(request)

    # Find the current offer
    offer = await db.exclusive_discounts.find_one({"code": code.upper()})
    if not offer:
        raise HTTPException(status_code=404, detail="Code not found")

    # Toggle the is_active status
    new_status = not offer.get("is_active", True)
    await db.exclusive_discounts.update_one(
        {"code": code.upper()},
        {"$set": {"is_active": new_status, "updated_at": datetime.now(timezone.utc)}},
    )

    return {
        "message": f"Offer {'enabled' if new_status else 'disabled'}",
        "is_active": new_status,
    }


# Get my offers (customer-facing - only active offers)
@router.get("/my-offers")
async def get_my_offers(request: Request):
    """Get active exclusive offers for the logged-in user"""
    try:
        # Get user from token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return {"offers": []}

        token = auth_header.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            email = payload.get("email", "").lower()
        except:
            return {"offers": []}

        if not email:
            return {"offers": []}

        # Find all ACTIVE offers where this user is eligible
        offers = await db.exclusive_discounts.find(
            {
                "is_active": {"$ne": False},  # Only active offers
                "eligible_emails": {
                    "$elemMatch": {"$regex": f"^{email}$", "$options": "i"}
                },
            },
            {"_id": 0},
        ).to_list(100)

        # Filter out expired offers
        valid_offers = []
        now = datetime.now(timezone.utc)
        for offer in offers:
            if offer.get("expires_at"):
                try:
                    expiry = datetime.fromisoformat(
                        offer["expires_at"].replace("Z", "+00:00")
                    )
                    if now > expiry:
                        continue
                except:
                    pass
            valid_offers.append(offer)

        return {"offers": valid_offers}
    except Exception as e:
        logging.error(f"Error getting my offers: {e}")
        return {"offers": []}


# ============= CLEANUP TEST DATA =============


@router.delete("/admin/cleanup-test-data")
async def cleanup_test_data(request: Request):
    """Remove all test orders, contacts, and subscribers (keeps admin account)"""
    await require_admin(request)

    results = {
        "orders_deleted": 0,
        "customers_deleted": 0,
        "subscribers_deleted": 0,
        "carts_deleted": 0,
        "reviews_deleted": 0,
    }

    # Delete all orders
    order_result = await db.orders.delete_many({})
    results["orders_deleted"] = order_result.deleted_count

    # Delete all customers except admin
    customer_result = await db.users.delete_many(
        {"email": {"$ne": "admin@reroots.ca"}, "is_admin": {"$ne": True}}
    )
    results["customers_deleted"] = customer_result.deleted_count

    # Delete all newsletter subscribers
    subscriber_result = await db.newsletter_subscribers.delete_many({})
    results["subscribers_deleted"] = subscriber_result.deleted_count

    # Delete all carts
    cart_result = await db.carts.delete_many({})
    results["carts_deleted"] = cart_result.deleted_count

    # Delete all reviews
    review_result = await db.reviews.delete_many({})
    results["reviews_deleted"] = review_result.deleted_count

    # Delete test chat sessions
    await db.chat_sessions.delete_many({})

    # Delete sent offers history
    await db.sent_offers.delete_many({})

    logging.info(f"Test data cleanup: {results}")

    return {"message": "Test data cleaned up successfully", "details": results}


