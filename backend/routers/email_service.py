"""
Central Email Service - All emails via Resend
Dark theme: #060608 background, #C9A86E gold accents, Georgia serif
"""
import os
import logging
import resend
from datetime import datetime, timezone
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Initialize Resend
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

FROM_EMAIL = "ReRoots <hello@reroots.ca>"
ADMIN_EMAIL = "tj@reroots.ca"

# ═══════════════════════════════════════════════════════════════════════════════
# BASE TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

def base_template(title: str, content: str, cta_text: str = None, cta_link: str = None) -> str:
    """Wrap content in branded dark theme template"""
    cta_block = ""
    if cta_text and cta_link:
        cta_block = f'''
        <div style="text-align:center;margin:28px 0;">
            <a href="{cta_link}" 
               style="background:#C9A86E;color:#060608;padding:14px 32px;
                      text-decoration:none;border-radius:4px;display:inline-block;
                      font-family:sans-serif;font-size:12px;letter-spacing:0.12em;
                      font-weight:600;">
                {cta_text}
            </a>
        </div>
        '''
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body style="margin:0;padding:0;background:#060608;">
        <div style="max-width:560px;margin:0 auto;padding:40px 20px;font-family:Georgia,serif;">
            <!-- Header -->
            <div style="text-align:center;margin-bottom:32px;padding-bottom:24px;border-bottom:1px solid rgba(201,168,110,0.15);">
                <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.3em;color:#8A6B38;margin:0 0 8px;text-transform:uppercase;">
                    Biotech Skincare Canada
                </p>
                <h1 style="font-size:32px;font-weight:300;color:#C9A86E;margin:0;letter-spacing:0.04em;">
                    ReRoots
                </h1>
            </div>
            
            <!-- Title -->
            <h2 style="font-size:24px;font-weight:300;color:#F0EBE0;margin:0 0 24px;line-height:1.3;">
                {title}
            </h2>
            
            <!-- Content -->
            <div style="color:#A89880;font-size:15px;line-height:1.8;">
                {content}
            </div>
            
            {cta_block}
            
            <!-- Footer -->
            <div style="margin-top:40px;padding-top:24px;border-top:1px solid rgba(255,255,255,0.05);text-align:center;">
                <p style="font-family:sans-serif;font-size:10px;color:#524D45;letter-spacing:0.08em;margin:0 0 6px;">
                    reroots.ca · Canadian Biotech Skincare
                </p>
                <p style="font-family:sans-serif;font-size:9px;color:#3a3530;margin:0;">
                    <a href="https://reroots.ca/unsubscribe" style="color:#5C5548;text-decoration:underline;">
                        Unsubscribe
                    </a>
                </p>
            </div>
        </div>
    </body>
    </html>
    '''


def send_email(to: str, subject: str, html: str) -> bool:
    """Send email via Resend"""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set - email not sent")
        return False
    try:
        result = resend.Emails.send({
            "from": FROM_EMAIL,
            "to": to,
            "subject": subject,
            "html": html
        })
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 1. WELCOME EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

def send_welcome_email(email: str, name: str, tier: str = "Silver", points: int = 0):
    """Send welcome email after signup"""
    content = f'''
    <p style="margin-bottom:16px;">Hi {name},</p>
    <p style="margin-bottom:16px;">Welcome to the ReRoots family! We're thrilled to have you join our community of skincare enthusiasts.</p>
    <div style="background:#0d0d10;border:1px solid rgba(201,168,110,0.15);border-radius:8px;padding:20px;margin:24px 0;">
        <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.15em;color:#8A6B38;margin:0 0 8px;text-transform:uppercase;">Your Membership</p>
        <p style="font-size:22px;color:#C9A86E;margin:0 0 4px;">{tier} Tier</p>
        <p style="font-size:14px;color:#A89880;margin:0;">{points} loyalty points to start</p>
    </div>
    <p>Explore our biotech skincare collection and start your journey to healthier skin.</p>
    '''
    html = base_template("Welcome to ReRoots", content, "START SHOPPING", "https://reroots.ca/app")
    return send_email(email, "Welcome to ReRoots — Your Skin Journey Begins", html)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ORDER CONFIRMATION
# ═══════════════════════════════════════════════════════════════════════════════

def send_order_confirmation(email: str, name: str, order_id: str, items: List[Dict], total: float, estimated_delivery: str = "3-5 business days"):
    """Send order confirmation email"""
    items_html = ""
    for item in items:
        items_html += f'''
        <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
            <span style="color:#F0EBE0;">{item.get("name", "Product")} x{item.get("quantity", 1)}</span>
            <span style="color:#C9A86E;">${item.get("price", 0):.2f}</span>
        </div>
        '''
    
    content = f'''
    <p style="margin-bottom:16px;">Hi {name},</p>
    <p style="margin-bottom:24px;">Thank you for your order! We're preparing your biotech skincare products with care.</p>
    
    <div style="background:#0d0d10;border:1px solid rgba(201,168,110,0.15);border-radius:8px;padding:20px;margin:24px 0;">
        <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.15em;color:#8A6B38;margin:0 0 12px;text-transform:uppercase;">Order #{order_id}</p>
        {items_html}
        <div style="display:flex;justify-content:space-between;padding:16px 0 0;margin-top:12px;border-top:1px solid rgba(201,168,110,0.2);">
            <span style="font-size:16px;color:#F0EBE0;">Total</span>
            <span style="font-size:18px;color:#C9A86E;font-weight:600;">${total:.2f} CAD</span>
        </div>
    </div>
    
    <p style="color:#A89880;">Estimated delivery: <span style="color:#C9A86E;">{estimated_delivery}</span></p>
    '''
    html = base_template("Order Confirmed", content, "TRACK ORDER", f"https://reroots.ca/track?order={order_id}")
    return send_email(email, f"Order Confirmed — #{order_id}", html)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SHIPPING CONFIRMATION
# ═══════════════════════════════════════════════════════════════════════════════

def send_shipping_confirmation(email: str, name: str, order_id: str, tracking_number: str, carrier: str = "FlagShip", estimated_arrival: str = "2-3 business days"):
    """Send shipping confirmation with tracking"""
    tracking_link = f"https://www.flagshipcompany.com/tracking/{tracking_number}"
    
    content = f'''
    <p style="margin-bottom:16px;">Hi {name},</p>
    <p style="margin-bottom:24px;">Great news! Your order is on its way.</p>
    
    <div style="background:#0d0d10;border:1px solid rgba(201,168,110,0.15);border-radius:8px;padding:20px;margin:24px 0;">
        <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.15em;color:#8A6B38;margin:0 0 12px;text-transform:uppercase;">Shipment Details</p>
        <p style="color:#A89880;margin:8px 0;">Order: <span style="color:#F0EBE0;">#{order_id}</span></p>
        <p style="color:#A89880;margin:8px 0;">Carrier: <span style="color:#F0EBE0;">{carrier}</span></p>
        <p style="color:#A89880;margin:8px 0;">Tracking: <span style="color:#C9A86E;">{tracking_number}</span></p>
        <p style="color:#A89880;margin:8px 0;">Est. Arrival: <span style="color:#C9A86E;">{estimated_arrival}</span></p>
    </div>
    '''
    html = base_template("Your Order Has Shipped", content, "TRACK PACKAGE", tracking_link)
    return send_email(email, f"Your ReRoots Order Has Shipped — #{order_id}", html)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. BIRTHDAY EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

def send_birthday_email(email: str, name: str, bonus_points: int = 500):
    """Send birthday email with bonus points"""
    content = f'''
    <p style="margin-bottom:16px;">Happy Birthday, {name}!</p>
    <p style="margin-bottom:24px;">We hope your special day is filled with joy. To celebrate, we've added a special gift to your account.</p>
    
    <div style="background:linear-gradient(135deg,#1a1408,#0d0d10);border:1px solid rgba(201,168,110,0.3);border-radius:12px;padding:28px;margin:24px 0;text-align:center;">
        <p style="font-family:sans-serif;font-size:11px;letter-spacing:0.2em;color:#8A6B38;margin:0 0 8px;text-transform:uppercase;">Birthday Bonus</p>
        <p style="font-size:42px;color:#C9A86E;margin:0;font-weight:300;">{bonus_points}</p>
        <p style="font-size:14px;color:#A89880;margin:4px 0 0;">loyalty points added</p>
    </div>
    
    <p>Use your points on your next purchase and treat yourself to something special.</p>
    '''
    html = base_template("Happy Birthday!", content, "REDEEM POINTS", "https://reroots.ca/app")
    return send_email(email, f"Happy Birthday, {name}! A Gift Awaits", html)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TIER UPGRADE EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

TIER_PERKS = {
    "Gold": ["2x points on all purchases", "Early access to new products", "Free shipping on orders $50+"],
    "Diamond": ["3x points on all purchases", "Exclusive member-only products", "Free shipping on all orders", "Birthday double points"],
    "Elite": ["5x points on all purchases", "VIP concierge support", "Free expedited shipping", "Exclusive events access", "Complimentary gifts"]
}

def send_tier_upgrade_email(email: str, name: str, new_tier: str, current_points: int):
    """Send tier upgrade congratulations"""
    perks = TIER_PERKS.get(new_tier, [])
    perks_html = "".join([f'<li style="margin:8px 0;color:#A89880;">{perk}</li>' for perk in perks])
    
    content = f'''
    <p style="margin-bottom:16px;">Congratulations, {name}!</p>
    <p style="margin-bottom:24px;">Your dedication to skincare has paid off. You've been upgraded to a new tier!</p>
    
    <div style="background:linear-gradient(135deg,#1a1408,#0d0d10);border:1px solid rgba(201,168,110,0.3);border-radius:12px;padding:28px;margin:24px 0;text-align:center;">
        <p style="font-family:sans-serif;font-size:11px;letter-spacing:0.2em;color:#8A6B38;margin:0 0 8px;text-transform:uppercase;">New Status</p>
        <p style="font-size:36px;color:#C9A86E;margin:0;font-weight:300;">{new_tier}</p>
        <p style="font-size:14px;color:#A89880;margin:8px 0 0;">{current_points:,} points</p>
    </div>
    
    <p style="color:#F0EBE0;margin-bottom:12px;">Your new perks:</p>
    <ul style="padding-left:20px;margin:0;">
        {perks_html}
    </ul>
    '''
    html = base_template(f"You're Now {new_tier}!", content, "EXPLORE PERKS", "https://reroots.ca/app")
    return send_email(email, f"Congratulations! You've Reached {new_tier} Status", html)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ABANDONED CART EMAILS (3-sequence)
# ═══════════════════════════════════════════════════════════════════════════════

def send_abandoned_cart_reminder(email: str, name: str, cart_items: List[Dict], sequence: int = 1, discount_code: str = None):
    """
    Send abandoned cart recovery email
    sequence: 1=24hr gentle, 2=48hr discount, 3=72hr urgency
    """
    items_html = ""
    total = 0
    for item in cart_items:
        price = item.get("price", 0) * item.get("quantity", 1)
        total += price
        items_html += f'''
        <div style="display:flex;align-items:center;padding:12px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
            <div style="flex:1;">
                <p style="color:#F0EBE0;margin:0;">{item.get("name", "Product")}</p>
                <p style="color:#A89880;font-size:13px;margin:4px 0 0;">Qty: {item.get("quantity", 1)}</p>
            </div>
            <span style="color:#C9A86E;">${price:.2f}</span>
        </div>
        '''
    
    if sequence == 1:
        # 24hr - Gentle reminder
        subject = "You left something behind..."
        title = "Still Thinking It Over?"
        intro = f"Hi {name}, we noticed you left some items in your cart. They're waiting for you!"
        urgency = ""
        discount_block = ""
        
    elif sequence == 2:
        # 48hr - Discount offer
        subject = "10% off your cart — just for you"
        title = "Here's a Little Incentive"
        intro = f"Hi {name}, we'd love to see you complete your order. Use this exclusive code for 10% off:"
        urgency = ""
        discount_block = f'''
        <div style="background:#1a1408;border:1px solid #C9A86E;border-radius:8px;padding:16px;margin:20px 0;text-align:center;">
            <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.2em;color:#8A6B38;margin:0 0 6px;text-transform:uppercase;">Your Code</p>
            <p style="font-size:24px;color:#C9A86E;letter-spacing:0.1em;margin:0;">{discount_code or "COMEBACK10"}</p>
        </div>
        '''
        
    else:
        # 72hr - Last chance
        subject = "Last chance — your cart is expiring"
        title = "Don't Miss Out"
        intro = f"Hi {name}, this is your final reminder. Your cart items may sell out soon!"
        urgency = '<p style="color:#E57373;font-size:13px;margin-top:16px;">⚠️ Low stock warning — some items may not be available much longer.</p>'
        discount_block = f'''
        <div style="background:#1a1408;border:1px solid #C9A86E;border-radius:8px;padding:16px;margin:20px 0;text-align:center;">
            <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.2em;color:#8A6B38;margin:0 0 6px;text-transform:uppercase;">Still Valid</p>
            <p style="font-size:24px;color:#C9A86E;letter-spacing:0.1em;margin:0;">{discount_code or "COMEBACK10"}</p>
        </div>
        ''' if discount_code else ''
    
    content = f'''
    <p style="margin-bottom:16px;">{intro}</p>
    
    {discount_block}
    
    <div style="background:#0d0d10;border:1px solid rgba(201,168,110,0.15);border-radius:8px;padding:20px;margin:24px 0;">
        <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.15em;color:#8A6B38;margin:0 0 12px;text-transform:uppercase;">Your Cart</p>
        {items_html}
        <div style="display:flex;justify-content:space-between;padding:16px 0 0;margin-top:12px;border-top:1px solid rgba(201,168,110,0.2);">
            <span style="font-size:16px;color:#F0EBE0;">Total</span>
            <span style="font-size:18px;color:#C9A86E;font-weight:600;">${total:.2f} CAD</span>
        </div>
    </div>
    {urgency}
    '''
    html = base_template(title, content, "COMPLETE PURCHASE", "https://reroots.ca/cart")
    return send_email(email, subject, html)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. DAILY SALES DIGEST (Admin)
# ═══════════════════════════════════════════════════════════════════════════════

def send_daily_sales_digest(orders_today: int, revenue_today: float, new_signups: int, low_stock_items: List[Dict]):
    """Send daily sales digest to admin"""
    low_stock_html = ""
    if low_stock_items:
        low_stock_html = '<p style="color:#E57373;font-size:13px;margin-top:20px;font-weight:600;">⚠️ Low Stock Alert:</p><ul style="padding-left:20px;">'
        for item in low_stock_items[:5]:
            low_stock_html += f'<li style="color:#A89880;margin:4px 0;">{item.get("name")} — {item.get("stock")} left</li>'
        low_stock_html += '</ul>'
    
    content = f'''
    <p style="margin-bottom:24px;">Here's your daily business snapshot for {datetime.now(timezone.utc).strftime("%B %d, %Y")}.</p>
    
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0;">
        <div style="background:#0d0d10;border:1px solid rgba(201,168,110,0.15);border-radius:8px;padding:20px;text-align:center;">
            <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.15em;color:#8A6B38;margin:0 0 8px;text-transform:uppercase;">Orders</p>
            <p style="font-size:32px;color:#C9A86E;margin:0;">{orders_today}</p>
        </div>
        <div style="background:#0d0d10;border:1px solid rgba(201,168,110,0.15);border-radius:8px;padding:20px;text-align:center;">
            <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.15em;color:#8A6B38;margin:0 0 8px;text-transform:uppercase;">Revenue</p>
            <p style="font-size:32px;color:#C9A86E;margin:0;">${revenue_today:,.2f}</p>
        </div>
    </div>
    
    <div style="background:#0d0d10;border:1px solid rgba(201,168,110,0.15);border-radius:8px;padding:20px;text-align:center;margin-bottom:20px;">
        <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.15em;color:#8A6B38;margin:0 0 8px;text-transform:uppercase;">New Signups</p>
        <p style="font-size:32px;color:#C9A86E;margin:0;">{new_signups}</p>
    </div>
    
    {low_stock_html}
    '''
    html = base_template("Daily Sales Digest", content, "VIEW DASHBOARD", "https://reroots.ca/new-admin")
    return send_email(ADMIN_EMAIL, f"Daily Digest — {orders_today} orders, ${revenue_today:,.2f} revenue", html)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. LOW STOCK ALERT (Admin)
# ═══════════════════════════════════════════════════════════════════════════════

def send_low_stock_alert(product_name: str, sku: str, current_stock: int, reorder_point: int):
    """Send immediate low stock alert to admin"""
    content = f'''
    <p style="margin-bottom:24px;">A product has fallen below the reorder threshold and needs attention.</p>
    
    <div style="background:#0d0d10;border:1px solid rgba(227,115,115,0.3);border-radius:8px;padding:20px;margin:24px 0;">
        <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.15em;color:#E57373;margin:0 0 12px;text-transform:uppercase;">⚠️ Low Stock Warning</p>
        <p style="color:#F0EBE0;font-size:18px;margin:0 0 12px;">{product_name}</p>
        <p style="color:#A89880;margin:4px 0;">SKU: <span style="color:#F0EBE0;">{sku}</span></p>
        <p style="color:#A89880;margin:4px 0;">Current Stock: <span style="color:#E57373;font-weight:600;">{current_stock}</span></p>
        <p style="color:#A89880;margin:4px 0;">Reorder Point: <span style="color:#C9A86E;">{reorder_point}</span></p>
    </div>
    
    <p>Please restock this item as soon as possible to avoid stockouts.</p>
    '''
    html = base_template("Low Stock Alert", content, "MANAGE INVENTORY", "https://reroots.ca/new-admin?tab=products")
    return send_email(ADMIN_EMAIL, f"⚠️ Low Stock: {product_name} ({current_stock} left)", html)


# ═══════════════════════════════════════════════════════════════════════════════
# PASSWORD RESET (already implemented, included for completeness)
# ═══════════════════════════════════════════════════════════════════════════════

def send_password_reset_email(email: str, name: str, reset_link: str):
    """Send password reset email"""
    content = f'''
    <p style="margin-bottom:16px;">Hi {name},</p>
    <p style="margin-bottom:24px;">Click below to reset your password. This link expires in 1 hour.</p>
    '''
    html = base_template("Password Reset", content, "RESET PASSWORD", reset_link)
    return send_email(email, "Reset your ReRoots password", html)
