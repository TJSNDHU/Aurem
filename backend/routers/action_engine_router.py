"""
AUREM Action Engine Router - Execute real-world actions

Endpoints:
- POST /api/action-engine/execute - Execute an action
- POST /api/action-engine/tool-call - Handle AI function call
- GET /api/action-engine/tools - Get tool definitions
- GET /api/action-engine/history/{business_id} - Get action history
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging

router = APIRouter(prefix="/api/action-engine", tags=["AUREM Action Engine"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


class ExecuteActionRequest(BaseModel):
    business_id: str
    action_type: str  # calendar.check_availability, stripe.create_invoice, etc.
    parameters: Dict[str, Any]
    triggered_by: str = "user"


class ToolCallRequest(BaseModel):
    business_id: str
    function_name: str
    arguments: Dict[str, Any]


@router.get("/tools")
async def get_tools():
    """Get all available tool definitions for AI function calling"""
    from services.aurem_commercial.action_engine import get_action_engine
    engine = get_action_engine(get_db())
    return {"tools": engine.get_tool_definitions()}


@router.post("/execute")
async def execute_action(request: ExecuteActionRequest, req: Request):
    """Execute an action (calendar, payment, email, etc.)"""
    from services.aurem_commercial.action_engine import get_action_engine, ActionType
    
    engine = get_action_engine(get_db())
    ip = req.client.host if req.client else None
    
    # Map string to ActionType
    type_map = {
        "calendar.check_availability": ActionType.CALENDAR_CHECK,
        "calendar.book_appointment": ActionType.CALENDAR_BOOK,
        "stripe.create_invoice": ActionType.STRIPE_INVOICE,
        "stripe.create_payment_link": ActionType.STRIPE_LINK,
        "email.send": ActionType.EMAIL_SEND,
        "whatsapp.send": ActionType.WHATSAPP_SEND
    }
    
    action_type = type_map.get(request.action_type)
    if not action_type:
        raise HTTPException(400, f"Unknown action type: {request.action_type}")
    
    result = await engine.execute(
        business_id=request.business_id,
        action_type=action_type,
        params=request.parameters,
        triggered_by=request.triggered_by,
        ip=ip
    )
    
    return {
        "action_id": result.action_id,
        "status": result.status.value,
        "result": result.result,
        "error": result.error
    }


@router.post("/tool-call")
async def handle_tool_call(request: ToolCallRequest, req: Request):
    """Handle an AI function/tool call"""
    from services.aurem_commercial.action_engine import get_action_engine
    
    engine = get_action_engine(get_db())
    ip = req.client.host if req.client else None
    
    result = await engine.handle_tool_call(
        business_id=request.business_id,
        func=request.function_name,
        args=request.arguments,
        ip=ip
    )
    
    return result


@router.get("/history/{business_id}")
async def get_action_history(business_id: str, limit: int = 20):
    """Get action execution history for a business"""
    db = get_db()
    
    actions = await db.aurem_actions.find(
        {"business_id": business_id},
        {"_id": 0}
    ).sort("started_at", -1).limit(limit).to_list(limit)
    
    return {"actions": actions, "count": len(actions)}


@router.get("/health")
async def health():
    """Health check"""
    from services.aurem_commercial.action_engine import get_action_engine
    
    try:
        engine = get_action_engine(get_db())
        tools = engine.get_tool_definitions()
        return {"status": "healthy", "tools_count": len(tools)}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
