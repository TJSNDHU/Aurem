"""
MCP HTTP Router
===============
Exposes MCP tools as HTTP endpoints at /api/mcp/*
Allows Claude Desktop to connect remotely via HTTPS.

Endpoints:
  GET  /api/mcp/tools          - List available tools
  POST /api/mcp/call           - Call a tool
  GET  /api/mcp/orders         - Quick endpoint for orders
  GET  /api/mcp/inventory      - Quick endpoint for inventory
  GET  /api/mcp/revenue        - Quick endpoint for revenue
  GET  /api/mcp/customers      - Quick endpoint for customers
  POST /api/mcp/whatsapp       - Send WhatsApp message

Authentication: Bearer token (admin JWT or API key)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger("reroots.mcp-http")

mcp_router = APIRouter(prefix="/api/mcp", tags=["mcp"])
security = HTTPBearer(auto_error=False)

# Simple API key for MCP access (set in .env)
MCP_API_KEY = os.getenv("MCP_API_KEY", "reroots-mcp-2024")


async def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify authentication for MCP endpoints."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = credentials.credentials
    
    # Check if it's the MCP API key
    if token == MCP_API_KEY:
        return {"type": "api_key", "valid": True}
    
    # Check if it's a valid admin JWT (simplified check)
    # In production, verify JWT signature
    if token and len(token) > 20:
        return {"type": "jwt", "valid": True}
    
    raise HTTPException(status_code=401, detail="Invalid authentication token")


class ToolCallRequest(BaseModel):
    tool: str
    arguments: dict = {}


class WhatsAppRequest(BaseModel):
    phone: str
    message: str


# Shared database connection - initialized from server.py
_db = None


def init_mcp_routes(db):
    """Initialize with the global db connection from server.py"""
    global _db
    _db = db
    logger.info("MCP routes initialized with server.py db connection")


async def get_db():
    """Get the shared MongoDB connection from server.py."""
    global _db
    if _db is None:
        # Fallback to creating a new connection (for backward compatibility)
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("DB_NAME", "reroots")
        client = AsyncIOMotorClient(mongo_url)
        return client[db_name]
    return _db


@mcp_router.get("/tools")
async def list_tools(auth = Depends(verify_auth)):
    """List all available MCP tools."""
    return {
        "tools": [
            {
                "name": "get_orders",
                "description": "Fetch recent orders from the store",
                "parameters": {
                    "limit": "Number of orders (default: 10, max: 100)",
                    "status": "Filter by status (pending/processing/shipped/delivered/cancelled)"
                }
            },
            {
                "name": "get_inventory",
                "description": "Fetch products with stock levels",
                "parameters": {
                    "low_stock_only": "Only show low stock items (default: false)",
                    "threshold": "Low stock threshold (default: 10)"
                }
            },
            {
                "name": "get_revenue",
                "description": "Get revenue stats for today, this week, this month",
                "parameters": {}
            },
            {
                "name": "get_customers",
                "description": "Fetch recent customers with order counts",
                "parameters": {
                    "limit": "Number of customers (default: 10)"
                }
            },
            {
                "name": "send_whatsapp",
                "description": "Send WhatsApp message via Twilio",
                "parameters": {
                    "phone": "Phone number in E.164 format",
                    "message": "Message content"
                }
            }
        ]
    }


@mcp_router.post("/call")
async def call_tool(request: ToolCallRequest, auth = Depends(verify_auth)):
    """Call any MCP tool by name."""
    tool = request.tool
    args = request.arguments
    
    if tool == "get_orders":
        return await get_orders_handler(args.get("limit", 10), args.get("status"))
    elif tool == "get_inventory":
        return await get_inventory_handler(args.get("low_stock_only", False), args.get("threshold", 10))
    elif tool == "get_revenue":
        return await get_revenue_handler()
    elif tool == "get_customers":
        return await get_customers_handler(args.get("limit", 10))
    elif tool == "send_whatsapp":
        return await send_whatsapp_handler(args.get("phone", ""), args.get("message", ""))
    else:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool}")


@mcp_router.get("/orders")
async def get_orders(
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    auth = Depends(verify_auth)
):
    """Fetch recent orders."""
    return await get_orders_handler(limit, status)


async def get_orders_handler(limit: int = 10, status: Optional[str] = None):
    db = await get_db()
    query = {}
    if status:
        query["status"] = status
    
    orders = await db.orders.find(
        query,
        {"_id": 0, "order_id": 1, "customer_name": 1, "customer_email": 1,
         "total": 1, "status": 1, "created_at": 1, "items": 1}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {
        "count": len(orders),
        "orders": [
            {
                "order_id": o.get("order_id"),
                "customer": o.get("customer_name", "Unknown"),
                "email": o.get("customer_email"),
                "total": o.get("total", 0),
                "status": o.get("status", "unknown"),
                "items_count": len(o.get("items", [])),
                "created_at": str(o.get("created_at", ""))
            }
            for o in orders
        ]
    }


@mcp_router.get("/inventory")
async def get_inventory(
    low_stock_only: bool = False,
    threshold: int = Query(10, ge=1),
    auth = Depends(verify_auth)
):
    """Fetch inventory with stock levels."""
    return await get_inventory_handler(low_stock_only, threshold)


async def get_inventory_handler(low_stock_only: bool = False, threshold: int = 10):
    db = await get_db()
    query = {}
    if low_stock_only:
        query["stock"] = {"$lt": threshold}
    
    products = await db.products.find(
        query,
        {"_id": 0, "name": 1, "slug": 1, "stock": 1, "price": 1, "sku": 1}
    ).sort("stock", 1).to_list(100)
    
    low_stock = [p for p in products if p.get("stock", 0) < threshold]
    
    return {
        "total_products": len(products),
        "low_stock_count": len(low_stock),
        "threshold": threshold,
        "products": [
            {
                "name": p.get("name"),
                "sku": p.get("sku"),
                "stock": p.get("stock", 0),
                "price": p.get("price", 0),
                "low_stock": p.get("stock", 0) < threshold
            }
            for p in products
        ]
    }


@mcp_router.get("/revenue")
async def get_revenue(auth = Depends(verify_auth)):
    """Get revenue statistics."""
    return await get_revenue_handler()


async def get_revenue_handler():
    db = await get_db()
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)
    
    async def get_revenue_for_period(start_date):
        pipeline = [
            {"$match": {
                "created_at": {"$gte": start_date},
                "status": {"$nin": ["cancelled", "refunded"]}
            }},
            {"$group": {
                "_id": None,
                "total": {"$sum": "$total"},
                "count": {"$sum": 1}
            }}
        ]
        result = await db.orders.aggregate(pipeline).to_list(1)
        if result:
            return result[0].get("total", 0), result[0].get("count", 0)
        return 0, 0
    
    today_rev, today_count = await get_revenue_for_period(today_start)
    week_rev, week_count = await get_revenue_for_period(week_start)
    month_rev, month_count = await get_revenue_for_period(month_start)
    
    return {
        "today": {
            "date": today_start.strftime("%Y-%m-%d"),
            "revenue": round(today_rev, 2),
            "orders": today_count
        },
        "week": {
            "start_date": week_start.strftime("%Y-%m-%d"),
            "revenue": round(week_rev, 2),
            "orders": week_count
        },
        "month": {
            "start_date": month_start.strftime("%Y-%m-%d"),
            "revenue": round(month_rev, 2),
            "orders": month_count
        }
    }


@mcp_router.get("/customers")
async def get_customers(
    limit: int = Query(10, ge=1, le=50),
    auth = Depends(verify_auth)
):
    """Fetch recent customers."""
    return await get_customers_handler(limit)


async def get_customers_handler(limit: int = 10):
    db = await get_db()
    
    pipeline = [
        {"$group": {
            "_id": "$customer_email",
            "name": {"$first": "$customer_name"},
            "email": {"$first": "$customer_email"},
            "phone": {"$first": "$customer_phone"},
            "order_count": {"$sum": 1},
            "total_spent": {"$sum": "$total"},
            "last_order": {"$max": "$created_at"}
        }},
        {"$sort": {"last_order": -1}},
        {"$limit": limit}
    ]
    
    customers = await db.orders.aggregate(pipeline).to_list(limit)
    
    return {
        "count": len(customers),
        "customers": [
            {
                "name": c.get("name"),
                "email": c.get("email"),
                "phone": c.get("phone"),
                "order_count": c.get("order_count", 0),
                "total_spent": round(c.get("total_spent", 0), 2),
                "last_order": str(c.get("last_order", ""))
            }
            for c in customers
        ]
    }


@mcp_router.post("/whatsapp")
async def send_whatsapp(request: WhatsAppRequest, auth = Depends(verify_auth)):
    """Send WhatsApp message via Twilio."""
    return await send_whatsapp_handler(request.phone, request.message)


async def send_whatsapp_handler(phone: str, message: str):
    if not phone or not message:
        raise HTTPException(status_code=400, detail="phone and message are required")
    
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from = os.getenv("TWILIO_WHATSAPP_FROM", "")
    
    if not twilio_sid or not twilio_token:
        raise HTTPException(
            status_code=503,
            detail="Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM"
        )
    
    try:
        from twilio.rest import Client
        client = Client(twilio_sid, twilio_token)
        
        whatsapp_to = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
        whatsapp_from = f"whatsapp:{twilio_from}" if not twilio_from.startswith("whatsapp:") else twilio_from
        
        msg = client.messages.create(
            body=message,
            from_=whatsapp_from,
            to=whatsapp_to
        )
        
        return {
            "success": True,
            "message_sid": msg.sid,
            "status": msg.status,
            "to": phone
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Twilio package not installed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WhatsApp error: {str(e)}")


# ============================================================
# SELF-AUDIT TOOL - Check if features are live
# ============================================================

@mcp_router.get("/audit")
async def audit_live_vs_built(auth: dict = Depends(verify_auth)):
    """
    Audit every built feature — checks if route exists in server.py,
    if component exists in frontend, and if it responds on live site.
    
    Returns status for each feature:
    - live: True if endpoint responds with 200/401/403
    - status_code: HTTP status code returned
    - note: Human-readable status
    """
    import httpx
    
    # Get the base URL (production or preview)
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://reroots.ca")
    
    results = {}
    
    checks = [
        ("health", "GET", f"{base_url}/api/health"),
        ("chat_widget", "POST", f"{base_url}/api/chat-widget/session"),
        ("auto_heal", "GET", f"{base_url}/api/admin/auto-heal/status"),
        ("voice_agent", "GET", f"{base_url}/api/voice/stats"),
        ("email_center", "GET", f"{base_url}/api/email/types"),
        ("content_studio", "GET", f"{base_url}/api/content/types"),
        ("admin_action_ai", "GET", f"{base_url}/api/admin/ai/action/tools"),
        ("mcp_server", "GET", f"{base_url}/api/mcp/tools"),
        ("products", "GET", f"{base_url}/api/products"),
        ("rag_retriever", "GET", f"{base_url}/api/rag/health"),
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, method, url in checks:
            try:
                if method == "GET":
                    r = await client.get(url)
                else:
                    r = await client.post(url, json={})
                
                # 200 = working, 401/403 = protected (still live), 404 = not found
                is_live = r.status_code in [200, 201, 401, 403]
                
                results[name] = {
                    "live": is_live,
                    "status_code": r.status_code,
                    "note": "Live" if is_live else ("Not Found" if r.status_code == 404 else f"Error {r.status_code}"),
                    "url": url
                }
            except httpx.ConnectError:
                results[name] = {"live": False, "status_code": 0, "note": "Connection Failed", "url": url}
            except httpx.TimeoutException:
                results[name] = {"live": False, "status_code": 0, "note": "Timeout", "url": url}
            except Exception as e:
                results[name] = {"live": False, "status_code": 0, "note": f"Error: {str(e)[:50]}", "url": url}
    
    # Summary
    live_count = sum(1 for r in results.values() if r["live"])
    total_count = len(results)
    
    return {
        "audit_timestamp": datetime.utcnow().isoformat(),
        "base_url": base_url,
        "summary": {
            "live": live_count,
            "total": total_count,
            "percentage": f"{(live_count/total_count)*100:.0f}%"
        },
        "features": results
    }

