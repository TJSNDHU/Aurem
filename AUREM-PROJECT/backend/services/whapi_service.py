"""
Whapi.cloud WhatsApp Integration Service
Handles: Phone validation, message sending, milestone notifications, and fraud prevention
"""

import os
import re
import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


# Whapi.cloud Configuration - loaded dynamically
def get_whapi_token():
    return os.environ.get("WHAPI_API_TOKEN")


def get_whapi_url():
    return os.environ.get("WHAPI_API_URL", "https://gate.whapi.cloud")


# Rate limiting
MESSAGE_RATE_LIMIT = {}  # phone -> [timestamps]
MAX_MESSAGES_PER_MINUTE = 10


def normalize_phone_number(phone: str, country_code: str = None) -> str:
    """
    Normalize phone number to international format without +.
    Removes common formatting characters and validates basic structure.
    """
    if not phone:
        return None

    # Remove common formatting characters
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", phone)

    # Remove leading plus if present
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    # Add country code if provided and number doesn't have one
    if country_code and len(cleaned) <= 10:
        country_code = country_code.lstrip("+")
        cleaned = country_code + cleaned

    # Validate it's all digits now
    if not cleaned.isdigit() or len(cleaned) < 10:
        return None

    return cleaned


def mask_phone_number(phone: str) -> str:
    """Mask phone number for safe logging."""
    if not phone or len(phone) < 4:
        return "****"
    return f"{phone[:3]}****{phone[-2:]}"


def get_headers() -> dict:
    """Get API headers for Whapi requests."""
    token = get_whapi_token()
    if not token:
        raise ValueError("WHAPI_API_TOKEN not configured")
    return {
        "accept": "application/json",
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
    }


async def validate_whatsapp_number(phone_number: str) -> dict:
    """
    Validate if a phone number is registered on WhatsApp using Whapi.cloud.
    This is the PRIMARY fraud gate - a referral only counts if it's a valid WhatsApp number.

    Uses the GET /contacts/{ContactID} endpoint to check if a number exists.

    Returns:
        dict with 'valid' (bool), 'whatsapp_id' (str if valid), 'reason' (str if invalid)
    """
    token = get_whapi_token()
    if not token:
        logger.warning("Whapi API token not configured - skipping validation")
        return {"valid": True, "reason": "Validation skipped - API not configured"}

    normalized = normalize_phone_number(phone_number)
    if not normalized:
        return {"valid": False, "reason": "Invalid phone number format"}

    try:
        # Whapi uses GET /contacts/{ContactID} to check if a number exists
        url = f"{get_whapi_url()}/contacts/{normalized}"
        headers = {"accept": "application/json", "authorization": f"Bearer {token}"}

        response = requests.get(url, headers=headers, timeout=30)

        # 404 means contact not found = not on WhatsApp (or not in contacts yet)
        # 200 means contact exists
        if response.status_code == 200:
            result = response.json()
            logger.info(f"WhatsApp contact found for {mask_phone_number(normalized)}")
            return {
                "valid": True,
                "whatsapp_id": result.get("id", normalized),
                "phone_normalized": normalized,
                "contact_name": result.get("pushname") or result.get("name"),
            }
        elif response.status_code == 404:
            # Contact not in list, but that doesn't mean they don't have WhatsApp
            # For now, we'll consider it valid but unverified (can still send messages)
            logger.info(
                f"WhatsApp contact not in list for {mask_phone_number(normalized)}, allowing anyway"
            )
            return {
                "valid": True,
                "whatsapp_id": normalized,
                "phone_normalized": normalized,
                "note": "Contact not in saved list but may still have WhatsApp",
            }
        else:
            response.raise_for_status()
            return {
                "valid": False,
                "reason": f"Unexpected status: {response.status_code}",
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Whapi validation error: {str(e)}")
        # Fail open for network errors (don't block user flow)
        return {
            "valid": True,
            "reason": f"Validation skipped - network error: {str(e)}",
        }


async def send_whatsapp_message(phone_number: str, message: str) -> dict:
    """
    Send a WhatsApp text message via Whapi.cloud.

    Returns:
        dict with 'success' (bool), 'message_id' (str if success), 'error' (str if failed)
    """
    token = get_whapi_token()
    if not token:
        logger.warning("Whapi API token not configured - message not sent")
        return {"success": False, "error": "API not configured"}

    normalized = normalize_phone_number(phone_number)
    if not normalized:
        return {"success": False, "error": "Invalid phone number format"}

    # Rate limiting check
    now = datetime.now(timezone.utc).timestamp()
    if normalized in MESSAGE_RATE_LIMIT:
        # Clean old timestamps (older than 1 minute)
        MESSAGE_RATE_LIMIT[normalized] = [
            ts for ts in MESSAGE_RATE_LIMIT[normalized] if now - ts < 60
        ]
        if len(MESSAGE_RATE_LIMIT[normalized]) >= MAX_MESSAGES_PER_MINUTE:
            logger.warning(f"Rate limit exceeded for {mask_phone_number(normalized)}")
            return {"success": False, "error": "Rate limit exceeded"}
    else:
        MESSAGE_RATE_LIMIT[normalized] = []

    try:
        url = f"{get_whapi_url()}/messages/text"
        headers = get_headers()

        payload = {"to": normalized, "body": message}

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()

        result = response.json()
        message_id = result.get("result", {}).get("id", "unknown")

        # Track for rate limiting
        MESSAGE_RATE_LIMIT[normalized].append(now)

        logger.info(f"WhatsApp sent to {mask_phone_number(normalized)}: {message_id}")
        return {"success": True, "message_id": message_id, "phone": normalized}

    except requests.exceptions.RequestException as e:
        logger.error(f"Whapi send error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============= MILESTONE NOTIFICATION TEMPLATES =============


def get_milestone_templates():
    """WhatsApp message templates for the milestone system."""
    return {
        "new_referral": """🎉 *New Referral Counted!*

Someone you referred just completed their Bio-Age Scan!

📊 Your Progress: {count}/{threshold}
{progress_bar}

{remaining_text}

Keep sharing: {referral_link}

- ReRoots Lab 🧬""",
        "almost_there_8": """⚡ *You're SO Close!*

Hi {name}! You're just {remaining} referral(s) away from unlocking your *30% LIFETIME DISCOUNT*!

📊 Progress: {count}/{threshold}
{progress_bar}

🎯 What happens when you hit 10:
• Permanent 30% off ALL orders
• Exclusive discount code to share
• VIP Founding Member status

Share now: {referral_link}

Don't let this slip away! 💪
- ReRoots Lab""",
        "milestone_unlocked": """🏆 *CONGRATULATIONS!*

{name}, you've done it!

You've unlocked your *30% LIFETIME DISCOUNT*! 🎉

🔓 Your exclusive code:
*{unlock_code}*

This discount is now permanently on your account. Every order. Forever.

Shop now: https://reroots.ca/shop

Welcome to the inner circle! 💎
- ReRoots Lab""",
        "launch_invite": """🧬 *ReRoots Founding Member Invitation*

Hi {name}!

You're one of our first Bio-Age Scan participants. We're inviting you to join our exclusive *Milestone Program*.

🎯 Here's the game:
• Refer 10 friends to take the Bio-Age Scan
• Unlock a *permanent 30% discount* on all orders
• Get the $100 PDRN protocol for just $70

📊 Your starting position: 0/10

Start now: {referral_link}

This is your chance to lock in founder pricing forever.

- ReRoots Lab 🧬""",
        "blog_followup": """📚 *Thanks for reading!*

Hi {name}, I noticed you were exploring our article on {topic}.

Did you know you can get a *personalized skin analysis* in 2 minutes?

Take your free Bio-Age Scan: {scan_link}

Have questions? Just reply here - I'm real! 🙂

- ReRoots Lab""",
    }


async def send_milestone_new_referral_whatsapp(
    phone: str, name: str, count: int, threshold: int, referral_code: str
) -> dict:
    """Send WhatsApp notification when a new referral is verified."""
    templates = get_milestone_templates()

    remaining = threshold - count
    progress_bar = "🟢" * count + "⚪" * remaining

    if remaining > 0:
        remaining_text = f"🎯 Only *{remaining}* more to unlock 30% OFF forever!"
    else:
        remaining_text = (
            "🎉 You've reached the threshold! Check your email for your code."
        )

    message = templates["new_referral"].format(
        count=count,
        threshold=threshold,
        progress_bar=progress_bar,
        remaining_text=remaining_text,
        referral_link=f"https://reroots.ca/Bio-Age-Repair-Scan?ref={referral_code}",
    )

    return await send_whatsapp_message(phone, message)


async def send_milestone_almost_there_whatsapp(
    phone: str, name: str, count: int, threshold: int, referral_code: str
) -> dict:
    """Send the '8/10 Almost There' WhatsApp - high urgency!"""
    templates = get_milestone_templates()

    remaining = threshold - count
    progress_bar = "🟢" * count + "⚪" * remaining

    message = templates["almost_there_8"].format(
        name=name.split()[0] if name else "there",
        count=count,
        threshold=threshold,
        remaining=remaining,
        progress_bar=progress_bar,
        referral_link=f"https://reroots.ca/Bio-Age-Repair-Scan?ref={referral_code}",
    )

    return await send_whatsapp_message(phone, message)


async def send_milestone_unlocked_whatsapp(
    phone: str, name: str, unlock_code: str
) -> dict:
    """Send the 'You Unlocked 30%!' celebration message."""
    templates = get_milestone_templates()

    message = templates["milestone_unlocked"].format(
        name=name.split()[0] if name else "Champion", unlock_code=unlock_code
    )

    return await send_whatsapp_message(phone, message)


async def send_launch_invite_whatsapp(
    phone: str, name: str, referral_code: str
) -> dict:
    """Send initial invitation to existing leads to start the 10-referral journey."""
    templates = get_milestone_templates()

    message = templates["launch_invite"].format(
        name=name.split()[0] if name else "there",
        referral_link=f"https://reroots.ca/Bio-Age-Repair-Scan?ref={referral_code}",
    )

    return await send_whatsapp_message(phone, message)


async def send_blog_followup_whatsapp(
    phone: str, name: str, topic: str, referral_code: str = None
) -> dict:
    """Send follow-up message when user reads a blog post (if logged in)."""
    templates = get_milestone_templates()

    scan_link = f"https://reroots.ca/Bio-Age-Repair-Scan"
    if referral_code:
        scan_link += f"?ref={referral_code}"

    message = templates["blog_followup"].format(
        name=name.split()[0] if name else "there", topic=topic, scan_link=scan_link
    )

    return await send_whatsapp_message(phone, message)


async def batch_send_launch_invites(leads: List[dict]) -> dict:
    """
    Send launch invites to a batch of existing leads.

    Args:
        leads: List of dicts with 'phone', 'name', 'referral_code'

    Returns:
        Summary dict with success/failure counts
    """
    results = {"total": len(leads), "sent": 0, "failed": 0, "errors": []}

    for lead in leads:
        phone = lead.get("phone") or lead.get("whatsapp")
        if not phone:
            results["failed"] += 1
            results["errors"].append(
                {"lead": lead.get("email", "unknown"), "error": "No phone number"}
            )
            continue

        result = await send_launch_invite_whatsapp(
            phone=phone,
            name=lead.get("name", ""),
            referral_code=lead.get("referral_code", ""),
        )

        if result.get("success"):
            results["sent"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(
                {
                    "lead": lead.get("email", "unknown"),
                    "error": result.get("error", "Unknown"),
                }
            )

    return results


# ============= FRAUD PROTECTION VIA WHAPI =============


async def verify_referral_phone(phone: str, referrer_code: str, db) -> dict:
    """
    Use Whapi phone verification as the PRIMARY anti-fraud gate.
    A referral only counts if it's a unique, active WhatsApp number.

    Returns:
        dict with 'valid', 'reason', 'phone_hash' (for duplicate detection)
    """
    # First, validate the phone is on WhatsApp
    validation = await validate_whatsapp_number(phone)

    if not validation.get("valid"):
        return {
            "valid": False,
            "reason": validation.get("reason", "Phone not on WhatsApp"),
            "fraud_type": "invalid_whatsapp",
        }

    normalized = validation.get("phone_normalized", normalize_phone_number(phone))

    # Create phone hash for duplicate detection (privacy-preserving)
    phone_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]

    # Check if this phone was already used by this referrer
    existing = await db.verified_referrals.find_one(
        {"referrer_code": referrer_code, "phone_hash": phone_hash}
    )

    if existing:
        return {
            "valid": False,
            "reason": "This phone number was already used for a referral",
            "fraud_type": "duplicate_phone",
        }

    # Check if this phone was used too many times across all referrers
    phone_usage_count = await db.verified_referrals.count_documents(
        {"phone_hash": phone_hash}
    )

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
        "whatsapp_verified": True,
    }


# ============= MARKETING LAB INTEGRATION =============


async def get_whatsapp_broadcast_list(db, filters: dict = None) -> List[dict]:
    """
    Get list of WhatsApp/SMS-verified contacts for Marketing Lab broadcasts.
    Aggregates contacts from ALL Data Hub sources:
    - Bio-Age Scans
    - Founding Members / Waitlist
    - Partners
    - Customers (from orders)
    - SMS Subscribers (from exit popup)

    Args:
        db: Database instance
        filters: Optional filters like {'intent': 'high', 'concern': 'dark_circles', 'source': 'customers'}

    Returns:
        List of contacts with phone, name, email, source tags
    """
    contacts = []
    seen_phones = set()  # Avoid duplicates
    
    source_filter = filters.get("source") if filters else None
    
    # 1. Bio-Age Scans (has whatsapp field)
    if not source_filter or source_filter == "bio_scans":
        query = {"whatsapp": {"$exists": True, "$ne": None, "$ne": ""}}
        if filters:
            if filters.get("intent") == "high":
                query["tags"] = {"$in": ["intent:high"]}
            if filters.get("concern"):
                query["concern"] = filters["concern"]
            if filters.get("has_scan"):
                query["bio_scan_completed"] = True

        async for scan in db.bio_scans.find(query, {"_id": 0}):
            phone = (scan.get("whatsapp") or "").strip()
            if phone and phone not in seen_phones:
                seen_phones.add(phone)
                contacts.append({
                    "phone": phone,
                    "name": scan.get("name", ""),
                    "email": scan.get("email", ""),
                    "concern": scan.get("concern", ""),
                    "source": "bio_scan",
                    "source_label": "Bio-Age Scan",
                    "source_color": "purple",
                    "referral_code": scan.get("referral_code", ""),
                })

    # 2. Founding Members / Waitlist
    if not source_filter or source_filter == "waitlist":
        async for member in db.founding_members.find(
            {"whatsapp": {"$exists": True, "$ne": None, "$ne": ""}}, {"_id": 0}
        ):
            phone = (member.get("whatsapp") or "").strip()
            if phone and phone not in seen_phones:
                seen_phones.add(phone)
                contacts.append({
                    "phone": phone,
                    "name": member.get("name", ""),
                    "email": member.get("email", ""),
                    "concern": "",
                    "source": "waitlist",
                    "source_label": "Waitlist",
                    "source_color": "amber",
                    "referral_code": member.get("referral_code", ""),
                })

    # 3. Partners (approved)
    if not source_filter or source_filter == "partners":
        async for partner in db.partners.find(
            {"status": "approved", "phone": {"$exists": True, "$ne": None, "$ne": ""}}, {"_id": 0}
        ):
            phone = (partner.get("phone") or "").strip()
            if phone and phone not in seen_phones:
                seen_phones.add(phone)
                contacts.append({
                    "phone": phone,
                    "name": partner.get("name", partner.get("business_name", "")),
                    "email": partner.get("email", ""),
                    "concern": "",
                    "source": "partner",
                    "source_label": "Partner",
                    "source_color": "emerald",
                    "referral_code": partner.get("referral_code", ""),
                })

    # 4. Customers (from orders with phone)
    if not source_filter or source_filter == "customers":
        async for order in db.orders.find(
            {"shipping_address.phone": {"$exists": True, "$ne": None, "$ne": ""}}, 
            {"_id": 0, "shipping_address": 1, "email": 1, "customer_name": 1}
        ):
            phone = (order.get("shipping_address", {}).get("phone") or "").strip()
            # Normalize phone
            if phone:
                digits = ''.join(filter(str.isdigit, phone))
                if len(digits) == 10:
                    phone = f"+1{digits}"
                elif len(digits) == 11 and digits.startswith("1"):
                    phone = f"+{digits}"
                elif not phone.startswith("+"):
                    phone = f"+{digits}"
            
            if phone and phone not in seen_phones:
                seen_phones.add(phone)
                contacts.append({
                    "phone": phone,
                    "name": order.get("customer_name", order.get("shipping_address", {}).get("name", "")),
                    "email": order.get("email", ""),
                    "concern": "",
                    "source": "customer",
                    "source_label": "Customer",
                    "source_color": "pink",
                    "referral_code": "",
                })

    # 5. SMS Subscribers (from exit popup)
    if not source_filter or source_filter == "sms_subscribers":
        async for sub in db.sms_subscribers.find(
            {"is_active": True, "phone": {"$exists": True, "$ne": None}}, {"_id": 0}
        ):
            phone = (sub.get("phone") or "").strip()
            if phone and phone not in seen_phones:
                seen_phones.add(phone)
                contacts.append({
                    "phone": phone,
                    "name": "",
                    "email": sub.get("email", ""),
                    "concern": "",
                    "source": "sms_popup",
                    "source_label": "SMS Signup",
                    "source_color": "blue",
                    "referral_code": "",
                })

    return contacts


async def analyze_scan_concerns(db) -> dict:
    """
    Analyze bio-scan data to find top concerns for AI content generation.
    Used by Marketing Lab to auto-generate targeted WhatsApp scripts.

    Returns:
        dict with concern breakdown and suggested content angles
    """
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
        percentage = (
            round((c["count"] / total_scans) * 100, 1) if total_scans > 0 else 0
        )
        concern_breakdown.append(
            {"concern": c["_id"], "count": c["count"], "percentage": percentage}
        )

    # Generate content suggestions based on top concerns
    content_suggestions = []
    if concern_breakdown:
        top_concern = concern_breakdown[0]
        if top_concern["percentage"] > 50:
            content_suggestions.append(
                {
                    "type": "whatsapp_script",
                    "topic": top_concern["concern"],
                    "hook": f"{int(top_concern['percentage'])}% of our scans show '{top_concern['concern']}' as the #1 concern.",
                    "angle": f"Focus on how PDRN addresses {top_concern['concern']}",
                }
            )

        # Add secondary suggestion if multiple concerns
        if len(concern_breakdown) > 1:
            second = concern_breakdown[1]
            content_suggestions.append(
                {
                    "type": "instagram_post",
                    "topic": second["concern"],
                    "hook": f"Struggling with {second['concern']}? You're not alone.",
                    "angle": "Before/after testimonial style",
                }
            )

    return {
        "total_scans": total_scans,
        "concern_breakdown": concern_breakdown,
        "content_suggestions": content_suggestions,
        "top_concern": concern_breakdown[0] if concern_breakdown else None,
    }


async def generate_social_proof_post(referrer_name: str, milestone: int) -> str:
    """
    Generate a 'Social Proof' post when someone hits the 10-referral milestone.
    To be used by Marketing Lab for auto-posting.
    """
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


# ============= PARTNER PROGRAM NOTIFICATIONS =============


async def send_partner_approved_whatsapp(
    phone: str, name: str, partner_code: str, referral_link: str
) -> dict:
    """
    Send WhatsApp notification when a partner application is APPROVED.
    Includes their unique code and partner dashboard link.
    """
    first_name = name.split()[0] if name else "there"

    message = f"""🎉 *Welcome to the ReRoots Partner Circle!*

Hi {first_name},

Your application has been *APPROVED*! You're now an official ReRoots Science Ambassador.

🔑 *Your Partner Code:*
*{partner_code}*

📊 *Your Referral Link:*
{referral_link}

🧬 *What's Next:*
1. Access your Partner Dashboard: https://reroots.ca/partner-dashboard
2. Download brand assets from your Resources tab
3. Share your link & start earning 10-15% commission

Your followers get up to 50% OFF with your code!

Questions? Just reply here - we're real humans 🙂

Welcome to the lab! 🧬
- ReRoots Partnership Team"""

    return await send_whatsapp_message(phone, message)


async def send_partner_denied_whatsapp(phone: str, name: str) -> dict:
    """
    Send a polite WhatsApp notification when a partner application is DENIED.
    Maintains premium brand image while declining.
    """
    first_name = name.split()[0] if name else "there"

    message = f"""Hi {first_name},

Thank you for your interest in partnering with ReRoots 🧬

After reviewing your application, we've decided not to move forward with a partnership at this time. Our program has specific requirements around audience alignment and content focus that we're prioritizing.

This isn't a reflection of your work - it's simply about finding the right fit for our biotech skincare community.

*Here's how you can still benefit:*
• Take our free Bio-Age Scan and join the Founding Member program
• Refer 10 friends to unlock a *permanent 30% discount*
• Shop with code WELCOME15 for 15% off your first order

Start here: https://reroots.ca/Bio-Age-Repair-Scan

We appreciate your interest and wish you success!

- ReRoots Team"""

    return await send_whatsapp_message(phone, message)


# ============= SHIPPING NOTIFICATIONS =============


async def send_shipping_whatsapp(
    phone: str, 
    name: str, 
    order_number: str, 
    tracking_number: str, 
    courier: str,
    tracking_url: str = None
) -> dict:
    """
    Send WhatsApp notification when an order is shipped.
    Includes tracking number and link.
    """
    first_name = name.split()[0] if name else "there"
    
    # Generate tracking URL if not provided
    if not tracking_url:
        tracking_url = f"https://www.google.com/search?q={tracking_number}+tracking"

    message = f"""📦 *Your Order Has Shipped!*

Hi {first_name},

Great news! Your ReRoots order is on its way! 🚚

🧾 *Order:* #{order_number}
📍 *Carrier:* {courier}
🔢 *Tracking #:* {tracking_number}

Track your package here:
{tracking_url}

Your skincare essentials will arrive soon! ✨

Questions? Just reply here.

- ReRoots Team 🧬"""

    return await send_whatsapp_message(phone, message)
