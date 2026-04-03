"""
AUREM Commercial Platform - Natural Language Date Parser
"The Universal Brain" for Date/Time Understanding

Provides intelligent date parsing across all AUREM channels:
- Voice (Vapi): "book me for next Tuesday at 3pm"
- WhatsApp: "can I come in tomorrow morning?"
- Web Chat: "schedule something end of month"

Features:
1. Universal Parsing - One service for all channels
2. Auto-Timezone - Mississauga/Eastern default with user overrides
3. Relative Dates - "tomorrow", "next week", "in 3 days"
4. Natural Language - "first thing Monday morning", "end of month"
5. Colloquial Support - "noon", "midnight", "lunch time"
6. Tool Integration - Auto-populates calendar/appointment tools

Business Timezone: America/Toronto (Mississauga/Eastern)
"""

import logging
from datetime import datetime, timedelta, time
from typing import Optional, Dict, Any, List, Tuple, Union
import dateparser
import pytz
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Default business timezone (Mississauga/Eastern)
DEFAULT_TIMEZONE = "America/Toronto"

# Business hours for "first thing", "end of day", etc.
BUSINESS_HOURS = {
    "start": time(9, 0),   # 9:00 AM
    "end": time(17, 0),    # 5:00 PM
    "lunch": time(12, 0),  # 12:00 PM (noon)
}

# Colloquial time mappings
COLLOQUIAL_TIMES = {
    "first thing": time(9, 0),
    "first thing in the morning": time(9, 0),
    "early morning": time(8, 0),
    "morning": time(10, 0),
    "mid-morning": time(10, 30),
    "late morning": time(11, 0),
    "noon": time(12, 0),
    "lunch": time(12, 0),
    "lunch time": time(12, 0),
    "afternoon": time(14, 0),
    "early afternoon": time(13, 0),
    "mid-afternoon": time(15, 0),
    "late afternoon": time(16, 0),
    "end of day": time(17, 0),
    "evening": time(18, 0),
    "night": time(20, 0),
    "midnight": time(0, 0),
}

# Relative period mappings
RELATIVE_PERIODS = {
    "end of week": lambda now: now + timedelta(days=(4 - now.weekday()) % 7),  # Friday
    "end of month": lambda now: (now.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
    "beginning of month": lambda now: now.replace(day=1),
    "next month": lambda now: (now.replace(day=1) + timedelta(days=32)).replace(day=1),
    "end of year": lambda now: now.replace(month=12, day=31),
}


class DateConfidence(str, Enum):
    """Confidence level of parsed date"""
    HIGH = "high"        # Exact date/time specified
    MEDIUM = "medium"    # Relative date with some ambiguity
    LOW = "low"          # Colloquial/vague reference
    NONE = "none"        # Could not parse


@dataclass
class ParsedDate:
    """Result of date parsing"""
    datetime: Optional[datetime]
    original_text: str
    confidence: DateConfidence
    timezone: str
    is_time_specified: bool
    is_date_specified: bool
    suggested_alternatives: List[datetime] = None
    parse_details: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "datetime": self.datetime.isoformat() if self.datetime else None,
            "date": self.datetime.strftime("%Y-%m-%d") if self.datetime else None,
            "time": self.datetime.strftime("%H:%M") if self.datetime else None,
            "original_text": self.original_text,
            "confidence": self.confidence.value,
            "timezone": self.timezone,
            "is_time_specified": self.is_time_specified,
            "is_date_specified": self.is_date_specified,
            "suggested_alternatives": [
                dt.isoformat() for dt in (self.suggested_alternatives or [])
            ],
            "human_readable": self._format_human_readable() if self.datetime else None
        }
    
    def _format_human_readable(self) -> str:
        if not self.datetime:
            return None
        
        now = datetime.now(pytz.timezone(self.timezone))
        dt = self.datetime
        
        # Check if it's today/tomorrow
        if dt.date() == now.date():
            day_str = "today"
        elif dt.date() == (now + timedelta(days=1)).date():
            day_str = "tomorrow"
        elif dt.date() == (now - timedelta(days=1)).date():
            day_str = "yesterday"
        else:
            day_str = dt.strftime("%A, %B %d")
        
        time_str = dt.strftime("%I:%M %p").lstrip("0")
        return f"{day_str} at {time_str}"


# ═══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL DATE PARSER
# ═══════════════════════════════════════════════════════════════════════════════

class AuremDateParser:
    """
    Universal Natural Language Date Parser for AUREM
    
    Handles date parsing from:
    - Voice transcriptions (Vapi)
    - WhatsApp messages
    - Web chat inputs
    - API requests
    
    Example inputs:
    - "next Tuesday at 3pm"
    - "tomorrow morning"
    - "in 3 days"
    - "end of month"
    - "first thing Monday"
    - "March 15th at noon"
    """
    
    def __init__(self, default_timezone: str = DEFAULT_TIMEZONE):
        self.default_timezone = default_timezone
        self.tz = pytz.timezone(default_timezone)
        
        # dateparser settings optimized for conversational input
        self.parser_settings = {
            "TIMEZONE": default_timezone,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",  # "tomorrow" means next, not past
            "PREFER_DAY_OF_MONTH": "first",
            "RELATIVE_BASE": datetime.now(self.tz),
        }
    
    def parse(
        self,
        text: str,
        user_timezone: Optional[str] = None,
        reference_date: Optional[datetime] = None
    ) -> ParsedDate:
        """
        Parse natural language date/time from text.
        
        Args:
            text: Natural language date string
            user_timezone: Override timezone (e.g., "America/New_York")
            reference_date: Base date for relative calculations
            
        Returns:
            ParsedDate with parsed datetime and metadata
        """
        if not text or not text.strip():
            return ParsedDate(
                datetime=None,
                original_text=text or "",
                confidence=DateConfidence.NONE,
                timezone=user_timezone or self.default_timezone,
                is_time_specified=False,
                is_date_specified=False
            )
        
        # Normalize input
        text_lower = text.lower().strip()
        tz = pytz.timezone(user_timezone) if user_timezone else self.tz
        now = reference_date or datetime.now(tz)
        
        # Update parser settings with current reference
        settings = {**self.parser_settings}
        settings["TIMEZONE"] = user_timezone or self.default_timezone
        settings["RELATIVE_BASE"] = now
        
        # Try colloquial patterns first
        parsed_dt, confidence, time_specified = self._try_colloquial_parse(text_lower, now, tz)
        
        if parsed_dt:
            return ParsedDate(
                datetime=parsed_dt,
                original_text=text,
                confidence=confidence,
                timezone=str(tz),
                is_time_specified=time_specified,
                is_date_specified=True,
                suggested_alternatives=self._generate_alternatives(parsed_dt, tz)
            )
        
        # Try day + time combination (e.g., "next Tuesday at 3pm")
        parsed_dt, confidence, time_specified = self._try_day_time_parse(text_lower, now, tz, settings)
        
        if parsed_dt:
            return ParsedDate(
                datetime=parsed_dt,
                original_text=text,
                confidence=confidence,
                timezone=str(tz),
                is_time_specified=time_specified,
                is_date_specified=True,
                suggested_alternatives=self._generate_alternatives(parsed_dt, tz)
            )
        
        # Try relative period patterns
        parsed_dt, confidence = self._try_relative_period_parse(text_lower, now, tz)
        
        if parsed_dt:
            return ParsedDate(
                datetime=parsed_dt,
                original_text=text,
                confidence=confidence,
                timezone=str(tz),
                is_time_specified=False,
                is_date_specified=True,
                suggested_alternatives=self._generate_alternatives(parsed_dt, tz)
            )
        
        # Fall back to dateparser library
        try:
            parsed = dateparser.parse(text, settings=settings)
            
            if parsed:
                # Ensure timezone awareness
                if parsed.tzinfo is None:
                    parsed = tz.localize(parsed)
                
                # Detect if time was specified
                time_specified = self._has_time_specification(text_lower)
                
                # If no time specified, default to business hours
                if not time_specified:
                    parsed = parsed.replace(
                        hour=BUSINESS_HOURS["start"].hour,
                        minute=BUSINESS_HOURS["start"].minute
                    )
                
                # Determine confidence
                confidence = self._assess_confidence(text_lower, parsed, now)
                
                return ParsedDate(
                    datetime=parsed,
                    original_text=text,
                    confidence=confidence,
                    timezone=str(tz),
                    is_time_specified=time_specified,
                    is_date_specified=True,
                    suggested_alternatives=self._generate_alternatives(parsed, tz)
                )
                
        except Exception as e:
            logger.warning(f"Date parsing failed for '{text}': {e}")
        
        # Could not parse
        return ParsedDate(
            datetime=None,
            original_text=text,
            confidence=DateConfidence.NONE,
            timezone=str(tz),
            is_time_specified=False,
            is_date_specified=False
        )
    
    def _try_colloquial_parse(
        self,
        text: str,
        now: datetime,
        tz: pytz.timezone
    ) -> Tuple[Optional[datetime], DateConfidence, bool]:
        """Try to parse colloquial time expressions"""
        
        # Check for colloquial time phrases
        for phrase, time_val in COLLOQUIAL_TIMES.items():
            if phrase in text:
                # Extract date part (if any)
                date_part = text.replace(phrase, "").strip()
                
                if date_part:
                    # Parse the date part
                    date_parsed = dateparser.parse(date_part, settings={
                        "TIMEZONE": str(tz),
                        "PREFER_DATES_FROM": "future",
                        "RELATIVE_BASE": now
                    })
                    if date_parsed:
                        result = date_parsed.replace(
                            hour=time_val.hour,
                            minute=time_val.minute
                        )
                        if result.tzinfo is None:
                            result = tz.localize(result)
                        return result, DateConfidence.MEDIUM, True
                else:
                    # Time only, assume today or tomorrow
                    result = now.replace(
                        hour=time_val.hour,
                        minute=time_val.minute,
                        second=0,
                        microsecond=0
                    )
                    # If time has passed today, assume tomorrow
                    if result <= now:
                        result += timedelta(days=1)
                    return result, DateConfidence.MEDIUM, True
        
        return None, DateConfidence.NONE, False
    
    def _try_day_time_parse(
        self,
        text: str,
        now: datetime,
        tz: pytz.timezone,
        settings: Dict
    ) -> Tuple[Optional[datetime], DateConfidence, bool]:
        """
        Try to parse day + time combinations that dateparser struggles with.
        
        Examples:
        - "next Tuesday at 3pm"
        - "this Friday at 2:30pm"
        - "tomorrow at noon"
        """
        import re
        
        # Pattern: [next/this]? [day] at [time]
        day_pattern = r"(next\s+|this\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today)"
        time_pattern = r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?|at\s+(noon|midnight)"
        
        day_match = re.search(day_pattern, text)
        time_match = re.search(time_pattern, text)
        
        if day_match:
            prefix = day_match.group(1)  # "next " or "this " or None
            day_name = day_match.group(2)  # monday, tuesday, etc.
            
            # Parse the day part - strip "next"/"this" which confuse dateparser
            day_parsed = dateparser.parse(day_name, settings=settings)
            
            if day_parsed:
                # If "next" prefix, ensure we get next week's occurrence
                if prefix and "next" in prefix.lower():
                    # If the parsed date is today or earlier this week, add 7 days
                    days_until = (day_parsed.date() - now.date()).days
                    if days_until <= 0:
                        day_parsed = day_parsed + timedelta(days=7)
                    elif days_until < 7:
                        # "next Tuesday" when today is Monday should be 8 days, not 1
                        day_parsed = day_parsed + timedelta(days=7)
                
                hour = 9  # Default to 9am
                minute = 0
                time_specified = False
                
                if time_match:
                    time_specified = True
                    groups = time_match.groups()
                    
                    if groups[3]:  # noon or midnight
                        hour = 12 if groups[3] == "noon" else 0
                    elif groups[0]:  # numeric time
                        hour = int(groups[0])
                        minute = int(groups[1]) if groups[1] else 0
                        meridiem = groups[2].lower().replace(".", "") if groups[2] else None
                        
                        if meridiem:
                            if meridiem == "pm" and hour != 12:
                                hour += 12
                            elif meridiem == "am" and hour == 12:
                                hour = 0
                        elif hour <= 7:  # Assume PM for hours 1-7 without meridiem
                            hour += 12
                
                result = day_parsed.replace(
                    hour=hour,
                    minute=minute,
                    second=0,
                    microsecond=0
                )
                
                if result.tzinfo is None:
                    result = tz.localize(result)
                
                confidence = DateConfidence.HIGH if time_specified else DateConfidence.MEDIUM
                return result, confidence, time_specified
        
        return None, DateConfidence.NONE, False
    
    def _try_relative_period_parse(
        self,
        text: str,
        now: datetime,
        tz: pytz.timezone
    ) -> Tuple[Optional[datetime], DateConfidence]:
        """Try to parse relative period expressions"""
        
        for phrase, calc_func in RELATIVE_PERIODS.items():
            if phrase in text:
                result = calc_func(now)
                if isinstance(result, datetime):
                    if result.tzinfo is None:
                        result = tz.localize(result)
                    # Set to business hours
                    result = result.replace(
                        hour=BUSINESS_HOURS["start"].hour,
                        minute=BUSINESS_HOURS["start"].minute
                    )
                    return result, DateConfidence.LOW
        
        return None, DateConfidence.NONE
    
    def _has_time_specification(self, text: str) -> bool:
        """Check if text contains a time specification"""
        time_indicators = [
            "am", "pm", "a.m.", "p.m.",
            "o'clock", "oclock",
            ":", "noon", "midnight",
            "morning", "afternoon", "evening", "night",
            "first thing", "end of day", "lunch"
        ]
        return any(ind in text for ind in time_indicators)
    
    def _assess_confidence(
        self,
        text: str,
        parsed: datetime,
        now: datetime
    ) -> DateConfidence:
        """Assess confidence level of parsed date"""
        
        # High confidence: specific date and time mentioned
        has_specific_date = any(x in text for x in [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
            "/", "-", "st", "nd", "rd", "th"
        ])
        has_specific_time = ":" in text or "am" in text or "pm" in text
        
        if has_specific_date and has_specific_time:
            return DateConfidence.HIGH
        
        # Medium confidence: relative date with time
        relative_terms = ["tomorrow", "today", "monday", "tuesday", "wednesday",
                         "thursday", "friday", "saturday", "sunday", "next", "this"]
        has_relative = any(term in text for term in relative_terms)
        
        if has_relative and (has_specific_time or self._has_time_specification(text)):
            return DateConfidence.MEDIUM
        
        if has_relative or has_specific_date:
            return DateConfidence.MEDIUM
        
        # Low confidence: vague expressions
        return DateConfidence.LOW
    
    def _generate_alternatives(
        self,
        parsed: datetime,
        tz: pytz.timezone,
        count: int = 3
    ) -> List[datetime]:
        """Generate alternative time slots"""
        alternatives = []
        
        # Same day, different hours
        for hour_offset in [1, 2, -1]:
            alt = parsed + timedelta(hours=hour_offset)
            if BUSINESS_HOURS["start"].hour <= alt.hour <= BUSINESS_HOURS["end"].hour:
                alternatives.append(alt)
        
        # Next day, same time
        next_day = parsed + timedelta(days=1)
        alternatives.append(next_day)
        
        return alternatives[:count]
    
    def extract_dates_from_message(
        self,
        message: str,
        user_timezone: Optional[str] = None
    ) -> List[ParsedDate]:
        """
        Extract all date references from a longer message.
        
        Useful for messages like:
        "I can do Tuesday at 2pm or Thursday morning"
        """
        results = []
        
        # Simple approach: split by "or", "and", commas
        parts = message.lower().replace(" or ", "|").replace(" and ", "|").replace(",", "|").split("|")
        
        for part in parts:
            part = part.strip()
            if part:
                parsed = self.parse(part, user_timezone)
                if parsed.datetime and parsed.confidence != DateConfidence.NONE:
                    results.append(parsed)
        
        # Remove duplicates (same datetime)
        seen = set()
        unique_results = []
        for r in results:
            if r.datetime and r.datetime.isoformat() not in seen:
                seen.add(r.datetime.isoformat())
                unique_results.append(r)
        
        return unique_results
    
    def format_for_confirmation(self, parsed: ParsedDate) -> str:
        """
        Format parsed date for voice/chat confirmation.
        
        Returns a natural language string like:
        "Tuesday, March 15th at 2:00 PM"
        """
        if not parsed.datetime:
            return "I couldn't understand that date. Could you please specify?"
        
        dt = parsed.datetime
        
        # Format day
        day_suffix = self._get_day_suffix(dt.day)
        day_str = dt.strftime(f"%A, %B {dt.day}{day_suffix}")
        
        # Format time
        time_str = dt.strftime("%I:%M %p").lstrip("0")
        
        return f"{day_str} at {time_str}"
    
    def _get_day_suffix(self, day: int) -> str:
        if 11 <= day <= 13:
            return "th"
        return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_date_parser: Optional[AuremDateParser] = None


def get_date_parser(timezone: str = DEFAULT_TIMEZONE) -> AuremDateParser:
    """Get or create the Date Parser singleton"""
    global _date_parser
    if _date_parser is None:
        _date_parser = AuremDateParser(timezone)
    return _date_parser


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_date(text: str, timezone: str = DEFAULT_TIMEZONE) -> ParsedDate:
    """Quick parse function for simple use cases"""
    return get_date_parser(timezone).parse(text)


def parse_date_for_tool(
    text: str,
    timezone: str = DEFAULT_TIMEZONE
) -> Dict[str, Any]:
    """
    Parse date and return in format ready for Action Engine tools.
    
    Returns dict with:
    - date: "YYYY-MM-DD"
    - time: "HH:MM"
    - datetime_iso: Full ISO string
    - confidence: Parsing confidence
    """
    result = parse_date(text, timezone)
    
    if not result.datetime:
        return {
            "success": False,
            "error": "Could not parse date from input",
            "original_text": text,
            "clarification_needed": True
        }
    
    return {
        "success": True,
        "date": result.datetime.strftime("%Y-%m-%d"),
        "time": result.datetime.strftime("%H:%M"),
        "datetime_iso": result.datetime.isoformat(),
        "confidence": result.confidence.value,
        "human_readable": result._format_human_readable(),
        "timezone": result.timezone,
        "clarification_needed": result.confidence == DateConfidence.LOW
    }
