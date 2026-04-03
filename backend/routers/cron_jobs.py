"""
Cron Jobs - Scheduled tasks for email automation
- Birthday emails: Daily check
- Daily sales digest: 8 AM EST
- Abandoned cart recovery: 24hr, 48hr, 72hr sequences
"""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# Database connection
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "reroots_db")

_client = None
_db = None

def get_cron_db():
    """Get database connection for cron jobs"""
    global _client, _db
    if _db is None and MONGO_URL:
        _client = AsyncIOMotorClient(MONGO_URL)
        _db = _client[DB_NAME]
    return _db


# ═══════════════════════════════════════════════════════════════════════════════
# BIRTHDAY EMAILS - Daily at midnight
# ═══════════════════════════════════════════════════════════════════════════════

async def process_birthday_emails():
    """Check for users with birthday today and send birthday emails"""
    from routers.email_service import send_birthday_email
    
    db = get_cron_db()
    if db is None:
        logger.warning("Database not available for birthday emails")
        return
    
    today = datetime.now(timezone.utc)
    today_month_day = (today.month, today.day)
    
    # Find users with birthday today
    # Birthday stored as string "YYYY-MM-DD" or datetime
    users = await db.users.find({
        "$or": [
            {"birthday": {"$regex": f"-{today.month:02d}-{today.day:02d}$"}},
            {"birthday": {"$regex": f"/{today.month}/{today.day}"}},
        ]
    }).to_list(1000)
    
    sent_count = 0
    for user in users:
        email = user.get("email")
        name = user.get("name") or user.get("first_name") or "Member"
        
        if not email:
            continue
        
        # Check if we already sent birthday email this year
        last_birthday_email = user.get("last_birthday_email")
        if last_birthday_email:
            last_year = last_birthday_email.year if hasattr(last_birthday_email, 'year') else None
            if last_year == today.year:
                continue
        
        # Add 500 bonus points
        await db.users.update_one(
            {"_id": user["_id"]},
            {
                "$inc": {"loyalty_points": 500},
                "$set": {"last_birthday_email": today}
            }
        )
        
        # Send email
        if send_birthday_email(email, name, 500):
            sent_count += 1
            logger.info(f"Birthday email sent to {email}")
    
    logger.info(f"Birthday emails processed: {sent_count} sent")
    return sent_count


# ═══════════════════════════════════════════════════════════════════════════════
# DAILY SALES DIGEST - 8 AM EST
# ═══════════════════════════════════════════════════════════════════════════════

async def send_daily_digest():
    """Generate and send daily sales digest to admin"""
    from routers.email_service import send_daily_sales_digest
    
    db = get_cron_db()
    if db is None:
        logger.warning("Database not available for daily digest")
        return
    
    # Calculate today's date range (EST timezone)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get orders from today
    orders = await db.orders.find({
        "created_at": {"$gte": today_start}
    }).to_list(1000)
    
    orders_today = len(orders)
    revenue_today = sum(o.get("total", 0) for o in orders)
    
    # Get new signups from today
    new_users = await db.users.count_documents({
        "created_at": {"$gte": today_start}
    })
    
    # Get low stock items
    low_stock_items = await db.products.find({
        "$expr": {"$lte": ["$stock", "$reorder_point"]}
    }, {"name": 1, "stock": 1, "sku": 1}).to_list(10)
    
    # Fallback query if reorder_point not set
    if not low_stock_items:
        low_stock_items = await db.products.find({
            "stock": {"$lte": 10}
        }, {"name": 1, "stock": 1, "sku": 1}).to_list(10)
    
    # Send digest
    send_daily_sales_digest(
        orders_today=orders_today,
        revenue_today=revenue_today,
        new_signups=new_users,
        low_stock_items=low_stock_items
    )
    
    logger.info(f"Daily digest sent: {orders_today} orders, ${revenue_today:.2f} revenue")


# ═══════════════════════════════════════════════════════════════════════════════
# ABANDONED CART RECOVERY - Check every hour
# ═══════════════════════════════════════════════════════════════════════════════

async def process_abandoned_carts():
    """
    Process abandoned carts and send recovery emails.
    Sequence: 24hr, 48hr, 72hr
    """
    from routers.email_service import send_abandoned_cart_reminder
    
    db = get_cron_db()
    if db is None:
        logger.warning("Database not available for abandoned cart processing")
        return
    
    now = datetime.now(timezone.utc)
    
    # Find abandoned carts (cart exists but no order)
    # Cart schema: {user_id, email, name, items, created_at, last_reminder_at, reminder_count}
    
    carts = await db.abandoned_carts.find({
        "converted": {"$ne": True},
        "unsubscribed": {"$ne": True}
    }).to_list(500)
    
    sent_count = 0
    for cart in carts:
        email = cart.get("email")
        name = cart.get("name", "there")
        items = cart.get("items", [])
        created_at = cart.get("created_at")
        reminder_count = cart.get("reminder_count", 0)
        last_reminder = cart.get("last_reminder_at")
        
        if not email or not items or not created_at:
            continue
        
        # Parse created_at if string
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        
        hours_since_created = (now - created_at).total_seconds() / 3600
        
        # Determine which email to send
        should_send = False
        sequence = 0
        
        if reminder_count == 0 and hours_since_created >= 24:
            should_send = True
            sequence = 1
        elif reminder_count == 1 and hours_since_created >= 48:
            should_send = True
            sequence = 2
        elif reminder_count == 2 and hours_since_created >= 72:
            should_send = True
            sequence = 3
        
        if should_send and sequence > 0:
            # Generate discount code for sequences 2 and 3
            discount_code = None
            if sequence >= 2:
                discount_code = f"COMEBACK10-{cart.get('_id', '')[-6:].upper()}"
            
            # Send email
            if send_abandoned_cart_reminder(email, name, items, sequence, discount_code):
                # Update cart record
                await db.abandoned_carts.update_one(
                    {"_id": cart["_id"]},
                    {
                        "$set": {"last_reminder_at": now},
                        "$inc": {"reminder_count": 1}
                    }
                )
                sent_count += 1
                logger.info(f"Abandoned cart email #{sequence} sent to {email}")
    
    logger.info(f"Abandoned cart processing complete: {sent_count} emails sent")
    return sent_count


# ═══════════════════════════════════════════════════════════════════════════════
# TIER UPGRADE CHECK - Run after loyalty points update
# ═══════════════════════════════════════════════════════════════════════════════

TIER_THRESHOLDS = {
    "Silver": 0,
    "Gold": 1000,
    "Diamond": 4000,
    "Elite": 10000
}

def get_tier_for_points(points: int) -> str:
    """Determine tier based on points"""
    if points >= 10000:
        return "Elite"
    elif points >= 4000:
        return "Diamond"
    elif points >= 1000:
        return "Gold"
    return "Silver"


async def check_tier_upgrade(user_id: str, new_points: int):
    """Check if user should be upgraded and send email"""
    from routers.email_service import send_tier_upgrade_email
    
    db = get_cron_db()
    if db is None:
        return
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        try:
            from bson import ObjectId
            user = await db.users.find_one({"_id": ObjectId(user_id)})
        except:
            return
    
    if not user:
        return
    
    current_tier = user.get("tier", "Silver")
    new_tier = get_tier_for_points(new_points)
    
    # Check if upgraded
    tier_order = ["Silver", "Gold", "Diamond", "Elite"]
    if tier_order.index(new_tier) > tier_order.index(current_tier):
        # Upgrade!
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"tier": new_tier}}
        )
        
        email = user.get("email")
        name = user.get("name") or user.get("first_name") or "Member"
        
        if email:
            send_tier_upgrade_email(email, name, new_tier, new_points)
            logger.info(f"Tier upgrade email sent to {email}: {current_tier} → {new_tier}")


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER - Run cron jobs
# ═══════════════════════════════════════════════════════════════════════════════

async def run_scheduled_tasks():
    """
    Main scheduler loop - runs in background.
    - Birthday emails: Every day at midnight UTC
    - Daily digest: Every day at 1 PM UTC (8 AM EST)
    - Abandoned carts: Every hour
    """
    logger.info("Cron scheduler started")
    
    last_birthday_check = None
    last_digest_sent = None
    last_cart_check = None
    
    while True:
        now = datetime.now(timezone.utc)
        
        try:
            # Birthday emails - once per day at midnight
            if last_birthday_check is None or now.date() > last_birthday_check.date():
                if now.hour == 0:  # Midnight UTC
                    await process_birthday_emails()
                    last_birthday_check = now
            
            # Daily digest - 1 PM UTC (8 AM EST)
            if last_digest_sent is None or now.date() > last_digest_sent.date():
                if now.hour == 13:  # 1 PM UTC = 8 AM EST
                    await send_daily_digest()
                    last_digest_sent = now
            
            # Abandoned carts - every hour
            if last_cart_check is None or (now - last_cart_check).total_seconds() >= 3600:
                await process_abandoned_carts()
                last_cart_check = now
                
        except Exception as e:
            logger.error(f"Cron job error: {e}")
        
        # Sleep for 5 minutes before next check
        await asyncio.sleep(300)
