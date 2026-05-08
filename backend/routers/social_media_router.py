"""
AUREM Social Media Router — Envoy Agent Social Channel
POST /api/social/generate — AI-generate post content
POST /api/social/publish — publish/schedule across platforms
POST /api/social/outreach — Envoy social outreach
GET  /api/social/history — post history
GET  /api/social/stats — analytics
GET  /api/social/brightbean/status — Brightbean Studio connection check
GET  /api/social/platforms — supported platforms list
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/social", tags=["Social Media (Envoy)"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        return jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _tenant(payload: dict) -> str:
    return payload.get("tenant_id") or payload.get("business_id") or "aurem_platform"


def _init():
    from services.social_media_service import set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass


class GenerateRequest(BaseModel):
    topic: str
    platform: str = "linkedin"
    tone: str = "professional"
    context: str = ""


@router.post("/generate")
async def generate_post(req: GenerateRequest, authorization: str = Header(None)):
    """AI-generate social media post content."""
    await _auth(authorization)
    from services.social_media_service import generate_post_content
    return await generate_post_content(req.topic, req.platform, req.tone, req.context)


class PublishRequest(BaseModel):
    content: str
    platforms: List[str]
    media_urls: List[str] = []
    schedule_at: Optional[str] = None


@router.post("/publish")
async def publish(req: PublishRequest, authorization: str = Header(None)):
    """Publish or schedule a post across platforms."""
    payload = await _auth(authorization)
    _init()
    from services.social_media_service import publish_post
    return await publish_post(req.content, req.platforms, req.media_urls, req.schedule_at, _tenant(payload))


class OutreachRequest(BaseModel):
    target_name: str
    target_handle: str
    platform: str = "linkedin"
    message_template: str


@router.post("/outreach")
async def outreach(req: OutreachRequest, authorization: str = Header(None)):
    """Envoy Agent social outreach — personalized engagement."""
    payload = await _auth(authorization)
    _init()
    from services.social_media_service import envoy_social_outreach
    return await envoy_social_outreach(req.target_name, req.target_handle, req.platform, req.message_template, _tenant(payload))


@router.get("/history")
async def history(limit: int = 20, authorization: str = Header(None)):
    """Get post history."""
    payload = await _auth(authorization)
    _init()
    from services.social_media_service import get_post_history
    posts = await get_post_history(_tenant(payload), limit)
    return {"posts": posts, "count": len(posts)}


@router.get("/stats")
async def stats(authorization: str = Header(None)):
    """Social media analytics."""
    payload = await _auth(authorization)
    _init()
    from services.social_media_service import get_social_stats
    return await get_social_stats(_tenant(payload))


@router.get("/brightbean/status")
async def brightbean_check(authorization: str = Header(None)):
    """Check Brightbean Studio connection."""
    await _auth(authorization)
    from services.social_media_service import brightbean_status
    return await brightbean_status()


@router.get("/platforms")
async def platforms(authorization: str = Header(None)):
    """List supported social media platforms."""
    await _auth(authorization)
    from services.social_media_service import PLATFORMS
    return {"platforms": PLATFORMS, "count": len(PLATFORMS)}
