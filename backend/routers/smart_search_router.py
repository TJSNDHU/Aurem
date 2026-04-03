"""
Smart Search Router
Intelligent search with Google → DuckDuckGo fallback
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from services.smart_search import get_smart_search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["Smart Search"])


class SearchRequest(BaseModel):
    """Search request"""
    q: str
    limit: int = 10
    engine: Optional[str] = None  # Manual override
    language: Optional[str] = "en"
    country: Optional[str] = "us"
    date_restrict: Optional[str] = None  # e.g., "d7" for last 7 days


@router.get("/")
async def smart_search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=10, description="Number of results"),
    engine: Optional[str] = Query(None, description="Force specific engine (google/duckduckgo)"),
    language: str = Query("en", description="Language code"),
    country: str = Query("us", description="Country code")
):
    """
    Smart search with automatic fallback
    
    **Strategy:**
    1. Uses Google first (best quality, 100 free/day)
    2. Auto-switches to DuckDuckGo when quota exceeded
    3. Resets daily at midnight UTC
    
    **Examples:**
    - `/api/search/?q=artificial+intelligence&limit=10`
    - `/api/search/?q=GPT-5&engine=google` (force Google)
    - `/api/search/?q=news&engine=duckduckgo` (force DuckDuckGo)
    
    **Response:**
    ```json
    {
      "query": "AI",
      "engine_used": "google",
      "quota_remaining": 42,
      "results": [...],
      "fallback_used": false
    }
    ```
    """
    search_service = get_smart_search()
    
    try:
        result = await search_service.search(
            query=q,
            limit=limit,
            engine=engine,
            language=language,
            country=country
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[Smart Search] Error: {e}")
        raise HTTPException(500, f"Search failed: {str(e)}")


@router.post("/")
async def smart_search_post(request: SearchRequest):
    """
    Smart search (POST version)
    
    Supports all advanced parameters
    """
    search_service = get_smart_search()
    
    try:
        result = await search_service.search(
            query=request.q,
            limit=request.limit,
            engine=request.engine,
            language=request.language,
            country=request.country,
            date_restrict=request.date_restrict
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[Smart Search] Error: {e}")
        raise HTTPException(500, f"Search failed: {str(e)}")


@router.get("/quota")
async def get_quota_status():
    """
    Get search quota status
    
    **Returns:**
    ```json
    {
      "google_used": 42,
      "google_remaining": 53,
      "google_limit": 95,
      "current_engine": "google",
      "duckduckgo_available": true,
      "resets_at": "2026-04-04T00:00:00Z",
      "fallback_active": false
    }
    ```
    """
    search_service = get_smart_search()
    
    try:
        status = await search_service.get_quota_status()
        return status
        
    except Exception as e:
        logger.error(f"[Smart Search] Quota check error: {e}")
        raise HTTPException(500, f"Failed to get quota: {str(e)}")


@router.post("/switch")
async def switch_engine(engine: str = Query(..., description="google or duckduckgo")):
    """
    Manually switch search engine
    
    **Use cases:**
    - Force DuckDuckGo for privacy
    - Force Google for better results
    - Override automatic selection
    
    **Example:**
    ```bash
    POST /api/search/switch?engine=duckduckgo
    ```
    """
    search_service = get_smart_search()
    
    try:
        success = await search_service.switch_engine(engine)
        
        if success:
            return {
                "success": True,
                "engine": engine,
                "message": f"Switched to {engine}"
            }
        else:
            raise HTTPException(400, f"Invalid engine: {engine}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Smart Search] Switch error: {e}")
        raise HTTPException(500, f"Failed to switch: {str(e)}")


@router.get("/history")
async def get_search_history(limit: int = Query(50, ge=1, le=100)):
    """
    Get recent search history
    
    Shows which engine was used, fallback status, etc.
    """
    search_service = get_smart_search()
    
    if search_service.db is None:
        raise HTTPException(500, "Database not available")
    
    try:
        history = await search_service.db.search_history.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return {
            "history": history,
            "total": len(history)
        }
        
    except Exception as e:
        logger.error(f"[Smart Search] History error: {e}")
        raise HTTPException(500, f"Failed to get history: {str(e)}")
