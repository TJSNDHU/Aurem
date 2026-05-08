"""
AUREM Platform — Email Notification System
HTML email template generators and notification functions.
Extracted from server.py during modularization.
"""

import os
import re
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

# ============= MODULE GLOBALS (Wired by server.py at startup) =============
# DB handle and Twilio client are injected via set_db()/set_twilio_client()
# from server.py during application boot. Until then they remain None and
# the email/SMS functions short-circuit cleanly.
db = None  # AsyncIOMotorDatabase, set via set_db()
twilio_client = None  # twilio.rest.Client, set via set_twilio_client()

# Configuration (read from environment so missing config fails fast)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
JWT_SECRET = os.environ.get("JWT_SECRET")

# Optional third-party SDKs — imported lazily so the module stays import-safe
# even when these packages are not installed (CI / partial deployments).
try:
    import resend  # type: ignore
    if RESEND_API_KEY:
        resend.api_key = RESEND_API_KEY
except Exception:  # pragma: no cover
    resend = None  # type: ignore


def set_db(database) -> None:
    """Inject the Motor database handle from server.py startup."""
    global db
    db = database


def set_twilio_client(client) -> None:
    """Inject the Twilio REST client from server.py startup."""
    global twilio_client
    twilio_client = client

# ============= EMAIL NOTIFICATION SYSTEM =============


def get_email_base_styles():
    """Base CSS styles for all email templates — used by external template renderers."""
    return """
        body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2D2A2E; margin: 0; padding: 0; background-color: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: #ffffff; }
        .header { background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center; }
        .logo { font-size: 32px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px; }
        .content { padding: 40px 30px; }
        .highlight-box { background: linear-gradient(135deg, #FFF5F7 0%, #FFF8E7 100%); border-radius: 12px; padding: 25px; margin: 20px 0; border-left: 4px solid #F8A5B8; }
        .button { display: inline-block; background: linear-gradient(135deg, #F8A5B8 0%, #FFB6C1 100%); color: #2D2A2E; padding: 15px 35px; text-decoration: none; border-radius: 30px; font-weight: bold; }
        .footer { background: #2D2A2E; color: #ffffff; padding: 30px; text-align: center; }
        .footer a { color: #F8A5B8; text-decoration: none; }
    """


def _email_wrap(title: str, content_html: str, store_name: str = "ReRoots", support_email: str = "support@reroots.ca") -> str:
    """Shared email wrapper: DOCTYPE + header + content + footer."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{title}</title></head>
<body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2D2A2E; margin: 0; padding: 0; background-color: #f5f5f5;">
<table cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f5f5;"><tr><td align="center" style="padding: 20px;">
<table cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
<tr><td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
<div style="font-size: 32px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
<div style="color: #D4AF37; font-size: 12px; letter-spacing: 3px; margin-top: 5px;">BEAUTY ENHANCER</div></td></tr>
<tr><td style="padding: 40px 30px;">{content_html}</td></tr>
<tr><td style="background: #2D2A2E; color: #ffffff; padding: 30px; text-align: center;">
<p style="margin: 0 0 10px 0; font-size: 14px;">Questions? Contact us at <a href="mailto:{support_email}" style="color: #F8A5B8; text-decoration: none;">{support_email}</a></p>
<p style="margin: 0; font-size: 12px; color: #888;">&copy; 2025 {store_name}. All rights reserved.</p></td></tr>
</table></td></tr></table></body></html>"""


def generate_order_confirmation_email(order: dict, store_settings: dict = None) -> str:
    """Generate HTML email for order confirmation"""
    store_name = (
        store_settings.get("store_name", "ReRoots") if store_settings else "ReRoots"
    )
    support_email = (
        store_settings.get("support_email", "support@reroots.ca")
        if store_settings
        else "support@reroots.ca"
    )

    # Build items HTML with ENGINE/BUFFER badges for combo products
    items_html = ""
    combo_detected = False
    for idx, item in enumerate(order.get("items", [])):
        product_image = item.get("product_image", "https://via.placeholder.com/80")
        product_name = item.get('product_name', 'Product')
        
        # Detect if this is a combo purchase (2+ items with related names)
        is_first_in_pair = idx == 0 and len(order.get("items", [])) >= 2
        is_second_in_pair = idx == 1 and len(order.get("items", [])) >= 2
        
        # Add ENGINE/BUFFER badge based on position in order
        protocol_badge = ""
        if len(order.get("items", [])) == 2:
            combo_detected = True
            if is_first_in_pair:
                protocol_badge = '<div style="display: inline-block; background: #9333EA; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; margin-top: 5px;">STEP 1 • ENGINE</div>'
            elif is_second_in_pair:
                protocol_badge = '<div style="display: inline-block; background: #EC4899; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; margin-top: 5px;">STEP 2 • BUFFER</div>'
        
        items_html += f"""
        <tr>
            <td style="padding: 15px 0; border-bottom: 1px solid #f0f0f0;">
                <table cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                        <td width="80" style="vertical-align: top;">
                            <img src="{product_image}" width="70" height="70" style="border-radius: 8px; object-fit: cover;" alt="{product_name}">
                        </td>
                        <td style="vertical-align: top; padding-left: 15px;">
                            <div style="font-weight: 600; color: #2D2A2E; margin-bottom: 5px;">{product_name}</div>
                            <div style="color: #666; font-size: 14px;">Qty: {item.get('quantity', 1)}</div>
                            {protocol_badge}
                            {"<div style='color: #7B1FA2; font-size: 12px; margin-top: 5px;'>📦 Pre-Order Item</div>" if item.get('is_preorder') else ""}
                        </td>
                        <td style="text-align: right; vertical-align: top; font-weight: 600; color: #F8A5B8;">
                            ${item.get('price', 0) * item.get('quantity', 1):.2f} CAD
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        """
    
    # Add 60-second protocol reminder for combo orders
    protocol_reminder = ""
    if combo_detected:
        protocol_reminder = """
        <div style="background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%); border-radius: 12px; padding: 20px; margin: 25px 0; border-left: 4px solid #F59E0B;">
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 24px; margin-right: 10px;">⏱️</span>
                <span style="font-weight: bold; color: #92400E; font-size: 18px;">60-Second Protocol</span>
            </div>
            <p style="color: #78350F; font-size: 14px; margin: 0;">
                For optimal results: Apply <strong>Step 1 (ENGINE)</strong>, wait <strong>60 seconds</strong> for the DMI "molecular taxi" to clear pathways, then apply <strong>Step 2 (BUFFER)</strong> while skin is still damp.
            </p>
            <p style="color: #92400E; font-size: 13px; margin-top: 10px;">
                🌅 Morning routine: Always finish with SPF 30+ sunscreen.
            </p>
        </div>
        """

    # Shipping address
    addr = order.get("shipping_address", {})
    address_html = f"""
        {addr.get('first_name', '')} {addr.get('last_name', '')}<br>
        {addr.get('address', '')}<br>
        {f"{addr.get('apartment')}<br>" if addr.get('apartment') else ""}
        {addr.get('city', '')}, {addr.get('province', '')} {addr.get('postal_code', '')}<br>
        {addr.get('country', 'Canada')}
    """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Order Confirmation - {store_name}</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2D2A2E; margin: 0; padding: 0; background-color: #f5f5f5;">
        <table cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f5f5;">
            <tr>
                <td align="center" style="padding: 20px;">
                    <table cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
                                <div style="font-size: 32px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
                                <div style="color: #D4AF37; font-size: 12px; letter-spacing: 3px; margin-top: 5px;">BEAUTY ENHANCER</div>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <!-- Success Icon -->
                                <div style="text-align: center; margin-bottom: 30px;">
                                    <div style="display: inline-block; width: 70px; height: 70px; background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%); border-radius: 50%; line-height: 70px; font-size: 36px;">✓</div>
                                </div>
                                
                                <h1 style="text-align: center; color: #2D2A2E; margin: 0 0 10px 0; font-size: 28px;">Thank You for Your Order!</h1>
                                <p style="text-align: center; color: #666; margin: 0 0 30px 0;">We're preparing your skincare essentials with love.</p>
                                
                                <!-- Order Number Box -->
                                <div style="background: linear-gradient(135deg, #FFF5F7 0%, #FFF8E7 100%); border-radius: 12px; padding: 25px; margin: 20px 0; border-left: 4px solid #F8A5B8; text-align: center;">
                                    <div style="font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px;">Order Number</div>
                                    <div style="font-size: 28px; font-weight: bold; color: #2D2A2E; margin: 10px 0;">{order.get('order_number', 'N/A')}</div>
                                    <span style="display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: bold; font-size: 14px; background: #E8F5E9; color: #2E7D32;">Order Confirmed</span>
                                </div>
                                
                                <!-- Order Items -->
                                <h3 style="color: #2D2A2E; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; margin-top: 30px;">Order Details</h3>
                                <table cellpadding="0" cellspacing="0" width="100%">
                                    {items_html}
                                </table>
                                
                                <!-- 60-Second Protocol Reminder (for combo orders) -->
                                {protocol_reminder}
                                
                                <!-- Order Summary -->
                                <div style="margin-top: 20px; padding: 20px; background: #f9f9f9; border-radius: 8px;">
                                    <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                                        <span style="color: #666;">Subtotal</span>
                                        <span style="font-weight: 600;">${order.get('subtotal', 0):.2f} CAD</span>
                                    </div>
                                    <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                                        <span style="color: #666;">Shipping</span>
                                        <span style="font-weight: 600;">${order.get('shipping', 0):.2f} CAD</span>
                                    </div>
                                    <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                                        <span style="color: #666;">Tax</span>
                                        <span style="font-weight: 600;">${order.get('tax', 0):.2f} CAD</span>
                                    </div>
                                    <div style="display: flex; justify-content: space-between; padding: 15px 0; margin-top: 10px; border-top: 2px solid #2D2A2E; font-size: 18px;">
                                        <span style="font-weight: bold;">Total</span>
                                        <span style="font-weight: bold; color: #F8A5B8;">${order.get('total', 0):.2f} CAD</span>
                                    </div>
                                </div>
                                
                                <!-- Shipping Address -->
                                <div style="margin-top: 30px;">
                                    <h3 style="color: #2D2A2E; margin-bottom: 15px;">Shipping Address</h3>
                                    <div style="background: #f9f9f9; border-radius: 8px; padding: 20px;">
                                        {address_html}
                                    </div>
                                </div>
                                
                                <!-- CTA Button -->
                                <div style="text-align: center; margin-top: 30px;">
                                    <a href="#" style="display: inline-block; background: linear-gradient(135deg, #F8A5B8 0%, #FFB6C1 100%); color: #2D2A2E; padding: 15px 35px; text-decoration: none; border-radius: 30px; font-weight: bold; box-shadow: 0 4px 15px rgba(248, 165, 184, 0.4);">View Order Status</a>
                                </div>
                                
                                <p style="text-align: center; color: #666; margin-top: 30px; font-size: 14px;">
                                    You'll receive a shipping confirmation email once your order is on its way!
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background: #2D2A2E; color: #ffffff; padding: 30px; text-align: center;">
                                <p style="margin: 0 0 10px 0; font-size: 14px;">Questions? Contact us at <a href="mailto:{support_email}" style="color: #F8A5B8; text-decoration: none;">{support_email}</a></p>
                                <p style="margin: 0; font-size: 12px; color: #888;">© 2025 {store_name}. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html


def generate_shipping_update_email(
    order: dict, tracking_status: str, store_settings: dict = None
) -> str:
    """Generate HTML email for shipping updates"""
    store_name = (
        store_settings.get("store_name", "ReRoots") if store_settings else "ReRoots"
    )
    support_email = (
        store_settings.get("support_email", "support@reroots.ca")
        if store_settings
        else "support@reroots.ca"
    )

    # Status messages and badges
    status_config = {
        "shipped": {
            "title": "Your Order Has Shipped! 📦",
            "message": "Great news! Your skincare essentials are on their way.",
            "badge_bg": "#E3F2FD",
            "badge_color": "#1565C0",
            "icon": "🚚",
        },
        "in_transit": {
            "title": "Your Order is On Its Way! 🚛",
            "message": "Your package is traveling to you. It won't be long now!",
            "badge_bg": "#FFF3E0",
            "badge_color": "#E65100",
            "icon": "📍",
        },
        "out_for_delivery": {
            "title": "Out for Delivery Today! 🎉",
            "message": "Your order is out for delivery and will arrive today!",
            "badge_bg": "#E8F5E9",
            "badge_color": "#2E7D32",
            "icon": "🏃",
        },
        "delivered": {
            "title": "Your Order Has Been Delivered! ✨",
            "message": "Your skincare products have arrived. Enjoy your glow!",
            "badge_bg": "#F3E5F5",
            "badge_color": "#7B1FA2",
            "icon": "🎁",
        },
    }

    config = status_config.get(tracking_status, status_config["shipped"])

    # Build tracking URL button
    tracking_url = order.get("tracking_url", "")
    tracking_button = ""
    if tracking_url:
        tracking_button = f"""
            <div style="text-align: center; margin: 20px 0;">
                <a href="{tracking_url}" style="display: inline-block; background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); color: #ffffff; padding: 15px 35px; text-decoration: none; border-radius: 30px; font-weight: bold;">Track Your Package</a>
            </div>
        """

    # Courier info
    courier_name = order.get("courier", "").upper() or "Carrier"
    tracking_number = order.get("tracking_number", "")
    estimated_delivery = order.get("estimated_delivery", "")

    # Build timeline
    timeline_html = ""
    updates = order.get("tracking_updates", [])
    for update in updates[-5:]:  # Last 5 updates
        timeline_html += f"""
            <div style="display: flex; margin-bottom: 15px;">
                <div style="width: 10px; height: 10px; border-radius: 50%; background: #F8A5B8; margin-right: 15px; margin-top: 5px;"></div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; color: #2D2A2E;">{update.get('description', update.get('status', 'Update'))}</div>
                    <div style="font-size: 12px; color: #888;">{update.get('location', '')} • {update.get('timestamp', '')[:10] if update.get('timestamp') else ''}</div>
                </div>
            </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Shipping Update - {store_name}</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2D2A2E; margin: 0; padding: 0; background-color: #f5f5f5;">
        <table cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f5f5;">
            <tr>
                <td align="center" style="padding: 20px;">
                    <table cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
                                <div style="font-size: 32px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
                                <div style="color: #D4AF37; font-size: 12px; letter-spacing: 3px; margin-top: 5px;">BEAUTY ENHANCER</div>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <!-- Status Icon -->
                                <div style="text-align: center; margin-bottom: 30px;">
                                    <div style="font-size: 60px;">{config['icon']}</div>
                                </div>
                                
                                <h1 style="text-align: center; color: #2D2A2E; margin: 0 0 10px 0; font-size: 24px;">{config['title']}</h1>
                                <p style="text-align: center; color: #666; margin: 0 0 30px 0;">{config['message']}</p>
                                
                                <!-- Order & Tracking Box -->
                                <div style="background: linear-gradient(135deg, #E3F2FD 0%, #E8F5E9 100%); border-radius: 12px; padding: 25px; margin: 20px 0; text-align: center;">
                                    <div style="font-size: 14px; color: #666; margin-bottom: 5px;">Order {order.get('order_number', '')}</div>
                                    <div style="font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-top: 15px;">Tracking Number</div>
                                    <div style="font-size: 18px; font-weight: bold; color: #1565C0; letter-spacing: 2px; margin: 5px 0;">{tracking_number or 'Pending'}</div>
                                    <div style="margin-top: 10px;">
                                        <span style="display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: bold; font-size: 14px; background: {config['badge_bg']}; color: {config['badge_color']};">{courier_name} • {tracking_status.replace('_', ' ').title()}</span>
                                    </div>
                                    {f'<div style="margin-top: 15px; font-size: 14px; color: #666;">📅 Estimated Delivery: <strong>{estimated_delivery}</strong></div>' if estimated_delivery else ''}
                                </div>
                                
                                {tracking_button}
                                
                                <!-- Timeline -->
                                {f'''
                                <div style="margin: 30px 0;">
                                    <h3 style="color: #2D2A2E; margin-bottom: 20px;">Tracking Updates</h3>
                                    {timeline_html}
                                </div>
                                ''' if timeline_html else ''}
                                
                                <p style="text-align: center; color: #666; margin-top: 30px; font-size: 14px;">
                                    Need help? Reply to this email or contact our support team.
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background: #2D2A2E; color: #ffffff; padding: 30px; text-align: center;">
                                <p style="margin: 0 0 10px 0; font-size: 14px;">Questions? Contact us at <a href="mailto:{support_email}" style="color: #F8A5B8; text-decoration: none;">{support_email}</a></p>
                                <p style="margin: 0; font-size: 12px; color: #888;">© 2025 {store_name}. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html


async def send_order_confirmation_email(order: dict, customer_email: str):
    """Send order confirmation email to customer"""
    if not RESEND_API_KEY or not customer_email:
        logging.info(
            f"Order confirmation email skipped - API key or email not configured"
        )
        return False

    try:
        store_settings = await db.store_settings.find_one({}, {"_id": 0})
        html_content = generate_order_confirmation_email(order, store_settings)

        params = {
            "from": SENDER_EMAIL,
            "to": [customer_email],
            "subject": f"Order Confirmed! #{order.get('order_number', '')} - ReRoots",
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)
        logging.info(f"Order confirmation email sent to: {customer_email}")

        # Update order to mark receipt sent
        await db.orders.update_one(
            {"id": order.get("id")},
            {
                "$set": {
                    "receipt_sent": True,
                    "receipt_sent_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        return True
    except Exception as e:
        logging.error(f"Failed to send order confirmation email: {e}")
        return False


async def send_shipping_update_email(
    order: dict, customer_email: str, tracking_status: str
):
    """Send shipping update email to customer"""
    if not RESEND_API_KEY or not customer_email:
        logging.info(f"Shipping update email skipped - API key or email not configured")
        return False

    try:
        store_settings = await db.store_settings.find_one({}, {"_id": 0})
        html_content = generate_shipping_update_email(
            order, tracking_status, store_settings
        )

        # Subject based on status
        subject_map = {
            "shipped": f"Your Order Has Shipped! #{order.get('order_number', '')}",
            "in_transit": f"Your Order is On Its Way! #{order.get('order_number', '')}",
            "out_for_delivery": f"Out for Delivery Today! #{order.get('order_number', '')}",
            "delivered": f"Your Order Has Been Delivered! #{order.get('order_number', '')}",
        }
        subject = subject_map.get(
            tracking_status, f"Shipping Update - #{order.get('order_number', '')}"
        )

        params = {
            "from": SENDER_EMAIL,
            "to": [customer_email],
            "subject": subject,
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)
        logging.info(
            f"Shipping update email ({tracking_status}) sent to: {customer_email}"
        )
        return True
    except Exception as e:
        logging.error(f"Failed to send shipping update email: {e}")
        return False


async def send_shipping_sms(phone: str, name: str, order_number: str, tracking_number: str, courier: str) -> bool:
    """Send SMS notification when an order is shipped."""
    twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER")
    
    if not twilio_client:
        logging.info("Twilio not configured - SMS shipping notification skipped")
        return False
    
    if not twilio_phone:
        logging.info("TWILIO_PHONE_NUMBER not set - SMS shipping notification skipped")
        return False
    
    try:
        first_name = name.split()[0] if name else "Customer"
        message = (
            f"📦 ReRoots: Hi {first_name}! Your order #{order_number} has shipped via {courier}. "
            f"Tracking: {tracking_number}. "
            f"Track: https://www.google.com/search?q={tracking_number}+tracking"
        )
        
        # Send SMS via Twilio
        twilio_client.messages.create(
            body=message,
            from_=twilio_phone,
            to=phone if phone.startswith("+") else f"+{phone}"
        )
        logging.info(f"Shipping SMS sent to {phone[:5]}***")
        return True
    except Exception as e:
        logging.error(f"Failed to send shipping SMS: {e}")
        return False


async def send_shipping_notifications(order: dict, tracking_number: str, courier: str, tracking_url: str = None) -> dict:
    """
    Send shipping notifications via all channels: Email, SMS, WhatsApp.
    
    Args:
        order: Order document with shipping_address
        tracking_number: Tracking number from carrier
        courier: Carrier name (e.g., "Purolator")
        tracking_url: Optional tracking URL
        
    Returns:
        dict with status of each notification channel
    """
    results = {"email": False, "sms": False, "whatsapp": False}

    # Late import to avoid circular dependency with whapi_service at module load
    try:
        from services.whapi_service import normalize_phone_number, send_shipping_whatsapp
    except Exception:
        normalize_phone_number = lambda p, c="1": p  # noqa: E731
        send_shipping_whatsapp = None

    shipping_addr = order.get("shipping_address", {})
    customer_email = shipping_addr.get("email")
    customer_phone = shipping_addr.get("phone")
    customer_name = f"{shipping_addr.get('first_name', '')} {shipping_addr.get('last_name', '')}".strip()
    order_number = order.get("order_number", order.get("id", "")[:8])
    
    if not tracking_url:
        tracking_url = f"https://www.google.com/search?q={tracking_number}+tracking"
    
    # Prepare order for email template
    order["tracking_number"] = tracking_number
    order["tracking_url"] = tracking_url
    order["courier"] = courier
    order["shipping_carrier"] = courier
    
    # Send Email
    if customer_email:
        results["email"] = await send_shipping_update_email(order, customer_email, "shipped")
    
    # Send SMS
    if customer_phone:
        # Normalize phone number
        phone_normalized = normalize_phone_number(customer_phone, shipping_addr.get("phone_country_code", "1"))
        if phone_normalized:
            results["sms"] = await send_shipping_sms(
                phone_normalized, customer_name, order_number, tracking_number, courier
            )
    
    # Send WhatsApp
    if customer_phone and send_shipping_whatsapp:
        phone_normalized = normalize_phone_number(customer_phone, shipping_addr.get("phone_country_code", "1"))
        if phone_normalized:
            wa_result = await send_shipping_whatsapp(
                phone_normalized, customer_name, order_number, tracking_number, courier, tracking_url
            )
            results["whatsapp"] = wa_result.get("success", False)
    
    logging.info(f"[Shipping Notifications] Order {order_number}: Email={results['email']}, SMS={results['sms']}, WhatsApp={results['whatsapp']}")
    return results


async def deduct_inventory_for_order(order_id: str):
    """
    Deduct inventory for all items in an order after payment is confirmed.
    
    Args:
        order_id: The order ID to process inventory for
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the order
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            logging.error(f"[Inventory] Order not found: {order_id}")
            return False
        
        # Check if inventory already deducted
        if order.get("inventory_deducted"):
            logging.info(f"[Inventory] Order {order_id} inventory already deducted")
            return True
        
        items = order.get("items", [])
        if not items:
            logging.warning(f"[Inventory] Order {order_id} has no items")
            return True
        
        # Track inventory changes for WebSocket broadcast
        inventory_updates = []
        
        # Deduct stock for each item
        for item in items:
            product_id = item.get("product_id") or item.get("id")
            quantity = item.get("quantity", 1)
            
            if not product_id:
                logging.warning(f"[Inventory] Item missing product_id in order {order_id}")
                continue
            
            # Find the product and deduct stock
            result = await db.products.update_one(
                {"id": product_id, "stock": {"$gte": quantity}},
                {"$inc": {"stock": -quantity}}
            )
            
            # Get updated product stock
            product = await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "name": 1, "stock": 1})
            
            if result.modified_count > 0:
                logging.info(f"[Inventory] Deducted {quantity} from product {product_id}")
                inventory_updates.append({
                    "product_id": product_id,
                    "product_name": product.get("name", "Unknown"),
                    "new_stock": product.get("stock", 0),
                    "deducted": quantity
                })
            else:
                # Try to deduct even if stock goes negative (to track overselling)
                await db.products.update_one(
                    {"id": product_id},
                    {"$inc": {"stock": -quantity}}
                )
                # Refresh stock
                product = await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "name": 1, "stock": 1})
                logging.warning(f"[Inventory] Low/negative stock for product {product_id} after order {order_id}")
                inventory_updates.append({
                    "product_id": product_id,
                    "product_name": product.get("name", "Unknown"),
                    "new_stock": product.get("stock", 0),
                    "deducted": quantity,
                    "low_stock_warning": True
                })
        
        # Mark inventory as deducted
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {"inventory_deducted": True}}
        )
        
        # Broadcast inventory update to all admins via WebSocket
        if inventory_updates:
            try:
                from routers.live_support import broadcast_to_admins  # late import
            except Exception:
                broadcast_to_admins = None
            try:
                from routers.aurem_redis_router import invalidate_cache  # late import
            except Exception:
                invalidate_cache = None

            if broadcast_to_admins:
                await broadcast_to_admins({
                    "type": "inventory_update",
                    "data": {
                        "order_id": order_id,
                        "updates": inventory_updates
                    }
                })

            # Invalidate products cache since stock changed
            if invalidate_cache:
                invalidate_cache("products_all_None_50")
        
        logging.info(f"[Inventory] Successfully deducted inventory for order {order_id}")
        return True
        
    except Exception as e:
        logging.error(f"[Inventory] Error deducting inventory for order {order_id}: {e}")
        return False


async def process_auto_shipping(order_id: str):
    """
    Automatically create shipping label after payment is confirmed.
    Updates order with tracking info and sends shipping email.
    
    Args:
        order_id: The order ID to process shipping for
    """
    # Late imports to avoid circular dependency on server.py at module load.
    # `auto_create_shipment` is defined inside server.py runtime; pulled in at
    # call time so this module remains importable in any boot order.
    try:
        from server import auto_create_shipment  # type: ignore
    except Exception:
        auto_create_shipment = None
    try:
        from middleware.websocket_manager import broadcast_admin_event
    except Exception:
        broadcast_admin_event = None

    try:
        # Get the order
        order = await db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            logging.error(f"[AutoShip] Order not found: {order_id}")
            return False
        
        # Check if already shipped
        if order.get("tracking_number"):
            logging.info(f"[AutoShip] Order {order_id} already has tracking number")
            return True
        
        logging.info(f"[AutoShip] Processing shipping for order {order_id}")
        
        # Validate shipping address before attempting shipment
        shipping_addr = order.get("shipping_address", {})
        missing_fields = []
        if not shipping_addr.get('first_name'):
            missing_fields.append('first_name')
        if not (shipping_addr.get('address_line1') or shipping_addr.get('address')):
            missing_fields.append('address')
        if not shipping_addr.get('city'):
            missing_fields.append('city')
        if not shipping_addr.get('postal_code'):
            missing_fields.append('postal_code')
        if not (shipping_addr.get('province') or shipping_addr.get('state')):
            missing_fields.append('province')
            
        if missing_fields:
            error_msg = f"Missing shipping address fields: {', '.join(missing_fields)}"
            logging.error(f"[AutoShip] Order {order_id}: {error_msg}")
            await db.orders.update_one(
                {"id": order_id},
                {"$set": {"shipping_note": error_msg}}
            )
            return False
        
        # Create shipment via FlagShip
        if not auto_create_shipment:
            logging.error(f"[AutoShip] auto_create_shipment unavailable; cannot ship order {order_id}")
            return False
        shipment_result = await auto_create_shipment(order)
        
        if not shipment_result:
            logging.error(f"[AutoShip] Failed to create shipment for order {order_id}")
            # Update order to note shipping needs manual attention
            await db.orders.update_one(
                {"id": order_id},
                {"$set": {"shipping_note": "Auto-ship failed - requires manual processing"}}
            )
            return False
        
        # Update order with shipping info
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {
                "tracking_number": shipment_result["tracking_number"],
                "tracking_url": shipment_result.get("tracking_url", ""),
                "shipment_id": shipment_result["shipment_id"],
                "shipping_carrier": shipment_result["courier_name"],
                "shipping_label_url": shipment_result["label_url"],
                "shipping_cost_actual": shipment_result["total_cost"],
                "order_status": "shipped",
                "shipped_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        logging.info(f"[AutoShip] Order {order_id} shipped! Tracking: {shipment_result['tracking_number']}")
        
        # Send shipping notifications via Email, SMS, and WhatsApp
        tracking_url = shipment_result.get("tracking_url") or f"https://www.google.com/search?q={shipment_result['tracking_number']}+tracking"
        await send_shipping_notifications(
            order=order,
            tracking_number=shipment_result["tracking_number"],
            courier=shipment_result["courier_name"],
            tracking_url=tracking_url
        )
        
        # Broadcast to admin dashboard
        if broadcast_admin_event:
            await broadcast_admin_event("order_shipped", {
            "order_id": order_id,
            "order_number": order.get("order_number", ""),
            "tracking_number": shipment_result["tracking_number"],
            "courier": shipment_result["courier_name"]
        })
        
        return True
        
    except Exception as e:
        logging.error(f"[AutoShip] Error processing shipping for {order_id}: {e}")
        return False


def generate_order_cancellation_email(order: dict, refund_amount: float, store_settings: dict = None) -> str:
    """Generate HTML email for order cancellation notification"""
    store_name = store_settings.get("store_name", "ReRoots") if store_settings else "ReRoots"
    support_email = store_settings.get("support_email", "support@reroots.ca") if store_settings else "support@reroots.ca"
    
    # Check if there was a refund
    has_refund = refund_amount > 0
    refund_message = f"""
        <div style="background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%); border-radius: 12px; padding: 25px; margin: 20px 0; text-align: center;">
            <div style="font-size: 14px; color: #2E7D32; text-transform: uppercase; letter-spacing: 1px;">Refund Processed</div>
            <div style="font-size: 32px; font-weight: bold; color: #2E7D32; margin: 10px 0;">${refund_amount:.2f} CAD</div>
            <p style="color: #388E3C; font-size: 14px; margin: 0;">Your refund will appear in your account within 5-10 business days.</p>
        </div>
    """ if has_refund else ""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Order Cancelled - {store_name}</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2D2A2E; margin: 0; padding: 0; background-color: #f5f5f5;">
        <table cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f5f5;">
            <tr>
                <td align="center" style="padding: 20px;">
                    <table cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
                                <div style="font-size: 32px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
                                <div style="color: #D4AF37; font-size: 12px; letter-spacing: 3px; margin-top: 5px;">BEAUTY ENHANCER</div>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <!-- Icon -->
                                <div style="text-align: center; margin-bottom: 30px;">
                                    <div style="display: inline-block; width: 70px; height: 70px; background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%); border-radius: 50%; line-height: 70px; font-size: 36px;">📋</div>
                                </div>
                                
                                <h1 style="text-align: center; color: #2D2A2E; margin: 0 0 10px 0; font-size: 28px;">Order Cancelled</h1>
                                <p style="text-align: center; color: #666; margin: 0 0 30px 0;">We've processed your order cancellation.</p>
                                
                                <!-- Order Number Box -->
                                <div style="background: linear-gradient(135deg, #FFF5F7 0%, #FFF8E7 100%); border-radius: 12px; padding: 25px; margin: 20px 0; border-left: 4px solid #FF9800; text-align: center;">
                                    <div style="font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px;">Order Number</div>
                                    <div style="font-size: 28px; font-weight: bold; color: #2D2A2E; margin: 10px 0;">{order.get('order_number', 'N/A')}</div>
                                    <span style="display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: bold; font-size: 14px; background: #FFF3E0; color: #E65100;">Cancelled</span>
                                </div>
                                
                                {refund_message}
                                
                                <div style="background: #f9f9f9; border-radius: 8px; padding: 20px; margin: 20px 0;">
                                    <p style="color: #666; margin: 0; font-size: 14px;">
                                        If you have any questions about this cancellation or need further assistance, 
                                        please don't hesitate to reach out to our support team.
                                    </p>
                                </div>
                                
                                <!-- CTA Button -->
                                <div style="text-align: center; margin-top: 30px;">
                                    <a href="{os.environ.get('FRONTEND_URL')}/shop" style="display: inline-block; background: linear-gradient(135deg, #F8A5B8 0%, #FFB6C1 100%); color: #2D2A2E; padding: 15px 35px; text-decoration: none; border-radius: 30px; font-weight: bold; box-shadow: 0 4px 15px rgba(248, 165, 184, 0.4);">Continue Shopping</a>
                                </div>
                                
                                <p style="text-align: center; color: #666; margin-top: 30px; font-size: 14px;">
                                    We hope to see you again soon! 💕
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background: #2D2A2E; color: #ffffff; padding: 30px; text-align: center;">
                                <p style="margin: 0 0 10px 0; font-size: 14px;">Questions? Contact us at <a href="mailto:{support_email}" style="color: #F8A5B8; text-decoration: none;">{support_email}</a></p>
                                <p style="margin: 0; font-size: 12px; color: #888;">© 2025 {store_name}. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html


async def send_order_cancellation_email(order: dict, customer_email: str, refund_amount: float = 0):
    """Send order cancellation notification email to customer"""
    if not RESEND_API_KEY or not customer_email:
        logging.info(f"Order cancellation email skipped - API key or email not configured")
        return False

    try:
        store_settings = await db.store_settings.find_one({}, {"_id": 0})
        html_content = generate_order_cancellation_email(order, refund_amount, store_settings)

        subject = f"Order Cancelled - #{order.get('order_number', '')}"
        if refund_amount > 0:
            subject = f"Order Cancelled & Refund Processed - #{order.get('order_number', '')}"

        params = {
            "from": SENDER_EMAIL,
            "to": [customer_email],
            "subject": subject,
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)
        logging.info(f"Order cancellation email sent to: {customer_email}")
        
        # Update order to mark cancellation email sent
        await db.orders.update_one(
            {"id": order.get("id")},
            {"$set": {"cancellation_email_sent": True, "cancellation_email_sent_at": datetime.now(timezone.utc).isoformat()}}
        )
        return True
    except Exception as e:
        logging.error(f"Failed to send order cancellation email: {e}")
        return False


async def send_review_notification_email(
    review: dict, product_name: str, customer_name: str, customer_email: str
):
    """Send admin notification when a new review is submitted - HYBRID SYSTEM
    - Instant alerts for 1-3 star reviews (priority)
    - Queue 4-5 star reviews for daily digest
    """
    if not RESEND_API_KEY:
        logging.info("Review notification email skipped - API key not configured")
        return False

    try:
        # Check if review notifications are enabled
        store_settings = await db.store_settings.find_one({}, {"_id": 0}) or {}
        if not store_settings.get("review_notifications_enabled", True):
            logging.info("Review notifications are disabled in settings")
            return False

        admin_email = store_settings.get("admin_email", "admin@reroots.ca")
        rating = review.get("rating", 5)
        review_id = review.get("id", "")

        # HYBRID LOGIC: Instant for low ratings, queue for positive
        if rating >= 4:
            # Queue for daily digest instead of instant email
            await db.review_digest_queue.insert_one(
                {
                    "review_id": review_id,
                    "product_name": product_name,
                    "customer_name": customer_name,
                    "rating": rating,
                    "comment": review.get("comment", "")[:100],
                    "has_photos": bool(review.get("images")),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "sent": False,
                }
            )
            logging.info(f"Positive review ({rating}★) queued for daily digest")
            return True

        # Generate secure one-click approve token
        approve_token = generate_email_action_token(review_id, "approve")
        base_url = os.environ.get("FRONTEND_URL")
        approve_url = f"{base_url}/api/reviews/quick-approve?token={approve_token}"

        # Generate star HTML
        stars_html = "".join(["★" if i < rating else "☆" for i in range(5)])
        star_color = "#FF6B6B" if rating <= 2 else "#FFA500"

        # Check for photos
        has_photos = (
            "Yes"
            if review.get("images") and len(review.get("images", [])) > 0
            else "No"
        )

        # Review text (truncated if too long)
        review_text = review.get("comment", "No comment provided")
        if len(review_text) > 300:
            review_text = review_text[:300] + "..."

        # Priority banner for low ratings
        priority_banner = '<div style="background-color: #FFEBEE; color: #C62828; padding: 12px; border-radius: 5px; margin-bottom: 15px; font-weight: bold; text-align: center;">⚠️ PRIORITY: LOW RATING ALERT - Immediate attention recommended</div>'

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        .container {{ font-family: 'Segoe UI', Tahoma, sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 0; background: #fff; border-radius: 8px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #FF6B6B 0%, #EE5A5A 100%); padding: 25px; text-align: center; }}
        .header h2 {{ color: white; margin: 0; font-size: 22px; }}
        .stars {{ color: {star_color}; font-size: 32px; letter-spacing: 3px; margin: 10px 0; }}
        .content {{ padding: 25px; line-height: 1.7; color: #333; }}
        .info-row {{ padding: 10px 0; border-bottom: 1px solid #f0f0f0; }}
        .info-label {{ font-weight: 600; color: #666; display: inline-block; min-width: 100px; }}
        .button {{ background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color: white; padding: 14px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold; margin: 8px; }}
        .button-contact {{ background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%); }}
        .button-view {{ background: linear-gradient(135deg, #F8A5B8 0%, #E88DA0 100%); }}
        .blockquote {{ background: #FFF3E0; padding: 15px 20px; border-left: 4px solid #FF9800; margin: 15px 0; font-style: italic; color: #555; }}
        .footer {{ font-size: 12px; color: #999; padding: 20px; border-top: 1px solid #eee; text-align: center; background: #fafafa; }}
        .action-buttons {{ text-align: center; margin: 25px 0; }}
    </style>
</head>
<body style="background: #f5f5f5; padding: 20px;">
    <div class="container">
        <div class="header">
            <h2>⚠️ Low Rating Alert</h2>
        </div>
        <div class="content">
            {priority_banner}
            <div style="text-align: center;">
                <div class="stars">{stars_html}</div>
                <p style="font-size: 18px; color: #666; margin: 5px 0;">{rating} out of 5 stars</p>
            </div>
            
            <div style="margin: 20px 0; background: #f9f9f9; padding: 15px; border-radius: 8px;">
                <div class="info-row">
                    <span class="info-label">Product:</span>
                    <strong>{product_name}</strong>
                </div>
                <div class="info-row">
                    <span class="info-label">Customer:</span>
                    {customer_name}
                </div>
                <div class="info-row">
                    <span class="info-label">Email:</span>
                    <a href="mailto:{customer_email}">{customer_email}</a>
                </div>
                <div class="info-row" style="border: none;">
                    <span class="info-label">Photos:</span>
                    {has_photos}
                </div>
            </div>
            
            <div class="blockquote">
                "{review_text}"
            </div>
            
            <div class="action-buttons">
                <a href="mailto:{customer_email}?subject=Re: Your ReRoots Experience&body=Hi {customer_name},%0D%0A%0D%0AThank you for your feedback. We noticed..." class="button button-contact">📧 Contact Customer</a>
                <a href="{base_url}/admin" class="button button-view">📋 View in Admin</a>
            </div>
            
            <p style="text-align: center; font-size: 13px; color: #666;">
                💡 <strong>Tip:</strong> Reaching out to resolve issues before publishing can turn unhappy customers into loyal advocates.
            </p>
        </div>
        <div class="footer">
            <p>Sent automatically by ReRoots Review Alert System</p>
            <p>This is a priority alert for reviews rated 3 stars or below.</p>
        </div>
    </div>
</body>
</html>"""

        subject = (
            f"⚠️ PRIORITY: {rating}-Star Review on {product_name} - Action Required"
        )

        params = {
            "from": SENDER_EMAIL,
            "to": [admin_email],
            "subject": subject,
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)
        logging.info(f"Priority review alert ({rating}★) sent to admin: {admin_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send review notification email: {e}")
        return False


def generate_email_action_token(review_id: str, action: str) -> str:
    """Generate a secure token for one-click email actions"""
    import hashlib
    import time

    secret = JWT_SECRET  # Use global validated secret
    timestamp = int(time.time())
    # Token expires in 7 days
    data = f"{review_id}:{action}:{timestamp}:{secret}"
    token = hashlib.sha256(data.encode()).hexdigest()[:32]
    return f"{review_id}.{timestamp}.{token}"


def verify_email_action_token(token: str, action: str) -> str:
    """Verify and extract review_id from action token"""
    import hashlib
    import time

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        review_id, timestamp_str, provided_hash = parts
        timestamp = int(timestamp_str)

        # Check if token is expired (7 days)
        if time.time() - timestamp > 7 * 24 * 60 * 60:
            return None

        secret = JWT_SECRET  # Use global validated secret
        data = f"{review_id}:{action}:{timestamp}:{secret}"
        expected_hash = hashlib.sha256(data.encode()).hexdigest()[:32]

        if provided_hash == expected_hash:
            return review_id
        return None
    except:
        return None


async def send_daily_review_digest():
    """Send daily digest of positive reviews (4-5 stars) - called by scheduler"""
    if not RESEND_API_KEY:
        return False

    try:
        store_settings = await db.store_settings.find_one({}, {"_id": 0}) or {}
        if not store_settings.get("review_notifications_enabled", True):
            return False

        admin_email = store_settings.get("admin_email", "admin@reroots.ca")

        # Get unsent digest items
        pending = await db.review_digest_queue.find({"sent": False}).to_list(100)
        if not pending:
            logging.info("No pending reviews for daily digest")
            return True

        # Group by rating
        five_star = [r for r in pending if r.get("rating") == 5]
        four_star = [r for r in pending if r.get("rating") == 4]

        base_url = os.environ.get("FRONTEND_URL")

        # Build review list HTML
        def review_row(r):
            stars = "★" * r.get("rating", 5)
            photo_badge = "📷" if r.get("has_photos") else ""
            return f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">{stars}</td>
                <td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>{r.get("product_name", "Product")}</strong></td>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">{r.get("customer_name", "Customer")} {photo_badge}</td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; max-width: 200px; overflow: hidden; text-overflow: ellipsis;">{r.get("comment", "")[:50]}...</td>
            </tr>"""

        reviews_html = "".join([review_row(r) for r in pending])

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="background: #f5f5f5; padding: 20px; font-family: 'Segoe UI', Tahoma, sans-serif;">
    <div style="max-width: 650px; margin: auto; background: #fff; border-radius: 8px; overflow: hidden; border: 1px solid #eee;">
        <div style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); padding: 25px; text-align: center;">
            <h2 style="color: white; margin: 0;">🎉 Daily Review Digest</h2>
            <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">You have {len(pending)} new positive reviews!</p>
        </div>
        
        <div style="padding: 25px;">
            <div style="display: flex; gap: 20px; margin-bottom: 20px; text-align: center;">
                <div style="flex: 1; background: #FFF8E1; padding: 15px; border-radius: 8px;">
                    <p style="font-size: 28px; margin: 0; color: #FFD700;">{"★" * 5}</p>
                    <p style="margin: 5px 0 0 0; color: #666;"><strong>{len(five_star)}</strong> five-star</p>
                </div>
                <div style="flex: 1; background: #E8F5E9; padding: 15px; border-radius: 8px;">
                    <p style="font-size: 28px; margin: 0; color: #4CAF50;">{"★" * 4}☆</p>
                    <p style="margin: 5px 0 0 0; color: #666;"><strong>{len(four_star)}</strong> four-star</p>
                </div>
            </div>
            
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 12px; text-align: left;">Rating</th>
                        <th style="padding: 12px; text-align: left;">Product</th>
                        <th style="padding: 12px; text-align: left;">Customer</th>
                        <th style="padding: 12px; text-align: left;">Preview</th>
                    </tr>
                </thead>
                <tbody>
                    {reviews_html}
                </tbody>
            </table>
            
            <div style="text-align: center; margin-top: 25px;">
                <a href="{base_url}/admin" style="background: linear-gradient(135deg, #F8A5B8 0%, #E88DA0 100%); color: white; padding: 14px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;">
                    Review & Approve All
                </a>
            </div>
            
            <p style="text-align: center; color: #666; font-size: 13px; margin-top: 20px;">
                💡 Approving these reviews quickly builds social proof and boosts conversions!
            </p>
        </div>
        
        <div style="font-size: 12px; color: #999; padding: 20px; border-top: 1px solid #eee; text-align: center; background: #fafafa;">
            <p>Daily digest from ReRoots Review System</p>
            <p>Positive reviews (4-5★) are summarized daily. Low ratings trigger instant alerts.</p>
        </div>
    </div>
</body>
</html>"""

        subject = f"🎉 Daily Review Digest: {len(pending)} New Positive Reviews!"

        params = {
            "from": SENDER_EMAIL,
            "to": [admin_email],
            "subject": subject,
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)

        # Mark as sent
        review_ids = [r.get("review_id") for r in pending]
        await db.review_digest_queue.update_many(
            {"review_id": {"$in": review_ids}},
            {"$set": {"sent": True, "sent_at": datetime.now(timezone.utc).isoformat()}},
        )

        logging.info(f"Daily review digest sent with {len(pending)} reviews")
        return True
    except Exception as e:
        logging.error(f"Failed to send daily review digest: {e}")
        return False


async def send_review_thank_you_email(
    review: dict, product_name: str, customer_email: str, customer_name: str
):
    """Send thank you email to customer when their review is approved"""
    if not RESEND_API_KEY or not customer_email:
        logging.info("Thank you email skipped - API key or email not configured")
        return False

    try:
        store_settings = await db.store_settings.find_one({}, {"_id": 0}) or {}
        if not store_settings.get("review_thank_you_enabled", True):
            logging.info("Review thank you emails are disabled")
            return False

        rating = review.get("rating", 5)
        has_photos = review.get("images") and len(review.get("images", [])) > 0

        # Generate a thank you discount code
        discount_code = "THANKYOU10"  # Can be made dynamic later

        # Personalized message based on rating and photos
        photo_message = ""
        if has_photos:
            photo_message = """
            <div style="background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%); padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center;">
                <p style="margin: 0; font-size: 16px;">📸 <strong>We loved your photo!</strong></p>
                <p style="margin: 5px 0 0 0; color: #1565C0;">It's now featured on our product page for others to see.</p>
            </div>"""

        stars_html = "★" * rating + "☆" * (5 - rating)

        base_url = os.environ.get("FRONTEND_URL")
        product_url = f"{base_url}/shop"  # Could be made product-specific

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="background: #f5f5f5; padding: 20px; font-family: 'Segoe UI', Tahoma, sans-serif;">
    <div style="max-width: 600px; margin: auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #F8A5B8 0%, #E88DA0 100%); padding: 35px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">Thank You! 💖</h1>
            <p style="color: rgba(255,255,255,0.95); margin: 10px 0 0 0; font-size: 16px;">Your review is now live on our site</p>
        </div>
        
        <!-- Content -->
        <div style="padding: 30px;">
            <p style="font-size: 17px; color: #333; margin: 0 0 20px 0;">
                Hi <strong>{customer_name.split()[0] if customer_name else "there"}</strong>,
            </p>
            
            <p style="color: #555; line-height: 1.7;">
                We just wanted to say a huge <strong>THANK YOU</strong> for taking the time to share your experience with <strong>{product_name}</strong>. Your feedback helps other skincare enthusiasts make informed decisions!
            </p>
            
            <!-- Review Summary -->
            <div style="background: #FDF9F9; border: 1px solid #F8A5B8; border-radius: 10px; padding: 20px; margin: 20px 0; text-align: center;">
                <p style="color: #FFD700; font-size: 28px; margin: 0; letter-spacing: 3px;">{stars_html}</p>
                <p style="color: #666; margin: 10px 0 0 0;">Your {rating}-star review for <strong>{product_name}</strong></p>
            </div>
            
            {photo_message}
            
            <!-- Thank You Discount -->
            <div style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); padding: 25px; border-radius: 10px; margin: 25px 0; text-align: center;">
                <p style="color: white; font-size: 14px; margin: 0; text-transform: uppercase; letter-spacing: 1px;">As a thank you, here's a special gift:</p>
                <p style="color: white; font-size: 32px; font-weight: bold; margin: 10px 0; letter-spacing: 2px;">10% OFF</p>
                <p style="color: rgba(255,255,255,0.9); margin: 0;">your next order</p>
                <div style="background: white; display: inline-block; padding: 12px 30px; border-radius: 6px; margin-top: 15px;">
                    <p style="margin: 0; font-size: 20px; font-weight: bold; color: #4CAF50; letter-spacing: 3px;">{discount_code}</p>
                </div>
            </div>
            
            <p style="color: #555; line-height: 1.7; text-align: center;">
                We're on a mission to bring biotech-powered skincare to everyone. Your support and honest feedback fuel that journey.
            </p>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="{product_url}" style="background: linear-gradient(135deg, #F8A5B8 0%, #E88DA0 100%); color: white; padding: 15px 35px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold; font-size: 16px;">
                    Shop Again & Save 10%
                </a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="background: #fafafa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
            <p style="color: #999; font-size: 13px; margin: 0;">
                With gratitude,<br>
                <strong style="color: #F8A5B8;">The ReRoots Team</strong>
            </p>
            <p style="color: #bbb; font-size: 11px; margin: 15px 0 0 0;">
                ReRoots Skincare Canada | Biotech Beauty
            </p>
        </div>
    </div>
</body>
</html>"""

        subject = f"Thank You for Your Review! 💖 Here's 10% Off Your Next Order"

        params = {
            "from": SENDER_EMAIL,
            "to": [customer_email],
            "subject": subject,
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)
        logging.info(f"Review thank you email sent to: {customer_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send review thank you email: {e}")
        return False


def generate_newsletter_confirmation_email(
    email: str, thank_you_message: str = None, store_settings: dict = None
) -> str:
    """Generate HTML email for newsletter subscription confirmation"""
    store_name = (
        store_settings.get("store_name", "ReRoots") if store_settings else "ReRoots"
    )
    support_email = (
        store_settings.get("support_email", "support@reroots.ca")
        if store_settings
        else "support@reroots.ca"
    )

    default_message = "Thank you for subscribing! You'll receive exclusive offers, skincare tips, and new product alerts."
    message = thank_you_message or default_message

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Welcome to {store_name} Newsletter</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2D2A2E; margin: 0; padding: 0; background-color: #f5f5f5;">
        <table cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f5f5;">
            <tr>
                <td align="center" style="padding: 20px;">
                    <table cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
                                <div style="font-size: 32px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
                                <div style="color: #D4AF37; font-size: 12px; letter-spacing: 3px; margin-top: 5px;">BEAUTY ENHANCER</div>
                            </td>
                        </tr>
                        
                        <!-- Welcome Badge -->
                        <tr>
                            <td style="padding: 30px 30px 0; text-align: center;">
                                <div style="display: inline-block; background: linear-gradient(135deg, #F8A5B8 0%, #E91E63 100%); color: white; padding: 12px 25px; border-radius: 50px; font-weight: 600; font-size: 14px; letter-spacing: 1px;">
                                    🎉 WELCOME TO THE FAMILY
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 30px;">
                                <h2 style="color: #2D2A2E; font-size: 24px; margin: 0 0 15px; text-align: center;">
                                    You're In! 💕
                                </h2>
                                <p style="color: #5A5A5A; font-size: 16px; text-align: center; margin-bottom: 25px;">
                                    {message}
                                </p>
                                
                                <!-- What to Expect -->
                                <div style="background: #FDF9F9; border-radius: 12px; padding: 25px; margin: 25px 0;">
                                    <h3 style="color: #2D2A2E; margin: 0 0 15px; font-size: 18px;">What you can expect:</h3>
                                    <ul style="color: #5A5A5A; margin: 0; padding-left: 20px;">
                                        <li style="margin-bottom: 10px;">🌟 <strong>Exclusive Offers</strong> - First access to sales & special deals</li>
                                        <li style="margin-bottom: 10px;">💡 <strong>Skincare Tips</strong> - Expert advice for your skin concerns</li>
                                        <li style="margin-bottom: 10px;">🆕 <strong>New Arrivals</strong> - Be the first to know about new products</li>
                                        <li style="margin-bottom: 10px;">🎁 <strong>Subscriber Perks</strong> - Special rewards just for you</li>
                                    </ul>
                                </div>
                                
                                <!-- CTA Button -->
                                <div style="text-align: center; margin: 30px 0;">
                                    <a href="{os.environ.get('FRONTEND_URL')}/shop" style="display: inline-block; background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 50px; font-weight: 600; font-size: 16px;">
                                        SHOP NOW 🛒
                                    </a>
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background: #2D2A2E; padding: 25px; text-align: center;">
                                <div style="color: #F8A5B8; font-size: 18px; font-weight: bold; letter-spacing: 1px; margin-bottom: 10px;">REROOTS</div>
                                <p style="color: #999; font-size: 12px; margin: 0 0 10px;">
                                    Premium Bio-Regenerative Skincare
                                </p>
                                <p style="color: #666; font-size: 11px; margin: 0;">
                                    Questions? Contact us at <a href="mailto:{support_email}" style="color: #F8A5B8;">{support_email}</a>
                                </p>
                                <p style="color: #666; font-size: 10px; margin: 15px 0 0;">
                                    You received this email because you subscribed to our newsletter.<br>
                                    <a href="{os.environ.get('FRONTEND_URL')}/unsubscribe?email={email}" style="color: #F8A5B8;">Unsubscribe</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html


async def send_newsletter_confirmation_email(email: str, thank_you_message: str = None):
    """Send newsletter subscription confirmation email"""
    if not RESEND_API_KEY or not email:
        logging.info(
            f"Newsletter confirmation email skipped - API key or email not configured"
        )
        return False

    try:
        store_settings = await db.store_settings.find_one({}, {"_id": 0})
        html_content = generate_newsletter_confirmation_email(
            email, thank_you_message, store_settings
        )

        params = {
            "from": SENDER_EMAIL,
            "to": [email],
            "subject": "Welcome to ReRoots! 🎉 You're Subscribed",
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)
        logging.info(f"Newsletter confirmation email sent to: {email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send newsletter confirmation email: {e}")
        return False


def generate_goal_achieved_email(
    user_name: str, email: str, final_price: float = 70.00, retail_price: float = 100.0
) -> str:
    """Generate the 'Goal Achieved: Your $70 Founding Member Price is Locked' email"""
    savings = retail_price - final_price
    savings_percent = int((1 - final_price / retail_price) * 100)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Goal Achieved - ReRoots</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0a0a0a; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width: 600px; background: linear-gradient(145deg, #1a1a1a 0%, #0a0a0a 100%); border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.3); overflow: hidden;">
                        
                        <!-- Gold Header Bar -->
                        <tr>
                            <td style="height: 4px; background: linear-gradient(90deg, transparent 0%, #D4AF37 50%, transparent 100%);"></td>
                        </tr>
                        
                        <!-- Logo -->
                        <tr>
                            <td style="padding: 30px 30px 20px; text-align: center;">
                                <div style="font-size: 24px; font-weight: bold; color: #D4AF37; letter-spacing: 3px;">REROOTS</div>
                                <div style="font-size: 10px; color: rgba(255,255,255,0.4); letter-spacing: 2px; margin-top: 5px;">BIOTECH SKINCARE</div>
                            </td>
                        </tr>
                        
                        <!-- VIP Badge -->
                        <tr>
                            <td style="padding: 0 30px; text-align: center;">
                                <div style="display: inline-block; background: linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%); color: #0a0a0a; padding: 10px 24px; border-radius: 50px; font-weight: bold; font-size: 12px; letter-spacing: 1px;">
                                    🧬 PROTOCOL LEVEL: LEAD — VOUCHER ACTIVATED
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Crown Icon -->
                        <tr>
                            <td style="padding: 30px 30px 10px; text-align: center;">
                                <div style="width: 80px; height: 80px; margin: 0 auto; background: linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(212, 175, 55, 0.05) 100%); border: 2px solid #D4AF37; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                                    <span style="font-size: 40px;">👑</span>
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Main Heading -->
                        <tr>
                            <td style="padding: 20px 30px 10px; text-align: center;">
                                <h1 style="margin: 0; font-size: 28px; color: white; font-family: Georgia, serif;">
                                    Congratulations, <span style="color: #D4AF37;">{user_name or 'Founding Member'}</span>!
                                </h1>
                            </td>
                        </tr>
                        
                        <!-- Message -->
                        <tr>
                            <td style="padding: 10px 40px 30px; text-align: center;">
                                <p style="margin: 0; color: rgba(255,255,255,0.7); font-size: 16px; line-height: 1.6;">
                                    You have successfully completed the referral mission. Your dedication to the ReRoots community has unlocked the <strong style="color: #D4AF37;">maximum Founding Member subsidy</strong>.
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Price Card -->
                        <tr>
                            <td style="padding: 0 30px 30px;">
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(212, 175, 55, 0.2); border-radius: 12px; overflow: hidden;">
                                    <tr>
                                        <td style="padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                            <table width="100%">
                                                <tr>
                                                    <td style="color: rgba(255,255,255,0.5); font-size: 14px;">Retail Value</td>
                                                    <td style="text-align: right; color: rgba(255,255,255,0.5); text-decoration: line-through; font-size: 14px;">${retail_price:.2f}</td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 20px; background: linear-gradient(135deg, rgba(212, 175, 55, 0.1) 0%, rgba(212, 175, 55, 0.05) 100%);">
                                            <table width="100%">
                                                <tr>
                                                    <td style="color: white; font-size: 16px; font-weight: 600;">⭐ Your Exclusive Price</td>
                                                    <td style="text-align: right;">
                                                        <span style="font-size: 32px; font-weight: bold; color: #D4AF37;">${final_price:.2f}</span>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 12px 20px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center;">
                                            <span style="color: rgba(255,255,255,0.4); font-size: 12px;">+ HST based on Retail Value</span>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- Savings Badge -->
                        <tr>
                            <td style="padding: 0 30px 30px; text-align: center;">
                                <div style="display: inline-block; background: linear-gradient(135deg, rgba(212, 175, 55, 0.15) 0%, rgba(212, 175, 55, 0.05) 100%); border: 1px solid rgba(212, 175, 55, 0.3); padding: 12px 24px; border-radius: 50px;">
                                    <span style="color: #D4AF37; font-weight: bold; font-size: 14px;">✨ You Save ${savings:.2f} ({savings_percent}% OFF)</span>
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Priority Notice -->
                        <tr>
                            <td style="padding: 0 30px 30px;">
                                <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 20px;">
                                    <table>
                                        <tr>
                                            <td style="vertical-align: top; padding-right: 15px;">
                                                <span style="font-size: 24px;">🛡️</span>
                                            </td>
                                            <td style="color: rgba(255,255,255,0.6); font-size: 14px; line-height: 1.6;">
                                                Your profile has been flagged for <strong style="color: white;">Priority Shipment</strong>. The moment we go live, your unique checkout link will be sent to your inbox. <span style="color: #D4AF37;">Stay tuned—the future of your skin is almost here.</span>
                                            </td>
                                        </tr>
                                    </table>
                                </div>
                            </td>
                        </tr>
                        
                        <!-- CTA Button -->
                        <tr>
                            <td style="padding: 0 30px 30px; text-align: center;">
                                <a href="{os.environ.get('FRONTEND_URL')}/mission-control?code={email.split('@')[0].upper()[:4]}" style="display: inline-block; background: linear-gradient(135deg, #D4AF37 0%, #B8960F 100%); color: #0a0a0a; padding: 16px 40px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px;">
                                    👑 View My VIP Dashboard
                                </a>
                            </td>
                        </tr>
                        
                        <!-- Top 1% Note -->
                        <tr>
                            <td style="padding: 0 30px 30px; text-align: center;">
                                <p style="margin: 0; color: rgba(255,255,255,0.3); font-size: 12px;">
                                    You are now in the <span style="color: #D4AF37;">Top 1%</span> of Founding Members
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background: #0a0a0a; padding: 25px; text-align: center; border-top: 1px solid rgba(255,255,255,0.05);">
                                <p style="color: rgba(255,255,255,0.3); font-size: 11px; margin: 0 0 10px;">
                                    ReRoots · Canadian Biotech Skincare · Founding Member Program
                                </p>
                                <p style="color: rgba(255,255,255,0.2); font-size: 10px; margin: 0;">
                                    This email confirms your $70 Founding Member price lock. Keep this for your records.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html


async def send_goal_achieved_email(email: str, user_name: str = None):
    """Send the 'Goal Achieved: Your $70 Founding Member Price is Locked' email"""
    if not RESEND_API_KEY or not email:
        logging.info(f"Goal achieved email skipped - API key or email not configured")
        return False

    try:
        html_content = generate_goal_achieved_email(
            user_name or "Founding Member", email
        )

        params = {
            "from": SENDER_EMAIL,
            "to": [email],
            "subject": "🏆 Goal Achieved: Your $70 Founding Member Price is Locked",
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)
        logging.info(f"Goal achieved email sent to: {email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send goal achieved email: {e}")
        return False


async def send_oroe_vip_approval_email(
    email: str,
    first_name: str,
    access_code: str,
    bottle_number: int,
    reservation_expires: str,
):
    """Send OROÉ VIP Approval email - The Founder's Note"""
    if not RESEND_API_KEY or not email:
        logging.info(
            f"OROÉ VIP approval email skipped - API key or email not configured"
        )
        return False

    try:
        # Format the expiration date nicely
        from datetime import datetime as dt

        exp_date = dt.fromisoformat(reservation_expires.replace("Z", "+00:00"))
        formatted_exp = exp_date.strftime("%B %d, %Y at %I:%M %p UTC")

        # The Founder's Note - Elegant HTML Email
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Maison OROÉ</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Georgia', serif; background-color: #0A0A0A;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0A0A0A; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #0A0A0A; border: 1px solid rgba(212,175,55,0.3);">
                    <!-- Header -->
                    <tr>
                        <td align="center" style="padding: 40px 40px 20px;">
                            <h1 style="color: #D4AF37; font-size: 28px; font-weight: normal; margin: 0; letter-spacing: 4px;">OROÉ</h1>
                            <p style="color: rgba(212,175,55,0.6); font-size: 11px; letter-spacing: 3px; margin: 8px 0 0;">MAISON DE LA LUMIÈRE DORÉE</p>
                        </td>
                    </tr>
                    
                    <!-- Golden Divider -->
                    <tr>
                        <td align="center" style="padding: 0 60px;">
                            <div style="height: 1px; background: linear-gradient(90deg, transparent, #D4AF37, transparent);"></div>
                        </td>
                    </tr>
                    
                    <!-- Main Content - The Founder's Note -->
                    <tr>
                        <td style="padding: 40px; color: #FDF8F0;">
                            <p style="font-size: 14px; color: rgba(212,175,55,0.8); letter-spacing: 2px; margin: 0 0 20px;">A NOTE FROM THE FOUNDER</p>
                            
                            <p style="font-size: 16px; line-height: 1.8; margin: 0 0 20px; color: #FDF8F0;">
                                Dear {first_name or 'Valued Guest'},
                            </p>
                            
                            <p style="font-size: 16px; line-height: 1.8; margin: 0 0 20px; color: rgba(253,248,240,0.85);">
                                It is with great pleasure that I welcome you to Maison OROÉ—a sanctuary where cellular science meets golden luxury.
                            </p>
                            
                            <p style="font-size: 16px; line-height: 1.8; margin: 0 0 20px; color: rgba(253,248,240,0.85);">
                                Your application has been reviewed and approved. You have been allocated <strong style="color: #D4AF37;">Bottle #{bottle_number}</strong> of our limited Luminous Elixir collection—one of only 500 numbered bottles in existence.
                            </p>
                            
                            <!-- Access Code Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 30px 0; background: rgba(212,175,55,0.1); border: 1px solid rgba(212,175,55,0.3);">
                                <tr>
                                    <td align="center" style="padding: 25px;">
                                        <p style="color: rgba(212,175,55,0.8); font-size: 12px; letter-spacing: 2px; margin: 0 0 10px;">YOUR VIP ACCESS CODE</p>
                                        <p style="color: #D4AF37; font-size: 28px; letter-spacing: 4px; margin: 0; font-weight: bold;">{access_code}</p>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="font-size: 14px; line-height: 1.8; margin: 0 0 20px; color: rgba(253,248,240,0.7);">
                                Your bottle reservation is valid until <strong style="color: #D4AF37;">{formatted_exp}</strong>. During this exclusive window, use your access code to complete your acquisition.
                            </p>
                            
                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 30px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{os.environ.get('FRONTEND_URL')}/oroe" 
                                           style="display: inline-block; padding: 16px 40px; background: linear-gradient(135deg, #D4AF37, #B8860B); 
                                                  color: #0A0A0A; text-decoration: none; font-size: 13px; letter-spacing: 2px; font-weight: bold;">
                                            COMPLETE YOUR ACQUISITION
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="font-size: 16px; line-height: 1.8; margin: 30px 0 0; color: rgba(253,248,240,0.85);">
                                Welcome to the inner circle.
                            </p>
                            
                            <p style="font-size: 16px; line-height: 1.8; margin: 20px 0 0; color: #D4AF37; font-style: italic;">
                                With golden regards,
                            </p>
                            <p style="font-size: 14px; margin: 5px 0 0; color: rgba(253,248,240,0.7);">
                                The Founder, Maison OROÉ
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td align="center" style="padding: 30px 40px; border-top: 1px solid rgba(212,175,55,0.2);">
                            <p style="color: rgba(212,175,55,0.5); font-size: 11px; letter-spacing: 2px; margin: 0;">
                                OROÉ · ALTA COSMÉSI · EST. 2025
                            </p>
                            <p style="color: rgba(253,248,240,0.4); font-size: 10px; margin: 10px 0 0;">
                                This email confirms your VIP allocation. Please do not share your access code.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        params = {
            "from": SENDER_EMAIL,
            "to": [email],
            "subject": "Welcome to Maison OROÉ - Your VIP Access Has Been Approved",
            "html": html_content,
        }

        await asyncio.to_thread(resend.Emails.send, params)
        logging.info(f"OROÉ VIP approval email sent to: {email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send OROÉ VIP approval email: {e}")
        return False


def validate_password_strength(password: str) -> tuple:
    """Check password strength, returns (is_valid, message)"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    return True, "Password is strong"


# Failed login tracking for account lockout
failed_logins = defaultdict(list)
LOCKOUT_THRESHOLD = 5  # failed attempts before lockout
LOCKOUT_DURATION = 900  # 15 minutes lockout


def check_account_lockout(email: str) -> bool:
    """Check if account is locked due to failed login attempts"""
    current_time = time.time()
    # Clean old failed attempts
    failed_logins[email] = [
        t for t in failed_logins[email] if current_time - t < LOCKOUT_DURATION
    ]
    return len(failed_logins[email]) >= LOCKOUT_THRESHOLD


def record_failed_login(email: str):
    """Record a failed login attempt"""
    failed_logins[email].append(time.time())


def clear_failed_logins(email: str):
    """Clear failed login attempts after successful login"""
    failed_logins[email] = []


# Create the main app

