"""
Proactive AI Outreach System for Reroots
Automated follow-ups and proactive customer engagement.

Features:
1. 30-day post-purchase follow-up
2. Abandoned browse detection (visited 3+ times without purchase)
3. Weather-based alerts (cold/dry = skin barrier support, UV = SPF reminder)
4. Restock reminders based on product usage patterns

Sends via WhatsApp (primary) and Email (fallback).
"""

import os
import logging
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Database reference
_db = None

# Admin WhatsApp for testing
ADMIN_WHATSAPP = os.environ.get("ADMIN_WHATSAPP", "+14168869408")

# Weather API
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")


def set_db(database):
    """Set database reference."""
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════
# WEATHER-BASED SKINCARE ALERTS
# ═══════════════════════════════════════════════════════════════════

async def check_weather_for_city(city: str) -> Dict[str, Any]:
    """
    Fetch weather data for a city and determine skincare recommendations.
    Uses the dedicated weather utility.
    
    Args:
        city: City name (e.g., "Toronto", "Brampton, CA")
    
    Returns:
        Dict with weather data and skincare recommendation
    """
    from utils.weather import get_skincare_weather, get_skincare_message
    
    weather_data = await get_skincare_weather(city=city)
    
    if weather_data.get("error"):
        return weather_data
    
    # Generate message if notification needed
    if weather_data.get("should_notify"):
        weather_data["recommendation"] = get_skincare_message(
            alert_type=weather_data.get("alert_type"),
            city=weather_data.get("city")
        )
    else:
        weather_data["recommendation"] = None
    
    return weather_data


async def get_customers_with_locations() -> List[Dict[str, Any]]:
    """
    Get customers with their locations from MongoDB using priority system:
    
    Priority 1: Shipping city from orders (most accurate)
    Priority 2: Detected city from IP/browser during chat
    Priority 3: Profile city (manually set)
    
    Returns:
        List of customer dicts with email, phone, name, city, source
    """
    if _db is None:
        return []
    
    customers = []
    seen_emails = set()
    
    try:
        # ═══════════════════════════════════════════════════════════════
        # PRIORITY 1: Shipping addresses from orders (most reliable)
        # ═══════════════════════════════════════════════════════════════
        orders = await _db.orders.aggregate([
            {"$match": {"shipping_address.city": {"$exists": True, "$ne": ""}}},
            {"$sort": {"created_at": -1}},
            {"$group": {
                "_id": "$customer_email",
                "phone": {"$first": "$customer_phone"},
                "name": {"$first": "$customer_name"},
                "city": {"$first": "$shipping_address.city"},
                "region": {"$first": "$shipping_address.province"}
            }},
            {"$limit": 200}
        ]).to_list(200)
        
        for order in orders:
            email = order.get("_id")
            if email and email not in seen_emails:
                seen_emails.add(email)
                customers.append({
                    "email": email,
                    "phone": order.get("phone"),
                    "name": order.get("name", "").split()[0] if order.get("name") else None,
                    "city": order.get("city"),
                    "region": order.get("region"),
                    "source": "shipping_address",
                    "priority": 1
                })
        
        logger.info(f"[WEATHER] Found {len(customers)} customers from shipping addresses")
        
        # ═══════════════════════════════════════════════════════════════
        # PRIORITY 2: IP/Browser detected locations from chat sessions
        # ═══════════════════════════════════════════════════════════════
        sessions = await _db.reroots_chat_sessions.aggregate([
            {"$match": {
                "detected_city": {"$exists": True, "$ne": ""},
                "customer_email": {"$exists": True, "$ne": ""}
            }},
            {"$sort": {"created_at": -1}},
            {"$group": {
                "_id": "$customer_email",
                "city": {"$first": "$detected_city"},
                "region": {"$first": "$detected_region"}
            }},
            {"$limit": 200}
        ]).to_list(200)
        
        for session in sessions:
            email = session.get("_id")
            if email and email not in seen_emails:
                seen_emails.add(email)
                customers.append({
                    "email": email,
                    "phone": None,  # Session doesn't have phone
                    "name": None,
                    "city": session.get("city"),
                    "region": session.get("region"),
                    "source": "ip_detection",
                    "priority": 2
                })
        
        logger.info(f"[WEATHER] Added {len(sessions)} customers from IP detection")
        
        # ═══════════════════════════════════════════════════════════════
        # PRIORITY 3: Profile cities (manually set or detected)
        # ═══════════════════════════════════════════════════════════════
        profiles = await _db.reroots_customer_profiles.find(
            {
                "$or": [
                    {"city": {"$exists": True, "$ne": ""}},
                    {"detected_city": {"$exists": True, "$ne": ""}}
                ]
            },
            {"customer_email": 1, "customer_phone": 1, "name": 1, "city": 1, "detected_city": 1}
        ).limit(200).to_list(200)
        
        for profile in profiles:
            email = profile.get("customer_email")
            if email and email not in seen_emails:
                seen_emails.add(email)
                city = profile.get("city") or profile.get("detected_city")
                if city:
                    customers.append({
                        "email": email,
                        "phone": profile.get("customer_phone"),
                        "name": profile.get("name", "").split()[0] if profile.get("name") else None,
                        "city": city,
                        "source": "profile",
                        "priority": 3
                    })
        
        # ═══════════════════════════════════════════════════════════════
        # PRIORITY 4: Users collection (fallback)
        # ═══════════════════════════════════════════════════════════════
        users = await _db.users.find(
            {"city": {"$exists": True, "$ne": ""}, "marketing_consent": {"$ne": False}},
            {"email": 1, "phone": 1, "name": 1, "city": 1}
        ).limit(200).to_list(200)
        
        for user in users:
            email = user.get("email")
            if email and email not in seen_emails:
                seen_emails.add(email)
                customers.append({
                    "email": email,
                    "phone": user.get("phone"),
                    "name": user.get("name", "").split()[0] if user.get("name") else None,
                    "city": user.get("city"),
                    "source": "users",
                    "priority": 4
                })
        
        logger.info(f"[WEATHER] Total: {len(customers)} customers with location data")
        return customers
        
    except Exception as e:
        logger.error(f"[WEATHER] Error fetching customers: {e}")
        return []


async def run_weather_based_outreach() -> Dict[str, Any]:
    """
    Run weather-based skincare alert campaign.
    
    1. Get all customers with location data
    2. Group by city to minimize API calls
    3. Check weather for each city
    4. Send relevant alerts
    """
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cities_checked": 0,
        "alerts_sent": 0,
        "customers_notified": [],
        "errors": []
    }
    
    if not WEATHER_API_KEY:
        results["errors"].append("WEATHER_API_KEY not configured")
        return results
    
    # Get customers with locations
    customers = await get_customers_with_locations()
    
    if not customers:
        logger.info("[WEATHER] No customers with location data found")
        return results
    
    # Group customers by city
    city_customers = {}
    for customer in customers:
        city = customer["city"].strip()
        if city:
            if city not in city_customers:
                city_customers[city] = []
            city_customers[city].append(customer)
    
    logger.info(f"[WEATHER] Checking weather for {len(city_customers)} cities")
    
    # Check weather for each city and send alerts
    for city, city_customer_list in city_customers.items():
        try:
            weather_data = await check_weather_for_city(city)
            results["cities_checked"] += 1
            
            if weather_data.get("should_notify") and weather_data.get("recommendation"):
                alert_type = weather_data.get("alert_type")
                
                # Import skin concern matching
                from utils.weather import should_notify_customer
                
                # Send to customers in this city (limit 5 per city per day)
                notified_count = 0
                for customer in city_customer_list:
                    if notified_count >= 5:
                        break
                    
                    # Get customer's skin concerns AND language from profile
                    customer_concerns = []
                    customer_language = "en"
                    if _db is not None:
                        profile = await _db.reroots_customer_profiles.find_one(
                            {"customer_email": customer["email"]},
                            {"skin_concerns": 1, "skin_type": 1, "preferred_language": 1}
                        )
                        if profile:
                            concerns = profile.get("skin_concerns", [])
                            if isinstance(concerns, list):
                                customer_concerns = concerns
                            elif isinstance(concerns, str):
                                customer_concerns = [concerns]
                            if profile.get("skin_type"):
                                customer_concerns.append(profile["skin_type"])
                            # Get preferred language
                            customer_language = profile.get("preferred_language", "en")
                    
                    # Check if this alert is relevant to customer's skin concerns
                    should_send = await should_notify_customer(alert_type, customer_concerns)
                    
                    if not should_send:
                        continue
                    
                    # Check if already notified today
                    already_notified = await _db.proactive_outreach_log.find_one({
                        "customer_email": customer["email"],
                        "template": f"weather_{alert_type}",
                        "sent_at": {"$gte": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()}
                    })
                    
                    if not already_notified:
                        # Generate personalized message with customer name
                        from utils.weather import get_skincare_message
                        personalized_message = get_skincare_message(
                            alert_type=alert_type,
                            customer_name=customer.get("name"),
                            city=city
                        )
                        
                        result = await send_outreach_message(
                            customer_email=customer["email"],
                            customer_phone=customer.get("phone"),
                            customer_name=customer.get("name"),
                            template_key="weather_alert",
                            variables={
                                "location": city,
                                "weather_message": personalized_message
                            },
                            customer_language=customer_language  # Multilingual support
                        )
                        
                        if result.get("success"):
                            notified_count += 1
                            results["alerts_sent"] += 1
                            results["customers_notified"].append({
                                "email": customer["email"][:3] + "****",
                                "city": city,
                                "alert_type": alert_type,
                                "language": customer_language,
                                "skin_concerns": customer_concerns[:2] if customer_concerns else []
                            })
                        
                        await asyncio.sleep(2)  # Rate limit
            
            await asyncio.sleep(1)  # Rate limit API calls
            
        except Exception as e:
            logger.error(f"[WEATHER] Error processing city {city}: {e}")
            results["errors"].append(f"{city}: {str(e)}")
    
    # Log results
    if _db is not None:
        await _db.weather_outreach_log.insert_one(results)
    
    logger.info(f"[WEATHER] Outreach complete: {results['alerts_sent']} alerts sent to {results['cities_checked']} cities")
    
    return results


# ═══════════════════════════════════════════════════════════════════
# OUTREACH MESSAGE TEMPLATES
# ═══════════════════════════════════════════════════════════════════

TEMPLATES = {
    "30_day_followup": {
        "subject": "How's your skin feeling? 💫",
        "whatsapp": """Hi {name}! 👋

It's been 30 days since you started your AURA-GEN journey. How's your skin feeling?

✨ Many customers notice visible improvements around this time — smoother texture, more even tone, and that healthy glow.

Quick questions:
1. Have you noticed any changes?
2. Any concerns I can help with?
3. Ready for a refill?

Reply anytime — I'm here to help! 

- {ai_name} 💛""",
        "email": """Hi {name},

It's been 30 days since you started using AURA-GEN. I wanted to check in and see how your skin is responding!

Around this time, many of our customers start noticing:
• Smoother skin texture
• More even skin tone  
• That healthy, hydrated glow

I'd love to hear about your experience so far. Have you noticed any changes? Any questions about your routine?

If you're ready for a refill or want to try something new, I'm happy to recommend products based on your results.

Just reply to this email or chat with me anytime at reroots.ca.

Cheers,
{ai_name}
Reroots Aesthetics"""
    },
    
    "weather_alert": {
        "subject": "Skincare tip for today's weather 🌤️",
        "whatsapp": """{weather_message}

Questions about your routine? Just reply — I'm here to help! 💛

- {ai_name}""",
        "email": """Hi {name},

{weather_message}

Have questions about adjusting your routine for the weather? Just reply to this email or chat with me at reroots.ca.

Cheers,
{ai_name}
Reroots Aesthetics"""
    },
    
    "abandoned_browse": {
        "subject": "Still thinking about AURA-GEN? 🤔",
        "whatsapp": """Hi there! 👋

I noticed you've been checking out AURA-GEN a few times. Still deciding?

I get it — skincare is personal. Let me know if you have any questions about:
• Which products are right for your skin type
• How the AURA-GEN system works
• Ingredients and what they do

No pressure — I'm just here if you need help! 💛

- {ai_name}""",
        "email": """Hi,

I noticed you've visited our site a few times recently. Still deciding on AURA-GEN?

Skincare is personal, and I want to make sure you find exactly what works for you.

If you have any questions about:
• Which products suit your skin type
• How to build an effective routine
• Ingredients and their benefits

Just reply to this email or chat with me at reroots.ca — I'm happy to help you figure out the perfect fit.

Cheers,
{ai_name}
Reroots Aesthetics"""
    },
    
    "restock_reminder": {
        "subject": "Time for a refill? 📦",
        "whatsapp": """Hey {name}! 👋

Based on when you ordered, you might be running low on {product_name} soon.

Want me to set up a quick reorder? Same products, same address — just reply "yes" and I'll handle it!

Or if you want to try something new, I can suggest products based on your skin type.

- {ai_name} 💛""",
        "email": """Hi {name},

Just a friendly heads up — based on your last order, you might be running low on {product_name} soon.

If you'd like to reorder, just reply to this email and I'll send you a quick checkout link.

Or if you're curious about trying something new, I'm happy to recommend products based on your skin type and goals.

Let me know if you need anything!

{ai_name}
Reroots Aesthetics"""
    }
}


# ═══════════════════════════════════════════════════════════════════
# OUTREACH FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

async def send_outreach_message(
    customer_email: str,
    customer_phone: Optional[str],
    customer_name: str,
    template_key: str,
    variables: Dict[str, str] = None,
    customer_language: str = "en"
) -> Dict[str, Any]:
    """
    Send proactive outreach message via WhatsApp and/or email.
    Supports multilingual translation based on customer's preferred language.
    
    Args:
        customer_email: Customer email address
        customer_phone: Customer phone number (optional)
        customer_name: Customer name for personalization
        template_key: Which template to use (30_day_followup, etc.)
        variables: Additional variables for template formatting
        customer_language: Customer's preferred language code (default: "en")
    
    Returns:
        Dict with send results
    """
    if template_key not in TEMPLATES:
        return {"success": False, "error": f"Unknown template: {template_key}"}
    
    template = TEMPLATES[template_key]
    
    # Build variables
    vars_dict = {
        "name": customer_name or "there",
        "ai_name": "Reroots AI",
        **(variables or {})
    }
    
    results = {"template": template_key, "channels": [], "language": customer_language}
    
    # Try WhatsApp first (preferred)
    if customer_phone:
        try:
            from services.twilio_service import send_whatsapp_message
            
            message = template["whatsapp"].format(**vars_dict)
            
            # Translate if not English
            if customer_language and customer_language.lower() not in ["en", "en-us", "en-gb", "en-ca"]:
                try:
                    from utils.language import translate_ai_response
                    message = await translate_ai_response(message, customer_language, "Reroots")
                    logger.info(f"[PROACTIVE] Translated WhatsApp to {customer_language}")
                except Exception as te:
                    logger.warning(f"[PROACTIVE] Translation failed, using English: {te}")
            
            await send_whatsapp_message(customer_phone, message)
            
            results["channels"].append({
                "channel": "whatsapp",
                "status": "sent",
                "phone": customer_phone[:6] + "****"
            })
            
            logger.info(f"[PROACTIVE] Sent WhatsApp {template_key} to {customer_phone[:6]}****")
            
        except Exception as e:
            logger.warning(f"[PROACTIVE] WhatsApp failed: {e}")
            results["channels"].append({
                "channel": "whatsapp",
                "status": "failed",
                "error": str(e)
            })
    
    # Fallback to email
    if customer_email:
        try:
            from services.email_ai import send_email_with_sendgrid
            
            subject = template["subject"].format(**vars_dict)
            body = template["email"].format(**vars_dict)
            
            # Translate if not English
            if customer_language and customer_language.lower() not in ["en", "en-us", "en-gb", "en-ca"]:
                try:
                    from utils.language import translate_ai_response
                    subject = await translate_ai_response(subject, customer_language, "Reroots")
                    body = await translate_ai_response(body, customer_language, "Reroots")
                    logger.info(f"[PROACTIVE] Translated email to {customer_language}")
                except Exception as te:
                    logger.warning(f"[PROACTIVE] Email translation failed, using English: {te}")
            
            # Convert to HTML
            html_body = f"""
            <div style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <img src="https://reroots.ca/reroots-logo.jpg" alt="Reroots" style="width: 120px; margin-bottom: 20px;">
                <div style="line-height: 1.6; color: #333;">
                    {body.replace(chr(10), '<br>')}
                </div>
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 12px;">
                    Reroots Aesthetics Inc. | Mississauga, ON<br>
                    <a href="https://reroots.ca/unsubscribe?email={customer_email}" style="color: #999;">Unsubscribe</a>
                </div>
            </div>
            """
            
            await send_email_with_sendgrid(
                to_email=customer_email,
                subject=subject,
                html_content=html_body,
                from_email="hello@reroots.ca",
                from_name="Reroots AI"
            )
            
            results["channels"].append({
                "channel": "email",
                "status": "sent",
                "email": customer_email[:3] + "****@" + customer_email.split("@")[1]
            })
            
            logger.info(f"[PROACTIVE] Sent email {template_key} to {customer_email[:3]}****")
            
        except Exception as e:
            logger.warning(f"[PROACTIVE] Email failed: {e}")
            results["channels"].append({
                "channel": "email",
                "status": "failed",
                "error": str(e)
            })
    
    results["success"] = any(c["status"] == "sent" for c in results["channels"])
    
    # Log outreach to database
    if _db is not None:
        try:
            await _db.proactive_outreach_log.insert_one({
                "customer_email": customer_email,
                "customer_phone": customer_phone,
                "template": template_key,
                "language": customer_language,
                "results": results,
                "sent_at": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.warning(f"[PROACTIVE] Failed to log outreach: {e}")
    
    return results


async def find_30_day_followup_candidates() -> List[Dict[str, Any]]:
    """Find customers who ordered ~30 days ago and haven't been contacted."""
    if _db is None:
        return []
    
    # Orders from 28-32 days ago (window around 30 days)
    cutoff_start = datetime.now(timezone.utc) - timedelta(days=32)
    cutoff_end = datetime.now(timezone.utc) - timedelta(days=28)
    
    # Find orders in this window
    orders = await _db.orders.find({
        "created_at": {
            "$gte": cutoff_start.isoformat(),
            "$lte": cutoff_end.isoformat()
        },
        "status": {"$in": ["delivered", "fulfilled", "completed"]}
    }).to_list(100)
    
    # Filter out those already contacted
    candidates = []
    for order in orders:
        email = order.get("customer_email")
        if not email:
            continue
        
        # Check if already contacted for this order
        existing = await _db.proactive_outreach_log.find_one({
            "customer_email": email,
            "template": "30_day_followup",
            "sent_at": {"$gte": cutoff_start.isoformat()}
        })
        
        if not existing:
            candidates.append({
                "email": email,
                "phone": order.get("customer_phone"),
                "name": order.get("customer_name", "").split()[0] if order.get("customer_name") else None,
                "order_id": order.get("order_id"),
                "ordered_at": order.get("created_at")
            })
    
    return candidates


async def find_abandoned_browse_candidates() -> List[Dict[str, Any]]:
    """Find visitors who browsed 3+ times but didn't purchase."""
    if _db is None:
        return []
    
    # Look at sessions from last 7 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Aggregate sessions by email/phone
    # This is a simplified version - would need session tracking in production
    
    sessions = await _db.reroots_chat_sessions.aggregate([
        {"$match": {"created_at": {"$gte": cutoff.isoformat()}}},
        {"$group": {
            "_id": "$customer_email",
            "visit_count": {"$sum": 1},
            "last_visit": {"$max": "$created_at"}
        }},
        {"$match": {"visit_count": {"$gte": 3}}},
        {"$limit": 50}
    ]).to_list(50)
    
    candidates = []
    for session in sessions:
        email = session.get("_id")
        if not email:
            continue
        
        # Check if they made a purchase
        order = await _db.orders.find_one({"customer_email": email})
        if order:
            continue  # Already a customer
        
        # Check if already contacted
        existing = await _db.proactive_outreach_log.find_one({
            "customer_email": email,
            "template": "abandoned_browse",
            "sent_at": {"$gte": cutoff.isoformat()}
        })
        
        if not existing:
            candidates.append({
                "email": email,
                "visit_count": session.get("visit_count"),
                "last_visit": session.get("last_visit")
            })
    
    return candidates


# ═══════════════════════════════════════════════════════════════════
# PROACTIVE OUTREACH SCHEDULER
# ═══════════════════════════════════════════════════════════════════

async def proactive_outreach_scheduler():
    """
    Background task that runs proactive outreach campaigns.
    
    Runs daily at 10 AM EST:
    - Weather-based skincare alerts (runs first)
    - 30-day post-purchase follow-ups
    - Abandoned browse recovery
    - Restock reminders
    """
    import pytz
    est = pytz.timezone('America/Toronto')
    
    # Wait 5 minutes after startup
    await asyncio.sleep(300)
    
    logger.info("[PROACTIVE] Proactive outreach scheduler started (runs daily at 10 AM EST)")
    
    while True:
        try:
            now = datetime.now(est)
            
            # Calculate next 10 AM EST
            target = now.replace(hour=10, minute=0, second=0, microsecond=0)
            if now.hour >= 10:
                target += timedelta(days=1)
            
            wait_seconds = (target - now).total_seconds()
            logger.info(f"[PROACTIVE] Next outreach run in {wait_seconds/3600:.1f} hours")
            
            await asyncio.sleep(wait_seconds)
            
            # Run outreach campaigns
            logger.info("[PROACTIVE] Running daily outreach campaigns...")
            
            # 0. Weather-based alerts (run first - most time-sensitive)
            logger.info("[PROACTIVE] Running weather-based outreach...")
            weather_results = await run_weather_based_outreach()
            logger.info(f"[PROACTIVE] Weather outreach: {weather_results.get('alerts_sent', 0)} alerts sent")
            
            # 1. 30-day follow-ups
            followup_candidates = await find_30_day_followup_candidates()
            logger.info(f"[PROACTIVE] Found {len(followup_candidates)} 30-day followup candidates")
            
            for candidate in followup_candidates[:10]:  # Limit to 10 per day
                await send_outreach_message(
                    customer_email=candidate["email"],
                    customer_phone=candidate.get("phone"),
                    customer_name=candidate.get("name"),
                    template_key="30_day_followup"
                )
                await asyncio.sleep(5)  # Rate limit
            
            # 2. Abandoned browse
            browse_candidates = await find_abandoned_browse_candidates()
            logger.info(f"[PROACTIVE] Found {len(browse_candidates)} abandoned browse candidates")
            
            for candidate in browse_candidates[:5]:  # Limit to 5 per day
                await send_outreach_message(
                    customer_email=candidate["email"],
                    customer_phone=None,
                    customer_name=None,
                    template_key="abandoned_browse"
                )
                await asyncio.sleep(5)
            
            logger.info("[PROACTIVE] Daily outreach complete")
            
            # Wait a bit to avoid double-triggering
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"[PROACTIVE] Scheduler error: {e}")
            await asyncio.sleep(3600)  # Wait an hour on error
