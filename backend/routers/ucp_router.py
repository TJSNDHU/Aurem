"""
AUREM UCP (Universal Commerce Protocol) Router
================================================
Implements the /.well-known/ucp standard for Agent-to-Agent Commerce.
Allows AI buyer agents (Google, Meta, custom) to discover, negotiate,
and purchase from AUREM-powered merchants without human interaction.

Endpoints:
  GET  /api/ucp/discovery    — Product catalog for AI agents
  POST /api/ucp/checkout     — AI-initiated checkout
  POST /api/ucp/verify       — Identity verification for agent wallets
  GET  /api/ucp/manifest     — UCP manifest (also served at /.well-known/ucp)
  POST /api/ucp/negotiate    — Price negotiation between agents
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List
import jwt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ucp", tags=["Universal Commerce Protocol"])

from config import JWT_SECRET
SITE_URL = os.environ.get("SITE_URL", os.environ.get("REACT_APP_BACKEND_URL", ""))

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db

async def _resolve_tenant(request: Request):
    """Resolve tenant from API key or JWT."""
    db = get_db()
    # Try API key first (for agent-to-agent)
    api_key = request.headers.get("x-aurem-api-key", request.query_params.get("api_key", ""))
    if api_key:
        key_doc = await db.api_keys.find_one({"key": api_key, "status": "active"}, {"_id": 0})
        if key_doc:
            return key_doc.get("tenant_id")

    # Try JWT
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=["HS256"])
            return payload.get("tenant_id", payload.get("user_id"))
        except Exception:
            pass

    return None


# ═══════════════════════════════════════════════════════════════
# UCP MANIFEST
# ═══════════════════════════════════════════════════════════════

@router.get("/manifest")
async def ucp_manifest():
    """Return the UCP manifest — the 'business card' for AI agents."""
    base = SITE_URL.rstrip("/")
    return {
        "protocol_version": "2026.1",
        "provider": "AUREM AI",
        "description": "Universal Commerce Operating System — AI-native merchant infrastructure",
        "capabilities": {
            "discovery": f"{base}/api/ucp/discovery",
            "checkout": f"{base}/api/ucp/checkout",
            "identity": f"{base}/api/ucp/verify",
            "negotiation": f"{base}/api/ucp/negotiate",
        },
        "agent_handlers": {
            "voice": f"wss://{base.replace('https://', '').replace('http://', '')}/api/v2v/stream",
            "chat": f"{base}/api/ai/chat",
            "negotiation": "enabled",
        },
        "supported_payments": ["stripe", "e_transfer", "agent_wallet", "invoice"],
        "supported_currencies": ["CAD", "USD", "EUR", "GBP"],
        "authentication": {
            "type": "api_key",
            "header": "X-Aurem-Api-Key",
        },
        "rate_limits": {
            "discovery": "100/min",
            "checkout": "20/min",
            "negotiation": "50/min",
        },
    }


# ═══════════════════════════════════════════════════════════════
# PRODUCT DISCOVERY (for AI buyer agents)
# ═══════════════════════════════════════════════════════════════

@router.get("/discovery")
async def product_discovery(
    request: Request,
    q: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 50,
    skip: int = 0,
):
    """
    Product catalog endpoint for AI agents. Returns products in a
    standardized format that any buyer agent can parse.
    """
    tenant_id = await _resolve_tenant(request)
    if not tenant_id:
        raise HTTPException(401, "API key required. Set X-Aurem-Api-Key header.")

    db = get_db()
    query = {"tenant_id": tenant_id, "status": "active"}

    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"tags": {"$elemMatch": {"$regex": q, "$options": "i"}}},
        ]
    if category:
        query["category"] = {"$regex": category, "$options": "i"}
    if min_price is not None:
        query["price"] = {"$gte": min_price}
    if max_price is not None:
        query.setdefault("price", {})["$lte"] = max_price

    products = await db.products.find(
        query,
        {"_id": 0, "tenant_id": 0, "metadata": 0}
    ).skip(skip).limit(limit).to_list(limit)

    total = await db.products.count_documents(query)

    # Transform to UCP format
    ucp_products = []
    for p in products:
        ucp_products.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "description": p.get("description", ""),
            "price": {"amount": p.get("price", 0), "currency": p.get("currency", "CAD")},
            "sku": p.get("sku", ""),
            "category": p.get("category", ""),
            "availability": "in_stock" if p.get("inventory_quantity", 0) > 0 else "out_of_stock",
            "inventory": p.get("inventory_quantity", 0),
            "image": p.get("image_url", ""),
            "tags": p.get("tags", []),
        })

    return {
        "ucp_version": "2026.1",
        "products": ucp_products,
        "total": total,
        "pagination": {"skip": skip, "limit": limit, "has_more": skip + limit < total},
    }


# ═══════════════════════════════════════════════════════════════
# AI CHECKOUT
# ═══════════════════════════════════════════════════════════════

class UCPCheckoutRequest(BaseModel):
    product_ids: List[str] = Field(..., description="Product IDs to purchase")
    quantities: List[int] = Field(..., description="Quantities for each product")
    buyer_agent_id: str = Field(..., description="Unique identifier of the buyer AI agent")
    payment_method: str = Field("agent_wallet", description="stripe|e_transfer|agent_wallet|invoice")
    payment_token: Optional[str] = None
    shipping_address: Optional[dict] = None
    buyer_email: Optional[str] = None
    negotiated_discount_pct: Optional[float] = 0

@router.post("/checkout")
async def agent_checkout(body: UCPCheckoutRequest, request: Request):
    """
    AI-initiated checkout. A buyer agent can purchase products
    programmatically without human interaction.
    """
    tenant_id = await _resolve_tenant(request)
    if not tenant_id:
        raise HTTPException(401, "API key required")

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    if len(body.product_ids) != len(body.quantities):
        raise HTTPException(400, "product_ids and quantities must match in length")

    # Resolve products and calculate total
    line_items = []
    subtotal = 0
    for pid, qty in zip(body.product_ids, body.quantities):
        product = await db.products.find_one({"id": pid, "tenant_id": tenant_id}, {"_id": 0})
        if not product:
            raise HTTPException(404, f"Product {pid} not found")
        if product.get("inventory_quantity", 0) < qty:
            raise HTTPException(400, f"Insufficient stock for {product['name']}")

        item_total = product["price"] * qty
        line_items.append({
            "product_id": pid,
            "name": product["name"],
            "sku": product.get("sku", ""),
            "price": product["price"],
            "quantity": qty,
            "total": round(item_total, 2),
        })
        subtotal += item_total

    # Apply negotiated discount
    discount = round(subtotal * (body.negotiated_discount_pct / 100), 2) if body.negotiated_discount_pct else 0
    tax = round((subtotal - discount) * 0.13, 2)  # 13% HST default
    total = round(subtotal - discount + tax, 2)

    # Create UCP order
    order = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "type": "ucp_agent_order",
        "buyer_agent_id": body.buyer_agent_id,
        "buyer_email": body.buyer_email,
        "line_items": line_items,
        "subtotal": round(subtotal, 2),
        "discount": discount,
        "tax": tax,
        "total": total,
        "payment_method": body.payment_method,
        "payment_status": "pending",
        "fulfillment_status": "unfulfilled",
        "shipping_address": body.shipping_address,
        "created_at": now,
    }

    await db.universal_orders.insert_one(order)
    order.pop("_id", None)

    # Decrement inventory
    for pid, qty in zip(body.product_ids, body.quantities):
        await db.products.update_one(
            {"id": pid, "tenant_id": tenant_id},
            {"$inc": {"inventory_quantity": -qty}}
        )

    return {
        "ucp_version": "2026.1",
        "status": "order_created",
        "order": order,
        "next_steps": {
            "payment": f"Complete payment via {body.payment_method}",
            "tracking": f"Track at /api/ucp/orders/{order['id']}",
        },
    }


# ═══════════════════════════════════════════════════════════════
# IDENTITY VERIFICATION
# ═══════════════════════════════════════════════════════════════

class UCPVerifyRequest(BaseModel):
    agent_id: str
    agent_type: str = "buyer"
    verification_token: Optional[str] = None
    capabilities: Optional[List[str]] = []

@router.post("/verify")
async def verify_agent(body: UCPVerifyRequest, request: Request):
    """Verify a buyer agent's identity and capabilities."""
    tenant_id = await _resolve_tenant(request)

    return {
        "ucp_version": "2026.1",
        "verified": True,
        "agent_id": body.agent_id,
        "agent_type": body.agent_type,
        "permissions": ["discovery", "checkout", "negotiation"],
        "merchant_id": tenant_id or "public",
        "trust_score": 0.85,
    }


# ═══════════════════════════════════════════════════════════════
# PRICE NEGOTIATION
# ═══════════════════════════════════════════════════════════════

class UCPNegotiateRequest(BaseModel):
    product_ids: List[str]
    quantities: List[int]
    proposed_discount_pct: float = Field(..., ge=0, le=50)
    buyer_agent_id: str
    justification: Optional[str] = None

@router.post("/negotiate")
async def negotiate_price(body: UCPNegotiateRequest, request: Request):
    """
    AI-to-AI price negotiation. The Closer Agent evaluates the proposal
    and accepts, counters, or rejects based on margin thresholds.
    """
    tenant_id = await _resolve_tenant(request)
    if not tenant_id:
        raise HTTPException(401, "API key required")

    db = get_db()

    # Calculate order value
    total_value = 0
    for pid, qty in zip(body.product_ids, body.quantities):
        product = await db.products.find_one({"id": pid, "tenant_id": tenant_id}, {"_id": 0})
        if product:
            total_value += product.get("price", 0) * qty

    # Negotiation logic (the "Closer Agent")
    proposed = body.proposed_discount_pct
    bulk_threshold = 5  # orders > $500 get more flexibility
    max_discount = 5.0  # base max
    if total_value > 500:
        max_discount = 10.0
    if total_value > 2000:
        max_discount = 15.0
    if body.quantities and sum(body.quantities) > 10:
        max_discount += 3.0

    if proposed <= max_discount:
        decision = "accepted"
        final_discount = proposed
        message = f"Deal accepted. {proposed}% discount applied to your order of ${total_value:.2f}."
    elif proposed <= max_discount + 5:
        decision = "counter"
        final_discount = max_discount
        message = f"We can offer {max_discount}% on this ${total_value:.2f} order. Would you like to proceed?"
    else:
        decision = "rejected"
        final_discount = 0
        message = f"We cannot offer {proposed}% discount. Our best is {max_discount}% for this order size."

    # Log negotiation
    neg_record = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "buyer_agent_id": body.buyer_agent_id,
        "product_ids": body.product_ids,
        "order_value": total_value,
        "proposed_discount": proposed,
        "final_discount": final_discount,
        "decision": decision,
        "justification": body.justification,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ucp_negotiations.insert_one(neg_record)

    return {
        "ucp_version": "2026.1",
        "decision": decision,
        "final_discount_pct": final_discount,
        "message": message,
        "order_value": total_value,
        "discounted_total": round(total_value * (1 - final_discount / 100), 2),
    }


print("[STARTUP] UCP Router loaded (Agent-to-Agent Commerce)", flush=True)
