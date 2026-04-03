"""
Weather Skincare AI - Weather-Based Product Recommendations
Fetches local weather → Analyzes skin impact → Recommends products from catalog
Uses FREE Open-Meteo API for weather data
"""

import os
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/weather-skincare", tags=["Weather Skincare"])

# MongoDB reference
_db = None

def set_db(database):
    """Set database reference"""
    global _db
    _db = database

# Open-Meteo API (FREE, no API key needed)
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"

# LLM for AI recommendations
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")


# ═══════════════════════════════════════════════════════════════════════════════
# WEATHER CONDITION MAPPINGS
# ═══════════════════════════════════════════════════════════════════════════════

WEATHER_SKIN_IMPACTS = {
    "hot_humid": {
        "conditions": "Hot and humid",
        "skin_effects": [
            "Increased oil production",
            "Clogged pores risk",
            "Sweat-induced irritation",
            "Dehydration despite humidity"
        ],
        "recommendations": [
            "Lightweight, oil-free products",
            "Gel-based moisturizers",
            "Mattifying serums",
            "Gentle cleansers",
            "SPF (non-greasy)"
        ],
        "ingredients_to_seek": ["niacinamide", "hyaluronic acid", "salicylic acid", "zinc"],
        "ingredients_to_avoid": ["heavy oils", "thick creams", "occlusive products"]
    },
    "hot_dry": {
        "conditions": "Hot and dry",
        "skin_effects": [
            "Severe dehydration",
            "Increased sensitivity",
            "Accelerated aging from UV",
            "Compromised barrier"
        ],
        "recommendations": [
            "Hydrating serums",
            "Lightweight but hydrating moisturizers",
            "High SPF protection",
            "Antioxidant serums",
            "Barrier repair products"
        ],
        "ingredients_to_seek": ["hyaluronic acid", "vitamin C", "vitamin E", "ceramides", "PDRN"],
        "ingredients_to_avoid": ["alcohol-based products", "harsh exfoliants"]
    },
    "cold_dry": {
        "conditions": "Cold and dry",
        "skin_effects": [
            "Dryness and flaking",
            "Cracked skin",
            "Redness and irritation",
            "Weakened barrier"
        ],
        "recommendations": [
            "Rich, nourishing creams",
            "Barrier repair products",
            "Gentle, hydrating cleansers",
            "Facial oils",
            "Intensive overnight masks"
        ],
        "ingredients_to_seek": ["ceramides", "squalane", "shea butter", "PDRN", "peptides"],
        "ingredients_to_avoid": ["foaming cleansers", "retinoids (reduce frequency)", "AHAs"]
    },
    "cold_humid": {
        "conditions": "Cold and humid",
        "skin_effects": [
            "Dullness",
            "Congestion",
            "Uneven texture",
            "Slower cell turnover"
        ],
        "recommendations": [
            "Balanced moisturizers",
            "Gentle exfoliants",
            "Brightening serums",
            "Circulation-boosting products"
        ],
        "ingredients_to_seek": ["vitamin C", "TXA", "AHAs", "peptides"],
        "ingredients_to_avoid": ["heavy occlusives"]
    },
    "high_uv": {
        "conditions": "High UV index",
        "skin_effects": [
            "Sun damage risk",
            "Hyperpigmentation",
            "Premature aging",
            "DNA damage"
        ],
        "recommendations": [
            "Broad-spectrum SPF 50+",
            "Antioxidant serums (AM)",
            "DNA repair products",
            "After-sun soothing care"
        ],
        "ingredients_to_seek": ["vitamin C", "vitamin E", "niacinamide", "PDRN", "centella"],
        "ingredients_to_avoid": ["photosensitizing ingredients", "retinoids (AM)"]
    },
    "windy": {
        "conditions": "Windy conditions",
        "skin_effects": [
            "Moisture loss",
            "Chapping",
            "Barrier damage",
            "Sensitivity"
        ],
        "recommendations": [
            "Barrier-strengthening products",
            "Occlusive moisturizers",
            "Lip care",
            "Protective serums"
        ],
        "ingredients_to_seek": ["ceramides", "squalane", "petrolatum", "shea butter"],
        "ingredients_to_avoid": ["light lotions only"]
    },
    "pollution_high": {
        "conditions": "High pollution levels",
        "skin_effects": [
            "Oxidative stress",
            "Clogged pores",
            "Dullness",
            "Accelerated aging"
        ],
        "recommendations": [
            "Double cleansing",
            "Antioxidant-rich products",
            "Barrier protection",
            "Detoxifying masks"
        ],
        "ingredients_to_seek": ["vitamin C", "vitamin E", "niacinamide", "green tea", "resveratrol"],
        "ingredients_to_avoid": []
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class LocationRequest(BaseModel):
    latitude: float = Field(..., description="User latitude")
    longitude: float = Field(..., description="User longitude")
    city: Optional[str] = Field(None, description="City name (optional)")


class CityRequest(BaseModel):
    city: str = Field(..., description="City name")
    country: Optional[str] = Field(None, description="Country code (e.g., CA, US)")


class WeatherSkinResponse(BaseModel):
    location: Dict[str, Any]
    weather: Dict[str, Any]
    skin_analysis: Dict[str, Any]
    product_recommendations: List[Dict[str, Any]]
    routine_tips: List[str]
    generated_at: str


# ═══════════════════════════════════════════════════════════════════════════════
# WEATHER FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

async def geocode_city(city: str, country: Optional[str] = None) -> Optional[Dict]:
    """Convert city name to coordinates"""
    try:
        params = {"name": city, "count": 1, "language": "en"}
        if country:
            params["country"] = country
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(GEOCODING_API_URL, params=params)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results:
                    return {
                        "latitude": results[0]["latitude"],
                        "longitude": results[0]["longitude"],
                        "city": results[0].get("name", city),
                        "country": results[0].get("country", ""),
                        "timezone": results[0].get("timezone", "")
                    }
        return None
    except Exception as e:
        logger.error(f"[Weather] Geocoding error: {e}")
        return None


async def fetch_weather(latitude: float, longitude: float) -> Optional[Dict]:
    """Fetch current weather from Open-Meteo (FREE)"""
    try:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "uv_index"
            ],
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "uv_index_max",
                "precipitation_sum"
            ],
            "timezone": "auto"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(WEATHER_API_URL, params=params)
            
            if response.status_code == 200:
                data = response.json()
                current = data.get("current", {})
                daily = data.get("daily", {})
                
                return {
                    "temperature": current.get("temperature_2m"),
                    "feels_like": current.get("apparent_temperature"),
                    "humidity": current.get("relative_humidity_2m"),
                    "uv_index": current.get("uv_index", 0),
                    "wind_speed": current.get("wind_speed_10m"),
                    "precipitation": current.get("precipitation", 0),
                    "weather_code": current.get("weather_code"),
                    "daily_high": daily.get("temperature_2m_max", [None])[0],
                    "daily_low": daily.get("temperature_2m_min", [None])[0],
                    "daily_uv_max": daily.get("uv_index_max", [0])[0],
                    "timezone": data.get("timezone", "")
                }
        return None
    except Exception as e:
        logger.error(f"[Weather] Fetch error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# SKIN ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_weather_for_skin(weather: Dict) -> Dict:
    """Analyze weather conditions and their impact on skin"""
    
    temp = weather.get("temperature", 20)
    humidity = weather.get("humidity", 50)
    uv_index = weather.get("uv_index", 0) or 0
    wind_speed = weather.get("wind_speed", 0) or 0
    
    conditions = []
    impacts = []
    recommendations = []
    ingredients_to_seek = set()
    ingredients_to_avoid = set()
    
    # Temperature + Humidity analysis
    if temp >= 25:  # Hot
        if humidity >= 60:
            profile = WEATHER_SKIN_IMPACTS["hot_humid"]
            conditions.append("hot_humid")
        else:
            profile = WEATHER_SKIN_IMPACTS["hot_dry"]
            conditions.append("hot_dry")
    elif temp <= 10:  # Cold
        if humidity >= 60:
            profile = WEATHER_SKIN_IMPACTS["cold_humid"]
            conditions.append("cold_humid")
        else:
            profile = WEATHER_SKIN_IMPACTS["cold_dry"]
            conditions.append("cold_dry")
    else:  # Moderate
        profile = WEATHER_SKIN_IMPACTS["cold_humid"]  # Default to balanced
    
    impacts.extend(profile["skin_effects"])
    recommendations.extend(profile["recommendations"])
    ingredients_to_seek.update(profile["ingredients_to_seek"])
    ingredients_to_avoid.update(profile["ingredients_to_avoid"])
    
    # UV analysis
    if uv_index >= 6:
        profile = WEATHER_SKIN_IMPACTS["high_uv"]
        conditions.append("high_uv")
        impacts.extend(profile["skin_effects"])
        recommendations.extend(profile["recommendations"])
        ingredients_to_seek.update(profile["ingredients_to_seek"])
    
    # Wind analysis
    if wind_speed >= 20:
        profile = WEATHER_SKIN_IMPACTS["windy"]
        conditions.append("windy")
        impacts.extend(profile["skin_effects"])
        recommendations.extend(profile["recommendations"])
        ingredients_to_seek.update(profile["ingredients_to_seek"])
    
    # Determine overall skin concern priority
    if temp >= 25 and uv_index >= 6:
        priority = "sun_protection"
        concern_level = "high"
    elif temp <= 5 and humidity < 40:
        priority = "hydration"
        concern_level = "high"
    elif uv_index >= 8:
        priority = "sun_protection"
        concern_level = "critical"
    else:
        priority = "maintenance"
        concern_level = "moderate"
    
    return {
        "conditions": conditions,
        "summary": f"Temperature {temp}°C, Humidity {humidity}%, UV {uv_index}",
        "skin_effects": list(set(impacts))[:5],
        "general_recommendations": list(set(recommendations))[:6],
        "ingredients_to_seek": list(ingredients_to_seek),
        "ingredients_to_avoid": list(ingredients_to_avoid),
        "priority": priority,
        "concern_level": concern_level
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT MATCHING
# ═══════════════════════════════════════════════════════════════════════════════

async def get_weather_matched_products(skin_analysis: Dict, limit: int = 5) -> List[Dict]:
    """Match products from catalog to weather-based skin needs"""
    
    if _db is None:
        return []
    
    try:
        # Get all active products
        products = await _db.products.find(
            {"is_active": {"$ne": False}},
            {"_id": 0, "id": 1, "name": 1, "slug": 1, "price": 1, "description": 1, 
             "hero_ingredients": 1, "primary_benefit": 1, "tags": 1, "images": 1,
             "ingredients": 1, "short_description": 1}
        ).to_list(50)
        
        if not products:
            return []
        
        # Score products based on ingredient match
        ingredients_to_seek = [i.lower() for i in skin_analysis.get("ingredients_to_seek", [])]
        priority = skin_analysis.get("priority", "maintenance")
        
        scored_products = []
        
        for product in products:
            score = 0
            match_reasons = []
            
            # Check hero ingredients
            hero_ings = product.get("hero_ingredients", [])
            for hero in hero_ings:
                if isinstance(hero, dict):
                    hero_name = hero.get("name", "").lower()
                    hero_display = hero.get("name", hero_name)
                else:
                    hero_name = str(hero).lower()
                    hero_display = str(hero)
                for seek in ingredients_to_seek:
                    if seek in hero_name:
                        score += 10
                        match_reasons.append(f"Contains {hero_display}")
            
            # Check full ingredients
            full_ings = str(product.get("ingredients", "")).lower()
            for seek in ingredients_to_seek:
                if seek in full_ings:
                    score += 3
            
            # Check tags/benefits
            tags = [t.lower() for t in product.get("tags", [])]
            benefit = str(product.get("primary_benefit", "")).lower()
            
            if priority == "sun_protection":
                if any(t in tags for t in ["spf", "sunscreen", "protection"]):
                    score += 15
                    match_reasons.append("Sun protection")
                if "antioxidant" in benefit or "brightening" in tags:
                    score += 5
                    match_reasons.append("Antioxidant protection")
            
            elif priority == "hydration":
                if any(t in tags for t in ["hydrating", "moisturizing", "barrier"]):
                    score += 15
                    match_reasons.append("Deep hydration")
                if "recovery" in benefit or "repair" in tags:
                    score += 5
                    match_reasons.append("Barrier repair")
            
            # PDRN products always score well for skin health
            pdrn_in_hero = any(
                "pdrn" in (h.get("name", "").lower() if isinstance(h, dict) else str(h).lower())
                for h in hero_ings
            )
            if "pdrn" in full_ings or pdrn_in_hero:
                score += 8
                match_reasons.append("PDRN cellular repair")
            
            # TXA / Tranexamic Acid for brightening
            if "tranexamic" in full_ings or "txa" in full_ings:
                score += 5
                match_reasons.append("Brightening & even tone")
            
            # Peptides for maintenance
            if "peptide" in full_ings or any("peptide" in t for t in tags):
                score += 4
                match_reasons.append("Peptide skin support")
            
            # Hyaluronic acid for hydration (always good)
            if "hyaluronic" in full_ings:
                score += 3
                match_reasons.append("Hydration boost")
            
            # Base score for all products (so we always return recommendations)
            if score == 0:
                score = 1
                match_reasons.append("Daily skincare essential")
            
            # Handle images - can be list of strings or list of dicts
            images = product.get("images", [])
            image_url = None
            if images:
                first_img = images[0]
                if isinstance(first_img, dict):
                    image_url = first_img.get("url")
                else:
                    image_url = first_img  # It's already a URL string
            
            scored_products.append({
                **product,
                "weather_match_score": score,
                "match_reasons": list(set(match_reasons))[:3],
                "image": image_url
            })
        
        # Sort by score and return top matches
        scored_products.sort(key=lambda x: x["weather_match_score"], reverse=True)
        
        return scored_products[:limit]
        
    except Exception as e:
        logger.error(f"[Weather] Product matching error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# AI ROUTINE TIPS
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_routine_tips(weather: Dict, skin_analysis: Dict, products: List[Dict]) -> List[str]:
    """Generate personalized routine tips using AI"""
    
    if not OPENROUTER_API_KEY:
        # Fallback tips based on conditions
        tips = []
        if "hot_humid" in skin_analysis.get("conditions", []):
            tips.append("Double cleanse in the evening to remove sweat and excess oil")
            tips.append("Use a lightweight, water-based moisturizer")
        if "cold_dry" in skin_analysis.get("conditions", []):
            tips.append("Layer a hydrating serum under your moisturizer")
            tips.append("Consider using a humidifier indoors")
        if "high_uv" in skin_analysis.get("conditions", []):
            tips.append("Reapply SPF every 2 hours when outdoors")
            tips.append("Apply antioxidant serum in the morning before sunscreen")
        if not tips:
            tips.append("Stay hydrated and maintain your regular skincare routine")
        return tips[:4]
    
    try:
        product_names = [p.get("name", "") for p in products[:3]]
        
        prompt = f"""Based on current weather conditions and skin analysis, provide 4 brief, actionable skincare routine tips.

WEATHER:
- Temperature: {weather.get('temperature')}°C
- Humidity: {weather.get('humidity')}%
- UV Index: {weather.get('uv_index')}
- Conditions: {', '.join(skin_analysis.get('conditions', ['normal']))}

SKIN CONCERNS: {', '.join(skin_analysis.get('skin_effects', [])[:3])}

RECOMMENDED PRODUCTS: {', '.join(product_names)}

Provide exactly 4 tips, each under 20 words. Focus on practical application timing and techniques.
Format: Just the tips, one per line, no numbering."""

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "google/gemini-2.0-flash-lite-001",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.7
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                tips = [tip.strip() for tip in content.split("\n") if tip.strip()]
                return tips[:4]
        
        return ["Follow your regular routine with extra attention to hydration."]
        
    except Exception as e:
        logger.error(f"[Weather] AI tips error: {e}")
        return ["Maintain your regular skincare routine and stay hydrated."]


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze")
async def analyze_weather_skincare(request: LocationRequest):
    """
    Get weather-based skincare recommendations for a location.
    Uses coordinates (latitude/longitude).
    """
    try:
        # Fetch weather
        weather = await fetch_weather(request.latitude, request.longitude)
        
        if not weather:
            raise HTTPException(status_code=503, detail="Unable to fetch weather data")
        
        # Analyze skin impact
        skin_analysis = analyze_weather_for_skin(weather)
        
        # Get matched products
        products = await get_weather_matched_products(skin_analysis)
        
        # Generate routine tips
        tips = await generate_routine_tips(weather, skin_analysis, products)
        
        return {
            "location": {
                "latitude": request.latitude,
                "longitude": request.longitude,
                "city": request.city
            },
            "weather": weather,
            "skin_analysis": skin_analysis,
            "product_recommendations": products,
            "routine_tips": tips,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Weather] Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/city")
async def analyze_weather_skincare_by_city(request: CityRequest):
    """
    Get weather-based skincare recommendations by city name.
    """
    try:
        # Geocode city
        location = await geocode_city(request.city, request.country)
        
        if not location:
            raise HTTPException(status_code=404, detail=f"City not found: {request.city}")
        
        # Fetch weather
        weather = await fetch_weather(location["latitude"], location["longitude"])
        
        if not weather:
            raise HTTPException(status_code=503, detail="Unable to fetch weather data")
        
        # Analyze skin impact
        skin_analysis = analyze_weather_for_skin(weather)
        
        # Get matched products
        products = await get_weather_matched_products(skin_analysis)
        
        # Generate routine tips
        tips = await generate_routine_tips(weather, skin_analysis, products)
        
        return {
            "location": location,
            "weather": weather,
            "skin_analysis": skin_analysis,
            "product_recommendations": products,
            "routine_tips": tips,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Weather] City analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conditions")
async def get_weather_conditions_info():
    """Get information about weather conditions and their skin impacts"""
    return {
        "conditions": WEATHER_SKIN_IMPACTS
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/alert/subscribe")
async def subscribe_weather_alerts(request: Request):
    """Subscribe user to daily weather skincare alerts"""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        body = await request.json()
        user_id = body.get("user_id")
        email = body.get("email")
        phone = body.get("phone")  # For WhatsApp alerts
        city = body.get("city")
        latitude = body.get("latitude")
        longitude = body.get("longitude")
        alert_time = body.get("alert_time", "07:00")  # Default 7 AM
        
        if not user_id or not (email or phone):
            raise HTTPException(status_code=400, detail="user_id and email/phone required")
        
        subscription = {
            "user_id": user_id,
            "email": email,
            "phone": phone,
            "city": city,
            "latitude": latitude,
            "longitude": longitude,
            "alert_time": alert_time,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Upsert subscription
        await _db.weather_skincare_subscriptions.update_one(
            {"user_id": user_id},
            {"$set": subscription},
            upsert=True
        )
        
        return {"status": "subscribed", "subscription": subscription}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Weather] Subscribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alert/unsubscribe")
async def unsubscribe_weather_alerts(user_id: str):
    """Unsubscribe from weather skincare alerts"""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        await _db.weather_skincare_subscriptions.update_one(
            {"user_id": user_id},
            {"$set": {"active": False}}
        )
        
        return {"status": "unsubscribed"}
        
    except Exception as e:
        logger.error(f"[Weather] Unsubscribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alert/send-daily")
async def send_daily_weather_alerts():
    """
    Send daily weather skincare alerts to all subscribers.
    Call this from a cron job (e.g., every morning at 7 AM).
    """
    if _db is None:
        return {"sent": 0, "error": "Database not available"}
    
    try:
        # Get active subscriptions
        subscriptions = await _db.weather_skincare_subscriptions.find(
            {"active": True}
        ).to_list(500)
        
        sent_count = 0
        
        for sub in subscriptions:
            try:
                # Get weather for user's location
                lat = sub.get("latitude")
                lon = sub.get("longitude")
                city = sub.get("city")
                
                if not (lat and lon) and city:
                    location = await geocode_city(city)
                    if location:
                        lat = location["latitude"]
                        lon = location["longitude"]
                
                if not (lat and lon):
                    continue
                
                weather = await fetch_weather(lat, lon)
                if not weather:
                    continue
                
                skin_analysis = analyze_weather_for_skin(weather)
                products = await get_weather_matched_products(skin_analysis, limit=2)
                
                # Build alert message
                temp = weather.get("temperature", 0)
                uv = weather.get("uv_index", 0)
                conditions = skin_analysis.get("conditions", [])
                
                message = f"""☀️ *Your Daily Skincare Forecast*

📍 {city or 'Your location'}
🌡️ {temp}°C | UV: {uv}

*Today's Skin Focus:*
{skin_analysis.get('priority', 'maintenance').replace('_', ' ').title()}

*Top Recommendations:*
"""
                for p in products[:2]:
                    message += f"• {p.get('name')}\n"
                
                message += f"\n💡 *Tip:* {skin_analysis.get('general_recommendations', ['Stay hydrated'])[0]}"
                
                # Send via WhatsApp if phone available
                if sub.get("phone"):
                    from routers.whatsapp_alerts import send_whatsapp
                    result = await send_whatsapp(sub["phone"], message)
                    if result.get("success"):
                        sent_count += 1
                
                # Send via Email if email available
                elif sub.get("email"):
                    from routers.email_service import send_email, base_template
                    html = base_template(
                        "Your Daily Skincare Forecast",
                        message.replace("\n", "<br>").replace("*", ""),
                        "VIEW RECOMMENDATIONS",
                        "https://reroots.ca/app"
                    )
                    if send_email(sub["email"], f"☀️ Skincare Forecast: {temp}°C, UV {uv}", html):
                        sent_count += 1
                        
            except Exception as e:
                logger.error(f"[Weather] Alert send error for {sub.get('user_id')}: {e}")
                continue
        
        return {"sent": sent_count, "total_subscribers": len(subscriptions)}
        
    except Exception as e:
        logger.error(f"[Weather] Daily alerts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
