"""
Admin Action AI API Routes
═══════════════════════════════════════════════════════════════════
REST API endpoints for the Admin Action AI.
Mounted at /api/admin/ai/action (separate from existing db_query_routes)
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ai/action", tags=["Admin Action AI"])

# Database reference - set from server.py
_db = None


def set_db(database):
    """Set database reference from server.py startup."""
    global _db
    _db = database
    logger.info("Admin Action AI routes: Database reference set")


# ═══════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════

class ActionRequest(BaseModel):
    """Request to execute an admin action."""
    query: str  # Natural language query
    confirm: bool = False  # For destructive actions


class ActionResponse(BaseModel):
    """Response from admin action."""
    success: bool
    action: Optional[str] = None
    explanation: Optional[str] = None
    result: Optional[dict] = None
    summary: Optional[str] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.post("/execute", response_model=ActionResponse)
async def execute_action(request: Request, body: ActionRequest):
    """
    Execute an admin action via natural language.
    
    Examples:
    - "Show me pending orders from the last week"
    - "What's our revenue for the past 30 days?"
    - "Create a 20% discount code WINTER20"
    - "Update AURA-GEN Rich Cream stock to 50"
    - "Flag order ORD-12345 for review - suspicious address"
    - "Send WhatsApp to +14165551234: Your order has shipped!"
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    from services.admin_action_ai import get_admin_action_ai
    
    ai = get_admin_action_ai(_db)
    result = await ai.execute(body.query)
    
    return result


@router.get("/suggestions")
async def get_suggestions(request: Request):
    """
    Get AI-powered suggestions based on current data.
    Analyzes stock levels, pending orders, revenue patterns.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    from services.admin_action_ai import get_admin_action_ai
    
    ai = get_admin_action_ai(_db)
    return await ai.suggest_actions()


@router.get("/tools")
async def list_tools():
    """
    List available admin action tools.
    """
    return {
        "tools": [
            {
                "name": "get_orders",
                "description": "Get orders with filters (status, email, date range)",
                "example": "Show me pending orders from the last 7 days"
            },
            {
                "name": "get_customers",
                "description": "Find customers by email or phone",
                "example": "Find customer with email john@example.com"
            },
            {
                "name": "get_revenue_summary",
                "description": "Revenue, order count, avg order value for a period",
                "example": "What's our revenue for the past month?"
            },
            {
                "name": "update_product_stock",
                "description": "Update product stock level",
                "example": "Set AURA-GEN Rich Cream stock to 100"
            },
            {
                "name": "send_whatsapp_to_customer",
                "description": "Send WhatsApp message to customer",
                "example": "Send WhatsApp to +14165551234: Your order shipped!"
            },
            {
                "name": "create_discount_code",
                "description": "Create a new discount/promo code",
                "example": "Create 15% off code SAVE15 for 2 weeks"
            },
            {
                "name": "flag_order",
                "description": "Flag an order for review (fraud, priority, etc.)",
                "example": "Flag order ORD-123 as priority - VIP customer"
            },
            {
                "name": "get_low_stock_products",
                "description": "Get products below stock threshold",
                "example": "What products are running low?"
            }
        ]
    }


@router.get("/health")
async def health():
    """Health check for Admin Action AI."""
    return {
        "status": "ok",
        "service": "admin-action-ai",
        "tools_count": 8
    }
