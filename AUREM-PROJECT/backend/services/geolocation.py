"""
Geolocation Service for Reroots
Provides IP-based and coordinate-based location detection.

Methods:
1. IP Geolocation (ip-api.com - free)
2. Reverse Geocoding (coordinates to city)
3. Cache results in MongoDB to reduce API calls
"""

import os
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Database reference
_db = None

# Cache duration for IP lookups (24 hours)
IP_CACHE_DURATION = timedelta(hours=24)


def set_db(database):
    """Set database reference."""
    global _db
    _db = database


async def get_location_from_ip(ip_address: str) -> Dict[str, Any]:
    """
    Get location data from IP address using ip-api.com (free, no API key needed).
    
    Args:
        ip_address: IPv4 or IPv6 address
        
    Returns:
        Dict with city, region, country, lat, lon, or error
    """
    # Skip private/local IPs
    if ip_address in ['127.0.0.1', 'localhost', '::1'] or ip_address.startswith('10.') or ip_address.startswith('192.168.'):
        return {"error": "Private IP address", "city": None}
    
    # Check cache first
    if _db is not None:
        cached = await _db.ip_location_cache.find_one({
            "ip": ip_address,
            "cached_at": {"$gte": (datetime.now(timezone.utc) - IP_CACHE_DURATION).isoformat()}
        })
        
        if cached:
            logger.debug(f"[GEO] Cache hit for IP {ip_address[:8]}...")
            return {
                "city": cached.get("city"),
                "region": cached.get("region"),
                "country": cached.get("country"),
                "lat": cached.get("lat"),
                "lon": cached.get("lon"),
                "cached": True
            }
    
    try:
        # ip-api.com is free for non-commercial use (45 requests/minute)
        url = f"http://ip-api.com/json/{ip_address}?fields=status,message,country,regionName,city,lat,lon,query"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            data = response.json()
        
        if data.get("status") == "success":
            result = {
                "city": data.get("city"),
                "region": data.get("regionName"),
                "country": data.get("country"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "ip": ip_address
            }
            
            # Cache the result
            if _db is not None and result.get("city"):
                await _db.ip_location_cache.update_one(
                    {"ip": ip_address},
                    {"$set": {
                        **result,
                        "cached_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
            
            logger.info(f"[GEO] IP {ip_address[:8]}... -> {result.get('city')}, {result.get('region')}")
            return result
        else:
            logger.warning(f"[GEO] IP lookup failed: {data.get('message')}")
            return {"error": data.get("message"), "city": None}
            
    except Exception as e:
        logger.error(f"[GEO] IP lookup error: {e}")
        return {"error": str(e), "city": None}


async def get_location_from_coordinates(lat: float, lon: float) -> Dict[str, Any]:
    """
    Reverse geocode coordinates to get city name.
    Uses OpenWeatherMap if key available, otherwise free Nominatim API.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Dict with city, region, country
    """
    api_key = os.environ.get("WEATHER_API_KEY", "")
    
    # Try OpenWeatherMap first if key is available
    if api_key:
        try:
            url = f"http://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=1&appid={api_key}"
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data and len(data) > 0:
                        location = data[0]
                        result = {
                            "city": location.get("name"),
                            "region": location.get("state"),
                            "country": location.get("country"),
                            "lat": lat,
                            "lon": lon
                        }
                        logger.info(f"[GEO] Coords ({lat:.2f}, {lon:.2f}) -> {result.get('city')} (OpenWeatherMap)")
                        return result
        except Exception as e:
            logger.warning(f"[GEO] OpenWeatherMap reverse geocoding failed: {e}, trying fallback")
    
    # Fallback to free Nominatim API
    return await _reverse_geocode_free(lat, lon)


async def _reverse_geocode_free(lat: float, lon: float) -> Dict[str, Any]:
    """
    Free reverse geocoding using OpenStreetMap Nominatim.
    """
    try:
        # Nominatim requires a custom User-Agent
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers={
                "User-Agent": "RerootsAI/1.0 (skincare advisor)"
            })
            data = response.json()
        
        address = data.get("address", {})
        
        return {
            "city": address.get("city") or address.get("town") or address.get("municipality") or address.get("village"),
            "region": address.get("state") or address.get("province"),
            "country": address.get("country"),
            "lat": lat,
            "lon": lon
        }
        
    except Exception as e:
        logger.error(f"[GEO] Free reverse geocoding error: {e}")
        return {"error": str(e), "city": None}


async def detect_and_store_location(
    session_id: str,
    ip_address: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    customer_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detect location from IP or coordinates and store in customer profile.
    
    Priority:
    1. Browser geolocation (lat/lon) - most accurate
    2. IP geolocation - automatic fallback
    
    Args:
        session_id: Chat session ID
        ip_address: Client IP address
        lat: Latitude from browser
        lon: Longitude from browser
        customer_email: Customer email if known
        
    Returns:
        Location data dict
    """
    location = None
    source = None
    
    # Priority 1: Browser geolocation
    if lat is not None and lon is not None:
        location = await get_location_from_coordinates(lat, lon)
        source = "browser_geolocation"
    
    # Priority 2: IP geolocation
    elif ip_address:
        location = await get_location_from_ip(ip_address)
        source = "ip_geolocation"
    
    if not location or not location.get("city"):
        return {"error": "Could not detect location", "city": None}
    
    location["source"] = source
    location["detected_at"] = datetime.now(timezone.utc).isoformat()
    
    # Store in session
    if _db is not None and session_id:
        await _db.reroots_chat_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "detected_city": location.get("city"),
                "detected_region": location.get("region"),
                "detected_country": location.get("country"),
                "location_source": source,
                "location_detected_at": location["detected_at"]
            }}
        )
    
    # Store in customer profile if email known
    if _db is not None and customer_email:
        await _db.reroots_customer_profiles.update_one(
            {"customer_email": customer_email},
            {"$set": {
                "detected_city": location.get("city"),
                "detected_region": location.get("region"),
                "location_source": source,
                "location_updated_at": location["detected_at"]
            }},
            upsert=True
        )
    
    logger.info(f"[GEO] Location detected for session {session_id[:16]}...: {location.get('city')} via {source}")
    
    return location


async def get_customer_location_priority(customer_email: str) -> Tuple[Optional[str], str]:
    """
    Get customer location using priority system:
    
    Priority 1: Shipping city from last order (most accurate)
    Priority 2: Detected city from IP/browser during chat
    Priority 3: Profile city (manually set)
    
    Args:
        customer_email: Customer email address
        
    Returns:
        Tuple of (city, source) or (None, "none")
    """
    if _db is None or not customer_email:
        return None, "none"
    
    # Priority 1: Shipping city from orders
    order = await _db.orders.find_one(
        {"customer_email": customer_email, "shipping_address.city": {"$exists": True}},
        {"shipping_address.city": 1},
        sort=[("created_at", -1)]  # Most recent order
    )
    
    if order and order.get("shipping_address", {}).get("city"):
        return order["shipping_address"]["city"], "shipping_address"
    
    # Priority 2: Detected city from chat sessions
    session = await _db.reroots_chat_sessions.find_one(
        {"customer_email": customer_email, "detected_city": {"$exists": True}},
        {"detected_city": 1},
        sort=[("created_at", -1)]
    )
    
    if session and session.get("detected_city"):
        return session["detected_city"], "ip_detection"
    
    # Priority 3: Profile city
    profile = await _db.reroots_customer_profiles.find_one(
        {"customer_email": customer_email},
        {"detected_city": 1, "city": 1}
    )
    
    if profile:
        city = profile.get("city") or profile.get("detected_city")
        if city:
            return city, "profile"
    
    return None, "none"
