"""
ReRoots AI Churn Prediction Router
Predict customer churn and trigger retention campaigns
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import json

router = APIRouter(prefix="/api/churn", tags=["churn-prediction"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


class ChurnPredictionRequest(BaseModel):
    user_id: Optional[str] = None
    days_inactive: int = 30


@router.get("/at-risk")
async def get_at_risk_customers():
    """Get list of customers at risk of churning"""
    # Customers who haven't ordered in 60+ days but were active before
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=60)
    active_cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    
    # Get customers with orders in last 180 days but not in last 60 days
    at_risk = await db.orders.aggregate([
        {"$match": {"created_at": {"$gte": active_cutoff}}},
        {"$group": {
            "_id": "$user_id",
            "last_order": {"$max": "$created_at"},
            "total_orders": {"$sum": 1},
            "total_spent": {"$sum": "$total"},
            "email": {"$first": "$customer_email"}
        }},
        {"$match": {"last_order": {"$lt": cutoff_date}}},
        {"$sort": {"last_order": 1}},
        {"$limit": 50}
    ]).to_list(50)
    
    # Calculate churn risk score
    for customer in at_risk:
        days_since_order = (datetime.now(timezone.utc) - customer["last_order"]).days
        
        # Simple risk scoring
        if days_since_order > 90:
            risk_level = "high"
            risk_score = 0.8 + min((days_since_order - 90) / 100, 0.2)
        elif days_since_order > 60:
            risk_level = "medium"
            risk_score = 0.5 + (days_since_order - 60) / 60 * 0.3
        else:
            risk_level = "low"
            risk_score = days_since_order / 60 * 0.5
        
        customer["days_since_order"] = days_since_order
        customer["risk_level"] = risk_level
        customer["risk_score"] = round(risk_score, 2)
        customer["recommended_action"] = get_recommended_action(risk_level, customer["total_orders"])
        
        # Clean up for JSON serialization
        customer["last_order"] = customer["last_order"].isoformat()
    
    return {
        "at_risk_customers": at_risk,
        "total_at_risk": len(at_risk),
        "high_risk_count": sum(1 for c in at_risk if c["risk_level"] == "high")
    }


def get_recommended_action(risk_level: str, total_orders: int) -> str:
    """Get recommended retention action"""
    if risk_level == "high":
        if total_orders >= 5:
            return "Send VIP win-back email with 25% discount"
        else:
            return "Send personalized win-back email with 20% discount"
    elif risk_level == "medium":
        if total_orders >= 3:
            return "Send loyalty rewards reminder email"
        else:
            return "Send product recommendation email"
    else:
        return "Schedule engagement email in 2 weeks"


@router.post("/predict/{user_id}")
async def predict_churn(user_id: str):
    """Predict churn probability for a specific user"""
    try:
        # Get user's order history
        orders = await db.orders.find(
            {"user_id": user_id},
            {"_id": 0, "created_at": 1, "total": 1, "items": 1}
        ).sort("created_at", -1).to_list(50)
        
        if not orders:
            return {
                "user_id": user_id,
                "churn_probability": 0.9,
                "risk_level": "high",
                "reason": "No order history found"
            }
        
        # Calculate metrics
        last_order = orders[0]["created_at"]
        days_since_order = (datetime.now(timezone.utc) - last_order).days
        total_orders = len(orders)
        total_spent = sum(o.get("total", 0) for o in orders)
        avg_order_value = total_spent / total_orders if total_orders > 0 else 0
        
        # Calculate order frequency
        if total_orders > 1:
            first_order = orders[-1]["created_at"]
            days_active = (last_order - first_order).days
            avg_days_between_orders = days_active / (total_orders - 1) if total_orders > 1 else 90
        else:
            avg_days_between_orders = 90
        
        # AI-enhanced prediction
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if api_key:
            import secrets
            chat = LlmChat(
                api_key=api_key,
                session_id=f"churn_{secrets.token_hex(6)}",
                system_message="""You are a customer churn prediction AI.
Analyze customer data and predict churn probability.
Respond in JSON:
{
  "churn_probability": number (0-1),
  "risk_level": "low|medium|high|critical",
  "key_factors": ["factor1", "factor2"],
  "retention_suggestions": ["action1", "action2"],
  "predicted_next_order": "YYYY-MM-DD or null",
  "customer_segment": "loyal|occasional|new|churning"
}"""
            ).with_model("openai", "gpt-5-mini")
            
            response = await chat.send_message(UserMessage(
                text=f"""Predict churn for customer:
- Days since last order: {days_since_order}
- Total orders: {total_orders}
- Total spent: ${total_spent:.2f}
- Average order value: ${avg_order_value:.2f}
- Average days between orders: {avg_days_between_orders:.0f}"""
            ))
            
            try:
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                prediction = json.loads(response.strip())
                prediction["user_id"] = user_id
                prediction["metrics"] = {
                    "days_since_order": days_since_order,
                    "total_orders": total_orders,
                    "total_spent": total_spent,
                    "avg_order_value": avg_order_value
                }
                return prediction
            except:
                pass
        
        # Fallback prediction
        if days_since_order > 90:
            churn_prob = min(0.95, 0.5 + (days_since_order - 90) / 100)
            risk_level = "high" if churn_prob > 0.8 else "medium"
        elif days_since_order > 60:
            churn_prob = 0.3 + (days_since_order - 60) / 60 * 0.2
            risk_level = "medium"
        else:
            churn_prob = max(0.1, days_since_order / 60 * 0.3)
            risk_level = "low"
        
        return {
            "user_id": user_id,
            "churn_probability": round(churn_prob, 2),
            "risk_level": risk_level,
            "metrics": {
                "days_since_order": days_since_order,
                "total_orders": total_orders,
                "total_spent": total_spent,
                "avg_order_value": avg_order_value
            },
            "retention_suggestions": [
                get_recommended_action(risk_level, total_orders)
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/analytics")
async def get_churn_analytics():
    """Get overall churn analytics"""
    now = datetime.now(timezone.utc)
    
    # Active customers (ordered in last 30 days)
    active_30 = await db.orders.aggregate([
        {"$match": {"created_at": {"$gte": now - timedelta(days=30)}}},
        {"$group": {"_id": "$user_id"}}
    ]).to_list(10000)
    
    # Active in last 60 days
    active_60 = await db.orders.aggregate([
        {"$match": {"created_at": {"$gte": now - timedelta(days=60)}}},
        {"$group": {"_id": "$user_id"}}
    ]).to_list(10000)
    
    # Active in last 90 days
    active_90 = await db.orders.aggregate([
        {"$match": {"created_at": {"$gte": now - timedelta(days=90)}}},
        {"$group": {"_id": "$user_id"}}
    ]).to_list(10000)
    
    # Total unique customers
    total_customers = await db.orders.distinct("user_id")
    
    # Calculate churn rates
    active_30_count = len(active_30)
    active_60_count = len(active_60)
    active_90_count = len(active_90)
    total_count = len(total_customers)
    
    return {
        "total_customers": total_count,
        "active_30_days": active_30_count,
        "active_60_days": active_60_count,
        "active_90_days": active_90_count,
        "churn_rate_30_days": round((1 - active_30_count / max(total_count, 1)) * 100, 2),
        "churn_rate_60_days": round((1 - active_60_count / max(total_count, 1)) * 100, 2),
        "churn_rate_90_days": round((1 - active_90_count / max(total_count, 1)) * 100, 2),
        "retention_rate": round(active_30_count / max(total_count, 1) * 100, 2)
    }


@router.post("/retention-campaign")
async def trigger_retention_campaign(
    target: str = "at_risk",  # at_risk, inactive, all
    channel: str = "email",  # email, sms, whatsapp
    discount_percent: int = 15
):
    """Trigger a retention campaign for at-risk customers"""
    # Get target customers
    if target == "at_risk":
        result = await get_at_risk_customers()
        customers = result["at_risk_customers"]
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90 if target == "inactive" else 30)
        customers = await db.orders.aggregate([
            {"$group": {
                "_id": "$user_id",
                "email": {"$first": "$customer_email"},
                "last_order": {"$max": "$created_at"}
            }},
            {"$match": {"last_order": {"$lt": cutoff} if target == "inactive" else {}}}
        ]).to_list(100)
    
    # Log campaign
    campaign = {
        "campaign_type": "retention",
        "target": target,
        "channel": channel,
        "discount_percent": discount_percent,
        "total_recipients": len(customers),
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.retention_campaigns.insert_one(campaign)
    
    return {
        "campaign_created": True,
        "target_audience": target,
        "channel": channel,
        "recipients_count": len(customers),
        "discount": f"{discount_percent}%",
        "status": "Campaign scheduled for sending"
    }
