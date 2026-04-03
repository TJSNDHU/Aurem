"""
Smart Search Service
Intelligent search with automatic fallback: Google → DuckDuckGo

Strategy:
1. Try Google first (100 free queries/day, best quality)
2. If quota exceeded → Auto-switch to DuckDuckGo (unlimited, lower quality)
3. Track daily usage
4. Reset at midnight
5. Manual override available
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SmartSearchService:
    """
    Intelligent search with automatic fallback
    
    Priority: Google (best quality) → DuckDuckGo (unlimited fallback)
    """
    
    def __init__(self, db=None):
        self.db = db
        self.google_daily_limit = 95  # Reserve 5 for safety
        self.current_engine = "google"
        self.google_queries_today = 0
        self.last_reset = datetime.now(timezone.utc).date()
    
    def set_db(self, db):
        """Set database reference"""
        self.db = db
    
    async def _check_and_reset_quota(self):
        """Reset quota at midnight"""
        today = datetime.now(timezone.utc).date()
        
        if today > self.last_reset:
            # New day, reset quota
            self.google_queries_today = 0
            self.last_reset = today
            self.current_engine = "google"
            logger.info("[SmartSearch] Daily quota reset - back to Google")
            
            # Log to database
            if self.db is not None:
                await self.db.search_quota.insert_one({
                    "event": "quota_reset",
                    "date": today.isoformat(),
                    "timestamp": datetime.now(timezone.utc)
                })
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        engine: Optional[str] = None,  # Manual override
        **kwargs
    ) -> Dict[str, Any]:
        """
        Smart search with automatic fallback
        
        Args:
            query: Search query
            limit: Number of results
            engine: Manual override ("google" or "duckduckgo")
            **kwargs: Additional params (language, country, date_restrict)
        
        Returns:
        {
            "query": "artificial intelligence",
            "engine_used": "google",
            "quota_remaining": 42,
            "results": [...],
            "fallback_used": false,
            "search_time": 0.523
        }
        """
        await self._check_and_reset_quota()
        
        start_time = datetime.now(timezone.utc)
        fallback_used = False
        engine_used = engine or self.current_engine
        results = []
        
        # Manual override
        if engine:
            logger.info(f"[SmartSearch] Manual override: {engine}")
            results = await self._execute_search(engine, query, limit, **kwargs)
            engine_used = engine
        
        else:
            # Try Google first (if quota available)
            if self.google_queries_today < self.google_daily_limit:
                try:
                    results = await self._execute_search("google", query, limit, **kwargs)
                    self.google_queries_today += 1
                    engine_used = "google"
                    
                    # Log successful Google search
                    logger.info(f"[SmartSearch] Google search successful ({self.google_queries_today}/{self.google_daily_limit})")
                
                except QuotaExceededException:
                    logger.warning("[SmartSearch] Google quota exceeded - switching to DuckDuckGo")
                    fallback_used = True
                    engine_used = "duckduckgo"
                    results = await self._execute_search("duckduckgo", query, limit, **kwargs)
                    
                    # Mark as permanently switched for today
                    self.current_engine = "duckduckgo"
                
                except Exception as e:
                    logger.error(f"[SmartSearch] Google search failed: {e}")
                    fallback_used = True
                    engine_used = "duckduckgo"
                    results = await self._execute_search("duckduckgo", query, limit, **kwargs)
            
            else:
                # Quota exceeded, use DuckDuckGo
                logger.info(f"[SmartSearch] Google quota reached ({self.google_queries_today}/{self.google_daily_limit}) - using DuckDuckGo")
                fallback_used = True
                engine_used = "duckduckgo"
                results = await self._execute_search("duckduckgo", query, limit, **kwargs)
        
        # Calculate search time
        search_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        # Log to database
        if self.db is not None:
            await self.db.search_history.insert_one({
                "query": query,
                "engine": engine_used,
                "results_count": len(results),
                "fallback_used": fallback_used,
                "search_time": search_time,
                "timestamp": datetime.now(timezone.utc)
            })
        
        return {
            "query": query,
            "engine_used": engine_used,
            "quota_remaining": self.google_daily_limit - self.google_queries_today if engine_used == "google" else None,
            "results": results,
            "fallback_used": fallback_used,
            "search_time": round(search_time, 3),
            "total_results": len(results)
        }
    
    async def _execute_search(
        self,
        engine: str,
        query: str,
        limit: int,
        **kwargs
    ) -> List[Dict]:
        """Execute search on specific engine"""
        from services.connector_ecosystem import get_connector_ecosystem
        
        ecosystem = get_connector_ecosystem()
        
        search_params = {
            "q": query,
            "limit": limit,
            **kwargs
        }
        
        results = await ecosystem.fetch_data(engine, search_params)
        
        if engine == "google" and not results:
            # Check if it's a quota issue
            raise QuotaExceededException("Google quota exceeded")
        
        return results
    
    async def get_quota_status(self) -> Dict[str, Any]:
        """
        Get current quota status
        
        Returns:
        {
            "google_used": 42,
            "google_remaining": 53,
            "google_limit": 95,
            "current_engine": "google",
            "resets_at": "2026-04-04T00:00:00Z"
        }
        """
        await self._check_and_reset_quota()
        
        # Calculate next reset time (midnight UTC)
        tomorrow = datetime.now(timezone.utc).date()
        from datetime import timedelta
        tomorrow = tomorrow + timedelta(days=1)
        reset_time = datetime.combine(tomorrow, datetime.min.time())
        
        return {
            "google_used": self.google_queries_today,
            "google_remaining": max(0, self.google_daily_limit - self.google_queries_today),
            "google_limit": self.google_daily_limit,
            "current_engine": self.current_engine,
            "duckduckgo_available": True,
            "resets_at": reset_time.isoformat(),
            "fallback_active": self.current_engine == "duckduckgo"
        }
    
    async def switch_engine(self, engine: str) -> bool:
        """
        Manually switch search engine
        
        Args:
            engine: "google" or "duckduckgo"
        """
        if engine not in ["google", "duckduckgo"]:
            return False
        
        self.current_engine = engine
        logger.info(f"[SmartSearch] Manual switch to {engine}")
        
        return True


class QuotaExceededException(Exception):
    """Raised when search quota is exceeded"""
    pass


# Global instance
_smart_search = SmartSearchService()


def get_smart_search() -> SmartSearchService:
    """Get global smart search instance"""
    return _smart_search


def set_smart_search_db(db):
    """Set database for smart search"""
    _smart_search.set_db(db)
