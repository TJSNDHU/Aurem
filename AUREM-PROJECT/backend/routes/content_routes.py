"""
Content Routes for Reroots
API endpoints for AI content generation
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from services.content_ai import (
    CONTENT_TYPES,
    generate_content,
    save_content,
    get_content_history,
    search_content,
    set_db as set_content_db
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/content", tags=["content"])

# Database reference
_db = None


def set_db(database):
    """Set database reference"""
    global _db
    _db = database
    set_content_db(database)


class GenerateContentRequest(BaseModel):
    content_type: str
    inputs: Dict[str, str]


class SaveContentRequest(BaseModel):
    content_type: str
    inputs: Dict[str, str]
    output: str


async def get_current_user(request: Request):
    """Get current user from request"""
    from server import get_current_user as server_get_user
    return await server_get_user(request)


@router.get("/types")
async def get_content_types():
    """Get all available content types"""
    return {
        "success": True,
        "types": CONTENT_TYPES
    }


@router.post("/generate")
async def generate_content_endpoint(request: Request, body: GenerateContentRequest):
    """Generate AI content"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if body.content_type not in CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid content type: {body.content_type}")
    
    result = await generate_content(body.content_type, body.inputs)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate content"))
    
    return result


@router.post("/save")
async def save_content_endpoint(request: Request, body: SaveContentRequest):
    """Save approved content to library"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if body.content_type not in CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid content type: {body.content_type}")
    
    result = await save_content(
        body.content_type,
        body.inputs,
        body.output,
        user.get("email", "admin")
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to save content"))
    
    return result


@router.get("/history")
async def get_history(
    request: Request,
    limit: int = 50,
    content_type: Optional[str] = None
):
    """Get content generation history"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    history = await get_content_history(limit=limit, content_type=content_type)
    
    return {
        "success": True,
        "history": history,
        "count": len(history)
    }


@router.get("/search")
async def search_content_endpoint(
    request: Request,
    q: str,
    content_type: Optional[str] = None,
    limit: int = 20
):
    """Search saved content"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    results = await search_content(q, content_type=content_type, limit=limit)
    
    return {
        "success": True,
        "results": results,
        "count": len(results)
    }


@router.get("/stats")
async def get_content_stats(request: Request):
    """Get content generation statistics"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get counts by type
    history = await get_content_history(limit=1000)
    
    stats = {}
    for item in history:
        ct = item.get("content_type", "unknown")
        stats[ct] = stats.get(ct, 0) + 1
    
    return {
        "success": True,
        "total": len(history),
        "by_type": stats,
        "types_available": list(CONTENT_TYPES.keys())
    }
