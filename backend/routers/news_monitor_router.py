"""
News Monitor Router — Scheduled News Intelligence
====================================================
Endpoints for news monitoring and manual trigger.
Scheduler runs every 2 hours via startup_init.
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/news", tags=["News Monitor"])
logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    import jwt
    try:
        return jwt.decode(auth.split(" ", 1)[1], os.environ.get("JWT_SECRET", ""), algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


@router.post("/fetch")
async def manual_fetch(request: Request):
    """Manually trigger a news fetch cycle."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")

    from services.news_monitor import fetch_news
    result = await fetch_news(db)
    return result


@router.get("/alerts")
async def get_alerts(request: Request, limit: int = 20):
    """Get recent news alerts."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")

    from services.news_monitor import get_recent_alerts
    alerts = await get_recent_alerts(db, limit)
    return {"alerts": alerts, "total": len(alerts)}


@router.get("/leads")
async def get_news_leads(request: Request, limit: int = 20):
    """Get news articles that matched lead criteria."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(503, "DB not available")

    from services.news_monitor import get_lead_matches
    leads = await get_lead_matches(db, limit)
    return {"leads": leads, "total": len(leads)}


@router.get("/topics")
async def get_monitor_topics():
    """Get configured monitoring topics."""
    from services.news_monitor import MONITOR_TOPICS
    return {"topics": MONITOR_TOPICS}
