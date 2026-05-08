"""
AUREM Content Engine Router — CRM-Triggered Content Generation
POST /api/content-engine/welcome-sequence — new customer → email sequence
POST /api/content-engine/campaign — multi-platform campaign copy
POST /api/content-engine/cold-outreach — lead → personalized outreach
POST /api/content-engine/social-post — single social post
POST /api/content-engine/generate-image — marketing image
POST /api/content-engine/one-click — full campaign (copy + image + schedule)
GET  /api/content-engine/usage — current month usage vs tier limit
GET  /api/content-engine/history — content generation history
GET  /api/content-engine/campaigns — campaign history
GET  /api/content-engine/tiers — plan tier limits for content engine
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/content-engine", tags=["Content Engine"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        return jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _tenant(p: dict) -> str:
    return p.get("tenant_id") or p.get("business_id") or "aurem_platform"


def _init():
    from services.content_engine import set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass


class WelcomeRequest(BaseModel):
    customer_name: str
    business_name: str
    industry: str = ""


@router.post("/welcome-sequence")
async def welcome_sequence(req: WelcomeRequest, authorization: str = Header(None)):
    """CRM: New customer → auto-generate 3-email welcome sequence."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import generate_welcome_sequence
    result = await generate_welcome_sequence(req.customer_name, req.business_name, req.industry, _tenant(p))
    if result.get("error") == "limit_reached":
        raise HTTPException(status_code=429, detail=result["message"])
    return result


class CampaignRequest(BaseModel):
    campaign_name: str
    target_audience: str
    platforms: List[str] = ["linkedin", "instagram"]
    tone: str = "professional"


@router.post("/campaign")
async def campaign_copy(req: CampaignRequest, authorization: str = Header(None)):
    """Generate multi-platform campaign copy."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import generate_campaign_copy
    result = await generate_campaign_copy(req.campaign_name, req.target_audience, req.platforms, req.tone, _tenant(p))
    if result.get("error") == "limit_reached":
        raise HTTPException(status_code=429, detail=result["message"])
    return result


class OutreachRequest(BaseModel):
    lead_name: str
    company: str
    pain_point: str = ""


@router.post("/cold-outreach")
async def cold_outreach(req: OutreachRequest, authorization: str = Header(None)):
    """CRM: New lead → personalized cold outreach email."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import generate_cold_outreach
    result = await generate_cold_outreach(req.lead_name, req.company, req.pain_point, _tenant(p))
    if result.get("error") == "limit_reached":
        raise HTTPException(status_code=429, detail=result["message"])
    return result


class SocialPostRequest(BaseModel):
    topic: str
    platform: str = "linkedin"
    brand_voice: str = "professional"


@router.post("/social-post")
async def social_post(req: SocialPostRequest, authorization: str = Header(None)):
    """Generate single social media post."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import generate_social_post
    result = await generate_social_post(req.topic, req.platform, req.brand_voice, _tenant(p))
    if result.get("error") == "limit_reached":
        raise HTTPException(status_code=429, detail=result["message"])
    return result


class ImageRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"


@router.post("/generate-image")
async def generate_image(req: ImageRequest, authorization: str = Header(None)):
    """Generate marketing image via GPT Image 1. Returns image_id + base64."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import generate_image as _gen
    result = await _gen(req.prompt, req.size, _tenant(p))
    if result.get("error") == "limit_reached":
        raise HTTPException(status_code=429, detail=result["message"])
    if result.get("error") and not result.get("generated"):
        raise HTTPException(status_code=500, detail=result.get("error", "Image generation failed"))
    return {k: v for k, v in result.items() if k != "image_base64_full"}


class OneClickRequest(BaseModel):
    campaign_name: str
    target_audience: str
    platforms: List[str] = ["linkedin", "instagram"]
    generate_images: bool = True
    auto_schedule: bool = False


@router.post("/one-click")
async def one_click(req: OneClickRequest, authorization: str = Header(None)):
    """One-click campaign: copy + image + video (Enterprise) + schedule. Full pipeline."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import one_click_campaign
    return await one_click_campaign(req.campaign_name, req.target_audience, req.platforms, req.generate_images, req.auto_schedule, _tenant(p))


# ═══════════════════════════════════════
# VIDEO GENERATION — Enterprise Only
# ═══════════════════════════════════════

class VideoRequest(BaseModel):
    product_name: str
    product_description: str = ""
    image_url: Optional[str] = None
    style: str = "brand_story"
    platform: str = "instagram_reels"
    aspect_ratio: str = "9:16"
    duration: int = 5


@router.post("/generate-video")
async def generate_video(req: VideoRequest, authorization: str = Header(None)):
    """Generate marketing video. Growth: 480p text-only. Enterprise: HD + I2V + all providers."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import generate_video_content
    result = await generate_video_content(
        product_name=req.product_name,
        product_description=req.product_description,
        image_url=req.image_url,
        style=req.style,
        platform=req.platform,
        aspect_ratio=req.aspect_ratio,
        duration=req.duration,
        tenant_id=_tenant(p),
    )
    if result.get("error") == "upgrade_required":
        raise HTTPException(status_code=403, detail=result.get("message") or "Video generation requires Growth or Enterprise plan")
    if result.get("error") and not result.get("generated"):
        detail = result.get("message") or result.get("error", "Video generation failed")
        code = 402 if "credit" in detail.lower() else 500
        raise HTTPException(status_code=code, detail=detail)
    return result


class ExtendVideoRequest(BaseModel):
    request_id: str
    prompt: str
    duration: int = 5


@router.post("/extend-video")
async def extend_video_endpoint(req: ExtendVideoRequest, authorization: str = Header(None)):
    """Extend an existing video. Enterprise only."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import check_limit
    check = await check_limit(_tenant(p), "videos_generated")
    if check.get("tier") != "enterprise":
        raise HTTPException(status_code=403, detail="Video extend requires Enterprise plan")
    from services.video_orchestrator import extend_video
    result = await extend_video(req.request_id, req.prompt, req.duration)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


class VideoUploadRequest(BaseModel):
    """For uploading product images for I2V."""
    pass


@router.post("/upload-video-image")
async def upload_video_image(authorization: str = Header(None)):
    """Upload product image for video generation. Returns hosted URL."""
    from fastapi import UploadFile, File
    raise HTTPException(status_code=501, detail="Use /api/content-engine/generate-video with image_url directly")


@router.get("/video-history")
async def video_history(limit: int = 20, authorization: str = Header(None)):
    """Get video generation history."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import get_video_history
    items = await get_video_history(_tenant(p), limit)
    return {"videos": items, "count": len(items)}


@router.get("/usage")
async def usage(authorization: str = Header(None)):
    """Get current month's content engine usage vs tier limit."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import get_usage, check_limit
    u = await get_usage(_tenant(p))
    posts_check = await check_limit(_tenant(p), "content_posts")
    images_check = await check_limit(_tenant(p), "images_generated")
    videos_check = await check_limit(_tenant(p), "videos_generated")
    return {
        "usage": u,
        "posts": posts_check,
        "images": images_check,
        "videos": videos_check,
    }


@router.get("/history")
async def history(limit: int = 20, authorization: str = Header(None)):
    """Content generation history."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import get_content_history
    items = await get_content_history(_tenant(p), limit)
    return {"items": items, "count": len(items)}


@router.get("/campaigns")
async def campaigns(limit: int = 10, authorization: str = Header(None)):
    """Campaign history."""
    p = await _auth(authorization)
    _init()
    from services.content_engine import get_campaign_history
    items = await get_campaign_history(_tenant(p), limit)
    return {"campaigns": items, "count": len(items)}


@router.get("/tiers")
async def tiers(authorization: str = Header(None)):
    """Content engine tier limits for each plan."""
    await _auth(authorization)
    from services.plan_enforcement import PLAN_TIERS
    return {
        tier: {
            "name": plan["name"],
            "price": f"${plan['price_monthly']}/mo",
            "content_posts": plan["limits"].get("content_posts_per_month", 0),
            "images": plan["limits"].get("images_per_month", 0),
            "social_channels": plan["limits"].get("social_channels", 0),
            "email_sequences": plan["limits"].get("email_sequences_active", 0),
            "video": plan["limits"].get("video_generation", False),
        }
        for tier, plan in PLAN_TIERS.items()
    }
