"""
Connector Ecosystem Router
API endpoints for all external integrations
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from services.connector_ecosystem import get_connector_ecosystem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connectors", tags=["Connector Ecosystem"])


class ConnectRequest(BaseModel):
    """Connect to a platform"""
    platform: str
    credentials: Optional[Dict[str, str]] = None


class FetchRequest(BaseModel):
    """Fetch data from platform"""
    platform: str
    query: Dict[str, Any]


class PostRequest(BaseModel):
    """Post data to platform"""
    platform: str
    content: Dict[str, Any]


@router.get("/platforms")
async def list_platforms():
    """
    List all available connector platforms
    
    Returns:
    {
        "social": ["twitter", "tiktok", "reddit"],
        "video": ["youtube", "bilibili", "xiaohongshu"],
        "dev_tools": ["github", "jira", "slack", "linear"],
        "web": ["duckduckgo", "serpapi"],
        "news": ["news_aggregator"]
    }
    """
    return {
        "social": ["twitter", "tiktok", "reddit"],
        "video": ["youtube", "bilibili", "xiaohongshu"],
        "dev_tools": ["github", "jira", "slack", "linear"],
        "web": ["duckduckgo", "serpapi"],
        "news": ["news"],
        "total": 12
    }


@router.post("/connect")
async def connect_platform(request: ConnectRequest):
    """
    Connect to a platform
    
    Request:
    {
        "platform": "github",
        "credentials": {
            "token": "ghp_xxxxx"
        }
    }
    """
    ecosystem = get_connector_ecosystem()
    
    try:
        success = await ecosystem.connect(request.platform, request.credentials)
        
        if success:
            return {
                "success": True,
                "platform": request.platform,
                "status": "connected"
            }
        else:
            raise HTTPException(401, "Authentication failed")
            
    except Exception as e:
        logger.error(f"[Connector] Connect error: {e}")
        raise HTTPException(500, f"Connection failed: {str(e)}")


@router.post("/fetch")
async def fetch_data(request: FetchRequest):
    """
    Fetch data from a platform
    
    Examples:
    
    GitHub Issues:
    {
        "platform": "github",
        "query": {
            "repo": "facebook/react",
            "type": "issues",
            "state": "open",
            "limit": 10
        }
    }
    
    YouTube Search:
    {
        "platform": "youtube",
        "query": {
            "search": "AI tutorials",
            "limit": 5
        }
    }
    
    News:
    {
        "platform": "news",
        "query": {
            "topic": "artificial intelligence",
            "limit": 20
        }
    }
    """
    ecosystem = get_connector_ecosystem()
    
    try:
        data = await ecosystem.fetch_data(request.platform, request.query)
        
        return {
            "success": True,
            "platform": request.platform,
            "results": len(data),
            "data": data
        }
        
    except Exception as e:
        logger.error(f"[Connector] Fetch error: {e}")
        raise HTTPException(500, f"Fetch failed: {str(e)}")


@router.post("/post")
async def post_data(request: PostRequest):
    """
    Post data to a platform
    
    Examples:
    
    Twitter Post:
    {
        "platform": "twitter",
        "content": {
            "text": "Hello from AUREM AI! 🚀"
        }
    }
    
    GitHub Issue:
    {
        "platform": "github",
        "content": {
            "repo": "myorg/myrepo",
            "type": "issue",
            "title": "Bug: Login not working",
            "body": "Users cannot log in...",
            "labels": ["bug", "high-priority"]
        }
    }
    
    Slack Message:
    {
        "platform": "slack",
        "content": {
            "channel": "#general",
            "text": "Deployment successful! ✅"
        }
    }
    """
    ecosystem = get_connector_ecosystem()
    
    try:
        success = await ecosystem.post_data(request.platform, request.content)
        
        if success:
            return {
                "success": True,
                "platform": request.platform,
                "message": "Posted successfully"
            }
        else:
            raise HTTPException(500, "Post failed")
            
    except Exception as e:
        logger.error(f"[Connector] Post error: {e}")
        raise HTTPException(500, f"Post failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SPECIALIZED ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/social/trends")
async def get_social_trends(platform: str = "twitter"):
    """
    Get trending topics from social platforms
    
    Args:
        platform: twitter, tiktok, reddit
    """
    ecosystem = get_connector_ecosystem()
    
    trends = await ecosystem.fetch_data(platform, {
        "type": "trends",
        "limit": 10
    })
    
    return {
        "platform": platform,
        "trends": trends
    }


@router.get("/news/latest")
async def get_latest_news(topic: str = "technology", limit: int = 20):
    """
    Get latest news articles
    
    Args:
        topic: technology, business, ai, crypto, etc.
        limit: Number of articles
    """
    ecosystem = get_connector_ecosystem()
    
    news = await ecosystem.fetch_data("news", {
        "topic": topic,
        "limit": limit
    })
    
    return {
        "topic": topic,
        "articles": news
    }


@router.get("/web/search")
async def web_search(q: str, engine: str = "duckduckgo", limit: int = 10):
    """
    Perform web search
    
    Args:
        q: Search query
        engine: duckduckgo or serpapi
        limit: Number of results
    """
    ecosystem = get_connector_ecosystem()
    
    results = await ecosystem.fetch_data(engine, {
        "q": q,
        "limit": limit
    })
    
    return {
        "query": q,
        "engine": engine,
        "results": results
    }


@router.get("/github/issues")
async def get_github_issues(repo: str, state: str = "open", limit: int = 50):
    """
    Get GitHub issues for a repository
    
    Args:
        repo: owner/repo format (e.g., "facebook/react")
        state: open, closed, or all
        limit: Number of issues
    """
    ecosystem = get_connector_ecosystem()
    
    issues = await ecosystem.fetch_data("github", {
        "repo": repo,
        "type": "issues",
        "state": state,
        "limit": limit
    })
    
    return {
        "repo": repo,
        "state": state,
        "issues": issues
    }


@router.get("/youtube/subtitles")
async def extract_youtube_subtitles(video_url: str):
    """
    Extract subtitles from YouTube video
    
    Args:
        video_url: YouTube video URL
    """
    ecosystem = get_connector_ecosystem()
    
    data = await ecosystem.fetch_data("youtube", {
        "video_url": video_url,
        "extract_subtitles": True
    })
    
    return {
        "video_url": video_url,
        "subtitles": data
    }
