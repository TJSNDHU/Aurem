"""
Weather Utility for Reroots Skincare
Provides skincare-relevant weather data using OpenWeatherMap API.

Features:
- Get weather by city name or coordinates
- Determine skincare alerts (dry, sunny, rainy, freezing)
- Generate personalized skincare messages
- UV index awareness for sun protection
"""

import os
import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")


async def get_skincare_weather(
    city: str = None, 
    lat: float = None, 
    lon: float = None
) -> Dict[str, Any]:
    """
    Gets weather data and returns skincare-relevant metrics.
    
    Args:
        city: City name (e.g., "Toronto,CA", "Brampton")
        lat: Latitude (optional, overrides city)
        lon: Longitude (optional, overrides city)
        
    Returns:
        Dict with city, temp, humidity, weather, alert_type, should_notify
    """
    if not WEATHER_API_KEY:
        logger.warning("[WEATHER] WEATHER_API_KEY not set")
        return {"error": "API key not configured", "should_notify": False}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Build URL based on available location data
            if lat is not None and lon is not None:
                url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
            else:
                city = city or "Mississauga,CA"
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
            
            response = await client.get(url)
            data = response.json()
            
            # Check for API errors
            if response.status_code != 200:
                logger.warning(f"[WEATHER] API error: {data.get('message', 'Unknown error')}")
                return {
                    "error": data.get("message", "API error"),
                    "should_notify": False
                }
            
            # Extract weather data
            humidity = data["main"]["humidity"]
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            weather_main = data["weather"][0]["main"]
            weather_desc = data["weather"][0]["description"]
            city_name = data.get("name", city)
            
            # Determine skincare alert type based on conditions
            alert_type = None
            severity = "normal"
            
            # Priority 1: Extreme cold (most damaging to skin)
            if temp < -10:
                alert_type = "extreme_cold"
                severity = "high"
            elif temp < 0:
                alert_type = "freezing"
                severity = "medium"
            
            # Priority 2: Very dry conditions
            elif humidity < 25:
                alert_type = "very_dry"
                severity = "high"
            elif humidity < 35:
                alert_type = "dry"
                severity = "medium"
            
            # Priority 3: Hot and sunny (UV damage)
            elif weather_main in ["Clear", "Sunny"] and temp > 25:
                alert_type = "hot_sunny"
                severity = "high"
            elif weather_main in ["Clear", "Sunny"] and temp > 18:
                alert_type = "sunny"
                severity = "medium"
            
            # Priority 4: Hot and humid (different routine needed)
            elif temp > 28 and humidity > 70:
                alert_type = "hot_humid"
                severity = "low"
            
            # Priority 5: Rainy (humid conditions)
            elif weather_main in ["Rain", "Drizzle", "Thunderstorm"]:
                alert_type = "rainy"
                severity = "low"
            
            # Priority 6: Cold and dry (winter skin barrier stress)
            elif temp < 5 and humidity < 45:
                alert_type = "cold_dry"
                severity = "medium"
            
            result = {
                "city": city_name,
                "temp": round(temp, 1),
                "feels_like": round(feels_like, 1),
                "humidity": humidity,
                "weather": weather_main,
                "description": weather_desc,
                "alert_type": alert_type,
                "severity": severity,
                "should_notify": alert_type is not None
            }
            
            logger.info(f"[WEATHER] {city_name}: {temp}°C, {humidity}% humidity, {weather_main} → Alert: {alert_type}")
            
            return result
            
    except httpx.TimeoutException:
        logger.error("[WEATHER] API timeout")
        return {"error": "API timeout", "should_notify": False}
    except Exception as e:
        logger.error(f"[WEATHER] Error: {e}")
        return {"error": str(e), "should_notify": False}


def get_skincare_message(alert_type: str, customer_name: str = None, city: str = None) -> str:
    """
    Returns AI-ready skincare advice for weather condition.
    
    Args:
        alert_type: Type of weather alert (dry, sunny, freezing, etc.)
        customer_name: Customer's first name for personalization
        city: City name for context
        
    Returns:
        Formatted skincare message
    """
    name = f"{customer_name}, " if customer_name else ""
    location = f" in {city}" if city else ""
    
    messages = {
        # High severity alerts
        "extreme_cold": (
            f"🥶 {name}extreme cold alert{location}! Temperatures below -10°C can cause serious skin barrier damage.\n\n"
            f"Critical steps today:\n"
            f"1. Apply a thick layer of AURA-GEN Rich Cream before going outside\n"
            f"2. Cover exposed skin as much as possible\n"
            f"3. Avoid hot showers — they strip your already stressed barrier\n"
            f"4. Reapply moisturizer mid-day if possible\n\n"
            f"Your skin deserves this protection. 💛"
        ),
        
        "very_dry": (
            f"⚠️ {name}critically low humidity{location} (under 25%)! Your skin is losing moisture rapidly.\n\n"
            f"Emergency routine:\n"
            f"1. Layer your serums — TXA first, then ARC\n"
            f"2. Don't skip the Rich Cream — your barrier needs it\n"
            f"3. Consider a humidifier if you're indoors\n"
            f"4. Drink extra water today\n\n"
            f"Your skin deserves this care. 💛"
        ),
        
        "hot_sunny": (
            f"☀️ {name}strong UV alert{location}! Hot, sunny conditions mean maximum sun damage risk.\n\n"
            f"Critical protection:\n"
            f"1. SPF 50+ is non-negotiable — apply generously\n"
            f"2. Reapply every 2 hours if outdoors\n"
            f"3. Your TXA serum helps prevent sun-induced hyperpigmentation\n"
            f"4. Seek shade between 10am-4pm when possible\n\n"
            f"Your skin deserves this protection. 💛"
        ),
        
        # Medium severity alerts
        "freezing": (
            f"🥶 {name}freezing temperatures{location}! Cold air strips your skin barrier fast.\n\n"
            f"Winter routine:\n"
            f"1. The AURA-GEN Rich Cream was formulated for exactly this\n"
            f"2. Apply before going out — creates protective layer\n"
            f"3. Don't forget your lips and hands\n\n"
            f"Your skin deserves this. 💛"
        ),
        
        "dry": (
            f"⚠️ {name}low humidity{location} today. Your skin barrier needs extra support.\n\n"
            f"Hydration boost:\n"
            f"1. Layer your AURA-GEN serums for maximum hydration\n"
            f"2. The Peptide Serum locks in moisture beautifully\n"
            f"3. Consider a hydrating mask tonight\n\n"
            f"Your skin deserves this. 💛"
        ),
        
        "sunny": (
            f"☀️ {name}sunny day{location}! Don't let UV rays undo your skincare progress.\n\n"
            f"Morning routine reminder:\n"
            f"1. Apply SPF 50+ as your final step\n"
            f"2. Your TXA serum protects against hyperpigmentation\n"
            f"3. Sunglasses protect the delicate eye area too\n\n"
            f"Your skin deserves this protection. 💛"
        ),
        
        "cold_dry": (
            f"❄️ {name}cold and dry conditions{location}. Double threat to your skin barrier.\n\n"
            f"Protective routine:\n"
            f"1. Layer: TXA serum → ARC serum → Rich Cream\n"
            f"2. The ARC creates a protective barrier\n"
            f"3. Apply thicker at night for overnight repair\n\n"
            f"Your skin deserves this. 💛"
        ),
        
        # Low severity alerts
        "hot_humid": (
            f"🌡️ {name}hot and humid{location}. Your skin might feel oily today.\n\n"
            f"Adjusted routine:\n"
            f"1. You can use a lighter moisturizer or skip it\n"
            f"2. Focus on the TXA serum — brightness without heaviness\n"
            f"3. Blot with tissues instead of washing (preserves barrier)\n\n"
            f"Your skin deserves this care. 💛"
        ),
        
        "rainy": (
            f"🌧️ {name}rainy weather{location}. Humidity is your friend today!\n\n"
            f"Simplified routine:\n"
            f"1. Your skin retains more moisture naturally in humid conditions\n"
            f"2. The ARC Serum alone may be enough — lightweight recovery\n"
            f"3. Still use SPF if there's any daylight!\n\n"
            f"Your skin deserves this. 💛"
        )
    }
    
    return messages.get(alert_type, "")


def get_alert_skin_match(alert_type: str) -> list:
    """
    Returns which skin concerns benefit most from this alert type.
    Used to target alerts to relevant customers.
    
    Args:
        alert_type: Weather alert type
        
    Returns:
        List of skin concern keywords that match
    """
    matches = {
        "extreme_cold": ["dry", "sensitive", "eczema", "rosacea", "barrier"],
        "very_dry": ["dry", "dehydrated", "flaky", "sensitive", "barrier"],
        "hot_sunny": ["hyperpigmentation", "melasma", "dark spots", "aging", "wrinkles"],
        "freezing": ["dry", "sensitive", "barrier", "cracking"],
        "dry": ["dry", "dehydrated", "flaky", "dull"],
        "sunny": ["hyperpigmentation", "melasma", "dark spots", "aging", "all"],
        "cold_dry": ["dry", "sensitive", "combination", "barrier"],
        "hot_humid": ["oily", "acne", "combination", "congested"],
        "rainy": ["oily", "acne", "combination"]
    }
    
    return matches.get(alert_type, ["all"])


async def should_notify_customer(alert_type: str, customer_skin_concerns: list) -> bool:
    """
    Determines if a customer should receive this weather alert
    based on their skin concerns.
    
    Args:
        alert_type: Weather alert type
        customer_skin_concerns: List of customer's skin concerns
        
    Returns:
        True if customer should be notified
    """
    if not alert_type:
        return False
    
    matching_concerns = get_alert_skin_match(alert_type)
    
    # "all" means everyone should get this alert
    if "all" in matching_concerns:
        return True
    
    # Check if any customer concerns match
    if customer_skin_concerns:
        for concern in customer_skin_concerns:
            concern_lower = concern.lower()
            for match in matching_concerns:
                if match in concern_lower:
                    return True
    
    # Default: send to everyone for medium/high severity alerts
    high_severity = ["extreme_cold", "very_dry", "hot_sunny", "freezing", "sunny"]
    return alert_type in high_severity
