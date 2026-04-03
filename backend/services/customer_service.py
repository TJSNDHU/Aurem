"""
Customer Service - CRM, LTV Tracking, VIP Status
Handles customer record management and order history stacking.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

# MongoDB will be injected from server.py
db = None

def set_db(database):
    """Set the database reference."""
    global db
    db = database


async def upsert_customer_record(order: dict) -> dict:
    """
    Called after every confirmed payment.
    Creates or updates customer — stacks order history + LTV.
    Triggers VIP flag on 4th order.
    
    Args:
        order: Order document with customer info
        
    Returns:
        dict with customer record and VIP status
    """
    email = order.get("customer_email") or order.get("shipping_address", {}).get("email")
    if not email:
        logging.warning("[CRM] No email found in order")
        return {"error": "No email found"}
    
    email = email.lower().strip()
    shipping_addr = order.get("shipping_address", {})
    
    # Check if customer exists
    customer = await db.customers.find_one({"email": email}, {"_id": 0})
    
    order_total = float(order.get("total", 0))
    order_date = order.get("created_at") or datetime.now(timezone.utc).isoformat()
    
    if not customer:
        # First order — create record
        new_customer = {
            "email": email,
            "name": f"{shipping_addr.get('first_name', '')} {shipping_addr.get('last_name', '')}".strip() or order.get("customer_name", "Customer"),
            "phone": shipping_addr.get("phone") or order.get("customer_phone", ""),
            "whatsapp_phone": order.get("whatsapp_phone") or shipping_addr.get("phone"),
            "whatsapp_opted_in": order.get("whatsapp_opted_in", False),
            "shipping_address": shipping_addr.get("address") or shipping_addr.get("address_line1", ""),
            "shipping_city": shipping_addr.get("city", ""),
            "shipping_province": shipping_addr.get("province") or shipping_addr.get("state", ""),
            "shipping_postal_code": shipping_addr.get("postal_code", ""),
            "shipping_country": shipping_addr.get("country", "Canada"),
            "ltv": order_total,
            "total_orders": 1,
            "first_order_date": order_date,
            "last_order_date": order_date,
            "vip_status": False,
            "vip_since": None,
            "notes": "",
            "store_credit": 0.0,
            "has_reviewed": False,
            "acquisition_source": order.get("acquisition_source", "direct"),
            "utm_campaign": order.get("utm_campaign"),
            "utm_medium": order.get("utm_medium"),
            "quiz_completed": order.get("quiz_completed", False),
            "created_at": order_date,
            "updated_at": order_date
        }
        
        await db.customers.insert_one(new_customer)
        logging.info(f"[CRM] ✅ New customer created: {email}")
        
        return {"customer": new_customer, "vip_triggered": False, "is_new": True}
    
    else:
        # Returning customer — stack order + update LTV
        new_total_orders = customer.get("total_orders", 0) + 1
        new_ltv = float(customer.get("ltv", 0)) + order_total
        
        # VIP trigger — 4th order
        vip_triggered = new_total_orders >= 4 and not customer.get("vip_status", False)
        
        update_data = {
            "ltv": new_ltv,
            "total_orders": new_total_orders,
            "last_order_date": order_date,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Update name/phone if provided
        name = f"{shipping_addr.get('first_name', '')} {shipping_addr.get('last_name', '')}".strip()
        if name:
            update_data["name"] = name
        if shipping_addr.get("phone"):
            update_data["phone"] = shipping_addr.get("phone")
        
        # Set VIP status if triggered
        if vip_triggered:
            update_data["vip_status"] = True
            update_data["vip_since"] = order_date
            logging.info(f"[CRM] ⭐ VIP unlocked: {email} — Order #{new_total_orders}")
        elif customer.get("vip_status"):
            update_data["vip_status"] = True
        
        await db.customers.update_one(
            {"email": email},
            {"$set": update_data}
        )
        
        logging.info(f"[CRM] ✅ Customer updated: {email} | Orders: {new_total_orders} | LTV: ${new_ltv:.2f}")
        
        # Return updated customer data
        updated_customer = await db.customers.find_one({"email": email}, {"_id": 0})
        
        return {
            "customer": updated_customer,
            "vip_triggered": vip_triggered,
            "is_new": False
        }


async def save_order_to_history(order: dict, fulfillment_data: dict = None) -> bool:
    """
    Links order to customer record with receipt + tracking.
    
    Args:
        order: Order document
        fulfillment_data: Optional dict with tracking_number, label_url, shipment_id
    """
    order_id = order.get("id") or order.get("order_id")
    if not order_id:
        return False
    
    update_data = {
        "receipt_url": f"/api/receipt/{order.get('order_number', order_id)}",
        "fulfilled_at": datetime.now(timezone.utc).isoformat()
    }
    
    if fulfillment_data:
        update_data.update({
            "tracking_number": fulfillment_data.get("tracking_number"),
            "flagship_shipment_id": fulfillment_data.get("shipment_id"),
            "label_url": fulfillment_data.get("label_url")
        })
    
    await db.orders.update_one(
        {"$or": [{"id": order_id}, {"order_id": order_id}]},
        {"$set": update_data}
    )
    
    return True


async def get_customer_full_record(email: str) -> dict:
    """
    Fetches complete customer record + full order history.
    GET /api/admin/customers/<email>
    """
    email = email.lower().strip()
    
    customer = await db.customers.find_one({"email": email}, {"_id": 0})
    
    if not customer:
        return {"error": "Customer not found"}
    
    # Get order history
    orders_cursor = db.orders.find(
        {"$or": [
            {"customer_email": email},
            {"shipping_address.email": email}
        ]},
        {"_id": 0}
    ).sort("created_at", -1)
    
    orders = await orders_cursor.to_list(100)
    
    # Format orders for response
    formatted_orders = []
    for order in orders:
        formatted_orders.append({
            "order_id": order.get("order_number") or order.get("id"),
            "created_at": order.get("created_at"),
            "total": order.get("total", 0),
            "status": order.get("order_status") or order.get("status", "pending"),
            "payment_status": order.get("payment_status", "pending"),
            "tracking_number": order.get("tracking_number"),
            "receipt_url": order.get("receipt_url") or f"/api/receipt/{order.get('order_number', order.get('id'))}",
            "label_url": order.get("label_url"),
            "fulfilled_at": order.get("fulfilled_at"),
            "items": order.get("items", [])
        })
    
    return {
        "customer": {
            "name": customer.get("name", ""),
            "email": customer.get("email"),
            "phone": customer.get("phone", ""),
            "whatsapp_opted_in": customer.get("whatsapp_opted_in", False),
            "whatsapp_phone": customer.get("whatsapp_phone"),
            "vip_status": customer.get("vip_status", False),
            "vip_since": customer.get("vip_since"),
            "ltv": float(customer.get("ltv", 0)),
            "total_orders": customer.get("total_orders", 0),
            "first_order_date": customer.get("first_order_date"),
            "last_order_date": customer.get("last_order_date"),
            "shipping_address": customer.get("shipping_address", ""),
            "shipping_city": customer.get("shipping_city", ""),
            "shipping_province": customer.get("shipping_province", ""),
            "shipping_postal_code": customer.get("shipping_postal_code", ""),
            "notes": customer.get("notes", ""),
            "store_credit": float(customer.get("store_credit", 0)),
            "has_reviewed": customer.get("has_reviewed", False),
            "acquisition_source": customer.get("acquisition_source", "direct"),
            "loyalty_points": customer.get("loyalty_points", 0)
        },
        "orders": formatted_orders
    }


async def get_all_customers_summary(filters: dict = None) -> list:
    """
    Admin CRM list view — all customers with LTV + VIP flag.
    GET /api/admin/customers
    Optional filters: vip=true, min_ltv=200, min_orders=2
    """
    query = {}
    
    if filters:
        if filters.get("vip"):
            query["vip_status"] = True
        if filters.get("min_ltv"):
            query["ltv"] = {"$gte": float(filters["min_ltv"])}
        if filters.get("min_orders"):
            query["total_orders"] = {"$gte": int(filters["min_orders"])}
        if filters.get("whatsapp"):
            query["whatsapp_opted_in"] = True
    
    cursor = db.customers.find(
        query,
        {
            "_id": 0,
            "email": 1,
            "name": 1,
            "phone": 1,
            "ltv": 1,
            "total_orders": 1,
            "vip_status": 1,
            "vip_since": 1,
            "last_order_date": 1,
            "whatsapp_opted_in": 1,
            "whatsapp_phone": 1,
            "loyalty_points": 1,
            "acquisition_source": 1
        }
    ).sort("ltv", -1)
    
    customers = await cursor.to_list(500)
    return customers


async def update_customer_notes(email: str, notes: str) -> bool:
    """Update admin notes for a customer."""
    result = await db.customers.update_one(
        {"email": email.lower().strip()},
        {"$set": {
            "notes": notes,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    return result.modified_count > 0


async def send_vip_notification(customer: dict, order: dict):
    """
    Fires when customer hits 4th order.
    Sends VIP email to customer + internal alert.
    """
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    if not SENDGRID_API_KEY:
        logging.info(f"[VIP] SendGrid not configured - skipping VIP notification for {customer.get('email')}")
        return False
    
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
        
        first_name = customer.get("name", "").split()[0] if customer.get("name") else "Friend"
        
        # Email to customer
        customer_email = Mail(
            from_email=("vip@reroots.ca", "ReRoots VIP"),
            to_emails=customer.get("email"),
            subject="⭐ You've unlocked ReRoots VIP Status!",
            html_content=f"""
            <div style="font-family: Arial; max-width: 600px; margin: 0 auto; background: #fff;">
                <div style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px; text-align: center;">
                    <h1 style="color: #F8A5B8; margin: 0; font-size: 28px;">REROOTS</h1>
                    <p style="color: #D4AF37; margin: 5px 0 0; font-size: 12px; letter-spacing: 2px;">BEAUTY ENHANCER</p>
                </div>
                
                <div style="padding: 40px 30px;">
                    <h2 style="color: #2D2A2E; text-align: center;">Welcome to VIP, {first_name}! ⭐</h2>
                    <p style="color: #666;">You've placed your 4th order with us — thank you for your incredible loyalty.</p>
                    
                    <div style="background: linear-gradient(135deg, #FFF8E7 0%, #FFE4B5 100%); border-radius: 12px; padding: 25px; margin: 25px 0; text-align: center;">
                        <div style="font-size: 40px; margin-bottom: 10px;">⭐</div>
                        <div style="font-size: 18px; font-weight: bold; color: #2D2A2E;">VIP Status Unlocked</div>
                    </div>
                    
                    <p style="color: #666;">As a VIP member you now get:</p>
                    <ul style="color: #666; line-height: 1.8;">
                        <li>Early access to new product launches</li>
                        <li>Priority customer support</li>
                        <li>Exclusive VIP-only offers</li>
                        <li>Birthday surprise rewards</li>
                    </ul>
                    
                    <p style="color: #666; margin-top: 25px;">Your dedicated team at ReRoots is here for you.<br>Reply to this email anytime.</p>
                    
                    <p style="color: #2D2A2E; font-weight: bold; margin-top: 25px;">ReRoots Aesthetics Team 🌿</p>
                </div>
            </div>
            """
        )
        sg.send(customer_email)
        
        # Internal alert
        admin_email = os.environ.get("ADMIN_EMAIL", "support@reroots.ca")
        internal_alert = Mail(
            from_email=("system@reroots.ca", "ReRoots System"),
            to_emails=admin_email,
            subject=f"⭐ New VIP Customer: {customer.get('name', 'Unknown')}",
            html_content=f"""
            <p><strong>{customer.get('name', 'Unknown')}</strong> just placed their 4th order.</p>
            <p>Email: {customer.get('email')}</p>
            <p>LTV: ${float(customer.get('ltv', 0)):.2f}</p>
            <p>WhatsApp: {'✅' if customer.get('whatsapp_opted_in') else '❌'}</p>
            <a href="https://reroots.ca/admin/crm">View in CRM →</a>
            """
        )
        sg.send(internal_alert)
        
        logging.info(f"[VIP] Notification sent for {customer.get('email')}")
        return True
        
    except Exception as e:
        logging.error(f"[VIP] Failed to send notification: {e}")
        return False
