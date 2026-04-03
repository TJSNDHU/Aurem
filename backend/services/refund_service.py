"""
Refund Service - Returns, Refunds, Store Credits
Handles refund requests and resolution workflow.
"""

import os
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

# MongoDB will be injected from server.py
db = None

def set_db(database):
    """Set the database reference."""
    global db
    db = database


async def request_refund(
    order_id: str,
    customer_email: str,
    reason: str,
    refund_type: str = "full",
    photos: list = None
) -> dict:
    """
    Customer submits refund request.
    POST /api/refunds/request
    """
    customer_email = customer_email.lower().strip()
    
    # Find order
    order = await db.orders.find_one(
        {"$or": [
            {"id": order_id},
            {"order_id": order_id},
            {"order_number": order_id.upper()}
        ]},
        {"_id": 0}
    )
    
    if not order:
        return {"success": False, "error": "Order not found"}
    
    # Verify email matches
    order_email = (
        order.get("customer_email") or 
        order.get("shipping_address", {}).get("email", "")
    ).lower().strip()
    
    if order_email != customer_email:
        return {"success": False, "error": "Unauthorized - email does not match order"}
    
    # Check 30-day return window
    order_date_str = order.get("created_at")
    if order_date_str:
        try:
            if isinstance(order_date_str, str):
                order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
            else:
                order_date = order_date_str
            
            if datetime.now(timezone.utc) - order_date > timedelta(days=30):
                return {"success": False, "error": "Return window expired (30 days)"}
        except Exception as e:
            logging.warning(f"[Refund] Date parsing error: {e}")
    
    # Check not already refunded
    existing = await db.refunds.find_one({
        "order_id": order.get("order_number") or order.get("id")
    })
    
    if existing:
        return {"success": False, "error": "Refund already requested for this order"}
    
    # Create refund record
    refund_amount = float(order.get("total", 0)) if refund_type == "full" else None
    refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
    
    refund_doc = {
        "id": refund_id,
        "order_id": order.get("order_number") or order.get("id"),
        "order_number": order.get("order_number"),
        "customer_email": customer_email,
        "customer_name": order.get("customer_name") or f"{order.get('shipping_address', {}).get('first_name', '')} {order.get('shipping_address', {}).get('last_name', '')}".strip(),
        "reason": reason,
        "status": "pending",
        "refund_type": refund_type,
        "refund_amount": refund_amount,
        "original_order_total": float(order.get("total", 0)),
        "photos": photos or [],
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        "resolved_by": None,
        "notes": None,
        "items": order.get("items", [])
    }
    
    await db.refunds.insert_one(refund_doc)
    
    # Update order status
    await db.orders.update_one(
        {"$or": [{"id": order.get("id")}, {"order_number": order.get("order_number")}]},
        {"$set": {"order_status": "return_requested"}}
    )
    
    # Alert admin
    await notify_admin_refund_request(order, reason)
    
    logging.info(f"[Refund] Request created: {refund_id} for order {order.get('order_number')}")
    
    return {
        "success": True,
        "refund_id": refund_id,
        "message": "Return request submitted. We'll respond within 24 hours."
    }


async def resolve_refund(
    refund_id: str,
    action: str,
    admin_name: str,
    notes: str = "",
    partial_amount: float = None
) -> dict:
    """
    Admin approves or rejects refund.
    PATCH /api/admin/refunds/<refund_id>
    action: 'approve' | 'reject' | 'store_credit'
    """
    refund = await db.refunds.find_one(
        {"$or": [{"id": refund_id}, {"_id": refund_id}]},
        {"_id": 0}
    )
    
    if not refund:
        return {"success": False, "error": "Refund not found"}
    
    if refund.get("status") != "pending":
        return {"success": False, "error": "Refund already resolved"}
    
    order = await db.orders.find_one(
        {"$or": [
            {"order_number": refund.get("order_number")},
            {"id": refund.get("order_id")}
        ]},
        {"_id": 0}
    )
    
    now = datetime.now(timezone.utc).isoformat()
    
    if action == "approve":
        # Process full or partial refund
        amount = partial_amount if partial_amount else float(refund.get("refund_amount") or refund.get("original_order_total", 0))
        
        # Update refund record
        await db.refunds.update_one(
            {"id": refund_id},
            {"$set": {
                "status": "refunded",
                "refund_amount": amount,
                "resolved_at": now,
                "resolved_by": admin_name,
                "notes": notes
            }}
        )
        
        # Update order status
        await db.orders.update_one(
            {"$or": [{"order_number": refund.get("order_number")}, {"id": refund.get("order_id")}]},
            {"$set": {"order_status": "refunded"}}
        )
        
        # Update customer LTV (subtract refund)
        await db.customers.update_one(
            {"email": refund.get("customer_email")},
            {"$inc": {
                "ltv": -amount,
                "total_orders": -1
            }}
        )
        
        # Send notification
        await send_refund_approved_email(order, refund, amount)
        
        logging.info(f"[Refund] Approved: {refund_id} - ${amount:.2f}")
        return {"success": True, "message": f"Refund of ${amount:.2f} approved"}
    
    elif action == "store_credit":
        amount = partial_amount if partial_amount else float(refund.get("refund_amount") or refund.get("original_order_total", 0))
        
        # Update refund record
        await db.refunds.update_one(
            {"id": refund_id},
            {"$set": {
                "status": "store_credit",
                "refund_type": "store_credit",
                "refund_amount": amount,
                "resolved_at": now,
                "resolved_by": admin_name,
                "notes": notes
            }}
        )
        
        # Add store credit to customer
        await db.customers.update_one(
            {"email": refund.get("customer_email")},
            {"$inc": {"store_credit": amount}}
        )
        
        # Update order status
        await db.orders.update_one(
            {"$or": [{"order_number": refund.get("order_number")}, {"id": refund.get("order_id")}]},
            {"$set": {"order_status": "store_credit_issued"}}
        )
        
        await send_store_credit_email(order, refund, amount)
        
        logging.info(f"[Refund] Store credit issued: {refund_id} - ${amount:.2f}")
        return {"success": True, "message": f"Store credit of ${amount:.2f} issued"}
    
    elif action == "reject":
        # Update refund record
        await db.refunds.update_one(
            {"id": refund_id},
            {"$set": {
                "status": "rejected",
                "resolved_at": now,
                "resolved_by": admin_name,
                "notes": notes
            }}
        )
        
        # Restore order status
        await db.orders.update_one(
            {"$or": [{"order_number": refund.get("order_number")}, {"id": refund.get("order_id")}]},
            {"$set": {"order_status": "fulfilled"}}
        )
        
        await send_refund_rejected_email(order, refund, notes)
        
        logging.info(f"[Refund] Rejected: {refund_id}")
        return {"success": True, "message": "Refund rejected"}
    
    else:
        return {"success": False, "error": f"Invalid action: {action}"}


async def get_refunds(status: str = None) -> list:
    """Get all refunds, optionally filtered by status."""
    query = {}
    if status:
        query["status"] = status
    
    cursor = db.refunds.find(query, {"_id": 0}).sort("requested_at", -1)
    return await cursor.to_list(100)


async def notify_admin_refund_request(order: dict, reason: str):
    """Send admin notification for new refund request."""
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    if not SENDGRID_API_KEY:
        logging.info("[Refund] SendGrid not configured - skipping admin notification")
        return
    
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
        
        admin_email = os.environ.get("ADMIN_EMAIL", "support@reroots.ca")
        customer_name = order.get("customer_name") or f"{order.get('shipping_address', {}).get('first_name', '')} {order.get('shipping_address', {}).get('last_name', '')}".strip()
        
        msg = Mail(
            from_email=("system@reroots.ca", "ReRoots System"),
            to_emails=admin_email,
            subject=f"🔄 Return Request: Order #{order.get('order_number', order.get('id'))}",
            html_content=f"""
            <div style="font-family: Arial; padding: 20px;">
                <h2 style="color: #FF9800;">New Return Request</h2>
                <p><strong>Customer:</strong> {customer_name}</p>
                <p><strong>Order:</strong> #{order.get('order_number', order.get('id'))}</p>
                <p><strong>Amount:</strong> ${order.get('total', 0):.2f} CAD</p>
                <p><strong>Reason:</strong> {reason}</p>
                <div style="margin-top: 20px;">
                    <a href="https://reroots.ca/admin/refunds" 
                       style="background: #1a1a2e; color: white; padding: 12px 24px; 
                              border-radius: 6px; text-decoration: none;">
                        Review in Admin →
                    </a>
                </div>
            </div>
            """
        )
        sg.send(msg)
    except Exception as e:
        logging.error(f"[Refund] Admin notification failed: {e}")


async def send_refund_approved_email(order: dict, refund: dict, amount: float):
    """Send refund approved notification to customer."""
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    if not SENDGRID_API_KEY:
        return
    
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
        
        first_name = refund.get("customer_name", "").split()[0] if refund.get("customer_name") else "Customer"
        
        msg = Mail(
            from_email=("support@reroots.ca", "ReRoots"),
            to_emails=refund.get("customer_email"),
            subject=f"✅ Your Refund Has Been Approved - Order #{refund.get('order_number')}",
            html_content=f"""
            <div style="font-family: Arial; max-width: 600px; margin: 0 auto;">
                <div style="background: #2D2A2E; padding: 25px; text-align: center;">
                    <h1 style="color: #F8A5B8; margin: 0;">REROOTS</h1>
                </div>
                <div style="padding: 30px;">
                    <h2 style="color: #4CAF50;">Refund Approved ✅</h2>
                    <p>Hi {first_name},</p>
                    <p>Your refund request for Order #{refund.get('order_number')} has been approved.</p>
                    
                    <div style="background: #E8F5E9; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #2E7D32;">
                            ${amount:.2f} CAD
                        </div>
                        <div style="color: #666; font-size: 14px;">Refund Amount</div>
                    </div>
                    
                    <p>The refund will be processed to your original payment method within 5-10 business days.</p>
                    
                    <p>Thank you for shopping with ReRoots. We hope to see you again!</p>
                    <p><strong>ReRoots Team</strong></p>
                </div>
            </div>
            """
        )
        sg.send(msg)
    except Exception as e:
        logging.error(f"[Refund] Approval email failed: {e}")


async def send_store_credit_email(order: dict, refund: dict, amount: float):
    """Send store credit notification to customer."""
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    if not SENDGRID_API_KEY:
        return
    
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
        
        first_name = refund.get("customer_name", "").split()[0] if refund.get("customer_name") else "Customer"
        
        msg = Mail(
            from_email=("support@reroots.ca", "ReRoots"),
            to_emails=refund.get("customer_email"),
            subject=f"💳 Store Credit Added to Your Account - ${amount:.2f}",
            html_content=f"""
            <div style="font-family: Arial; max-width: 600px; margin: 0 auto;">
                <div style="background: #2D2A2E; padding: 25px; text-align: center;">
                    <h1 style="color: #F8A5B8; margin: 0;">REROOTS</h1>
                </div>
                <div style="padding: 30px;">
                    <h2 style="color: #9C27B0;">Store Credit Added 💳</h2>
                    <p>Hi {first_name},</p>
                    <p>We've added store credit to your account for Order #{refund.get('order_number')}.</p>
                    
                    <div style="background: #F3E5F5; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #7B1FA2;">
                            ${amount:.2f} CAD
                        </div>
                        <div style="color: #666; font-size: 14px;">Store Credit Balance</div>
                    </div>
                    
                    <p>This credit will be automatically applied to your next purchase.</p>
                    
                    <div style="text-align: center; margin: 25px 0;">
                        <a href="https://reroots.ca/shop" 
                           style="background: #9C27B0; color: white; padding: 12px 30px; 
                                  border-radius: 6px; text-decoration: none; display: inline-block;">
                            Shop Now →
                        </a>
                    </div>
                    
                    <p><strong>ReRoots Team</strong></p>
                </div>
            </div>
            """
        )
        sg.send(msg)
    except Exception as e:
        logging.error(f"[Refund] Store credit email failed: {e}")


async def send_refund_rejected_email(order: dict, refund: dict, notes: str):
    """Send refund rejection notification to customer."""
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    if not SENDGRID_API_KEY:
        return
    
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
        
        first_name = refund.get("customer_name", "").split()[0] if refund.get("customer_name") else "Customer"
        
        msg = Mail(
            from_email=("support@reroots.ca", "ReRoots"),
            to_emails=refund.get("customer_email"),
            subject=f"Update on Your Return Request - Order #{refund.get('order_number')}",
            html_content=f"""
            <div style="font-family: Arial; max-width: 600px; margin: 0 auto;">
                <div style="background: #2D2A2E; padding: 25px; text-align: center;">
                    <h1 style="color: #F8A5B8; margin: 0;">REROOTS</h1>
                </div>
                <div style="padding: 30px;">
                    <h2 style="color: #2D2A2E;">Return Request Update</h2>
                    <p>Hi {first_name},</p>
                    <p>Thank you for contacting us about Order #{refund.get('order_number')}.</p>
                    
                    <p>After reviewing your request, we're unable to process a refund at this time.</p>
                    
                    {f'<div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;"><strong>Note:</strong> {notes}</div>' if notes else ''}
                    
                    <p>If you have any questions, please don't hesitate to reply to this email.</p>
                    
                    <p><strong>ReRoots Team</strong></p>
                </div>
            </div>
            """
        )
        sg.send(msg)
    except Exception as e:
        logging.error(f"[Refund] Rejection email failed: {e}")
