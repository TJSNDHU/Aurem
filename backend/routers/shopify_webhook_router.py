"""
Shopify Webhook Router
Receives real-time webhooks from Shopify stores

Endpoints:
- POST /api/shopify/webhooks/orders/create - Order created
- POST /api/shopify/webhooks/inventory/update - Inventory level changed
- POST /api/shopify/webhooks/products/update - Product info updated
- GET  /api/shopify/products/{product_id} - Check product availability
"""

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shopify", tags=["Shopify"])

# Database connection (set by server.py)
db = None


def set_db(database):
    global db
    db = database


@router.post("/webhooks/orders/create")
async def shopify_order_create_webhook(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None)
):
    """
    Shopify orders/create webhook
    
    Triggered when an order is placed
    Updates inventory in real-time
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Get raw body for signature verification
        body = await request.body()
        order_data = json.loads(body)
        
        # Extract tenant_id from shop domain
        # In production, you'd look up tenant by shop_domain
        shop_domain = x_shopify_shop_domain or order_data.get("shop", "unknown")
        tenant_id = f"shopify_{shop_domain.replace('.myshopify.com', '')}"
        
        # TODO: Verify webhook signature
        # webhook_secret = await get_tenant_shopify_secret(tenant_id)
        # if not verify_webhook(body, x_shopify_hmac_sha256, webhook_secret):
        #     raise HTTPException(401, "Invalid webhook signature")
        
        # Process order
        from services.shopify_live_sync_service import get_shopify_sync_service
        
        sync_service = get_shopify_sync_service(db)
        result = await sync_service.handle_order_create(
            tenant_id=tenant_id,
            order_data=order_data
        )
        
        if result["success"]:
            logger.info(
                f"[Shopify Webhook] Order processed: {result['products_updated']} "
                f"products updated"
            )
            return {
                "success": True,
                "message": "Order webhook processed",
                "products_updated": result["products_updated"]
            }
        else:
            raise HTTPException(500, result.get("error", "Processing failed"))
    
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON payload")
    except Exception as e:
        logger.error(f"[Shopify Webhook] Order create error: {e}")
        raise HTTPException(500, str(e))


@router.post("/webhooks/inventory/update")
async def shopify_inventory_update_webhook(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None)
):
    """
    Shopify inventory_levels/update webhook
    
    Triggered when inventory levels change
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        body = await request.body()
        inventory_data = json.loads(body)
        
        shop_domain = x_shopify_shop_domain or "unknown"
        tenant_id = f"shopify_{shop_domain.replace('.myshopify.com', '')}"
        
        from services.shopify_live_sync_service import get_shopify_sync_service
        
        sync_service = get_shopify_sync_service(db)
        result = await sync_service.handle_inventory_update(
            tenant_id=tenant_id,
            inventory_data=inventory_data
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "Inventory webhook processed"
            }
        else:
            raise HTTPException(500, result.get("error"))
    
    except Exception as e:
        logger.error(f"[Shopify Webhook] Inventory update error: {e}")
        raise HTTPException(500, str(e))


@router.post("/webhooks/products/update")
async def shopify_product_update_webhook(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None)
):
    """
    Shopify products/update webhook
    
    Triggered when product info changes (title, price, etc.)
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        body = await request.body()
        product_data = json.loads(body)
        
        shop_domain = x_shopify_shop_domain or "unknown"
        tenant_id = f"shopify_{shop_domain.replace('.myshopify.com', '')}"
        
        from services.shopify_live_sync_service import get_shopify_sync_service
        
        sync_service = get_shopify_sync_service(db)
        result = await sync_service.handle_product_update(
            tenant_id=tenant_id,
            product_data=product_data
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "Product webhook processed",
                "vector_db_updated": result["vector_db_updated"]
            }
        else:
            raise HTTPException(500, result.get("error"))
    
    except Exception as e:
        logger.error(f"[Shopify Webhook] Product update error: {e}")
        raise HTTPException(500, str(e))


@router.get("/products/availability")
async def check_product_availability(
    product_name: str,
    tenant_id: str = "aurem_platform"  # TODO: Get from TenantContext
):
    """
    Check if a product is in stock
    
    Query params:
        product_name: Product name or SKU
        tenant_id: Tenant ID (auto-detected in production)
    
    Returns:
        Product availability info for AI Agent
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        from services.shopify_live_sync_service import get_shopify_sync_service
        
        sync_service = get_shopify_sync_service(db)
        result = await sync_service.get_product_availability(
            tenant_id=tenant_id,
            product_query=product_name
        )
        
        return {
            "success": True,
            **result
        }
    
    except Exception as e:
        logger.error(f"[Shopify] Availability check error: {e}")
        raise HTTPException(500, str(e))


@router.post("/test/simulate-order")
async def simulate_shopify_order(tenant_id: str = "test_shopify"):
    """
    Test endpoint to simulate a Shopify order webhook
    
    For development/testing only
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    # Simulated order webhook payload
    mock_order = {
        "id": 123456789,
        "shop": "test-shop.myshopify.com",
        "line_items": [
            {
                "product_id": 111,
                "variant_id": 222,
                "sku": "ROSE-GEN-001",
                "title": "Rose-Gen Serum",
                "quantity": 1
            },
            {
                "product_id": 333,
                "variant_id": 444,
                "sku": "AURA-GEN-001",
                "title": "Aura-Gen Cream",
                "quantity": 2
            }
        ]
    }
    
    try:
        from services.shopify_live_sync_service import get_shopify_sync_service
        
        sync_service = get_shopify_sync_service(db)
        result = await sync_service.handle_order_create(
            tenant_id=tenant_id,
            order_data=mock_order
        )
        
        return {
            "success": True,
            "message": "Simulated order processed",
            "result": result
        }
    
    except Exception as e:
        logger.error(f"[Shopify] Simulation error: {e}")
        raise HTTPException(500, str(e))
