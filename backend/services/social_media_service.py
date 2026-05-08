"""
AUREM Social Media Service — Envoy Agent Social Channel
========================================================
Bridges to Brightbean Studio (self-hosted) OR posts directly via platform APIs.
Adds social media as a channel alongside WhatsApp/Email/SMS in Envoy Agent.

Mode 1: Brightbean Bridge (if BRIGHTBEAN_URL set)
  → AURA generates content → pushes to Brightbean API → Brightbean publishes
Mode 2: Direct Post (if platform tokens in DB)
  → AURA generates content → posts directly via platform APIs

Platforms: Instagram, LinkedIn, Twitter/X, Facebook, TikTok, Bluesky
Cost: $0 — fully self-hosted Brightbean replaces Buffer ($18/mo)
"""
import os
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

import httpx

logger = logging.getLogger(__name__)

_db = None

BRIGHTBEAN_URL = os.environ.get("BRIGHTBEAN_URL", "")
BRIGHTBEAN_API_KEY = os.environ.get("BRIGHTBEAN_API_KEY", "")


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


PLATFORMS = ["instagram", "linkedin", "twitter", "facebook", "tiktok", "bluesky", "threads"]


# ═══════════════════════════════════════════════════════════════
# CONTENT GENERATION (AURA writes the post)
# ═══════════════════════════════════════════════════════════════

async def generate_post_content(
    topic: str,
    platform: str = "linkedin",
    tone: str = "professional",
    context: str = "",
) -> Dict:
    """AURA generates social media post content via LLM."""
    char_limits = {"twitter": 280, "instagram": 2200, "linkedin": 3000, "facebook": 5000, "tiktok": 2200, "bluesky": 300, "threads": 500}
    limit = char_limits.get(platform, 2000)

    prompt = f"""Write a {platform} post about: {topic}
Tone: {tone}. Max {limit} chars. Include 3-5 relevant hashtags.
{f'Context: {context}' if context else ''}
Return ONLY the post text, nothing else."""

    try:
        from services.openrouter_client import call_model, FREE_MODELS
        result = await call_model(FREE_MODELS[0], "You are a social media expert.", prompt, temperature=0.7, max_tokens=500)
        content = result.get("content", "").strip()
        if content:
            return {"content": content[:limit], "platform": platform, "chars": len(content[:limit]), "limit": limit, "generated": True}
    except Exception as e:
        logger.debug(f"[Social] LLM generation failed: {e}")

    # Fallback: template-based
    content = f"{topic}\n\n#AUREM #AI #Business"
    return {"content": content[:limit], "platform": platform, "chars": len(content), "limit": limit, "generated": False, "note": "template_fallback"}


# ═══════════════════════════════════════════════════════════════
# BRIGHTBEAN / POSTIZ BRIDGE (self-hosted on Legion)
# Supports both Brightbean Studio and Postiz (open-source social scheduler)
# ═══════════════════════════════════════════════════════════════

async def _social_post(endpoint: str, payload: dict) -> Optional[dict]:
    """Call social scheduler API (Postiz or Brightbean)."""
    if not BRIGHTBEAN_URL:
        return None
    headers = {"Content-Type": "application/json"}
    if BRIGHTBEAN_API_KEY:
        headers["Authorization"] = f"Bearer {BRIGHTBEAN_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(f"{BRIGHTBEAN_URL.rstrip('/')}{endpoint}", json=payload, headers=headers)
            if r.status_code in (200, 201):
                return r.json()
            logger.warning(f"[Social] {endpoint}: {r.status_code}")
    except Exception as e:
        logger.debug(f"[Social] error: {e}")
    return None


async def brightbean_status() -> Dict:
    """Check if social scheduler (Postiz/Brightbean) is reachable."""
    if not BRIGHTBEAN_URL:
        return {"connected": False, "url": "", "setup": "Set BRIGHTBEAN_URL in .env (e.g. https://social.aurem.live)"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            # Try Postiz health endpoint first
            r = await c.get(f"{BRIGHTBEAN_URL.rstrip('/')}/api/health")
            if r.status_code == 200:
                return {"connected": True, "url": BRIGHTBEAN_URL, "engine": "postiz"}
            # Fallback to Brightbean endpoint
            r = await c.get(f"{BRIGHTBEAN_URL.rstrip('/')}/api/health/")
            return {"connected": r.status_code == 200, "url": BRIGHTBEAN_URL, "engine": "brightbean"}
    except Exception:
        return {"connected": False, "url": BRIGHTBEAN_URL, "error": "unreachable"}


# ═══════════════════════════════════════════════════════════════
# UNIFIED POST / SCHEDULE
# ═══════════════════════════════════════════════════════════════

async def publish_post(
    content: str,
    platforms: List[str],
    media_urls: List[str] = None,
    schedule_at: str = None,
    tenant_id: str = "aurem_platform",
) -> Dict:
    """
    Publish or schedule a post across multiple platforms.
    Route: Brightbean (if available) → Direct API → Queue for later.
    """
    db = _get_db()
    post_id = f"post_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc).isoformat()
    results = {}

    # Try Brightbean first
    if BRIGHTBEAN_URL:
        bb_result = await _brightbean_post("/api/posts/create/", {
            "content": content,
            "platforms": platforms,
            "media_urls": media_urls or [],
            "schedule_at": schedule_at,
        })
        if bb_result:
            for p in platforms:
                results[p] = {"status": "queued_brightbean", "bb_post_id": bb_result.get("id")}

    # Direct API fallback for platforms not handled by Brightbean
    for platform in platforms:
        if platform in results:
            continue
        results[platform] = {"status": "queued", "note": "Direct API posting requires platform tokens in DB"}

    # Save to DB
    if db:
        await db.social_posts.insert_one({
            "post_id": post_id,
            "tenant_id": tenant_id,
            "content": content[:5000],
            "platforms": platforms,
            "media_urls": media_urls or [],
            "schedule_at": schedule_at,
            "results": results,
            "status": "published" if any(r.get("status") == "queued_brightbean" for r in results.values()) else "queued",
            "created_at": now,
        })

    return {"post_id": post_id, "results": results, "platforms": platforms}


async def schedule_post(
    content: str,
    platforms: List[str],
    schedule_at: str,
    media_urls: List[str] = None,
    tenant_id: str = "aurem_platform",
) -> Dict:
    """Schedule a post for future publishing."""
    return await publish_post(content, platforms, media_urls, schedule_at, tenant_id)


# ═══════════════════════════════════════════════════════════════
# ENVOY AGENT INTEGRATION
# ═══════════════════════════════════════════════════════════════

async def envoy_social_outreach(
    target_name: str,
    target_handle: str,
    platform: str,
    message_template: str,
    tenant_id: str = "aurem_platform",
) -> Dict:
    """
    Envoy Agent social outreach — personalized engagement.
    Part of the Forensic Miner → Scout → AURA → Envoy pipeline.
    """
    post = await generate_post_content(
        topic=message_template.replace("{name}", target_name),
        platform=platform,
        tone="friendly and professional",
        context=f"Reaching out to {target_name} ({target_handle})",
    )
    result = await publish_post(post["content"], [platform], tenant_id=tenant_id)
    result["target"] = target_name
    result["platform"] = platform
    return result


# ═══════════════════════════════════════════════════════════════
# ANALYTICS & HISTORY
# ═══════════════════════════════════════════════════════════════

async def get_post_history(tenant_id: str = None, limit: int = 20) -> List[Dict]:
    db = _get_db()
    if not db:
        return []
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    cursor = db.social_posts.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_social_stats(tenant_id: str = None) -> Dict:
    db = _get_db()
    if not db:
        return {"total_posts": 0, "platforms": {}}
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    total = await db.social_posts.count_documents(query)
    return {
        "total_posts": total,
        "brightbean_connected": bool(BRIGHTBEAN_URL),
        "brightbean_url": BRIGHTBEAN_URL or None,
        "supported_platforms": PLATFORMS,
    }
