"""
AUREM Universal Connector Middleware
=====================================
The Central Nervous System for any merchant. Normalizes data from
Shopify, WooCommerce, Stripe, CSV uploads, or manual entry into
Universal Commerce Primitives.

Architecture:
  ExternalData -> Adapter -> UniversalModel -> MongoDB -> AUREM Brain

Adapters:
  - ShopifyAdapter: GraphQL Admin API
  - ManualAdapter: Invoice/Ledger system (Iteration 66)
  - CSVAdapter: File upload with AI column matching
  - StripeAdapter: Payment events
  - GenericWebhookAdapter: Any platform webhook
"""

import logging
import uuid
import csv
import io
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# ═══════════════════════════════════════════════════════════════
# UNIVERSAL DATA MODELS
# ═══════════════════════════════════════════════════════════════

PLATFORM_TYPES = [
    "shopify", "woocommerce", "magento", "square", "clover",
    "stripe", "csv_manual", "api_import", "standalone"
]


def make_universal_product(
    name: str,
    price: float,
    source_platform: str = "standalone",
    tenant_id: str = "",
    **kwargs
) -> dict:
    """Create a Universal Product record."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "name": name,
        "description": kwargs.get("description", ""),
        "price": round(price, 2),
        "compare_at_price": kwargs.get("compare_at_price"),
        "sku": kwargs.get("sku", ""),
        "barcode": kwargs.get("barcode", ""),
        "category": kwargs.get("category", ""),
        "tags": kwargs.get("tags", []),
        "inventory_quantity": kwargs.get("inventory_quantity", 0),
        "weight": kwargs.get("weight"),
        "weight_unit": kwargs.get("weight_unit", "kg"),
        "image_url": kwargs.get("image_url", ""),
        "status": kwargs.get("status", "active"),
        "source_platform": source_platform,
        "source_id": kwargs.get("source_id", ""),
        "currency": kwargs.get("currency", "CAD"),
        "variants": kwargs.get("variants", []),
        "metadata": kwargs.get("metadata", {}),
        "created_at": now,
        "updated_at": now,
    }


def make_universal_customer(
    email: str,
    source_platform: str = "standalone",
    tenant_id: str = "",
    **kwargs
) -> dict:
    """Create a Universal Customer record."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "email": email,
        "first_name": kwargs.get("first_name", ""),
        "last_name": kwargs.get("last_name", ""),
        "phone": kwargs.get("phone", ""),
        "company": kwargs.get("company", ""),
        "total_spend": kwargs.get("total_spend", 0.0),
        "orders_count": kwargs.get("orders_count", 0),
        "tags": kwargs.get("tags", []),
        "source_platform": source_platform,
        "source_id": kwargs.get("source_id", ""),
        "accepts_marketing": kwargs.get("accepts_marketing", False),
        "notes": kwargs.get("notes", ""),
        "metadata": kwargs.get("metadata", {}),
        "created_at": now,
        "updated_at": now,
    }


def make_universal_order(
    customer_email: str,
    total: float,
    source_platform: str = "standalone",
    tenant_id: str = "",
    **kwargs
) -> dict:
    """Create a Universal Order record."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "order_number": kwargs.get("order_number", f"ORD-{uuid.uuid4().hex[:8].upper()}"),
        "customer_email": customer_email,
        "customer_name": kwargs.get("customer_name", ""),
        "line_items": kwargs.get("line_items", []),
        "subtotal": kwargs.get("subtotal", total),
        "tax_amount": kwargs.get("tax_amount", 0),
        "total": round(total, 2),
        "currency": kwargs.get("currency", "CAD"),
        "status": kwargs.get("status", "pending"),
        "payment_status": kwargs.get("payment_status", "unpaid"),
        "payment_method": kwargs.get("payment_method", ""),
        "source_platform": source_platform,
        "source_id": kwargs.get("source_id", ""),
        "metadata": kwargs.get("metadata", {}),
        "created_at": now,
        "updated_at": now,
    }


# ═══════════════════════════════════════════════════════════════
# ADAPTER: SHOPIFY -> UNIVERSAL
# ═══════════════════════════════════════════════════════════════

def shopify_customer_to_universal(shopify_data: dict, tenant_id: str) -> dict:
    """Convert a Shopify GraphQL customer to Universal format."""
    return make_universal_customer(
        email=shopify_data.get("email", ""),
        source_platform="shopify",
        tenant_id=tenant_id,
        first_name=shopify_data.get("first_name", shopify_data.get("firstName", "")),
        last_name=shopify_data.get("last_name", shopify_data.get("lastName", "")),
        phone=shopify_data.get("phone", ""),
        total_spend=shopify_data.get("total_spend", shopify_data.get("totalSpent", {}).get("amount", 0)),
        orders_count=shopify_data.get("orders_count", shopify_data.get("ordersCount", 0)),
        tags=shopify_data.get("tags", []),
        source_id=shopify_data.get("shopify_customer_id", shopify_data.get("id", "")),
        accepts_marketing=shopify_data.get("accepts_marketing", shopify_data.get("acceptsMarketing", False)),
        metadata={"shopify_raw": {k: v for k, v in shopify_data.items() if k not in ("email", "first_name", "last_name")}},
    )


def shopify_product_to_universal(shopify_data: dict, tenant_id: str) -> dict:
    """Convert a Shopify product to Universal format."""
    price = 0
    variants = shopify_data.get("variants", [])
    if variants and isinstance(variants, list):
        first = variants[0] if isinstance(variants[0], dict) else {}
        price = float(first.get("price", 0))

    return make_universal_product(
        name=shopify_data.get("title", ""),
        price=price,
        source_platform="shopify",
        tenant_id=tenant_id,
        description=shopify_data.get("body_html", shopify_data.get("description", "")),
        sku=shopify_data.get("sku", ""),
        category=shopify_data.get("product_type", ""),
        tags=[t.strip() for t in shopify_data.get("tags", "").split(",")] if isinstance(shopify_data.get("tags"), str) else shopify_data.get("tags", []),
        status=shopify_data.get("status", "active"),
        source_id=shopify_data.get("id", ""),
        image_url=shopify_data.get("image", {}).get("src", "") if isinstance(shopify_data.get("image"), dict) else "",
        variants=variants,
    )


def shopify_order_to_universal(shopify_data: dict, tenant_id: str) -> dict:
    """Convert a Shopify order webhook payload to Universal format."""
    customer = shopify_data.get("customer", {})
    line_items = []
    for item in shopify_data.get("line_items", []):
        line_items.append({
            "name": item.get("title", item.get("name", "")),
            "quantity": item.get("quantity", 1),
            "price": float(item.get("price", 0)),
            "sku": item.get("sku", ""),
        })

    return make_universal_order(
        customer_email=customer.get("email", shopify_data.get("email", "")),
        total=float(shopify_data.get("total_price", 0)),
        source_platform="shopify",
        tenant_id=tenant_id,
        order_number=str(shopify_data.get("order_number", shopify_data.get("name", ""))),
        customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
        line_items=line_items,
        subtotal=float(shopify_data.get("subtotal_price", 0)),
        tax_amount=float(shopify_data.get("total_tax", 0)),
        currency=shopify_data.get("currency", "CAD"),
        status="completed" if shopify_data.get("financial_status") == "paid" else "pending",
        payment_status=shopify_data.get("financial_status", "unpaid"),
        source_id=str(shopify_data.get("id", "")),
    )


# ═══════════════════════════════════════════════════════════════
# ADAPTER: MANUAL/INVOICE -> UNIVERSAL
# ═══════════════════════════════════════════════════════════════

def invoice_to_universal_order(invoice: dict, tenant_id: str) -> dict:
    """Convert an AUREM Invoice to a Universal Order."""
    line_items = []
    for item in invoice.get("line_items", []):
        line_items.append({
            "name": item.get("description", ""),
            "quantity": item.get("quantity", 1),
            "price": item.get("unit_price", 0),
            "sku": "",
        })

    return make_universal_order(
        customer_email=invoice.get("customer_email", ""),
        total=invoice.get("total", 0),
        source_platform="standalone",
        tenant_id=tenant_id,
        order_number=invoice.get("invoice_number", ""),
        customer_name=invoice.get("customer_name", ""),
        line_items=line_items,
        subtotal=invoice.get("subtotal", 0),
        tax_amount=invoice.get("tax_amount", 0),
        currency=invoice.get("currency", "CAD"),
        status="completed" if invoice.get("status") == "paid" else "pending",
        payment_status=invoice.get("status", "draft"),
        payment_method=invoice.get("payment_method", ""),
        source_id=invoice.get("id", ""),
    )


# ═══════════════════════════════════════════════════════════════
# ADAPTER: CSV -> UNIVERSAL (with AI Template Matcher)
# ═══════════════════════════════════════════════════════════════

# Standard template columns
CSV_PRODUCT_TEMPLATE = [
    "name", "description", "price", "compare_at_price", "sku",
    "barcode", "category", "tags", "inventory_quantity", "weight",
    "weight_unit", "image_url", "status"
]

CSV_CUSTOMER_TEMPLATE = [
    "email", "first_name", "last_name", "phone", "company",
    "total_spend", "orders_count", "tags", "notes"
]

# Common column name aliases for auto-detection
COLUMN_ALIASES = {
    # Product fields
    "name": ["name", "product_name", "title", "product_title", "product", "item_name", "item"],
    "description": ["description", "desc", "product_description", "details", "body", "body_html"],
    "price": ["price", "unit_price", "cost", "amount", "retail_price", "selling_price", "msrp"],
    "compare_at_price": ["compare_at_price", "original_price", "list_price", "was_price", "regular_price"],
    "sku": ["sku", "item_sku", "product_sku", "stock_code", "item_code", "part_number"],
    "barcode": ["barcode", "upc", "ean", "isbn", "gtin"],
    "category": ["category", "product_type", "type", "department", "collection", "group"],
    "tags": ["tags", "labels", "keywords"],
    "inventory_quantity": ["inventory_quantity", "quantity", "stock", "qty", "inventory", "stock_level", "in_stock"],
    "weight": ["weight", "weight_value", "item_weight"],
    "image_url": ["image_url", "image", "photo", "picture", "thumbnail", "img_url", "photo_url"],
    "status": ["status", "active", "published", "visible"],
    # Customer fields
    "email": ["email", "email_address", "e_mail", "contact_email"],
    "first_name": ["first_name", "firstname", "first", "given_name"],
    "last_name": ["last_name", "lastname", "last", "surname", "family_name"],
    "phone": ["phone", "phone_number", "telephone", "mobile", "cell"],
    "company": ["company", "company_name", "business", "organization", "org"],
    "total_spend": ["total_spend", "total_spent", "lifetime_value", "ltv", "revenue"],
    "orders_count": ["orders_count", "total_orders", "orders", "order_count", "num_orders"],
    "notes": ["notes", "note", "comments", "memo"],
}


def match_columns_basic(headers: list) -> dict:
    """Rule-based column matching using aliases."""
    mapping = {}
    normalized = [h.strip().lower().replace(" ", "_").replace("-", "_") for h in headers]

    for std_field, aliases in COLUMN_ALIASES.items():
        for i, col in enumerate(normalized):
            if col in aliases:
                mapping[headers[i]] = std_field
                break
    return mapping


async def match_columns_ai(headers: list, sample_rows: list, data_type: str = "products") -> dict:
    """AI-powered column matching using GPT-4o for messy/non-standard headers."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        if not EMERGENT_LLM_KEY:
            logger.warning("[CSV] No EMERGENT_LLM_KEY, falling back to basic matching")
            return match_columns_basic(headers)

        template = CSV_PRODUCT_TEMPLATE if data_type == "products" else CSV_CUSTOMER_TEMPLATE

        prompt = f"""You are a CSV column mapper. Given these CSV column headers and sample data, map each header to the closest standard field name. Return ONLY a JSON object mapping original header -> standard field name.

Standard fields for {data_type}: {template}

CSV Headers: {headers}
Sample data (first 3 rows): {sample_rows[:3]}

Rules:
- Map each CSV header to exactly one standard field, or "skip" if no match
- Be smart about variations (e.g., "MSRP" -> "price", "Product Title" -> "name")
- Return valid JSON only, no explanation

Example response: {{"Product Title": "name", "Retail Price": "price", "Stock Level": "inventory_quantity"}}"""

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"csv_match_{data_type}",
            system_message="You are a CSV column mapping assistant. Map column headers to standard field names."
        )
        chat.with_model("openai", "gpt-4o")
        resp = await chat.send_message(UserMessage(text=prompt))

        import json
        text = resp.strip() if isinstance(resp, str) else str(resp).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        mapping = json.loads(text)

        # Filter out "skip" entries
        return {k: v for k, v in mapping.items() if v != "skip" and v in template}

    except Exception as e:
        logger.warning(f"[CSV] AI column matching failed ({e}), falling back to basic")
        return match_columns_basic(headers)


def parse_csv_products(csv_text: str, column_mapping: dict, tenant_id: str) -> list:
    """Parse CSV text into Universal Product records using the column mapping."""
    reader = csv.DictReader(io.StringIO(csv_text))
    products = []

    for row in reader:
        mapped = {}
        for csv_col, std_field in column_mapping.items():
            val = row.get(csv_col, "").strip()
            if val:
                mapped[std_field] = val

        name = mapped.get("name", "")
        if not name:
            continue

        try:
            price = float(mapped.get("price", 0))
        except (ValueError, TypeError):
            price = 0

        tags = []
        if mapped.get("tags"):
            tags = [t.strip() for t in mapped["tags"].split(",")]

        try:
            qty = int(float(mapped.get("inventory_quantity", 0)))
        except (ValueError, TypeError):
            qty = 0

        product = make_universal_product(
            name=name,
            price=price,
            source_platform="csv_manual",
            tenant_id=tenant_id,
            description=mapped.get("description", ""),
            compare_at_price=float(mapped.get("compare_at_price", 0)) if mapped.get("compare_at_price") else None,
            sku=mapped.get("sku", ""),
            barcode=mapped.get("barcode", ""),
            category=mapped.get("category", ""),
            tags=tags,
            inventory_quantity=qty,
            weight=float(mapped.get("weight", 0)) if mapped.get("weight") else None,
            weight_unit=mapped.get("weight_unit", "kg"),
            image_url=mapped.get("image_url", ""),
            status=mapped.get("status", "active"),
        )
        products.append(product)

    return products


def parse_csv_customers(csv_text: str, column_mapping: dict, tenant_id: str) -> list:
    """Parse CSV text into Universal Customer records using the column mapping."""
    reader = csv.DictReader(io.StringIO(csv_text))
    customers = []

    for row in reader:
        mapped = {}
        for csv_col, std_field in column_mapping.items():
            val = row.get(csv_col, "").strip()
            if val:
                mapped[std_field] = val

        email = mapped.get("email", "")
        if not email:
            continue

        tags = []
        if mapped.get("tags"):
            tags = [t.strip() for t in mapped["tags"].split(",")]

        customer = make_universal_customer(
            email=email,
            source_platform="csv_manual",
            tenant_id=tenant_id,
            first_name=mapped.get("first_name", ""),
            last_name=mapped.get("last_name", ""),
            phone=mapped.get("phone", ""),
            company=mapped.get("company", ""),
            total_spend=float(mapped.get("total_spend", 0)),
            orders_count=int(float(mapped.get("orders_count", 0))) if mapped.get("orders_count") else 0,
            tags=tags,
            notes=mapped.get("notes", ""),
        )
        customers.append(customer)

    return customers


# ═══════════════════════════════════════════════════════════════
# ADAPTER: GENERIC WEBHOOK -> UNIVERSAL
# ═══════════════════════════════════════════════════════════════

def normalize_webhook_event(platform: str, event_type: str, payload: dict, tenant_id: str) -> dict:
    """Normalize any platform webhook into a universal event."""
    now = datetime.now(timezone.utc).isoformat()

    # Map platform-specific event types to universal
    universal_event_map = {
        "order_created": "order.created",
        "order_paid": "order.paid",
        "order_cancelled": "order.cancelled",
        "customer_created": "customer.created",
        "customer_updated": "customer.updated",
        "product_updated": "product.updated",
        "inventory_updated": "inventory.updated",
        "cart_abandoned": "cart.abandoned",
        "payment_completed": "payment.completed",
        "payment_failed": "payment.failed",
        "refund_created": "refund.created",
        # Shopify-specific mappings
        "orders/create": "order.created",
        "orders/paid": "order.paid",
        "checkouts/create": "cart.abandoned",
        "products/update": "product.updated",
        "inventory_levels/update": "inventory.updated",
        # Stripe-specific mappings
        "payment_intent.succeeded": "payment.completed",
        "payment_intent.payment_failed": "payment.failed",
        "invoice.paid": "order.paid",
        "charge.refunded": "refund.created",
        # WooCommerce-specific mappings
        "woocommerce_new_order": "order.created",
        "woocommerce_payment_complete": "payment.completed",
    }

    universal_type = universal_event_map.get(event_type, f"custom.{event_type}")

    return {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "platform": platform,
        "event_type": universal_type,
        "original_event_type": event_type,
        "payload": payload,
        "processed": False,
        "created_at": now,
    }


# ═══════════════════════════════════════════════════════════════
# PLATFORM CONNECTION MODEL
# ═══════════════════════════════════════════════════════════════

def make_platform_connection(
    tenant_id: str,
    platform_type: str,
    display_name: str,
    **kwargs
) -> dict:
    """Create a platform connection record."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "platform_type": platform_type,
        "display_name": display_name,
        "status": kwargs.get("status", "active"),
        "credentials_stored": kwargs.get("credentials_stored", False),
        "shop_domain": kwargs.get("shop_domain", ""),
        "api_url": kwargs.get("api_url", ""),
        "last_sync_at": kwargs.get("last_sync_at"),
        "products_synced": kwargs.get("products_synced", 0),
        "customers_synced": kwargs.get("customers_synced", 0),
        "orders_synced": kwargs.get("orders_synced", 0),
        "config": kwargs.get("config", {}),
        "metadata": kwargs.get("metadata", {}),
        "created_at": now,
        "updated_at": now,
    }


logger.info("[STARTUP] Universal Connector Middleware loaded (Phase F)")
