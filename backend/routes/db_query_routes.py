"""
DB Query Routes
===============
Admin endpoint for natural language database queries.
Powers the DatabaseQueryChat.jsx component in the admin panel.

Endpoints:
  POST /api/admin/db-query - Execute a natural language query against MongoDB
  
NOTE: Uses the global `db` connection from server.py - do NOT create a new connection
"""

import os
import logging
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger("reroots.db-query")

db_query_router = APIRouter(prefix="/api/admin", tags=["db-query"])
security = HTTPBearer(auto_error=False)

# Will be set by init_db_query_routes() from server.py
_db = None


def init_db_query_routes(db):
    """Initialize with the global db connection from server.py"""
    global _db
    _db = db
    logger.info("DB Query routes initialized with server.py db connection")


async def get_db():
    """Get the shared MongoDB connection from server.py."""
    global _db
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _db


async def verify_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin authentication."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    # In production, verify JWT token here
    return {"authenticated": True}


class QueryRequest(BaseModel):
    query: str
    collection: Optional[str] = None


class QueryResponse(BaseModel):
    success: bool
    data: Optional[list] = None
    count: Optional[int] = None
    query_interpreted: Optional[str] = None
    error: Optional[str] = None


# Pre-defined query patterns for natural language
QUERY_PATTERNS = {
    "orders today": {
        "collection": "orders",
        "filter": lambda: {"created_at": {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0)}},
        "description": "Orders created today"
    },
    "recent orders": {
        "collection": "orders",
        "filter": lambda: {},
        "sort": [("created_at", -1)],
        "limit": 10,
        "description": "Last 10 orders"
    },
    "low stock": {
        "collection": "products",
        "filter": lambda: {"stock": {"$lt": 10}},
        "description": "Products with stock below 10"
    },
    "all products": {
        "collection": "products",
        "filter": lambda: {},
        "description": "All products"
    },
    "all customers": {
        "collection": "customers",
        "filter": lambda: {},
        "description": "All customers"
    },
    "pending orders": {
        "collection": "orders",
        "filter": lambda: {"status": "pending"},
        "description": "Orders with pending status"
    },
    "total revenue": {
        "collection": "orders",
        "aggregate": [
            {"$match": {"status": {"$nin": ["cancelled", "refunded"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}}
        ],
        "description": "Total revenue from all orders"
    }
}


def parse_natural_query(query: str) -> dict:
    """Parse natural language query into MongoDB query."""
    query_lower = query.lower().strip()
    
    # Check for exact matches first
    for pattern, config in QUERY_PATTERNS.items():
        if pattern in query_lower:
            return config
    
    # Check for collection-specific queries
    if "order" in query_lower:
        return {
            "collection": "orders",
            "filter": lambda: {},
            "sort": [("created_at", -1)],
            "limit": 20,
            "description": "Recent orders"
        }
    elif "product" in query_lower:
        return {
            "collection": "products",
            "filter": lambda: {},
            "description": "All products"
        }
    elif "customer" in query_lower:
        return {
            "collection": "customers",
            "filter": lambda: {},
            "description": "All customers"
        }
    elif "inventory" in query_lower or "stock" in query_lower:
        return {
            "collection": "products",
            "filter": lambda: {},
            "sort": [("stock", 1)],
            "description": "Products by stock level"
        }
    
    # Default: return error
    return {"error": f"Could not understand query: {query}"}


@db_query_router.post("/db-query", response_model=QueryResponse)
async def execute_query(request: QueryRequest, auth = Depends(verify_admin)):
    """Execute a natural language database query."""
    try:
        db = await get_db()
        
        # Parse the query
        parsed = parse_natural_query(request.query)
        
        if "error" in parsed:
            return QueryResponse(
                success=False,
                error=parsed["error"],
                query_interpreted=None
            )
        
        collection_name = request.collection or parsed.get("collection", "orders")
        collection = db[collection_name]
        
        # Handle aggregation queries
        if "aggregate" in parsed:
            cursor = collection.aggregate(parsed["aggregate"])
            results = await cursor.to_list(100)
        else:
            # Build the query
            filter_func = parsed.get("filter", lambda: {})
            query_filter = filter_func()
            
            cursor = collection.find(query_filter, {"_id": 0})
            
            if "sort" in parsed:
                cursor = cursor.sort(parsed["sort"])
            
            limit = parsed.get("limit", 50)
            results = await cursor.limit(limit).to_list(limit)
        
        # Convert datetime objects to strings for JSON serialization
        for doc in results:
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.isoformat()
        
        return QueryResponse(
            success=True,
            data=results,
            count=len(results),
            query_interpreted=parsed.get("description", request.query)
        )
        
    except Exception as e:
        logger.error(f"DB Query error: {e}")
        return QueryResponse(
            success=False,
            error=str(e)
        )


@db_query_router.get("/db-query/collections")
async def list_collections(auth = Depends(verify_admin)):
    """List available collections."""
    try:
        db = await get_db()
        collections = await db.list_collection_names()
        
        # Get document counts
        result = []
        for coll in collections:
            count = await db[coll].count_documents({})
            result.append({"name": coll, "count": count})
        
        return {"collections": sorted(result, key=lambda x: x["name"])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@db_query_router.get("/db-query/examples")
async def get_query_examples():
    """Get example queries."""
    return {
        "examples": [
            "Show me orders today",
            "Recent orders",
            "Low stock products",
            "All products",
            "Pending orders",
            "Total revenue",
            "All customers"
        ]
    }
