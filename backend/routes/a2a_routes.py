"""
A2A Protocol Routes for Reroots AI
Agent-to-Agent communication protocol (Google A2A standard).

Makes Reroots AI discoverable and callable by other AI agents.
Exposes skills: skincare_advice, skin_analysis, order_management, inventory_check.

Reference: https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["A2A Protocol"])

# Database reference
_db = None


def set_db(database):
    """Set database reference."""
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════
# A2A REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════

class A2ATaskRequest(BaseModel):
    """A2A task request format."""
    task_id: str
    skill_id: str
    input: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    callback_url: Optional[str] = None


class A2ATaskResponse(BaseModel):
    """A2A task response format."""
    task_id: str
    status: str  # pending, in_progress, completed, failed
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# AGENT DISCOVERY (.well-known/agent.json)
# ═══════════════════════════════════════════════════════════════════

@router.get("/.well-known/agent.json")
async def get_agent_card():
    """
    A2A Agent Discovery Endpoint.
    
    Returns the agent card that describes Reroots AI's capabilities
    to other A2A-compatible agents.
    
    This makes Reroots AI discoverable by:
    - Google's A2A-compatible agents
    - Other platforms implementing A2A protocol
    - Enterprise AI orchestration systems
    """
    agent_card_path = Path(__file__).parent.parent / "a2a" / "agent_card.json"
    
    try:
        with open(agent_card_path, "r") as f:
            agent_card = json.load(f)
        
        # Update URL dynamically based on environment
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://reroots.ca")
        agent_card["url"] = f"{base_url}/api/a2a"
        
        return JSONResponse(content=agent_card)
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Agent card not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid agent card format")


# ═══════════════════════════════════════════════════════════════════
# A2A TASK ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@router.post("/api/a2a/task")
async def handle_a2a_task(
    request: Request,
    task: A2ATaskRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    A2A Task Handler.
    
    Receives tasks from other AI agents and routes them to appropriate
    Reroots AI skills.
    
    Supported skills:
    - skincare_advice: Personalized skincare recommendations
    - skin_analysis: Analyze skin photos (requires image in input)
    - order_management: Check order status
    - inventory_check: Check product availability
    - product_info: Get product details
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    # Validate API key for B2B operations
    b2b_skills = ["supplier_order"]
    if task.skill_id in b2b_skills:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="API key required for this skill")
        # Validate API key here (integrate with api_key_manager)
    
    # Log A2A task
    await _db.a2a_tasks.insert_one({
        "task_id": task.task_id,
        "skill_id": task.skill_id,
        "input": task.input,
        "context": task.context,
        "status": "in_progress",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_ip": request.client.host
    })
    
    try:
        # Route to appropriate skill handler
        if task.skill_id == "skincare_advice":
            result = await handle_skincare_advice(task.input)
        elif task.skill_id == "skin_analysis":
            result = await handle_skin_analysis(task.input)
        elif task.skill_id == "order_management":
            result = await handle_order_management(task.input)
        elif task.skill_id == "inventory_check":
            result = await handle_inventory_check(task.input)
        elif task.skill_id == "product_info":
            result = await handle_product_info(task.input)
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unknown skill: {task.skill_id}"
            )
        
        # Update task status
        await _db.a2a_tasks.update_one(
            {"task_id": task.task_id},
            {"$set": {"status": "completed", "output": result}}
        )
        
        return A2ATaskResponse(
            task_id=task.task_id,
            status="completed",
            output=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"A2A task error: {e}", exc_info=True)
        
        await _db.a2a_tasks.update_one(
            {"task_id": task.task_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )
        
        return A2ATaskResponse(
            task_id=task.task_id,
            status="failed",
            error=str(e)
        )


# ═══════════════════════════════════════════════════════════════════
# SKILL HANDLERS
# ═══════════════════════════════════════════════════════════════════

async def handle_skincare_advice(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle skincare advice requests from other agents."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    from brands_config import get_protected_system_prompt
    
    query = input_data.get("query", input_data.get("message", ""))
    skin_type = input_data.get("skin_type", "")
    concerns = input_data.get("concerns", [])
    
    if not query:
        raise ValueError("Missing 'query' in input")
    
    # Build context
    context_parts = []
    if skin_type:
        context_parts.append(f"Customer's skin type: {skin_type}")
    if concerns:
        context_parts.append(f"Skin concerns: {', '.join(concerns)}")
    
    full_query = query
    if context_parts:
        full_query = f"{' | '.join(context_parts)}\n\nQuestion: {query}"
    
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise ValueError("AI service not configured")
    
    system_prompt = get_protected_system_prompt("reroots")
    
    chat = LlmChat(
        api_key=api_key,
        session_id=f"a2a_skincare_{datetime.now().timestamp()}",
        system_message=system_prompt
    )
    chat.with_model("openai", "gpt-4o")
    
    response = await chat.send_message(UserMessage(text=full_query))
    
    return {
        "response": response,
        "skin_type": skin_type,
        "concerns": concerns
    }


async def handle_skin_analysis(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle skin analysis requests with image."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    image_data = input_data.get("image", input_data.get("image_url", ""))
    message = input_data.get("message", "Please analyze this skin photo")
    
    if not image_data:
        raise ValueError("Missing 'image' in input (base64 or URL)")
    
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise ValueError("AI service not configured")
    
    analysis_prompt = """You are a professional skincare advisor. Analyze the skin in this image and provide:
1. Skin type assessment (oily, dry, combination, sensitive)
2. Visible concerns (acne, hyperpigmentation, wrinkles, etc.)
3. Product recommendations from the AURA-GEN line
4. A brief skincare routine suggestion"""
    
    chat = LlmChat(
        api_key=api_key,
        session_id=f"a2a_analysis_{datetime.now().timestamp()}",
        system_message=analysis_prompt
    )
    chat.with_model("openai", "gpt-4o")
    
    user_msg = UserMessage(text=message, image_url=image_data)
    response = await chat.send_message(user_msg)
    
    return {
        "analysis": response,
        "analyzed_at": datetime.now(timezone.utc).isoformat()
    }


async def handle_order_management(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle order management requests."""
    order_id = input_data.get("order_id", "")
    email = input_data.get("email", "")
    # action can be: status, tracking, history
    _ = input_data.get("action", "status")
    
    if not order_id and not email:
        raise ValueError("Missing 'order_id' or 'email' in input")
    
    # Query orders from database
    query = {}
    if order_id:
        query["order_id"] = order_id
    if email:
        query["customer_email"] = email
    
    orders = await _db.orders.find(query, {"_id": 0}).limit(10).to_list(10)
    
    if not orders:
        return {
            "found": False,
            "message": "No orders found matching the criteria"
        }
    
    return {
        "found": True,
        "orders": orders,
        "count": len(orders)
    }


async def handle_inventory_check(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle inventory/stock check requests."""
    product_id = input_data.get("product_id", "")
    product_name = input_data.get("product_name", "")
    sku = input_data.get("sku", "")
    
    query = {}
    if product_id:
        query["product_id"] = product_id
    elif sku:
        query["sku"] = sku
    elif product_name:
        query["name"] = {"$regex": product_name, "$options": "i"}
    else:
        # Return all products
        pass
    
    products = await _db.products.find(query, {"_id": 0}).limit(20).to_list(20)
    
    inventory = []
    for product in products:
        inventory.append({
            "name": product.get("name"),
            "sku": product.get("sku"),
            "in_stock": product.get("in_stock", True),
            "quantity": product.get("quantity", "Available"),
            "price": product.get("price")
        })
    
    return {
        "products": inventory,
        "count": len(inventory),
        "checked_at": datetime.now(timezone.utc).isoformat()
    }


async def handle_product_info(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle product information requests."""
    product_id = input_data.get("product_id", "")
    product_name = input_data.get("product_name", "")
    slug = input_data.get("slug", "")
    
    query = {}
    if product_id:
        query["product_id"] = product_id
    elif slug:
        query["slug"] = slug
    elif product_name:
        query["name"] = {"$regex": product_name, "$options": "i"}
    else:
        raise ValueError("Missing product identifier in input")
    
    product = await _db.products.find_one(query, {"_id": 0})
    
    if not product:
        return {
            "found": False,
            "message": "Product not found"
        }
    
    return {
        "found": True,
        "product": product
    }


# ═══════════════════════════════════════════════════════════════════
# A2A TASK STATUS
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/a2a/task/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of an A2A task."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    task = await _db.a2a_tasks.find_one(
        {"task_id": task_id},
        {"_id": 0}
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return A2ATaskResponse(
        task_id=task["task_id"],
        status=task.get("status", "unknown"),
        output=task.get("output"),
        error=task.get("error")
    )
