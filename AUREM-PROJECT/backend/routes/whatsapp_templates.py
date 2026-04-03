"""
Task 5: 28-Day WhatsApp Message Templates
Using wa.me links - no WHAPI needed.
Messages are generated with wa.me links that open WhatsApp with pre-filled text.
Admin clicks to send.
"""

import os
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional, List

logger = logging.getLogger(__name__)

GOOGLE_REVIEW_LINK = os.environ.get('GOOGLE_REVIEW_LINK', 'https://g.page/r/CY76Se2EyM-_EBM/review')


def generate_whatsapp_link(phone: str, message: str) -> str:
    """Generate wa.me link with pre-filled message."""
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    message_encoded = urllib.parse.quote(message)
    return f"https://wa.me/{phone_clean}?text={message_encoded}"


# ═══════════════════════════════════════════════════════════
# DAY MESSAGE GENERATORS
# ═══════════════════════════════════════════════════════════

def day_0_message(name: str, loyalty_balance: int) -> str:
    """DAY 0 — Welcome message"""
    return f"""Hi {name}! 🌿 Welcome to ReRoots!

Your AURA-GEN PDRN+TXA Serum is on its way.

Here's what to expect:
• Week 1-2: Deep hydration + barrier repair
• Week 2-3: Brightening begins (TXA activating)
• Week 3-4: Visible pigmentation reduction 🌟

Your Roots balance: {loyalty_balance} Roots ✨

Questions? Reply anytime 🙏
- Tj, ReRoots Founder"""


def day_7_message(name: str, loyalty_balance: int) -> str:
    """DAY 7 — Check-in message"""
    roots_to_goal = max(0, 600 - loyalty_balance)
    return f"""Hey {name}! 👋

One week with AURA-GEN — how's your skin feeling?

💧 Pro tip: Apply 3-4 drops to damp skin
after cleansing for maximum penetration

Your Roots: {loyalty_balance}
({roots_to_goal} away from 30% off!)

Reply and let me know how it's going! 🌿"""


def day_14_message(name: str, loyalty_balance: int) -> str:
    """DAY 14 — Progress message"""
    return f"""Hi {name}! 🌟

2 weeks in! Early brightening should be
visible as TXA activates ✨

Tag @reroots.ca on Instagram
and earn 50 Roots! 📸

Your balance: {loyalty_balance} Roots"""


def day_21_message(name: str, token: str, loyalty_balance: int) -> str:
    """DAY 21 — Review request message"""
    review_url = f"reroots.ca/review/{token}"
    return f"""Hi {name}! 🙏

3 weeks — full PDRN cycle complete!

⭐ Leave your review (earn 100 Roots):
{review_url}

🔍 Google review:
{GOOGLE_REVIEW_LINK}

2 minutes. Means everything to us 🌿"""


def day_25_message(name: str, loyalty_balance: int) -> str:
    """DAY 25 — Running low message"""
    loyalty_value = loyalty_balance * 0.05
    return f"""Hi {name}! ⚠️

Your AURA-GEN is likely running low.
Don't break your skin cycle!

Reorder now → reroots.ca 📦

{loyalty_balance} Roots = ${loyalty_value:.2f} off 💰"""


def day_28_message(name: str, loyalty_balance: int) -> str:
    """DAY 28 — Cycle complete message"""
    goal = "🎊 You have enough for 30% off!" if loyalty_balance >= 600 else f"Only {600 - loyalty_balance} Roots to 30% off!"
    return f"""Hi {name}! 🎉

28 days — full biotech regeneration done!

Ready for round 2?
reroots.ca/bundles 📦

Your Roots: {loyalty_balance}
{goal}"""


def day_35_message(name: str, loyalty_balance: int, discount_code: str = "COMEBACK10", discount_pct: int = 10) -> str:
    """DAY 35 — Win-back message"""
    return f"""Hi {name}! 🌿

Miss you at ReRoots.

Personal offer: {discount_code} — {discount_pct}% off
Valid 7 days 💙

👉 reroots.ca

Roots waiting: {loyalty_balance}"""


# Message generator lookup
DAY_MESSAGE_GENERATORS = {
    0: ("Welcome", day_0_message),
    7: ("Check-in", day_7_message),
    14: ("Progress", day_14_message),
    21: ("Review Request", day_21_message),
    25: ("Running Low", day_25_message),
    28: ("Cycle Complete", day_28_message),
    35: ("Win-Back", day_35_message),
}


# ═══════════════════════════════════════════════════════════
# CRM ACTION FUNCTIONS
# ═══════════════════════════════════════════════════════════

async def process_day_message(db, customer: dict, order: dict, day: int, review_token: str = None) -> Optional[str]:
    """
    Generate a WhatsApp message for a specific day and store as CRM action.
    Returns the wa.me link.
    """
    if day not in DAY_MESSAGE_GENERATORS:
        return None
    
    phone = customer.get('phone')
    if not phone:
        logger.warning(f"No phone for customer {customer.get('email')}, skipping Day {day} message")
        return None
    
    name = customer.get('first_name', customer.get('email', 'there').split('@')[0])
    loyalty_balance = customer.get('loyalty_balance', 0)
    
    # Also check loyalty_members collection
    if loyalty_balance == 0:
        member = await db.loyalty_members.find_one({'email': customer.get('email')}, {'_id': 0, 'points': 1})
        if member:
            loyalty_balance = member.get('points', 0)
    
    # Generate message based on day
    label, generator = DAY_MESSAGE_GENERATORS[day]
    
    if day == 21 and review_token:
        message = generator(name, review_token, loyalty_balance)
    elif day == 35:
        # Generate unique discount code for win-back
        discount_code = f"COMEBACK{str(order.get('_id', ''))[-4:].upper()}"
        message = generator(name, loyalty_balance, discount_code, 15)
    else:
        message = generator(name, loyalty_balance)
    
    # Generate wa.me link
    whatsapp_link = generate_whatsapp_link(phone, message)
    
    # Store as CRM action for admin to send
    await db.crm_actions.insert_one({
        'customer_id': str(customer.get('_id', customer.get('id', customer.get('email')))),
        'customer_email': customer.get('email'),
        'customer_name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or customer.get('email'),
        'customer_phone': phone,
        'order_id': str(order.get('_id', order.get('id', ''))),
        'day': day,
        'label': label,
        'type': 'whatsapp',
        'message': message,
        'link': whatsapp_link,
        'status': 'pending',
        'created_at': datetime.now(timezone.utc)
    })
    
    logger.info(f"Created Day {day} WhatsApp action for {customer.get('email')}")
    return whatsapp_link


async def check_day_messages(db, target_day: int) -> int:
    """
    Check for customers who need a specific day message.
    Called by scheduler for each day (0, 7, 14, 21, 25, 28, 35).
    """
    now = datetime.now(timezone.utc)
    target_date_start = now - timedelta(days=target_day)
    target_date_end = target_date_start + timedelta(hours=24)
    
    # Find orders placed on the target day
    orders = await db.orders.find({
        'created_at': {
            '$gte': target_date_start.isoformat(),
            '$lt': target_date_end.isoformat()
        },
        'status': {'$in': ['delivered', 'completed', 'processing', 'shipped']}
    }).to_list(length=100)
    
    created_count = 0
    
    for order in orders:
        customer_email = order.get('customerEmail') or order.get('email')
        order_id = str(order.get('_id', order.get('id', '')))
        
        if not customer_email:
            continue
        
        # Check if we already created this day's action for this order
        existing = await db.crm_actions.find_one({
            'order_id': order_id,
            'day': target_day,
            'type': 'whatsapp'
        })
        if existing:
            continue
        
        # Get customer data
        customer = await db.users.find_one({'email': customer_email}, {'_id': 0})
        if not customer:
            customer = {
                'email': customer_email,
                'first_name': order.get('customerName', '').split()[0] if order.get('customerName') else customer_email.split('@')[0],
                'phone': order.get('phone')
            }
        
        if not customer.get('phone'):
            continue
        
        # For Day 21, generate a review token
        review_token = None
        if target_day == 21:
            import uuid
            review_token = str(uuid.uuid4())
            # Create review request
            await db.review_requests.insert_one({
                'customer_id': customer.get('id', customer_email),
                'order_id': order_id,
                'email': customer_email,
                'phone': customer.get('phone'),
                'customer_name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                'token': review_token,
                'status': 'pending',
                'created_at': now,
                'expires_at': now + timedelta(days=30),
                'submitted_at': None
            })
        
        # Create the CRM action
        await process_day_message(db, customer, order, target_day, review_token)
        created_count += 1
    
    logger.info(f"Day {target_day} check: {created_count} actions created from {len(orders)} orders")
    return created_count


async def get_pending_whatsapp_actions(db, limit: int = 50) -> List[dict]:
    """Get pending WhatsApp actions for admin CRM panel (both 28-day and loyalty)."""
    # Get all pending actions (not just 'whatsapp' type)
    actions = await db.crm_actions.find(
        {'status': 'pending'},
        {'_id': 0}
    ).sort('created_at', -1).limit(limit).to_list(limit)
    return actions


async def mark_whatsapp_sent(db, order_id: str, day: int) -> bool:
    """Mark a 28-day WhatsApp action as sent."""
    result = await db.crm_actions.update_one(
        {'order_id': order_id, 'day': day, 'type': 'whatsapp'},
        {'$set': {'status': 'sent', 'sent_at': datetime.now(timezone.utc)}}
    )
    return result.modified_count > 0


async def get_whatsapp_stats(db) -> dict:
    """Get WhatsApp action statistics (all types)."""
    pending = await db.crm_actions.count_documents({'status': 'pending'})
    sent = await db.crm_actions.count_documents({'status': 'sent'})
    
    # Count by action type
    pipeline = [
        {'$group': {'_id': {'type': '$action_type', 'day': '$day'}, 'count': {'$sum': 1}}}
    ]
    by_type_result = await db.crm_actions.aggregate(pipeline).to_list(50)
    by_day = {item['_id'].get('day'): item['count'] for item in by_type_result if item['_id'].get('day') is not None}
    
    return {
        'pending': pending,
        'sent': sent,
        'total': pending + sent,
        'by_day': by_day
    }


# ═══════════════════════════════════════════════════════════
# TEMPLATE STORAGE (for admin editing)
# ═══════════════════════════════════════════════════════════

DEFAULT_TEMPLATES = [
    {"key": "day_0", "day": 0, "name": "Day 0 - Welcome", "description": "Sent when order is placed"},
    {"key": "day_7", "day": 7, "name": "Day 7 - Check-in", "description": "Week 1 check-in"},
    {"key": "day_14", "day": 14, "name": "Day 14 - Progress", "description": "Week 2 progress"},
    {"key": "day_21", "day": 21, "name": "Day 21 - Review", "description": "Review request + Google review"},
    {"key": "day_25", "day": 25, "name": "Day 25 - Running Low", "description": "Reorder reminder"},
    {"key": "day_28", "day": 28, "name": "Day 28 - Cycle Complete", "description": "Full cycle done"},
    {"key": "day_35", "day": 35, "name": "Day 35 - Win-Back", "description": "Win-back with discount"},
]


async def initialize_whatsapp_templates(db):
    """Initialize default templates if they don't exist."""
    existing = await db.whatsapp_templates.count_documents({})
    if existing == 0:
        for template in DEFAULT_TEMPLATES:
            # Get the actual message generator to store the template text
            if template['day'] in DAY_MESSAGE_GENERATORS:
                _, generator = DAY_MESSAGE_GENERATORS[template['day']]
                # Generate sample message
                if template['day'] == 21:
                    sample = generator("{name}", "sample-token", 250)
                elif template['day'] == 35:
                    sample = generator("{name}", 250, "COMEBACK10", 10)
                else:
                    sample = generator("{name}", 250)
                template['template'] = sample
            
            template['active'] = True
            template['created_at'] = datetime.now(timezone.utc)
            await db.whatsapp_templates.insert_one(template)
        logger.info(f"Initialized {len(DEFAULT_TEMPLATES)} WhatsApp templates")
    return existing == 0


async def get_all_whatsapp_templates(db) -> List[dict]:
    """Get all templates for admin panel."""
    templates = await db.whatsapp_templates.find({}, {"_id": 0}).sort("day", 1).to_list(20)
    return templates


async def update_whatsapp_template(db, key: str, updates: dict) -> bool:
    """Update a template from admin panel."""
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db.whatsapp_templates.update_one(
        {"key": key},
        {"$set": updates}
    )
    return result.modified_count > 0


async def get_whatsapp_template(db, key: str) -> Optional[dict]:
    """Get a specific template by key."""
    template = await db.whatsapp_templates.find_one({"key": key}, {"_id": 0})
    return template


# ═══════════════════════════════════════════════════════════
# TASK 6: LOYALTY POINTS EVENT NOTIFICATIONS
# ═══════════════════════════════════════════════════════════

def points_earned_message(name: str, points_earned: int, new_balance: int, is_first_order: bool = False) -> str:
    """Points earned after every order."""
    roots_to_goal = max(0, 600 - new_balance)
    goal = "🎊 You have enough for 30% off!" if new_balance >= 600 else f"Only {roots_to_goal} Roots to 30% off!"
    reason = "First purchase bonus — double points! 🌟" if is_first_order else "Purchase reward"
    return f"""🌿 You earned {points_earned} Roots, {name}!

Reason: {reason}
New balance: {new_balance} Roots
(${new_balance * 0.05:.2f} value)

{goal}

View balance: reroots.ca/account 🌿"""


def redemption_confirmed_message(name: str, points_redeemed: int, discount: float, new_balance: int) -> str:
    """Redemption confirmed at checkout."""
    return f"""✅ Roots redeemed, {name}!

{points_redeemed} Roots applied → ${discount:.2f} off 🎉

Remaining balance: {new_balance} Roots
(${new_balance * 0.05:.2f} value)

Thank you for shopping ReRoots 🌿
reroots.ca"""


def gift_sent_message(name: str, points_gifted: int, recipient_email: str, new_balance: int, is_new: bool = False) -> str:
    """Gift sent notification to sender."""
    bonus = "\n🌟 +50 bonus Roots for gifting to a new member!" if is_new else ""
    return f"""🎁 Roots gift sent, {name}!

You gifted {points_gifted} Roots to {recipient_email}{bonus}

Your new balance: {new_balance} Roots
(${new_balance * 0.05:.2f} value)

Thank you for sharing ReRoots 🌿"""


def gift_received_message(name: str, points_gifted: int, new_balance: int) -> str:
    """Gift received notification to recipient."""
    return f"""🎁 You received a Roots gift, {name}!

{points_gifted} Roots added to your account
= ${points_gifted * 0.05:.2f} to use at checkout

Your balance: {new_balance} Roots

Redeem at reroots.ca 🌿"""


def review_thankyou_message(name: str, new_balance: int) -> str:
    """Thank you message after review submission."""
    return f"""🌟 Thank you for your review, {name}!

+100 Roots added to your account 🎉
New balance: {new_balance} Roots
(${new_balance * 0.05:.2f} value)

Love ReRoots? Leave a Google review too 💙
{GOOGLE_REVIEW_LINK}

reroots.ca 🌿"""


# ═══════════════════════════════════════════════════════════
# TASK 7: BIRTHDAY + REFERRAL BONUS MESSAGES
# ═══════════════════════════════════════════════════════════

def birthday_bonus_message(name: str, new_balance: int) -> str:
    """Birthday bonus notification."""
    return f"""🎂 Happy Birthday {name}!

ReRoots is celebrating with you 🎉
We just added 100 Roots to your account!

New balance: {new_balance} Roots
(${new_balance * 0.05:.2f} value)

Treat yourself today 🌿
reroots.ca"""


def referral_bonus_message(name: str, new_balance: int) -> str:
    """Referral bonus notification when referred customer makes first purchase."""
    return f"""🎉 Your referral just made their first purchase, {name}!

You earned 500 Roots 🌟
New balance: {new_balance} Roots
(${new_balance * 0.05:.2f} value)

Thank you for sharing ReRoots 💙
reroots.ca 🌿"""


async def notify_birthday_bonus(db, customer: dict, new_balance: int) -> str:
    """Create WhatsApp notification for birthday bonus."""
    name = customer.get('first_name', customer.get('email', 'there').split('@')[0])
    message = birthday_bonus_message(name, new_balance)
    return await store_whatsapp_action(
        db=db,
        customer_id=str(customer.get('_id', customer.get('id', customer.get('email')))),
        customer_email=customer.get('email'),
        customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or customer.get('email'),
        phone=customer.get('phone'),
        message=message,
        action_type='birthday_bonus'
    )


async def notify_referral_bonus(db, referrer: dict, new_balance: int) -> str:
    """Create WhatsApp notification for referral bonus."""
    name = referrer.get('first_name', referrer.get('email', 'there').split('@')[0])
    message = referral_bonus_message(name, new_balance)
    return await store_whatsapp_action(
        db=db,
        customer_id=str(referrer.get('_id', referrer.get('id', referrer.get('email')))),
        customer_email=referrer.get('email'),
        customer_name=f"{referrer.get('first_name', '')} {referrer.get('last_name', '')}".strip() or referrer.get('email'),
        phone=referrer.get('phone'),
        message=message,
        action_type='referral_bonus'
    )


async def store_whatsapp_action(db, customer_id: str, customer_email: str, customer_name: str, 
                                 phone: str, message: str, action_type: str) -> str:
    """
    Store a WhatsApp CRM action with pre-filled wa.me link.
    Used for instant loyalty notifications.
    Returns the wa.me link.
    """
    import uuid
    
    if not phone:
        logger.warning(f"No phone for customer {customer_email}, skipping {action_type} WhatsApp action")
        return None
    
    link = generate_whatsapp_link(phone, message)
    action_id = str(uuid.uuid4())
    
    await db.crm_actions.insert_one({
        'action_id': action_id,
        'customer_id': customer_id,
        'customer_email': customer_email,
        'customer_name': customer_name,
        'customer_phone': phone,
        'type': action_type,
        'action_type': action_type,  # Redundant but keeps consistency
        'message': message,
        'link': link,
        'status': 'pending',
        'created_at': datetime.now(timezone.utc)
    })
    
    logger.info(f"Created {action_type} WhatsApp action for {customer_email}")
    return link


# Convenience wrappers for each event
async def notify_points_earned(db, customer: dict, points_earned: int, new_balance: int, is_first_order: bool = False) -> str:
    """Create WhatsApp notification for points earned."""
    name = customer.get('first_name', customer.get('email', 'there').split('@')[0])
    message = points_earned_message(name, points_earned, new_balance, is_first_order)
    return await store_whatsapp_action(
        db=db,
        customer_id=str(customer.get('_id', customer.get('id', customer.get('email')))),
        customer_email=customer.get('email'),
        customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or customer.get('email'),
        phone=customer.get('phone'),
        message=message,
        action_type='points_earned'
    )


async def notify_redemption_confirmed(db, customer: dict, points_redeemed: int, discount: float, new_balance: int) -> str:
    """Create WhatsApp notification for redemption."""
    name = customer.get('first_name', customer.get('email', 'there').split('@')[0])
    message = redemption_confirmed_message(name, points_redeemed, discount, new_balance)
    return await store_whatsapp_action(
        db=db,
        customer_id=str(customer.get('_id', customer.get('id', customer.get('email')))),
        customer_email=customer.get('email'),
        customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or customer.get('email'),
        phone=customer.get('phone'),
        message=message,
        action_type='redemption_confirmed'
    )


async def notify_gift_sent(db, sender: dict, points_gifted: int, recipient_email: str, new_balance: int, is_new: bool = False) -> str:
    """Create WhatsApp notification for gift sender."""
    name = sender.get('first_name', sender.get('email', 'there').split('@')[0])
    message = gift_sent_message(name, points_gifted, recipient_email, new_balance, is_new)
    return await store_whatsapp_action(
        db=db,
        customer_id=str(sender.get('_id', sender.get('id', sender.get('email')))),
        customer_email=sender.get('email'),
        customer_name=f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip() or sender.get('email'),
        phone=sender.get('phone'),
        message=message,
        action_type='gift_sent'
    )


async def notify_gift_received(db, recipient: dict, points_gifted: int, new_balance: int) -> str:
    """Create WhatsApp notification for gift recipient."""
    name = recipient.get('first_name', recipient.get('email', 'there').split('@')[0])
    message = gift_received_message(name, points_gifted, new_balance)
    return await store_whatsapp_action(
        db=db,
        customer_id=str(recipient.get('_id', recipient.get('id', recipient.get('email')))),
        customer_email=recipient.get('email'),
        customer_name=f"{recipient.get('first_name', '')} {recipient.get('last_name', '')}".strip() or recipient.get('email'),
        phone=recipient.get('phone'),
        message=message,
        action_type='gift_received'
    )


async def notify_review_thankyou(db, customer: dict, new_balance: int) -> str:
    """Create WhatsApp notification for review thank you."""
    name = customer.get('first_name', customer.get('email', 'there').split('@')[0])
    message = review_thankyou_message(name, new_balance)
    return await store_whatsapp_action(
        db=db,
        customer_id=str(customer.get('_id', customer.get('id', customer.get('email')))),
        customer_email=customer.get('email'),
        customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or customer.get('email'),
        phone=customer.get('phone'),
        message=message,
        action_type='review_thankyou'
    )

