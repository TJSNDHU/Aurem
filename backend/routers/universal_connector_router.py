"""
AUREM Universal Connector Router — Phase F
============================================
API endpoints for the Universal Commerce layer:
- Platform connections (connect any platform)
- CSV import (products + customers) with AI column matching
- Generic webhook receiver
- Product/customer/order management (universal)
- CSV template downloads
"""

import os
import io
import csv
import json
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import jwt

from services.universal_connector import (
    PLATFORM_TYPES, CSV_PRODUCT_TEMPLATE, CSV_CUSTOMER_TEMPLATE,
    match_columns_basic, match_columns_ai,
    parse_csv_products, parse_csv_customers,
    normalize_webhook_event, make_platform_connection, make_universal_product,
    shopify_order_to_universal, shopify_customer_to_universal,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/universal", tags=["Universal Connector"])

from config import JWT_SECRET

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db

async def _get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        return jwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


# ═══════════════════════════════════════════════════════════════
# PLATFORM CONNECTIONS
# ═══════════════════════════════════════════════════════════════

class PlatformConnectRequest(BaseModel):
    platform_type: str = Field(..., description="shopify|woocommerce|magento|square|clover|stripe|csv_manual|standalone")
    display_name: str = Field(..., description="Human-readable name for this connection")
    shop_domain: Optional[str] = None
    api_url: Optional[str] = None
    config: Optional[dict] = None

@router.get("/platforms")
async def list_supported_platforms():
    """List all supported platform types."""
    return {
        "platforms": [
            {"type": "shopify", "name": "Shopify", "status": "supported", "icon": "shopping-bag"},
            {"type": "woocommerce", "name": "WooCommerce", "status": "coming_soon", "icon": "globe"},
            {"type": "magento", "name": "Magento/Adobe Commerce", "status": "coming_soon", "icon": "server"},
            {"type": "square", "name": "Square POS", "status": "coming_soon", "icon": "credit-card"},
            {"type": "clover", "name": "Clover POS", "status": "coming_soon", "icon": "monitor"},
            {"type": "stripe", "name": "Stripe", "status": "scaffold", "icon": "zap"},
            {"type": "csv_manual", "name": "CSV Import", "status": "supported", "icon": "file-text"},
            {"type": "standalone", "name": "Standalone (Manual)", "status": "supported", "icon": "briefcase"},
        ],
        "total": len(PLATFORM_TYPES),
    }

@router.get("/connections")
async def list_connections(request: Request):
    """List all platform connections for this tenant."""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    connections = await db.platform_connections.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    # Also count products/customers per platform
    for conn in connections:
        pt = conn.get("platform_type", "")
        conn["products_synced"] = await db.products.count_documents({"tenant_id": tenant_id, "source_platform": pt})
        conn["customers_synced"] = await db.tenant_customers.count_documents({"tenant_id": tenant_id, "source": pt})

    return {"connections": connections, "total": len(connections)}


@router.post("/connections")
async def create_connection(body: PlatformConnectRequest, request: Request):
    """Register a new platform connection."""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    if body.platform_type not in PLATFORM_TYPES:
        raise HTTPException(400, f"Unsupported platform. Choose from: {PLATFORM_TYPES}")

    conn = make_platform_connection(
        tenant_id=tenant_id,
        platform_type=body.platform_type,
        display_name=body.display_name,
        shop_domain=body.shop_domain or "",
        api_url=body.api_url or "",
        config=body.config or {},
    )

    await db.platform_connections.insert_one(conn)
    conn.pop("_id", None)
    return {"success": True, "connection": conn}


@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str, request: Request):
    """Remove a platform connection."""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    result = await db.platform_connections.delete_one({"id": connection_id, "tenant_id": tenant_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Connection not found")
    return {"success": True, "deleted": connection_id}


# ═══════════════════════════════════════════════════════════════
# CSV IMPORT (Products + Customers)
# ═══════════════════════════════════════════════════════════════

@router.get("/templates/products")
async def download_product_template():
    """Download a CSV template for product imports."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_PRODUCT_TEMPLATE)
    writer.writerow(["Example Widget", "A great product", "29.99", "39.99", "WDG-001",
                      "123456789012", "Electronics", "widget,gadget", "100", "0.5", "kg",
                      "https://example.com/widget.jpg", "active"])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aurem_product_template.csv"}
    )


@router.get("/templates/customers")
async def download_customer_template():
    """Download a CSV template for customer imports."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_CUSTOMER_TEMPLATE)
    writer.writerow(["jane@example.com", "Jane", "Doe", "+1 555-0100", "Acme Inc",
                      "450.00", "3", "vip,returning", "Great customer"])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aurem_customer_template.csv"}
    )


class CSVAnalyzeResponse(BaseModel):
    headers: List[str]
    mapping: dict
    sample_rows: list
    data_type: str
    match_method: str
    row_count: int


@router.post("/import/analyze")
async def analyze_csv(request: Request, file: UploadFile = File(...), data_type: str = Form("products"), use_ai: bool = Form(True)):
    """
    Step 1 of CSV import: Upload file and get AI-matched column mapping.
    Returns the detected mapping for user review before actual import.
    """
    await _get_user(request)

    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        csv_text = content.decode("latin-1")

    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if len(rows) < 2:
        raise HTTPException(400, "CSV must have a header row and at least one data row")

    headers = rows[0]
    sample_rows = rows[1:4]

    # Try AI matching first, fall back to basic
    if use_ai:
        mapping = await match_columns_ai(headers, sample_rows, data_type)
        method = "ai"
    else:
        mapping = match_columns_basic(headers)
        method = "basic"

    # If AI returned nothing useful, fall back to basic
    if not mapping:
        mapping = match_columns_basic(headers)
        method = "basic_fallback"

    return {
        "headers": headers,
        "mapping": mapping,
        "sample_rows": sample_rows,
        "data_type": data_type,
        "match_method": method,
        "row_count": len(rows) - 1,
    }


class CSVImportRequest(BaseModel):
    csv_text: str
    column_mapping: dict
    data_type: str = "products"

@router.post("/import/execute")
async def execute_csv_import(body: CSVImportRequest, request: Request):
    """
    Step 2 of CSV import: Execute the import with the confirmed column mapping.
    """
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    if body.data_type == "products":
        records = parse_csv_products(body.csv_text, body.column_mapping, tenant_id)
        if records:
            await db.products.insert_many([{**r} for r in records])
            for r in records:
                r.pop("_id", None)
        return {"success": True, "imported": len(records), "type": "products", "records": records[:5]}

    elif body.data_type == "customers":
        records = parse_csv_customers(body.csv_text, body.column_mapping, tenant_id)
        if records:
            await db.tenant_customers.insert_many([{**r} for r in records])
            for r in records:
                r.pop("_id", None)
        return {"success": True, "imported": len(records), "type": "customers", "records": records[:5]}

    else:
        raise HTTPException(400, "data_type must be 'products' or 'customers'")


@router.post("/import/quick")
async def quick_csv_import(request: Request, file: UploadFile = File(...), data_type: str = Form("products")):
    """
    One-step CSV import: Auto-detect columns and import immediately.
    Best for files that use the AUREM template or have standard headers.
    """
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        csv_text = content.decode("latin-1")

    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if len(rows) < 2:
        raise HTTPException(400, "CSV must have at least a header and one data row")

    headers = rows[0]
    sample_rows = rows[1:4]

    # Try AI first, then basic
    mapping = await match_columns_ai(headers, sample_rows, data_type)
    if not mapping:
        mapping = match_columns_basic(headers)

    if data_type == "products":
        records = parse_csv_products(csv_text, mapping, tenant_id)
        if records:
            await db.products.insert_many([{**r} for r in records])
            for r in records:
                r.pop("_id", None)
        return {"success": True, "imported": len(records), "type": "products", "mapping_used": mapping}
    else:
        records = parse_csv_customers(csv_text, mapping, tenant_id)
        if records:
            await db.tenant_customers.insert_many([{**r} for r in records])
            for r in records:
                r.pop("_id", None)
        return {"success": True, "imported": len(records), "type": "customers", "mapping_used": mapping}


# ═══════════════════════════════════════════════════════════════
# PRODUCTS (Universal)
# ═══════════════════════════════════════════════════════════════

@router.get("/products")
async def list_products(request: Request, limit: int = 50, skip: int = 0, source: Optional[str] = None):
    """List all products from the universal catalog."""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    query = {"tenant_id": tenant_id}
    if source:
        query["source_platform"] = source

    products = await db.products.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    total = await db.products.count_documents(query)

    # Platform breakdown
    platform_pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {"$group": {"_id": "$source_platform", "count": {"$sum": 1}}}
    ]
    breakdown = await db.products.aggregate(platform_pipeline).to_list(20)
    by_platform = {b["_id"]: b["count"] for b in breakdown}

    return {"products": products, "total": total, "by_platform": by_platform}


class ManualProductCreate(BaseModel):
    name: str
    price: float
    description: Optional[str] = ""
    sku: Optional[str] = ""
    category: Optional[str] = ""
    tags: Optional[List[str]] = []
    inventory_quantity: Optional[int] = 0
    image_url: Optional[str] = ""
    currency: Optional[str] = "CAD"

@router.post("/products")
async def create_product(body: ManualProductCreate, request: Request):
    """Manually create a product in the universal catalog."""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    product = make_universal_product(
        name=body.name, price=body.price,
        source_platform="standalone", tenant_id=tenant_id,
        description=body.description, sku=body.sku,
        category=body.category, tags=body.tags or [],
        inventory_quantity=body.inventory_quantity or 0,
        image_url=body.image_url or "", currency=body.currency or "CAD",
    )

    await db.products.insert_one(product)
    product.pop("_id", None)
    return {"success": True, "product": product}


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, request: Request):
    """Delete a product."""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    result = await db.products.delete_one({"id": product_id, "tenant_id": tenant_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Product not found")
    return {"success": True, "deleted": product_id}


# ═══════════════════════════════════════════════════════════════
# GENERIC WEBHOOK RECEIVER
# ═══════════════════════════════════════════════════════════════

@router.post("/webhooks/{platform}")
async def receive_webhook(platform: str, request: Request):
    """
    Universal webhook receiver. Accepts events from any platform
    and normalizes them into universal events.
    Supported platforms: shopify, stripe, woocommerce, generic
    """
    db = get_db()

    # ── Stripe Signature Verification ──
    if platform == "stripe":
        import stripe as stripe_lib
        stripe_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        if stripe_webhook_secret:
            sig_header = request.headers.get("stripe-signature", "")
            raw_body = await request.body()
            try:
                stripe_lib.Webhook.construct_event(raw_body, sig_header, stripe_webhook_secret)
            except (stripe_lib.error.SignatureVerificationError, ValueError) as e:
                logger.warning(f"[Webhook] Stripe signature verification failed: {e}")
                raise HTTPException(400, "Invalid Stripe webhook signature")
            body = json.loads(raw_body)
        else:
            logger.warning("[Webhook] STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
            body = await request.json()
    elif platform == "shopify":
        # Bug-fix #181 (R22): Shopify webhook HMAC verification.
        import hmac as _hmac, hashlib as _hashlib, base64 as _base64
        secret = os.environ.get("SHOPIFY_WEBHOOK_SECRET") or os.environ.get("SHOPIFY_API_SECRET")
        raw_body = await request.body()
        sig = request.headers.get("X-Shopify-Hmac-Sha256", "") or request.headers.get("x-shopify-hmac-sha256", "")
        if secret:
            digest = _hmac.new(secret.encode("utf-8"), raw_body, _hashlib.sha256).digest()
            computed = _base64.b64encode(digest).decode("utf-8")
            if not (sig and _hmac.compare_digest(computed, sig)):
                raise HTTPException(401, "invalid Shopify webhook signature")
        elif os.environ.get("AUREM_ENV") == "production":
            raise HTTPException(500, "SHOPIFY_WEBHOOK_SECRET not configured")
        try:
            body = json.loads(raw_body) if raw_body else {}
        except Exception:
            body = {}
    elif platform == "woocommerce":
        # Bug-fix #181 (R22): WooCommerce webhook HMAC (base64 sha256).
        import hmac as _hmac, hashlib as _hashlib, base64 as _base64
        secret = os.environ.get("WOOCOMMERCE_WEBHOOK_SECRET", "")
        raw_body = await request.body()
        sig = request.headers.get("x-wc-webhook-signature", "")
        if secret:
            digest = _hmac.new(secret.encode("utf-8"), raw_body, _hashlib.sha256).digest()
            computed = _base64.b64encode(digest).decode("utf-8")
            if not (sig and _hmac.compare_digest(computed, sig)):
                raise HTTPException(401, "invalid WooCommerce webhook signature")
        elif os.environ.get("AUREM_ENV") == "production":
            raise HTTPException(500, "WOOCOMMERCE_WEBHOOK_SECRET not configured")
        try:
            body = json.loads(raw_body) if raw_body else {}
        except Exception:
            body = {}
    else:
        body = await request.json()

    # Resolve tenant from webhook payload or header
    tenant_id = None

    if platform == "shopify":
        shop_domain = request.headers.get("x-shopify-shop-domain", body.get("shop_domain", ""))
        if shop_domain:
            conn = await db.platform_connections.find_one(
                {"platform_type": "shopify", "shop_domain": shop_domain}, {"_id": 0}
            )
            if conn:
                tenant_id = conn.get("tenant_id")
        event_type = request.headers.get("x-shopify-topic", body.get("topic", "unknown"))

    elif platform == "stripe":
        event_type = body.get("type", "unknown")
        stripe_account = body.get("account", "")
        if stripe_account:
            conn = await db.platform_connections.find_one(
                {"platform_type": "stripe", "config.stripe_account": stripe_account}, {"_id": 0}
            )
            if conn:
                tenant_id = conn.get("tenant_id")

    elif platform == "woocommerce":
        event_type = request.headers.get("x-wc-webhook-topic", body.get("action", "unknown"))
        source_url = request.headers.get("x-wc-webhook-source", "")
        if source_url:
            conn = await db.platform_connections.find_one(
                {"platform_type": "woocommerce", "api_url": {"$regex": source_url}}, {"_id": 0}
            )
            if conn:
                tenant_id = conn.get("tenant_id")

    else:
        event_type = body.get("event_type", body.get("type", "custom"))
        tenant_id = body.get("tenant_id")

    if not tenant_id:
        # Try API key based auth
        api_key = request.headers.get("x-aurem-api-key", "")
        if api_key:
            key_doc = await db.api_keys.find_one({"key": api_key, "status": "active"}, {"_id": 0})
            if key_doc:
                tenant_id = key_doc.get("tenant_id")

    if not tenant_id:
        tenant_id = "unresolved"
        logger.warning(f"[Webhook] Unresolved tenant for {platform}/{event_type}")

    event = normalize_webhook_event(platform, event_type, body, tenant_id)

    # Route unresolved events to quarantine collection
    if tenant_id == "unresolved":
        await db["_unresolved_quarantine"].insert_one(event)
    else:
        await db.universal_events.insert_one(event)
    event.pop("_id", None)

    return {"received": True, "event_id": event["id"], "universal_type": event["event_type"]}


# ═══════════════════════════════════════════════════════════════
# UNIVERSAL DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def universal_stats(request: Request):
    """Get aggregated stats across all platforms for this tenant."""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    connections = await db.platform_connections.count_documents({"tenant_id": tenant_id})
    products = await db.products.count_documents({"tenant_id": tenant_id})
    customers = await db.tenant_customers.count_documents({"tenant_id": tenant_id})
    events = await db.universal_events.count_documents({"tenant_id": tenant_id})
    invoices = await db.invoices.count_documents({"tenant_id": tenant_id})

    # Products by platform
    prod_pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {"$group": {"_id": "$source_platform", "count": {"$sum": 1}}}
    ]
    prod_breakdown = await db.products.aggregate(prod_pipeline).to_list(20)

    return {
        "connections": connections,
        "products": products,
        "customers": customers,
        "events": events,
        "invoices": invoices,
        "products_by_platform": {b["_id"]: b["count"] for b in prod_breakdown},
    }


print("[STARTUP] Universal Connector Router loaded (Phase F)", flush=True)
