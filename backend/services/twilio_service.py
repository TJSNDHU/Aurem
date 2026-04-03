"""
Twilio All-in-One Communication Service
Handles: WhatsApp, SMS, Voice Calls, Phone Validation, and Automation
Replaces: WHAPI service with full Twilio capabilities
"""

import os
import re
import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Twilio client - lazy loaded
_twilio_client = None


def get_twilio_client():
    """Get or create Twilio client."""
    global _twilio_client
    if _twilio_client is None:
        try:
            from twilio.rest import Client
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            if account_sid and auth_token:
                _twilio_client = Client(account_sid, auth_token)
            else:
                logger.warning("Twilio credentials not configured")
        except ImportError:
            logger.error("Twilio library not installed. Run: pip install twilio")
    return _twilio_client


def get_twilio_phone():
    """Get Twilio phone number for SMS/Voice."""
    return os.environ.get("TWILIO_PHONE_NUMBER")


def get_twilio_whatsapp():
    """Get Twilio WhatsApp number."""
    whatsapp_num = os.environ.get("TWILIO_WHATSAPP_NUMBER")
    if whatsapp_num and not whatsapp_num.startswith("whatsapp:"):
        return f"whatsapp:{whatsapp_num}"
    return whatsapp_num


# Rate limiting
MESSAGE_RATE_LIMIT = {}
MAX_MESSAGES_PER_MINUTE = 10


def normalize_phone_number(phone: str, country_code: str = "1") -> str:
    """
    Normalize phone number to E.164 format with +.
    """
    if not phone:
        return None

    # Remove common formatting characters
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", phone)

    # Remove leading plus if present
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    # Add country code if number is 10 digits (North American)
    if len(cleaned) == 10:
        cleaned = country_code + cleaned

    # Validate it's all digits now
    if not cleaned.isdigit() or len(cleaned) < 10:
        return None

    return f"+{cleaned}"


def mask_phone_number(phone: str) -> str:
    """Mask phone number for safe logging."""
    if not phone or len(phone) < 4:
        return "****"
    return f"{phone[:4]}****{phone[-2:]}"


# ============= PHONE VALIDATION =============


async def validate_phone_number(phone_number: str) -> dict:
    """
    Validate if a phone number is valid using Twilio Lookup API.
    
    Returns:
        dict with 'valid' (bool), 'phone_type', 'carrier', 'country_code'
    """
    client = get_twilio_client()
    if not client:
        logger.warning("Twilio not configured - skipping validation")
        return {"valid": True, "reason": "Validation skipped - Twilio not configured"}

    normalized = normalize_phone_number(phone_number)
    if not normalized:
        return {"valid": False, "reason": "Invalid phone number format"}

    try:
        lookup = client.lookups.v2.phone_numbers(normalized).fetch()
        
        return {
            "valid": lookup.valid,
            "phone_normalized": lookup.phone_number,
            "country_code": lookup.country_code,
            "national_format": lookup.national_format,
            "phone_type": lookup.line_type_intelligence.get("type") if lookup.line_type_intelligence else None,
        }
    except Exception as e:
        logger.error(f"Phone validation failed: {str(e)}")
        return {"valid": False, "reason": str(e)}


async def validate_whatsapp_number(phone_number: str) -> dict:
    """
    Alias for validate_phone_number for backwards compatibility with WHAPI.
    Note: Twilio doesn't have direct WhatsApp validation like WHAPI.
    We validate the phone format and assume WhatsApp availability.
    """
    result = await validate_phone_number(phone_number)
    if result.get("valid"):
        result["whatsapp_verified"] = True
    return result


# ============= WHATSAPP MESSAGING =============


async def send_whatsapp_message(phone: str, message: str) -> dict:
    """
    Send a WhatsApp message via Twilio.
    
    Args:
        phone: Recipient phone number
        message: Message text
        
    Returns:
        dict with 'success', 'message_sid', or 'error'
    """
    client = get_twilio_client()
    if not client:
        return {"success": False, "error": "Twilio not configured"}

    whatsapp_from = get_twilio_whatsapp()
    if not whatsapp_from:
        return {"success": False, "error": "Twilio WhatsApp number not configured"}

    normalized = normalize_phone_number(phone)
    if not normalized:
        return {"success": False, "error": "Invalid phone number format"}

    try:
        msg = client.messages.create(
            body=message,
            from_=whatsapp_from,
            to=f"whatsapp:{normalized}"
        )
        
        logger.info(f"WhatsApp sent to {mask_phone_number(normalized)}: {msg.sid}")
        return {
            "success": True,
            "message_sid": msg.sid,
            "status": msg.status,
            "channel": "whatsapp"
        }
    except Exception as e:
        logger.error(f"WhatsApp send failed to {mask_phone_number(normalized)}: {str(e)}")
        return {"success": False, "error": str(e)}


# ============= SMS MESSAGING =============


async def send_sms(phone: str, message: str) -> dict:
    """
    Send an SMS message via Twilio.
    
    Args:
        phone: Recipient phone number
        message: Message text (max 160 chars for single SMS)
        
    Returns:
        dict with 'success', 'message_sid', or 'error'
    """
    client = get_twilio_client()
    if not client:
        return {"success": False, "error": "Twilio not configured"}

    twilio_phone = get_twilio_phone()
    if not twilio_phone:
        return {"success": False, "error": "Twilio phone number not configured"}

    normalized = normalize_phone_number(phone)
    if not normalized:
        return {"success": False, "error": "Invalid phone number format"}

    try:
        msg = client.messages.create(
            body=message,
            from_=twilio_phone,
            to=normalized
        )
        
        logger.info(f"SMS sent to {mask_phone_number(normalized)}: {msg.sid}")
        return {
            "success": True,
            "message_sid": msg.sid,
            "status": msg.status,
            "channel": "sms"
        }
    except Exception as e:
        logger.error(f"SMS send failed to {mask_phone_number(normalized)}: {str(e)}")
        return {"success": False, "error": str(e)}


# ============= VOICE CALLS =============


async def make_voice_call(
    phone: str, 
    message: str = None, 
    twiml_url: str = None,
    voice: str = "alice"
) -> dict:
    """
    Make an automated voice call via Twilio.
    
    Args:
        phone: Recipient phone number
        message: Text to speak (uses TTS)
        twiml_url: URL to TwiML instructions (alternative to message)
        voice: Voice to use (alice, man, woman, etc.)
        
    Returns:
        dict with 'success', 'call_sid', or 'error'
    """
    client = get_twilio_client()
    if not client:
        return {"success": False, "error": "Twilio not configured"}

    twilio_phone = get_twilio_phone()
    if not twilio_phone:
        return {"success": False, "error": "Twilio phone number not configured"}

    normalized = normalize_phone_number(phone)
    if not normalized:
        return {"success": False, "error": "Invalid phone number format"}

    try:
        call_params = {
            "from_": twilio_phone,
            "to": normalized,
        }
        
        if twiml_url:
            call_params["url"] = twiml_url
        elif message:
            # Create TwiML for simple text-to-speech
            twiml = f'<Response><Say voice="{voice}">{message}</Say></Response>'
            call_params["twiml"] = twiml
        else:
            return {"success": False, "error": "No message or TwiML URL provided"}

        call = client.calls.create(**call_params)
        
        logger.info(f"Voice call initiated to {mask_phone_number(normalized)}: {call.sid}")
        return {
            "success": True,
            "call_sid": call.sid,
            "status": call.status,
            "channel": "voice"
        }
    except Exception as e:
        logger.error(f"Voice call failed to {mask_phone_number(normalized)}: {str(e)}")
        return {"success": False, "error": str(e)}


# ============= MULTI-CHANNEL SEND =============


async def send_notification(
    phone: str,
    message: str,
    channels: List[str] = ["whatsapp", "sms"],
    voice_message: str = None
) -> dict:
    """
    Send notification across multiple channels with fallback.
    
    Args:
        phone: Recipient phone number
        message: Message text
        channels: List of channels to try in order ["whatsapp", "sms", "voice"]
        voice_message: Optional different message for voice calls
        
    Returns:
        dict with results for each channel attempted
    """
    results = {"phone": mask_phone_number(phone), "channels": {}}
    
    for channel in channels:
        if channel == "whatsapp":
            result = await send_whatsapp_message(phone, message)
        elif channel == "sms":
            # Truncate SMS to 1600 chars (max for long SMS)
            sms_message = message[:1600] if len(message) > 1600 else message
            result = await send_sms(phone, sms_message)
        elif channel == "voice":
            vm = voice_message or message[:500]  # TTS has limits
            result = await make_voice_call(phone, message=vm)
        else:
            result = {"success": False, "error": f"Unknown channel: {channel}"}
        
        results["channels"][channel] = result
        
        # If successful, we're done (unless we want all channels)
        if result.get("success"):
            results["delivered_via"] = channel
            break
    
    results["success"] = any(r.get("success") for r in results["channels"].values())
    return results


# ============= MESSAGE TEMPLATES =============


def get_milestone_templates():
    """WhatsApp/SMS message templates for the milestone system."""
    return {
        "new_referral": """🎉 New Referral Counted!

Someone you referred just completed their Bio-Age Scan!

📊 Your Progress: {count}/{threshold}
{progress_bar}

{remaining_text}

Keep sharing: {referral_link}

- ReRoots Lab 🧬""",

        "almost_there_8": """⚡ You're SO Close!

Hi {name}! You're just {remaining} referral(s) away from unlocking your 30% LIFETIME DISCOUNT!

📊 Progress: {count}/{threshold}
{progress_bar}

🎯 What happens when you hit 10:
• Permanent 30% off ALL orders
• Exclusive discount code to share
• VIP Founding Member status

Share now: {referral_link}

Don't let this slip away! 💪
- ReRoots Lab""",

        "milestone_unlocked": """🏆 CONGRATULATIONS!

{name}, you've done it!

You've unlocked your 30% LIFETIME DISCOUNT! 🎉

🔓 Your exclusive code:
{unlock_code}

This discount is now permanently on your account. Every order. Forever.

Shop now: https://reroots.ca/shop

Welcome to the inner circle! 💎
- ReRoots Lab""",

        "launch_invite": """🧬 ReRoots Founding Member Invitation

Hi {name}!

You're one of our first Bio-Age Scan participants. We're inviting you to join our exclusive Milestone Program.

🎯 Here's the game:
• Refer 10 friends to take the Bio-Age Scan
• Unlock a permanent 30% discount on all orders
• Get the $100 PDRN protocol for just $70

📊 Your starting position: 0/10

Start now: {referral_link}

This is your chance to lock in founder pricing forever.

- ReRoots Lab 🧬""",

        "blog_followup": """📚 Thanks for reading!

Hi {name}, I noticed you were exploring our article on {topic}.

Did you know you can get a personalized skin analysis in 2 minutes?

Take your free Bio-Age Scan: {scan_link}

Have questions? Just reply here - I'm real! 🙂

- ReRoots Lab""",

        "order_confirmation": """✅ Order Confirmed!

Hi {name},

Thank you for your order! 🎉

🧾 Order #: {order_number}
💰 Total: ${total}

We're preparing your skincare essentials now. You'll receive tracking info once shipped.

Questions? Reply here anytime.

- ReRoots Team 🧬""",

        "abandoned_cart": """👋 You left something behind!

Hi {name},

We noticed you didn't complete your order. Your skincare routine is waiting!

🛒 Items in your cart:
{cart_items}

Complete your order: {checkout_link}

Need help? Just reply here.

- ReRoots Team""",

        "review_request": """⭐ How was your experience?

Hi {name}!

Your order #{order_number} was delivered {days_ago} days ago. We'd love to hear your thoughts!

Leave a quick review: {review_link}

Your feedback helps us improve and helps others discover ReRoots.

Thank you! 🙏
- ReRoots Team""",

        "restock_alert": """🔔 Back in Stock!

Hi {name}!

Great news - {product_name} is back in stock!

You asked us to notify you, so here it is.

Shop now: {product_link}

Don't wait - it sold out fast last time!

- ReRoots Team""",

        "birthday": """🎂 Happy Birthday, {name}!

From all of us at ReRoots - have an amazing day!

Here's a special gift: 25% OFF your next order.

🎁 Use code: BDAY{year}
Valid for 7 days.

Shop: https://reroots.ca/shop

Cheers! 🎉
- ReRoots Team""",
    }


def get_sms_templates():
    """Short SMS templates (160 char limit for single SMS)."""
    return {
        "new_referral": "🎉 New referral counted! Progress: {count}/{threshold}. Keep sharing: {referral_link} -ReRoots",
        "milestone_unlocked": "🏆 You did it! Your 30% lifetime code: {unlock_code}. Shop: reroots.ca/shop -ReRoots",
        "shipping": "📦 Order #{order_number} shipped! Track: {tracking_url} -ReRoots",
        "otp": "Your ReRoots verification code is: {code}. Valid for 10 minutes.",
        "abandoned_cart": "👋 Your cart is waiting! Complete your order: {checkout_link} -ReRoots",
    }


def get_voice_templates():
    """Voice call scripts (TTS)."""
    return {
        "abandoned_cart": """
            Hello {name}! This is ReRoots calling. 
            We noticed you left some items in your cart. 
            Your skincare routine is waiting for you! 
            Visit reroots.ca to complete your order. 
            Thank you, and have a great day!
        """,
        "order_shipped": """
            Hello {name}! Great news from ReRoots. 
            Your order number {order_number} has shipped and is on its way to you.
            Check your email or text messages for tracking details.
            Thank you for choosing ReRoots!
        """,
        "appointment_reminder": """
            Hello {name}! This is a reminder from ReRoots 
            about your consultation scheduled for {date} at {time}.
            If you need to reschedule, please visit our website or reply to our text message.
            We look forward to seeing you!
        """,
    }


# ============= MILESTONE NOTIFICATIONS =============


async def send_milestone_new_referral(
    phone: str, 
    name: str, 
    count: int, 
    threshold: int, 
    referral_code: str,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send notification when a new referral is verified."""
    templates = get_milestone_templates()
    sms_templates = get_sms_templates()

    remaining = threshold - count
    progress_bar = "🟢" * count + "⚪" * remaining

    if remaining > 0:
        remaining_text = f"🎯 Only {remaining} more to unlock 30% OFF forever!"
    else:
        remaining_text = "🎉 You've reached the threshold! Check your email for your code."

    referral_link = f"https://reroots.ca/Bio-Age-Repair-Scan?ref={referral_code}"

    # Full message for WhatsApp
    whatsapp_message = templates["new_referral"].format(
        count=count,
        threshold=threshold,
        progress_bar=progress_bar,
        remaining_text=remaining_text,
        referral_link=referral_link,
    )

    # Short message for SMS
    sms_message = sms_templates["new_referral"].format(
        count=count,
        threshold=threshold,
        referral_link=referral_link[:50],  # Shortened
    )

    if "whatsapp" in channels and "sms" in channels:
        # Try WhatsApp first, fallback to SMS
        result = await send_whatsapp_message(phone, whatsapp_message)
        if not result.get("success"):
            result = await send_sms(phone, sms_message)
        return result
    elif "whatsapp" in channels:
        return await send_whatsapp_message(phone, whatsapp_message)
    else:
        return await send_sms(phone, sms_message)


# Backwards compatibility alias
async def send_milestone_new_referral_whatsapp(
    phone: str, name: str, count: int, threshold: int, referral_code: str
) -> dict:
    """Backwards compatible wrapper for WHAPI migration."""
    return await send_milestone_new_referral(phone, name, count, threshold, referral_code, ["whatsapp"])


async def send_milestone_almost_there(
    phone: str, 
    name: str, 
    count: int, 
    threshold: int, 
    referral_code: str,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send the '8/10 Almost There' notification - high urgency!"""
    templates = get_milestone_templates()

    remaining = threshold - count
    progress_bar = "🟢" * count + "⚪" * remaining
    referral_link = f"https://reroots.ca/Bio-Age-Repair-Scan?ref={referral_code}"

    message = templates["almost_there_8"].format(
        name=name.split()[0] if name else "there",
        count=count,
        threshold=threshold,
        remaining=remaining,
        progress_bar=progress_bar,
        referral_link=referral_link,
    )

    return await send_notification(phone, message, channels)


# Backwards compatibility alias
async def send_milestone_almost_there_whatsapp(
    phone: str, name: str, count: int, threshold: int, referral_code: str
) -> dict:
    """Backwards compatible wrapper for WHAPI migration."""
    return await send_milestone_almost_there(phone, name, count, threshold, referral_code, ["whatsapp"])


async def send_milestone_unlocked(
    phone: str, 
    name: str, 
    unlock_code: str,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send the 'You Unlocked 30%!' celebration message."""
    templates = get_milestone_templates()
    sms_templates = get_sms_templates()

    whatsapp_message = templates["milestone_unlocked"].format(
        name=name.split()[0] if name else "Champion", 
        unlock_code=unlock_code
    )
    
    sms_message = sms_templates["milestone_unlocked"].format(unlock_code=unlock_code)

    if "whatsapp" in channels:
        result = await send_whatsapp_message(phone, whatsapp_message)
        if result.get("success"):
            return result
    
    if "sms" in channels:
        return await send_sms(phone, sms_message)
    
    return {"success": False, "error": "No valid channel"}


# Backwards compatibility alias
async def send_milestone_unlocked_whatsapp(phone: str, name: str, unlock_code: str) -> dict:
    """Backwards compatible wrapper for WHAPI migration."""
    return await send_milestone_unlocked(phone, name, unlock_code, ["whatsapp"])


async def send_launch_invite(
    phone: str, 
    name: str, 
    referral_code: str,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send initial invitation to existing leads to start the 10-referral journey."""
    templates = get_milestone_templates()

    message = templates["launch_invite"].format(
        name=name.split()[0] if name else "there",
        referral_link=f"https://reroots.ca/Bio-Age-Repair-Scan?ref={referral_code}",
    )

    return await send_notification(phone, message, channels)


# Backwards compatibility alias
async def send_launch_invite_whatsapp(phone: str, name: str, referral_code: str) -> dict:
    """Backwards compatible wrapper for WHAPI migration."""
    return await send_launch_invite(phone, name, referral_code, ["whatsapp"])


async def send_blog_followup(
    phone: str, 
    name: str, 
    topic: str, 
    referral_code: str = None,
    channels: List[str] = ["whatsapp"]
) -> dict:
    """Send follow-up message when user reads a blog post."""
    templates = get_milestone_templates()

    scan_link = "https://reroots.ca/Bio-Age-Repair-Scan"
    if referral_code:
        scan_link += f"?ref={referral_code}"

    message = templates["blog_followup"].format(
        name=name.split()[0] if name else "there", 
        topic=topic, 
        scan_link=scan_link
    )

    return await send_notification(phone, message, channels)


# Backwards compatibility alias
async def send_blog_followup_whatsapp(
    phone: str, name: str, topic: str, referral_code: str = None
) -> dict:
    """Backwards compatible wrapper for WHAPI migration."""
    return await send_blog_followup(phone, name, topic, referral_code, ["whatsapp"])


# ============= ORDER NOTIFICATIONS =============


async def send_order_confirmation(
    phone: str,
    name: str,
    order_number: str,
    total: float,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send order confirmation notification."""
    templates = get_milestone_templates()
    
    message = templates["order_confirmation"].format(
        name=name.split()[0] if name else "there",
        order_number=order_number,
        total=f"{total:.2f}"
    )
    
    return await send_notification(phone, message, channels)


async def send_shipping_notification(
    phone: str, 
    name: str, 
    order_number: str, 
    tracking_number: str, 
    courier: str,
    tracking_url: str = None,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send shipping notification when an order is shipped."""
    first_name = name.split()[0] if name else "there"
    
    if not tracking_url:
        tracking_url = f"https://www.google.com/search?q={tracking_number}+tracking"

    whatsapp_message = f"""📦 Your Order Has Shipped!

Hi {first_name},

Great news! Your ReRoots order is on its way! 🚚

🧾 Order: #{order_number}
📍 Carrier: {courier}
🔢 Tracking #: {tracking_number}

Track your package here:
{tracking_url}

Your skincare essentials will arrive soon! ✨

Questions? Just reply here.

- ReRoots Team 🧬"""

    sms_message = f"📦 Order #{order_number} shipped via {courier}! Track: {tracking_url[:50]} -ReRoots"

    if "whatsapp" in channels:
        result = await send_whatsapp_message(phone, whatsapp_message)
        if result.get("success"):
            return result
    
    if "sms" in channels:
        return await send_sms(phone, sms_message)
    
    return {"success": False, "error": "No valid channel"}


# Backwards compatibility alias
async def send_shipping_whatsapp(
    phone: str, name: str, order_number: str, tracking_number: str, 
    courier: str, tracking_url: str = None
) -> dict:
    """Backwards compatible wrapper for WHAPI migration."""
    return await send_shipping_notification(
        phone, name, order_number, tracking_number, courier, tracking_url, ["whatsapp"]
    )


# ============= PARTNER NOTIFICATIONS =============


async def send_partner_approved(
    phone: str, 
    name: str, 
    partner_code: str, 
    referral_link: str,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send notification when a partner application is APPROVED."""
    first_name = name.split()[0] if name else "there"

    message = f"""🎉 Welcome to the ReRoots Partner Circle!

Hi {first_name},

Your application has been APPROVED! You're now an official ReRoots Science Ambassador.

🔑 Your Partner Code:
{partner_code}

📊 Your Referral Link:
{referral_link}

🧬 What's Next:
1. Access your Partner Dashboard: https://reroots.ca/partner-dashboard
2. Download brand assets from your Resources tab
3. Share your link & start earning 10-15% commission

Your followers get up to 50% OFF with your code!

Questions? Just reply here - we're real humans 🙂

Welcome to the lab! 🧬
- ReRoots Partnership Team"""

    return await send_notification(phone, message, channels)


# Backwards compatibility alias
async def send_partner_approved_whatsapp(
    phone: str, name: str, partner_code: str, referral_link: str
) -> dict:
    """Backwards compatible wrapper for WHAPI migration."""
    return await send_partner_approved(phone, name, partner_code, referral_link, ["whatsapp"])


async def send_partner_denied(
    phone: str, 
    name: str,
    channels: List[str] = ["whatsapp"]
) -> dict:
    """Send notification when a partner application is DENIED."""
    first_name = name.split()[0] if name else "there"

    message = f"""Hi {first_name},

Thank you for your interest in partnering with ReRoots 🧬

After reviewing your application, we've decided not to move forward with a partnership at this time. Our program has specific requirements around audience alignment and content focus that we're prioritizing.

This isn't a reflection of your work - it's simply about finding the right fit for our biotech skincare community.

Here's how you can still benefit:
• Take our free Bio-Age Scan and join the Founding Member program
• Refer 10 friends to unlock a permanent 30% discount
• Shop with code WELCOME15 for 15% off your first order

Start here: https://reroots.ca/Bio-Age-Repair-Scan

We appreciate your interest and wish you success!

- ReRoots Team"""

    return await send_notification(phone, message, channels)


# Backwards compatibility alias
async def send_partner_denied_whatsapp(phone: str, name: str) -> dict:
    """Backwards compatible wrapper for WHAPI migration."""
    return await send_partner_denied(phone, name, ["whatsapp"])


# ============= CART & CONVERSION AUTOMATION =============


async def send_abandoned_cart_notification(
    phone: str,
    name: str,
    cart_items: str,
    checkout_link: str,
    channels: List[str] = ["whatsapp", "sms"],
    include_call: bool = False
) -> dict:
    """Send abandoned cart reminder via multiple channels."""
    templates = get_milestone_templates()
    sms_templates = get_sms_templates()
    voice_templates = get_voice_templates()
    
    whatsapp_message = templates["abandoned_cart"].format(
        name=name.split()[0] if name else "there",
        cart_items=cart_items,
        checkout_link=checkout_link
    )
    
    sms_message = sms_templates["abandoned_cart"].format(checkout_link=checkout_link[:50])
    
    results = {"channels": {}}
    
    # Try WhatsApp first
    if "whatsapp" in channels:
        results["channels"]["whatsapp"] = await send_whatsapp_message(phone, whatsapp_message)
    
    # Then SMS
    if "sms" in channels:
        results["channels"]["sms"] = await send_sms(phone, sms_message)
    
    # Optionally voice call for high-value carts
    if include_call and "voice" in channels:
        voice_message = voice_templates["abandoned_cart"].format(
            name=name.split()[0] if name else "there"
        )
        results["channels"]["voice"] = await make_voice_call(phone, message=voice_message)
    
    results["success"] = any(r.get("success") for r in results["channels"].values())
    return results


async def send_review_request(
    phone: str,
    name: str,
    order_number: str,
    days_ago: int,
    review_link: str,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send review request after delivery."""
    templates = get_milestone_templates()
    
    message = templates["review_request"].format(
        name=name.split()[0] if name else "there",
        order_number=order_number,
        days_ago=days_ago,
        review_link=review_link
    )
    
    return await send_notification(phone, message, channels)


async def send_restock_alert(
    phone: str,
    name: str,
    product_name: str,
    product_link: str,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send restock notification for waitlisted products."""
    templates = get_milestone_templates()
    
    message = templates["restock_alert"].format(
        name=name.split()[0] if name else "there",
        product_name=product_name,
        product_link=product_link
    )
    
    return await send_notification(phone, message, channels)


async def send_birthday_message(
    phone: str,
    name: str,
    year: str = None,
    channels: List[str] = ["whatsapp", "sms"]
) -> dict:
    """Send birthday greeting with discount code."""
    templates = get_milestone_templates()
    
    if not year:
        year = datetime.now().strftime("%y")
    
    message = templates["birthday"].format(
        name=name.split()[0] if name else "there",
        year=year
    )
    
    return await send_notification(phone, message, channels)


# ============= OTP & VERIFICATION =============


async def send_otp(phone: str, code: str, channel: str = "sms") -> dict:
    """Send OTP verification code."""
    sms_templates = get_sms_templates()
    message = sms_templates["otp"].format(code=code)
    
    if channel == "sms":
        return await send_sms(phone, message)
    elif channel == "whatsapp":
        return await send_whatsapp_message(phone, message)
    elif channel == "voice":
        voice_message = f"Your ReRoots verification code is: {' '.join(code)}. I repeat: {' '.join(code)}."
        return await make_voice_call(phone, message=voice_message)
    
    return {"success": False, "error": f"Unknown channel: {channel}"}


# ============= BATCH OPERATIONS =============


async def batch_send_launch_invites(leads: List[dict]) -> dict:
    """Send launch invites to a batch of existing leads."""
    results = {"total": len(leads), "sent": 0, "failed": 0, "errors": []}

    for lead in leads:
        phone = lead.get("phone") or lead.get("whatsapp")
        if not phone:
            results["failed"] += 1
            results["errors"].append({
                "lead": lead.get("email", "unknown"), 
                "error": "No phone number"
            })
            continue

        result = await send_launch_invite(
            phone=phone,
            name=lead.get("name", ""),
            referral_code=lead.get("referral_code", ""),
        )

        if result.get("success"):
            results["sent"] += 1
        else:
            results["failed"] += 1
            results["errors"].append({
                "lead": lead.get("email", "unknown"),
                "error": result.get("error", "Unknown"),
            })

    return results


# ============= FRAUD PROTECTION =============


async def verify_referral_phone(phone: str, referrer_code: str, db) -> dict:
    """
    Use phone verification as the PRIMARY anti-fraud gate.
    A referral only counts if it's a unique, valid phone number.
    """
    validation = await validate_phone_number(phone)

    if not validation.get("valid"):
        return {
            "valid": False,
            "reason": validation.get("reason", "Invalid phone number"),
            "fraud_type": "invalid_phone",
        }

    normalized = validation.get("phone_normalized", normalize_phone_number(phone))

    # Create phone hash for duplicate detection
    phone_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]

    # Check if this phone was already used by this referrer
    existing = await db.verified_referrals.find_one({
        "referrer_code": referrer_code, 
        "phone_hash": phone_hash
    })

    if existing:
        return {
            "valid": False,
            "reason": "This phone number was already used for a referral",
            "fraud_type": "duplicate_phone",
        }

    # Check if this phone was used too many times across all referrers
    phone_usage_count = await db.verified_referrals.count_documents({"phone_hash": phone_hash})

    if phone_usage_count >= 3:
        return {
            "valid": False,
            "reason": "This phone number has reached the referral limit",
            "fraud_type": "phone_abuse",
        }

    return {
        "valid": True,
        "phone_normalized": normalized,
        "phone_hash": phone_hash,
        "phone_verified": True,
    }


# ============= MARKETING LAB INTEGRATION =============


async def get_whatsapp_broadcast_list(db, filters: dict = None) -> List[dict]:
    """
    Get list of phone-verified contacts for Marketing Lab broadcasts.
    Same functionality as WHAPI version for backwards compatibility.
    """
    contacts = []
    seen_phones = set()
    
    source_filter = filters.get("source") if filters else None
    
    # 1. Bio-Age Scans
    if not source_filter or source_filter == "bio_scans":
        query = {"whatsapp": {"$exists": True, "$ne": None, "$ne": ""}}
        if filters:
            if filters.get("intent") == "high":
                query["tags"] = {"$in": ["intent:high"]}
        
        async for scan in db.bio_scans.find(query):
            phone = scan.get("whatsapp") or scan.get("phone")
            if phone and phone not in seen_phones:
                seen_phones.add(phone)
                contacts.append({
                    "phone": phone,
                    "name": scan.get("name", ""),
                    "email": scan.get("email", ""),
                    "source": "bio_scan",
                    "source_label": "Bio-Age Scan",
                    "referral_code": scan.get("referral_code", ""),
                })
    
    # 2. Founding Members
    if not source_filter or source_filter == "founding_members":
        async for member in db.founding_members.find({"whatsapp": {"$exists": True, "$ne": ""}}):
            phone = member.get("whatsapp") or member.get("phone")
            if phone and phone not in seen_phones:
                seen_phones.add(phone)
                contacts.append({
                    "phone": phone,
                    "name": member.get("name", ""),
                    "email": member.get("email", ""),
                    "source": "founding_member",
                    "source_label": "Founding Member",
                    "referral_code": member.get("referral_code", ""),
                })
    
    # 3. Orders/Customers
    if not source_filter or source_filter == "customers":
        async for order in db.orders.find({"phone": {"$exists": True, "$ne": ""}}):
            phone = order.get("phone")
            if phone and phone not in seen_phones:
                seen_phones.add(phone)
                contacts.append({
                    "phone": phone,
                    "name": order.get("shipping_address", {}).get("name", ""),
                    "email": order.get("email", ""),
                    "source": "customer",
                    "source_label": "Customer",
                    "referral_code": "",
                })
    
    return contacts


async def analyze_scan_concerns(db) -> dict:
    """Analyze bio-scan data to find top concerns for AI content generation."""
    pipeline = [
        {"$match": {"concern": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$concern", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]

    concerns = await db.bio_scans.aggregate(pipeline).to_list(10)
    total_scans = await db.bio_scans.count_documents({})

    concern_breakdown = []
    for c in concerns:
        percentage = round((c["count"] / total_scans) * 100, 1) if total_scans > 0 else 0
        concern_breakdown.append({
            "concern": c["_id"], 
            "count": c["count"], 
            "percentage": percentage
        })

    content_suggestions = []
    if concern_breakdown:
        top_concern = concern_breakdown[0]
        if top_concern["percentage"] > 50:
            content_suggestions.append({
                "type": "whatsapp_script",
                "topic": top_concern["concern"],
                "hook": f"{int(top_concern['percentage'])}% of our scans show '{top_concern['concern']}' as the #1 concern.",
                "angle": f"Focus on how PDRN addresses {top_concern['concern']}",
            })

    return {
        "total_scans": total_scans,
        "concern_breakdown": concern_breakdown,
        "content_suggestions": content_suggestions,
        "top_concern": concern_breakdown[0] if concern_breakdown else None,
    }


async def generate_social_proof_post(referrer_name: str, milestone: int) -> str:
    """Generate a 'Social Proof' post when someone hits the 10-referral milestone."""
    first_name = referrer_name.split()[0] if referrer_name else "Another member"

    return f"""🎉 {first_name} just unlocked *Lifetime 30% OFF*!

They referred {milestone} friends who took the Bio-Age Scan and earned their permanent discount.

Ready to join them?

1️⃣ Take the Bio-Age Scan (free)
2️⃣ Get your referral link
3️⃣ Share with 10 friends
4️⃣ Unlock 30% off forever

Start: reroots.ca/Bio-Age-Repair-Scan

#ReRoots #FoundingMember #BiohackingSkincare #PDRN"""
