"""
Analytics Aggregator Service
Anonymized intelligence for AUREM super-admin (The Luxe Way)

CRITICAL PRIVACY RULE:
- NO PII (Personally Identifiable Information) stored in master analytics
- Customer emails/phones/names belong ONLY to tenants
- Only aggregate trends, counts, and anonymized patterns

What IS stored:
- Industry categories
- Geographic regions (city-level, not addresses)
- Conversation topics (anonymized)
- Engagement metrics
- Conversion patterns

What is NOT stored:
- Customer names
- Customer emails
- Customer phone numbers
- Specific conversation content
- Tenant customer lists
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class AnalyticsAggregator:
    """
    Aggregate anonymized analytics for AUREM growth intelligence
    
    TRUST LAYER: Customer data stays with tenant, only trends shared
    """
    
    def __init__(self, db=None):
        self.db = db
    
    async def aggregate_lead_event(
        self,
        tenant_id: str,
        industry: Optional[str] = None,
        location: Optional[Dict] = None,
        conversation_topics: Optional[List[str]] = None,
        engagement_score: float = 0.0,
        lead_source: Optional[str] = None
    ):
        """
        Record anonymized lead event for analytics
        
        Args:
            tenant_id: Tenant ID (for attribution, not exposed)
            industry: Business industry category
            location: {"city": "Toronto", "region": "ON", "country": "CA"}
            conversation_topics: List of detected topics (anonymized)
            engagement_score: 0.0-1.0 engagement level
            lead_source: Channel (whatsapp, voice, web, etc.)
        
        Stores aggregate data ONLY - no PII
        """
        if self.db is None:
            logger.error("[AnalyticsAggregator] Database not initialized")
            return
        
        try:
            # Create anonymized event
            event = {
                "event_type": "lead_captured",
                "tenant_id": tenant_id,  # Internal only
                "industry": industry or "uncategorized",
                "location": {
                    "city": location.get("city") if location else None,
                    "region": location.get("region") if location else None,
                    "country": location.get("country", "Unknown") if location else "Unknown"
                },
                "topics": conversation_topics or [],
                "engagement_score": engagement_score,
                "lead_source": lead_source or "web",
                "timestamp": datetime.now(timezone.utc),
                "date": datetime.now(timezone.utc).date().isoformat(),
                "hour": datetime.now(timezone.utc).hour
            }
            
            # Store in master analytics collection (NO PII)
            await self.db.analytics_events.insert_one(event)
            
            # Update daily aggregates for fast queries
            await self._update_daily_aggregates(event)
            
            logger.info(f"[AnalyticsAggregator] Event recorded: {industry} lead in {location.get('city') if location else 'Unknown'}")
        
        except Exception as e:
            logger.error(f"[AnalyticsAggregator] Error recording event: {e}")
    
    async def _update_daily_aggregates(self, event: Dict):
        """Update daily summary for fast dashboard queries"""
        
        date_key = event["date"]
        
        # Increment counters
        await self.db.analytics_daily.update_one(
            {"date": date_key},
            {
                "$inc": {
                    "total_leads": 1,
                    f"by_industry.{event['industry']}": 1,
                    f"by_country.{event['location']['country']}": 1,
                    f"by_source.{event['lead_source']}": 1
                },
                "$addToSet": {
                    "topics": {"$each": event["topics"]}
                },
                "$set": {
                    "last_updated": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
    
    async def get_insights_dashboard(
        self,
        date_range_days: int = 30
    ) -> Dict:
        """
        Get super-admin insights dashboard (anonymized data only)
        
        Args:
            date_range_days: How many days to look back
        
        Returns:
            {
                "total_leads": int,
                "by_industry": {...},
                "by_geography": {...},
                "by_source": {...},
                "trending_topics": [...],
                "engagement_trends": {...},
                "growth_rate": float
            }
        """
        if self.db is None:
            return {"error": "Database not initialized"}
        
        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=date_range_days)
            
            # Get daily aggregates
            daily_data = await self.db.analytics_daily.find(
                {
                    "date": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat()
                    }
                },
                {"_id": 0}
            ).to_list(100)
            
            # Aggregate across days
            total_leads = 0
            by_industry = defaultdict(int)
            by_country = defaultdict(int)
            by_source = defaultdict(int)
            all_topics = []
            
            for day in daily_data:
                total_leads += day.get("total_leads", 0)
                
                # Industry breakdown
                for industry, count in day.get("by_industry", {}).items():
                    by_industry[industry] += count
                
                # Geography breakdown
                for country, count in day.get("by_country", {}).items():
                    by_country[country] += count
                
                # Source breakdown
                for source, count in day.get("by_source", {}).items():
                    by_source[source] += count
                
                # Topics
                all_topics.extend(day.get("topics", []))
            
            # Calculate growth rate (compare to previous period)
            previous_start = start_date - timedelta(days=date_range_days)
            previous_data = await self.db.analytics_daily.find(
                {
                    "date": {
                        "$gte": previous_start.isoformat(),
                        "$lt": start_date.isoformat()
                    }
                },
                {"_id": 0}
            ).to_list(100)
            
            previous_total = sum(d.get("total_leads", 0) for d in previous_data)
            growth_rate = ((total_leads - previous_total) / previous_total * 100) if previous_total > 0 else 0.0
            
            # Get trending topics (frequency count)
            from collections import Counter
            topic_counts = Counter(all_topics)
            trending_topics = [
                {"topic": topic, "count": count}
                for topic, count in topic_counts.most_common(10)
            ]
            
            return {
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": date_range_days
                },
                "total_leads": total_leads,
                "by_industry": dict(by_industry),
                "by_geography": dict(by_country),
                "by_source": dict(by_source),
                "trending_topics": trending_topics,
                "growth_rate": round(growth_rate, 2),
                "previous_period_total": previous_total
            }
        
        except Exception as e:
            logger.error(f"[AnalyticsAggregator] Error getting insights: {e}")
            return {"error": str(e)}
    
    async def get_industry_insights(self, industry: str) -> Dict:
        """
        Get deep insights for specific industry
        
        Args:
            industry: Industry category
        
        Returns:
            Anonymized trends for that industry
        """
        if self.db is None:
            return {"error": "Database not initialized"}
        
        try:
            # Get recent events for this industry
            events = await self.db.analytics_events.find(
                {
                    "industry": industry,
                    "timestamp": {
                        "$gte": datetime.now(timezone.utc) - timedelta(days=30)
                    }
                },
                {"_id": 0}
            ).to_list(1000)
            
            if not events:
                return {"industry": industry, "total_leads": 0}
            
            # Analyze patterns
            total = len(events)
            avg_engagement = sum(e.get("engagement_score", 0) for e in events) / total
            
            # Top topics for this industry
            all_topics = []
            for e in events:
                all_topics.extend(e.get("topics", []))
            
            from collections import Counter
            topic_counts = Counter(all_topics)
            top_topics = [
                {"topic": topic, "count": count}
                for topic, count in topic_counts.most_common(5)
            ]
            
            # Geographic distribution
            cities = defaultdict(int)
            for e in events:
                city = e.get("location", {}).get("city")
                if city:
                    cities[city] += 1
            
            top_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                "industry": industry,
                "total_leads": total,
                "avg_engagement_score": round(avg_engagement, 2),
                "top_topics": top_topics,
                "top_cities": [{"city": city, "count": count} for city, count in top_cities],
                "date_range_days": 30
            }
        
        except Exception as e:
            logger.error(f"[AnalyticsAggregator] Error getting industry insights: {e}")
            return {"error": str(e)}


# Singleton instance
_analytics_aggregator = None


def get_analytics_aggregator(db=None) -> AnalyticsAggregator:
    """Get or create analytics aggregator instance"""
    global _analytics_aggregator
    if _analytics_aggregator is None or db is not None:
        _analytics_aggregator = AnalyticsAggregator(db)
    return _analytics_aggregator
