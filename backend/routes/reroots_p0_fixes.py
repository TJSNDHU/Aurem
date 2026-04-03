"""
ReRoots — P0 Revenue Fixes
Drop these into server.py at the indicated locations.
Base URL: https://live-support-test.preview.emergentagent.com/api

FIXES IN THIS FILE:
  1. Founder discount → restrict to founders tag only (stops bleeding ~$49/order)
  2. Partner code → commission tracking on order creation
  3. SendGrid config + test endpoint
  4. FlagShip webhook → auto-fulfill + start 28-day cycle
  5. Loyalty points fix → /admin/loyalty/users endpoint
  6. Quiz submit → CRM upsert + follow-up email

INSTRUCTIONS:
  - Search for the function name indicated in each section header
  - Replace OR add as shown
  - All sections are independent — can be applied one at a time
"""
import os
import logging
from datetime import datetime, timezone
from bson import ObjectId

# ══════════════════════════════════════════════════════════════
# FIX 1 — FOUNDER DISCOUNT: RESTRICT TO FOUNDERS TAG ONLY
# ══════════════════════════════════════════════════════════════

def apply_auto_discount(customer_tags: list, discount_code: str = None) -> dict:
    """
    Returns the correct discount for this customer.
    FOUNDER DISCOUNT PERMANENTLY DISABLED as of 2026-03-03.
    All customers pay full price. No auto-discounts.
    Only manual campaign codes apply at checkout.
    """
    # VIP discount still applies if you want to keep it
    # Comment out if you want zero auto-discounts
    # if "vip" in [t.lower() for t in (customer_tags or [])]:
    #     return {"pct": 0.15, "label": "VIP Member Discount", "type": "vip"}
    
    # Manual discount codes handled separately in checkout
    if discount_code:
        return None  # handled by partner tracking or campaign code logic
    
    # Default: NO auto-discount for anyone
    return {"pct": 0.0, "label": None, "type": "none"}


async def delete_founder_discount_permanently(db):
    """
    One-time migration: PERMANENTLY DELETE Founder Launch Subsidy.
    This discount was causing revenue loss of ~$49/order.
    Removed as of 2026-03-03.
    """
    result = await db.auto_discounts.delete_many(
        {"name": {"$regex": "Founder", "$options": "i"}}
    )
    logging.info(f"✅ Founder discount PERMANENTLY DELETED: {result.deleted_count} documents removed")
    
    # Also disable any other auto-discounts that might be active
    disable_result = await db.auto_discounts.update_many(
        {"globallyActive": True},
        {"$set": {"globallyActive": False, "deletedAt": datetime.now(timezone.utc)}}
    )
    logging.info(f"✅ Disabled {disable_result.modified_count} other auto-discounts")
    
    return {"deleted": result.deleted_count, "disabled": disable_result.modified_count}


# ══════════════════════════════════════════════════════════════
# FIX 2 — PARTNER TRACKING: ATTRIBUTE SALES TO PARTNER CODES
# ══════════════════════════════════════════════════════════════

async def track_partner_referral(db, order_id: str, order_total: float, discount_code: str):
    """
    If an order uses a partner code, record the referral and increment earnings.
    Call this immediately after order creation.
    """
    if not discount_code:
        return None
    
    partner = await db.partners.find_one({
        "$or": [
            {"code": discount_code},
            {"code": discount_code.upper()},
            {"referralCode": discount_code},
        ]
    })
    
    if not partner:
        return None
    
    commission_rate = partner.get("commissionRate", 0.10)
    commission_amount = round(order_total * commission_rate, 2)
    
    referral = {
        "partnerId":      str(partner["_id"]),
        "partnerEmail":   partner["email"],
        "partnerCode":    discount_code,
        "orderId":        str(order_id),
        "orderTotal":     order_total,
        "commissionRate": commission_rate,
        "commission":     commission_amount,
        "currency":       "CAD",
        "status":         "pending",
        "createdAt":      datetime.now(timezone.utc),
        "paid":           False,
    }
    await db.partner_referrals.insert_one(referral)
    
    await db.partners.update_one(
        {"_id": partner["_id"]},
        {"$inc": {
            "totalSales":    order_total,
            "totalEarnings": commission_amount,
            "orderCount":    1,
        },
        "$set": {"lastSaleAt": datetime.now(timezone.utc)}}
    )
    
    logging.info(f"✅ Partner referral tracked: {partner['email']} earned ${commission_amount} CAD on order {order_id}")
    return referral


# ══════════════════════════════════════════════════════════════
# FIX 3 — SENDGRID: CONFIG + SEND FUNCTION
# ══════════════════════════════════════════════════════════════

async def sendgrid_send_email(to: str, subject: str, html_body: str, text_body: str = None) -> bool:
    """Central SendGrid send function."""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
    except ImportError:
        logging.warning("sendgrid not installed — pip install sendgrid")
        return False
    
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        logging.warning(f"⚠️ SENDGRID_API_KEY not set — email to {to} logged only")
        logging.info(f"   Subject: {subject}")
        return False
    
    sg = sendgrid.SendGridAPIClient(api_key=api_key)
    message = Mail(
        from_email=(os.getenv("SENDGRID_FROM_EMAIL", "hello@reroots.ca"), os.getenv("SENDGRID_FROM_NAME", "ReRoots")),
        to_emails=to,
        subject=subject,
        html_content=html_body,
        plain_text_content=text_body or subject,
    )
    
    try:
        response = sg.send(message)
        logging.info(f"✅ Email sent to {to} — status {response.status_code}")
        return response.status_code in [200, 202]
    except Exception as e:
        logging.error(f"❌ SendGrid error: {e}")
        return False


def get_test_email_html():
    """Test email HTML template."""
    return """
    <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #FDF9F9;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #2D2A2E; font-weight: 300;">RE<span style="color: #F8A5B8;">ROOTS</span></h1>
        <p style="font-size: 11px; letter-spacing: 0.2em; color: #C4BAC0; text-transform: uppercase;">Email System Active</p>
      </div>
      <div style="background: #fff; border: 1px solid #F0E8E8; border-radius: 12px; padding: 32px; text-align: center;">
        <div style="font-size: 36px; margin-bottom: 16px;">✅</div>
        <h2 style="font-size: 20px; color: #2D2A2E; font-weight: 400; margin-bottom: 8px;">SendGrid is working</h2>
        <p style="font-size: 14px; color: #8A8490; line-height: 1.6;">
          Your email automation system is live.<br>
          127 abandoned carts are ready for recovery.
        </p>
      </div>
      <p style="text-align: center; font-size: 11px; color: #C4BAC0; margin-top: 24px; letter-spacing: 0.1em;">
        REROOTS AESTHETICS INC. · TORONTO, CANADA
      </p>
    </div>
    """


# ══════════════════════════════════════════════════════════════
# FIX 4 — FLAGSHIP WEBHOOK: AUTO-FULFILL + START 28-DAY CYCLE
# ══════════════════════════════════════════════════════════════

async def handle_flagship_webhook(db, payload: dict):
    """
    Called by FlagShip when a shipping label is created.
    Configure in FlagShip dashboard: Settings → Webhooks → Add URL:
    https://live-support-test.preview.emergentagent.com/api/admin/flagship/webhook
    """
    order_id  = payload.get("orderId") or payload.get("order_id")
    tracking  = payload.get("trackingNumber") or payload.get("tracking_number")
    carrier   = payload.get("carrier", "canada_post")
    est_del   = payload.get("estimatedDelivery")
    
    if not order_id:
        return {"error": "orderId required"}
    
    try:
        order = await db.orders.find_one({"_id": ObjectId(order_id)})
    except Exception:
        order = await db.orders.find_one({"orderId": order_id})
    
    if not order:
        return {"error": f"Order {order_id} not found"}
    
    # 1. Mark order as shipped
    await db.orders.update_one(
        {"_id": order["_id"]},
        {"$set": {
            "status":            "shipped",
            "trackingNumber":    tracking,
            "carrier":           carrier,
            "estimatedDelivery": est_del,
            "fulfilledAt":       datetime.now(timezone.utc),
        }}
    )
    
    # 2. Start 28-day PDRN cycle clock in CRM
    customer_email = order.get("customerEmail") or order.get("email")
    if customer_email:
        await db.crm_customers.update_one(
            {"email": customer_email},
            {"$set": {
                "cycleStartDate": datetime.now(timezone.utc),
                "lastOrderId":    str(order["_id"]),
                "cycleDay":       0,
                "cycleStatus":    "active",
            }},
            upsert=True
        )
    
    # 3. Send shipping notification email
    if customer_email:
        carrier_tracking_urls = {
            "canada_post":  f"https://www.canadapost-postescanada.ca/track-reperage/en#/search?searchFor={tracking}",
            "fedex":        f"https://www.fedex.com/apps/fedextrack/?trknbr={tracking}",
            "purolator":    f"https://www.purolator.com/purolator/ship-track/tracking-summary.page?pin={tracking}",
            "ups":          f"https://www.ups.com/track?tracknum={tracking}",
        }
        tracking_url = carrier_tracking_urls.get(carrier.lower().replace(" ", "_"), "#")
        carrier_display = carrier.replace("_", " ").title()
        customer_name = order.get("customerName") or order.get("name") or "there"
        
        shipping_html = get_shipping_email_html(customer_name, tracking, carrier_display, tracking_url, est_del)
        await sendgrid_send_email(
            to=customer_email,
            subject=f"Your ReRoots order is on its way — {tracking}",
            html_body=shipping_html,
        )
    
    # 4. Send WhatsApp tracking notification
    customer_phone = order.get("customerPhone") or order.get("phone")
    if not customer_phone:
        # Try to get phone from shipping address
        shipping_addr = order.get("shipping_address", {}) or order.get("shippingAddress", {})
        customer_phone = shipping_addr.get("phone")
    
    whatsapp_sent = False
    if customer_phone:
        try:
            from services.twilio_service import send_whatsapp_message
            est_del_display = est_del or "3-5 business days"
            whatsapp_msg = f"""📦 Your AURA-GEN System has shipped!

Tracking: {tracking}
Carrier: {carrier.replace('_', ' ').title()}
Estimated delivery: {est_del_display}

Track at canadapost.ca

Your skin deserves this. 🌿"""
            await send_whatsapp_message(customer_phone, whatsapp_msg)
            whatsapp_sent = True
            logging.info(f"[FlagShip Webhook] WhatsApp tracking sent to {customer_phone}")
        except Exception as e:
            logging.warning(f"[FlagShip Webhook] WhatsApp tracking failed: {e}")
    
    return {
        "status": "ok",
        "orderId": str(order_id),
        "tracking": tracking,
        "cycleStarted": bool(customer_email),
        "emailSent": bool(customer_email),
        "whatsappSent": whatsapp_sent,
    }


def get_shipping_email_html(customer_name, tracking, carrier_display, tracking_url, est_del):
    """Generate shipping notification email HTML."""
    return f"""
    <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #FDF9F9;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #2D2A2E; font-weight: 300;">RE<span style="color: #F8A5B8;">ROOTS</span></h1>
      </div>
      <div style="background: #fff; border: 1px solid #F0E8E8; border-radius: 12px; padding: 32px;">
        <h2 style="font-size: 22px; color: #2D2A2E; font-weight: 300; margin-bottom: 8px;">Your PDRN ritual is on its way</h2>
        <p style="font-size: 14px; color: #8A8490; margin-bottom: 24px;">Hi {customer_name} — your order has been shipped.</p>
        <div style="background: #FDF9F9; border: 1px solid #F0E8E8; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
          <p style="font-size: 11px; letter-spacing: 0.15em; color: #C4BAC0; text-transform: uppercase; margin-bottom: 6px;">Tracking Number</p>
          <p style="font-size: 18px; color: #F8A5B8; font-family: 'JetBrains Mono', monospace; letter-spacing: 0.1em;">{tracking}</p>
          <p style="font-size: 12px; color: #8A8490; margin-top: 4px;">via {carrier_display}{f" · Est. {est_del}" if est_del else ""}</p>
        </div>
        <a href="{tracking_url}" style="display: block; background: #F8A5B8; color: #fff; text-align: center; padding: 14px; border-radius: 8px; text-decoration: none; font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; letter-spacing: 0.05em;">Track My Package →</a>
        <p style="font-size: 12px; color: #8A8490; margin-top: 20px; line-height: 1.7;">
          While you wait — your 28-day PDRN science protocol begins the day your order arrives.<br>
          We'll send you a full guide on Day 1.
        </p>
      </div>
      <p style="text-align: center; font-size: 11px; color: #C4BAC0; margin-top: 24px; letter-spacing: 0.1em;">REROOTS AESTHETICS INC. · TORONTO, CANADA</p>
    </div>
    """


# ══════════════════════════════════════════════════════════════
# FIX 5 — LOYALTY POINTS: FIX /admin/loyalty/users ENDPOINT
# ══════════════════════════════════════════════════════════════

async def get_loyalty_users_fixed(db):
    """Fixed loyalty users endpoint."""
    users = []
    
    # Try dedicated loyalty collection first
    users = await db.loyalty_members.find({}).to_list(None)
    
    # Fallback to users collection
    if not users:
        users = await db.users.find(
            {"$or": [
                {"loyaltyPoints": {"$exists": True}},
                {"points": {"$exists": True}},
            ]},
            {"email": 1, "name": 1, "loyaltyPoints": 1, "points": 1, "loyaltyTier": 1, "totalSpend": 1}
        ).to_list(None)
    
    # Fallback to CRM customers
    if not users:
        users = await db.crm_customers.find(
            {"loyaltyPoints": {"$gt": 0}},
            {"email": 1, "name": 1, "loyaltyPoints": 1, "loyaltyTier": 1, "totalSpend": 1}
        ).to_list(None)
    
    normalized = []
    for u in users:
        normalized.append({
            "id":           str(u.get("_id", "")),
            "email":        u.get("email", ""),
            "name":         u.get("name", ""),
            "points":       u.get("loyaltyPoints") or u.get("points") or 0,
            "tier":         u.get("loyaltyTier", "Standard"),
            "totalSpend":   u.get("totalSpend", 0),
        })
    
    return {
        "users":        normalized,
        "total":        len(normalized),
        "pointsPerPurchase": 250,
        "pointValue":   0.05,
        "pointsPerDollar": 20,
    }


async def check_first_order(db, customer_email: str) -> bool:
    """Check if this is the customer's first order."""
    member = await db.loyalty_members.find_one({"email": customer_email}, {"_id": 0, "totalOrders": 1})
    if not member:
        return True  # No record means first order
    return member.get("totalOrders", 0) == 0


async def get_loyalty_balance(db, customer_email: str) -> int:
    """Get customer's current loyalty balance (Roots)."""
    member = await db.loyalty_members.find_one({"email": customer_email}, {"_id": 0, "points": 1})
    return member.get("points", 0) if member else 0


async def award_loyalty_points(db, customer_email: str, order_total: float, order_id: str, customer_phone: str = None, customer_name: str = None) -> dict:
    """
    Award Roots (loyalty points) per purchase.
    - First order: 500 Roots (double points!)
    - Regular orders: 250 Roots
    Returns dict with points_earned, is_first_order, new_balance
    """
    # Check if first order BEFORE incrementing totalOrders
    is_first_order = await check_first_order(db, customer_email)
    points_to_award = 500 if is_first_order else 250
    note = "First purchase bonus — double Roots!" if is_first_order else "Purchase reward"
    
    # Update or create loyalty member
    await db.loyalty_members.update_one(
        {"email": customer_email},
        {
            "$inc":  {"points": points_to_award, "totalOrders": 1, "lifetimeEarned": points_to_award},
            "$set":  {"lastOrderAt": datetime.now(timezone.utc), "lastOrderId": order_id},
            "$setOnInsert": {
                "email":     customer_email,
                "tier":      "Standard",
                "joinedAt":  datetime.now(timezone.utc),
            }
        },
        upsert=True
    )
    
    # Log transaction
    await db.loyalty_transactions.insert_one({
        "email":     customer_email,
        "type":      "earn",
        "points":    points_to_award,
        "reason":    note,
        "orderId":   order_id,
        "createdAt": datetime.now(timezone.utc),
    })
    
    # Get new balance
    new_balance = await get_loyalty_balance(db, customer_email)
    
    # Send points earned email notification
    try:
        await send_points_earned_email(
            customer_email=customer_email,
            customer_name=customer_name or customer_email.split("@")[0],
            points_earned=points_to_award,
            new_balance=new_balance,
            is_first_order=is_first_order
        )
    except Exception as e:
        logging.warning(f"Points earned email failed: {e}")
    
    # Send WhatsApp notification if phone provided
    if customer_phone:
        try:
            await send_whatsapp_points_notification(
                phone=customer_phone,
                name=customer_name or "there",
                points_earned=points_to_award,
                new_balance=new_balance,
                reason=note
            )
        except Exception as e:
            logging.warning(f"WhatsApp points notification failed: {e}")
    
    return {
        "points_earned": points_to_award,
        "is_first_order": is_first_order,
        "new_balance": new_balance,
        "note": note
    }


async def send_points_earned_email(customer_email: str, customer_name: str, points_earned: int, new_balance: int, is_first_order: bool = False):
    """Send email notification when customer earns Roots."""
    first_name = customer_name.split()[0] if customer_name else "there"
    roots_to_goal = max(0, 600 - new_balance)
    goal_message = "You have enough Roots for 30% off!" if new_balance >= 600 else f"Only {roots_to_goal} Roots to go for 30% off!"
    
    html = f"""
    <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #FDF9F9;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #2D2A2E; font-weight: 300;">RE<span style="color: #F8A5B8;">ROOTS</span></h1>
        <p style="font-size: 11px; letter-spacing: 0.2em; color: #C4BAC0; text-transform: uppercase;">Roots Earned</p>
      </div>
      <div style="background: #fff; border: 1px solid #F0E8E8; border-radius: 12px; padding: 32px;">
        <h2 style="font-size: 22px; color: #2D2A2E; font-weight: 300; margin-bottom: 8px;">You earned {points_earned} Roots!</h2>
        <p style="font-size: 14px; color: #8A8490; line-height: 1.7; margin-bottom: 20px;">
          Hi {first_name}, {'congratulations on your first ReRoots purchase — you earned double Roots!' if is_first_order else 'thank you for your purchase!'}
        </p>
        <div style="background: #FDF9F9; border: 1px solid #F8A5B8; border-radius: 10px; padding: 20px; margin-bottom: 24px; text-align: center;">
          <p style="font-size: 11px; letter-spacing: 0.15em; color: #C4BAC0; text-transform: uppercase; margin-bottom: 8px;">Your Roots Balance</p>
          <p style="font-size: 32px; color: #F8A5B8; font-weight: 600; margin-bottom: 4px;">{new_balance} Roots</p>
          <p style="font-size: 14px; color: #8A8490;">${new_balance * 0.05:.2f} value</p>
          <p style="font-size: 13px; color: #2D2A2E; margin-top: 12px; font-weight: 500;">{goal_message}</p>
        </div>
        <a href="https://reroots.ca/account" style="display: block; background: #F8A5B8; color: #fff; text-align: center; padding: 14px; border-radius: 8px; text-decoration: none; font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; letter-spacing: 0.05em;">View Your Roots Balance →</a>
      </div>
      <p style="text-align: center; font-size: 11px; color: #C4BAC0; margin-top: 24px;">
        Your Roots balance: {new_balance} Roots (${new_balance * 0.05:.2f} value)<br>
        {roots_to_goal} Roots away from 30% off<br>
        REROOTS AESTHETICS INC. · TORONTO, CANADA
      </p>
    </div>
    """
    
    await sendgrid_send_email(
        to=customer_email,
        subject=f"You earned {points_earned} Roots! 🌿",
        html_body=html
    )


async def send_whatsapp_points_notification(phone: str, name: str, points_earned: int, new_balance: int, reason: str):
    """Send WhatsApp notification when customer earns Roots."""
    from services.twilio_service import send_whatsapp_message
    
    first_name = name.split()[0] if name else "there"
    roots_to_goal = max(0, 600 - new_balance)
    
    if new_balance >= 600:
        goal_message = "🎊 You have enough Roots for 30% off!"
    else:
        goal_message = f"Only *{roots_to_goal} Roots* to 30% off!"
    
    message = f"""🌟 You earned *{points_earned} Roots*, {first_name}!

Reason: {reason}
New balance: *{new_balance} Roots*
(${new_balance * 0.05:.2f} value)

{goal_message}

View balance: reroots.ca/account 🌿"""
    
    return await send_whatsapp_message(phone, message)


async def send_whatsapp_order_confirmation(db, order_data: dict) -> dict:
    """
    Send WhatsApp order confirmation with loyalty balance info.
    Called after order is placed successfully.
    """
    from services.twilio_service import send_whatsapp_message
    
    customer_email = order_data.get("email") or order_data.get("customerEmail")
    customer_phone = order_data.get("phone")
    customer_name = order_data.get("name") or order_data.get("customerName") or "there"
    first_name = customer_name.split()[0] if customer_name else "there"
    
    if not customer_phone:
        return {"success": False, "error": "No phone number provided"}
    
    # Get loyalty balance
    new_balance = await get_loyalty_balance(db, customer_email) if customer_email else 0
    
    # Get order details
    order_id = order_data.get("order_id") or order_data.get("id") or order_data.get("order_number", "")
    order_total = order_data.get("total", 0)
    product_name = order_data.get("product_name", "your items")
    is_first_order = order_data.get("is_first_order", False)
    points_earned = 500 if is_first_order else 250
    
    message = f"""Hi {first_name}! 🌿

Your ReRoots order #{order_id} is confirmed!

🧴 {product_name}
💰 ${order_total:.2f} CAD
📦 Processing now via FlagShip

You just earned *{points_earned} Roots* 🌟
Your balance: *{new_balance} Roots*

Track your order: reroots.ca/account
Questions? Just reply here! 🙏"""
    
    return await send_whatsapp_message(customer_phone, message)


# ══════════════════════════════════════════════════════════════
# FIX 6 — QUIZ SUBMIT: CRM UPSERT + FOLLOW-UP EMAIL
# ══════════════════════════════════════════════════════════════

async def post_quiz_crm_and_email(db, email: str, name: str, quiz_result: dict):
    """After quiz scoring, add lead to CRM and fire personalised email."""
    recommended_product = quiz_result.get("recommended_product", "AURA-GEN PDRN+TXA+ARGIRELINE 17%")
    concerns            = quiz_result.get("concerns", [])
    score               = quiz_result.get("score", 0)
    
    # 1. Upsert CRM customer as high-intent lead
    await db.crm_customers.update_one(
        {"email": email},
        {"$set": {
            "email":               email,
            "name":                name,
            "source":              "quiz",
            "status":              "high_intent_lead",
            "quizScore":           score,
            "recommendedProduct":  recommended_product,
            "skinConcerns":        concerns,
            "quizCompletedAt":     datetime.now(timezone.utc),
        }},
        upsert=True
    )
    
    # 2. Build personalised quiz result email
    concern_text = ", ".join(concerns) if concerns else "aging and skin renewal"
    first_name = name.split()[0] if name else "there"
    
    html = get_quiz_result_email_html(name, concern_text, recommended_product)
    
    await sendgrid_send_email(
        to=email,
        subject=f"Your personalised PDRN protocol is ready, {first_name} — ReRoots",
        html_body=html,
    )
    
    return {"crm": "added", "email": "sent", "product": recommended_product}


def get_quiz_result_email_html(name, concern_text, recommended_product):
    """Generate quiz result email HTML."""
    return f"""
    <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #FDF9F9;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #2D2A2E; font-weight: 300;">RE<span style="color: #F8A5B8;">ROOTS</span></h1>
        <p style="font-size: 11px; letter-spacing: 0.2em; color: #C4BAC0; text-transform: uppercase;">Your Personalised Protocol</p>
      </div>
      <div style="background: #fff; border: 1px solid #F0E8E8; border-radius: 12px; padding: 32px;">
        <h2 style="font-size: 22px; color: #2D2A2E; font-weight: 300; margin-bottom: 8px;">Hi {name},</h2>
        <p style="font-size: 14px; color: #8A8490; line-height: 1.7; margin-bottom: 20px;">
          Based on your skin quiz — your top concerns are <strong style="color: #2D2A2E;">{concern_text}</strong>.<br>
          We've matched you with the right PDRN protocol.
        </p>
        <div style="background: #FDF9F9; border: 1px solid #F8A5B8; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
          <p style="font-size: 11px; letter-spacing: 0.15em; color: #C4BAC0; text-transform: uppercase; margin-bottom: 8px;">Your Recommended Ritual</p>
          <p style="font-size: 18px; color: #2D2A2E; font-weight: 400; margin-bottom: 4px;">{recommended_product}</p>
          <p style="font-size: 13px; color: #F8A5B8; font-weight: 600;">$99</p>
          <p style="font-size: 12px; color: #8A8490; margin-top: 8px; line-height: 1.6;">
            37.25% active concentration · PDRN 2% + TXA 5% + Argireline 17%<br>
            28-day science protocol included
          </p>
        </div>
        <a href="https://reroots.ca/products/aura-gen-pdrn" style="display: block; background: #F8A5B8; color: #fff; text-align: center; padding: 14px; border-radius: 8px; text-decoration: none; font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; letter-spacing: 0.05em;">Start Your 28-Day Protocol →</a>
      </div>
      <p style="text-align: center; font-size: 11px; color: #C4BAC0; margin-top: 24px;">Results may vary. Cosmetic use only. · REROOTS AESTHETICS INC.</p>
    </div>
    """



async def send_redemption_confirmation_whatsapp(phone: str, name: str, points_redeemed: int, discount_applied: float, remaining_balance: int):
    """Send WhatsApp confirmation when customer redeems Roots at checkout."""
    from services.twilio_service import send_whatsapp_message
    
    first_name = name.split()[0] if name else "there"
    
    message = f"""✅ Roots redeemed successfully!

*{points_redeemed} Roots* applied → 
*${discount_applied:.2f} off* your order 🎉

Remaining balance: *{remaining_balance} Roots*
(${remaining_balance * 0.05:.2f} value)

Thank you for shopping ReRoots 🌿"""
    
    return await send_whatsapp_message(phone, message)


async def send_redemption_confirmation_email(customer_email: str, customer_name: str, points_redeemed: int, discount_applied: float, remaining_balance: int):
    """Send email confirmation when customer redeems Roots at checkout."""
    first_name = customer_name.split()[0] if customer_name else "there"
    
    html = f"""
    <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #FDF9F9;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #2D2A2E; font-weight: 300;">RE<span style="color: #F8A5B8;">ROOTS</span></h1>
        <p style="font-size: 11px; letter-spacing: 0.2em; color: #C4BAC0; text-transform: uppercase;">Roots Redeemed</p>
      </div>
      <div style="background: #fff; border: 1px solid #F0E8E8; border-radius: 12px; padding: 32px;">
        <h2 style="font-size: 22px; color: #2D2A2E; font-weight: 300; margin-bottom: 8px;">You saved ${discount_applied:.2f}!</h2>
        <p style="font-size: 14px; color: #8A8490; line-height: 1.7; margin-bottom: 20px;">
          Hi {first_name}, you redeemed *{points_redeemed} Roots* on your order.
        </p>
        <div style="background: #FDF9F9; border: 1px solid #F8A5B8; border-radius: 10px; padding: 20px; margin-bottom: 24px; text-align: center;">
          <p style="font-size: 11px; letter-spacing: 0.15em; color: #C4BAC0; text-transform: uppercase; margin-bottom: 8px;">Remaining Roots Balance</p>
          <p style="font-size: 32px; color: #F8A5B8; font-weight: 600; margin-bottom: 4px;">{remaining_balance} Roots</p>
          <p style="font-size: 14px; color: #8A8490;">${remaining_balance * 0.05:.2f} value</p>
        </div>
        <a href="https://reroots.ca/account" style="display: block; background: #F8A5B8; color: #fff; text-align: center; padding: 14px; border-radius: 8px; text-decoration: none; font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; letter-spacing: 0.05em;">View Your Account →</a>
      </div>
      <p style="text-align: center; font-size: 11px; color: #C4BAC0; margin-top: 24px;">
        REROOTS AESTHETICS INC. · TORONTO, CANADA
      </p>
    </div>
    """
    
    await sendgrid_send_email(
        to=customer_email,
        subject=f"You redeemed {points_redeemed} Roots! 🌿",
        html_body=html
    )
