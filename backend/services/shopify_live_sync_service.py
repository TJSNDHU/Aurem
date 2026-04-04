"""
Shopify Live Sync Service
Real-time inventory synchronization via webhooks

Features:
- Receive Shopify webhooks (orders/create, inventory_levels/update, products/update)
- Update Vector DB with real-time inventory data
- Multi-tenant support (each business has their own Shopify store)
- Webhook verification for security
"""

import logging
import hmac
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ShopifyLiveSyncService:
    """
    Real-time synchronization service for Shopify inventory
    """
    
    def __init__(self, db):
        """
        Initialize Shopify Live Sync Service
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        logger.info("[ShopifySync] Service initialized")
    
    def verify_webhook(self, webhook_data: bytes, hmac_header: str, secret: str) -> bool:
        """
        Verify Shopify webhook signature
        
        Args:
            webhook_data: Raw webhook body (bytes)
            hmac_header: X-Shopify-Hmac-SHA256 header value
            secret: Shopify webhook secret
        
        Returns:
            True if signature is valid
        """
        try:
            # Compute HMAC
            computed_hmac = hmac.new(
                secret.encode('utf-8'),
                webhook_data,
                hashlib.sha256
            ).hexdigest()
            
            # Compare with header
            is_valid = hmac.compare_digest(computed_hmac, hmac_header)
            
            if not is_valid:
                logger.warning("[ShopifySync] Webhook signature verification failed")
            
            return is_valid
        
        except Exception as e:
            logger.error(f"[ShopifySync] Webhook verification error: {e}")
            return False
    
    async def handle_order_create(
        self,
        tenant_id: str,
        order_data: Dict
    ) -> Dict[str, Any]:
        """
        Handle orders/create webhook
        Updates inventory for ordered products
        
        Args:
            tenant_id: Tenant ID (which Shopify store)
            order_data: Shopify order webhook payload
        
        Returns:
            {
                "success": bool,
                "products_updated": int,
                "vector_db_updated": bool
            }
        """
        try:
            line_items = order_data.get("line_items", [])
            products_updated = 0
            
            for item in line_items:
                product_id = item.get("product_id")
                variant_id = item.get("variant_id")
                sku = item.get("sku")
                quantity_ordered = item.get("quantity", 0)
                product_title = item.get("title")
                
                # Update inventory in database
                await self._update_product_inventory(
                    tenant_id=tenant_id,
                    product_id=str(product_id),
                    sku=sku,
                    quantity_change=-quantity_ordered,  # Decrease inventory
                    product_title=product_title,
                    event_type="order_create"
                )
                
                products_updated += 1
            
            # Update Vector DB for affected products
            vector_updated = await self._sync_to_vector_db(
                tenant_id=tenant_id,
                product_ids=[str(item.get("product_id")) for item in line_items]
            )
            
            logger.info(
                f"[ShopifySync] Order processed: {products_updated} products updated "
                f"for tenant {tenant_id}"
            )
            
            return {
                "success": True,
                "products_updated": products_updated,
                "vector_db_updated": vector_updated,
                "order_id": order_data.get("id")
            }
        
        except Exception as e:
            logger.error(f"[ShopifySync] Order create error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_inventory_update(
        self,
        tenant_id: str,
        inventory_data: Dict
    ) -> Dict[str, Any]:
        """
        Handle inventory_levels/update webhook
        Direct inventory level changes
        
        Args:
            tenant_id: Tenant ID
            inventory_data: Shopify inventory webhook payload
        
        Returns:
            Update result
        """
        try:
            inventory_item_id = inventory_data.get("inventory_item_id")
            available = inventory_data.get("available")
            
            # Get product details from inventory_item_id
            # This would require a Shopify API call to get product info
            # For now, we'll store the raw inventory data
            
            await self.db.shopify_inventory.update_one(
                {
                    "tenant_id": tenant_id,
                    "inventory_item_id": str(inventory_item_id)
                },
                {
                    "$set": {
                        "available": available,
                        "updated_at": datetime.now(timezone.utc),
                        "last_webhook": inventory_data
                    }
                },
                upsert=True
            )
            
            logger.info(
                f"[ShopifySync] Inventory updated: item {inventory_item_id}, "
                f"available: {available}"
            )
            
            return {
                "success": True,
                "inventory_item_id": inventory_item_id,
                "available": available
            }
        
        except Exception as e:
            logger.error(f"[ShopifySync] Inventory update error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_product_update(
        self,
        tenant_id: str,
        product_data: Dict
    ) -> Dict[str, Any]:
        """
        Handle products/update webhook
        Product information changes (title, price, etc.)
        
        Args:
            tenant_id: Tenant ID
            product_data: Shopify product webhook payload
        
        Returns:
            Update result
        """
        try:
            product_id = str(product_data.get("id"))
            title = product_data.get("title")
            variants = product_data.get("variants", [])
            
            # Update product in database
            await self.db.shopify_products.update_one(
                {
                    "tenant_id": tenant_id,
                    "product_id": product_id
                },
                {
                    "$set": {
                        "title": title,
                        "variants": variants,
                        "product_type": product_data.get("product_type"),
                        "tags": product_data.get("tags", "").split(","),
                        "updated_at": datetime.now(timezone.utc),
                        "shopify_data": product_data
                    }
                },
                upsert=True
            )
            
            # Update Vector DB
            vector_updated = await self._sync_to_vector_db(
                tenant_id=tenant_id,
                product_ids=[product_id]
            )
            
            logger.info(f"[ShopifySync] Product updated: {title} (ID: {product_id})")
            
            return {
                "success": True,
                "product_id": product_id,
                "vector_db_updated": vector_updated
            }
        
        except Exception as e:
            logger.error(f"[ShopifySync] Product update error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _update_product_inventory(
        self,
        tenant_id: str,
        product_id: str,
        sku: Optional[str],
        quantity_change: int,
        product_title: Optional[str] = None,
        event_type: str = "manual"
    ) -> bool:
        """
        Update product inventory in database
        
        Args:
            tenant_id: Tenant ID
            product_id: Product ID
            sku: Product SKU
            quantity_change: Change in quantity (positive or negative)
            product_title: Product title
            event_type: Type of event causing the change
        
        Returns:
            Success boolean
        """
        try:
            # Update or create product record
            update_data = {
                "tenant_id": tenant_id,
                "product_id": product_id,
                "$inc": {"quantity": quantity_change},
                "$set": {
                    "updated_at": datetime.now(timezone.utc),
                    "last_event": event_type
                }
            }
            
            if sku:
                update_data["$set"]["sku"] = sku
            if product_title:
                update_data["$set"]["title"] = product_title
            
            await self.db.shopify_products.update_one(
                {"tenant_id": tenant_id, "product_id": product_id},
                update_data,
                upsert=True
            )
            
            return True
        
        except Exception as e:
            logger.error(f"[ShopifySync] Inventory update error: {e}")
            return False
    
    async def _sync_to_vector_db(
        self,
        tenant_id: str,
        product_ids: List[str]
    ) -> bool:
        """
        Sync updated products to Vector DB (ChromaDB)
        
        Args:
            tenant_id: Tenant ID
            product_ids: List of product IDs to sync
        
        Returns:
            Success boolean
        """
        try:
            # Get product data from database
            products = await self.db.shopify_products.find(
                {
                    "tenant_id": tenant_id,
                    "product_id": {"$in": product_ids}
                },
                {"_id": 0}
            ).to_list(100)
            
            if not products:
                logger.warning(f"[ShopifySync] No products found for IDs: {product_ids}")
                return False
            
            # Import vector search service
            from services.vector_search import get_vector_search
            
            vector_service = get_vector_search()
            
            # Index each product
            for product in products:
                # Create searchable text
                searchable_text = self._create_product_searchable_text(product)
                
                # Update Vector DB
                # Note: This uses the connector_data collection
                # In production, you might want a separate shopify_products collection
                await vector_service.index_connector_data(
                    platform="shopify",
                    data=[{
                        "product_id": product["product_id"],
                        "title": product.get("title"),
                        "sku": product.get("sku"),
                        "quantity": product.get("quantity", 0),
                        "in_stock": product.get("quantity", 0) > 0,
                        "searchable_text": searchable_text,
                        "last_updated": product.get("updated_at")
                    }],
                    query_context="shopify_inventory_sync",
                    tenant_id=tenant_id
                )
            
            logger.info(
                f"[ShopifySync] Vector DB updated: {len(products)} products "
                f"for tenant {tenant_id}"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"[ShopifySync] Vector DB sync error: {e}")
            return False
    
    def _create_product_searchable_text(self, product: Dict) -> str:
        """
        Create searchable text from product data
        
        Args:
            product: Product document
        
        Returns:
            Searchable text string
        """
        parts = []
        
        if product.get("title"):
            parts.append(f"Product: {product['title']}")
        
        if product.get("sku"):
            parts.append(f"SKU: {product['sku']}")
        
        quantity = product.get("quantity", 0)
        stock_status = "in stock" if quantity > 0 else "out of stock"
        parts.append(f"Stock: {quantity} units ({stock_status})")
        
        if product.get("product_type"):
            parts.append(f"Type: {product['product_type']}")
        
        if product.get("tags"):
            parts.append(f"Tags: {', '.join(product['tags'])}")
        
        return " | ".join(parts)
    
    async def get_product_availability(
        self,
        tenant_id: str,
        product_query: str
    ) -> Dict[str, Any]:
        """
        Check product availability (for AI Agent to use)
        
        Args:
            tenant_id: Tenant ID
            product_query: Product name or SKU
        
        Returns:
            {
                "available": bool,
                "quantity": int,
                "product_name": str,
                "message": str  # For AI to say
            }
        """
        try:
            # Search in database
            product = await self.db.shopify_products.find_one(
                {
                    "tenant_id": tenant_id,
                    "$or": [
                        {"title": {"$regex": product_query, "$options": "i"}},
                        {"sku": product_query}
                    ]
                },
                {"_id": 0}
            )
            
            if not product:
                return {
                    "available": False,
                    "quantity": 0,
                    "product_name": product_query,
                    "message": f"I couldn't find '{product_query}' in our inventory. Would you like me to suggest similar products?"
                }
            
            quantity = product.get("quantity", 0)
            product_name = product.get("title", product_query)
            
            if quantity > 0:
                return {
                    "available": True,
                    "quantity": quantity,
                    "product_name": product_name,
                    "message": f"Yes! We have {quantity} units of {product_name} in stock. Would you like to place an order?"
                }
            else:
                return {
                    "available": False,
                    "quantity": 0,
                    "product_name": product_name,
                    "message": f"I'm sorry, {product_name} just sold out! Would you like me to notify you when it's back in stock, or can I suggest an alternative?"
                }
        
        except Exception as e:
            logger.error(f"[ShopifySync] Availability check error: {e}")
            return {
                "available": False,
                "quantity": 0,
                "product_name": product_query,
                "message": "I'm having trouble checking inventory right now. Let me transfer you to someone who can help."
            }


# Singleton instance
_shopify_sync_service = None


def get_shopify_sync_service(db):
    """Get singleton ShopifyLiveSyncService instance"""
    global _shopify_sync_service
    
    if _shopify_sync_service is None:
        _shopify_sync_service = ShopifyLiveSyncService(db)
    
    return _shopify_sync_service
