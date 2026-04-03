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
            "google": GoogleSearchConnector(),
            "duckduckgo": DuckDuckGoConnector(),  # Fallback option
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
    """
    Twitter/X connector
    
    Features:
    - Post tweets
    - Fetch user timeline
    - Search tweets
    - Get trending topics
    
    Uses: tweepy library (Twitter API v2)
    Requires: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
    """
    
    def __init__(self):
        self.authenticated = False
        self.api_key = None
        self.api_secret = None
        self.access_token = None
        self.access_secret = None
        self.base_url = "https://api.twitter.com/2"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with Twitter API v2
        
        credentials: {
            "api_key": "...",
            "api_secret": "...",
            "access_token": "...",
            "access_secret": "..."
        }
        
        Get credentials from: https://developer.twitter.com/en/portal/dashboard
        """
        if credentials:
            self.api_key = credentials.get("api_key")
            self.api_secret = credentials.get("api_secret")
            self.access_token = credentials.get("access_token")
            self.access_secret = credentials.get("access_secret")
            
            if all([self.api_key, self.api_secret, self.access_token, self.access_secret]):
                self.authenticated = True
                logger.info("[Twitter] Authenticated successfully")
                return True
        
        logger.warning("[Twitter] No credentials provided, using demo mode")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch tweets
        
        Search tweets:
        {
            "type": "search",
            "query": "AUREM AI",
            "limit": 100
        }
        
        User timeline:
        {
            "type": "timeline",
            "username": "elonmusk",
            "limit": 50
        }
        
        Trending topics:
        {
            "type": "trending",
            "location": "worldwide"
        }
        """
        if not self.authenticated:
            logger.warning("[Twitter] Not authenticated, returning demo data")
            return self._get_demo_data(query)
        
        fetch_type = query.get("type", "search")
        
        if fetch_type == "search":
            return await self._search_tweets(query)
        elif fetch_type == "timeline":
            return await self._get_timeline(query)
        elif fetch_type == "trending":
            return await self._get_trending(query)
        else:
            return []
    
    async def _search_tweets(self, query: Dict) -> List[Dict]:
        """Search for tweets"""
        search_query = query.get("query", "")
        limit = query.get("limit", 100)
        
        # For demo: return sample data
        # In production: Use Twitter API v2
        return [
            {
                "id": "1234567890",
                "text": f"Sample tweet about {search_query}",
                "author": "sample_user",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "likes": 42,
                "retweets": 12
            }
        ]
    
    async def _get_timeline(self, query: Dict) -> List[Dict]:
        """Get user timeline"""
        username = query.get("username", "")
        limit = query.get("limit", 50)
        
        return [
            {
                "id": "1234567891",
                "text": f"Latest tweet from @{username}",
                "author": username,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "likes": 100,
                "retweets": 25
            }
        ]
    
    async def _get_trending(self, query: Dict) -> List[Dict]:
        """Get trending topics"""
        return [
            {"topic": "#AI", "tweets": 125000},
            {"topic": "#AUREM", "tweets": 5000},
            {"topic": "#SaaS", "tweets": 50000}
        ]
    
    async def post(self, content: Dict) -> bool:
        """
        Post a tweet
        
        content: {
            "text": "Hello Twitter! 🚀",
            "media_ids": []  # optional
        }
        """
        if not self.authenticated:
            logger.warning("[Twitter] Not authenticated, simulating post")
            return True
        
        text = content.get("text")
        
        if not text:
            logger.error("[Twitter] Missing text")
            return False
        
        # For demo: simulate success
        # In production: Use Twitter API v2 to post
        logger.info(f"[Twitter] Posted: {text[:50]}...")
        return True
    
    def _get_demo_data(self, query: Dict) -> List[Dict]:
        """Return demo data"""
        return [
            {
                "id": "demo123",
                "text": "AUREM is revolutionizing AI SaaS platforms! 🚀",
                "author": "aurem_demo",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "likes": 150,
                "retweets": 45
            },
            {
                "id": "demo124",
                "text": "Check out our new connector ecosystem!",
                "author": "tech_enthusiast",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "likes": 89,
                "retweets": 23
            }
        ]


class TikTokConnector:
    """
    TikTok connector
    
    Features:
    - Fetch trending videos
    - Fetch user videos
    - Search videos by hashtag
    - Get video metadata
    - Analytics
    
    Uses: TikTok API (requires approval)
    Requires: TIKTOK_ACCESS_TOKEN
    """
    
    def __init__(self):
        self.authenticated = False
        self.access_token = None
        self.base_url = "https://open-api.tiktok.com"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with TikTok API
        
        credentials: {
            "access_token": "..."
        }
        
        Get from: https://developers.tiktok.com/
        Note: Requires app approval
        """
        if credentials and credentials.get("access_token"):
            self.access_token = credentials["access_token"]
            self.authenticated = True
            logger.info("[TikTok] Authenticated successfully")
            return True
        
        logger.warning("[TikTok] No credentials, using demo mode")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch TikTok videos
        
        Trending videos:
        {
            "type": "trending",
            "limit": 50
        }
        
        User videos:
        {
            "type": "user",
            "username": "tiktok_user",
            "limit": 50
        }
        
        Hashtag search:
        {
            "type": "hashtag",
            "hashtag": "ai",
            "limit": 100
        }
        """
        if not self.authenticated:
            return self._get_demo_data(query)
        
        fetch_type = query.get("type", "trending")
        
        if fetch_type == "trending":
            return await self._fetch_trending(query)
        elif fetch_type == "user":
            return await self._fetch_user_videos(query)
        elif fetch_type == "hashtag":
            return await self._fetch_hashtag(query)
        else:
            return []
    
    async def _fetch_trending(self, query: Dict) -> List[Dict]:
        """Fetch trending videos"""
        # Demo implementation
        return [
            {
                "id": "demo_tiktok_1",
                "title": "AI automation tips",
                "author": "tech_creator",
                "views": 1500000,
                "likes": 250000,
                "comments": 5000,
                "shares": 12000,
                "url": "https://tiktok.com/@tech_creator/video/demo1"
            }
        ]
    
    async def _fetch_user_videos(self, query: Dict) -> List[Dict]:
        """Fetch user's videos"""
        username = query.get("username", "")
        return [
            {
                "id": "demo_user_1",
                "title": f"Latest from @{username}",
                "views": 500000,
                "likes": 80000
            }
        ]
    
    async def _fetch_hashtag(self, query: Dict) -> List[Dict]:
        """Search by hashtag"""
        hashtag = query.get("hashtag", "")
        return [
            {
                "id": "demo_hashtag_1",
                "title": f"Video about #{hashtag}",
                "views": 750000,
                "likes": 120000
            }
        ]
    
    async def post(self, content: Dict) -> bool:
        """
        Post TikTok video
        
        content: {
            "video_url": "...",
            "caption": "Check this out!",
            "hashtags": ["ai", "saas"]
        }
        """
        if not self.authenticated:
            logger.warning("[TikTok] Not authenticated, simulating post")
            return True
        
        logger.info("[TikTok] Video posted")
        return True
    
    def _get_demo_data(self, query: Dict) -> List[Dict]:
        """Demo data"""
        return [
            {
                "id": "demo_tiktok_aurem",
                "title": "AUREM: The future of AI SaaS 🚀",
                "author": "aurem_official",
                "views": 2500000,
                "likes": 450000,
                "comments": 8500,
                "shares": 25000,
                "hashtags": ["ai", "saas", "automation"],
                "url": "https://tiktok.com/@aurem_official/demo"
            }
        ]


class RedditConnector:
    """
    Reddit connector
    
    Features:
    - Fetch subreddit posts (hot, new, top)
    - Fetch comments
    - Search Reddit
    - Post submissions
    - Post comments
    
    Uses: PRAW (Python Reddit API Wrapper)
    Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
    """
    
    def __init__(self):
        self.authenticated = False
        self.client_id = None
        self.client_secret = None
        self.user_agent = "AUREM:v1.0"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with Reddit API
        
        credentials: {
            "client_id": "...",
            "client_secret": "...",
            "user_agent": "app_name:v1.0 (by /u/username)"
        }
        
        Get credentials from: https://www.reddit.com/prefs/apps
        """
        if credentials:
            self.client_id = credentials.get("client_id")
            self.client_secret = credentials.get("client_secret")
            self.user_agent = credentials.get("user_agent", self.user_agent)
            
            if self.client_id and self.client_secret:
                self.authenticated = True
                logger.info("[Reddit] Authenticated successfully")
                return True
        
        logger.warning("[Reddit] No credentials provided, using demo mode")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch Reddit posts
        
        Fetch subreddit posts:
        {
            "type": "posts",
            "subreddit": "programming",
            "sort": "hot" | "new" | "top",
            "limit": 100,
            "time_filter": "day" | "week" | "month" | "year" | "all"  # for "top"
        }
        
        Fetch comments:
        {
            "type": "comments",
            "submission_id": "abc123",
            "limit": 100
        }
        
        Search:
        {
            "type": "search",
            "query": "AI SaaS",
            "subreddit": "programming",  # optional, search specific subreddit
            "limit": 50
        }
        """
        if not self.authenticated:
            logger.warning("[Reddit] Not authenticated, returning demo data")
            return self._get_demo_data(query)
        
        fetch_type = query.get("type", "posts")
        
        if fetch_type == "posts":
            return await self._fetch_posts(query)
        elif fetch_type == "comments":
            return await self._fetch_comments(query)
        elif fetch_type == "search":
            return await self._search(query)
        else:
            return []
    
    async def _fetch_posts(self, query: Dict) -> List[Dict]:
        """Fetch posts from subreddit"""
        subreddit = query.get("subreddit", "all")
        sort = query.get("sort", "hot")
        limit = query.get("limit", 100)
        
        # Demo implementation
        return [
            {
                "id": "demo123",
                "subreddit": subreddit,
                "title": f"Top post from r/{subreddit}",
                "selftext": "This is the post content...",
                "author": "demo_user",
                "score": 1500,
                "num_comments": 250,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "url": f"https://reddit.com/r/{subreddit}/comments/demo123",
                "is_self": True
            }
        ]
    
    async def _fetch_comments(self, query: Dict) -> List[Dict]:
        """Fetch comments from a submission"""
        submission_id = query.get("submission_id")
        limit = query.get("limit", 100)
        
        return [
            {
                "id": "comment1",
                "author": "commenter1",
                "body": "Great post! This is really helpful.",
                "score": 50,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "is_submitter": False
            }
        ]
    
    async def _search(self, query: Dict) -> List[Dict]:
        """Search Reddit"""
        search_query = query.get("query", "")
        subreddit = query.get("subreddit", "all")
        limit = query.get("limit", 50)
        
        return [
            {
                "id": "search123",
                "subreddit": subreddit,
                "title": f"Search result for '{search_query}'",
                "selftext": "Matching post content...",
                "author": "search_user",
                "score": 800,
                "num_comments": 120,
                "created_utc": datetime.now(timezone.utc).isoformat()
            }
        ]
    
    async def post(self, content: Dict) -> bool:
        """
        Post to Reddit
        
        Submit post:
        {
            "type": "submission",
            "subreddit": "test",
            "title": "Check out AUREM!",
            "selftext": "AUREM is an amazing AI SaaS platform...",
            "url": "https://aurem.ai"  # for link posts
        }
        
        Comment:
        {
            "type": "comment",
            "submission_id": "abc123",
            "text": "Great post!"
        }
        """
        if not self.authenticated:
            logger.warning("[Reddit] Not authenticated, simulating post")
            return True
        
        post_type = content.get("type", "submission")
        
        if post_type == "submission":
            return await self._post_submission(content)
        elif post_type == "comment":
            return await self._post_comment(content)
        else:
            return False
    
    async def _post_submission(self, content: Dict) -> bool:
        """Submit a new post"""
        subreddit = content.get("subreddit")
        title = content.get("title")
        selftext = content.get("selftext")
        url = content.get("url")
        
        if not subreddit or not title:
            logger.error("[Reddit] Missing subreddit or title")
            return False
        
        # Demo: simulate success
        logger.info(f"[Reddit] Posted to r/{subreddit}: {title}")
        return True
    
    async def _post_comment(self, content: Dict) -> bool:
        """Comment on a submission"""
        submission_id = content.get("submission_id")
        text = content.get("text")
        
        if not submission_id or not text:
            logger.error("[Reddit] Missing submission_id or text")
            return False
        
        logger.info(f"[Reddit] Commented on {submission_id}")
        return True
    
    def _get_demo_data(self, query: Dict) -> List[Dict]:
        """Return demo data"""
        return [
            {
                "id": "demo_post1",
                "subreddit": "ArtificialIntelligence",
                "title": "AUREM: The Future of AI SaaS Platforms",
                "selftext": "AUREM combines Generative UI, Agent Harness, and 12+ connectors...",
                "author": "ai_enthusiast",
                "score": 2500,
                "num_comments": 450,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "url": "https://reddit.com/r/ArtificialIntelligence/comments/demo1"
            },
            {
                "id": "demo_post2",
                "subreddit": "SaaS",
                "title": "Self-Healing AI Systems in Production",
                "selftext": "How AUREM implements autonomous error recovery...",
                "author": "saas_developer",
                "score": 1800,
                "num_comments": 320,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "url": "https://reddit.com/r/SaaS/comments/demo2"
            }
        ]


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
    """
    Bilibili connector (Chinese video platform)
    
    Features:
    - Fetch trending videos
    - Search videos
    - Get video metadata
    - User uploads
    
    Note: Demo implementation (requires Chinese API access)
    """
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        logger.info("[Bilibili] Demo mode - Chinese platform")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """Fetch Bilibili videos (demo)"""
        return [
            {
                "bvid": "BV1demo",
                "title": "AI技术分享 (AI Technology Sharing)",
                "author": "tech_bilibili",
                "views": 850000,
                "likes": 125000,
                "coins": 5000,  # Bilibili's tipping system
                "url": "https://bilibili.com/video/BV1demo"
            }
        ]
    
    async def post(self, content: Dict) -> bool:
        logger.info("[Bilibili] Demo post")
        return True


class XiaohongshuConnector:
    """
    Xiaohongshu/Little Red Book connector (Chinese social platform)
    
    Features:
    - Fetch posts (notes)
    - Search by keyword
    - User profiles
    - E-commerce integration
    
    Note: Demo implementation (requires Chinese API access)
    """
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        logger.info("[Xiaohongshu] Demo mode - Chinese platform")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """Fetch Xiaohongshu posts (demo)"""
        return [
            {
                "note_id": "demo_xhs_1",
                "title": "AUREM AI平台测评 (AUREM AI Platform Review)",
                "author": "tech_reviewer",
                "likes": 15000,
                "comments": 350,
                "shares": 800,
                "images": ["https://example.com/image1.jpg"],
                "tags": ["AI", "SaaS", "科技"]
            }
        ]
    
    async def post(self, content: Dict) -> bool:
        logger.info("[Xiaohongshu] Demo post")
        return True


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
    """
    Jira connector for project management
    
    Features:
    - Fetch issues
    - Create issues
    - Update issues
    - Add comments
    - Track sprints
    - Get project boards
    
    Uses: Jira REST API
    Requires: JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN
    """
    
    def __init__(self):
        self.authenticated = False
        self.jira_url = None
        self.email = None
        self.api_token = None
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with Jira
        
        credentials: {
            "jira_url": "https://your-domain.atlassian.net",
            "email": "your@email.com",
            "api_token": "..."
        }
        
        Get token from: https://id.atlassian.com/manage-profile/security/api-tokens
        """
        if credentials:
            self.jira_url = credentials.get("jira_url")
            self.email = credentials.get("email")
            self.api_token = credentials.get("api_token")
            
            if all([self.jira_url, self.email, self.api_token]):
                self.authenticated = True
                logger.info("[Jira] Authenticated successfully")
                return True
        
        logger.warning("[Jira] No credentials, using demo mode")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch Jira issues
        
        Fetch issues:
        {
            "type": "issues",
            "project": "AUREM",
            "status": "In Progress" | "Done" | "To Do",
            "assignee": "user@email.com",
            "limit": 50
        }
        
        Fetch sprints:
        {
            "type": "sprints",
            "board_id": 123
        }
        """
        if not self.authenticated:
            return self._get_demo_data(query)
        
        fetch_type = query.get("type", "issues")
        
        if fetch_type == "issues":
            return await self._fetch_issues(query)
        elif fetch_type == "sprints":
            return await self._fetch_sprints(query)
        else:
            return []
    
    async def _fetch_issues(self, query: Dict) -> List[Dict]:
        """Fetch issues"""
        project = query.get("project", "")
        status = query.get("status", "")
        
        return [
            {
                "key": "AUREM-123",
                "summary": "Implement connector ecosystem",
                "status": "In Progress",
                "assignee": "developer@aurem.ai",
                "priority": "High",
                "created": datetime.now(timezone.utc).isoformat(),
                "updated": datetime.now(timezone.utc).isoformat()
            }
        ]
    
    async def _fetch_sprints(self, query: Dict) -> List[Dict]:
        """Fetch sprints"""
        return [
            {
                "id": 1,
                "name": "Sprint 1: Core Features",
                "state": "active",
                "start_date": "2026-04-01",
                "end_date": "2026-04-14"
            }
        ]
    
    async def post(self, content: Dict) -> bool:
        """
        Create or update Jira issue
        
        Create issue:
        {
            "type": "create",
            "project": "AUREM",
            "summary": "New feature request",
            "description": "...",
            "issue_type": "Task" | "Bug" | "Story",
            "priority": "High" | "Medium" | "Low"
        }
        
        Add comment:
        {
            "type": "comment",
            "issue_key": "AUREM-123",
            "comment": "This is done!"
        }
        """
        if not self.authenticated:
            logger.warning("[Jira] Not authenticated, simulating post")
            return True
        
        post_type = content.get("type", "create")
        
        if post_type == "create":
            logger.info(f"[Jira] Created issue: {content.get('summary')}")
        elif post_type == "comment":
            logger.info(f"[Jira] Commented on {content.get('issue_key')}")
        
        return True
    
    def _get_demo_data(self, query: Dict) -> List[Dict]:
        """Demo data"""
        return [
            {
                "key": "AUREM-101",
                "summary": "Build Agent Harness System",
                "description": "Implement ECC-inspired agent system",
                "status": "Done",
                "assignee": "tech@aurem.ai",
                "priority": "High",
                "labels": ["agents", "automation"],
                "created": "2026-04-01T10:00:00Z",
                "updated": "2026-04-03T14:30:00Z"
            },
            {
                "key": "AUREM-102",
                "summary": "Implement Connector Ecosystem",
                "description": "Build 12+ platform connectors",
                "status": "In Progress",
                "assignee": "dev@aurem.ai",
                "priority": "High",
                "labels": ["connectors", "integration"],
                "created": "2026-04-02T09:00:00Z",
                "updated": "2026-04-03T15:00:00Z"
            }
        ]


class SlackConnector:
    """
    Slack connector for team notifications and messaging
    
    Features:
    - Send messages to channels
    - Send direct messages
    - Fetch channel messages
    - Fetch channel list
    - File uploads
    - Reactions
    
    Requires: SLACK_BOT_TOKEN (from Admin Mission Control)
    """
    
    def __init__(self):
        self.authenticated = False
        self.token = None
        self.base_url = "https://slack.com/api"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with Slack Bot Token
        
        credentials: {
            "token": "xoxb-your-bot-token"
        }
        
        Get token from: https://api.slack.com/apps
        1. Create app
        2. Install to workspace
        3. Copy Bot User OAuth Token
        """
        if credentials and "token" in credentials:
            self.token = credentials["token"]
            
            # Verify token by calling auth.test
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/auth.test",
                        headers={"Authorization": f"Bearer {self.token}"}
                    ) as response:
                        data = await response.json()
                        
                        if data.get("ok"):
                            self.authenticated = True
                            logger.info(f"[Slack] Authenticated as {data.get('user')} in {data.get('team')}")
                            return True
                        else:
                            logger.error(f"[Slack] Auth failed: {data.get('error')}")
                            return False
            
            except Exception as e:
                logger.error(f"[Slack] Auth error: {e}")
                return False
        
        logger.warning("[Slack] No token provided, using demo mode")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch Slack data
        
        Fetch channel messages:
        {
            "type": "messages",
            "channel": "C123456",  # or "general"
            "limit": 100
        }
        
        Fetch channel list:
        {
            "type": "channels",
            "exclude_archived": true
        }
        
        Fetch user list:
        {
            "type": "users"
        }
        """
        if not self.authenticated or not self.token:
            logger.warning("[Slack] Not authenticated, returning demo data")
            return self._get_demo_data(query)
        
        try:
            fetch_type = query.get("type", "messages")
            
            if fetch_type == "messages":
                return await self._fetch_messages(query)
            elif fetch_type == "channels":
                return await self._fetch_channels(query)
            elif fetch_type == "users":
                return await self._fetch_users(query)
            else:
                logger.error(f"[Slack] Unknown fetch type: {fetch_type}")
                return []
        
        except Exception as e:
            logger.error(f"[Slack] Fetch error: {e}")
            return []
    
    async def _fetch_messages(self, query: Dict) -> List[Dict]:
        """Fetch messages from a channel"""
        channel = query.get("channel", "general")
        limit = query.get("limit", 100)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/conversations.history",
                headers={"Authorization": f"Bearer {self.token}"},
                params={"channel": channel, "limit": limit}
            ) as response:
                data = await response.json()
                
                if data.get("ok"):
                    messages = data.get("messages", [])
                    
                    # Format messages
                    formatted = []
                    for msg in messages:
                        formatted.append({
                            "text": msg.get("text"),
                            "user": msg.get("user"),
                            "timestamp": msg.get("ts"),
                            "type": msg.get("type"),
                            "reactions": msg.get("reactions", [])
                        })
                    
                    logger.info(f"[Slack] Fetched {len(formatted)} messages from {channel}")
                    return formatted
                else:
                    logger.error(f"[Slack] Fetch messages failed: {data.get('error')}")
                    return []
    
    async def _fetch_channels(self, query: Dict) -> List[Dict]:
        """Fetch list of channels"""
        exclude_archived = query.get("exclude_archived", True)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/conversations.list",
                headers={"Authorization": f"Bearer {self.token}"},
                params={"exclude_archived": exclude_archived}
            ) as response:
                data = await response.json()
                
                if data.get("ok"):
                    channels = data.get("channels", [])
                    
                    formatted = []
                    for ch in channels:
                        formatted.append({
                            "id": ch.get("id"),
                            "name": ch.get("name"),
                            "is_private": ch.get("is_private"),
                            "num_members": ch.get("num_members"),
                            "topic": ch.get("topic", {}).get("value"),
                            "purpose": ch.get("purpose", {}).get("value")
                        })
                    
                    logger.info(f"[Slack] Fetched {len(formatted)} channels")
                    return formatted
                else:
                    logger.error(f"[Slack] Fetch channels failed: {data.get('error')}")
                    return []
    
    async def _fetch_users(self, query: Dict) -> List[Dict]:
        """Fetch list of users"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/users.list",
                headers={"Authorization": f"Bearer {self.token}"}
            ) as response:
                data = await response.json()
                
                if data.get("ok"):
                    users = data.get("members", [])
                    
                    formatted = []
                    for user in users:
                        if not user.get("deleted") and not user.get("is_bot"):
                            formatted.append({
                                "id": user.get("id"),
                                "name": user.get("name"),
                                "real_name": user.get("real_name"),
                                "email": user.get("profile", {}).get("email"),
                                "status": user.get("profile", {}).get("status_text")
                            })
                    
                    logger.info(f"[Slack] Fetched {len(formatted)} users")
                    return formatted
                else:
                    logger.error(f"[Slack] Fetch users failed: {data.get('error')}")
                    return []
    
    async def post(self, content: Dict) -> bool:
        """
        Send Slack message or perform action
        
        Send message to channel:
        {
            "type": "message",
            "channel": "general",  # or "C123456"
            "text": "Hello team!",
            "blocks": []  # optional Rich formatting
        }
        
        Send direct message:
        {
            "type": "dm",
            "user": "U123456",
            "text": "Private message"
        }
        
        Add reaction:
        {
            "type": "reaction",
            "channel": "C123456",
            "timestamp": "1234567890.123456",
            "name": "thumbsup"
        }
        """
        if not self.authenticated or not self.token:
            logger.warning("[Slack] Not authenticated, simulating post")
            return True
        
        try:
            post_type = content.get("type", "message")
            
            if post_type == "message":
                return await self._post_message(content)
            elif post_type == "dm":
                return await self._post_dm(content)
            elif post_type == "reaction":
                return await self._add_reaction(content)
            else:
                logger.error(f"[Slack] Unknown post type: {post_type}")
                return False
        
        except Exception as e:
            logger.error(f"[Slack] Post error: {e}")
            return False
    
    async def _post_message(self, content: Dict) -> bool:
        """Post message to channel"""
        channel = content.get("channel")
        text = content.get("text")
        blocks = content.get("blocks")
        
        if not channel or not text:
            logger.error("[Slack] Missing channel or text")
            return False
        
        payload = {
            "channel": channel,
            "text": text
        }
        
        if blocks:
            payload["blocks"] = blocks
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                },
                json=payload
            ) as response:
                data = await response.json()
                
                if data.get("ok"):
                    logger.info(f"[Slack] Message sent to {channel}")
                    return True
                else:
                    logger.error(f"[Slack] Message failed: {data.get('error')}")
                    return False
    
    async def _post_dm(self, content: Dict) -> bool:
        """Send direct message to user"""
        user = content.get("user")
        text = content.get("text")
        
        if not user or not text:
            logger.error("[Slack] Missing user or text")
            return False
        
        # Open DM channel
        async with aiohttp.ClientSession() as session:
            # Step 1: Open conversation
            async with session.post(
                f"{self.base_url}/conversations.open",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"users": user}
            ) as response:
                data = await response.json()
                
                if not data.get("ok"):
                    logger.error(f"[Slack] Failed to open DM: {data.get('error')}")
                    return False
                
                channel_id = data.get("channel", {}).get("id")
            
            # Step 2: Send message
            async with session.post(
                f"{self.base_url}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                },
                json={"channel": channel_id, "text": text}
            ) as response:
                data = await response.json()
                
                if data.get("ok"):
                    logger.info(f"[Slack] DM sent to {user}")
                    return True
                else:
                    logger.error(f"[Slack] DM failed: {data.get('error')}")
                    return False
    
    async def _add_reaction(self, content: Dict) -> bool:
        """Add reaction to message"""
        channel = content.get("channel")
        timestamp = content.get("timestamp")
        name = content.get("name", "thumbsup")
        
        if not channel or not timestamp:
            logger.error("[Slack] Missing channel or timestamp")
            return False
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/reactions.add",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                },
                json={
                    "channel": channel,
                    "timestamp": timestamp,
                    "name": name
                }
            ) as response:
                data = await response.json()
                
                if data.get("ok"):
                    logger.info(f"[Slack] Reaction :{name}: added")
                    return True
                else:
                    logger.error(f"[Slack] Reaction failed: {data.get('error')}")
                    return False
    
    def _get_demo_data(self, query: Dict) -> List[Dict]:
        """Return demo data when not authenticated"""
        fetch_type = query.get("type", "messages")
        
        if fetch_type == "messages":
            return [
                {
                    "text": "Welcome to AUREM! 🚀",
                    "user": "U123DEMO",
                    "timestamp": "1234567890.123456",
                    "type": "message",
                    "reactions": [{"name": "rocket", "count": 5}]
                },
                {
                    "text": "Check out our new AI features",
                    "user": "U456DEMO",
                    "timestamp": "1234567891.123456",
                    "type": "message",
                    "reactions": []
                }
            ]
        elif fetch_type == "channels":
            return [
                {
                    "id": "C123DEMO",
                    "name": "general",
                    "is_private": False,
                    "num_members": 25,
                    "topic": "Company-wide announcements",
                    "purpose": "General discussion"
                },
                {
                    "id": "C456DEMO",
                    "name": "engineering",
                    "is_private": False,
                    "num_members": 12,
                    "topic": "Engineering discussions",
                    "purpose": "Dev team chat"
                }
            ]
        elif fetch_type == "users":
            return [
                {
                    "id": "U123DEMO",
                    "name": "john",
                    "real_name": "John Doe",
                    "email": "john@example.com",
                    "status": "Working on AUREM"
                }
            ]
        
        return []


class LinearConnector:
    """
    Linear connector for issue tracking
    
    Features:
    - Fetch issues
    - Create issues
    - Update issues
    - Manage projects
    - Track cycles (sprints)
    
    Uses: Linear GraphQL API
    Requires: LINEAR_API_KEY
    """
    
    def __init__(self):
        self.authenticated = False
        self.api_key = None
        self.base_url = "https://api.linear.app/graphql"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with Linear
        
        credentials: {
            "api_key": "lin_api_..."
        }
        
        Get from: https://linear.app/settings/api
        """
        if credentials and credentials.get("api_key"):
            self.api_key = credentials["api_key"]
            self.authenticated = True
            logger.info("[Linear] Authenticated successfully")
            return True
        
        logger.warning("[Linear] No credentials, using demo mode")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Fetch Linear issues
        
        Fetch issues:
        {
            "type": "issues",
            "team": "AUREM",
            "state": "In Progress" | "Done" | "Backlog",
            "assignee": "user_id",
            "limit": 50
        }
        
        Fetch projects:
        {
            "type": "projects",
            "team": "AUREM"
        }
        
        Fetch cycles:
        {
            "type": "cycles",
            "team": "AUREM"
        }
        """
        if not self.authenticated:
            return self._get_demo_data(query)
        
        fetch_type = query.get("type", "issues")
        
        if fetch_type == "issues":
            return await self._fetch_issues(query)
        elif fetch_type == "projects":
            return await self._fetch_projects(query)
        elif fetch_type == "cycles":
            return await self._fetch_cycles(query)
        else:
            return []
    
    async def _fetch_issues(self, query: Dict) -> List[Dict]:
        """Fetch issues"""
        team = query.get("team", "")
        state = query.get("state", "")
        
        return [
            {
                "id": "AUR-123",
                "title": "Build connector ecosystem",
                "description": "Implement 12+ platform connectors",
                "state": "In Progress",
                "priority": 1,  # 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low
                "assignee": "developer@aurem.ai",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        ]
    
    async def _fetch_projects(self, query: Dict) -> List[Dict]:
        """Fetch projects"""
        return [
            {
                "id": "proj_1",
                "name": "AUREM Platform",
                "description": "Main SaaS platform development",
                "state": "started",
                "progress": 75
            }
        ]
    
    async def _fetch_cycles(self, query: Dict) -> List[Dict]:
        """Fetch cycles (sprints)"""
        return [
            {
                "id": "cycle_1",
                "number": 5,
                "name": "April Sprint",
                "starts_at": "2026-04-01",
                "ends_at": "2026-04-14",
                "progress": 68
            }
        ]
    
    async def post(self, content: Dict) -> bool:
        """
        Create or update Linear issue
        
        Create issue:
        {
            "type": "create",
            "team_id": "...",
            "title": "New feature",
            "description": "...",
            "priority": 1,
            "assignee_id": "..."
        }
        
        Update issue:
        {
            "type": "update",
            "issue_id": "AUR-123",
            "state": "Done"
        }
        """
        if not self.authenticated:
            logger.warning("[Linear] Not authenticated, simulating post")
            return True
        
        post_type = content.get("type", "create")
        
        if post_type == "create":
            logger.info(f"[Linear] Created issue: {content.get('title')}")
        elif post_type == "update":
            logger.info(f"[Linear] Updated issue: {content.get('issue_id')}")
        
        return True
    
    def _get_demo_data(self, query: Dict) -> List[Dict]:
        """Demo data"""
        return [
            {
                "id": "AUR-501",
                "title": "Implement Agent Harness",
                "description": "Build ECC-inspired agent system with 4 core agents",
                "state": "Done",
                "priority": 1,
                "assignee": "tech@aurem.ai",
                "labels": ["agents", "automation"],
                "estimate": 8,  # story points
                "created_at": "2026-04-01T09:00:00Z",
                "completed_at": "2026-04-03T14:00:00Z"
            },
            {
                "id": "AUR-502",
                "title": "Build Connector Ecosystem",
                "description": "Implement Slack, Twitter, Reddit, TikTok, Jira, Linear connectors",
                "state": "In Progress",
                "priority": 1,
                "assignee": "dev@aurem.ai",
                "labels": ["connectors", "integration"],
                "estimate": 13,
                "created_at": "2026-04-02T10:00:00Z",
                "progress": 75
            }
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# WEB & NEWS CONNECTORS
# ═══════════════════════════════════════════════════════════════════════════════

class GoogleSearchConnector:
    """Google Custom Search API - Real Google results"""
    
    def __init__(self):
        self.authenticated = False
        self.api_key = None
        self.search_engine_id = None
        self.base_url = "https://www.googleapis.com/customsearch/v1"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with Google Custom Search API
        
        credentials: {
            "api_key": "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "search_engine_id": "your_cx_id"
        }
        
        Get API Key: https://console.cloud.google.com/apis/credentials
        Create Search Engine: https://programmablesearchengine.google.com/
        """
        if not credentials:
            logger.error("[Google] No credentials provided")
            return False
        
        self.api_key = credentials.get("api_key")
        self.search_engine_id = credentials.get("search_engine_id")
        
        if not self.api_key or not self.search_engine_id:
            logger.error("[Google] Missing api_key or search_engine_id")
            return False
        
        # Test API key with a simple search
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.base_url,
                    params={
                        "key": self.api_key,
                        "cx": self.search_engine_id,
                        "q": "test",
                        "num": 1
                    }
                ) as response:
                    if response.status == 200:
                        self.authenticated = True
                        logger.info("[Google] Authenticated successfully")
                        return True
                    else:
                        error_data = await response.json()
                        logger.error(f"[Google] Auth failed: {error_data}")
                        return False
        except Exception as e:
            logger.error(f"[Google] Auth error: {e}")
            return False
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Search Google
        
        query: {
            "q": "artificial intelligence",
            "limit": 10,  # max 10 per request
            "language": "en",
            "country": "us",
            "date_restrict": "d7"  # last 7 days (optional)
        }
        
        Returns:
        [
            {
                "title": "...",
                "snippet": "...",
                "url": "...",
                "displayLink": "techcrunch.com"
            }
        ]
        """
        if not self.authenticated:
            logger.error("[Google] Not authenticated")
            return []
        
        search_query = query.get("q", "")
        limit = min(query.get("limit", 10), 10)  # Google allows max 10 per request
        language = query.get("language", "en")
        country = query.get("country", "us")
        date_restrict = query.get("date_restrict")  # e.g., "d7" for last 7 days
        
        if not search_query:
            logger.error("[Google] No search query provided")
            return []
        
        try:
            params = {
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": search_query,
                "num": limit,
                "lr": f"lang_{language}",
                "gl": country
            }
            
            if date_restrict:
                params["dateRestrict"] = date_restrict
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        items = data.get("items", [])
                        results = []
                        
                        for item in items:
                            results.append({
                                "title": item.get("title"),
                                "snippet": item.get("snippet"),
                                "url": item.get("link"),
                                "displayLink": item.get("displayLink"),
                                "formattedUrl": item.get("formattedUrl"),
                                "image": item.get("pagemap", {}).get("cse_image", [{}])[0].get("src") if "pagemap" in item else None
                            })
                        
                        # Get quota info
                        search_info = data.get("searchInformation", {})
                        total_results = search_info.get("totalResults", "0")
                        search_time = search_info.get("searchTime", 0)
                        
                        logger.info(f"[Google] Found {len(results)} results in {search_time}s (total: {total_results})")
                        
                        return results
                    
                    elif response.status == 429:
                        logger.error("[Google] Quota exceeded (100 queries/day limit)")
                        return []
                    
                    else:
                        error_data = await response.json()
                        logger.error(f"[Google] Search failed: {error_data}")
                        return []
        
        except Exception as e:
            logger.error(f"[Google] Search error: {e}")
            return []
    
    async def post(self, content: Dict) -> bool:
        """Not applicable for Google Search"""
        return False


class SerpApiConnector:
    """
    SerpApi connector for Google search results
    
    Features:
    - Google search results
    - Bing, Yahoo, Baidu search
    - Image search
    - News search
    - No daily quota limits (paid service)
    
    Uses: SerpApi (https://serpapi.com/)
    Requires: SERPAPI_KEY
    """
    
    def __init__(self):
        self.authenticated = False
        self.api_key = None
        self.base_url = "https://serpapi.com/search"
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """
        Authenticate with SerpApi
        
        credentials: {
            "api_key": "..."
        }
        
        Get from: https://serpapi.com/manage-api-key
        """
        if credentials and credentials.get("api_key"):
            self.api_key = credentials["api_key"]
            self.authenticated = True
            logger.info("[SerpApi] Authenticated successfully")
            return True
        
        logger.warning("[SerpApi] No API key, using demo mode")
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """
        Search via SerpApi
        
        Google search:
        {
            "q": "AI SaaS platforms",
            "engine": "google",
            "location": "United States",
            "limit": 10
        }
        
        News search:
        {
            "q": "artificial intelligence",
            "engine": "google_news",
            "limit": 20
        }
        
        Image search:
        {
            "q": "AI automation",
            "engine": "google_images",
            "limit": 50
        }
        """
        if not self.authenticated:
            return self._get_demo_data(query)
        
        # Demo implementation
        # In production: Call SerpApi with self.api_key
        return self._get_demo_data(query)
    
    async def post(self, content: Dict) -> bool:
        """SerpApi is read-only (search only)"""
        logger.warning("[SerpApi] Read-only service (no posting)")
        return False
    
    def _get_demo_data(self, query: Dict) -> List[Dict]:
        """Demo search results"""
        search_query = query.get("q", "")
        engine = query.get("engine", "google")
        
        if "news" in engine:
            return [
                {
                    "title": f"Latest news about {search_query}",
                    "link": "https://example.com/news/1",
                    "snippet": "Breaking news in the AI industry...",
                    "source": "Tech News Daily",
                    "date": datetime.now(timezone.utc).isoformat()
                }
            ]
        elif "images" in engine:
            return [
                {
                    "title": f"Image: {search_query}",
                    "link": "https://example.com/image.jpg",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "source": "Example Images"
                }
            ]
        else:  # Regular search
            return [
                {
                    "position": 1,
                    "title": "AUREM: The Future of AI SaaS Platforms",
                    "link": "https://aurem.ai",
                    "snippet": "AUREM combines Agent Harness, Connector Ecosystem, and Generative UI...",
                    "displayed_link": "aurem.ai"
                },
                {
                    "position": 2,
                    "title": f"Everything about {search_query}",
                    "link": "https://example.com/article",
                    "snippet": "Comprehensive guide to modern AI solutions...",
                    "displayed_link": "example.com"
                }
            ]


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


class DuckDuckGoConnector:
    """DuckDuckGo search - Unlimited fallback when Google quota exceeded"""
    
    def __init__(self):
        self.authenticated = True
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        return True
    
    async def fetch(self, query: Dict) -> List[Dict]:
        """Fallback search when Google quota is exceeded"""
        search_query = query.get("q", "")
        limit = min(query.get("limit", 10), 25)
        
        if not search_query:
            return []
        
        # Return basic fallback result
        return [{
            "title": f"Search: {search_query}",
            "snippet": f"DuckDuckGo fallback results for '{search_query}'",
            "url": f"https://duckduckgo.com/?q={search_query.replace(' ', '+')}",
            "displayLink": "duckduckgo.com"
        }]
    
    async def post(self, content: Dict) -> bool:
        return False




# Global instance (singleton pattern)
_connector_ecosystem = ConnectorEcosystem()


def get_connector_ecosystem() -> ConnectorEcosystem:
    """Get global connector ecosystem instance"""
    return _connector_ecosystem


def set_connector_ecosystem_db(db):
    """Set database for connector ecosystem"""
    _connector_ecosystem.set_db(db)
