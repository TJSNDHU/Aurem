# ============================================================
# REROOTS BUSINESS SYSTEM — API ENDPOINTS
# Module 01: Inventory & Batch Tracking
# Module 02: CRM & 28-Day Repurchase Engine
# Module 03: Orders & Fulfillment
# Module 04: Accounting & GST/HST Canada
# ============================================================

from fastapi import APIRouter, HTTPException, Body, Query
from datetime import datetime, date, timedelta
from typing import Optional, List
from bson import ObjectId
import uuid

router = APIRouter(prefix="/api/business", tags=["Business System"])

# Database reference - will be set by server.py
db = None

def set_db(database):
    """Set the database reference from server.py"""
    global db
    db = database


# ─── HELPERS ────────────────────────────────────────────────

def str_id(obj):
    """Convert MongoDB _id to string for JSON response"""
    if obj and "_id" in obj:
        obj["_id"] = str(obj["_id"])
    return obj


def calc_cycle(last_purchase_str: str):
    """Calculate 28-day repurchase cycle fields from last purchase date"""
    try:
        last = datetime.strptime(last_purchase_str, "%Y-%m-%d").date()
        today = date.today()
        cycle_day = (today - last).days
        next_due = last + timedelta(days=28)

        if cycle_day <= 23:
            status = "On Track"
        elif cycle_day <= 28:
            status = "Due Soon"
        elif cycle_day <= 35:
            status = "Overdue"
        else:
            status = "Lapsed"

        return {
            "cycleDay": cycle_day,
            "status": status,
            "nextDue": next_due.isoformat()
        }
    except Exception:
        return {"cycleDay": 0, "status": "On Track", "nextDue": ""}


# Canadian tax rates by province
PROVINCE_TAX = {
    "ON": 0.13, "BC": 0.12, "AB": 0.05, "QC": 0.14975,
    "MB": 0.12, "SK": 0.11, "NS": 0.15, "NB": 0.15,
    "NL": 0.15, "PE": 0.15
}


def calc_tax(subtotal: float, province: str) -> float:
    rate = PROVINCE_TAX.get(province, 0.13)
    return round(subtotal * rate, 2)


# ════════════════════════════════════════════════════════════
# MODULE 01 — INVENTORY & BATCH TRACKING
# ════════════════════════════════════════════════════════════

# ── Raw Ingredients ─────────────────────────────────────────

@router.get("/inventory/ingredients")
async def get_ingredients():
    """Get all raw ingredients"""
    try:
        ingredients = await db["ingredients"].find().sort("name", 1).to_list(500)
        return [str_id(i) for i in ingredients]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inventory/ingredients")
async def add_ingredient(data: dict = Body(...)):
    """Add a new raw ingredient"""
    try:
        data["lastUpdated"] = date.today().isoformat()
        data["createdAt"] = datetime.utcnow().isoformat()
        if "adjustmentLog" not in data:
            data["adjustmentLog"] = []
        result = await db["ingredients"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/inventory/ingredients/{ingredient_id}")
async def adjust_ingredient_stock(ingredient_id: str, data: dict = Body(...)):
    """
    Adjust stock level for an ingredient.
    Body: { adjustment: float, reason: str }
    """
    try:
        ingredient = await db["ingredients"].find_one({"_id": ObjectId(ingredient_id)})
        if not ingredient:
            raise HTTPException(status_code=404, detail="Ingredient not found")

        adjustment = float(data.get("adjustment", 0))
        new_stock = max(0, ingredient.get("stock", 0) + adjustment)

        await db["ingredients"].update_one(
            {"_id": ObjectId(ingredient_id)},
            {"$set": {
                "stock": new_stock,
                "lastUpdated": date.today().isoformat()
            },
            "$push": {
                "adjustmentLog": {
                    "date": date.today().isoformat(),
                    "adjustment": adjustment,
                    "reason": data.get("reason", ""),
                    "newStock": new_stock
                }
            }}
        )
        ingredient["stock"] = new_stock
        ingredient["lastUpdated"] = date.today().isoformat()
        return str_id(ingredient)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Finished Products ────────────────────────────────────────

@router.get("/inventory/products")
async def get_inventory_products():
    """Get all finished product inventory"""
    try:
        products = await db["inventory_products"].find().sort("name", 1).to_list(200)
        return [str_id(p) for p in products]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inventory/products")
async def add_inventory_product(data: dict = Body(...)):
    """Add a new finished product inventory entry"""
    try:
        data["createdAt"] = datetime.utcnow().isoformat()
        result = await db["inventory_products"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/inventory/products/{product_id}")
async def update_inventory_product(product_id: str, data: dict = Body(...)):
    """Update finished product inventory"""
    try:
        data.pop("_id", None)
        data["updatedAt"] = datetime.utcnow().isoformat()
        await db["inventory_products"].update_one(
            {"_id": ObjectId(product_id)},
            {"$set": data}
        )
        return {"success": True, "id": product_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Batch Records ────────────────────────────────────────────

@router.get("/inventory/batches")
async def get_batches():
    """Get all production batch records"""
    try:
        batches = await db["batch_records"].find().sort("manufactured", -1).to_list(500)
        return [str_id(b) for b in batches]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inventory/batches")
async def add_batch(data: dict = Body(...)):
    """Log a new production batch"""
    try:
        data["createdAt"] = datetime.utcnow().isoformat()
        if not data.get("batchNo"):
            data["batchNo"] = f"RR-{date.today().year}-{str(uuid.uuid4())[:4].upper()}"
        result = await db["batch_records"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/inventory/batches/{batch_id}")
async def update_batch(batch_id: str, data: dict = Body(...)):
    """Update batch record"""
    try:
        data.pop("_id", None)
        data["updatedAt"] = datetime.utcnow().isoformat()
        await db["batch_records"].update_one(
            {"_id": ObjectId(batch_id)},
            {"$set": data}
        )
        return {"success": True, "id": batch_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════
# MODULE 02 — CRM & 28-DAY REPURCHASE ENGINE
# ════════════════════════════════════════════════════════════

@router.get("/crm/customers")
async def get_crm_customers(
    status: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """
    Get all CRM customers with auto-calculated 28-day cycle fields.
    Optional filters: status, tier, search (name/email)
    """
    try:
        query = {}
        if tier:
            query["tier"] = tier
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}}
            ]

        customers = await db["crm_customers"].find(query).sort("name", 1).to_list(1000)

        result = []
        for c in customers:
            c = str_id(c)
            # Auto-calculate cycle fields every time
            if c.get("lastPurchase"):
                cycle_data = calc_cycle(c["lastPurchase"])
                c.update(cycle_data)
            # Apply status filter after calculation
            if status and c.get("status") != status:
                continue
            result.append(c)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crm/customers/{customer_id}")
async def get_crm_customer(customer_id: str):
    """Get single CRM customer profile"""
    try:
        customer = await db["crm_customers"].find_one({"_id": ObjectId(customer_id)})
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer = str_id(customer)
        if customer.get("lastPurchase"):
            customer.update(calc_cycle(customer["lastPurchase"]))
        return customer
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crm/customers")
async def add_crm_customer(data: dict = Body(...)):
    """Add a new CRM customer"""
    try:
        data["createdAt"] = datetime.utcnow().isoformat()
        data["totalSpend"] = data.get("totalSpend", 0)
        data["orders"] = data.get("orders", 1)
        # Auto-calculate cycle on creation
        if data.get("lastPurchase"):
            data.update(calc_cycle(data["lastPurchase"]))
        result = await db["crm_customers"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/crm/customers/{customer_id}")
async def update_crm_customer(customer_id: str, data: dict = Body(...)):
    """Update CRM customer details"""
    try:
        data.pop("_id", None)
        data["updatedAt"] = datetime.utcnow().isoformat()
        await db["crm_customers"].update_one(
            {"_id": ObjectId(customer_id)},
            {"$set": data}
        )
        return {"success": True, "id": customer_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/crm/customers/{customer_id}/notes")
async def update_crm_customer_notes(customer_id: str, data: dict = Body(...)):
    """
    Add or update CRM customer notes.
    Body: { notes: str }
    """
    try:
        await db["crm_customers"].update_one(
            {"_id": ObjectId(customer_id)},
            {"$set": {
                "notes": data.get("notes", ""),
                "notesUpdatedAt": datetime.utcnow().isoformat()
            }}
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crm/automations")
async def get_crm_automations():
    """Get all CRM automations"""
    try:
        automations = await db["crm_automations"].find().to_list(100)
        return [str_id(a) for a in automations]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crm/automations")
async def add_crm_automation(data: dict = Body(...)):
    """Create a new CRM automation"""
    try:
        data["createdAt"] = datetime.utcnow().isoformat()
        data["sent"] = data.get("sent", 0)
        data["opened"] = data.get("opened", 0)
        data["converted"] = data.get("converted", 0)
        result = await db["crm_automations"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/crm/automations/{automation_id}")
async def update_crm_automation(automation_id: str, data: dict = Body(...)):
    """Update CRM automation"""
    try:
        data.pop("_id", None)
        data["updatedAt"] = datetime.utcnow().isoformat()
        await db["crm_automations"].update_one(
            {"_id": ObjectId(automation_id)},
            {"$set": data}
        )
        return {"success": True, "id": automation_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crm/stats")
async def get_crm_stats():
    """Get CRM overview statistics"""
    try:
        customers = await db["crm_customers"].find().to_list(1000)
        
        total = len(customers)
        due_soon = 0
        overdue = 0
        lapsed = 0
        vip_count = 0
        total_revenue = 0
        
        for c in customers:
            if c.get("lastPurchase"):
                cycle = calc_cycle(c["lastPurchase"])
                if cycle["status"] == "Due Soon":
                    due_soon += 1
                elif cycle["status"] == "Overdue":
                    overdue += 1
                elif cycle["status"] == "Lapsed":
                    lapsed += 1
            
            if c.get("tier") == "VIP":
                vip_count += 1
            
            total_revenue += c.get("totalSpend", 0)
        
        return {
            "total": total,
            "dueSoon": due_soon,
            "overdue": overdue,
            "lapsed": lapsed,
            "vipCount": vip_count,
            "totalRevenue": total_revenue,
            "avgOrderValue": round(total_revenue / total, 2) if total > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════
# MODULE 03 — ORDERS & FULFILLMENT
# ════════════════════════════════════════════════════════════

@router.get("/fulfillment/orders")
async def get_fulfillment_orders(
    status: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100)
):
    """Get all orders for fulfillment, newest first"""
    try:
        query = {}
        if status:
            query["status"] = status
        if payment_status:
            query["paymentStatus"] = payment_status
        if search:
            query["$or"] = [
                {"id": {"$regex": search, "$options": "i"}},
                {"customer": {"$regex": search, "$options": "i"}},
                {"city": {"$regex": search, "$options": "i"}}
            ]

        orders = await db["fulfillment_orders"].find(query).sort("date", -1).to_list(limit)
        return [str_id(o) for o in orders]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fulfillment/orders/{order_id}")
async def get_fulfillment_order(order_id: str):
    """Get single order detail"""
    try:
        # Try by custom id field first, then MongoDB _id
        order = await db["fulfillment_orders"].find_one({"id": order_id})
        if not order:
            try:
                order = await db["fulfillment_orders"].find_one({"_id": ObjectId(order_id)})
            except Exception:
                pass
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return str_id(order)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fulfillment/orders")
async def create_fulfillment_order(data: dict = Body(...)):
    """
    Create a new order.
    Body: { customer, email, city, province, items[], notes, channel }
    Tax and total are calculated server-side.
    """
    try:
        # Generate order ID
        count = await db["fulfillment_orders"].count_documents({})
        order_id = f"RR-{10001 + count}"

        # Calculate financials
        items = data.get("items", [])
        subtotal = sum(item.get("qty", 1) * item.get("price", 0) for item in items)
        province = data.get("province", "ON")
        tax = calc_tax(subtotal, province)
        shipping = 0 if subtotal >= 150 else 9.99
        total = round(subtotal + tax + shipping, 2)

        order = {
            "id": order_id,
            "customer": data.get("customer", ""),
            "email": data.get("email", ""),
            "city": f"{data.get('city', '')}, {province}",
            "date": date.today().isoformat(),
            "items": items,
            "subtotal": subtotal,
            "tax": tax,
            "shipping": shipping,
            "total": total,
            "status": "Processing",
            "fulfillment": "Unfulfilled",
            "carrier": None,
            "tracking": None,
            "notes": data.get("notes", ""),
            "channel": data.get("channel", "Website"),
            "paymentStatus": "Paid",
            "createdAt": datetime.utcnow().isoformat()
        }

        result = await db["fulfillment_orders"].insert_one(order)
        order["_id"] = str(result.inserted_id)

        # Auto-create accounting revenue transaction
        await db["accounting_transactions"].insert_one({
            "date": date.today().isoformat(),
            "type": "Revenue",
            "category": "Product Sales",
            "description": f"Order {order_id} - {data.get('customer', '')}",
            "amount": total,
            "tax": tax,
            "province": province,
            "account": "Revenue",
            "status": "Cleared",
            "orderId": order_id,
            "createdAt": datetime.utcnow().isoformat()
        })

        # Update CRM customer totalSpend + orders count + lastPurchase
        if data.get("email"):
            await db["crm_customers"].update_one(
                {"email": data["email"]},
                {"$inc": {"totalSpend": total, "orders": 1},
                 "$set": {
                     "lastPurchase": date.today().isoformat(),
                     "lastProduct": items[0].get("sku", "") if items else ""
                 }},
                upsert=False
            )

        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/fulfillment/orders/{order_id}/fulfill")
async def fulfill_order(order_id: str, data: dict = Body(...)):
    """
    Mark order as fulfilled / shipped.
    Body: { carrier: str, tracking: str }
    """
    try:
        if not data.get("carrier") or not data.get("tracking"):
            raise HTTPException(status_code=400, detail="Carrier and tracking number required")

        await db["fulfillment_orders"].update_one(
            {"id": order_id},
            {"$set": {
                "status": "Shipped",
                "fulfillment": "Fulfilled",
                "carrier": data["carrier"],
                "tracking": data["tracking"],
                "fulfilledAt": datetime.utcnow().isoformat()
            }}
        )
        return {"success": True, "orderId": order_id, "status": "Shipped"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/fulfillment/orders/{order_id}/refund")
async def refund_order(order_id: str, data: dict = Body(...)):
    """
    Issue a refund on an order.
    Body: { reason: str (optional) }
    Auto-creates negative accounting transaction.
    """
    try:
        order = await db["fulfillment_orders"].find_one({"id": order_id})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Update order status
        await db["fulfillment_orders"].update_one(
            {"id": order_id},
            {"$set": {
                "status": "Refunded",
                "fulfillment": "Returned",
                "paymentStatus": "Refunded",
                "refundReason": data.get("reason", ""),
                "refundedAt": datetime.utcnow().isoformat()
            }}
        )

        # Auto-create negative accounting transaction
        city_parts = order.get("city", ", ON").split(", ")
        province = city_parts[-1] if len(city_parts) > 1 else "ON"
        
        await db["accounting_transactions"].insert_one({
            "date": date.today().isoformat(),
            "type": "Expense",
            "category": "Refund Issued",
            "description": f"Refund - Order {order_id} - {order.get('customer', '')}",
            "amount": -order.get("total", 0),
            "tax": -order.get("tax", 0),
            "province": province,
            "account": "Revenue",
            "status": "Cleared",
            "orderId": order_id,
            "createdAt": datetime.utcnow().isoformat()
        })

        return {"success": True, "orderId": order_id, "refunded": order.get("total", 0)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fulfillment/stats")
async def get_fulfillment_stats():
    """Get fulfillment overview statistics"""
    try:
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        
        orders = await db["fulfillment_orders"].find({
            "date": {"$gte": month_start}
        }).to_list(1000)
        
        total_revenue = sum(o.get("total", 0) for o in orders if o.get("paymentStatus") == "Paid")
        processing = sum(1 for o in orders if o.get("status") == "Processing")
        shipped = sum(1 for o in orders if o.get("status") == "Shipped")
        delivered = sum(1 for o in orders if o.get("status") == "Delivered")
        refunded = sum(1 for o in orders if o.get("status") == "Refunded")
        
        return {
            "revenue": total_revenue,
            "processing": processing,
            "shipped": shipped,
            "delivered": delivered,
            "refunded": refunded,
            "totalOrders": len(orders)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════
# MODULE 04 — ACCOUNTING & GST/HST
# ════════════════════════════════════════════════════════════

@router.get("/accounting/transactions")
async def get_accounting_transactions(
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200)
):
    """Get transaction ledger, newest first"""
    try:
        query = {}
        if type:
            query["type"] = type
        if category:
            query["category"] = category
        if search:
            query["$or"] = [
                {"description": {"$regex": search, "$options": "i"}},
                {"category": {"$regex": search, "$options": "i"}}
            ]

        transactions = await db["accounting_transactions"].find(query).sort("date", -1).to_list(limit)
        return [str_id(t) for t in transactions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounting/transactions")
async def add_accounting_transaction(data: dict = Body(...)):
    """
    Manually add a transaction.
    Body: { date, type, category, description, amount, province, account }
    Tax is auto-calculated for Revenue transactions.
    """
    try:
        # Auto-calculate tax for revenue entries
        if data.get("type") == "Revenue":
            province = data.get("province", "ON")
            subtotal = abs(float(data.get("amount", 0)))
            rate = PROVINCE_TAX.get(province, 0.13)
            data["tax"] = round(subtotal * rate / (1 + rate), 2)  # Extract tax from gross
        else:
            data["tax"] = data.get("tax", 0)

        data["status"] = data.get("status", "Cleared")
        data["createdAt"] = datetime.utcnow().isoformat()
        result = await db["accounting_transactions"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/accounting/transactions/{transaction_id}")
async def update_accounting_transaction(transaction_id: str, data: dict = Body(...)):
    """Update accounting transaction"""
    try:
        data.pop("_id", None)
        data["updatedAt"] = datetime.utcnow().isoformat()
        await db["accounting_transactions"].update_one(
            {"_id": ObjectId(transaction_id)},
            {"$set": data}
        )
        return {"success": True, "id": transaction_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounting/accounts")
async def get_accounting_accounts():
    """Get chart of accounts"""
    try:
        accounts = await db["accounting_accounts"].find().to_list(100)
        return [str_id(a) for a in accounts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounting/accounts")
async def add_accounting_account(data: dict = Body(...)):
    """Add a new account to chart of accounts"""
    try:
        data["createdAt"] = datetime.utcnow().isoformat()
        data["balance"] = data.get("balance", 0)
        result = await db["accounting_accounts"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/accounting/accounts/{account_id}")
async def update_accounting_account(account_id: str, data: dict = Body(...)):
    """
    Update account balance.
    Body: { balance: float, name: str, type: str, institution: str }
    """
    try:
        data.pop("_id", None)
        data["updatedAt"] = datetime.utcnow().isoformat()
        await db["accounting_accounts"].update_one(
            {"_id": ObjectId(account_id)},
            {"$set": data}
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounting/summary")
async def get_accounting_summary():
    """
    P&L summary for current month.
    Used by Executive Intelligence dashboard.
    """
    try:
        month_start = date.today().replace(day=1).isoformat()

        transactions = await db["accounting_transactions"].find({
            "date": {"$gte": month_start}
        }).to_list(1000)

        revenue = sum(t.get("amount", 0) for t in transactions if t.get("type") == "Revenue" and t.get("amount", 0) > 0)
        expenses = sum(abs(t.get("amount", 0)) for t in transactions if t.get("type") == "Expense")
        cogs = sum(abs(t.get("amount", 0)) for t in transactions if t.get("category") == "COGS")
        tax_collected = sum(t.get("tax", 0) for t in transactions if t.get("type") == "Revenue")

        gross_profit = revenue - cogs
        net_profit = revenue - expenses

        return {
            "revenue": revenue,
            "cogs": cogs,
            "grossProfit": gross_profit,
            "grossMargin": round((gross_profit / revenue * 100), 1) if revenue > 0 else 0,
            "expenses": expenses,
            "netProfit": net_profit,
            "netMargin": round((net_profit / revenue * 100), 1) if revenue > 0 else 0,
            "taxCollected": tax_collected,
            "period": f"{date.today().strftime('%B %Y')}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounting/gst-summary")
async def get_gst_summary():
    """Get GST/HST summary for tax remittance"""
    try:
        # Get transactions for current quarter
        today = date.today()
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        quarter_start = today.replace(month=quarter_month, day=1).isoformat()
        
        transactions = await db["accounting_transactions"].find({
            "date": {"$gte": quarter_start}
        }).to_list(1000)
        
        # Calculate GST/HST collected and paid
        collected = sum(t.get("tax", 0) for t in transactions if t.get("type") == "Revenue" and t.get("tax", 0) > 0)
        paid = sum(abs(t.get("tax", 0)) for t in transactions if t.get("type") == "Expense" and t.get("tax", 0) < 0)
        
        # Group by province
        by_province = {}
        for t in transactions:
            if t.get("type") == "Revenue" and t.get("tax", 0) > 0:
                prov = t.get("province", "ON")
                if prov not in by_province:
                    by_province[prov] = {"collected": 0, "sales": 0}
                by_province[prov]["collected"] += t.get("tax", 0)
                by_province[prov]["sales"] += t.get("amount", 0)
        
        return {
            "quarterStart": quarter_start,
            "quarterEnd": today.isoformat(),
            "collected": round(collected, 2),
            "paid": round(paid, 2),
            "netOwing": round(collected - paid, 2),
            "byProvince": by_province
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════
# ANALYTICS ENDPOINT (for Executive Intelligence)
# ════════════════════════════════════════════════════════════

@router.get("/business-analytics")
async def get_business_analytics():
    """
    Dashboard analytics summary.
    Used by Executive Intelligence for CEO Briefing.
    """
    try:
        today = date.today()
        week_ago = (today - timedelta(days=7)).isoformat()

        # Weekly revenue from fulfillment orders
        weekly_orders = await db["fulfillment_orders"].find({
            "date": {"$gte": week_ago},
            "paymentStatus": "Paid"
        }).to_list(1000)
        weekly_revenue = sum(o.get("total", 0) for o in weekly_orders)

        # Previous week for growth calc
        two_weeks_ago = (today - timedelta(days=14)).isoformat()
        prev_week_orders = await db["fulfillment_orders"].find({
            "date": {"$gte": two_weeks_ago, "$lt": week_ago},
            "paymentStatus": "Paid"
        }).to_list(1000)
        prev_revenue = sum(o.get("total", 0) for o in prev_week_orders)
        growth = round(((weekly_revenue - prev_revenue) / prev_revenue * 100), 1) if prev_revenue > 0 else 0

        # Top SKU this week
        sku_counts = {}
        for o in weekly_orders:
            for item in o.get("items", []):
                sku = item.get("sku", "")
                sku_counts[sku] = sku_counts.get(sku, 0) + item.get("qty", 1)
        top_sku = max(sku_counts, key=sku_counts.get) if sku_counts else "-"

        # Repurchase rate (CRM customers with 2+ orders)
        repeat_customers = await db["crm_customers"].count_documents({"orders": {"$gte": 2}})
        total_customers = await db["crm_customers"].count_documents({})
        repurchase_rate = round((repeat_customers / total_customers * 100), 1) if total_customers > 0 else 0

        # Low stock alerts
        low_stock = await db["ingredients"].count_documents({
            "$expr": {"$lte": ["$stock", "$reorderPoint"]}
        })

        # Customers needing attention (Due Soon or Overdue)
        all_crm = await db["crm_customers"].find(
            {"lastPurchase": {"$exists": True}}
        ).to_list(1000)
        due_soon = sum(1 for c in all_crm if calc_cycle(c.get("lastPurchase", ""))["status"] in ["Due Soon", "Overdue"])

        return {
            "weekly": {
                "revenue": f"${weekly_revenue:,.2f}",
                "growth": f"{'+' if growth >= 0 else ''}{growth}%",
                "orders": len(weekly_orders),
                "topSKU": top_sku
            },
            "repurchaseRate": f"{repurchase_rate}%",
            "lowStockAlerts": low_stock,
            "customersDueSoon": due_soon,
            "totalCustomers": total_customers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════
# DATABASE SEEDING — Run once to populate initial data
# ════════════════════════════════════════════════════════════

async def seed_business_system_data():
    """
    Seed initial data for the Business System modules.
    Call from startup event.
    """
    try:
        # Seed Chart of Accounts if empty
        existing_accounts = await db["accounting_accounts"].count_documents({})
        if existing_accounts == 0:
            await db["accounting_accounts"].insert_many([
                {"name": "Chequing - Reroots Aesthetics Inc.", "balance": 0, "type": "Bank", "institution": "RBC"},
                {"name": "Business Savings", "balance": 0, "type": "Bank", "institution": "RBC"},
                {"name": "Stripe Merchant Account", "balance": 0, "type": "Payment Processor", "institution": "Stripe"},
                {"name": "Accounts Receivable", "balance": 0, "type": "A/R", "institution": "-"},
                {"name": "GST/HST Owing (CRA)", "balance": 0, "type": "Tax Liability", "institution": "CRA"},
            ])
            print("[Business System] Chart of accounts seeded")

        # Seed sample CRM automations if empty
        existing_automations = await db["crm_automations"].count_documents({})
        if existing_automations == 0:
            await db["crm_automations"].insert_many([
                {
                    "name": "Day 25 - Gentle Reminder",
                    "trigger": "Day 25 of Cycle",
                    "action": "Send Email",
                    "status": "Active",
                    "sent": 0,
                    "opened": 0,
                    "converted": 0,
                    "createdAt": datetime.utcnow().isoformat()
                },
                {
                    "name": "Day 28 - Reorder Now",
                    "trigger": "Day 28 of Cycle",
                    "action": "Send Email + SMS",
                    "status": "Active",
                    "sent": 0,
                    "opened": 0,
                    "converted": 0,
                    "createdAt": datetime.utcnow().isoformat()
                },
                {
                    "name": "Day 35 - Win-Back Offer",
                    "trigger": "Day 35 of Cycle",
                    "action": "Send Email",
                    "status": "Active",
                    "sent": 0,
                    "opened": 0,
                    "converted": 0,
                    "createdAt": datetime.utcnow().isoformat()
                }
            ])
            print("[Business System] CRM automations seeded")

        print("[Business System] Data seeding complete")
    except Exception as e:
        print(f"[Business System] Seeding error: {e}")
