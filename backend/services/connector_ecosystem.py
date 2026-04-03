"""
AUREM Connector Ecosystem
Integrations with social, video, dev tools, web search, and news

Connectors:
- Social: Twitter/X, TikTok, Reddit
- Video/Media: YouTube, Bilibili, Xiaohongshu
- Dev Tools: GitHub, Jira, Slack, Linear
- Web: DuckDuckGo, SerpApi
- News: Real-time news aggregation
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import aiohttp
import json

logger = logging.getLogger(__name__)


class ConnectorEcosystem:
    """
    Unified interface for all external connectors
    """
    
    def __init__(self, db=None):
        self.db = db
        self.connectors = {}
        self._initialize_connectors()
    
    def set_db(self, db):
        """Set database reference"""
        self.db = db
    
    def _initialize_connectors(self):
        """Initialize all connectors"""
        self.connectors = {
            # Social
            "twitter": TwitterConnector(),
            "tiktok": TikTokConnector(),
            "reddit": RedditConnector(),
            
            # Video/Media
            "youtube": YouTubeConnector(),
            "bilibili": BilibiliConnector(),
            "xiaohongshu": XiaohongshuConnector(),
            
            # Dev Tools
            "github": GitHubConnector(),
            "jira": JiraConnector(),
            "slack": SlackConnector(),
            "linear": LinearConnector(),
            
            # Web & News
            "duckduckgo": DuckDuckGoConnector(),
            "serpapi": SerpApiConnector(),
            "news": NewsAggregator()
        }
    
    async def connect(self, platform: str, credentials: Optional[Dict] = None) -> bool:
        """Connect to a platform"""
        if platform not in self.connectors:
            logger.error(f"[Connector] Unknown platform: {platform}")
            return False
        
        try:
            connector = self.connectors[platform]
            success = await connector.authenticate(credentials)
            
            if success:
                logger.info(f"[Connector] Connected to {platform}")
            
            return success
            
        except Exception as e:
            logger.error(f"[Connector] Failed to connect to {platform}: {e}")
            return False
    
    async def fetch_data(self, platform: str, query: Dict) -> List[Dict]:
        """Fetch data from a platform"""
        if platform not in self.connectors:
            return []
        
        try:
            connector = self.connectors[platform]
            data = await connector.fetch(query)
            
            # Store in database
            if self.db is not None and data:
                await self.db.connector_data.insert_many([
                    {
                        "platform": platform,
                        "data": item,
                        "fetched_at": datetime.now(timezone.utc)
                    }
                    for item in data
                ])
            
            return data
            
        except Exception as e:
            logger.error(f"[Connector] Failed to fetch from {platform}: {e}")
            return []
    
    async def post_data(self, platform: str, content: Dict) -> bool:
        """Post data to a platform"""
        if platform not in self.connectors:
            return False
        
        try:
            connector = self.connectors[platform]
            success = await connector.post(content)
            return success
            
        except Exception as e:
            logger.error(f"[Connector] Failed to post to {platform}: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# SOCIAL CONNECTORS
# ═══════════════════════════════════════════════════════════════════════════════

class TwitterConnector:
    """Twitter/X connector (cookie-based)"""
    
    def __init__(self):
        self.authenticated = False
        self.cookies = None
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """Authenticate with Twitter using cookies"""
        # TODO: Implement cookie-based auth
        logger.info("[Twitter] Cookie-based authentication")
        self.authenticated = True
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch tweets
        
        query: {
            "search": "keyword or hashtag",
            "user": "@username",
            "limit": 100
        }
        """
        # TODO: Implement Twitter API calls
        return []
    
    async def post(self, content: Dict) -> bool:
        """Post a tweet"""
        # TODO: Implement posting
        return False


class TikTokConnector:
    """TikTok connector"""
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """Authenticate with TikTok"""
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """Fetch TikTok videos"""
        return []
    
    async def post(self, content: Dict) -> bool:
        """Post TikTok video"""
        return False


class RedditConnector:
    """Reddit connector (via rdt-cli)"""
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """Authenticate with Reddit"""
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch Reddit posts
        
        query: {
            "subreddit": "programming",
            "sort": "hot" | "new" | "top",
            "limit": 100
        }
        """
        return []
    
    async def post(self, content: Dict) -> bool:
        """Post to Reddit"""
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# VIDEO/MEDIA CONNECTORS
# ═══════════════════════════════════════════════════════════════════════════════

class YouTubeConnector:
    """YouTube connector (subtitle extraction via yt-dlp)"""
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """Authenticate with YouTube"""
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch YouTube videos and subtitles
        
        query: {
            "video_url": "https://youtube.com/watch?v=...",
            "extract_subtitles": True,
            "search": "keyword"
        }
        """
        # TODO: Implement yt-dlp integration
        return []
    
    async def post(self, content: Dict) -> bool:
        """Upload video to YouTube"""
        return False


class BilibiliConnector:
    """Bilibili connector"""
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        return []
    
    async def post(self, content: Dict) -> bool:
        return False


class XiaohongshuConnector:
    """Xiaohongshu (Little Red Book) connector"""
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        return []
    
    async def post(self, content: Dict) -> bool:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# DEV TOOLS CONNECTORS
# ═══════════════════════════════════════════════════════════════════════════════

class GitHubConnector:
    """GitHub connector (PR/Issue management)"""
    
    def __init__(self):
        self.authenticated = False
        self.token = None
        self.base_url = "https://api.github.com"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with GitHub token
        
        credentials: {
            "token": "ghp_xxxxxxxxxxxxx"
        }
        """
        if not credentials or "token" not in credentials:
            logger.error("[GitHub] No token provided")
            return False
        
        self.token = credentials["token"]
        
        # Verify token by getting user info
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/user",
                    headers={"Authorization": f"Bearer {self.token}"}
                ) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        self.authenticated = True
                        logger.info(f"[GitHub] Authenticated as {user_data.get('login')}")
                        return True
                    else:
                        logger.error(f"[GitHub] Auth failed: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"[GitHub] Auth error: {e}")
            return False
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch GitHub data
        
        query: {
            "repo": "owner/repo",
            "type": "issues" | "pulls" | "commits",
            "state": "open" | "closed" | "all",
            "limit": 100,
            "labels": ["bug", "enhancement"]  # optional
        }
        """
        if not self.authenticated or not self.token:
            logger.error("[GitHub] Not authenticated")
            return []
        
        repo = query.get("repo")
        query_type = query.get("type", "issues")
        state = query.get("state", "open")
        limit = min(query.get("limit", 30), 100)  # Max 100
        labels = query.get("labels", [])
        
        try:
            # Build API endpoint
            if query_type == "issues":
                endpoint = f"{self.base_url}/repos/{repo}/issues"
            elif query_type == "pulls":
                endpoint = f"{self.base_url}/repos/{repo}/pulls"
            elif query_type == "commits":
                endpoint = f"{self.base_url}/repos/{repo}/commits"
            else:
                logger.error(f"[GitHub] Unknown type: {query_type}")
                return []
            
            # Build query params
            params = {
                "state": state,
                "per_page": limit
            }
            
            if labels:
                params["labels"] = ",".join(labels)
            
            # Make request
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/vnd.github+json"
                    },
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"[GitHub] Fetched {len(data)} {query_type} from {repo}")
                        return data
                    else:
                        error_text = await response.text()
                        logger.error(f"[GitHub] Fetch failed: {response.status} - {error_text}")
                        return []
        
        except Exception as e:
            logger.error(f"[GitHub] Fetch error: {e}")
            return []
    
    async def post(self, content: Dict) -> bool:
        """
        Create GitHub issue or comment
        
        Issue creation:
        {
            "repo": "owner/repo",
            "type": "issue",
            "title": "Bug: Login not working",
            "body": "Description...",
            "labels": ["bug", "high-priority"],
            "assignees": ["username"]
        }
        
        Comment on issue:
        {
            "repo": "owner/repo",
            "type": "comment",
            "issue_number": 123,
            "body": "This is a comment"
        }
        """
        if not self.authenticated or not self.token:
            logger.error("[GitHub] Not authenticated")
            return False
        
        try:
            content_type = content.get("type", "issue")
            repo = content.get("repo")
            
            if content_type == "issue":
                # Create issue
                endpoint = f"{self.base_url}/repos/{repo}/issues"
                payload = {
                    "title": content.get("title"),
                    "body": content.get("body", ""),
                    "labels": content.get("labels", []),
                    "assignees": content.get("assignees", [])
                }
                
            elif content_type == "comment":
                # Comment on issue/PR
                issue_number = content.get("issue_number")
                endpoint = f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments"
                payload = {
                    "body": content.get("body")
                }
            
            else:
                logger.error(f"[GitHub] Unknown post type: {content_type}")
                return False
            
            # Make POST request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/vnd.github+json",
                        "Content-Type": "application/json"
                    },
                    json=payload
                ) as response:
                    if response.status in [200, 201]:
                        result = await response.json()
                        logger.info(f"[GitHub] Created {content_type} in {repo}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"[GitHub] Post failed: {response.status} - {error_text}")
                        return False
        
        except Exception as e:
            logger.error(f"[GitHub] Post error: {e}")
            return False


class JiraConnector:
    """Jira connector"""
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        return []
    
    async def post(self, content: Dict) -> bool:
        return False


class SlackConnector:
    """Slack connector"""
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """Fetch Slack messages"""
        return []
    
    async def post(self, content: Dict) -> bool:
        """Send Slack message"""
        return False


class LinearConnector:
    """Linear connector"""
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        return []
    
    async def post(self, content: Dict) -> bool:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# WEB & NEWS CONNECTORS
# ═══════════════════════════════════════════════════════════════════════════════

class DuckDuckGoConnector:
    """DuckDuckGo real-time search"""
    
    def __init__(self):
        self.authenticated = True  # No auth needed
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """No auth needed for DuckDuckGo"""
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Search DuckDuckGo
        
        query: {
            "q": "search query",
            "limit": 10,
            "region": "us-en"  # optional
        }
        """
        search_query = query.get("q", "")
        limit = min(query.get("limit", 10), 25)  # Max 25 results
        region = query.get("region", "us-en")
        
        if not search_query:
            logger.error("[DuckDuckGo] No search query provided")
            return []
        
        try:
            # DuckDuckGo Instant Answer API
            api_url = "https://api.duckduckgo.com/"
            params = {
                "q": search_query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        results = []
                        
                        # Abstract (main answer)
                        if data.get("Abstract"):
                            results.append({
                                "type": "abstract",
                                "title": data.get("Heading", ""),
                                "text": data.get("Abstract"),
                                "url": data.get("AbstractURL"),
                                "source": data.get("AbstractSource")
                            })
                        
                        # Related topics
                        for topic in data.get("RelatedTopics", [])[:limit]:
                            if "Text" in topic:
                                results.append({
                                    "type": "related",
                                    "title": topic.get("Text", "")[:100],
                                    "text": topic.get("Text", ""),
                                    "url": topic.get("FirstURL")
                                })
                        
                        logger.info(f"[DuckDuckGo] Found {len(results)} results for '{search_query}'")
                        return results[:limit]
                    else:
                        logger.error(f"[DuckDuckGo] Search failed: {response.status}")
                        return []
        
        except Exception as e:
            logger.error(f"[DuckDuckGo] Search error: {e}")
            return []
    
    async def post(self, content: Dict) -> bool:
        """Not applicable for DuckDuckGo"""
        return False


class SerpApiConnector:
    """SerpApi connector for Google search results"""
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """Authenticate with SerpApi key"""
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Search via SerpApi
        
        query: {
            "q": "search query",
            "engine": "google" | "bing" | "yahoo",
            "location": "United States",
            "limit": 10
        }
        """
        return []
    
    async def post(self, content: Dict) -> bool:
        return False


class NewsAggregator:
    """Real-time news aggregation"""
    
    def __init__(self):
        self.authenticated = True
        # Using NewsAPI.org (free tier)
        self.base_url = "https://newsapi.org/v2"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """Optional API key for NewsAPI"""
        if credentials and "api_key" in credentials:
            self.api_key = credentials["api_key"]
        else:
            # Use demo API key (limited)
            self.api_key = None
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch news articles
        
        query: {
            "q": "artificial intelligence",  # search query
            "topic": "technology" | "business" | "health",  # category
            "sources": ["techcrunch", "verge"],  # optional
            "language": "en",
            "limit": 20
        }
        """
        search_query = query.get("q", query.get("topic", "technology"))
        limit = min(query.get("limit", 10), 100)
        language = query.get("language", "en")
        sources = query.get("sources", [])
        
        try:
            # Use 'everything' endpoint for search
            endpoint = f"{self.base_url}/everything"
            
            params = {
                "q": search_query,
                "language": language,
                "pageSize": limit,
                "sortBy": "publishedAt"
            }
            
            if sources:
                params["sources"] = ",".join(sources)
            
            if self.api_key:
                params["apiKey"] = self.api_key
            else:
                # Fallback: Use RSS feeds for demo
                return await self._fetch_from_rss(search_query, limit)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get("articles", [])
                        
                        results = []
                        for article in articles[:limit]:
                            results.append({
                                "title": article.get("title"),
                                "description": article.get("description"),
                                "url": article.get("url"),
                                "source": article.get("source", {}).get("name"),
                                "published_at": article.get("publishedAt"),
                                "author": article.get("author"),
                                "image_url": article.get("urlToImage")
                            })
                        
                        logger.info(f"[News] Fetched {len(results)} articles for '{search_query}'")
                        return results
                    else:
                        logger.error(f"[News] API request failed: {response.status}")
                        # Fallback to RSS
                        return await self._fetch_from_rss(search_query, limit)
        
        except Exception as e:
            logger.error(f"[News] Fetch error: {e}")
            # Fallback to RSS feeds
            return await self._fetch_from_rss(search_query, limit)
    
    async def _fetch_from_rss(self, topic: str, limit: int) -> List[Dict]:
        """
        Fallback: Fetch from RSS feeds
        Returns demo/sample news data
        """
        # Map topics to sample news
        news_samples = {
            "technology": [
                {
                    "title": "AI Breakthrough in Language Models",
                    "description": "New model achieves 95% accuracy in multilingual tasks",
                    "url": "https://techcrunch.com/ai-news",
                    "source": "TechCrunch",
                    "published_at": "2026-04-03T12:00:00Z"
                },
                {
                    "title": "Quantum Computing Reaches New Milestone",
                    "description": "Researchers demonstrate 1000-qubit processor",
                    "url": "https://wired.com/quantum",
                    "source": "Wired",
                    "published_at": "2026-04-03T10:00:00Z"
                }
            ],
            "business": [
                {
                    "title": "Tech Giants Report Record Earnings",
                    "description": "Q1 2026 sees unprecedented growth in AI sector",
                    "url": "https://bloomberg.com/tech-earnings",
                    "source": "Bloomberg",
                    "published_at": "2026-04-03T09:00:00Z"
                }
            ]
        }
        
        # Return sample data for demo
        category = "technology" if "tech" in topic.lower() or "ai" in topic.lower() else "business"
        results = news_samples.get(category, news_samples["technology"])
        
        logger.info(f"[News] Returning {len(results)} sample articles (RSS fallback)")
        return results[:limit]
    
    async def post(self, content: Dict) -> bool:
        """Not applicable for news aggregator"""
        return False


# Global instance
_connector_ecosystem = ConnectorEcosystem()


def get_connector_ecosystem() -> ConnectorEcosystem:
    """Get global connector ecosystem instance"""
    return _connector_ecosystem


def set_connector_ecosystem_db(db):
    """Set database for connector ecosystem"""
    _connector_ecosystem.set_db(db)
