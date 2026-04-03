"""
Admin Action AI Service
═══════════════════════════════════════════════════════════════════
AI assistant that can execute real admin actions via natural language.
Tools: orders, customers, revenue, stock, WhatsApp, discount codes, flags.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Callable
from functools import wraps

# Import TOON converter
from utils.toon import json_to_toon

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════════════════

class AdminTools:
    """Collection of admin action tools."""
    
    def __init__(self, db):
        self.db = db
        self.twilio_client = None
        self._init_twilio()
    
    def _init_twilio(self):
        """Initialize Twilio client for WhatsApp."""
        try:
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            if account_sid and auth_token:
                from twilio.rest import Client
                self.twilio_client = Client(account_sid, auth_token)
                logger.info("AdminTools: Twilio client initialized")
        except Exception as e:
            logger.warning(f"AdminTools: Twilio init failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # TOOL 1: GET ORDERS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_orders(
        self,
        status: str = None,
        customer_email: str = None,
        limit: int = 10,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get orders with optional filters.
        
        Args:
            status: Filter by status (pending, processing, shipped, delivered, cancelled)
            customer_email: Filter by customer email
            limit: Max orders to return
            days: Look back period in days
        """
        query = {}
        
        if status:
            query["status"] = status
        
        if customer_email:
            query["customer.email"] = {"$regex": customer_email, "$options": "i"}
        
        # Date filter
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query["created_at"] = {"$gte": cutoff}
        
        orders = await self.db.orders.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return {
            "success": True,
            "count": len(orders),
            "orders": orders
        }
    
    # ═══════════════════════════════════════════════════════════════
    # TOOL 2: GET CUSTOMERS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_customers(
        self,
        email: str = None,
        phone: str = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get customers with optional filters.
        
        Args:
            email: Filter by email (partial match)
            phone: Filter by phone number
            limit: Max customers to return
        """
        query = {}
        
        if email:
            query["email"] = {"$regex": email, "$options": "i"}
        
        if phone:
            query["phone"] = {"$regex": phone.replace("+", "").replace("-", ""), "$options": "i"}
        
        # Try multiple collections where customers might be
        customers = []
        
        for collection in ["customers", "users", "crm_customers"]:
            try:
                results = await self.db[collection].find(
                    query,
                    {"_id": 0, "password": 0, "password_hash": 0}
                ).limit(limit).to_list(limit)
                customers.extend(results)
            except Exception:
                continue
        
        # Deduplicate by email
        seen_emails = set()
        unique_customers = []
        for c in customers:
            email = c.get("email", "")
            if email and email not in seen_emails:
                seen_emails.add(email)
                unique_customers.append(c)
        
        return {
            "success": True,
            "count": len(unique_customers),
            "customers": unique_customers[:limit]
        }
    
    # ═══════════════════════════════════════════════════════════════
    # TOOL 3: GET REVENUE SUMMARY
    # ═══════════════════════════════════════════════════════════════
    
    async def get_revenue_summary(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get revenue summary for a period.
        
        Args:
            days: Look back period in days
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Aggregate orders
        pipeline = [
            {"$match": {
                "created_at": {"$gte": cutoff},
                "status": {"$nin": ["cancelled", "refunded"]}
            }},
            {"$group": {
                "_id": None,
                "total_revenue": {"$sum": "$total"},
                "order_count": {"$sum": 1},
                "avg_order_value": {"$avg": "$total"}
            }}
        ]
        
        result = await self.db.orders.aggregate(pipeline).to_list(1)
        
        if result:
            summary = result[0]
            return {
                "success": True,
                "period_days": days,
                "total_revenue": round(summary.get("total_revenue", 0), 2),
                "order_count": summary.get("order_count", 0),
                "avg_order_value": round(summary.get("avg_order_value", 0), 2),
                "currency": "CAD"
            }
        
        return {
            "success": True,
            "period_days": days,
            "total_revenue": 0,
            "order_count": 0,
            "avg_order_value": 0,
            "currency": "CAD"
        }
    
    # ═══════════════════════════════════════════════════════════════
    # TOOL 4: UPDATE PRODUCT STOCK
    # ═══════════════════════════════════════════════════════════════
    
    async def update_product_stock(
        self,
        product_name: str,
        new_quantity: int = None,
        adjustment: int = None
    ) -> Dict[str, Any]:
        """
        Update product stock level.
        
        Args:
            product_name: Product name to update (partial match supported)
            new_quantity: Set exact quantity (overrides adjustment)
            adjustment: Adjust by +/- amount
        """
        if new_quantity is None and adjustment is None:
            return {"success": False, "error": "Provide new_quantity or adjustment"}
        
        # Find product
        product = await self.db.products.find_one(
            {"name": {"$regex": product_name, "$options": "i"}},
            {"_id": 1, "name": 1, "stock": 1}
        )
        
        if not product:
            return {"success": False, "error": f"Product '{product_name}' not found"}
        
        old_stock = product.get("stock", 0)
        
        if new_quantity is not None:
            new_stock = new_quantity
        else:
            new_stock = old_stock + adjustment
        
        # Prevent negative stock
        if new_stock < 0:
            return {"success": False, "error": "Cannot set negative stock"}
        
        # Update
        await self.db.products.update_one(
            {"_id": product["_id"]},
            {"$set": {"stock": new_stock, "updated_at": datetime.now(timezone.utc)}}
        )
        
        # Log the change
        await self.db.stock_changes.insert_one({
            "product_id": str(product["_id"]),
            "product_name": product["name"],
            "old_stock": old_stock,
            "new_stock": new_stock,
            "change": new_stock - old_stock,
            "changed_by": "admin_ai",
            "timestamp": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "product": product["name"],
            "old_stock": old_stock,
            "new_stock": new_stock,
            "change": new_stock - old_stock
        }
    
    # ═══════════════════════════════════════════════════════════════
    # TOOL 5: SEND WHATSAPP TO CUSTOMER
    # ═══════════════════════════════════════════════════════════════
    
    async def send_whatsapp_to_customer(
        self,
        phone: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send WhatsApp message to a customer.
        
        Args:
            phone: Customer phone number (with country code)
            message: Message to send
        """
        if not self.twilio_client:
            return {"success": False, "error": "Twilio not configured"}
        
        # Normalize phone number
        phone = phone.replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            phone = f"+1{phone}"  # Default to Canada/US
        
        try:
            from_number = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")
            if not from_number:
                return {"success": False, "error": "TWILIO_WHATSAPP_NUMBER not configured"}
            
            result = self.twilio_client.messages.create(
                body=message,
                from_=f"whatsapp:{from_number}",
                to=f"whatsapp:{phone}"
            )
            
            # Log message
            await self.db.admin_whatsapp_log.insert_one({
                "to": phone,
                "message": message,
                "sid": result.sid,
                "status": result.status,
                "sent_by": "admin_ai",
                "timestamp": datetime.now(timezone.utc)
            })
            
            return {
                "success": True,
                "message_sid": result.sid,
                "status": result.status,
                "to": phone
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════
    # TOOL 6: CREATE DISCOUNT CODE
    # ═══════════════════════════════════════════════════════════════
    
    async def create_discount_code(
        self,
        code: str,
        discount_percent: int = None,
        discount_amount: float = None,
        expires_days: int = 30,
        max_uses: int = 100,
        min_order: float = 0
    ) -> Dict[str, Any]:
        """
        Create a new discount code.
        
        Args:
            code: Discount code (will be uppercased)
            discount_percent: Percentage discount (e.g., 15 for 15%)
            discount_amount: Fixed dollar amount discount
            expires_days: Days until expiry
            max_uses: Maximum number of uses
            min_order: Minimum order value required
        """
        if not discount_percent and not discount_amount:
            return {"success": False, "error": "Provide discount_percent or discount_amount"}
        
        code = code.upper().strip()
        
        # Check if code exists
        existing = await self.db.discount_codes.find_one({"code": code})
        if existing:
            return {"success": False, "error": f"Code '{code}' already exists"}
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        
        discount_doc = {
            "code": code,
            "type": "percent" if discount_percent else "fixed",
            "value": discount_percent or discount_amount,
            "min_order": min_order,
            "max_uses": max_uses,
            "uses": 0,
            "expires_at": expires_at,
            "active": True,
            "created_by": "admin_ai",
            "created_at": datetime.now(timezone.utc)
        }
        
        await self.db.discount_codes.insert_one(discount_doc)
        
        return {
            "success": True,
            "code": code,
            "type": discount_doc["type"],
            "value": discount_doc["value"],
            "expires_at": expires_at.isoformat(),
            "max_uses": max_uses
        }
    
    # ═══════════════════════════════════════════════════════════════
    # TOOL 7: FLAG ORDER
    # ═══════════════════════════════════════════════════════════════
    
    async def flag_order(
        self,
        order_id: str,
        flag_type: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Flag an order for review.
        
        Args:
            order_id: Order ID to flag
            flag_type: Type of flag (fraud, review, priority, hold)
            reason: Reason for flagging
        """
        valid_flags = ["fraud", "review", "priority", "hold", "vip", "issue"]
        if flag_type not in valid_flags:
            return {"success": False, "error": f"Invalid flag_type. Use: {valid_flags}"}
        
        # Find order
        order = await self.db.orders.find_one(
            {"$or": [
                {"order_id": order_id},
                {"order_number": order_id}
            ]}
        )
        
        if not order:
            return {"success": False, "error": f"Order '{order_id}' not found"}
        
        # Add flag
        flag_doc = {
            "type": flag_type,
            "reason": reason,
            "flagged_by": "admin_ai",
            "flagged_at": datetime.now(timezone.utc)
        }
        
        await self.db.orders.update_one(
            {"_id": order["_id"]},
            {
                "$push": {"flags": flag_doc},
                "$set": {"has_flags": True}
            }
        )
        
        return {
            "success": True,
            "order_id": order_id,
            "flag_type": flag_type,
            "reason": reason
        }
    
    # ═══════════════════════════════════════════════════════════════
    # TOOL 8: GET LOW STOCK PRODUCTS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_low_stock_products(
        self,
        threshold: int = 10
    ) -> Dict[str, Any]:
        """
        Get products with stock below threshold.
        
        Args:
            threshold: Stock level threshold (default 10)
        """
        products = await self.db.products.find(
            {"stock": {"$lt": threshold, "$gte": 0}},
            {"_id": 0, "name": 1, "stock": 1, "sku": 1, "brand": 1}
        ).sort("stock", 1).to_list(50)
        
        # Categorize by urgency
        critical = [p for p in products if p.get("stock", 0) <= 2]
        low = [p for p in products if 2 < p.get("stock", 0) <= 5]
        warning = [p for p in products if 5 < p.get("stock", 0) < threshold]
        
        return {
            "success": True,
            "threshold": threshold,
            "total_low_stock": len(products),
            "critical": {"count": len(critical), "products": critical},
            "low": {"count": len(low), "products": low},
            "warning": {"count": len(warning), "products": warning}
        }


# ═══════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═══════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS = """
Available tools:

1. get_orders(status, customer_email, limit, days)
   - Get orders with filters
   - status: pending, processing, shipped, delivered, cancelled
   - Example: get_orders(status="pending", days=7)

2. get_customers(email, phone, limit)
   - Find customers by email or phone
   - Example: get_customers(email="john@example.com")

3. get_revenue_summary(days)
   - Revenue, order count, avg order value
   - Example: get_revenue_summary(days=30)

4. update_product_stock(product_name, new_quantity, adjustment)
   - Set stock or adjust +/-
   - Example: update_product_stock("AURA-GEN Rich Cream", adjustment=-5)

5. send_whatsapp_to_customer(phone, message)
   - Send WhatsApp message
   - Example: send_whatsapp_to_customer("+14165551234", "Your order shipped!")

6. create_discount_code(code, discount_percent, discount_amount, expires_days, max_uses, min_order)
   - Create promo code
   - Example: create_discount_code("SUMMER20", discount_percent=20, expires_days=14)

7. flag_order(order_id, flag_type, reason)
   - Flag order for review
   - flag_type: fraud, review, priority, hold, vip, issue
   - Example: flag_order("ORD-12345", "priority", "VIP customer")

8. get_low_stock_products(threshold)
   - Products below stock threshold
   - Example: get_low_stock_products(threshold=5)
"""


# ═══════════════════════════════════════════════════════════════════
# AI ACTION EXECUTOR
# ═══════════════════════════════════════════════════════════════════

class AdminActionAI:
    """AI that interprets natural language and executes admin actions."""
    
    def __init__(self, db):
        self.db = db
        self.tools = AdminTools(db)
    
    async def execute(self, user_query: str) -> Dict[str, Any]:
        """
        Process natural language query and execute appropriate action.
        
        Args:
            user_query: Natural language request from admin
        
        Returns:
            Result of the action with AI explanation
        """
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return {"success": False, "error": "EMERGENT_LLM_KEY not configured"}
        
        # Step 1: Use LLM to interpret query and generate tool call
        system_prompt = f"""You are an admin action assistant for Reroots Aesthetics Inc.
Your job is to interpret admin requests and call the appropriate tool.

{TOOL_DEFINITIONS}

INSTRUCTIONS:
1. Analyze the user's request
2. Determine which tool to use
3. Extract the parameters from the request
4. Return a JSON object with:
   - "tool": the tool name
   - "params": dictionary of parameters
   - "explanation": brief explanation of what you're doing

Example response:
{{"tool": "get_orders", "params": {{"status": "pending", "limit": 10}}, "explanation": "Getting all pending orders"}}

If the request is unclear or cannot be fulfilled with available tools, return:
{{"tool": "none", "params": {{}}, "explanation": "Explain what you need or why this can't be done"}}

IMPORTANT:
- Always respond with valid JSON only
- Never execute dangerous operations without clear intent
- For stock updates, be careful about the direction (+/-)
"""
        
        chat = LlmChat(
            api_key=api_key,
            session_id="admin_action_temp",
            system_message=system_prompt
        )
        chat.with_model("openai", "gpt-4o-mini")  # Fast for tool selection
        
        try:
            response = await chat.send_message(UserMessage(text=user_query))
            logger.info(f"AdminActionAI raw response: {response[:500]}")
            
            # Parse JSON response - handle nested JSON
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if not json_match:
                return {
                    "success": False,
                    "error": "Could not parse AI response",
                    "raw_response": response
                }
            
            action = json.loads(json_match.group())
            tool_name = action.get("tool", "none")
            params = action.get("params", {})
            explanation = action.get("explanation", "")
            
            if tool_name == "none":
                return {
                    "success": True,
                    "action": "none",
                    "message": explanation
                }
            
            # Step 2: Execute the tool
            tool_method = getattr(self.tools, tool_name, None)
            if not tool_method:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
            
            # Execute tool
            result = await tool_method(**params)
            
            # Step 3: Generate human-friendly summary
            summary = await self._generate_summary(user_query, tool_name, result)
            
            return {
                "success": True,
                "action": tool_name,
                "parameters": params,
                "explanation": explanation,
                "result": result,
                "summary": summary
            }
            
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON parse error: {e}"}
        except Exception as e:
            logger.error(f"AdminActionAI error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_summary(
        self,
        query: str,
        tool: str,
        result: Dict[str, Any]
    ) -> str:
        """Generate a human-friendly summary of the result."""
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return str(result)
        
        try:
            chat = LlmChat(
                api_key=api_key,
                session_id="summary_temp",
                system_message="Summarize this admin action result in 1-2 sentences. Be concise and helpful."
            )
            chat.with_model("openai", "gpt-4o-mini")
            
            # Convert list results to TOON format for LLM efficiency
            result_for_llm = result
            if tool == "get_orders" and "orders" in result and isinstance(result["orders"], list):
                # Convert orders list to TOON
                orders_toon = json_to_toon(result["orders"], "Orders")
                result_for_llm = f"Count: {result.get('count', 0)}\n{orders_toon}"
            elif tool == "get_customers" and "customers" in result and isinstance(result["customers"], list):
                # Convert customers list to TOON
                customers_toon = json_to_toon(result["customers"], "Customers")
                result_for_llm = f"Count: {result.get('count', 0)}\n{customers_toon}"
            else:
                result_for_llm = json.dumps(result, default=str)[:1000]
            
            prompt = f"User asked: {query}\nTool used: {tool}\nResult:\n{result_for_llm}"
            summary = await chat.send_message(UserMessage(text=prompt))
            return summary
            
        except Exception:
            return f"Action '{tool}' completed."
    
    async def suggest_actions(self) -> Dict[str, Any]:
        """
        Analyze current data and suggest actions.
        """
        suggestions = []
        
        # Check low stock
        low_stock = await self.tools.get_low_stock_products(threshold=5)
        if low_stock.get("critical", {}).get("count", 0) > 0:
            products = low_stock["critical"]["products"]
            suggestions.append({
                "priority": "high",
                "type": "low_stock",
                "message": f"{len(products)} products critically low on stock",
                "products": [p["name"] for p in products[:3]],
                "suggested_action": f"Restock these products immediately"
            })
        
        # Check pending orders
        pending = await self.tools.get_orders(status="pending", days=3)
        if pending.get("count", 0) > 5:
            suggestions.append({
                "priority": "medium",
                "type": "pending_orders",
                "message": f"{pending['count']} orders pending for 3+ days",
                "suggested_action": "Review and process pending orders"
            })
        
        # Check revenue
        revenue = await self.tools.get_revenue_summary(days=7)
        if revenue.get("order_count", 0) == 0:
            suggestions.append({
                "priority": "medium",
                "type": "no_sales",
                "message": "No orders in the past 7 days",
                "suggested_action": "Consider running a promotion"
            })
        
        return {
            "success": True,
            "suggestion_count": len(suggestions),
            "suggestions": suggestions
        }


# ═══════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════

_admin_ai_instance: Optional[AdminActionAI] = None


def get_admin_action_ai(db) -> AdminActionAI:
    """Get or create AdminActionAI singleton."""
    global _admin_ai_instance
    if _admin_ai_instance is None:
        _admin_ai_instance = AdminActionAI(db)
    return _admin_ai_instance
