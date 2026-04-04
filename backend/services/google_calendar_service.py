"""
Google Calendar Integration Service
Enables AI to book appointments directly into business owner's calendar

Features:
- Check calendar availability
- Create calendar events
- Send calendar invites
- Handle timezone conversions
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import os

logger = logging.getLogger(__name__)

# Google Calendar will be integrated via google-auth and google-api-python-client
# For now, we'll create the service structure and add actual Google integration later

class GoogleCalendarService:
    """
    Service for Google Calendar integration
    """
    
    def __init__(self, db):
        """
        Initialize Google Calendar Service
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.enabled = False  # Will be enabled once Google OAuth is configured
        logger.info("[GoogleCalendar] Service initialized (OAuth pending)")
    
    async def check_availability(
        self,
        tenant_id: str,
        date: str,
        time_slots: List[str]
    ) -> Dict[str, bool]:
        """
        Check if specific time slots are available
        
        Args:
            tenant_id: Tenant ID (to get their calendar)
            date: Date in YYYY-MM-DD format
            time_slots: List of times in HH:MM format (e.g., ["14:00", "15:00"])
        
        Returns:
            {
                "14:00": True,  # Available
                "15:00": False  # Booked
            }
        """
        if not self.enabled:
            logger.warning("[GoogleCalendar] Service not enabled, returning mock availability")
            # Mock response for development
            return {slot: True for slot in time_slots}
        
        try:
            # TODO: Implement actual Google Calendar API call
            # 1. Get tenant's calendar credentials from database
            # 2. Query Google Calendar API for busy times
            # 3. Return availability map
            
            pass
        
        except Exception as e:
            logger.error(f"[GoogleCalendar] Error checking availability: {e}")
            return {}
    
    async def create_appointment(
        self,
        tenant_id: str,
        appointment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a calendar appointment
        
        Args:
            tenant_id: Tenant ID
            appointment_data: {
                "customer_name": str,
                "customer_email": str,
                "service": str,
                "date": str (YYYY-MM-DD),
                "time": str (HH:MM),
                "duration_minutes": int,
                "notes": str (optional)
            }
        
        Returns:
            {
                "success": bool,
                "event_id": str,
                "calendar_link": str,
                "ics_download": str (for email attachments)
            }
        """
        if not self.enabled:
            logger.warning("[GoogleCalendar] Service not enabled, creating mock appointment")
            # Mock response for development
            return {
                "success": True,
                "event_id": f"mock_event_{datetime.now().timestamp()}",
                "calendar_link": "https://calendar.google.com/calendar/event?eid=mock",
                "ics_download": None
            }
        
        try:
            # TODO: Implement actual Google Calendar event creation
            # 1. Get tenant's calendar credentials
            # 2. Create event via Google Calendar API
            # 3. Send invite to customer_email
            # 4. Return event details
            
            pass
        
        except Exception as e:
            logger.error(f"[GoogleCalendar] Error creating appointment: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_available_slots(
        self,
        tenant_id: str,
        date: str,
        duration_minutes: int = 60
    ) -> List[str]:
        """
        Get all available time slots for a given date
        
        Args:
            tenant_id: Tenant ID
            date: Date in YYYY-MM-DD format
            duration_minutes: Appointment duration (default: 60 minutes)
        
        Returns:
            List of available times ["09:00", "10:00", "11:00", ...]
        """
        if not self.enabled:
            # Mock response: Return business hours (9 AM - 5 PM)
            return [f"{hour:02d}:00" for hour in range(9, 17)]
        
        try:
            # TODO: Implement actual availability calculation
            # 1. Get tenant's business hours from settings
            # 2. Query Google Calendar for busy times
            # 3. Calculate free slots based on duration
            # 4. Return available times
            
            pass
        
        except Exception as e:
            logger.error(f"[GoogleCalendar] Error getting available slots: {e}")
            return []
    
    async def configure_calendar(
        self,
        tenant_id: str,
        oauth_credentials: Dict
    ) -> bool:
        """
        Configure Google Calendar OAuth for a tenant
        
        Args:
            tenant_id: Tenant ID
            oauth_credentials: Google OAuth credentials from tenant
        
        Returns:
            Success boolean
        """
        try:
            # Store encrypted OAuth credentials in database
            await self.db.tenant_integrations.update_one(
                {"tenant_id": tenant_id, "integration": "google_calendar"},
                {
                    "$set": {
                        "credentials": oauth_credentials,  # Should be encrypted
                        "configured_at": datetime.now(timezone.utc),
                        "status": "active"
                    }
                },
                upsert=True
            )
            
            logger.info(f"[GoogleCalendar] Configured for tenant {tenant_id}")
            return True
        
        except Exception as e:
            logger.error(f"[GoogleCalendar] Configuration error: {e}")
            return False


# Singleton instance
_google_calendar_service = None


def get_google_calendar_service(db):
    """Get singleton GoogleCalendarService instance"""
    global _google_calendar_service
    
    if _google_calendar_service is None:
        _google_calendar_service = GoogleCalendarService(db)
    
    return _google_calendar_service


# Helper function for AI Agent to use
async def ai_book_appointment(
    db,
    tenant_id: str,
    customer_name: str,
    customer_email: str,
    service: str,
    preferred_date: str,
    preferred_time: Optional[str] = None
) -> Dict[str, Any]:
    """
    Helper function for AI Agent to book appointments
    
    Args:
        db: Database instance
        tenant_id: Tenant ID
        customer_name: Customer's name
        customer_email: Customer's email
        service: Service being booked
        preferred_date: Preferred date (YYYY-MM-DD or "tomorrow", "next week")
        preferred_time: Preferred time (HH:MM or "morning", "afternoon")
    
    Returns:
        {
            "success": bool,
            "appointment": {...} or None,
            "message": str,  # For AI to say to customer
            "available_slots": List[str]  # If preferred time not available
        }
    """
    try:
        calendar_service = get_google_calendar_service(db)
        
        # Parse natural language date/time
        parsed_date = _parse_date(preferred_date)
        
        if preferred_time:
            parsed_time = _parse_time(preferred_time)
            
            # Check if specific time is available
            availability = await calendar_service.check_availability(
                tenant_id=tenant_id,
                date=parsed_date,
                time_slots=[parsed_time]
            )
            
            if availability.get(parsed_time):
                # Time is available, book it
                appointment = await calendar_service.create_appointment(
                    tenant_id=tenant_id,
                    appointment_data={
                        "customer_name": customer_name,
                        "customer_email": customer_email,
                        "service": service,
                        "date": parsed_date,
                        "time": parsed_time,
                        "duration_minutes": 60
                    }
                )
                
                if appointment["success"]:
                    return {
                        "success": True,
                        "appointment": appointment,
                        "message": f"Perfect! I've booked your {service} appointment for {parsed_date} at {parsed_time}. You'll receive a confirmation email shortly.",
                        "available_slots": None
                    }
        
        # If no specific time or time unavailable, suggest available slots
        available_slots = await calendar_service.get_available_slots(
            tenant_id=tenant_id,
            date=parsed_date,
            duration_minutes=60
        )
        
        if available_slots:
            slots_str = ", ".join(available_slots[:3])  # Show first 3 slots
            return {
                "success": False,
                "appointment": None,
                "message": f"We have appointments available on {parsed_date} at: {slots_str}. Which time works best for you?",
                "available_slots": available_slots
            }
        else:
            return {
                "success": False,
                "appointment": None,
                "message": f"I'm sorry, we don't have any availability on {parsed_date}. Would another day work for you?",
                "available_slots": []
            }
    
    except Exception as e:
        logger.error(f"[GoogleCalendar] AI booking error: {e}")
        return {
            "success": False,
            "appointment": None,
            "message": "I'm having trouble accessing the calendar right now. Let me transfer you to a team member who can help.",
            "available_slots": []
        }


def _parse_date(date_str: str) -> str:
    """
    Parse natural language date to YYYY-MM-DD
    
    Args:
        date_str: "tomorrow", "next week", "2025-02-15", etc.
    
    Returns:
        Date in YYYY-MM-DD format
    """
    date_str_lower = date_str.lower()
    today = datetime.now()
    
    if "tomorrow" in date_str_lower:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "next week" in date_str_lower:
        return (today + timedelta(days=7)).strftime("%Y-%m-%d")
    elif "today" in date_str_lower:
        return today.strftime("%Y-%m-%d")
    else:
        # Assume it's already in YYYY-MM-DD format
        return date_str


def _parse_time(time_str: str) -> str:
    """
    Parse natural language time to HH:MM
    
    Args:
        time_str: "morning", "afternoon", "2pm", "14:00", etc.
    
    Returns:
        Time in HH:MM format (24-hour)
    """
    time_str_lower = time_str.lower()
    
    if "morning" in time_str_lower:
        return "09:00"
    elif "afternoon" in time_str_lower:
        return "14:00"
    elif "evening" in time_str_lower:
        return "17:00"
    elif "pm" in time_str_lower or "am" in time_str_lower:
        # Parse "2pm" -> "14:00"
        import re
        match = re.search(r'(\d{1,2})\s*(am|pm)', time_str_lower)
        if match:
            hour = int(match.group(1))
            meridiem = match.group(2)
            if meridiem == "pm" and hour != 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            return f"{hour:02d}:00"
    
    # Assume it's already in HH:MM format
    return time_str
