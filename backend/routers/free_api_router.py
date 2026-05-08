"""
AUREM Free API Arsenal Router
All zero-cost intelligence APIs in one place.
GET  /api/free-apis/registry — list all free APIs and what they replace
POST /api/free-apis/call — call any free API tool
GET  /api/free-apis/weather — quick weather (no key)
GET  /api/free-apis/rates — quick exchange rates
POST /api/free-apis/url-check — malware URL check
POST /api/free-apis/translate — translate text
POST /api/free-apis/validate-email — email validation
GET  /api/free-apis/domains — domain search
GET  /api/free-apis/geolocate — IP geolocation
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/free-apis", tags=["Free API Arsenal"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        return jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/registry")
async def free_api_registry(authorization: str = Header(None)):
    """List all free APIs integrated, what they replace, and their cost."""
    await _auth(authorization)
    from services.free_api_arsenal import FREE_API_REGISTRY, TOOL_DEFS
    return {"apis": FREE_API_REGISTRY, "tools": TOOL_DEFS, "total_apis": len(FREE_API_REGISTRY), "total_cost": "$0"}


class ToolCallRequest(BaseModel):
    tool: str
    arguments: dict = {}


@router.post("/call")
async def call_tool(req: ToolCallRequest, authorization: str = Header(None)):
    """Call any free API tool by name."""
    await _auth(authorization)
    from services.free_api_arsenal import call_free_api
    return await call_free_api(req.tool, req.arguments)


@router.get("/weather")
async def weather(lat: float = 43.59, lon: float = -79.65, city: str = "Mississauga", authorization: str = Header(None)):
    """Free weather via Open-Meteo. No API key needed."""
    await _auth(authorization)
    from services.free_api_arsenal import get_weather
    return await get_weather(lat, lon, city)


@router.get("/rates")
async def exchange_rates(base: str = "CAD", authorization: str = Header(None)):
    """Free currency exchange rates. No API key needed."""
    await _auth(authorization)
    from services.free_api_arsenal import get_exchange_rates
    return await get_exchange_rates(base)


class URLCheckRequest(BaseModel):
    url: str


@router.post("/url-check")
async def url_check(req: URLCheckRequest, authorization: str = Header(None)):
    """Check URL for malware/phishing via URLhaus. Free, no key."""
    await _auth(authorization)
    from services.free_api_arsenal import check_url_malware
    return await check_url_malware(req.url)


class TranslateRequest(BaseModel):
    text: str
    source: str = "auto"
    target: str = "en"


@router.post("/translate")
async def translate(req: TranslateRequest, authorization: str = Header(None)):
    """Translate text via LibreTranslate. Free, no key."""
    await _auth(authorization)
    from services.free_api_arsenal import translate_text
    return await translate_text(req.text, req.source, req.target)


class EmailValidateRequest(BaseModel):
    email: str


@router.post("/validate-email")
async def validate_email(req: EmailValidateRequest, authorization: str = Header(None)):
    """Validate email format + DNS MX check. Zero cost."""
    await _auth(authorization)
    from services.free_api_arsenal import validate_email as _validate
    return await _validate(req.email)


@router.get("/domains")
async def domain_search(keyword: str, zone: str = "com", limit: int = 20, authorization: str = Header(None)):
    """Search registered domains by keyword. Free, no key."""
    await _auth(authorization)
    from services.free_api_arsenal import search_domains
    return await search_domains(keyword, zone, limit)


@router.get("/geolocate")
async def geolocate(ip: str, authorization: str = Header(None)):
    """IP geolocation. Free, no key."""
    await _auth(authorization)
    from services.free_api_arsenal import geolocate_ip
    return await geolocate_ip(ip)


@router.get("/find-emails")
async def find_emails(domain: str, limit: int = 10, authorization: str = Header(None)):
    """Find emails for a company domain via Tomba.io. Free 50/month."""
    await _auth(authorization)
    from services.free_api_arsenal import find_emails_by_domain
    return await find_emails_by_domain(domain, limit)


class VerifyEmailTombaRequest(BaseModel):
    email: str


@router.post("/verify-email")
async def verify_email(req: VerifyEmailTombaRequest, authorization: str = Header(None)):
    """Verify email deliverability via Tomba.io."""
    await _auth(authorization)
    from services.free_api_arsenal import verify_email_tomba
    return await verify_email_tomba(req.email)


class PhoneValidateRequest(BaseModel):
    phone: str


@router.post("/validate-phone")
async def validate_phone(req: PhoneValidateRequest, authorization: str = Header(None)):
    """Validate phone number via Numverify. Country, carrier, line type."""
    await _auth(authorization)
    from services.free_api_arsenal import validate_phone as _validate
    return await _validate(req.phone)


@router.get("/geolocate-rich")
async def geolocate_rich(ip: str, authorization: str = Header(None)):
    """Rich IP geolocation via IPstack — currency, flag, languages. Falls back to ip-api."""
    await _auth(authorization)
    from services.free_api_arsenal import geolocate_ip_rich
    return await geolocate_ip_rich(ip)


class VisionRequest(BaseModel):
    image_url: str
    question: str = "Describe this image"


@router.post("/vision")
async def vision(req: VisionRequest, authorization: str = Header(None)):
    """Analyze image via DeepAI. Free tier. Replaces mmx vision."""
    await _auth(authorization)
    from services.free_api_arsenal import analyze_image_vision
    return await analyze_image_vision(req.image_url, req.question)


@router.get("/music")
async def music(query: str = "corporate background", limit: int = 5, mood: str = "", authorization: str = Header(None)):
    """Search royalty-free music via Jamendo. CC licensed, $0."""
    await _auth(authorization)
    from services.free_api_arsenal import search_music
    return await search_music(query, limit, mood)
