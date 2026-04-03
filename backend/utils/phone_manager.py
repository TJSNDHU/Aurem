"""
Telnyx Global Phone Number Manager
═══════════════════════════════════════════════════════════════════
Provision, manage, and route global phone numbers for voice AI.

Features:
- Provision phone numbers in 13+ countries
- Language-aware voice greetings per caller country
- TeXML webhook routing to voice agent WebSocket
- Admin management (provision, list, release)
- Mock mode when TELNYX_API_KEY is not configured

Supported Countries:
CA, US, GB, FR, DE, AU, IN, AE, SA, SG, JP, BR, MX
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Database reference
_db = None

def set_db(database):
    """Set database reference."""
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# Supported countries with phone number provisioning
SUPPORTED_COUNTRIES = {
    "CA": {"name": "Canada", "language": "en", "area_codes": ["416", "647", "905", "289"]},
    "US": {"name": "United States", "language": "en", "area_codes": ["212", "310", "415", "305"]},
    "GB": {"name": "United Kingdom", "language": "en", "area_codes": ["20", "121", "131"]},
    "FR": {"name": "France", "language": "fr", "area_codes": ["1", "4", "6"]},
    "DE": {"name": "Germany", "language": "de", "area_codes": ["30", "89", "40"]},
    "AU": {"name": "Australia", "language": "en", "area_codes": ["2", "3", "7"]},
    "IN": {"name": "India", "language": "hi", "area_codes": ["22", "11", "80"]},
    "AE": {"name": "United Arab Emirates", "language": "ar", "area_codes": ["4", "2"]},
    "SA": {"name": "Saudi Arabia", "language": "ar", "area_codes": ["11", "12"]},
    "SG": {"name": "Singapore", "language": "en", "area_codes": ["6"]},
    "JP": {"name": "Japan", "language": "ja", "area_codes": ["3", "6", "52"]},
    "BR": {"name": "Brazil", "language": "pt", "area_codes": ["11", "21", "31"]},
    "MX": {"name": "Mexico", "language": "es", "area_codes": ["55", "33", "81"]},
}

# Country code to ISO mapping
COUNTRY_CODE_PREFIX = {
    "CA": "+1",
    "US": "+1",
    "GB": "+44",
    "FR": "+33",
    "DE": "+49",
    "AU": "+61",
    "IN": "+91",
    "AE": "+971",
    "SA": "+966",
    "SG": "+65",
    "JP": "+81",
    "BR": "+55",
    "MX": "+52",
}

# Monthly costs per country (USD estimate)
MONTHLY_COSTS = {
    "CA": 1.50,
    "US": 1.00,
    "GB": 2.50,
    "FR": 3.00,
    "DE": 3.00,
    "AU": 4.00,
    "IN": 5.00,
    "AE": 8.00,
    "SA": 10.00,
    "SG": 4.00,
    "JP": 6.00,
    "BR": 5.00,
    "MX": 3.50,
}


# ═══════════════════════════════════════════════════════════════════
# MOCK PROVISIONING (When TELNYX_API_KEY not set)
# ═══════════════════════════════════════════════════════════════════

def _generate_mock_number(country_code: str) -> Dict[str, Any]:
    """Generate a mock phone number for testing."""
    import random
    
    prefix = COUNTRY_CODE_PREFIX.get(country_code.upper(), "+1")
    area_codes = SUPPORTED_COUNTRIES.get(country_code.upper(), {}).get("area_codes", ["555"])
    area = random.choice(area_codes)
    
    # Generate random last 7 digits
    last_digits = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    
    return {
        "phone_number": f"{prefix}-{area}-{last_digits[:3]}-{last_digits[3:]}",
        "country": country_code.upper(),
        "status": "mocked — add TELNYX_API_KEY to activate real provisioning",
        "monthly_cost_usd": MONTHLY_COSTS.get(country_code.upper(), 2.00),
        "telnyx_id": f"mock_{country_code.lower()}_{datetime.now(timezone.utc).timestamp()}",
        "is_mock": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }


# ═══════════════════════════════════════════════════════════════════
# PHONE NUMBER PROVISIONING
# ═══════════════════════════════════════════════════════════════════

async def provision_number(
    country_code: str,
    tenant_id: str = "reroots",
    voice_webhook_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Provision a new phone number in the specified country.
    
    Args:
        country_code: ISO 2-letter country code (CA, US, GB, etc.)
        tenant_id: Platform tenant identifier
        voice_webhook_url: Optional webhook URL for incoming calls
    
    Returns:
        Dict with phone number details or error
    """
    country_code = country_code.upper()
    
    # Validate country
    if country_code not in SUPPORTED_COUNTRIES:
        return {
            "success": False,
            "error": f"Country {country_code} not supported. Supported: {list(SUPPORTED_COUNTRIES.keys())}"
        }
    
    # Check for Telnyx API key
    telnyx_api_key = os.environ.get("TELNYX_API_KEY")
    
    if not telnyx_api_key:
        # Return mock response
        logger.info(f"[PHONE] Mocking phone provision for {country_code} (no TELNYX_API_KEY)")
        mock_number = _generate_mock_number(country_code)
        
        # Store in database
        if _db is not None:
            await _db.platform_phone_numbers.insert_one({
                "tenant_id": tenant_id,
                **mock_number
            })
        
        return {
            "success": True,
            **mock_number
        }
    
    # Real Telnyx provisioning
    try:
        import telnyx
        telnyx.api_key = telnyx_api_key
        
        # Search for available numbers
        country_info = SUPPORTED_COUNTRIES[country_code]
        
        # Use Telnyx Number Orders API
        available = telnyx.NumberSearch.list(
            filter={
                "country_code": country_code.lower(),
                "limit": 5
            }
        )
        
        if not available.data:
            return {
                "success": False,
                "error": f"No available numbers in {country_info['name']}"
            }
        
        # Order the first available number
        number_to_order = available.data[0]
        
        order = telnyx.NumberOrder.create(
            phone_numbers=[{"phone_number": number_to_order.phone_number}]
        )
        
        # Configure the number for voice
        if voice_webhook_url and order.phone_numbers:
            phone_number_id = order.phone_numbers[0].id
            telnyx.PhoneNumber.update(
                phone_number_id,
                connection_id=os.environ.get("TELNYX_APP_ID"),
                enable_caller_id=True
            )
        
        result = {
            "success": True,
            "phone_number": number_to_order.phone_number,
            "country": country_code,
            "status": "active",
            "monthly_cost_usd": MONTHLY_COSTS.get(country_code, 2.00),
            "telnyx_id": order.id,
            "is_mock": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Store in database
        if _db is not None:
            await _db.platform_phone_numbers.insert_one({
                "tenant_id": tenant_id,
                **result
            })
        
        logger.info(f"[PHONE] Provisioned {result['phone_number']} in {country_code}")
        return result
        
    except Exception as e:
        logger.error(f"[PHONE] Telnyx provisioning error: {e}")
        return {
            "success": False,
            "error": f"Provisioning failed: {str(e)}"
        }


async def list_numbers(tenant_id: str = "reroots") -> Dict[str, Any]:
    """
    List all phone numbers for a tenant.
    
    Args:
        tenant_id: Platform tenant identifier
    
    Returns:
        Dict with list of phone numbers
    """
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    try:
        numbers = await _db.platform_phone_numbers.find(
            {"tenant_id": tenant_id},
            {"_id": 0}
        ).to_list(100)
        
        # Group by country
        by_country = {}
        for num in numbers:
            country = num.get("country", "UNKNOWN")
            if country not in by_country:
                by_country[country] = []
            by_country[country].append(num)
        
        total_monthly_cost = sum(n.get("monthly_cost_usd", 0) for n in numbers)
        
        return {
            "success": True,
            "count": len(numbers),
            "numbers": numbers,
            "by_country": by_country,
            "total_monthly_cost_usd": round(total_monthly_cost, 2)
        }
        
    except Exception as e:
        logger.error(f"[PHONE] List numbers error: {e}")
        return {"success": False, "error": str(e)}


async def release_number(
    phone_number: str,
    tenant_id: str = "reroots"
) -> Dict[str, Any]:
    """
    Release/delete a phone number.
    
    Args:
        phone_number: The phone number to release
        tenant_id: Platform tenant identifier
    
    Returns:
        Dict with release status
    """
    if _db is None:
        return {"success": False, "error": "Database not available"}
    
    try:
        # Find the number
        number_doc = await _db.platform_phone_numbers.find_one({
            "tenant_id": tenant_id,
            "phone_number": phone_number
        })
        
        if not number_doc:
            return {"success": False, "error": "Phone number not found"}
        
        # If real Telnyx number, release via API
        if not number_doc.get("is_mock") and os.environ.get("TELNYX_API_KEY"):
            try:
                import telnyx
                telnyx.api_key = os.environ.get("TELNYX_API_KEY")
                
                # Find and delete the number
                telnyx_id = number_doc.get("telnyx_id")
                if telnyx_id:
                    telnyx.NumberOrder.delete(telnyx_id)
            except Exception as e:
                logger.warning(f"[PHONE] Telnyx release error (continuing): {e}")
        
        # Remove from database
        await _db.platform_phone_numbers.delete_one({
            "tenant_id": tenant_id,
            "phone_number": phone_number
        })
        
        logger.info(f"[PHONE] Released {phone_number}")
        
        return {
            "success": True,
            "message": f"Released {phone_number}",
            "country": number_doc.get("country")
        }
        
    except Exception as e:
        logger.error(f"[PHONE] Release number error: {e}")
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# TEXML WEBHOOK HANDLING
# ═══════════════════════════════════════════════════════════════════

def generate_texml_response(
    caller_country: str,
    voice_agent_ws_url: str,
    brand_name: str = "Reroots"
) -> str:
    """
    Generate TeXML response for inbound calls.
    
    Args:
        caller_country: Detected country of caller
        voice_agent_ws_url: WebSocket URL for voice agent
        brand_name: Brand name for greeting
    
    Returns:
        TeXML string for Telnyx to process
    """
    from utils.language import get_voice_greeting, get_language_for_country
    
    # Get language for caller's country
    language = get_language_for_country(caller_country)
    greeting = get_voice_greeting(language, brand_name)
    
    # Map language to Telnyx voice
    voice_map = {
        "en": "Polly.Joanna",
        "es": "Polly.Penelope",
        "fr": "Polly.Celine",
        "de": "Polly.Vicki",
        "ar": "Polly.Zeina",
        "hi": "Polly.Aditi",
        "pt": "Polly.Vitoria",
        "ja": "Polly.Mizuki",
        "zh": "Polly.Zhiyu",
        "ko": "Polly.Seoyeon",
    }
    
    voice = voice_map.get(language, "Polly.Joanna")
    
    texml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}">{greeting}</Say>
    <Connect>
        <Stream url="{voice_agent_ws_url}" />
    </Connect>
</Response>"""
    
    return texml


def detect_country_from_number(phone_number: str) -> str:
    """
    Detect country from phone number prefix.
    
    Args:
        phone_number: E.164 formatted phone number
    
    Returns:
        ISO 2-letter country code
    """
    # Clean the number
    clean = phone_number.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    
    # Check prefixes (longest match first)
    prefix_map = {
        "+1": "US",  # Default to US for NANP, will refine later
        "+44": "GB",
        "+33": "FR",
        "+49": "DE",
        "+61": "AU",
        "+91": "IN",
        "+971": "AE",
        "+966": "SA",
        "+65": "SG",
        "+81": "JP",
        "+55": "BR",
        "+52": "MX",
    }
    
    for prefix, country in sorted(prefix_map.items(), key=lambda x: -len(x[0])):
        if clean.startswith(prefix):
            # For +1, check if it's Canada based on area code
            if prefix == "+1" and len(clean) >= 5:
                area_code = clean[2:5]
                canadian_area_codes = ["204", "226", "236", "249", "250", "289", "306", "343", "365", 
                                       "387", "403", "416", "418", "431", "437", "438", "450", "506",
                                       "514", "519", "548", "579", "581", "587", "604", "613", "639",
                                       "647", "672", "705", "709", "778", "780", "782", "807", "819",
                                       "825", "867", "873", "902", "905"]
                if area_code in canadian_area_codes:
                    return "CA"
            return country
    
    return "US"  # Default


# ═══════════════════════════════════════════════════════════════════
# SUPPORTED COUNTRIES API
# ═══════════════════════════════════════════════════════════════════

def get_supported_countries() -> List[Dict[str, Any]]:
    """
    Get list of supported countries for phone provisioning.
    
    Returns:
        List of country dicts with code, name, language, cost
    """
    countries = []
    for code, info in SUPPORTED_COUNTRIES.items():
        countries.append({
            "code": code,
            "name": info["name"],
            "language": info["language"],
            "phone_prefix": COUNTRY_CODE_PREFIX.get(code, ""),
            "monthly_cost_usd": MONTHLY_COSTS.get(code, 2.00)
        })
    
    return sorted(countries, key=lambda x: x["name"])
