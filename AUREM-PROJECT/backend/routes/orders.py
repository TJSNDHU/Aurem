"""
Order Routes: Cart, Checkout, Order Management, Admin Orders with Server-Side Pagination
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import get_database
from utils.auth import require_auth, require_admin, get_current_user

# Initialize router
router = APIRouter(tags=["Orders"])


# ============= CART MODELS =============

class CartItem(BaseModel):
    product_id: str
    quantity: int = 1


class Cart(BaseModel):
    id: str = None
    user_id: Optional[str] = None
    session_id: str
    items: List[Dict] = []
    updated_at: str = None

    def __init__(self, **data):
        if 'id' not in data or data['id'] is None:
            data['id'] = str(uuid.uuid4())
        if 'updated_at' not in data or data['updated_at'] is None:
            data['updated_at'] = datetime.now(timezone.utc).isoformat()
        super().__init__(**data)


# ============= CART ROUTES =============

@router.get("/cart/{session_id}")
async def get_cart(session_id: str):
    """Get or create cart by session ID"""
    db = get_database()
    
    cart = await db.carts.find_one({"session_id": session_id}, {"_id": 0})
    if not cart:
        new_cart = Cart(session_id=session_id)
        cart_dict = new_cart.model_dump()
        await db.carts.insert_one(cart_dict)
        cart = await db.carts.find_one({"session_id": session_id}, {"_id": 0})

    # Populate product details with batch fetch (avoid N+1)
    items = cart.get("items", [])
    if items:
        product_ids = [item["product_id"] for item in items]
        products_list = await db.products.find(
            {"$or": [{"id": {"$in": product_ids}}, {"slug": {"$in": product_ids}}]},
            {"_id": 0},
        ).to_list(len(product_ids) * 2)

        products_dict = {}
        for p in products_list:
            products_dict[p["id"]] = p
            if p.get("slug"):
                products_dict[p["slug"]] = p

        items_with_details = []
        for item in items:
            product = products_dict.get(item["product_id"])
            if product:
                items_with_details.append({**item, "product": product})
        cart["items"] = items_with_details
    
    return cart


@router.post("/cart/{session_id}/add")
async def add_to_cart(session_id: str, item: CartItem):
    """Add item to cart"""
    db = get_database()
    
    # Support both UUID and slug lookup
    product = await db.products.find_one(
        {"$or": [{"id": item.product_id}, {"slug": item.product_id}]},
        {"_id": 0, "id": 1},
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    actual_product_id = product["id"]

    cart = await db.carts.find_one({"session_id": session_id})
    if not cart:
        cart = Cart(session_id=session_id).model_dump()
        await db.carts.insert_one(cart)

    items = cart.get("items", [])
    existing_item = next(
        (i for i in items if i["product_id"] == actual_product_id), None
    )

    if existing_item:
        existing_item["quantity"] += item.quantity
    else:
        items.append({"product_id": actual_product_id, "quantity": item.quantity})

    await db.carts.update_one(
        {"session_id": session_id},
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    return await get_cart(session_id)


@router.put("/cart/{session_id}/update")
async def update_cart_item(session_id: str, item: CartItem):
    """Update cart item quantity"""
    db = get_database()
    
    cart = await db.carts.find_one({"session_id": session_id})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    items = cart.get("items", [])
    for i in items:
        if i["product_id"] == item.product_id:
            if item.quantity <= 0:
                items.remove(i)
            else:
                i["quantity"] = item.quantity
            break

    await db.carts.update_one(
        {"session_id": session_id},
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    return await get_cart(session_id)


@router.delete("/cart/{session_id}/item/{product_id}")
async def remove_from_cart(session_id: str, product_id: str):
    """Remove item from cart"""
    db = get_database()
    
    await db.carts.update_one(
        {"session_id": session_id},
        {
            "$pull": {"items": {"product_id": product_id}},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        },
    )
    return await get_cart(session_id)


@router.delete("/cart/{session_id}")
async def clear_cart(session_id: str):
    """Clear all items from cart"""
    db = get_database()
    
    await db.carts.update_one(
        {"session_id": session_id},
        {"$set": {"items": [], "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"message": "Cart cleared"}


# ============= USER ORDERS =============

@router.get("/orders")
async def get_user_orders(request: Request):
    """Get orders for authenticated user"""
    db = get_database()
    user = await get_current_user(request)
    
    if not user:
        return []
    
    orders = await db.orders.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return orders


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get single order by ID"""
    db = get_database()
    
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/orders/{order_id}/tracking")
async def get_order_tracking(order_id: str):
    """Get tracking info for an order"""
    db = get_database()
    
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order_id": order_id,
        "order_number": order.get("order_number"),
        "status": order.get("order_status", order.get("status")),
        "tracking_number": order.get("tracking_number"),
        "courier": order.get("courier"),
        "shipped_at": order.get("shipped_at"),
        "tracking_url": order.get("tracking_url"),
    }


# ============= ADMIN ORDERS (Server-Side Pagination) =============

@router.get("/admin/orders")
async def get_all_orders(
    request: Request,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
):
    """
    Get orders with server-side pagination, search, and filtering.
    
    - page: Page number (1-indexed)
    - limit: Items per page (default 20, max 100)
    - search: Search in order_number, customer name, email
    - status: Filter by order status
    - sort_by: Field to sort by
    - sort_order: 'asc' or 'desc'
    """
    db = get_database()
    await require_admin(request)

    # Ensure limit is reasonable
    limit = min(max(1, limit), 100)
    skip = (page - 1) * limit

    # Build query
    query = {}
    if status and status != "all":
        query["order_status"] = status

    # Search functionality
    if search:
        search_regex = {"$regex": search, "$options": "i"}
        query["$or"] = [
            {"order_number": search_regex},
            {"shipping_address.first_name": search_regex},
            {"shipping_address.last_name": search_regex},
            {"shipping_address.email": search_regex},
            {"user_email": search_regex},
            {"id": search_regex}
        ]

    # Sort direction
    sort_direction = -1 if sort_order == "desc" else 1

    # Get total count for pagination
    total_count = await db.orders.count_documents(query)

    # Fetch paginated orders
    orders = await db.orders.find(query, {"_id": 0}).sort(
        sort_by, sort_direction
    ).skip(skip).limit(limit).to_list(limit)

    # Calculate pagination metadata
    total_pages = (total_count + limit - 1) // limit

    return {
        "orders": orders,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }


@router.put("/admin/orders/{order_id}/status")
async def update_order_status(order_id: str, status_data: dict, request: Request):
    """Update order status"""
    db = get_database()
    await require_admin(request)
    
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {"order_status": status_data.get("status"), "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Order status updated"}


@router.post("/admin/orders/{order_id}/cancel")
async def admin_cancel_order(order_id: str, data: dict, request: Request):
    """Admin cancels an order"""
    db = get_database()
    await require_admin(request)

    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    reason = data.get("reason", "Cancelled by admin")

    await db.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "order_status": "cancelled",
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                "cancellation_reason": reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
    )

    logging.info(f"Order {order_id} cancelled by admin: {reason}")
    return {"message": "Order cancelled", "order_id": order_id}


@router.post("/admin/orders/{order_id}/approve")
async def approve_order(order_id: str, request: Request):
    """Approve a pending order"""
    db = get_database()
    await require_admin(request)

    result = await db.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "order_status": "confirmed",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")

    return {"message": "Order approved"}


@router.delete("/admin/orders/{order_id}")
async def delete_order(order_id: str, request: Request):
    """Delete an order (admin only)"""
    db = get_database()
    await require_admin(request)

    result = await db.orders.delete_one({"id": order_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")

    logging.info(f"Order {order_id} deleted by admin")
    return {"message": "Order deleted"}


# ============= ORDER TAGS =============

@router.post("/admin/orders/{order_id}/tags")
async def add_order_tag(order_id: str, data: dict, request: Request):
    """Add a tag to an order"""
    db = get_database()
    await require_admin(request)

    tag = data.get("tag", "").strip()
    if not tag:
        raise HTTPException(status_code=400, detail="Tag is required")

    await db.orders.update_one(
        {"id": order_id},
        {"$addToSet": {"tags": tag}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Tag added"}


@router.delete("/admin/orders/{order_id}/tags/{tag}")
async def remove_order_tag(order_id: str, tag: str, request: Request):
    """Remove a tag from an order"""
    db = get_database()
    await require_admin(request)

    await db.orders.update_one(
        {"id": order_id},
        {"$pull": {"tags": tag}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Tag removed"}
