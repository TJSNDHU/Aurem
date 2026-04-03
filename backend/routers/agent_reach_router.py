"""
AUREM Agent-Reach Router
Zero-API Social Intelligence Endpoints

Provides social media search and web reading capabilities
without expensive API subscriptions.

Endpoints:
- POST /api/reach/twitter - Search Twitter/X
- POST /api/reach/reddit - Search Reddit
- POST /api/reach/youtube - Extract YouTube transcript
- POST /api/reach/web - Read any webpage
- GET /api/reach/tools - Get available tool status
- GET /api/reach/history/{business_id} - Get search history
- GET /api/reach/health - Health check
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/reach", tags=["AUREM Agent-Reach"])

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


# ==================== MODELS ====================

class TwitterSearchRequest(BaseModel):
    query: str = Field(..., description="Search query (e.g., 'PDRN skincare reviews')")
    limit: int = Field(20, ge=1, le=100, description="Max results")
    sentiment_filter: str = Field("all", description="Filter: all, positive, negative, questions")


class RedditSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    subreddit: Optional[str] = Field(None, description="Specific subreddit (optional)")
    sort: str = Field("relevance", description="Sort: relevance, hot, new, top")
    limit: int = Field(10, ge=1, le=50)


class YouTubeTranscriptRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL")
    language: str = Field("en", description="Preferred language code")


class WebReaderRequest(BaseModel):
    url: str = Field(..., description="URL of webpage to read")
    extract_images: bool = Field(False, description="Include image descriptions")


# ==================== ENDPOINTS ====================

@router.post("/twitter")
async def search_twitter(request: TwitterSearchRequest):
    """
    Search Twitter/X for real-time discussions.
    
    Uses bird CLI with browser cookies - appears as regular user.
    Zero API cost for brand monitoring and sentiment analysis.
    
    Example:
    - "PDRN skincare reviews" → Recent tweets about your product
    - "@competitorname" → Monitor competitor mentions
    """
    from services.aurem_commercial.agent_reach import get_reach_service
    
    service = get_reach_service(get_db())
    result = await service.search_twitter(
        query=request.query,
        limit=request.limit,
        sentiment_filter=request.sentiment_filter
    )
    
    return result.to_dict()


@router.post("/reddit")
async def search_reddit(request: RedditSearchRequest):
    """
    Search Reddit for in-depth discussions and reviews.
    
    Perfect for market research and customer sentiment.
    Uses Exa search with site:reddit.com filter.
    
    Example:
    - "best auto mechanic Toronto" → Find local recommendations
    - "skincare routine PDRN" → Detailed product discussions
    """
    from services.aurem_commercial.agent_reach import get_reach_service
    
    service = get_reach_service(get_db())
    result = await service.search_reddit(
        query=request.query,
        subreddit=request.subreddit,
        sort=request.sort,
        limit=request.limit
    )
    
    return result.to_dict()


@router.post("/youtube")
async def get_youtube_transcript(request: YouTubeTranscriptRequest):
    """
    Extract full transcript from YouTube video.
    
    Uses yt-dlp to download subtitles/auto-captions.
    Zero cost way to analyze competitor videos or update knowledge base.
    
    Example:
    - Competitor product demo → Extract and summarize
    - Tutorial videos → Import into AUREM knowledge base
    """
    from services.aurem_commercial.agent_reach import get_reach_service
    
    service = get_reach_service(get_db())
    result = await service.get_youtube_transcript(
        url=request.url,
        language=request.language
    )
    
    return result.to_dict()


@router.post("/web")
async def read_webpage(request: WebReaderRequest):
    """
    Convert any webpage to clean, AI-readable Markdown.
    
    Strips ads, navigation, and clutter using Jina Reader.
    Perfect for reading product pages or competitor websites.
    
    Example:
    - Competitor product page → Extract features and pricing
    - Industry article → Summarize for knowledge base
    """
    from services.aurem_commercial.agent_reach import get_reach_service
    
    service = get_reach_service(get_db())
    result = await service.read_webpage(
        url=request.url,
        extract_images=request.extract_images
    )
    
    return result.to_dict()


@router.get("/tools")
async def get_tool_status():
    """
    Get availability status of all Agent-Reach tools.
    
    Shows which tools are installed and ready to use.
    """
    from services.aurem_commercial.agent_reach import get_reach_service, REACH_TOOL_DEFINITIONS
    
    service = get_reach_service(get_db())
    available = service.get_available_tools()
    
    tools_info = []
    for tool_def in REACH_TOOL_DEFINITIONS:
        func = tool_def.get("function", {})
        name = func.get("name")
        
        # Map function names to tool keys
        tool_map = {
            "search_twitter": "twitter_search",
            "search_reddit": "reddit_search",
            "get_youtube_transcript": "youtube_transcript",
            "read_webpage": "web_reader"
        }
        
        is_available = available.get(tool_map.get(name, name), False)
        
        tools_info.append({
            "name": name,
            "description": func.get("description"),
            "available": is_available,
            "cost": "$0 per request",
            "parameters": func.get("parameters", {}).get("properties", {})
        })
    
    return {
        "tools": tools_info,
        "total": len(tools_info),
        "available_count": sum(1 for t in tools_info if t["available"]),
        "note": "Agent-Reach provides zero-API social intelligence"
    }


@router.get("/history/{business_id}")
async def get_search_history(
    business_id: str,
    tool: Optional[str] = Query(None, description="Filter by tool type"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get recent Agent-Reach search history.
    
    Useful for reviewing past searches and building analytics.
    """
    from services.aurem_commercial.agent_reach import get_reach_service
    
    service = get_reach_service(get_db())
    history = await service.get_search_history(business_id, tool, limit)
    
    return {
        "business_id": business_id,
        "history": history,
        "count": len(history)
    }


@router.get("/skill-definitions")
async def get_skill_definitions():
    """
    Get SKILL.md compatible tool definitions.
    
    Use this to register Agent-Reach tools with the Scout Agent.
    The Scout Agent reads SKILL.md to learn available commands.
    """
    from services.aurem_commercial.agent_reach import REACH_TOOL_DEFINITIONS
    
    # Generate SKILL.md format
    skill_md = """# AUREM Agent-Reach Skills

## Social Intelligence Tools (Zero API Cost)

### Twitter/X Search
Command: `search_twitter(query, limit=20, sentiment_filter="all")`
Description: Search Twitter for real-time discussions and sentiment.
Example: `search_twitter("PDRN skincare reviews")`

### Reddit Search
Command: `search_reddit(query, subreddit=None, sort="relevance", limit=10)`
Description: Search Reddit for in-depth discussions and reviews.
Example: `search_reddit("best mechanic Toronto", subreddit="askTO")`

### YouTube Transcript
Command: `get_youtube_transcript(url, language="en")`
Description: Extract full transcript from any YouTube video.
Example: `get_youtube_transcript("https://youtube.com/watch?v=xxx")`

### Web Reader
Command: `read_webpage(url, extract_images=False)`
Description: Convert any webpage to clean Markdown for AI reading.
Example: `read_webpage("https://competitor.com/product")`

## Usage Notes
- All tools cost $0 (no API keys required)
- Twitter search uses browser cookies for auth
- Results are cached for analytics
"""
    
    return {
        "skill_md": skill_md,
        "tool_definitions": REACH_TOOL_DEFINITIONS,
        "format": "openai_function_calling"
    }


@router.get("/health")
async def health():
    """
    Health check for Agent-Reach service.
    
    Shows tool availability and configuration status.
    """
    from services.aurem_commercial.agent_reach import get_reach_service
    import os
    
    service = get_reach_service(get_db())
    available = service.get_available_tools()
    
    return {
        "status": "healthy",
        "service": "aurem-agent-reach",
        "philosophy": "zero-api-social-intelligence",
        "tools": {
            "twitter_search": {
                "status": "available" if available.get("twitter_search") else "mock_mode",
                "requires": "bird CLI + browser cookies"
            },
            "reddit_search": {
                "status": "available",
                "requires": "Exa API (free tier) or mock"
            },
            "youtube_transcript": {
                "status": "available" if available.get("youtube_transcript") else "mock_mode",
                "requires": "yt-dlp"
            },
            "web_reader": {
                "status": "available",
                "requires": "Jina Reader API (free)"
            }
        },
        "configuration": {
            "exa_api_key": "configured" if os.environ.get("EXA_API_KEY") else "not_configured",
            "bird_cookies": "check ~/.bird/cookies.txt"
        },
        "cost_savings": "100% - all tools operate at $0/request"
    }
