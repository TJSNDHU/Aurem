"""
AUREM Intelligence API Router
==============================
Unified endpoints for predictive intelligence, lead scoring, and revenue forecasting.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import jwt
import os
import logging

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])
logger = logging.getLogger(__name__)

_db = None

def set_db(database):
    global _db
    _db = database
    from services.intelligence_engine import set_db as set_intel_db
    set_intel_db(database)


def _get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth.split(" ", 1)[1]
    secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


class DealPredictRequest(BaseModel):
    deal_id: Optional[str] = None
    title: Optional[str] = None
    value: Optional[float] = 0
    stage: Optional[str] = None
    company: Optional[str] = None
    days_in_pipeline: Optional[int] = 30


class LeadScoreRequest(BaseModel):
    lead_id: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    source: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None


@router.get("/pipeline/predictions")
async def get_pipeline_predictions(request: Request):
    """Get win probability predictions for all open deals"""
    _get_user(request)
    if _db is None:
        raise HTTPException(500, "Database not initialized")

    from services.intelligence_engine import predict_deal

    deals = await _db.deals.find(
        {"status": {"$nin": ["won", "lost"]}},
        {"_id": 0, "title": 1, "value": 1, "stage": 1, "company": 1, "status": 1, "created_at": 1}
    ).limit(20).to_list(20)

    predictions = []
    for deal in deals:
        days = 30
        if deal.get("created_at"):
            created = deal["created_at"]
            # Handle both naive and aware datetimes
            if hasattr(created, "timestamp"):
                if created.tzinfo is None:
                    # Naive datetime - assume UTC
                    created = created.replace(tzinfo=timezone.utc)
                days = (datetime.now(timezone.utc) - created).days
        deal["days_in_pipeline"] = days
        pred = await predict_deal(deal)
        predictions.append({
            **deal,
            "prediction": pred,
            "created_at": deal["created_at"].isoformat() if hasattr(deal.get("created_at", ""), "isoformat") else str(deal.get("created_at", "")),
        })

    # Sort by win probability descending
    predictions.sort(key=lambda x: x["prediction"].get("win_probability", 0), reverse=True)

    total_pipeline = sum(d.get("value", 0) for d in predictions)
    weighted = sum(d.get("value", 0) * d["prediction"].get("win_probability", 0) for d in predictions)

    return {
        "predictions": predictions,
        "summary": {
            "total_deals": len(predictions),
            "total_pipeline_value": total_pipeline,
            "weighted_pipeline_value": round(weighted, 2),
            "avg_win_probability": round(sum(d["prediction"].get("win_probability", 0) for d in predictions) / max(len(predictions), 1), 2),
            "deals_at_risk": sum(1 for d in predictions if d["prediction"].get("deal_health") == "at_risk"),
            "deals_cold": sum(1 for d in predictions if d["prediction"].get("deal_health") == "cold"),
        }
    }


@router.post("/deal/predict")
async def predict_single_deal(request: Request, body: DealPredictRequest):
    """Predict win probability for a single deal"""
    _get_user(request)
    from services.intelligence_engine import predict_deal
    result = await predict_deal(body.dict())
    return {"success": True, "prediction": result}


@router.post("/lead/score")
async def score_single_lead(request: Request, body: LeadScoreRequest):
    """Score a single lead"""
    _get_user(request)
    from services.intelligence_engine import score_lead
    result = await score_lead(body.dict())
    return {"success": True, "scoring": result}


@router.get("/leads/scores")
async def get_all_lead_scores(request: Request):
    """Score all leads in the CRM"""
    _get_user(request)
    if _db is None:
        raise HTTPException(500, "Database not initialized")

    from services.intelligence_engine import score_lead

    leads = await _db.contacts.find(
        {}, {"_id": 0, "name": 1, "email": 1, "company": 1, "website": 1, "source": 1, "industry": 1, "phone": 1, "status": 1}
    ).limit(30).to_list(30)

    scored = []
    for lead in leads:
        result = await score_lead(lead)
        scored.append({**lead, "scoring": result})

    scored.sort(key=lambda x: x["scoring"].get("score", 0), reverse=True)

    return {
        "leads": scored,
        "summary": {
            "total": len(scored),
            "grade_a": sum(1 for l in scored if l["scoring"].get("grade") == "A"),
            "grade_b": sum(1 for l in scored if l["scoring"].get("grade") == "B"),
            "grade_c": sum(1 for l in scored if l["scoring"].get("grade") == "C"),
            "avg_score": round(sum(l["scoring"].get("score", 0) for l in scored) / max(len(scored), 1), 1),
        }
    }


@router.get("/revenue/forecast")
async def get_revenue_forecast(request: Request, months: int = 6):
    """Forecast revenue for next N months"""
    _get_user(request)
    from services.intelligence_engine import forecast_revenue
    result = await forecast_revenue(months)
    return {"success": True, **result}


@router.get("/dashboard")
async def get_intelligence_dashboard(request: Request):
    """Unified intelligence dashboard data"""
    _get_user(request)
    if _db is None:
        raise HTTPException(500, "Database not initialized")

    from services.intelligence_engine import forecast_revenue

    # Quick stats
    contacts = await _db.contacts.count_documents({})
    deals = await _db.deals.count_documents({})
    open_deals = await _db.deals.count_documents({"status": {"$nin": ["won", "lost"]}})
    won_deals = await _db.deals.count_documents({"status": "won"})

    # Pipeline value
    pipeline = await _db.deals.find(
        {"status": {"$nin": ["won", "lost"]}}, {"_id": 0, "value": 1}
    ).to_list(500)
    pipeline_value = sum(d.get("value", 0) for d in pipeline)

    # Revenue forecast (3 months quick)
    forecast = await forecast_revenue(3)

    return {
        "stats": {
            "total_contacts": contacts,
            "total_deals": deals,
            "open_deals": open_deals,
            "won_deals": won_deals,
            "pipeline_value": pipeline_value,
            "win_rate": round(won_deals / max(deals, 1) * 100, 1),
        },
        "forecast_summary": {
            "methodology": forecast.get("methodology", "unknown"),
            "next_3_months": forecast.get("forecast", [])[:3],
            "weighted_pipeline": forecast.get("weighted_pipeline", 0),
        },
        "ai_powered": True,
    }
