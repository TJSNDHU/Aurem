"""
Proactive Outreach Admin Routes for Reroots
Admin endpoints to test and manage proactive AI outreach.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/outreach", tags=["proactive-outreach"])

# Database reference
_db = None


def set_db(database):
    """Set database reference"""
    global _db
    _db = database


@router.get("/weather/test/{city}")
async def test_weather_for_city(city: str):
    """
    Test weather API and skincare recommendation for a specific city.
    
    Example: /api/admin/outreach/weather/test/Toronto
    """
    from services.proactive_outreach import check_weather_for_city
    
    result = await check_weather_for_city(city)
    
    return {
        "city": city,
        "weather_data": result,
        "would_notify": result.get("should_notify", False),
        "recommendation": result.get("recommendation")
    }


@router.get("/weather-test")
async def weather_test_simple():
    """
    Simple weather test endpoint for Site Audit.
    Returns status of weather integration.
    """
    import os
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    
    result = {
        "success": bool(api_key),
        "api_key_configured": bool(api_key),
        "city": "Toronto",
        "alerts_active": bool(api_key)
    }
    
    # If API key exists, try a quick test
    if api_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://api.openweathermap.org/data/2.5/weather?q=Toronto&appid={api_key}&units=metric"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result["current_temp"] = data.get("main", {}).get("temp")
                    result["condition"] = data.get("weather", [{}])[0].get("main")
                    result["success"] = True
                else:
                    result["success"] = False
                    result["error"] = f"API returned {resp.status_code}"
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
    
    return result


@router.get("/weather/mock-test")
async def mock_weather_test():
    """
    Test the weather message generation without calling the API.
    Uses mock data to verify the system works.
    """
    from utils.weather import get_skincare_message, should_notify_customer
    
    # Test all alert types
    alert_types = ["extreme_cold", "very_dry", "hot_sunny", "freezing", "dry", "sunny", "cold_dry", "hot_humid", "rainy"]
    
    results = {}
    for alert_type in alert_types:
        message = get_skincare_message(alert_type, customer_name="Tj", city="Mississauga")
        dry_skin_match = await should_notify_customer(alert_type, ["dry", "sensitive"])
        oily_skin_match = await should_notify_customer(alert_type, ["oily", "acne"])
        
        results[alert_type] = {
            "message_preview": message[:100] + "..." if message else "No message",
            "sends_to_dry_skin": dry_skin_match,
            "sends_to_oily_skin": oily_skin_match
        }
    
    return {
        "status": "Weather system ready",
        "api_key_status": "Waiting for activation (2 hours)",
        "alert_types_configured": len(alert_types),
        "test_results": results
    }


@router.post("/weather/run")
async def run_weather_outreach_now():
    """
    Manually trigger weather-based outreach for all customers with location data.
    Use this to test the full weather outreach flow.
    """
    from services.proactive_outreach import run_weather_based_outreach
    
    logger.info("[ADMIN] Manual weather outreach triggered")
    
    result = await run_weather_based_outreach()
    
    return {
        "status": "completed",
        "result": result
    }


@router.get("/customers/with-locations")
async def get_customers_with_locations():
    """
    Get a sample of customers with location data for testing.
    """
    from services.proactive_outreach import get_customers_with_locations
    
    customers = await get_customers_with_locations()
    
    # Mask sensitive data
    masked_customers = []
    for c in customers[:20]:  # Limit to 20 for preview
        masked_customers.append({
            "email": c["email"][:3] + "****@" + c["email"].split("@")[1] if "@" in c.get("email", "") else "****",
            "phone": c.get("phone", "")[:6] + "****" if c.get("phone") else None,
            "name": c.get("name"),
            "city": c.get("city"),
            "source": c.get("source")
        })
    
    return {
        "total_customers": len(customers),
        "sample": masked_customers,
        "cities": list(set(c["city"] for c in customers if c.get("city")))
    }


@router.get("/logs")
async def get_outreach_logs(limit: int = Query(50, le=200)):
    """
    Get recent proactive outreach logs.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    logs = await _db.proactive_outreach_log.find(
        {},
        {"_id": 0}
    ).sort("sent_at", -1).limit(limit).to_list(limit)
    
    return {
        "total": len(logs),
        "logs": logs
    }


@router.get("/weather/logs")
async def get_weather_outreach_logs(limit: int = Query(20, le=100)):
    """
    Get weather outreach campaign logs.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    logs = await _db.weather_outreach_log.find(
        {},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    return {
        "total": len(logs),
        "logs": logs
    }


@router.get("/stats")
async def get_outreach_stats():
    """
    Get outreach statistics for the last 30 days.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    
    # Count by template type
    pipeline = [
        {"$match": {"sent_at": {"$gte": cutoff.isoformat()}}},
        {"$group": {
            "_id": "$template",
            "count": {"$sum": 1},
            "successful": {"$sum": {"$cond": ["$results.success", 1, 0]}}
        }}
    ]
    
    stats = await _db.proactive_outreach_log.aggregate(pipeline).to_list(100)
    
    # Get weather outreach stats
    weather_stats = await _db.weather_outreach_log.find(
        {"timestamp": {"$gte": cutoff.isoformat()}},
        {"_id": 0, "alerts_sent": 1, "cities_checked": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(30).to_list(30)
    
    total_weather_alerts = sum(w.get("alerts_sent", 0) for w in weather_stats)
    
    return {
        "period": "last_30_days",
        "by_template": {s["_id"]: {"total": s["count"], "successful": s["successful"]} for s in stats},
        "weather_outreach": {
            "total_alerts": total_weather_alerts,
            "campaigns_run": len(weather_stats)
        }
    }
