"""
AUREM Daily Digest System
Centralized notification engine - replaces spam with one smart summary
BOS Core Feature
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DigestFrequency(str, Enum):
    """Digest delivery frequency"""
    DAILY = "daily"        # Once per day (8am)
    TWICE_DAILY = "twice_daily"  # 8am and 6pm
    WEEKLY = "weekly"      # Monday 8am
    REAL_TIME = "real_time"  # Immediate (for critical events only)


class EventPriority(str, Enum):
    """Event priority levels"""
    CRITICAL = "critical"  # System down, security breach
    HIGH = "high"          # Revenue loss, major bug
    MEDIUM = "medium"      # New lead, cart abandonment
    LOW = "low"            # Analytics update, info


class DigestEvent(BaseModel):
    """Event to be included in digest"""
    event_id: str
    event_type: str
    priority: EventPriority
    title: str
    description: str
    timestamp: datetime
    business_id: str
    metadata: Dict[str, Any] = {}
    action_required: bool = False
    action_url: Optional[str] = None


class DailyDigestEngine:
    """
    Daily Digest System - Autonomous Business Operating System Core
    
    Replaces 50 notifications with 1 smart summary.
    
    Features:
    - Event aggregation from all sources
    - AI summarization (not just list)
    - Priority-based filtering
    - Action recommendations
    - Multi-channel delivery (WhatsApp, Email, Dashboard)
    """
    
    def __init__(self, db=None):
        self.db = db
        self.api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    
    async def record_event(
        self,
        event_type: str,
        title: str,
        description: str,
        business_id: str,
        priority: EventPriority = EventPriority.MEDIUM,
        metadata: Dict[str, Any] = None,
        action_required: bool = False,
        action_url: str = None
    ) -> str:
        """
        Record event for digest aggregation
        
        All system events flow through here:
        - Cart abandonments
        - New leads
        - System errors
        - Revenue milestones
        - Customer feedback
        - Follow-up results
        """
        from uuid import uuid4
        
        event = DigestEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            priority=priority,
            title=title,
            description=description,
            timestamp=datetime.now(timezone.utc),
            business_id=business_id,
            metadata=metadata or {},
            action_required=action_required,
            action_url=action_url
        )
        
        # Store in database
        if self.db:
            await self.db.aurem_digest_events.insert_one(event.dict())
        
        # If CRITICAL priority, send real-time alert
        if priority == EventPriority.CRITICAL:
            await self._send_realtime_alert(event)
        
        logger.info(f"[DIGEST] Recorded {priority.value} event: {title}")
        return event.event_id
    
    async def generate_daily_digest(
        self,
        business_id: str,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> Dict[str, Any]:
        """
        Generate daily digest for a business
        
        This is the "orchestrator" - aggregates all events and creates
        one intelligent summary instead of spam.
        """
        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        if not end_time:
            end_time = datetime.now(timezone.utc)
        
        # Get all events in time range
        events = []
        if self.db:
            cursor = self.db.aurem_digest_events.find({
                "business_id": business_id,
                "timestamp": {"$gte": start_time, "$lt": end_time}
            }).sort("timestamp", -1)
            events = await cursor.to_list(1000)
        
        if not events:
            return {
                "business_id": business_id,
                "period": f"{start_time.date()} to {end_time.date()}",
                "events_count": 0,
                "summary": "No activity in the last 24 hours.",
                "sections": []
            }
        
        # Group events by type and priority
        grouped = self._group_events(events)
        
        # Generate AI summary
        summary = await self._generate_ai_summary(grouped, business_id)
        
        # Build digest structure
        digest = {
            "business_id": business_id,
            "period": f"{start_time.date()} to {end_time.date()}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "events_count": len(events),
            "summary": summary,
            "sections": self._build_sections(grouped),
            "action_items": self._extract_action_items(events),
            "key_metrics": await self._calculate_metrics(business_id, start_time, end_time)
        }
        
        return digest
    
    def _group_events(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """Group events by type and priority"""
        grouped = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": []
        }
        
        for event in events:
            priority = event.get("priority", "medium")
            grouped[priority].append(event)
        
        return grouped
    
    async def _generate_ai_summary(
        self,
        grouped_events: Dict[str, List[Dict]],
        business_id: str
    ) -> str:
        """
        Use AI to generate intelligent summary
        Not just a list - actual insights
        """
        # Count events
        total_events = sum(len(events) for events in grouped_events.values())
        critical_count = len(grouped_events.get("critical", []))
        high_count = len(grouped_events.get("high", []))
        
        if total_events == 0:
            return "No significant activity in the last 24 hours."
        
        # Build context for AI
        event_context = []
        for priority, events in grouped_events.items():
            if events:
                event_context.append(f"{priority.upper()} ({len(events)} events):")
                for event in events[:5]:  # Top 5 per priority
                    event_context.append(f"  - {event.get('title')}")
        
        context_text = "\n".join(event_context)
        
        prompt = f"""You are analyzing business activity for the last 24 hours.

Activity Summary:
{context_text}

Generate a concise 2-3 sentence executive summary highlighting:
1. The most important development
2. Overall business health indicator
3. Key action needed (if any)

Be specific and actionable. Focus on what matters."""

        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"digest_{business_id}"
            ).with_model("openai", "gpt-4o")
            
            response = await chat.send_message(UserMessage(text=prompt))
            return response
            
        except Exception as e:
            logger.error(f"AI summary generation error: {e}")
            # Fallback to simple summary
            if critical_count > 0:
                return f"⚠️ {critical_count} critical issues require immediate attention. {total_events} total events recorded."
            else:
                return f"✅ {total_events} events recorded. {high_count} high-priority items for review."
    
    def _build_sections(self, grouped_events: Dict[str, List[Dict]]) -> List[Dict]:
        """Build structured sections for digest"""
        sections = []
        
        priority_order = ["critical", "high", "medium", "low"]
        priority_icons = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "ℹ️",
            "low": "📊"
        }
        priority_titles = {
            "critical": "Critical Issues",
            "high": "High Priority",
            "medium": "Medium Priority",
            "low": "Updates & Info"
        }
        
        for priority in priority_order:
            events = grouped_events.get(priority, [])
            if events:
                sections.append({
                    "priority": priority,
                    "icon": priority_icons[priority],
                    "title": priority_titles[priority],
                    "count": len(events),
                    "events": [
                        {
                            "title": e.get("title"),
                            "description": e.get("description"),
                            "timestamp": e.get("timestamp"),
                            "action_required": e.get("action_required", False),
                            "action_url": e.get("action_url")
                        }
                        for e in events[:10]  # Top 10 per section
                    ]
                })
        
        return sections
    
    def _extract_action_items(self, events: List[Dict]) -> List[Dict]:
        """Extract events that require action"""
        action_items = []
        
        for event in events:
            if event.get("action_required"):
                action_items.append({
                    "title": event.get("title"),
                    "description": event.get("description"),
                    "action_url": event.get("action_url"),
                    "priority": event.get("priority")
                })
        
        return sorted(action_items, key=lambda x: ["critical", "high", "medium", "low"].index(x["priority"]))
    
    async def _calculate_metrics(
        self,
        business_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Calculate key metrics for the period"""
        metrics = {
            "new_leads": 0,
            "followups_sent": 0,
            "conversations_started": 0,
            "handoffs_to_human": 0,
            "revenue_opportunities": 0
        }
        
        if not self.db:
            return metrics
        
        try:
            # Count new customers
            new_customers = await self.db.aurem_customers.count_documents({
                "business_id": business_id,
                "created_at": {"$gte": start_time, "$lt": end_time}
            })
            metrics["new_leads"] = new_customers
            
            # Count follow-ups sent
            followups = await self.db.aurem_messages.count_documents({
                "business_id": business_id,
                "direction": "outbound",
                "metadata.followup": True,
                "timestamp": {"$gte": start_time, "$lt": end_time}
            })
            metrics["followups_sent"] = followups
            
            # Count conversations
            conversations = await self.db.aurem_messages.count_documents({
                "business_id": business_id,
                "direction": "inbound",
                "timestamp": {"$gte": start_time, "$lt": end_time}
            })
            metrics["conversations_started"] = conversations
            
        except Exception as e:
            logger.error(f"Metrics calculation error: {e}")
        
        return metrics
    
    async def _send_realtime_alert(self, event: DigestEvent):
        """Send immediate alert for critical events"""
        logger.warning(f"[DIGEST] CRITICAL ALERT: {event.title}")
        
        # TODO: Integrate with WhatsApp/SMS for real-time alerts
        # For now, just log
        pass
    
    async def send_digest(
        self,
        business_id: str,
        channel: str = "whatsapp",
        recipient: str = None
    ) -> Dict[str, Any]:
        """
        Generate and send digest via specified channel
        
        Channels: whatsapp, email, dashboard
        """
        # Generate digest
        digest = await self.generate_daily_digest(business_id)
        
        # Format for channel
        if channel == "whatsapp":
            message = self._format_whatsapp_digest(digest)
        elif channel == "email":
            message = self._format_email_digest(digest)
        else:
            message = digest  # JSON for dashboard
        
        # Send via appropriate channel
        if channel == "whatsapp" and recipient:
            from services.omnidimension_service import get_omni_service, Channel
            omni = get_omni_service(self.db)
            
            result = await omni.send_outbound_message(
                channel=Channel.WHATSAPP,
                business_id=business_id,
                customer_id=recipient,
                content=message,
                metadata={"digest": True, "automated": True}
            )
            
            return {"sent": True, "channel": channel, "result": result}
        
        return {"sent": False, "digest": digest, "message": message}
    
    def _format_whatsapp_digest(self, digest: Dict) -> str:
        """Format digest for WhatsApp (concise, actionable)"""
        lines = [
            f"🤖 *AUREM Daily Digest*",
            f"📅 {digest['period']}",
            "",
            f"📊 *Summary*",
            digest['summary'],
            ""
        ]
        
        # Add action items if any
        action_items = digest.get('action_items', [])
        if action_items:
            lines.append("⚡ *Action Required:*")
            for item in action_items[:3]:  # Top 3
                lines.append(f"  • {item['title']}")
            lines.append("")
        
        # Add key metrics
        metrics = digest.get('key_metrics', {})
        if metrics:
            lines.append("📈 *Key Metrics:*")
            if metrics.get('new_leads'):
                lines.append(f"  • {metrics['new_leads']} new leads")
            if metrics.get('followups_sent'):
                lines.append(f"  • {metrics['followups_sent']} follow-ups sent")
            if metrics.get('conversations_started'):
                lines.append(f"  • {metrics['conversations_started']} conversations")
        
        return "\n".join(lines)
    
    def _format_email_digest(self, digest: Dict) -> str:
        """Format digest for email (detailed HTML)"""
        # TODO: Build HTML email template
        return self._format_whatsapp_digest(digest)  # Fallback to text for now


# Singleton
_digest_engine = None

def get_digest_engine(db=None):
    global _digest_engine
    if _digest_engine is None:
        _digest_engine = DailyDigestEngine(db)
    elif db and _digest_engine.db is None:
        _digest_engine.db = db
    return _digest_engine
