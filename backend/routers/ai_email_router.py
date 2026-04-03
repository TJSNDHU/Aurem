"""
AI Email Router - Wire AI Content Generation to Resend Email Sending
Enables: Generate AI email → Preview → Send
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import resend

# Import existing services
from services.content_ai import generate_content, CONTENT_TYPES, apply_brand_guard
from routers.email_service import base_template, send_email, FROM_EMAIL, ADMIN_EMAIL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-email", tags=["AI Email"])

# MongoDB reference
_db = None

def set_db(database):
    """Set database reference"""
    global _db
    _db = database

# Initialize Resend
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class GenerateEmailRequest(BaseModel):
    """Request to generate AI email content"""
    email_type: str = Field(..., description="Type: promo, announcement, followup, newsletter, restock, custom")
    subject_style: str = Field(default="engaging", description="Style: engaging, urgent, personal, question, benefit")
    context: Dict[str, Any] = Field(default={}, description="Context like product name, offer, audience")
    tone: str = Field(default="warm", description="Tone: warm, professional, playful, urgent")


class SendEmailRequest(BaseModel):
    """Request to send generated email"""
    to: List[str] = Field(..., description="List of recipient emails")
    subject: str = Field(..., description="Email subject line")
    body_html: str = Field(..., description="Generated HTML body")
    save_to_history: bool = Field(default=True, description="Save to content history")


class BroadcastRequest(BaseModel):
    """Request for bulk email broadcast"""
    segment: str = Field(default="all", description="Segment: all, gold, diamond, elite, inactive, recent")
    subject: str = Field(..., description="Email subject")
    body_html: str = Field(..., description="Email HTML content")
    test_mode: bool = Field(default=True, description="If true, only send to admin")


class SequenceEmailRequest(BaseModel):
    """Request for automated email sequence"""
    sequence_type: str = Field(..., description="Type: welcome, abandoned_cart, post_purchase, reengagement")
    user_email: str = Field(..., description="Target user email")
    user_name: str = Field(default="Customer", description="User name")
    context: Dict[str, Any] = Field(default={}, description="Additional context")


# ═══════════════════════════════════════════════════════════════════════════════
# AI EMAIL GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

EMAIL_PROMPTS = {
    "promo": """Write a promotional email for ReRoots biotech skincare.
Product/Offer: {product}
Discount: {discount}
Target Audience: {audience}

Requirements:
- Lead with the benefit, not the discount
- Create desire before revealing the offer
- Include a clear, single CTA
- 150-200 words max
- Luxury biotech voice""",

    "announcement": """Write an announcement email for ReRoots.
Announcement: {announcement}
Key Details: {details}

Requirements:
- Build excitement from the first line
- Clear, scannable format
- One main message, one CTA
- 100-150 words max""",

    "followup": """Write a follow-up email for a ReRoots customer.
Previous Interaction: {interaction}
Goal: {goal}

Requirements:
- Reference the previous interaction naturally
- Provide value, not just a sales pitch
- Warm and personal tone
- 100-150 words max""",

    "newsletter": """Write a newsletter email for ReRoots subscribers.
Topic: {topic}
Featured Products: {products}
Tip/Education: {tip}

Requirements:
- Educational first, promotional second
- Include skincare tip or ingredient spotlight
- Subtle product mentions
- 200-250 words max""",

    "restock": """Write a restock notification email.
Product: {product}
Previous Interest: The customer was waiting for this

Requirements:
- Create urgency without being pushy
- Mention limited quantities tastefully
- Clear CTA to purchase
- 80-120 words max""",

    "custom": """Write an email for ReRoots based on:
{custom_prompt}

Requirements:
- Match ReRoots luxury biotech voice
- Clear single purpose
- One CTA
- Professional but warm"""
}


@router.post("/generate")
async def generate_ai_email(request: GenerateEmailRequest):
    """
    Generate AI email content with subject lines.
    Returns preview HTML and multiple subject line options.
    """
    try:
        email_type = request.email_type
        context = request.context
        
        # Build prompt from template
        prompt_template = EMAIL_PROMPTS.get(email_type, EMAIL_PROMPTS["custom"])
        
        # Fill in context
        prompt = prompt_template.format(
            product=context.get("product", "AURA-GEN Series"),
            discount=context.get("discount", "exclusive offer"),
            audience=context.get("audience", "skincare enthusiasts"),
            announcement=context.get("announcement", "exciting news"),
            details=context.get("details", ""),
            interaction=context.get("interaction", "recent purchase"),
            goal=context.get("goal", "build relationship"),
            topic=context.get("topic", "skincare science"),
            products=context.get("products", "AURA-GEN TXA+PDRN Serum"),
            tip=context.get("tip", ""),
            custom_prompt=context.get("custom_prompt", "general update")
        )
        
        # Generate body content
        body_result = await generate_content("product_description", {
            "product_name": f"Email: {email_type}",
            "ingredients": [],
            "benefits": [prompt],
            "target_audience": context.get("audience", "customers")
        })
        
        if not body_result.get("success"):
            # Fallback: direct prompt
            body_content = f"""
            <p>Dear valued customer,</p>
            <p>{context.get('announcement', 'We have exciting news to share with you.')}</p>
            <p>Discover the latest from ReRoots biotech skincare.</p>
            """
        else:
            body_content = body_result.get("output", "")
            # Convert to HTML paragraphs
            body_content = "<p>" + body_content.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
        
        # Apply brand guard
        body_content = apply_brand_guard(body_content)
        
        # Generate subject lines
        subject_result = await generate_content("email_subjects", {
            "email_goal": email_type,
            "target_audience": context.get("audience", "existing customers")
        })
        
        subject_lines = []
        if subject_result.get("success"):
            # Parse subject lines from output
            output = subject_result.get("output", "")
            import re
            matches = re.findall(r'["\']([^"\']+)["\']', output)
            subject_lines = matches[:5] if matches else ["Your ReRoots Update"]
        else:
            subject_lines = [
                "Something special awaits",
                "Your skin deserves this",
                "ReRoots: A moment for you",
                "Unlock your skin's potential",
                "The science of beautiful skin"
            ]
        
        # Generate full HTML preview
        cta_text = context.get("cta_text", "SHOP NOW")
        cta_link = context.get("cta_link", "https://reroots.ca/app")
        title = context.get("title", "")
        
        preview_html = base_template(
            title=title or subject_lines[0] if subject_lines else "Your Update",
            content=body_content,
            cta_text=cta_text,
            cta_link=cta_link
        )
        
        return {
            "success": True,
            "email_type": email_type,
            "subject_lines": subject_lines,
            "body_content": body_content,
            "preview_html": preview_html,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"[AI-Email] Generate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# SEND EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/send")
async def send_ai_email(request: SendEmailRequest):
    """
    Send generated email to recipients.
    """
    if not RESEND_API_KEY:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    try:
        results = []
        
        for recipient in request.to:
            success = send_email(recipient, request.subject, request.body_html)
            results.append({
                "email": recipient,
                "sent": success
            })
        
        # Save to history if requested
        if request.save_to_history and _db is not None:
            await _db.ai_email_history.insert_one({
                "subject": request.subject,
                "recipients": request.to,
                "sent_count": len([r for r in results if r["sent"]]),
                "sent_at": datetime.now(timezone.utc).isoformat()
            })
        
        sent_count = len([r for r in results if r["sent"]])
        
        return {
            "success": True,
            "sent_count": sent_count,
            "total": len(request.to),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"[AI-Email] Send error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# BROADCAST TO SEGMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/broadcast")
async def broadcast_email(request: BroadcastRequest):
    """
    Send email to customer segment.
    """
    if not RESEND_API_KEY:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Test mode - only send to admin
        if request.test_mode:
            success = send_email(ADMIN_EMAIL, f"[TEST] {request.subject}", request.body_html)
            return {
                "success": success,
                "mode": "test",
                "sent_to": ADMIN_EMAIL
            }
        
        # Get recipients based on segment
        query = {}
        if request.segment == "gold":
            query = {"tier": "Gold"}
        elif request.segment == "diamond":
            query = {"tier": "Diamond"}
        elif request.segment == "elite":
            query = {"tier": "Elite"}
        elif request.segment == "inactive":
            # Users who haven't ordered in 30 days
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            query = {"last_order_date": {"$lt": cutoff.isoformat()}}
        elif request.segment == "recent":
            # Users who ordered in last 7 days
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            query = {"last_order_date": {"$gte": cutoff.isoformat()}}
        
        # Fetch users
        users = await _db.users.find(
            query,
            {"email": 1, "name": 1, "_id": 0}
        ).limit(500).to_list(500)  # Safety limit
        
        sent_count = 0
        for user in users:
            email = user.get("email")
            if email:
                if send_email(email, request.subject, request.body_html):
                    sent_count += 1
        
        # Log broadcast
        await _db.ai_email_broadcasts.insert_one({
            "segment": request.segment,
            "subject": request.subject,
            "sent_count": sent_count,
            "total_recipients": len(users),
            "sent_at": datetime.now(timezone.utc).isoformat()
        })
        
        return {
            "success": True,
            "mode": "live",
            "segment": request.segment,
            "sent_count": sent_count,
            "total_recipients": len(users)
        }
        
    except Exception as e:
        logger.error(f"[AI-Email] Broadcast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATED SEQUENCES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/sequence/trigger")
async def trigger_email_sequence(request: SequenceEmailRequest):
    """
    Trigger an automated email sequence for a user.
    Sequences: welcome, abandoned_cart, post_purchase, reengagement
    """
    try:
        from routers.email_service import (
            send_welcome_email,
            send_abandoned_cart_reminder
        )
        
        sequence_type = request.sequence_type
        user_email = request.user_email
        user_name = request.user_name
        context = request.context
        
        if sequence_type == "welcome":
            # Send welcome email
            success = send_welcome_email(
                user_email,
                user_name,
                context.get("tier", "Silver"),
                context.get("points", 100)
            )
            return {"success": success, "sequence": "welcome", "step": 1}
        
        elif sequence_type == "abandoned_cart":
            # Send cart reminder (sequence 1, 2, or 3)
            step = context.get("step", 1)
            cart_items = context.get("cart_items", [])
            discount_code = context.get("discount_code") if step >= 2 else None
            
            success = send_abandoned_cart_reminder(
                user_email,
                user_name,
                cart_items,
                step,
                discount_code
            )
            return {"success": success, "sequence": "abandoned_cart", "step": step}
        
        elif sequence_type == "post_purchase":
            # Generate and send post-purchase follow-up
            result = await generate_ai_email(GenerateEmailRequest(
                email_type="followup",
                context={
                    "interaction": f"purchased {context.get('product', 'AURA-GEN products')}",
                    "goal": "thank and provide usage tips"
                }
            ))
            
            if result.get("success"):
                success = send_email(
                    user_email,
                    result.get("subject_lines", ["Thank you for your order"])[0],
                    result.get("preview_html", "")
                )
                return {"success": success, "sequence": "post_purchase", "step": 1}
        
        elif sequence_type == "reengagement":
            # Generate reengagement email
            result = await generate_ai_email(GenerateEmailRequest(
                email_type="promo",
                context={
                    "product": "AURA-GEN Collection",
                    "discount": "15% comeback offer",
                    "audience": "returning customers"
                }
            ))
            
            if result.get("success"):
                success = send_email(
                    user_email,
                    "We miss you! Here's 15% off",
                    result.get("preview_html", "")
                )
                return {"success": success, "sequence": "reengagement", "step": 1}
        
        return {"success": False, "error": f"Unknown sequence: {sequence_type}"}
        
    except Exception as e:
        logger.error(f"[AI-Email] Sequence error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# HISTORY & ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/history")
async def get_email_history(limit: int = 50):
    """Get AI email history"""
    if _db is None:
        return {"emails": []}
    
    try:
        history = await _db.ai_email_history.find(
            {},
            {"_id": 0}
        ).sort("sent_at", -1).limit(limit).to_list(limit)
        
        return {"emails": history}
        
    except Exception as e:
        logger.error(f"[AI-Email] History error: {e}")
        return {"emails": []}


@router.get("/broadcasts")
async def get_broadcast_history(limit: int = 20):
    """Get broadcast history"""
    if _db is None:
        return {"broadcasts": []}
    
    try:
        broadcasts = await _db.ai_email_broadcasts.find(
            {},
            {"_id": 0}
        ).sort("sent_at", -1).limit(limit).to_list(limit)
        
        return {"broadcasts": broadcasts}
        
    except Exception as e:
        logger.error(f"[AI-Email] Broadcasts error: {e}")
        return {"broadcasts": []}
