"""
Shipping integration, QR codes, abandoned carts, analytics
Extracted from server.py during modularization.
"""

import os
import logging
import json
import hashlib
import secrets
import time
import uuid
import re
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Query, Body, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from utils.stubs import (
    send_shipping_update_email, handle_flagship_webhook,
    get_all_customers_summary, get_customer_full_record,
    update_customer_notes, request_refund, get_refunds, resolve_refund,
    get_sales_dashboard, get_acquisition_sources, get_revenue_metrics,
)
try:
    from models.server_models import Product, Cart, Review, ShippingAddress, Order, ShippingRate
except ImportError:
    pass
try:
    pass  # No email templates needed
except ImportError:
    pass

logger = logging.getLogger(__name__)
orders_collection = None  # Set during DB init

# Common imports from server.py scope
import bcrypt
import jwt
try:
    import stripe
except ImportError:
    stripe = None

try:
    from performance_patch import limiter
except ImportError:
    limiter = type('obj', (object,), {'limit': lambda self, *a, **kw: lambda f: f})()

from middleware.security import sanitize_input, validate_email

try:
    from middleware.websocket_manager import WebSocketConnectionManager
    manager = WebSocketConnectionManager()
except ImportError:
    manager = None

from config import JWT_SECRET
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
SITE_URL = os.environ.get("SITE_URL", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# MongoDB client reference (set at startup)
client = None

def set_client(c):
    global client
    client = c

# Helpers from server.py scope
ROOT_DIR = __import__("pathlib").Path(os.path.dirname(os.path.abspath(__file__)))

async def get_current_user(request: Request):
    """Extract user from JWT token in request."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        token = auth.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except Exception:
        return None

async def require_admin(request: Request):
    """Verify admin role from JWT."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ("admin", "founder", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def generate_jwt_token(user_data: dict, expires_hours: int = 24):
    """Generate JWT token."""
    import time as _time
    payload = {
        **user_data,
        "exp": int(_time.time()) + (expires_hours * 3600),
        "iat": int(_time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")



# Shared state — set by server.py at startup
db = None
api_router = None

def set_db(database):
    global db
    db = database

def set_router(router):
    global api_router
    api_router = router

def get_db():
    return db

router = APIRouter()

# ============= FLAGSHIP SHIPPING INTEGRATION =============
# Real-time shipping rates from UPS, FedEx, Purolator, Canada Post
# Documentation: https://docs.smartship.io

from services.flagship_shipping import (
    get_shipping_rates,
    create_shipping_label,
    auto_create_shipment,
    flagship_client,
    ShippingAddress as FSShippingAddress,
    Package as FSPackage,
    ShippingRate as FSShippingRate,
)


class ShippingRateRequest(BaseModel):
    """Request model for getting shipping rates"""

    name: str
    address: str
    city: str
    state: str  # Province: ON, BC, AB, QC, etc.
    postal_code: str
    country: str = "CA"
    phone: Optional[str] = ""
    packages: List[dict] = Field(
        default_factory=lambda: [{"weight": 0.5, "description": "Skincare Products"}]
    )


class CreateShipmentRequest(BaseModel):
    """Request model for creating a shipment with label"""

    order_id: str
    to_address: dict
    packages: List[dict]
    selected_rate: dict


@router.post("/shipping/rates")
async def get_rates(request: ShippingRateRequest):
    """
    Get real-time shipping rates from multiple carriers.

    Returns rates from UPS, FedEx, Purolator, and Canada Post
    sorted by price (cheapest first).
    """
    try:
        to_address = {
            "name": request.name,
            "address": request.address,
            "city": request.city,
            "state": request.state,
            "postal_code": request.postal_code,
            "country": request.country,
            "phone": request.phone or "",
        }

        # Default package for skincare (if not specified)
        packages = (
            request.packages
            if request.packages
            else [
                {
                    "weight": 0.5,
                    "length": 20,
                    "width": 15,
                    "height": 10,
                    "description": "Skincare Products",
                }
            ]
        )

        rates = await get_shipping_rates(to_address, packages)

        return {
            "success": True,
            "rates": rates,
            "from": "Toronto, ON",
            "to": f"{request.city}, {request.state}",
        }

    except Exception as e:
        logging.error(f"Shipping rate error: {e}")
        # Return fallback flat rates if API fails
        return {
            "success": False,
            "error": str(e),
            "rates": [
                {
                    "courier_name": "Standard Shipping",
                    "courier_code": "STANDARD",
                    "service_code": "standard",
                    "service_name": "Standard Delivery",
                    "transit_days": 5,
                    "total_price": 9.99,
                    "currency": "CAD",
                },
                {
                    "courier_name": "Express Shipping",
                    "courier_code": "EXPRESS",
                    "service_code": "express",
                    "service_name": "Express Delivery",
                    "transit_days": 2,
                    "total_price": 19.99,
                    "currency": "CAD",
                },
            ],
        }


@router.post("/shipping/create-shipment")
async def create_shipment(
    request: CreateShipmentRequest, current_user: dict = Depends(require_admin)
):
    """
    Create a shipment and generate shipping label.
    Admin only - used from order management dashboard.
    """
    try:
        result = await create_shipping_label(
            to_address=request.to_address,
            packages=request.packages,
            selected_rate=request.selected_rate,
            order_id=request.order_id,
        )

        # Update order with shipping info
        await orders_collection.update_one(
            {"order_id": request.order_id},
            {
                "$set": {
                    "shipping_label_url": result.get("label_url"),
                    "tracking_number": result.get("tracking_number"),
                    "shipping_carrier": result.get("courier_name"),
                    "shipment_id": result.get("shipment_id"),
                    "shipping_cost_paid": result.get("total_cost", 0),
                    "status": "shipped",
                    "shipped_at": datetime.now(timezone.utc),
                }
            },
        )

        # Get order details for email notification
        order = await orders_collection.find_one({"order_id": request.order_id})
        if order and order.get("email"):
            try:
                await send_shipping_update_email(order, order["email"], "shipped")
            except Exception as email_err:
                logging.error(f"Failed to send shipping email: {email_err}")

        return {
            "success": True,
            "shipment": result,
            "message": f"Shipment created with tracking: {result.get('tracking_number')}",
        }

    except Exception as e:
        logging.error(f"Shipment creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= PUBLIC ORDER TRACKING & RECEIPTS =============

@router.get("/track")
async def public_order_tracking(order: str = None, email: str = None):
    """
    Public endpoint for customers to track their order.
    Requires order number AND email for verification.
    No login required - accessible via direct link from emails.
    
    Args:
        order: Order number (e.g., "RR-240301-ABC123")
        email: Customer's email for verification
        
    Returns:
        Order tracking information including status, shipping details, and timeline
    """
    if not order or not email:
        raise HTTPException(
            status_code=400, 
            detail="Both order number and email are required"
        )
    
    # Normalize email
    email = email.lower().strip()
    
    # Find order by order_number
    order_doc = await db.orders.find_one(
        {"order_number": order.upper()},
        {"_id": 0}
    )
    
    if not order_doc:
        # Also try searching by order ID
        order_doc = await db.orders.find_one(
            {"id": order},
            {"_id": 0}
        )
    
    if not order_doc:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify email matches
    shipping_email = order_doc.get("shipping_address", {}).get("email", "").lower().strip()
    billing_email = order_doc.get("billing_address", {}).get("email", "").lower().strip()
    customer_email = order_doc.get("customer_email", "").lower().strip()
    
    if email not in [shipping_email, billing_email, customer_email]:
        raise HTTPException(status_code=403, detail="Email does not match order")
    
    # Get live tracking from FlagShip if available
    tracking_info = None
    tracking_number = order_doc.get("tracking_number")
    if tracking_number:
        try:
            tracking_info = await flagship_client.track_shipment(tracking_number)
        except Exception as e:
            logging.warning(f"FlagShip tracking lookup failed: {e}")
    
    # Build timeline
    timeline = []
    
    # Order placed
    created_at = order_doc.get("created_at")
    if created_at:
        timeline.append({
            "status": "Order Placed",
            "description": "Your order has been received",
            "timestamp": created_at,
            "completed": True
        })
    
    # Payment confirmed
    if order_doc.get("payment_status") in ["paid", "completed", "success"]:
        timeline.append({
            "status": "Payment Confirmed",
            "description": "Payment successfully processed",
            "timestamp": order_doc.get("paid_at") or created_at,
            "completed": True
        })
    
    # Processing
    order_status = order_doc.get("order_status", "pending")
    if order_status in ["processing", "shipped", "delivered"]:
        timeline.append({
            "status": "Processing",
            "description": "Your order is being prepared",
            "timestamp": order_doc.get("processing_at") or created_at,
            "completed": True
        })
    elif order_status == "pending":
        timeline.append({
            "status": "Processing",
            "description": "Your order is being prepared",
            "timestamp": None,
            "completed": False
        })
    
    # Shipped
    if order_status in ["shipped", "delivered"]:
        timeline.append({
            "status": "Shipped",
            "description": f"Shipped via {order_doc.get('shipping_carrier', 'carrier')}",
            "timestamp": order_doc.get("shipped_at"),
            "completed": True,
            "tracking_number": tracking_number
        })
    elif order_status not in ["cancelled", "refunded"]:
        timeline.append({
            "status": "Shipped",
            "description": "Package will be shipped soon",
            "timestamp": None,
            "completed": False
        })
    
    # Delivered
    if order_status == "delivered":
        timeline.append({
            "status": "Delivered",
            "description": "Package delivered",
            "timestamp": order_doc.get("delivered_at"),
            "completed": True
        })
    elif order_status not in ["cancelled", "refunded"]:
        timeline.append({
            "status": "Delivered",
            "description": "Estimated delivery pending",
            "timestamp": None,
            "completed": False
        })
    
    # Build response
    shipping_addr = order_doc.get("shipping_address", {})
    
    return {
        "success": True,
        "order": {
            "order_number": order_doc.get("order_number"),
            "order_status": order_status,
            "payment_status": order_doc.get("payment_status", "pending"),
            "created_at": order_doc.get("created_at"),
            "total": order_doc.get("total", 0),
            "currency": "CAD",
            "items_count": sum(item.get("quantity", 1) for item in order_doc.get("items", [])),
            "items": [
                {
                    "name": item.get("product_name", item.get("name", "Product")),
                    "quantity": item.get("quantity", 1),
                    "price": item.get("price", 0),
                    "image": item.get("product_image", item.get("image", ""))
                }
                for item in order_doc.get("items", [])
            ]
        },
        "shipping": {
            "recipient": f"{shipping_addr.get('first_name', '')} {shipping_addr.get('last_name', '')}".strip(),
            "address": shipping_addr.get("address", "") or shipping_addr.get("address_line1", ""),
            "city": shipping_addr.get("city", ""),
            "province": shipping_addr.get("province", "") or shipping_addr.get("state", ""),
            "postal_code": shipping_addr.get("postal_code", ""),
            "country": shipping_addr.get("country", "Canada")
        },
        "tracking": {
            "carrier": order_doc.get("shipping_carrier"),
            "tracking_number": tracking_number,
            "tracking_url": order_doc.get("tracking_url"),
            "shipped_at": order_doc.get("shipped_at"),
            "delivered_at": order_doc.get("delivered_at"),
            "label_url": order_doc.get("shipping_label_url"),
            "live_tracking": tracking_info
        },
        "timeline": timeline
    }


@router.get("/receipt/{order_id}")
async def get_receipt_pdf(order_id: str, email: str = None):
    """
    Generate and return a PDF receipt for an order.
    Requires email verification for security.
    
    Args:
        order_id: Order ID or order number
        email: Customer's email for verification
        
    Returns:
        PDF file download
    """
    from services.receipt_service import generate_receipt_pdf
    
    if not email:
        raise HTTPException(status_code=400, detail="Email is required for verification")
    
    email = email.lower().strip()
    
    # Find order
    order_doc = await db.orders.find_one(
        {"$or": [{"id": order_id}, {"order_number": order_id.upper()}]},
        {"_id": 0}
    )
    
    if not order_doc:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify email
    shipping_email = order_doc.get("shipping_address", {}).get("email", "").lower().strip()
    billing_email = order_doc.get("billing_address", {}).get("email", "").lower().strip()
    customer_email = order_doc.get("customer_email", "").lower().strip()
    
    if email not in [shipping_email, billing_email, customer_email]:
        raise HTTPException(status_code=403, detail="Email does not match order")
    
    # Check payment status
    if order_doc.get("payment_status") not in ["paid", "completed", "success"]:
        raise HTTPException(status_code=400, detail="Receipt not available - order not paid")
    
    try:
        # Generate PDF
        pdf_bytes = generate_receipt_pdf(order_doc)
        
        order_number = order_doc.get("order_number", order_id)
        filename = f"ReRoots_Receipt_{order_number}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logging.error(f"[Receipt] PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate receipt")


@router.post("/receipt/{order_id}/send")
async def send_receipt_email_endpoint(order_id: str, request: Request):
    """
    Send PDF receipt via email. Admin only.
    
    Args:
        order_id: Order ID or order number
    """
    await require_admin(request)
    
    from services.receipt_service import send_receipt_email
    
    # Find order
    order_doc = await db.orders.find_one(
        {"$or": [{"id": order_id}, {"order_number": order_id.upper()}]},
        {"_id": 0}
    )
    
    if not order_doc:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get customer email
    customer_email = (
        order_doc.get("shipping_address", {}).get("email") or
        order_doc.get("billing_address", {}).get("email") or
        order_doc.get("customer_email")
    )
    
    if not customer_email:
        raise HTTPException(status_code=400, detail="No email address found for order")
    
    # Send receipt
    success = await send_receipt_email(order_doc, customer_email)
    
    if success:
        # Update order to mark receipt sent
        await db.orders.update_one(
            {"id": order_doc.get("id")},
            {"$set": {
                "receipt_pdf_sent": True,
                "receipt_pdf_sent_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return {"success": True, "message": f"Receipt sent to {customer_email}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send receipt email")


@router.get("/shipping/track/{tracking_number}")
async def track_shipment(tracking_number: str):
    """
    Get tracking information for a shipment.
    """
    try:
        tracking_info = await flagship_client.track_shipment(tracking_number)
        return {"success": True, "tracking": tracking_info}
    except Exception as e:
        logging.error(f"Tracking error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/admin/flagship/shipments")
async def get_flagship_shipments(
    request: Request,
    limit: int = 50,
    page: int = 1
):
    """
    Get all shipped orders with tracking numbers from our system.
    Shows orders that have been shipped via FlagShip.
    """
    await require_admin(request)
    
    try:
        skip = (page - 1) * limit
        
        # Get all orders that have tracking numbers (shipped orders)
        shipped_orders = await db.orders.find(
            {"tracking_number": {"$exists": True, "$ne": None}},
            {"_id": 0}
        ).sort("shipped_at", -1).skip(skip).limit(limit).to_list(None)
        
        # Get total count
        total_count = await db.orders.count_documents(
            {"tracking_number": {"$exists": True, "$ne": None}}
        )
        
        # Format for display
        shipments = []
        for order in shipped_orders:
            addr = order.get("shipping_address", {})
            shipments.append({
                "id": order.get("id"),
                "order_number": order.get("order_number"),
                "tracking_number": order.get("tracking_number"),
                "tracking_url": order.get("tracking_url"),
                "courier_name": order.get("shipping_carrier", "Unknown"),
                "status": order.get("order_status", "shipped"),
                "created_at": order.get("created_at"),
                "shipped_at": order.get("shipped_at"),
                "label_url": order.get("shipping_label_url"),
                "to": {
                    "name": f"{addr.get('first_name', '')} {addr.get('last_name', '')}".strip(),
                    "address": addr.get("address_line1", ""),
                    "city": addr.get("city", ""),
                    "state": addr.get("province", "") or addr.get("state", ""),
                    "postal_code": addr.get("postal_code", ""),
                    "country": addr.get("country", "CA"),
                },
                "total_price": order.get("shipping_cost_actual", 0),
                "order_total": order.get("total", 0),
                "internal_order": {
                    "id": order.get("id"),
                    "order_number": order.get("order_number"),
                    "total": order.get("total", 0)
                }
            })
        
        return {
            "success": True,
            "shipments": shipments,
            "total": total_count,
            "page": page,
            "limit": limit
        }
        
    except Exception as e:
        logging.error(f"[Admin] Failed to fetch shipments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch shipments: {str(e)}")


@router.post("/admin/flagship/sync")
async def sync_flagship_shipments(request: Request):
    """
    Sync shipments from FlagShip API to local database.
    Fetches ALL shipments from FlagShip (including those created externally)
    and stores them locally for unified tracking.
    """
    await require_admin(request)
    
    try:
        from services.flagship_shipping import flagship_client
        
        # Fetch shipments from FlagShip API (multiple pages if needed)
        all_flagship_shipments = []
        page = 1
        while True:
            shipments = await flagship_client.list_shipments(limit=100, page=page)
            if not shipments:
                break
            all_flagship_shipments.extend(shipments)
            if len(shipments) < 100:  # Last page
                break
            page += 1
        
        logging.info(f"[FlagShip Sync] Fetched {len(all_flagship_shipments)} shipments from FlagShip API")
        
        # Get all tracking numbers already in our orders
        existing_orders = await db.orders.find(
            {"tracking_number": {"$exists": True, "$ne": None}},
            {"tracking_number": 1, "_id": 0}
        ).to_list(None)
        existing_tracking = {o.get("tracking_number") for o in existing_orders}
        
        # Get already synced external shipments
        existing_external = await db.external_shipments.find(
            {},
            {"flagship_id": 1, "tracking_number": 1, "_id": 0}
        ).to_list(None)
        existing_external_ids = {e.get("flagship_id") for e in existing_external}
        existing_external_tracking = {e.get("tracking_number") for e in existing_external}
        
        # Find shipments that are not in our orders (external shipments)
        new_synced = 0
        updated_synced = 0
        
        for shipment in all_flagship_shipments:
            flagship_id = str(shipment.get("id", ""))
            tracking_number = shipment.get("tracking_number", "")
            
            # Skip if already in our orders collection
            if tracking_number and tracking_number in existing_tracking:
                continue
            
            # Prepare external shipment document
            external_doc = {
                "flagship_id": flagship_id,
                "tracking_number": tracking_number,
                "courier_name": shipment.get("courier_name", "Unknown"),
                "courier_code": shipment.get("courier_code", ""),
                "status": shipment.get("status", "unknown"),
                "created_at": shipment.get("created_at"),
                "shipped_at": shipment.get("shipped_at"),
                "label_url": shipment.get("label_url"),
                "from": shipment.get("from", {}),
                "to": shipment.get("to", {}),
                "total_price": shipment.get("total_price", 0),
                "reference": shipment.get("reference", ""),
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "source": "flagship_external"
            }
            
            if flagship_id in existing_external_ids or tracking_number in existing_external_tracking:
                # Update existing external shipment
                await db.external_shipments.update_one(
                    {"$or": [{"flagship_id": flagship_id}, {"tracking_number": tracking_number}]},
                    {"$set": external_doc}
                )
                updated_synced += 1
            else:
                # Insert new external shipment
                await db.external_shipments.insert_one(external_doc)
                new_synced += 1
        
        logging.info(f"[FlagShip Sync] New: {new_synced}, Updated: {updated_synced}")
        
        return {
            "success": True,
            "message": f"Sync complete. {new_synced} new external shipments added, {updated_synced} updated.",
            "flagship_total": len(all_flagship_shipments),
            "new_synced": new_synced,
            "updated_synced": updated_synced
        }
        
    except Exception as e:
        logging.error(f"[FlagShip Sync] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/admin/flagship/webhook")
async def flagship_webhook_endpoint(request: Request):
    """
    Webhook endpoint for FlagShip to call when a shipping label is created.
    Configure in FlagShip dashboard: Settings → Webhooks → Add URL
    """
    try:
        payload = await request.json()
        result = await handle_flagship_webhook(db, payload)
        return result
    except Exception as e:
        logging.error(f"[FlagShip Webhook] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


@router.get("/admin/flagship/all-shipments")
async def get_all_flagship_shipments(
    request: Request,
    limit: int = 50,
    page: int = 1,
    source: str = "all"  # all, internal, external
):
    """
    Get all shipments: both internal (from orders) and external (synced from FlagShip).
    """
    await require_admin(request)
    
    try:
        skip = (page - 1) * limit
        shipments = []
        
        # Get internal shipments (from orders)
        if source in ["all", "internal"]:
            shipped_orders = await db.orders.find(
                {"tracking_number": {"$exists": True, "$ne": None}},
                {"_id": 0}
            ).sort("shipped_at", -1).to_list(None)
            
            for order in shipped_orders:
                addr = order.get("shipping_address", {})
                shipments.append({
                    "id": order.get("id"),
                    "flagship_id": order.get("flagship_shipment_id"),
                    "order_number": order.get("order_number"),
                    "tracking_number": order.get("tracking_number"),
                    "tracking_url": order.get("tracking_url"),
                    "courier_name": order.get("shipping_carrier", "Unknown"),
                    "status": order.get("order_status", "shipped"),
                    "created_at": order.get("created_at"),
                    "shipped_at": order.get("shipped_at"),
                    "label_url": order.get("shipping_label_url"),
                    "to": {
                        "name": f"{addr.get('first_name', '')} {addr.get('last_name', '')}".strip(),
                        "address": addr.get("address_line1", ""),
                        "city": addr.get("city", ""),
                        "state": addr.get("province", "") or addr.get("state", ""),
                        "postal_code": addr.get("postal_code", ""),
                        "country": addr.get("country", "CA"),
                    },
                    "total_price": order.get("shipping_cost_actual", 0),
                    "order_total": order.get("total", 0),
                    "source": "internal"
                })
        
        # Get external shipments (synced from FlagShip)
        if source in ["all", "external"]:
            external_shipments = await db.external_shipments.find(
                {},
                {"_id": 0}
            ).sort("synced_at", -1).to_list(None)
            
            for ext in external_shipments:
                shipments.append({
                    "id": ext.get("flagship_id"),
                    "flagship_id": ext.get("flagship_id"),
                    "order_number": ext.get("reference") or f"EXT-{ext.get('flagship_id', '')[:8]}",
                    "tracking_number": ext.get("tracking_number"),
                    "tracking_url": f"https://www.google.com/search?q={ext.get('tracking_number')}+tracking",
                    "courier_name": ext.get("courier_name", "Unknown"),
                    "status": ext.get("status", "unknown"),
                    "created_at": ext.get("created_at"),
                    "shipped_at": ext.get("shipped_at"),
                    "label_url": ext.get("label_url"),
                    "to": ext.get("to", {}),
                    "total_price": ext.get("total_price", 0),
                    "order_total": 0,
                    "source": "external",
                    "synced_at": ext.get("synced_at")
                })
        
        # Sort by shipped_at descending
        shipments.sort(key=lambda x: x.get("shipped_at") or x.get("created_at") or "", reverse=True)
        
        # Apply pagination
        total_count = len(shipments)
        paginated = shipments[skip:skip + limit]
        
        return {
            "success": True,
            "shipments": paginated,
            "total": total_count,
            "page": page,
            "limit": limit,
            "internal_count": len([s for s in shipments if s.get("source") == "internal"]),
            "external_count": len([s for s in shipments if s.get("source") == "external"])
        }
        
    except Exception as e:
        logging.error(f"[Admin] Failed to fetch all shipments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch shipments: {str(e)}")


@router.get("/admin/shipping/pending")
async def get_pending_shipments(current_user: dict = Depends(require_admin)):
    """
    Get orders that need shipping labels created.
    """
    try:
        pending = (
            await orders_collection.find(
                {
                    "status": {"$in": ["paid", "processing", "confirmed"]},
                    "tracking_number": {"$exists": False},
                }
            )
            .sort("created_at", -1)
            .to_list(100)
        )

        # Format for frontend
        shipments = []
        for order in pending:
            shipments.append(
                {
                    "order_id": order.get("order_id"),
                    "customer_name": order.get("shipping_address", {}).get(
                        "name", "Unknown"
                    ),
                    "customer_email": order.get("email"),
                    "shipping_address": order.get("shipping_address", {}),
                    "items": order.get("items", []),
                    "total": order.get("total", 0),
                    "created_at": order.get("created_at"),
                    "status": order.get("status"),
                }
            )

        return {
            "success": True,
            "pending_count": len(shipments),
            "shipments": shipments,
        }

    except Exception as e:
        logging.error(f"Failed to get pending shipments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/shipping/shipped")
async def get_shipped_orders(current_user: dict = Depends(require_admin)):
    """
    Get orders that have been shipped (have tracking numbers).
    """
    try:
        shipped = (
            await orders_collection.find(
                {"tracking_number": {"$exists": True, "$ne": ""}}
            )
            .sort("shipped_at", -1)
            .to_list(100)
        )

        shipments = []
        for order in shipped:
            shipments.append(
                {
                    "order_id": order.get("order_id"),
                    "customer_name": order.get("shipping_address", {}).get(
                        "name", "Unknown"
                    ),
                    "tracking_number": order.get("tracking_number"),
                    "shipping_carrier": order.get("shipping_carrier"),
                    "label_url": order.get("shipping_label_url"),
                    "shipped_at": order.get("shipped_at"),
                    "status": order.get("status"),
                }
            )

        return {
            "success": True,
            "shipped_count": len(shipments),
            "shipments": shipments,
        }

    except Exception as e:
        logging.error(f"Failed to get shipped orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= DYNAMIC QR CODE SYSTEM =============
# Allows creating QR codes with changeable destinations without reprinting


class DynamicQRCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    destination_url: str
    qr_type: str = "product"  # product, promo, bridge, verification
    brand: str = "reroots"  # reroots, oroe, lavela
    batch_id: Optional[str] = None
    metadata: Optional[dict] = {}


@router.post("/admin/dynamic-qr")
async def create_dynamic_qr(
    qr_data: DynamicQRCreate, current_user: dict = Depends(require_admin)
):
    """Create a new dynamic QR code entry"""
    try:
        # Generate unique short code for the QR
        import secrets

        short_code = secrets.token_urlsafe(8)[:10].upper()

        qr_entry = {
            "short_code": short_code,
            "name": qr_data.name,
            "description": qr_data.description,
            "destination_url": qr_data.destination_url,
            "qr_type": qr_data.qr_type,
            "brand": qr_data.brand,
            "batch_id": qr_data.batch_id,
            "metadata": qr_data.metadata,
            "scan_count": 0,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": current_user.get("email", "admin"),
        }

        result = await db.dynamic_qr_codes.insert_one(qr_entry)
        qr_entry["_id"] = str(result.inserted_id)

        # Generate the redirect URL (this is what gets printed on the QR)
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://reroots.ca")
        redirect_url = f"{base_url}/qr/{short_code}"

        return {
            "success": True,
            "qr_code": {**qr_entry, "_id": str(result.inserted_id)},
            "redirect_url": redirect_url,
            "short_code": short_code,
        }
    except Exception as e:
        logging.error(f"Failed to create dynamic QR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/dynamic-qr")
async def get_dynamic_qr_codes(current_user: dict = Depends(require_admin)):
    """Get all dynamic QR codes"""
    try:
        qr_codes = (
            await db.dynamic_qr_codes.find({}).sort("created_at", -1).to_list(1000)
        )
        for qr in qr_codes:
            qr["_id"] = str(qr["_id"])
        return {"success": True, "qr_codes": qr_codes}
    except Exception as e:
        logging.error(f"Failed to get dynamic QR codes: {e}")
        return {"success": False, "qr_codes": []}


@router.put("/admin/dynamic-qr/{short_code}")
async def update_dynamic_qr(
    short_code: str,
    updates: dict = Body(...),
    current_user: dict = Depends(require_admin),
):
    """Update a dynamic QR code's destination (the magic - no reprint needed!)"""
    try:
        updates["updated_at"] = datetime.now(timezone.utc)
        result = await db.dynamic_qr_codes.update_one(
            {"short_code": short_code}, {"$set": updates}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="QR code not found")
        return {"success": True, "message": "QR destination updated successfully"}
    except Exception as e:
        logging.error(f"Failed to update dynamic QR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/dynamic-qr/{short_code}")
async def delete_dynamic_qr(
    short_code: str, current_user: dict = Depends(require_admin)
):
    """Delete a dynamic QR code"""
    try:
        result = await db.dynamic_qr_codes.delete_one({"short_code": short_code})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="QR code not found")
        return {"success": True, "message": "QR code deleted"}
    except Exception as e:
        logging.error(f"Failed to delete dynamic QR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Public endpoint - this is the redirect that the printed QR points to
@router.get("/qr/{short_code}")
async def redirect_qr(short_code: str, request: Request):
    """Public redirect endpoint for dynamic QR codes"""
    try:
        qr_entry = await db.dynamic_qr_codes.find_one(
            {"short_code": short_code, "is_active": True}
        )

        if not qr_entry:
            # Fallback to homepage if QR not found
            return RedirectResponse(url="/", status_code=302)

        # Track the scan
        await db.dynamic_qr_codes.update_one(
            {"short_code": short_code}, {"$inc": {"scan_count": 1}}
        )

        # Log scan details
        scan_log = {
            "short_code": short_code,
            "destination": qr_entry["destination_url"],
            "user_agent": request.headers.get("user-agent", ""),
            "ip": request.client.host if request.client else "unknown",
            "scanned_at": datetime.now(timezone.utc),
        }
        await db.qr_scan_logs.insert_one(scan_log)

        return RedirectResponse(url=qr_entry["destination_url"], status_code=302)
    except Exception as e:
        logging.error(f"QR redirect error: {e}")
        return RedirectResponse(url="/", status_code=302)


@router.get("/admin/dynamic-qr/{short_code}/stats")
async def get_qr_stats(short_code: str, current_user: dict = Depends(require_admin)):
    """Get scan statistics for a specific QR code"""
    try:
        qr_entry = await db.dynamic_qr_codes.find_one({"short_code": short_code})
        if not qr_entry:
            raise HTTPException(status_code=404, detail="QR code not found")

        # Get scan history
        scans = (
            await db.qr_scan_logs.find({"short_code": short_code})
            .sort("scanned_at", -1)
            .to_list(100)
        )

        # Stats
        total_scans = qr_entry.get("scan_count", 0)

        return {
            "success": True,
            "short_code": short_code,
            "total_scans": total_scans,
            "recent_scans": [
                {
                    "scanned_at": s.get("scanned_at"),
                    "user_agent": s.get("user_agent", "")[:50],
                }
                for s in scans[:20]
            ],
        }
    except Exception as e:
        logging.error(f"Failed to get QR stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= QR CODE DECODE & HISTORY =============
# Upload old QR codes to decode and redirect


@router.post("/admin/qr/decode")
async def decode_qr_image(request: Request):
    """Decode a QR code image to extract the URL inside"""
    await require_admin(request)
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        from PIL import Image
        import io
        import base64

        body = await request.json()
        image_data = body.get("image")  # Base64 encoded image

        if not image_data:
            raise HTTPException(status_code=400, detail="No image data provided")

        # Remove data URL prefix if present
        if "base64," in image_data:
            image_data = image_data.split("base64,")[1]

        # Decode base64 to bytes
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Decode QR code
        decoded_objects = pyzbar_decode(image)

        if not decoded_objects:
            return {
                "success": False,
                "message": "No QR code found in image",
                "url": None,
            }

        # Get the URL from the first QR code found
        qr_data = decoded_objects[0].data.decode("utf-8")

        return {
            "success": True,
            "url": qr_data,
            "message": "QR code decoded successfully",
        }
    except Exception as e:
        logging.error(f"Failed to decode QR: {e}")
        return {"success": False, "message": str(e), "url": None}


@router.post("/admin/qr/import")
async def import_old_qr(request: Request):
    """Import an old QR code and create a redirect for it"""
    await require_admin(request)
    try:
        body = await request.json()
        original_url = body.get("original_url")  # The URL in the old QR
        new_destination = body.get("new_destination")  # Where it should now go
        name = body.get("name", "Imported QR")
        description = body.get("description", "")
        qr_image_data = body.get("qr_image")  # Base64 image to save

        if not original_url:
            raise HTTPException(status_code=400, detail="Original URL is required")

        # Check if this URL already has a redirect
        existing = await db.qr_url_redirects.find_one({"original_url": original_url})
        if existing:
            # Update existing redirect
            await db.qr_url_redirects.update_one(
                {"original_url": original_url},
                {
                    "$set": {
                        "destination_url": new_destination
                        or existing.get("destination_url"),
                        "name": name,
                        "description": description,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
            return {
                "success": True,
                "message": "QR redirect updated",
                "id": str(existing["_id"]),
            }

        # Create new redirect entry
        redirect_entry = {
            "id": str(uuid.uuid4()),
            "original_url": original_url,
            "destination_url": new_destination or original_url,
            "name": name,
            "description": description,
            "qr_image": qr_image_data,  # Store the QR image
            "scan_count": 0,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.qr_url_redirects.insert_one(redirect_entry)

        return {
            "success": True,
            "message": "QR code imported successfully",
            "redirect": redirect_entry,
        }
    except Exception as e:
        logging.error(f"Failed to import QR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/qr/history")
async def get_qr_history(request: Request):
    """Get all QR codes history (generated + imported)"""
    await require_admin(request)
    try:
        # Get dynamic QR codes
        dynamic_qrs = (
            await db.dynamic_qr_codes.find({}, {"_id": 0})
            .sort("created_at", -1)
            .to_list(500)
        )

        # Get imported QR redirects
        imported_qrs = (
            await db.qr_url_redirects.find({}, {"_id": 0})
            .sort("created_at", -1)
            .to_list(500)
        )

        # Get generated QR history
        generated_qrs = (
            await db.qr_generation_history.find({}, {"_id": 0})
            .sort("created_at", -1)
            .to_list(500)
        )

        return {
            "success": True,
            "dynamic_qr_codes": dynamic_qrs,
            "imported_redirects": imported_qrs,
            "generated_history": generated_qrs,
            "total_count": len(dynamic_qrs) + len(imported_qrs) + len(generated_qrs),
        }
    except Exception as e:
        logging.error(f"Failed to get QR history: {e}")
        return {
            "success": False,
            "dynamic_qr_codes": [],
            "imported_redirects": [],
            "generated_history": [],
        }


@router.post("/admin/qr/save-generated")
async def save_generated_qr(request: Request):
    """Save a newly generated QR code to history"""
    await require_admin(request)
    try:
        body = await request.json()

        qr_entry = {
            "id": str(uuid.uuid4()),
            "url": body.get("url"),
            "name": body.get("name", "Generated QR"),
            "description": body.get("description", ""),
            "qr_image": body.get("qr_image"),  # Base64 QR image
            "qr_type": body.get("qr_type", "custom"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.qr_generation_history.insert_one(qr_entry)

        return {"success": True, "message": "QR saved to history", "qr": qr_entry}
    except Exception as e:
        logging.error(f"Failed to save QR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/qr/redirect/{redirect_id}")
async def update_qr_redirect(redirect_id: str, request: Request):
    """Update an imported QR's destination URL"""
    await require_admin(request)
    try:
        body = await request.json()
        new_destination = body.get("destination_url")

        result = await db.qr_url_redirects.update_one(
            {"id": redirect_id},
            {
                "$set": {
                    "destination_url": new_destination,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Redirect not found")

        return {"success": True, "message": "Redirect updated successfully"}
    except Exception as e:
        logging.error(f"Failed to update redirect: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/qr/history/{qr_id}")
async def delete_qr_from_history(qr_id: str, request: Request):
    """Delete a QR from history"""
    await require_admin(request)
    try:
        # Try to delete from all collections
        await db.qr_generation_history.delete_one({"id": qr_id})
        await db.qr_url_redirects.delete_one({"id": qr_id})

        return {"success": True, "message": "QR deleted from history"}
    except Exception as e:
        logging.error(f"Failed to delete QR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= ABANDONED CARTS SYSTEM =============
# Tracks cart abandonment and enables recovery via Email/WhatsApp
# Threshold: 1 hour of inactivity marks a cart as abandoned


class AbandonedCartContact(BaseModel):
    session_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    checkout_step: Optional[str] = "cart"  # cart, shipping, payment


@router.post("/checkout/track-contact")
async def track_checkout_contact(contact: AbandonedCartContact):
    """Track customer contact info during checkout for abandoned cart recovery"""
    try:
        # Update cart with contact info
        update_data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "checkout_step": contact.checkout_step,
        }
        if contact.email:
            update_data["customer_email"] = contact.email
        if contact.phone:
            update_data["customer_phone"] = contact.phone
        if contact.name:
            update_data["customer_name"] = contact.name

        await db.carts.update_one(
            {"session_id": contact.session_id}, {"$set": update_data}
        )
        return {"success": True}
    except Exception as e:
        logging.error(f"Failed to track checkout contact: {e}")
        return {"success": False}


@router.get("/admin/abandoned-carts")
async def get_abandoned_carts(
    current_user: dict = Depends(get_current_user), hours: int = 1, limit: int = 100
):
    """Get all abandoned carts (carts inactive for more than specified hours)"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Calculate cutoff time (default 1 hour)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Find carts that:
    # 1. Have items
    # 2. Were last updated before cutoff time
    # 3. Don't have a corresponding completed order

    abandoned_carts = []

    try:
        # Get all carts with items that haven't been updated recently
        carts = (
            await db.carts.find(
                {
                    "items": {"$exists": True, "$ne": []},
                    "$or": [
                        {"updated_at": {"$lt": cutoff_time.isoformat()}},
                        {
                            "updated_at": {
                                "$lt": cutoff_time.strftime("%Y-%m-%dT%H:%M:%S")
                            }
                        },
                    ],
                },
                {"_id": 0},
            )
            .sort("updated_at", -1)
            .to_list(limit)
        )

        # Get list of completed order session IDs to exclude
        completed_orders = await db.orders.find(
            {"status": {"$in": ["completed", "shipped", "delivered", "processing"]}},
            {"session_id": 1, "_id": 0},
        ).to_list(10000)
        completed_session_ids = {
            o.get("session_id") for o in completed_orders if o.get("session_id")
        }

        # Fetch all product details in one query for efficiency
        all_product_ids = set()
        for cart in carts:
            for item in cart.get("items", []):
                all_product_ids.add(item.get("product_id"))

        products_list = await db.products.find(
            {
                "$or": [
                    {"id": {"$in": list(all_product_ids)}},
                    {"slug": {"$in": list(all_product_ids)}},
                ]
            },
            {"_id": 0, "id": 1, "slug": 1, "name": 1, "price": 1, "images": 1},
        ).to_list(len(all_product_ids) * 2)

        products_dict = {}
        for p in products_list:
            products_dict[p["id"]] = p
            if p.get("slug"):
                products_dict[p["slug"]] = p

        for cart in carts:
            session_id = cart.get("session_id")

            # Skip if this cart resulted in a completed order
            if session_id in completed_session_ids:
                continue

            # Calculate cart total and build items with details
            items = []
            total = 0
            for item in cart.get("items", []):
                product = products_dict.get(item.get("product_id"))
                if product:
                    item_total = float(product.get("price", 0)) * item.get(
                        "quantity", 1
                    )
                    total += item_total
                    items.append(
                        {
                            "name": product.get("name", "Unknown Product"),
                            "quantity": item.get("quantity", 1),
                            "price": float(product.get("price", 0)),
                            "image": (
                                product.get("images", [""])[0]
                                if product.get("images")
                                else ""
                            ),
                        }
                    )

            if items:  # Only include carts with valid products
                abandoned_cart = {
                    "id": f"cart_{session_id[:8]}",
                    "session_id": session_id,
                    "customer_email": cart.get("customer_email"),
                    "customer_phone": cart.get("customer_phone"),
                    "customer_name": cart.get("customer_name", "Guest"),
                    "items": items,
                    "total": total,
                    "currency": "CAD",
                    "abandoned_at": cart.get("updated_at"),
                    "checkout_step": cart.get("checkout_step", "cart"),
                    "recovery_email_sent": cart.get("recovery_email_sent", False),
                    "recovery_whatsapp_sent": cart.get("recovery_whatsapp_sent", False),
                    "recovered": False,
                    "shipping_address": cart.get("shipping_address"),
                }
                abandoned_carts.append(abandoned_cart)

        # Calculate stats
        total_value = sum(c["total"] for c in abandoned_carts)
        recovered_carts = [c for c in abandoned_carts if c.get("recovered")]
        recovered_value = sum(c["total"] for c in recovered_carts)

        return {
            "carts": abandoned_carts,
            "stats": {
                "total": len(abandoned_carts),
                "totalValue": total_value,
                "recovered": len(recovered_carts),
                "recoveredValue": recovered_value,
            },
        }
    except Exception as e:
        logging.error(f"Failed to fetch abandoned carts: {e}")
        return {
            "carts": [],
            "stats": {"total": 0, "totalValue": 0, "recovered": 0, "recoveredValue": 0},
        }


@router.post("/admin/abandoned-carts/{cart_id}/send-recovery-email")
async def send_abandoned_cart_recovery_email(
    cart_id: str, current_user: dict = Depends(get_current_user)
):
    """Send recovery email for abandoned cart"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Extract session_id from cart_id
    session_id = cart_id.replace("cart_", "")

    # Find the cart
    cart = await db.carts.find_one({"session_id": session_id})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    email = cart.get("customer_email")
    if not email:
        raise HTTPException(
            status_code=400, detail="No email address available for this cart"
        )

    # Here you would integrate with your email service (Resend, SendGrid, etc.)
    # For now, we'll mark it as sent

    await db.carts.update_one(
        {"session_id": cart["session_id"]},
        {
            "$set": {
                "recovery_email_sent": True,
                "recovery_email_sent_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"success": True, "message": f"Recovery email sent to {email}"}


@router.post("/admin/abandoned-carts/{cart_id}/send-whatsapp")
async def send_abandoned_cart_whatsapp(
    cart_id: str, current_user: dict = Depends(get_current_user)
):
    """Send WhatsApp recovery message for abandoned cart (WHAPI integration)"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Extract session_id from cart_id
    session_id = cart_id.replace("cart_", "")

    # Find the cart
    cart = await db.carts.find_one({"session_id": session_id})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    phone = cart.get("customer_phone")
    if not phone:
        raise HTTPException(
            status_code=400, detail="No phone number available for this cart"
        )

    # Here you would integrate with WHAPI
    # For now, we'll mark it as sent

    await db.carts.update_one(
        {"session_id": cart["session_id"]},
        {
            "$set": {
                "recovery_whatsapp_sent": True,
                "recovery_whatsapp_sent_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"success": True, "message": f"WhatsApp recovery sent to {phone}"}


@router.delete("/admin/abandoned-carts/{cart_id}")
async def delete_abandoned_cart(
    cart_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete an abandoned cart from tracking"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Try to find by id field first (UUID), then by session_id
    result = await db.carts.delete_one({"id": cart_id})
    
    if result.deleted_count == 0:
        # Fallback: try session_id with cart_ prefix removed
        session_id = cart_id.replace("cart_", "")
        result = await db.carts.delete_one({"session_id": session_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cart not found")

    return {"success": True, "message": "Cart deleted"}


# ============= ADMIN ANALYTICS API =============
# Server-side analytics to avoid client-side tracking overhead


@router.get("/admin/analytics")
async def get_admin_analytics(
    request: Request, days: int = 30, brand: Optional[str] = None
):
    """Get admin analytics data (server-side computed)"""
    current_user = await require_admin(request)
    
    try:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        start_date_str = start_date.isoformat()

        # Base date query
        date_query = {
            "$or": [
                {"created_at": {"$gte": start_date_str}},
                {"created_at": {"$gte": start_date.strftime("%Y-%m-%dT%H:%M:%S")}},
            ]
        }
        
        # Add brand filter if specified
        order_query = {**date_query}
        if brand and brand != "all":
            if brand == "lavela":
                order_query["$or"] = [
                    {"brand": "lavela"},
                    {"items.brand": "lavela"},
                ]
            elif brand == "reroots":
                order_query["brand"] = {"$ne": "lavela"}

        # Total orders in period
        orders = await db.orders.find(
            order_query,
            {"_id": 0, "total": 1, "status": 1},
        ).to_list(10000)

        total_orders = len(orders)
        completed_orders = [
            o
            for o in orders
            if o.get("status") in ["completed", "shipped", "delivered"]
        ]
        total_revenue = sum(float(o.get("total", 0)) for o in completed_orders)

        # Sessions (unique carts)
        total_sessions = await db.carts.count_documents(
            {
                "$or": [
                    {"updated_at": {"$gte": start_date_str}},
                    {"updated_at": {"$gte": start_date.strftime("%Y-%m-%dT%H:%M:%S")}},
                ]
            }
        )

        # Calculate metrics
        conversion_rate = (
            (total_orders / total_sessions * 100) if total_sessions > 0 else 0
        )
        aov = (total_revenue / len(completed_orders)) if completed_orders else 0

        # Get abandoned cart stats
        abandoned_response = await get_abandoned_carts(
            current_user, hours=1, limit=1000
        )
        abandoned_stats = abandoned_response.get("stats", {})

        recovery_rate = (
            (
                abandoned_stats.get("recovered", 0)
                / abandoned_stats.get("total", 1)
                * 100
            )
            if abandoned_stats.get("total", 0) > 0
            else 0
        )

        return {
            "period_days": days,
            "total_orders": total_orders,
            "completed_orders": len(completed_orders),
            "total_revenue": round(total_revenue, 2),
            "total_sessions": total_sessions,
            "conversion_rate": round(conversion_rate, 2),
            "average_order_value": round(aov, 2),
            "abandoned_carts": abandoned_stats.get("total", 0),
            "abandoned_value": round(abandoned_stats.get("totalValue", 0), 2),
            "recovered_carts": abandoned_stats.get("recovered", 0),
            "recovered_value": round(abandoned_stats.get("recoveredValue", 0), 2),
            "recovery_rate": round(recovery_rate, 2),
        }
    except Exception as e:
        logging.error(f"Analytics error: {e}")
        return {
            "period_days": days,
            "total_orders": 0,
            "completed_orders": 0,
            "total_revenue": 0,
            "total_sessions": 0,
            "conversion_rate": 0,
            "average_order_value": 0,
            "abandoned_carts": 0,
            "abandoned_value": 0,
            "recovered_carts": 0,
            "recovered_value": 0,
            "recovery_rate": 0,
        }


# ============ AI INTELLIGENCE & DATA GOLD MINE ============


@router.get("/admin/ai-intelligence/insights")
async def get_ai_intelligence_insights(
    current_user: dict = Depends(get_current_user)
):
    """
    AI Intelligence Dashboard - Aggregates all data sources for insights.
    Pulls from quiz, orders, abandoned carts, reviews, loyalty, and email logs.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Get date ranges
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)
        
        # ====== QUIZ DATA ======
        quiz_data = await db.quiz_responses.find({}, {"_id": 0}).to_list(1000)
        quiz_count = len(quiz_data)
        quiz_converted = len([q for q in quiz_data if q.get("converted")])
        quiz_conversion_rate = (quiz_converted / quiz_count * 100) if quiz_count > 0 else 0
        
        # Top skin concerns from quizzes
        concerns_count = {}
        for q in quiz_data:
            for concern in q.get("concerns", []):
                concerns_count[concern] = concerns_count.get(concern, 0) + 1
        top_concerns = sorted(concerns_count.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # ====== ORDER DATA ======
        orders = await db.orders.find(
            {"status": {"$in": ["completed", "shipped", "delivered", "processing"]}},
            {"_id": 0, "total": 1, "customer_id": 1, "created_at": 1, "email": 1}
        ).to_list(10000)
        
        total_orders = len(orders)
        total_revenue = sum(float(o.get("total", 0)) for o in orders)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Repeat customer analysis
        customer_orders = {}
        for o in orders:
            cid = o.get("customer_id") or o.get("email", "unknown")
            customer_orders[cid] = customer_orders.get(cid, 0) + 1
        repeat_customers = len([c for c, count in customer_orders.items() if count > 1])
        repeat_rate = (repeat_customers / len(customer_orders) * 100) if customer_orders else 0
        
        # ====== ABANDONED CART DATA ======
        abandoned = await db.abandoned_carts.find({}, {"_id": 0}).to_list(1000)
        if not abandoned:
            # Fallback to carts collection for abandoned cart analysis
            cutoff = now - timedelta(hours=1)
            abandoned = await db.carts.find(
                {"items": {"$exists": True, "$ne": []}},
                {"_id": 0, "total": 1, "recovered": 1, "recovery_revenue": 1}
            ).to_list(1000)
        
        abandoned_count = len(abandoned)
        abandoned_value = sum(float(a.get("cart_value", a.get("total", 0))) for a in abandoned)
        recovered = len([a for a in abandoned if a.get("recovered")])
        recovery_rate = (recovered / abandoned_count * 100) if abandoned_count > 0 else 0
        recovered_revenue = sum(float(a.get("recovery_revenue", 0)) for a in abandoned if a.get("recovered"))
        
        # ====== REVIEW DATA ======
        reviews = await db.reviews.find({}, {"_id": 0, "rating": 1, "created_at": 1}).to_list(1000)
        review_count = len(reviews)
        avg_rating = sum(r.get("rating", 0) for r in reviews) / review_count if review_count > 0 else 0
        five_star_reviews = len([r for r in reviews if r.get("rating") == 5])
        five_star_rate = (five_star_reviews / review_count * 100) if review_count > 0 else 0
        
        # ====== LOYALTY DATA ======
        loyalty_transactions = await db.loyalty_transactions.find({}, {"_id": 0}).to_list(10000)
        total_points_earned = sum(t.get("points", 0) for t in loyalty_transactions if t.get("type") in ["earn", "bonus", "gift_received"])
        total_points_redeemed = sum(abs(t.get("points", 0)) for t in loyalty_transactions if t.get("type") == "redeem")
        redemption_rate = (total_points_redeemed / total_points_earned * 100) if total_points_earned > 0 else 0
        
        # Loyalty members count
        loyalty_members = await db.customers.count_documents({"loyalty_balance": {"$gt": 0}})
        
        # ====== EMAIL ENGAGEMENT (CRM) ======
        email_logs = await db.email_log.find({}, {"_id": 0}).to_list(10000)
        emails_sent = len(email_logs)
        emails_opened = len([e for e in email_logs if e.get("opened")])
        emails_clicked = len([e for e in email_logs if e.get("clicked")])
        open_rate = (emails_opened / emails_sent * 100) if emails_sent > 0 else 0
        click_rate = (emails_clicked / emails_sent * 100) if emails_sent > 0 else 0
        
        # Best performing CRM day
        day_performance = {}
        for e in email_logs:
            day = e.get("day", "unknown")
            if day not in day_performance:
                day_performance[day] = {"sent": 0, "opened": 0, "converted": 0}
            day_performance[day]["sent"] += 1
            if e.get("opened"):
                day_performance[day]["opened"] += 1
            if e.get("converted"):
                day_performance[day]["converted"] += 1
        
        best_crm_day = max(day_performance.items(), key=lambda x: x[1].get("opened", 0))[0] if day_performance else "N/A"
        
        # ====== CUSTOMER DATA ======
        total_customers = await db.customers.count_documents({})
        customers_with_phone = await db.customers.count_documents({"phone": {"$exists": True, "$ne": None}})
        phone_capture_rate = (customers_with_phone / total_customers * 100) if total_customers > 0 else 0
        
        # ====== AUTOMATION FLOW STATS ======
        # 28-day cycle active
        crm_actions = await db.crm_actions.find({"status": "pending"}, {"_id": 0}).to_list(10000)
        pending_crm_actions = len(crm_actions)
        
        # Waitlist signups
        waitlist_count = await db.waitlist.count_documents({})
        
        return {
            "generated_at": now.isoformat(),
            "data_summary": {
                "total_customers": total_customers,
                "customers_with_phone": customers_with_phone,
                "phone_capture_rate": round(phone_capture_rate, 1),
                "total_orders": total_orders,
                "total_revenue": round(total_revenue, 2),
                "avg_order_value": round(avg_order_value, 2),
                "repeat_rate": round(repeat_rate, 1),
                "loyalty_members": loyalty_members
            },
            "quiz_insights": {
                "total_completions": quiz_count,
                "conversion_rate": round(quiz_conversion_rate, 1),
                "top_concerns": top_concerns
            },
            "abandoned_cart_insights": {
                "total_abandoned": abandoned_count,
                "total_value": round(abandoned_value, 2),
                "recovered_count": recovered,
                "recovery_rate": round(recovery_rate, 1),
                "recovered_revenue": round(recovered_revenue, 2)
            },
            "review_insights": {
                "total_reviews": review_count,
                "avg_rating": round(avg_rating, 1),
                "five_star_rate": round(five_star_rate, 1)
            },
            "loyalty_insights": {
                "total_earned": total_points_earned,
                "total_redeemed": total_points_redeemed,
                "redemption_rate": round(redemption_rate, 1),
                "active_members": loyalty_members
            },
            "email_insights": {
                "total_sent": emails_sent,
                "open_rate": round(open_rate, 1),
                "click_rate": round(click_rate, 1),
                "best_performing_day": best_crm_day
            },
            "automation_status": {
                "pending_crm_actions": pending_crm_actions,
                "waitlist_signups": waitlist_count
            },
            "action_items": [
                f"Quiz conversion at {round(quiz_conversion_rate, 1)}% - optimize follow-up sequence" if quiz_conversion_rate < 20 else None,
                f"Recovery rate at {round(recovery_rate, 1)}% - enhance win-back emails" if recovery_rate < 15 else None,
                f"Phone capture at {round(phone_capture_rate, 1)}% - add phone field to forms" if phone_capture_rate < 50 else None,
                f"{pending_crm_actions} pending WhatsApp messages to send" if pending_crm_actions > 0 else None
            ]
        }
    except Exception as e:
        print(f"AI Intelligence error: {e}")
        return {
            "error": str(e),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_summary": {"total_customers": 0, "total_orders": 0}
        }


# ============= CRM - CUSTOMER RELATIONSHIP MANAGEMENT =============

@router.get("/admin/customers")
async def get_customers_list(
    current_user: dict = Depends(get_current_user),
    vip: bool = None,
    min_ltv: float = None,
    min_orders: int = None,
    whatsapp: bool = None
):
    """
    Get all customers with LTV, VIP status, and order counts.
    Supports filtering by vip, min_ltv, min_orders, and whatsapp opted-in.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    filters = {}
    if vip is not None:
        filters["vip"] = vip
    if min_ltv is not None:
        filters["min_ltv"] = min_ltv
    if min_orders is not None:
        filters["min_orders"] = min_orders
    if whatsapp is not None:
        filters["whatsapp"] = whatsapp
    
    try:
        customers = await get_all_customers_summary(filters if filters else None)
        return customers
    except Exception as e:
        logging.error(f"[CRM] Error fetching customers: {e}")
        return []


@router.get("/admin/customers/{email}")
async def get_customer_detail(
    email: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get complete customer record including full order history.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await get_customer_full_record(email)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.patch("/admin/customers/{email}/notes")
async def update_customer_notes_endpoint(
    email: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Update admin notes for a customer.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    body = await request.json()
    notes = body.get("notes", "")
    
    success = await update_customer_notes(email, notes)
    
    if not success:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return {"success": True}


# ============= REFUND & RETURN MANAGEMENT =============

@router.post("/refunds/request")
async def request_refund_endpoint(request: Request):
    """
    Customer submits a refund request.
    No authentication required - uses order email verification.
    """
    body = await request.json()
    
    order_id = body.get("order_id")
    customer_email = body.get("email")
    reason = body.get("reason")
    refund_type = body.get("refund_type", "full")
    photos = body.get("photos", [])
    
    if not order_id or not customer_email or not reason:
        raise HTTPException(status_code=400, detail="order_id, email, and reason are required")
    
    result = await request_refund(order_id, customer_email, reason, refund_type, photos)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Refund request failed"))
    
    return result


@router.get("/admin/refunds")
async def get_refunds_list(
    current_user: dict = Depends(get_current_user),
    status: str = None
):
    """
    Get all refund requests, optionally filtered by status.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    refunds = await get_refunds(status)
    return refunds


@router.patch("/admin/refunds/{refund_id}")
async def resolve_refund_endpoint(
    refund_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Admin resolves a refund request.
    action: 'approve' | 'reject' | 'store_credit'
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    body = await request.json()
    
    action = body.get("action")
    admin_name = body.get("admin_name", current_user.get("name", "Admin"))
    notes = body.get("notes", "")
    partial_amount = body.get("partial_amount")
    
    if action not in ["approve", "reject", "store_credit"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use: approve, reject, or store_credit")
    
    result = await resolve_refund(refund_id, action, admin_name, notes, partial_amount)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Resolution failed"))
    
    return result


# ============= SALES ANALYTICS DASHBOARD =============

@router.get("/admin/analytics/sales")
async def get_sales_analytics(
    current_user: dict = Depends(get_current_user),
    period: str = "daily"
):
    """
    Get sales dashboard data with revenue charts, top products, and summary stats.
    period: daily | weekly | monthly
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if period not in ["daily", "weekly", "monthly"]:
        period = "daily"
    
    try:
        data = await get_sales_dashboard(period)
        return data
    except Exception as e:
        logging.error(f"[Analytics] Sales dashboard error: {e}")
        return {
            "period": period,
            "summary": {"total_orders": 0, "total_revenue": 0, "avg_order_value": 0, "unique_customers": 0},
            "chart_data": [],
            "top_products": []
        }


@router.get("/admin/analytics/acquisition")
async def get_acquisition_analytics(
    current_user: dict = Depends(get_current_user)
):
    """
    Get acquisition source analytics and conversion funnel data.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        data = await get_acquisition_sources()
        return data
    except Exception as e:
        logging.error(f"[Analytics] Acquisition analytics error: {e}")
        return {
            "by_source": [],
            "funnel": {"visitors": 0, "quiz_completions": 0, "first_purchase": 0, "repeat_purchase": 0, "vip": 0}
        }


@router.get("/admin/analytics/revenue-metrics")
async def get_revenue_metrics_endpoint(
    current_user: dict = Depends(get_current_user)
):
    """
    Get key revenue metrics for quick dashboard cards.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        data = await get_revenue_metrics()
        return data
    except Exception as e:
        logging.error(f"[Analytics] Revenue metrics error: {e}")
        return {
            "today": {"orders": 0, "revenue": 0},
            "this_month": {"orders": 0, "revenue": 0},
            "last_month": {"orders": 0, "revenue": 0},
            "revenue_growth_percent": 0
        }


@router.get("/admin/automation-intelligence/flows")
async def get_automation_flows(
    current_user: dict = Depends(get_current_user)
):
    """Get all active automation flows with real-time stats"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        
        # ====== 28-DAY REPURCHASE CYCLE ======
        crm_actions = await db.crm_actions.find({}, {"_id": 0}).to_list(10000)
        day_breakdown = {}
        for action in crm_actions:
            day = action.get("type", "unknown")
            if day.startswith("day_"):
                day_num = day.replace("day_", "D")
                day_breakdown[day_num] = day_breakdown.get(day_num, 0) + 1
        
        # Calculate conversion from CRM
        crm_conversions = len([a for a in crm_actions if a.get("converted")])
        crm_total = len(crm_actions)
        crm_conversion_rate = (crm_conversions / crm_total * 100) if crm_total > 0 else 0
        
        # ====== ABANDONED CART WIN-BACK ======
        abandoned_carts = await db.abandoned_carts.find({}, {"_id": 0}).to_list(1000)
        if not abandoned_carts:
            abandoned_carts = await db.carts.find(
                {"items": {"$exists": True, "$ne": []}},
                {"_id": 0}
            ).to_list(1000)
        
        recovered = [c for c in abandoned_carts if c.get("recovered")]
        recovered_revenue = sum(float(c.get("recovery_revenue", c.get("total", 0))) for c in recovered)
        
        # ====== QUIZ FOLLOW-UP ======
        quiz_responses = await db.quiz_responses.find({}, {"_id": 0}).to_list(1000)
        quiz_converted = len([q for q in quiz_responses if q.get("converted")])
        
        # ====== DAY 21 REVIEW REQUESTS ======
        review_requests = await db.crm_actions.count_documents({"type": "day_21"})
        reviews_submitted = await db.reviews.count_documents({})
        review_submit_rate = (reviews_submitted / review_requests * 100) if review_requests > 0 else 0
        
        reviews = await db.reviews.find({}, {"_id": 0, "rating": 1}).to_list(1000)
        avg_rating = sum(r.get("rating", 0) for r in reviews) / len(reviews) if reviews else 0
        
        # ====== BIRTHDAY BONUS ======
        birthday_bonuses = await db.loyalty_transactions.count_documents({
            "type": "bonus",
            "source": "birthday"
        })
        birthday_roots = await db.loyalty_transactions.aggregate([
            {"$match": {"type": "bonus", "source": "birthday"}},
            {"$group": {"_id": None, "total": {"$sum": "$points"}}}
        ]).to_list(1)
        total_birthday_roots = birthday_roots[0]["total"] if birthday_roots else 0
        
        # ====== REFERRAL BONUS ======
        referral_bonuses = await db.loyalty_transactions.count_documents({
            "type": "bonus", 
            "source": "referral"
        })
        referral_roots = await db.loyalty_transactions.aggregate([
            {"$match": {"type": "bonus", "source": "referral"}},
            {"$group": {"_id": None, "total": {"$sum": "$points"}}}
        ]).to_list(1)
        total_referral_roots = referral_roots[0]["total"] if referral_roots else 0
        
        return {
            "flows": [
                {
                    "name": "28-Day Repurchase Cycle",
                    "status": "active",
                    "active_customers": crm_total,
                    "day_breakdown": day_breakdown,
                    "conversion_rate": round(crm_conversion_rate, 1)
                },
                {
                    "name": "Abandoned Cart Win-Back",
                    "status": "active",
                    "active": len(abandoned_carts),
                    "recovered": len(recovered),
                    "recovery_rate": round((len(recovered) / len(abandoned_carts) * 100) if abandoned_carts else 0, 1),
                    "revenue_saved": round(recovered_revenue, 2)
                },
                {
                    "name": "Quiz Follow-Up Sequence",
                    "status": "active",
                    "sent": len(quiz_responses),
                    "converted": quiz_converted,
                    "conversion_rate": round((quiz_converted / len(quiz_responses) * 100) if quiz_responses else 0, 1)
                },
                {
                    "name": "Day 21 Review Requests",
                    "status": "active",
                    "sent": review_requests,
                    "submitted": reviews_submitted,
                    "submit_rate": round(review_submit_rate, 1),
                    "avg_rating": round(avg_rating, 1)
                },
                {
                    "name": "Birthday Bonus Scheduler",
                    "status": "active",
                    "sent_this_month": birthday_bonuses,
                    "roots_awarded": total_birthday_roots
                },
                {
                    "name": "Referral Bonus Tracker",
                    "status": "active",
                    "conversions_this_month": referral_bonuses,
                    "roots_awarded": total_referral_roots
                }
            ],
            "generated_at": now.isoformat()
        }
    except Exception as e:
        print(f"Automation flows error: {e}")
        return {"flows": [], "error": str(e)}


# ============ WHATSAPP BROADCAST SYSTEM ============


@router.get("/admin/whatsapp-broadcast/customers")
async def get_whatsapp_opted_in_customers(
    filter: str = "all",
    brand: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all customers who opted in to WhatsApp updates.
    Filters: all, purchased, quiz_only, vip
    """
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Build query based on filter
        query = {"whatsapp_opted_in": True}
        
        # Add brand filter
        active_brand = brand or 'reroots'
        if active_brand == "lavela":
            query["$or"] = [{"brand": "lavela"}, {"preferences.brand": "lavela"}, {"source": "lavela"}]
        elif active_brand == "reroots":
            query["brand"] = {"$ne": "lavela"}
        
        if filter == "purchased":
            query["order_count"] = {"$gt": 0}
        elif filter == "quiz_only":
            query["order_count"] = {"$in": [0, None]}
            query["quiz_completed"] = True
        elif filter == "vip":
            query["order_count"] = {"$gte": 3}
        
        # Fetch customers
        customers = await db.customers.find(
            query,
            {"_id": 0, "password": 0, "password_hash": 0}
        ).to_list(1000)
        
        # Also check orders for whatsapp_opted_in flag with brand filter
        orders_query = {"whatsapp_opted_in": True}
        if active_brand == "lavela":
            orders_query["$or"] = [{"brand": "lavela"}, {"items.brand": "lavela"}]
        elif active_brand == "reroots":
            orders_query["brand"] = {"$ne": "lavela"}
            
        orders_with_optin = await db.orders.find(
            orders_query,
            {"_id": 0, "email": 1, "phone": 1, "first_name": 1, "last_name": 1, "customer_id": 1}
        ).to_list(1000)
        
        # Merge unique customers from orders
        existing_emails = {c.get("email", "").lower() for c in customers}
        for order in orders_with_optin:
            email = order.get("email", "").lower()
            if email and email not in existing_emails:
                customers.append({
                    "id": order.get("customer_id", email),
                    "email": email,
                    "name": f"{order.get('first_name', '')} {order.get('last_name', '')}".strip() or None,
                    "first_name": order.get("first_name"),
                    "phone": order.get("phone"),
                    "whatsapp_phone": order.get("phone"),
                    "whatsapp_opted_in": True,
                    "order_count": 1
                })
                existing_emails.add(email)
        
        # Calculate stats
        stats = {
            "total": len(customers),
            "purchased": len([c for c in customers if (c.get("order_count") or 0) > 0]),
            "quiz_only": len([c for c in customers if (c.get("order_count") or 0) == 0 and c.get("quiz_completed")]),
            "vip": len([c for c in customers if (c.get("order_count") or 0) >= 3])
        }
        
        return {
            "customers": customers,
            "stats": stats
        }
    except Exception as e:
        print(f"WhatsApp broadcast customers error: {e}")
        return {"customers": [], "stats": {"total": 0, "purchased": 0, "quiz_only": 0, "vip": 0}}


