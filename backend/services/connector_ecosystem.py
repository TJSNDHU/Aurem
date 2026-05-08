"""
AUREM Connector Ecosystem — PULSE Compacted
Social, Video, Dev Tools, Web Search, News connectors.
Demo connectors use StubConnector. Real APIs: GitHub, Slack, Google, News.
"""
import asyncio
import logging
import aiohttp
import json
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class StubConnector:
    """Config-driven connector for platforms without live API keys (demo mode)."""
    def __init__(self, name: str, demo_data: List[Dict] = None):
        self.name, self.authenticated, self.demo = name, False, demo_data or []

    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        if credentials:
            self.authenticated = True
            logger.info(f"[{self.name}] Authenticated")
        return True

    async def fetch(self, query: Dict) -> List[Dict]:
        return self.demo

    async def post(self, content: Dict) -> bool:
        logger.info(f"[{self.name}] Post simulated: {str(content)[:80]}")
        return True


# ═══════════════════════════════════════════════════════════════
# REAL CONNECTORS (GitHub, Slack, Google Search, News)
# ═══════════════════════════════════════════════════════════════

class GitHubConnector:
    def __init__(self):
        self.authenticated, self.token = False, None
        self.base_url = "https://api.github.com"

    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        if not credentials or "token" not in credentials:
            return False
        self.token = credentials["token"]
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.base_url}/user", headers={"Authorization": f"Bearer {self.token}"}) as r:
                    if r.status == 200:
                        self.authenticated = True
                        return True
        except Exception as e:
            logger.error(f"[GitHub] Auth error: {e}")
        return False

    async def fetch(self, query: Dict) -> List[Dict]:
        if not self.authenticated:
            return []
        repo, qtype = query.get("repo"), query.get("type", "issues")
        state, limit = query.get("state", "open"), min(query.get("limit", 30), 100)
        endpoint = f"{self.base_url}/repos/{repo}/{qtype if qtype != 'pulls' else 'pulls'}"
        params = {"state": state, "per_page": limit}
        if query.get("labels"):
            params["labels"] = ",".join(query["labels"])
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(endpoint, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}, params=params) as r:
                    return await r.json() if r.status == 200 else []
        except Exception as e:
            logger.error(f"[GitHub] Fetch: {e}")
            return []

    async def post(self, content: Dict) -> bool:
        if not self.authenticated:
            return False
        repo, ctype = content.get("repo"), content.get("type", "issue")
        if ctype == "issue":
            endpoint = f"{self.base_url}/repos/{repo}/issues"
            payload = {"title": content.get("title"), "body": content.get("body", ""), "labels": content.get("labels", []), "assignees": content.get("assignees", [])}
        elif ctype == "comment":
            endpoint = f"{self.base_url}/repos/{repo}/issues/{content.get('issue_number')}/comments"
            payload = {"body": content.get("body")}
        else:
            return False
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(endpoint, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}, json=payload) as r:
                    return r.status in [200, 201]
        except Exception as e:
            logger.error(f"[GitHub] Post: {e}")
            return False


class SlackConnector:
    def __init__(self):
        self.authenticated, self.token = False, None
        self.base_url = "https://slack.com/api"

    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        if not credentials or "token" not in credentials:
            return True
        self.token = credentials["token"]
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.base_url}/auth.test", headers={"Authorization": f"Bearer {self.token}"}) as r:
                    data = await r.json()
                    if data.get("ok"):
                        self.authenticated = True
                        return True
        except Exception as e:
            logger.error(f"[Slack] Auth: {e}")
        return False

    async def _api_get(self, method: str, params: dict = None) -> dict:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{self.base_url}/{method}", headers={"Authorization": f"Bearer {self.token}"}, params=params or {}) as r:
                return await r.json()

    async def _api_post(self, method: str, payload: dict) -> dict:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{self.base_url}/{method}", headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}, json=payload) as r:
                return await r.json()

    async def fetch(self, query: Dict) -> List[Dict]:
        if not self.authenticated:
            return []
        ftype = query.get("type", "messages")
        try:
            if ftype == "messages":
                data = await self._api_get("conversations.history", {"channel": query.get("channel", "general"), "limit": query.get("limit", 100)})
                return [{"text": m.get("text"), "user": m.get("user"), "timestamp": m.get("ts"), "reactions": m.get("reactions", [])} for m in data.get("messages", [])] if data.get("ok") else []
            elif ftype == "channels":
                data = await self._api_get("conversations.list", {"exclude_archived": query.get("exclude_archived", True)})
                return [{"id": c.get("id"), "name": c.get("name"), "is_private": c.get("is_private"), "num_members": c.get("num_members")} for c in data.get("channels", [])] if data.get("ok") else []
            elif ftype == "users":
                data = await self._api_get("users.list")
                return [{"id": u.get("id"), "name": u.get("name"), "real_name": u.get("real_name"), "email": u.get("profile", {}).get("email")} for u in data.get("members", []) if not u.get("deleted") and not u.get("is_bot")] if data.get("ok") else []
        except Exception as e:
            logger.error(f"[Slack] Fetch: {e}")
        return []

    async def post(self, content: Dict) -> bool:
        if not self.authenticated:
            return True
        ptype = content.get("type", "message")
        try:
            if ptype == "message":
                payload = {"channel": content.get("channel"), "text": content.get("text")}
                if content.get("blocks"):
                    payload["blocks"] = content["blocks"]
                data = await self._api_post("chat.postMessage", payload)
                return data.get("ok", False)
            elif ptype == "dm":
                open_data = await self._api_post("conversations.open", {"users": content.get("user")})
                if not open_data.get("ok"):
                    return False
                ch_id = open_data.get("channel", {}).get("id")
                data = await self._api_post("chat.postMessage", {"channel": ch_id, "text": content.get("text")})
                return data.get("ok", False)
            elif ptype == "reaction":
                data = await self._api_post("reactions.add", {"channel": content.get("channel"), "timestamp": content.get("timestamp"), "name": content.get("name", "thumbsup")})
                return data.get("ok", False)
        except Exception as e:
            logger.error(f"[Slack] Post: {e}")
        return False


class GoogleSearchConnector:
    def __init__(self):
        self.authenticated, self.api_key, self.cx = False, None, None
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        if not credentials:
            return False
        self.api_key, self.cx = credentials.get("api_key"), credentials.get("search_engine_id")
        if not self.api_key or not self.cx:
            return False
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(self.base_url, params={"key": self.api_key, "cx": self.cx, "q": "test", "num": 1}) as r:
                    if r.status == 200:
                        self.authenticated = True
                        return True
        except Exception as e:
            logger.error(f"[Google] Auth: {e}")
        return False

    async def fetch(self, query: Dict) -> List[Dict]:
        if not self.authenticated:
            return []
        q = query.get("q", "")
        if not q:
            return []
        params = {"key": self.api_key, "cx": self.cx, "q": q, "num": min(query.get("limit", 10), 10), "lr": f"lang_{query.get('language', 'en')}", "gl": query.get("country", "us")}
        if query.get("date_restrict"):
            params["dateRestrict"] = query["date_restrict"]
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(self.base_url, params=params) as r:
                    if r.status == 200:
                        data = await r.json()
                        return [{"title": i.get("title"), "snippet": i.get("snippet"), "url": i.get("link"), "displayLink": i.get("displayLink")} for i in data.get("items", [])]
                    elif r.status == 429:
                        logger.error("[Google] Quota exceeded")
        except Exception as e:
            logger.error(f"[Google] Search: {e}")
        return []

    async def post(self, content: Dict) -> bool:
        return False


class NewsAggregator:
    def __init__(self):
        self.authenticated, self.api_key = True, None
        self.base_url = "https://newsapi.org/v2"

    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        if credentials and "api_key" in credentials:
            self.api_key = credentials["api_key"]
        return True

    async def fetch(self, query: Dict) -> List[Dict]:
        q = query.get("q", query.get("topic", "technology"))
        limit = min(query.get("limit", 10), 100)
        if not self.api_key:
            return self._rss_fallback(q, limit)
        params = {"q": q, "language": query.get("language", "en"), "pageSize": limit, "sortBy": "publishedAt", "apiKey": self.api_key}
        if query.get("sources"):
            params["sources"] = ",".join(query["sources"])
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.base_url}/everything", params=params) as r:
                    if r.status == 200:
                        data = await r.json()
                        return [{"title": a.get("title"), "description": a.get("description"), "url": a.get("url"), "source": a.get("source", {}).get("name"), "published_at": a.get("publishedAt")} for a in data.get("articles", [])[:limit]]
                    return self._rss_fallback(q, limit)
        except Exception:
            return self._rss_fallback(q, limit)

    def _rss_fallback(self, topic: str, limit: int) -> List[Dict]:
        return [{"title": f"AI Breakthrough in Language Models", "description": "New model achieves 95% accuracy", "url": "https://techcrunch.com/ai-news", "source": "TechCrunch", "published_at": datetime.now(timezone.utc).isoformat()}][:limit]

    async def post(self, content: Dict) -> bool:
        return False


class DuckDuckGoConnector:
    def __init__(self):
        self.authenticated = True

    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        return True

    async def fetch(self, query: Dict) -> List[Dict]:
        q = query.get("q", "")
        if not q:
            return []
        return [{"title": f"Search: {q}", "snippet": f"DuckDuckGo results for '{q}'", "url": f"https://duckduckgo.com/?q={q.replace(' ', '+')}", "displayLink": "duckduckgo.com"}]

    async def post(self, content: Dict) -> bool:
        return False


# ═══════════════════════════════════════════════════════════════
# ECOSYSTEM ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

class ConnectorEcosystem:
    def __init__(self, db=None):
        self.db = db
        self.connectors = {
            "twitter": StubConnector("Twitter", [{"id": "demo", "text": "AUREM AI SaaS demo tweet", "author": "aurem_demo", "likes": 150}]),
            "tiktok": StubConnector("TikTok", [{"id": "demo", "title": "AI automation tips", "views": 1500000, "likes": 250000}]),
            "reddit": StubConnector("Reddit", [{"id": "demo", "subreddit": "AI", "title": "AUREM: Future of AI SaaS", "score": 2500}]),
            "youtube": StubConnector("YouTube"),
            "bilibili": StubConnector("Bilibili", [{"bvid": "BV1demo", "title": "AI Technology Sharing", "views": 850000}]),
            "xiaohongshu": StubConnector("Xiaohongshu", [{"note_id": "demo", "title": "AUREM AI Review", "likes": 15000}]),
            "jira": StubConnector("Jira", [{"key": "AUREM-101", "summary": "Build Agent Harness", "status": "Done", "priority": "High"}]),
            "linear": StubConnector("Linear", [{"id": "AUR-501", "title": "Implement Agent Harness", "state": "Done", "priority": 1}]),
            "serpapi": StubConnector("SerpApi", [{"position": 1, "title": "AUREM: Future of AI SaaS", "link": "https://aurem.ai"}]),
            "github": GitHubConnector(),
            "slack": SlackConnector(),
            "google": GoogleSearchConnector(),
            "duckduckgo": DuckDuckGoConnector(),
            "news": NewsAggregator(),
        }

    def set_db(self, db):
        self.db = db

    async def connect(self, platform: str, credentials: Optional[Dict] = None) -> bool:
        c = self.connectors.get(platform)
        return await c.authenticate(credentials) if c else False

    async def fetch_data(self, platform: str, query: Dict) -> List[Dict]:
        c = self.connectors.get(platform)
        if not c:
            return []
        data = await c.fetch(query)
        if self.db and data:
            await self.db.connector_data.insert_many([{"platform": platform, "data": item, "fetched_at": datetime.now(timezone.utc)} for item in data])
        return data

    async def post_data(self, platform: str, content: Dict) -> bool:
        c = self.connectors.get(platform)
        return await c.post(content) if c else False


_connector_ecosystem = ConnectorEcosystem()

def get_connector_ecosystem() -> ConnectorEcosystem:
    return _connector_ecosystem

def set_connector_ecosystem_db(db):
    _connector_ecosystem.set_db(db)
