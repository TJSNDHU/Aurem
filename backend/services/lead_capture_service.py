"""
Lead Capture Service
Detects sales intent in AI conversations and extracts structured lead data

Features:
- Intent detection (buying signals, appointment requests)
- Lead data extraction (name, phone, email, preferences)
- Multi-tenancy support
- Integration with CRM systems
"""

import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)


class LeadCaptureService:
    """
    Detect and capture leads from AI conversations
    """
    
    # Intent keywords that signal a potential lead
    LEAD_INTENT_KEYWORDS = [
        # Booking/Appointment
        "book", "appointment", "schedule", "reserve", "consultation",
        # Buying
        "buy", "purchase", "order", "get", "interested", "want",
        # Pricing/Information
        "price", "cost", "how much", "available", "in stock",
        # Contact
        "call me", "email me", "contact", "reach out",
        # Urgency
        "today", "tomorrow", "asap", "urgent", "now"
    ]
    
    # Keywords that indicate NOT a lead (questions, general info)
    NEGATIVE_KEYWORDS = [
        "just looking", "browsing", "maybe later", "not ready",
        "thinking about", "just curious", "no thanks"
    ]
    
    def __init__(self, db):
        """
        Initialize Lead Capture Service
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        logger.info("[LeadCapture] Service initialized")
    
    def detect_lead_intent(self, message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Detect if a message contains lead intent (buying signals)
        
        Args:
            message: Current user message
            conversation_history: Previous messages in conversation
        
        Returns:
            {
                "is_lead": bool,
                "confidence": float (0.0 to 1.0),
                "signals": List[str],  # What triggered the detection
                "intent_type": str  # "booking", "purchase", "inquiry"
            }
        """
        message_lower = message.lower()
        
        # Check for negative signals first
        negative_score = sum(1 for keyword in self.NEGATIVE_KEYWORDS if keyword in message_lower)
        if negative_score > 0:
            return {
                "is_lead": False,
                "confidence": 0.0,
                "signals": [],
                "intent_type": None
            }
        
        # Check for positive signals
        signals = []
        for keyword in self.LEAD_INTENT_KEYWORDS:
            if keyword in message_lower:
                signals.append(keyword)
        
        # Determine intent type
        intent_type = None
        if any(k in message_lower for k in ["book", "appointment", "schedule", "consultation"]):
            intent_type = "booking"
        elif any(k in message_lower for k in ["buy", "purchase", "order"]):
            intent_type = "purchase"
        elif any(k in message_lower for k in ["price", "cost", "available"]):
            intent_type = "inquiry"
        
        # Calculate confidence based on number of signals
        confidence = min(len(signals) * 0.25, 1.0)  # Each signal adds 25%
        
        # Boost confidence if conversation history shows engagement
        if conversation_history and len(conversation_history) > 3:
            confidence = min(confidence + 0.2, 1.0)
        
        is_lead = confidence >= 0.5  # Threshold: 50% confidence
        
        return {
            "is_lead": is_lead,
            "confidence": confidence,
            "signals": signals,
            "intent_type": intent_type
        }
    
    def extract_contact_info(self, conversation: List[Dict]) -> Dict[str, Optional[str]]:
        """
        Extract contact information from conversation
        
        Args:
            conversation: List of messages [{"role": "user"/"assistant", "content": "..."}]
        
        Returns:
            {
                "name": str or None,
                "phone": str or None,
                "email": str or None
            }
        """
        contact_info = {
            "name": None,
            "phone": None,
            "email": None
        }
        
        # Combine all user messages
        user_messages = " ".join([
            msg["content"] for msg in conversation 
            if msg.get("role") == "user"
        ])
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, user_messages)
        if email_match:
            contact_info["email"] = email_match.group(0)
        
        # Extract phone (various formats)
        phone_patterns = [
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 555-123-4567
            r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b',  # (555) 123-4567
            r'\b\+\d{1,3}\s*\d{3}[-.]?\d{3}[-.]?\d{4}\b'  # +1 555-123-4567
        ]
        for pattern in phone_patterns:
            phone_match = re.search(pattern, user_messages)
            if phone_match:
                contact_info["phone"] = phone_match.group(0)
                break
        
        # Extract name (basic heuristic - look for "my name is", "I'm", etc.)
        name_patterns = [
            r"my name is ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
            r"I'm ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
            r"this is ([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, user_messages, re.IGNORECASE)
            if name_match:
                contact_info["name"] = name_match.group(1)
                break
        
        return contact_info
    
    def extract_preferences(self, conversation: List[Dict]) -> Dict[str, Any]:
        """
        Extract customer preferences from conversation
        
        Args:
            conversation: List of messages
        
        Returns:
            {
                "product_interest": str or None,
                "service_interest": str or None,
                "preferred_time": str or None,
                "budget": str or None,
                "special_requests": str or None
            }
        """
        user_messages = " ".join([
            msg["content"] for msg in conversation 
            if msg.get("role") == "user"
        ])
        
        preferences = {
            "product_interest": None,
            "service_interest": None,
            "preferred_time": None,
            "budget": None,
            "special_requests": None
        }
        
        # Extract time preferences
        time_keywords = ["tomorrow", "today", "next week", "this afternoon", "morning", "evening"]
        for keyword in time_keywords:
            if keyword in user_messages.lower():
                preferences["preferred_time"] = keyword
                break
        
        # Extract budget (look for dollar amounts)
        budget_pattern = r'\$\d+(?:,\d{3})*(?:\.\d{2})?'
        budget_match = re.search(budget_pattern, user_messages)
        if budget_match:
            preferences["budget"] = budget_match.group(0)
        
        return preferences
    
    async def create_lead(
        self,
        tenant_id: str,
        conversation_id: str,
        conversation: List[Dict],
        intent_data: Dict,
        source: str = "ai_chat"
    ) -> Dict[str, Any]:
        """
        Create a lead record in the database
        
        Args:
            tenant_id: Tenant ID (for multi-tenancy)
            conversation_id: ID of the conversation
            conversation: Full conversation history
            intent_data: Output from detect_lead_intent()
            source: Lead source (default: "ai_chat")
        
        Returns:
            Created lead document
        """
        try:
            # Extract contact info and preferences
            contact_info = self.extract_contact_info(conversation)
            preferences = self.extract_preferences(conversation)
            
            # Generate lead ID
            lead_id = f"lead_{uuid4().hex[:12]}"
            
            # Create lead document
            lead = {
                "lead_id": lead_id,
                "tenant_id": tenant_id,
                "status": "new",  # new, contacted, converted, lost
                "source": source,
                "customer": {
                    "name": contact_info.get("name") or "Unknown",
                    "phone": contact_info.get("phone"),
                    "email": contact_info.get("email")
                },
                "interest": {
                    "intent_type": intent_data.get("intent_type"),
                    "product_interest": preferences.get("product_interest"),
                    "service_interest": preferences.get("service_interest"),
                    "preferred_time": preferences.get("preferred_time"),
                    "budget": preferences.get("budget"),
                    "special_requests": preferences.get("special_requests")
                },
                "conversation_id": conversation_id,
                "transcript": conversation,
                "detection": {
                    "confidence": intent_data.get("confidence"),
                    "signals": intent_data.get("signals")
                },
                "captured_at": datetime.now(timezone.utc),
                "value_estimate": self._estimate_lead_value(intent_data, preferences),
                "ai_confidence": intent_data.get("confidence"),
                "notifications_sent": [],
                "metadata": {}
            }
            
            # Save to database
            await self.db.leads.insert_one(lead)
            
            logger.info(f"[LeadCapture] Created lead {lead_id} for tenant {tenant_id}")
            
            return lead
        
        except Exception as e:
            logger.error(f"[LeadCapture] Error creating lead: {e}")
            raise
    
    def _estimate_lead_value(self, intent_data: Dict, preferences: Dict) -> float:
        """
        Estimate the potential value of a lead
        
        Args:
            intent_data: Intent detection results
            preferences: Customer preferences
        
        Returns:
            Estimated value in dollars
        """
        base_value = 100.0  # Base value for any lead
        
        # Boost for high-intent keywords
        if intent_data.get("intent_type") == "purchase":
            base_value *= 2.0
        elif intent_data.get("intent_type") == "booking":
            base_value *= 1.5
        
        # Boost for budget mentioned
        if preferences.get("budget"):
            try:
                budget_str = preferences["budget"].replace("$", "").replace(",", "")
                budget_amount = float(budget_str)
                base_value = max(base_value, budget_amount * 0.7)  # 70% of stated budget
            except:
                pass
        
        # Boost for urgency
        if preferences.get("preferred_time") in ["today", "tomorrow", "asap"]:
            base_value *= 1.3
        
        return round(base_value, 2)
    
    async def get_leads(
        self,
        tenant_id: str,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get leads for a tenant
        
        Args:
            tenant_id: Tenant ID
            status: Filter by status (new, contacted, converted, lost)
            limit: Max number of leads to return
        
        Returns:
            List of lead documents
        """
        try:
            query = {"tenant_id": tenant_id}
            
            if status:
                query["status"] = status
            
            leads = await self.db.leads.find(
                query,
                {"_id": 0}
            ).sort("captured_at", -1).limit(limit).to_list(limit)
            
            return leads
        
        except Exception as e:
            logger.error(f"[LeadCapture] Error getting leads: {e}")
            return []
    
    async def get_lead_stats(self, tenant_id: str, period: str = "today") -> Dict[str, Any]:
        """
        Get lead statistics for a tenant
        
        Args:
            tenant_id: Tenant ID
            period: Time period ("today", "week", "month", "all")
        
        Returns:
            {
                "total_leads": int,
                "new_leads": int,
                "converted": int,
                "total_value": float,
                "conversion_rate": float
            }
        """
        try:
            # Determine date filter based on period
            now = datetime.now(timezone.utc)
            date_filter = {}
            
            if period == "today":
                from datetime import timedelta
                start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                date_filter = {"captured_at": {"$gte": start_of_day}}
            
            query = {"tenant_id": tenant_id, **date_filter}
            
            # Get all leads
            all_leads = await self.db.leads.find(query, {"_id": 0}).to_list(1000)
            
            # Calculate stats
            total_leads = len(all_leads)
            new_leads = len([l for l in all_leads if l.get("status") == "new"])
            converted = len([l for l in all_leads if l.get("status") == "converted"])
            total_value = sum(l.get("value_estimate", 0) for l in all_leads)
            conversion_rate = (converted / total_leads * 100) if total_leads > 0 else 0
            
            return {
                "total_leads": total_leads,
                "new_leads": new_leads,
                "converted": converted,
                "total_value": round(total_value, 2),
                "conversion_rate": round(conversion_rate, 1)
            }
        
        except Exception as e:
            logger.error(f"[LeadCapture] Error getting stats: {e}")
            return {
                "total_leads": 0,
                "new_leads": 0,
                "converted": 0,
                "total_value": 0.0,
                "conversion_rate": 0.0
            }


# Singleton instance
_lead_capture_service = None


def get_lead_capture_service(db):
    """Get singleton LeadCaptureService instance"""
    global _lead_capture_service
    
    if _lead_capture_service is None:
        _lead_capture_service = LeadCaptureService(db)
    
    return _lead_capture_service
