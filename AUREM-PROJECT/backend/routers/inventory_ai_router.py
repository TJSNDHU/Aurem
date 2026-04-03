"""
ReRoots AI Inventory Prediction Router
Predictive inventory management using AI
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import json

router = APIRouter(prefix="/api/inventory-ai", tags=["inventory-ai"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


class InventoryPredictionRequest(BaseModel):
    product_id: Optional[str] = None
    days_ahead: int = 30
    include_seasonality: bool = True


@router.get("/status")
async def get_inventory_status():
    """Get current inventory status overview"""
    # Low stock products
    low_stock = await db.products.find(
        {"stock": {"$lt": 10}, "active": True},
        {"_id": 0, "id": 1, "name": 1, "stock": 1}
    ).to_list(20)
    
    # Out of stock
    out_of_stock = await db.products.find(
        {"stock": {"$lte": 0}, "active": True},
        {"_id": 0, "id": 1, "name": 1}
    ).to_list(20)
    
    # Total products
    total_products = await db.products.count_documents({"active": True})
    total_stock = await db.products.aggregate([
        {"$match": {"active": True}},
        {"$group": {"_id": None, "total": {"$sum": "$stock"}}}
    ]).to_list(1)
    
    return {
        "total_products": total_products,
        "total_stock": total_stock[0]["total"] if total_stock else 0,
        "low_stock_count": len(low_stock),
        "out_of_stock_count": len(out_of_stock),
        "low_stock_products": low_stock,
        "out_of_stock_products": out_of_stock
    }


@router.post("/predict")
async def predict_inventory(data: InventoryPredictionRequest):
    """Predict inventory needs using AI"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            # Fallback to simple prediction
            return await simple_inventory_prediction(data)
        
        # Get historical sales data
        since = datetime.now(timezone.utc) - timedelta(days=90)
        
        if data.product_id:
            # Single product prediction
            sales = await db.orders.aggregate([
                {"$match": {"created_at": {"$gte": since}, "status": "completed"}},
                {"$unwind": "$items"},
                {"$match": {"items.product_id": data.product_id}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "quantity": {"$sum": "$items.quantity"}
                }},
                {"$sort": {"_id": 1}}
            ]).to_list(100)
            
            product = await db.products.find_one(
                {"id": data.product_id},
                {"_id": 0, "name": 1, "stock": 1, "price": 1}
            )
            
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            
            # AI prediction
            import secrets
            chat = LlmChat(
                api_key=api_key,
                session_id=f"inventory_{secrets.token_hex(6)}",
                system_message="""You are an AI inventory analyst for a skincare brand.
Analyze sales data and predict future inventory needs.
Consider seasonality, trends, and patterns.
Respond in JSON format:
{
  "predicted_daily_sales": number,
  "predicted_total_demand": number,
  "reorder_recommendation": "order X units by date",
  "stockout_risk": "low|medium|high",
  "stockout_date": "YYYY-MM-DD or null",
  "confidence": number,
  "factors": ["factor1", "factor2"]
}"""
            ).with_model("openai", "gpt-5-mini")
            
            response = await chat.send_message(UserMessage(
                text=f"""Predict inventory for {product['name']}:
Current stock: {product['stock']} units
Price: ${product.get('price', 0)}
Prediction period: {data.days_ahead} days
Historical daily sales: {json.dumps(sales[-30:])}
Consider seasonality: {data.include_seasonality}"""
            ))
            
            try:
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                prediction = json.loads(response.strip())
            except:
                prediction = {
                    "predicted_daily_sales": 2,
                    "predicted_total_demand": data.days_ahead * 2,
                    "stockout_risk": "medium",
                    "confidence": 0.6
                }
            
            return {
                "product_id": data.product_id,
                "product_name": product["name"],
                "current_stock": product["stock"],
                "prediction_days": data.days_ahead,
                "prediction": prediction
            }
        
        else:
            # All products prediction
            return await get_all_products_prediction(data.days_ahead)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


async def simple_inventory_prediction(data: InventoryPredictionRequest) -> Dict:
    """Simple rule-based inventory prediction fallback"""
    products = await db.products.find(
        {"active": True},
        {"_id": 0, "id": 1, "name": 1, "stock": 1}
    ).to_list(100)
    
    predictions = []
    for product in products:
        avg_daily_sales = 2  # Default estimate
        days_until_stockout = product["stock"] / avg_daily_sales if avg_daily_sales > 0 else 999
        
        predictions.append({
            "product_id": product["id"],
            "product_name": product["name"],
            "current_stock": product["stock"],
            "estimated_daily_sales": avg_daily_sales,
            "days_until_stockout": round(days_until_stockout),
            "reorder_needed": days_until_stockout < data.days_ahead,
            "stockout_risk": "high" if days_until_stockout < 7 else "medium" if days_until_stockout < 14 else "low"
        })
    
    # Sort by stockout risk
    predictions.sort(key=lambda x: x["days_until_stockout"])
    
    return {
        "prediction_days": data.days_ahead,
        "total_products": len(predictions),
        "high_risk_count": sum(1 for p in predictions if p["stockout_risk"] == "high"),
        "predictions": predictions[:20]
    }


async def get_all_products_prediction(days_ahead: int) -> Dict:
    """Get predictions for all products"""
    return await simple_inventory_prediction(InventoryPredictionRequest(days_ahead=days_ahead))


@router.get("/reorder-list")
async def get_reorder_list():
    """Get list of products that need reordering"""
    # Products with stock < reorder point (default 10)
    products = await db.products.find(
        {"stock": {"$lt": 10}, "active": True},
        {"_id": 0, "id": 1, "name": 1, "stock": 1, "price": 1}
    ).sort("stock", 1).to_list(50)
    
    reorder_list = []
    for product in products:
        suggested_order = max(20, 50 - product["stock"])  # Order up to 50 units
        
        reorder_list.append({
            "product_id": product["id"],
            "product_name": product["name"],
            "current_stock": product["stock"],
            "suggested_order_quantity": suggested_order,
            "estimated_cost": suggested_order * (product.get("price", 0) * 0.4),  # 40% cost estimate
            "urgency": "critical" if product["stock"] <= 0 else "high" if product["stock"] < 5 else "medium"
        })
    
    return {
        "reorder_list": reorder_list,
        "total_items": len(reorder_list),
        "critical_count": sum(1 for p in reorder_list if p["urgency"] == "critical")
    }


@router.post("/optimize")
async def optimize_inventory():
    """Get AI-powered inventory optimization suggestions"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"suggestions": ["Enable AI integration for optimization suggestions"]}
        
        # Get inventory data
        products = await db.products.find(
            {"active": True},
            {"_id": 0, "name": 1, "stock": 1, "price": 1, "category": 1}
        ).to_list(50)
        
        import secrets
        chat = LlmChat(
            api_key=api_key,
            session_id=f"optimize_{secrets.token_hex(6)}",
            system_message="""You are an inventory optimization AI for a skincare brand.
Analyze inventory data and provide actionable optimization suggestions.
Focus on: reducing overstock, preventing stockouts, optimizing cash flow, seasonal preparation.
Respond in JSON:
{
  "overall_health_score": number,
  "suggestions": [{"priority": "high|medium|low", "action": "string", "impact": "string"}],
  "overstock_products": ["product names"],
  "understock_products": ["product names"],
  "cash_optimization": "advice"
}"""
        ).with_model("openai", "gpt-5-mini")
        
        response = await chat.send_message(UserMessage(
            text=f"Optimize this inventory:\n{json.dumps(products[:30])}"
        ))
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            return json.loads(response.strip())
        except:
            return {"suggestions": [{"priority": "medium", "action": "Review low stock items", "impact": "Prevent stockouts"}]}
            
    except Exception as e:
        return {"error": str(e), "suggestions": []}
