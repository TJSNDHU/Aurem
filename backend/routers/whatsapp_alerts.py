"""
WhatsApp Alerts Router - Transactional & Marketing Alerts via WHAPI
Alerts: Order updates, shipping, abandoned cart, promos, low stock, restock
"""

import os
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp-alerts", tags=["WhatsApp Alerts"])

# WHAPI Configuration
WHAPI_API_TOKEN = os.environ.get("WHAPI_API_TOKEN", "")
WHAPI_API_URL = os.environ.get("WHAPI_API_URL", "https://gate.whapi.cloud")

# Admin phone for alerts (set this in .env or hardcode)
ADMIN_PHONE = os.environ.get("ADMIN_WHATSAPP", "")

# MongoDB reference
_db = None

def set_db(database):
    """Set database reference"""
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════════════════
# WHAPI SEND FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

async def send_whatsapp(phone: str, message: str) -> Dict:
    """
    Send WhatsApp message via WHAPI.
    Phone should be in format: 1234567890 (no + or spaces)
    """
    if not WHAPI_API_TOKEN:
        logger.warning("[WhatsApp] WHAPI_API_TOKEN not configured")
        return {"success": False, "error": "WHAPI not configured"}
    
    # Normalize phone number
    phone = phone.lstrip("+").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{WHAPI_API_URL}/messages/text",
                headers={
                    "accept": "application/json",
                    "authorization": f"Bearer {WHAPI_API_TOKEN}",
                    "content-type": "application/json"
                },
                json={
                    "to": f"{phone}@s.whatsapp.net",
                    "body": message
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[WhatsApp] Message sent to {phone[:5]}***")
                return {"success": True, "message_id": data.get("message", {}).get("id")}
            else:
                logger.error(f"[WhatsApp] Send failed: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
                
    except Exception as e:
        logger.error(f"[WhatsApp] Send error: {e}")
        return {"success": False, "error": str(e)}


async def send_whatsapp_media(phone: str, media_url: str, caption: str = "") -> Dict:
    """Send WhatsApp image/media message"""
    if not WHAPI_API_TOKEN:
        return {"success": False, "error": "WHAPI not configured"}
    
    phone = phone.lstrip("+").replace("-", "").replace(" ", "")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{WHAPI_API_URL}/messages/image",
                headers={
                    "accept": "application/json",
                    "authorization": f"Bearer {WHAPI_API_TOKEN}",
                    "content-type": "application/json"
                },
                json={
                    "to": f"{phone}@s.whatsapp.net",
                    "media": {"link": media_url},
                    "caption": caption
                }
            )
            
            if response.status_code == 200:
                return {"success": True}
            else:
                return {"success": False, "error": response.text}
                
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATES = {
    "order_confirmed": """✨ *Order Confirmed* ✨

Hi {name}! Your ReRoots order #{order_id} has been received.

📦 *Items:* {items}
💰 *Total:* ${total:.2f} CAD

We're preparing your biotech skincare with care. You'll receive tracking info once shipped.

Thank you for choosing ReRoots! 🌿""",

    "order_shipped": """🚚 *Your Order Has Shipped!*

Hi {name}! Great news — your ReRoots order #{order_id} is on the way!

📦 *Carrier:* {carrier}
🔗 *Track:* {tracking_link}
📅 *Est. Arrival:* {eta}

Questions? Reply to this message anytime.""",

    "order_delivered": """🎉 *Package Delivered!*

Hi {name}! Your ReRoots order #{order_id} has been delivered.

We hope you love your new skincare! For best results, follow the usage instructions included.

💬 Questions about your products? Just reply here!

Enjoying ReRoots? Share your glow: @rerootscanada""",

    "abandoned_cart_1": """Hey {name} 👋

You left some skincare goodness in your cart!

🛒 *Your Cart:* {items}

Your skin is waiting for its upgrade. Complete your order before these sell out!

👉 {cart_link}""",

    "abandoned_cart_2": """Hi {name}! Still thinking about it? 🤔

We saved your cart:
{items}

Here's *10% off* to help you decide:
🎁 Code: *COMEBACK10*

👉 {cart_link}

Expires in 24 hours!""",

    "abandoned_cart_3": """⏰ *Last Chance, {name}!*

Your cart is about to expire and some items are running low.

{items}

Use *COMEBACK10* for 10% off — valid today only!

👉 {cart_link}""",

    "promo_broadcast": """✨ *{headline}* ✨

{message}

🛒 Shop now: {link}

Reply STOP to unsubscribe.""",

    "restock_alert": """🔔 *Back in Stock!*

Hi {name}! The {product} you were waiting for is back!

Only {stock} units available — they won't last long.

👉 {link}

Get yours before it's gone!""",

    "low_stock_admin": """⚠️ *LOW STOCK ALERT*

Product: {product}
SKU: {sku}
Current Stock: {stock}
Reorder Point: {reorder_point}

Action needed: Restock immediately.""",

    "daily_digest_admin": """📊 *Daily Sales Digest*
{date}

💰 Revenue: ${revenue:.2f}
📦 Orders: {orders}
👥 New Signups: {signups}
🔴 Low Stock Items: {low_stock_count}

View details in admin panel.""",

    "welcome": """🌿 *Welcome to ReRoots!*

Hi {name}! Thanks for joining our skincare family.

You've earned *{points} loyalty points* to start!

Discover biotech skincare that works at the cellular level.

👉 Explore: reroots.ca/app

Questions? Just reply here!""",

    "birthday": """🎂 *Happy Birthday, {name}!*

It's your special day, and we have a gift!

🎁 *{bonus_points} bonus points* added to your account

Treat yourself to something special:
👉 reroots.ca/app

Have a wonderful birthday! 🎉""",

    "tier_upgrade": """🏆 *Congratulations, {name}!*

You've been upgraded to *{tier}* status!

Your new perks:
{perks}

Thank you for being part of ReRoots! 🌿"""
}


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class OrderAlertRequest(BaseModel):
    phone: str = Field(..., description="Customer phone number")
    name: str = Field(default="Customer")
    order_id: str = Field(...)
    alert_type: str = Field(..., description="confirmed, shipped, delivered")
    items: str = Field(default="Your items")
    total: float = Field(default=0.0)
    carrier: str = Field(default="FlagShip")
    tracking_link: str = Field(default="")
    eta: str = Field(default="2-3 business days")


class AbandonedCartAlertRequest(BaseModel):
    phone: str = Field(...)
    name: str = Field(default="there")
    items: str = Field(...)
    cart_link: str = Field(default="https://reroots.ca/cart")
    sequence: int = Field(default=1, description="1=gentle, 2=discount, 3=urgency")


class PromoRequest(BaseModel):
    phones: List[str] = Field(..., description="List of phone numbers")
    headline: str = Field(...)
    message: str = Field(...)
    link: str = Field(default="https://reroots.ca/app")


class RestockAlertRequest(BaseModel):
    phone: str = Field(...)
    name: str = Field(default="there")
    product: str = Field(...)
    stock: int = Field(default=10)
    link: str = Field(default="https://reroots.ca/app")


class LowStockAdminRequest(BaseModel):
    product: str = Field(...)
    sku: str = Field(...)
    stock: int = Field(...)
    reorder_point: int = Field(default=10)


class SendMessageRequest(BaseModel):
    phone: str = Field(...)
    message: str = Field(...)


# ═══════════════════════════════════════════════════════════════════════════════
# ORDER ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/order")
async def send_order_alert(request: OrderAlertRequest):
    """Send order status WhatsApp alert"""
    try:
        if request.alert_type == "confirmed":
            template = TEMPLATES["order_confirmed"]
            message = template.format(
                name=request.name,
                order_id=request.order_id,
                items=request.items,
                total=request.total
            )
        elif request.alert_type == "shipped":
            template = TEMPLATES["order_shipped"]
            message = template.format(
                name=request.name,
                order_id=request.order_id,
                carrier=request.carrier,
                tracking_link=request.tracking_link or "Check email for tracking",
                eta=request.eta
            )
        elif request.alert_type == "delivered":
            template = TEMPLATES["order_delivered"]
            message = template.format(
                name=request.name,
                order_id=request.order_id
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown alert_type: {request.alert_type}")
        
        result = await send_whatsapp(request.phone, message)
        
        # Log to database
        if _db is not None:
            await _db.whatsapp_alerts_log.insert_one({
                "type": f"order_{request.alert_type}",
                "phone": request.phone[:5] + "***",
                "order_id": request.order_id,
                "success": result.get("success"),
                "sent_at": datetime.now(timezone.utc).isoformat()
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[WhatsApp] Order alert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ABANDONED CART ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/abandoned-cart")
async def send_abandoned_cart_alert(request: AbandonedCartAlertRequest):
    """Send abandoned cart WhatsApp reminder"""
    try:
        if request.sequence == 1:
            template = TEMPLATES["abandoned_cart_1"]
        elif request.sequence == 2:
            template = TEMPLATES["abandoned_cart_2"]
        else:
            template = TEMPLATES["abandoned_cart_3"]
        
        message = template.format(
            name=request.name,
            items=request.items,
            cart_link=request.cart_link
        )
        
        result = await send_whatsapp(request.phone, message)
        
        if _db is not None:
            await _db.whatsapp_alerts_log.insert_one({
                "type": f"abandoned_cart_{request.sequence}",
                "phone": request.phone[:5] + "***",
                "success": result.get("success"),
                "sent_at": datetime.now(timezone.utc).isoformat()
            })
        
        return result
        
    except Exception as e:
        logger.error(f"[WhatsApp] Abandoned cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# PROMO BROADCAST
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/broadcast")
async def send_promo_broadcast(request: PromoRequest, background_tasks: BackgroundTasks):
    """Send promotional WhatsApp broadcast to multiple numbers"""
    try:
        message = TEMPLATES["promo_broadcast"].format(
            headline=request.headline,
            message=request.message,
            link=request.link
        )
        
        # Send in background to avoid timeout
        async def send_broadcast():
            sent = 0
            failed = 0
            for phone in request.phones:
                result = await send_whatsapp(phone, message)
                if result.get("success"):
                    sent += 1
                else:
                    failed += 1
            
            if _db is not None:
                await _db.whatsapp_broadcasts.insert_one({
                    "headline": request.headline,
                    "recipients": len(request.phones),
                    "sent": sent,
                    "failed": failed,
                    "sent_at": datetime.now(timezone.utc).isoformat()
                })
        
        background_tasks.add_task(send_broadcast)
        
        return {
            "status": "queued",
            "recipients": len(request.phones),
            "message": "Broadcast started in background"
        }
        
    except Exception as e:
        logger.error(f"[WhatsApp] Broadcast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# RESTOCK ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/restock")
async def send_restock_alert(request: RestockAlertRequest):
    """Send restock notification to customer"""
    try:
        message = TEMPLATES["restock_alert"].format(
            name=request.name,
            product=request.product,
            stock=request.stock,
            link=request.link
        )
        
        result = await send_whatsapp(request.phone, message)
        return result
        
    except Exception as e:
        logger.error(f"[WhatsApp] Restock alert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restock/notify-waitlist")
async def notify_restock_waitlist(product_id: str, product_name: str, stock: int):
    """Notify all waitlist customers when product is restocked"""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get waitlist entries for this product
        waitlist = await _db.waitlist.find({
            "product_id": product_id,
            "notified": {"$ne": True}
        }).to_list(100)
        
        sent = 0
        for entry in waitlist:
            phone = entry.get("phone")
            name = entry.get("name", "there")
            
            if phone:
                result = await send_whatsapp(phone, TEMPLATES["restock_alert"].format(
                    name=name,
                    product=product_name,
                    stock=stock,
                    link=f"https://reroots.ca/app?product={product_id}"
                ))
                
                if result.get("success"):
                    sent += 1
                    # Mark as notified
                    await _db.waitlist.update_one(
                        {"_id": entry["_id"]},
                        {"$set": {"notified": True, "notified_at": datetime.now(timezone.utc).isoformat()}}
                    )
        
        return {"notified": sent, "total_waitlist": len(waitlist)}
        
    except Exception as e:
        logger.error(f"[WhatsApp] Waitlist notify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/admin/low-stock")
async def send_low_stock_admin_alert(request: LowStockAdminRequest):
    """Send low stock alert to admin via WhatsApp"""
    if not ADMIN_PHONE:
        return {"success": False, "error": "ADMIN_WHATSAPP not configured"}
    
    try:
        message = TEMPLATES["low_stock_admin"].format(
            product=request.product,
            sku=request.sku,
            stock=request.stock,
            reorder_point=request.reorder_point
        )
        
        result = await send_whatsapp(ADMIN_PHONE, message)
        return result
        
    except Exception as e:
        logger.error(f"[WhatsApp] Low stock admin alert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/daily-digest")
async def send_daily_digest_admin():
    """Send daily sales digest to admin via WhatsApp"""
    if not ADMIN_PHONE:
        return {"success": False, "error": "ADMIN_WHATSAPP not configured"}
    
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Get today's stats
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count orders today
        orders_today = await _db.orders.count_documents({
            "created_at": {"$gte": today.isoformat()}
        })
        
        # Sum revenue
        revenue_pipeline = [
            {"$match": {"created_at": {"$gte": today.isoformat()}}},
            {"$group": {"_id": None, "total": {"$sum": "$total"}}}
        ]
        revenue_result = await _db.orders.aggregate(revenue_pipeline).to_list(1)
        revenue = revenue_result[0]["total"] if revenue_result else 0
        
        # Count new signups
        signups = await _db.users.count_documents({
            "created_at": {"$gte": today.isoformat()}
        })
        
        # Count low stock items
        low_stock = await _db.products.count_documents({
            "stock": {"$lt": 10}
        })
        
        message = TEMPLATES["daily_digest_admin"].format(
            date=today.strftime("%B %d, %Y"),
            revenue=revenue,
            orders=orders_today,
            signups=signups,
            low_stock_count=low_stock
        )
        
        result = await send_whatsapp(ADMIN_PHONE, message)
        return result
        
    except Exception as e:
        logger.error(f"[WhatsApp] Daily digest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# LIFECYCLE ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/welcome")
async def send_welcome_whatsapp(phone: str, name: str = "there", points: int = 100):
    """Send welcome WhatsApp message to new user"""
    try:
        message = TEMPLATES["welcome"].format(
            name=name,
            points=points
        )
        
        result = await send_whatsapp(phone, message)
        return result
        
    except Exception as e:
        logger.error(f"[WhatsApp] Welcome error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/birthday")
async def send_birthday_whatsapp(phone: str, name: str, bonus_points: int = 500):
    """Send birthday WhatsApp message"""
    try:
        message = TEMPLATES["birthday"].format(
            name=name,
            bonus_points=bonus_points
        )
        
        result = await send_whatsapp(phone, message)
        return result
        
    except Exception as e:
        logger.error(f"[WhatsApp] Birthday error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tier-upgrade")
async def send_tier_upgrade_whatsapp(phone: str, name: str, tier: str):
    """Send tier upgrade WhatsApp notification"""
    try:
        perks_map = {
            "Gold": "• 2x points\n• Early access\n• Free shipping $50+",
            "Diamond": "• 3x points\n• Exclusive products\n• Free shipping all orders",
            "Elite": "• 5x points\n• VIP concierge\n• Free expedited shipping"
        }
        
        message = TEMPLATES["tier_upgrade"].format(
            name=name,
            tier=tier,
            perks=perks_map.get(tier, "• Exclusive benefits")
        )
        
        result = await send_whatsapp(phone, message)
        return result
        
    except Exception as e:
        logger.error(f"[WhatsApp] Tier upgrade error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DIRECT SEND (Custom message)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/send")
async def send_custom_message(request: SendMessageRequest):
    """Send custom WhatsApp message"""
    try:
        result = await send_whatsapp(request.phone, request.message)
        return result
        
    except Exception as e:
        logger.error(f"[WhatsApp] Send error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# LOGS & ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/logs")
async def get_alert_logs(limit: int = 50):
    """Get WhatsApp alert logs"""
    if _db is None:
        return {"logs": []}
    
    try:
        logs = await _db.whatsapp_alerts_log.find(
            {},
            {"_id": 0}
        ).sort("sent_at", -1).limit(limit).to_list(limit)
        
        return {"logs": logs}
        
    except Exception as e:
        logger.error(f"[WhatsApp] Logs error: {e}")
        return {"logs": []}


@router.get("/broadcasts")
async def get_broadcast_history(limit: int = 20):
    """Get WhatsApp broadcast history"""
    if _db is None:
        return {"broadcasts": []}
    
    try:
        broadcasts = await _db.whatsapp_broadcasts.find(
            {},
            {"_id": 0}
        ).sort("sent_at", -1).limit(limit).to_list(limit)
        
        return {"broadcasts": broadcasts}
        
    except Exception as e:
        logger.error(f"[WhatsApp] Broadcasts error: {e}")
        return {"broadcasts": []}


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def whatsapp_health():
    """Check WhatsApp integration health"""
    return {
        "whapi_configured": bool(WHAPI_API_TOKEN),
        "admin_phone_configured": bool(ADMIN_PHONE),
        "status": "ready" if WHAPI_API_TOKEN else "not_configured"
    }
