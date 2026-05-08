"""
AUREM Camofox Router — Anti-Detection Browser API
Exposes Camofox capabilities to the admin dashboard.
"""
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/camofox", tags=["Camofox"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db


def _verify_admin(request: Request):
    import jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT not configured")
    try:
        return jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


@router.get("/status")
async def camofox_status(request: Request):
    """Check Camofox service health."""
    _verify_admin(request)
    from services.camofox_client import is_camofox_available
    available = await is_camofox_available()
    return {"available": available, "service": "camofox"}


class BrowseRequest(BaseModel):
    url: str
    scroll: bool = False
    selector: Optional[str] = None


@router.post("/browse")
async def browse(data: BrowseRequest, request: Request):
    """Browse URL with anti-detection fallback."""
    _verify_admin(request)
    from services.camofox_client import browse_url
    result = await browse_url(data.url, scroll=data.scroll, selector=data.selector)
    return result


class LeadSearchRequest(BaseModel):
    query: str
    location: str


@router.post("/leads/google-maps")
async def google_maps_search(data: LeadSearchRequest, request: Request):
    """Extract leads from Google Maps."""
    _verify_admin(request)
    from services.camofox_client import google_maps_leads
    result = await google_maps_leads(data.query, data.location)
    # Store leads in DB
    if _db and result.get("leads"):
        for lead in result["leads"]:
            lead["source"] = "google_maps_camofox"
            lead["query"] = data.query
            lead["location"] = data.location
            lead["extracted_at"] = datetime.now(timezone.utc).isoformat()
        await _db.camofox_leads.insert_many(result["leads"])
    return result


class LinkedInRequest(BaseModel):
    url: str


@router.post("/leads/linkedin")
async def linkedin_scrape(data: LinkedInRequest, request: Request):
    """Scrape LinkedIn company page."""
    _verify_admin(request)
    from services.camofox_client import linkedin_company
    result = await linkedin_company(data.url)
    return result


class CompetitorMonitorRequest(BaseModel):
    urls: List[str]


@router.post("/monitor/competitors")
async def monitor_competitors(data: CompetitorMonitorRequest, request: Request):
    """Monitor competitor websites."""
    _verify_admin(request)
    from services.camofox_client import competitor_monitor
    results = await competitor_monitor(data.urls)
    # Store monitoring results
    if _db:
        await _db.competitor_snapshots.insert_one({
            "urls": data.urls,
            "results": results,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        })
    return {"results": results, "total": len(results)}
