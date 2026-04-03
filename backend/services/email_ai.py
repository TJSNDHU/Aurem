"""
Email AI Service for Reroots
Automated email generation and sending via SendGrid
Activates when SENDGRID_API_KEY is added to environment

5 Email Types:
1. Welcome email - new customer registration
2. Post-purchase follow-up - 3 days after AURA-GEN order
3. 7-day review request - after delivery
4. Re-engagement - 30 days inactive
5. Low stock alert - product stock < 20
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

# MongoDB reference
_db = None

# SendGrid configuration
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "hello@reroots.ca")
SENDGRID_FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "ReRoots Skincare")

# LLM configuration
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
LLM_MODEL = "anthropic/claude-sonnet-4"

# Brand voice rules
BRAND_VOICE_RULES = """
BRAND VOICE RULES - STRICTLY FOLLOW:
- Say "age recovery" NOT "anti-aging"
- Say "AURA-GEN System" NOT "products"
- Say "skin renewal" NOT "anti-wrinkle"
- Tone: warm, knowledgeable, clinical-meets-luxe
- Never mention competitors by name
- Focus on skin health journey, not quick fixes
- Use "clinical-grade" and "medical aesthetics" terminology
- Sign off as "The ReRoots Team" or "Tj & The ReRoots Team"
"""

EMAIL_TYPES = {
    "welcome": {
        "name": "Welcome Email",
        "subject": "Welcome to Reroots — your skin journey starts here",
        "trigger": "new_customer_registration",
        "description": "Sent when a new customer registers"
    },
    "post_purchase": {
        "name": "Post-Purchase Follow-up",
        "subject": "Your AURA-GEN System — day 3 tips",
        "trigger": "3_days_after_order",
        "description": "Sent 3 days after AURA-GEN combo order"
    },
    "review_request": {
        "name": "7-Day Review Request",
        "subject": "How is your skin feeling?",
        "trigger": "7_days_after_delivery",
        "description": "Warm, non-pushy review request"
    },
    "reengagement": {
        "name": "Re-engagement",
        "subject": "Checking in on your skin",
        "trigger": "30_days_inactive",
        "description": "Personalized check-in for inactive customers"
    },
    "low_stock": {
        "name": "Low Stock Alert",
        "subject": "Your favorite is running low",
        "trigger": "stock_below_20",
        "description": "Urgency email for wishlist/cart items"
    }
}


def set_db(database):
    """Set database reference"""
    global _db
    _db = database


def is_sendgrid_configured() -> bool:
    """Check if SendGrid is configured"""
    return bool(SENDGRID_API_KEY)


async def get_customer_profile(customer_id: str) -> Optional[Dict]:
    """Get customer profile from reroots_customer_profiles"""
    if _db is None:
        return None
    
    try:
        profile = await _db.reroots_customer_profiles.find_one(
            {"customer_id": customer_id},
            {"_id": 0}
        )
        return profile
    except Exception as e:
        logger.error(f"[EMAIL_AI] Failed to get customer profile: {e}")
        return None


async def get_customer_by_email(email: str) -> Optional[Dict]:
    """Get customer by email"""
    if _db is None:
        return None
    
    try:
        user = await _db.users.find_one(
            {"email": email},
            {"_id": 0, "password": 0, "password_hash": 0}
        )
        return user
    except Exception as e:
        logger.error(f"[EMAIL_AI] Failed to get customer: {e}")
        return None


def apply_brand_guard(text: str) -> str:
    """Apply brand guard to strip competitor mentions"""
    competitors = [
        "La Mer", "Tatcha", "Drunk Elephant", "SK-II", "Estee Lauder",
        "Clinique", "Lancome", "Olay", "Neutrogena", "CeraVe", "The Ordinary"
    ]
    
    result = text
    for competitor in competitors:
        result = result.replace(competitor, "other brands")
        result = result.replace(competitor.lower(), "other brands")
    
    return result


async def generate_email_content(
    email_type: str,
    customer_email: str,
    context: Optional[Dict] = None
) -> Dict[str, Any]:
    """Generate personalized email content using Claude"""
    
    if not LLM_API_KEY:
        return {
            "success": False,
            "error": "LLM API key not configured"
        }
    
    # Get customer profile for personalization
    customer = await get_customer_by_email(customer_email)
    profile = None
    if customer:
        profile = await get_customer_profile(customer.get("id", ""))
    
    email_config = EMAIL_TYPES.get(email_type)
    if not email_config:
        return {
            "success": False,
            "error": f"Unknown email type: {email_type}"
        }
    
    # Build context for Claude
    customer_context = ""
    if profile:
        if profile.get("skin_type"):
            customer_context += f"Skin type: {profile['skin_type']}\n"
        if profile.get("concerns"):
            concerns = profile["concerns"] if isinstance(profile["concerns"], list) else [profile["concerns"]]
            customer_context += f"Skin concerns: {', '.join(concerns)}\n"
        if profile.get("products_mentioned"):
            customer_context += f"Interested in: {', '.join(profile['products_mentioned'][:3])}\n"
    
    if customer:
        customer_context += f"Customer name: {customer.get('name', 'Valued Customer')}\n"
    
    # Build prompt based on email type
    prompts = {
        "welcome": f"""Write a warm, personalized welcome email for a new ReRoots customer.
{customer_context}
The email should:
- Welcome them to the ReRoots family
- Reference their skin concern if known
- Introduce the AURA-GEN System briefly
- Invite them to explore and ask questions
- Be warm but professional, clinical-meets-luxe tone
- Keep it under 200 words""",

        "post_purchase": f"""Write a helpful post-purchase follow-up email for day 3 of using AURA-GEN.
{customer_context}
Additional context: {context or {}}
The email should:
- Thank them for choosing AURA-GEN
- Provide day 3 tips specific to their skin type
- Explain what they might be experiencing
- Encourage consistency
- Offer support if they have questions
- Be warm and supportive, not salesy
- Keep it under 250 words""",

        "review_request": f"""Write a warm, non-pushy review request email for 7 days post-delivery.
{customer_context}
The email should:
- Check in on their experience
- Ask how their skin is feeling
- Gently request a review if they're happy
- Provide easy review link placeholder: [REVIEW_LINK]
- Make it personal, not template-y
- No pressure, just genuine curiosity
- Keep it under 150 words""",

        "reengagement": f"""Write a personalized re-engagement email for a customer inactive 30 days.
{customer_context}
The email should:
- Acknowledge it's been a while without being guilt-trippy
- Reference their last skin concern if known
- Share what's new at ReRoots
- Offer a reason to return (new tips, not discounts)
- Warm and welcoming tone
- Keep it under 180 words""",

        "low_stock": f"""Write an urgency email about low stock for a product in customer's wishlist/cart.
{customer_context}
Product context: {context or {}}
The email should:
- Alert them their item is running low
- Create urgency without being pushy
- Reference why they wanted it (skin concern)
- Include clear CTA to complete purchase
- Be helpful not manipulative
- Keep it under 120 words"""
    }
    
    prompt = prompts.get(email_type, prompts["welcome"])
    
    system_prompt = f"""You are the email copywriter for ReRoots Aesthetics Inc., a clinical skincare brand.

{BRAND_VOICE_RULES}

Write emails that feel personal, not templated. Use the customer's name and reference their specific situation.
Format the email with proper greeting and sign-off.
Do not include subject line - just the email body.
Use HTML formatting: <p> for paragraphs, <strong> for emphasis, <br> for line breaks.
"""
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 800,
                    "temperature": 0.7
                }
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"LLM API error: {response.status_code}"
                }
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Apply brand guard
            content = apply_brand_guard(content)
            
            return {
                "success": True,
                "subject": email_config["subject"],
                "body": content,
                "email_type": email_type,
                "customer_email": customer_email,
                "personalization": {
                    "has_profile": profile is not None,
                    "skin_type": profile.get("skin_type") if profile else None,
                    "concerns": profile.get("concerns") if profile else None
                }
            }
            
    except Exception as e:
        logger.error(f"[EMAIL_AI] Failed to generate email: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    email_type: str,
    test_mode: bool = False
) -> Dict[str, Any]:
    """Send email via SendGrid or queue if not configured"""
    
    # Wrap content in email template
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Georgia', serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ text-align: center; padding: 20px 0; border-bottom: 1px solid #C8A96A; }}
            .logo {{ font-size: 24px; color: #C8A96A; letter-spacing: 2px; }}
            .content {{ padding: 30px 0; }}
            .footer {{ text-align: center; padding: 20px 0; border-top: 1px solid #eee; font-size: 12px; color: #999; }}
            a {{ color: #C8A96A; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">REROOTS</div>
            <div style="font-size: 10px; color: #999; letter-spacing: 1px;">MEDICAL AESTHETICS</div>
        </div>
        <div class="content">
            {html_content}
        </div>
        <div class="footer">
            <p>ReRoots Aesthetics Inc. | Toronto, Canada</p>
            <p><a href="https://reroots.ca">reroots.ca</a></p>
            <p style="font-size: 10px;">You're receiving this because you're part of the ReRoots family.</p>
        </div>
    </body>
    </html>
    """
    
    # Log to MongoDB
    email_log = {
        "to_email": to_email,
        "subject": subject,
        "email_type": email_type,
        "test_mode": test_mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "queued",
        "sendgrid_configured": is_sendgrid_configured()
    }
    
    if is_sendgrid_configured() and not test_mode:
        # Send via SendGrid
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "personalizations": [{"to": [{"email": to_email}]}],
                        "from": {"email": SENDGRID_FROM_EMAIL, "name": SENDGRID_FROM_NAME},
                        "subject": subject,
                        "content": [{"type": "text/html", "value": full_html}]
                    }
                )
                
                if response.status_code in [200, 201, 202]:
                    email_log["status"] = "sent"
                    email_log["sent_at"] = datetime.now(timezone.utc).isoformat()
                else:
                    email_log["status"] = "failed"
                    email_log["error"] = f"SendGrid error: {response.status_code}"
                    
        except Exception as e:
            email_log["status"] = "failed"
            email_log["error"] = str(e)
    else:
        # Queue for later (SendGrid not configured)
        email_log["status"] = "queued"
        email_log["html_content"] = full_html
    
    # Save to MongoDB
    if _db is not None:
        try:
            await _db.reroots_emails.insert_one(email_log)
        except Exception as e:
            logger.error(f"[EMAIL_AI] Failed to log email: {e}")
    
    return {
        "success": email_log["status"] in ["sent", "queued"],
        "status": email_log["status"],
        "sendgrid_configured": is_sendgrid_configured(),
        "message": "Email sent successfully" if email_log["status"] == "sent" else "Email queued (SendGrid not configured)"
    }


async def get_email_logs(limit: int = 50, email_type: Optional[str] = None) -> List[Dict]:
    """Get email logs from MongoDB"""
    if _db is None:
        return []
    
    try:
        query = {}
        if email_type:
            query["email_type"] = email_type
        
        logs = await _db.reroots_emails.find(
            query,
            {"_id": 0, "html_content": 0}  # Exclude large content
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return logs
    except Exception as e:
        logger.error(f"[EMAIL_AI] Failed to get logs: {e}")
        return []


async def get_queued_emails() -> List[Dict]:
    """Get all queued emails (for when SendGrid is added)"""
    if _db is None:
        return []
    
    try:
        emails = await _db.reroots_emails.find(
            {"status": "queued"},
            {"_id": 0}
        ).to_list(1000)
        
        return emails
    except Exception as e:
        logger.error(f"[EMAIL_AI] Failed to get queued emails: {e}")
        return []


async def process_queued_emails() -> Dict[str, int]:
    """Process all queued emails (call when SendGrid key is added)"""
    if not is_sendgrid_configured():
        return {"processed": 0, "error": "SendGrid not configured"}
    
    queued = await get_queued_emails()
    sent = 0
    failed = 0
    
    for email in queued:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "personalizations": [{"to": [{"email": email["to_email"]}]}],
                        "from": {"email": SENDGRID_FROM_EMAIL, "name": SENDGRID_FROM_NAME},
                        "subject": email["subject"],
                        "content": [{"type": "text/html", "value": email.get("html_content", "")}]
                    }
                )
                
                if response.status_code in [200, 201, 202]:
                    # Update status in MongoDB
                    await _db.reroots_emails.update_one(
                        {"to_email": email["to_email"], "created_at": email["created_at"]},
                        {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc).isoformat()}}
                    )
                    sent += 1
                else:
                    failed += 1
                    
        except Exception as e:
            logger.error(f"[EMAIL_AI] Failed to send queued email: {e}")
            failed += 1
    
    return {"sent": sent, "failed": failed, "total": len(queued)}


# Email trigger functions (called by cron jobs or event handlers)

async def trigger_welcome_email(customer_email: str) -> Dict:
    """Trigger welcome email for new customer"""
    content = await generate_email_content("welcome", customer_email)
    if not content.get("success"):
        return content
    
    return await send_email(
        to_email=customer_email,
        subject=content["subject"],
        html_content=content["body"],
        email_type="welcome"
    )


async def trigger_post_purchase_email(customer_email: str, order_context: Dict) -> Dict:
    """Trigger post-purchase follow-up email"""
    content = await generate_email_content("post_purchase", customer_email, order_context)
    if not content.get("success"):
        return content
    
    return await send_email(
        to_email=customer_email,
        subject=content["subject"],
        html_content=content["body"],
        email_type="post_purchase"
    )


async def trigger_review_request_email(customer_email: str) -> Dict:
    """Trigger 7-day review request email"""
    content = await generate_email_content("review_request", customer_email)
    if not content.get("success"):
        return content
    
    return await send_email(
        to_email=customer_email,
        subject=content["subject"],
        html_content=content["body"],
        email_type="review_request"
    )


async def trigger_reengagement_email(customer_email: str) -> Dict:
    """Trigger re-engagement email"""
    content = await generate_email_content("reengagement", customer_email)
    if not content.get("success"):
        return content
    
    return await send_email(
        to_email=customer_email,
        subject=content["subject"],
        html_content=content["body"],
        email_type="reengagement"
    )


async def trigger_low_stock_email(customer_email: str, product_context: Dict) -> Dict:
    """Trigger low stock alert email"""
    content = await generate_email_content("low_stock", customer_email, product_context)
    if not content.get("success"):
        return content
    
    return await send_email(
        to_email=customer_email,
        subject=content["subject"],
        html_content=content["body"],
        email_type="low_stock"
    )
