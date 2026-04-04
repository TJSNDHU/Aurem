"""
Super-Admin Analytics Router
Anonymized intelligence dashboard for AUREM growth (The Luxe Way)

PRIVACY GUARANTEE:
- NO customer PII exposed
- Only aggregate trends and patterns
- Data sovereignty protected
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/analytics", tags=["Super Admin Analytics"])

# MongoDB connection
db = None

def set_db(database):
    global db
    db = database


@router.get("/insights")
async def get_insights_dashboard(
    date_range_days: int = 30,
    x_admin_key: Optional[str] = Header(None)
):
    """
    Get AUREM intelligence dashboard (anonymized)
    
    Query params:
        date_range_days: Days to look back (default: 30)
    
    Returns:
        {
            "total_leads": int,
            "by_industry": {...},
            "by_geography": {...},
            "trending_topics": [...],
            "growth_rate": float
        }
    
    NOTE: NO customer PII - aggregate data only
    """
    import os
    admin_key = os.getenv("ADMIN_KEY", "aurem_admin_2024_secure")
    
    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(403, "Invalid admin key")
    
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        from services.analytics_aggregator import get_analytics_aggregator
        
        aggregator = get_analytics_aggregator(db)
        insights = await aggregator.get_insights_dashboard(date_range_days)
        
        return {
            "success": True,
            "insights": insights,
            "privacy_note": "This data is anonymized. No customer PII is stored or shared."
        }
    
    except Exception as e:
        logger.error(f"[SuperAdminAnalytics] Error: {e}")
        raise HTTPException(500, str(e))


@router.get("/industry/{industry}")
async def get_industry_insights(
    industry: str,
    x_admin_key: Optional[str] = Header(None)
):
    """
    Get deep insights for specific industry
    
    Returns anonymized trends for industry vertical
    """
    import os
    admin_key = os.getenv("ADMIN_KEY", "aurem_admin_2024_secure")
    
    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(403, "Invalid admin key")
    
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        from services.analytics_aggregator import get_analytics_aggregator
        
        aggregator = get_analytics_aggregator(db)
        insights = await aggregator.get_industry_insights(industry)
        
        return {
            "success": True,
            "industry_insights": insights
        }
    
    except Exception as e:
        logger.error(f"[SuperAdminAnalytics] Error: {e}")
        raise HTTPException(500, str(e))
