"""
AUREM Content Engine — CRM-Triggered Autonomous Content Generation
===================================================================
Inspired by MarketingSkills (21K+ stars). 4 content skills:
  1. Welcome email sequence (new customer)
  2. Campaign copywriting (campaign created)
  3. Cold outreach (new lead)
  4. Social media posts (ongoing engagement)

+ Image generation via Emergent LLM Key (GPT Image 1)
+ Usage tracking per tenant with plan tier limits
+ One-click campaign generation (copy + image + schedule)
+ Connected to Brightbean/Social publish pipeline

Tier limits enforced:
  Starter: 50 posts/mo, 50 images/mo, 2 channels
  Growth:  500 posts/mo, 500 images/mo, 7 channels
  Enterprise: Unlimited + video
"""
import os
import logging
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_db = None


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


# ═══════════════════════════════════════════════════════════════
# USAGE TRACKING & TIER ENFORCEMENT
# ═══════════════════════════════════════════════════════════════

async def _get_tenant_tier(tenant_id: str) -> str:
    db = _get_db()
    if not db:
        return "starter"
    ws = await db.workspaces.find_one({"tenant_id": tenant_id}, {"_id": 0, "tier": 1, "plan": 1})
    if ws:
        return ws.get("tier") or ws.get("plan") or "starter"
    return "starter"


async def get_usage(tenant_id: str) -> Dict:
    """Get current month's content engine usage for a tenant."""
    db = _get_db()
    if not db:
        return {"content_posts": 0, "images_generated": 0, "month": ""}
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = await db.content_engine_usage.find_one(
        {"tenant_id": tenant_id, "month": month_key}, {"_id": 0}
    )
    if not usage:
        return {"content_posts": 0, "images_generated": 0, "month": month_key, "tenant_id": tenant_id}
    return usage


async def _increment_usage(tenant_id: str, field: str, count: int = 1):
    db = _get_db()
    if not db:
        return
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    await db.content_engine_usage.update_one(
        {"tenant_id": tenant_id, "month": month_key},
        {"$inc": {field: count}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


async def check_limit(tenant_id: str, resource: str) -> Dict:
    """Check if tenant has remaining quota for a resource."""
    from services.plan_enforcement import PLAN_TIERS
    tier = await _get_tenant_tier(tenant_id)
    plan = PLAN_TIERS.get(tier, PLAN_TIERS["starter"])
    limits = plan.get("limits", {})

    limit_map = {
        "content_posts": "content_posts_per_month",
        "images_generated": "images_per_month",
        "videos_generated": "videos_per_month",
    }
    limit_key = limit_map.get(resource, resource)
    max_allowed = limits.get(limit_key, 0)

    # Video generation is tiered: False=blocked, "basic"=limited, True=unlimited
    if resource == "videos_generated":
        video_enabled = limits.get("video_generation", False)
        if not video_enabled:
            return {"allowed": False, "used": 0, "limit": 0, "tier": tier, "reason": "upgrade_required",
                    "message": f"Video generation requires Growth or Enterprise plan. Current: {tier.capitalize()}"}
        # Enterprise = unlimited
        videos_limit = limits.get("videos_per_month", 0)
        if videos_limit == -1 or video_enabled is True:
            usage = await get_usage(tenant_id)
            used = usage.get("videos_generated", 0)
            return {"allowed": True, "used": used, "limit": "unlimited", "tier": tier, "quality": "HD"}
        # Growth = basic with monthly limit
        if video_enabled == "basic":
            usage = await get_usage(tenant_id)
            used = usage.get("videos_generated", 0)
            allowed = used < videos_limit if videos_limit > 0 else True
            return {"allowed": allowed, "used": used, "limit": videos_limit, "tier": tier, "quality": "480p",
                    "remaining": max(0, videos_limit - used) if videos_limit > 0 else "unlimited"}

    if max_allowed == -1:
        return {"allowed": True, "used": 0, "limit": "unlimited", "tier": tier}

    usage = await get_usage(tenant_id)
    used = usage.get(resource, 0)
    return {"allowed": used < max_allowed, "used": used, "limit": max_allowed, "remaining": max(0, max_allowed - used), "tier": tier}


# ═══════════════════════════════════════════════════════════════
# CONTENT SKILLS — LLM-Powered Generation
# ═══════════════════════════════════════════════════════════════

async def _llm_generate(prompt: str, system: str = "You are AURA, an expert marketing copywriter.", max_tokens: int = 1500, skill_id: str = None) -> str:
    """Generate content via Emergent LLM Key with optional Marketing Skill system prompt."""
    # Use marketing skill system prompt if provided
    if skill_id:
        from services.marketing_skills import get_skill_system_prompt
        skill_system = get_skill_system_prompt(skill_id)
        if skill_system:
            system = skill_system
    try:
        from services.openrouter_client import call_model, FREE_MODELS
        result = await call_model(FREE_MODELS[0], system, prompt, temperature=0.7, max_tokens=max_tokens)
        content = result.get("content", "")
        if content and len(content) > 20:
            return content
    except Exception as e:
        logger.debug(f"[ContentEngine] OpenRouter failed: {e}")

    try:
        from emergentintegrations.llm.openai import chat_completion, OpenAiChatModel, SystemMessage, UserMessage
        emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if emergent_key:
            resp = await chat_completion(api_key=emergent_key, model=OpenAiChatModel.GPT_4O_MINI, messages=[SystemMessage(content=system), UserMessage(content=prompt)], max_tokens=max_tokens)
            return resp.choices[0].message.content or ""
    except Exception as e:
        logger.debug(f"[ContentEngine] Emergent fallback: {e}")

    return ""


async def generate_welcome_sequence(customer_name: str, business_name: str, industry: str = "", tenant_id: str = "aurem_platform") -> Dict:
    """Skill 1: Generate welcome email sequence for new customer."""
    check = await check_limit(tenant_id, "content_posts")
    if not check["allowed"]:
        return {"error": "limit_reached", "message": f"Content post limit reached ({check['used']}/{check['limit']}). Upgrade plan.", "tier": check["tier"]}

    prompt = f"""Write a 3-email welcome sequence for a new customer:
Customer: {customer_name}
Business: {business_name}
Industry: {industry or 'general'}

For each email provide:
- Subject line (compelling, <60 chars)
- Body (warm, professional, 100-150 words)
- CTA button text

Email 1: Welcome + value proposition (send immediately)
Email 2: Getting started guide (send day 2)
Email 3: Success story + upsell hint (send day 5)

Format as JSON array with keys: subject, body, cta, send_day"""

    content = await _llm_generate(prompt)
    await _increment_usage(tenant_id, "content_posts", 3)

    db = _get_db()
    seq_id = f"seq_{secrets.token_hex(6)}"
    if db:
        await db.content_engine_outputs.insert_one({
            "output_id": seq_id, "type": "welcome_sequence", "tenant_id": tenant_id,
            "customer_name": customer_name, "business_name": business_name,
            "content": content, "status": "generated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {"sequence_id": seq_id, "type": "welcome_sequence", "content": content, "emails": 3, "generated": bool(content)}


async def generate_campaign_copy(campaign_name: str, target_audience: str, platforms: List[str], tone: str = "professional", tenant_id: str = "aurem_platform") -> Dict:
    """Skill 2: Generate multi-platform campaign copy."""
    check = await check_limit(tenant_id, "content_posts")
    if not check["allowed"]:
        return {"error": "limit_reached", "message": f"Limit reached ({check['used']}/{check['limit']}). Upgrade plan.", "tier": check["tier"]}

    platform_specs = {"linkedin": 3000, "instagram": 2200, "twitter": 280, "facebook": 5000, "tiktok": 2200, "email": 2000}
    platform_list = "\n".join(f"- {p}: max {platform_specs.get(p, 2000)} chars" for p in platforms)

    prompt = f"""Write marketing copy for campaign: {campaign_name}
Target audience: {target_audience}
Tone: {tone}

Generate copy for each platform:
{platform_list}

For each platform provide:
- Headline (attention-grabbing)
- Body copy (platform-appropriate length)
- Hashtags (3-5 relevant)
- CTA

Format as JSON object with platform names as keys."""

    content = await _llm_generate(prompt, max_tokens=2000)
    await _increment_usage(tenant_id, "content_posts", len(platforms))

    db = _get_db()
    campaign_id = f"camp_{secrets.token_hex(6)}"
    if db:
        await db.content_engine_outputs.insert_one({
            "output_id": campaign_id, "type": "campaign_copy", "tenant_id": tenant_id,
            "campaign_name": campaign_name, "target_audience": target_audience,
            "platforms": platforms, "content": content, "status": "generated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {"campaign_id": campaign_id, "type": "campaign_copy", "platforms": platforms, "content": content, "generated": bool(content)}


async def generate_cold_outreach(lead_name: str, company: str, pain_point: str = "", tenant_id: str = "aurem_platform") -> Dict:
    """Skill 3: Generate personalized cold outreach email."""
    check = await check_limit(tenant_id, "content_posts")
    if not check["allowed"]:
        return {"error": "limit_reached", "message": f"Limit reached ({check['used']}/{check['limit']}). Upgrade plan.", "tier": check["tier"]}

    prompt = f"""Write a cold outreach email:
Lead: {lead_name} at {company}
Pain point: {pain_point or 'improving their business efficiency'}

Requirements:
- Subject line: personalized, <50 chars, no spam triggers
- Opening: reference their company specifically
- Body: 3-4 sentences max, focus on value not features
- CTA: soft ask (quick call, not hard sell)
- PS line: social proof or urgency

Format: subject, opening, body, cta, ps"""

    content = await _llm_generate(prompt, max_tokens=800)
    await _increment_usage(tenant_id, "content_posts", 1)

    db = _get_db()
    outreach_id = f"out_{secrets.token_hex(6)}"
    if db:
        await db.content_engine_outputs.insert_one({
            "output_id": outreach_id, "type": "cold_outreach", "tenant_id": tenant_id,
            "lead_name": lead_name, "company": company, "pain_point": pain_point,
            "content": content, "status": "generated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {"outreach_id": outreach_id, "type": "cold_outreach", "content": content, "generated": bool(content)}


async def generate_social_post(topic: str, platform: str = "linkedin", brand_voice: str = "professional", tenant_id: str = "aurem_platform") -> Dict:
    """Skill 4: Generate social media post using Marketing Skills."""
    check = await check_limit(tenant_id, "content_posts")
    if not check["allowed"]:
        return {"error": "limit_reached", "message": f"Limit reached ({check['used']}/{check['limit']}). Upgrade plan.", "tier": check["tier"]}

    # Auto-select marketing skill by platform
    platform_skills = {
        "instagram": "instagram_caption",
        "linkedin": "linkedin_post",
        "twitter": "twitter_thread",
        "tiktok": "tiktok_script",
        "youtube": "youtube_description",
        "pinterest": "pinterest_pin",
    }
    skill_id = platform_skills.get(platform)

    char_limits = {"twitter": 280, "instagram": 2200, "linkedin": 3000, "facebook": 5000, "tiktok": 2200, "bluesky": 300}
    limit = char_limits.get(platform, 2000)

    prompt = f"""Write a {platform} post about: {topic}
Brand voice: {brand_voice}. Max {limit} chars.
Include 3-5 relevant hashtags at the end.
Make it engaging, shareable, and professional.
Return ONLY the post text."""

    content = await _llm_generate(prompt, max_tokens=500, skill_id=skill_id)
    await _increment_usage(tenant_id, "content_posts", 1)

    return {"type": "social_post", "platform": platform, "content": content[:limit], "chars": len(content[:limit]), "limit": limit, "generated": bool(content), "skill_used": skill_id}


# ═══════════════════════════════════════════════════════════════
# IMAGE GENERATION — Emergent LLM Key (GPT Image 1)
# ═══════════════════════════════════════════════════════════════

async def generate_image(prompt: str, size: str = "1024x1024", tenant_id: str = "aurem_platform") -> Dict:
    """Generate marketing image via GPT Image 1 (Emergent Key). Returns base64 image."""
    check = await check_limit(tenant_id, "images")
    if not check["allowed"]:
        return {"error": "limit_reached", "message": f"Image limit reached ({check['used']}/{check['limit']}). Upgrade plan.", "tier": check["tier"]}

    try:
        import base64
        from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
        from dotenv import load_dotenv
        load_dotenv()
        emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not emergent_key:
            return {"error": "no_key", "message": "EMERGENT_LLM_KEY not configured"}

        image_gen = OpenAIImageGeneration(api_key=emergent_key)
        images = await image_gen.generate_images(prompt=prompt, model="gpt-image-1", number_of_images=1)

        if not images or len(images) == 0:
            return {"error": "empty", "message": "No image generated", "generated": False}

        image_b64 = base64.b64encode(images[0]).decode("utf-8")
        await _increment_usage(tenant_id, "images_generated", 1)

        # Save to uploads for serving
        img_id = f"img_{secrets.token_hex(8)}"
        upload_dir = "/app/backend/uploads/generated_images"
        os.makedirs(upload_dir, exist_ok=True)
        img_path = f"{upload_dir}/{img_id}.png"
        with open(img_path, "wb") as f:
            f.write(images[0])

        db = _get_db()
        if db:
            await db.content_engine_images.insert_one({
                "image_id": img_id, "tenant_id": tenant_id, "prompt": prompt[:200],
                "size": size, "file_path": img_path, "bytes": len(images[0]),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        return {
            "image_id": img_id,
            "image_base64": image_b64[:100] + "...",
            "image_base64_full": image_b64,
            "file_path": img_path,
            "size_bytes": len(images[0]),
            "prompt": prompt[:100],
            "generated": True,
        }
    except Exception as e:
        logger.warning(f"[ContentEngine] Image gen failed: {e}")
        return {"error": str(e), "generated": False}


# ═══════════════════════════════════════════════════════════════
# VIDEO GENERATION — Enterprise Tier Only (Muapi)
# ═══════════════════════════════════════════════════════════════

async def generate_video_content(
    product_name: str,
    product_description: str = "",
    image_url: str = None,
    style: str = "brand_story",
    platform: str = "instagram_reels",
    aspect_ratio: str = "9:16",
    duration: int = 5,
    tenant_id: str = "aurem_platform",
) -> Dict:
    """
    Enterprise-only: Generate marketing video via ModelsLab Seedance 2.
    1. Check tier (Enterprise required)
    2. Generate video prompt via LLM
    3. Call ModelsLab seedance2_multi_reference
    4. Generate caption + hashtags
    5. Track usage
    """
    # Gate: Enterprise only
    check = await check_limit(tenant_id, "videos_generated")
    if not check.get("allowed"):
        return {
            "error": "upgrade_required",
            "message": check.get("message", "Video generation requires Enterprise plan"),
            "tier": check.get("tier", "starter"),
        }

    video_id = f"vid_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc)

    # Step 1: Generate optimized video prompt via LLM
    platform_label = platform.replace("_", " ").title()
    style_label = style.replace("_", " ").title()

    prompt_instruction = (
        f"Write a concise, vivid video generation prompt (2-3 sentences max) for a {style_label} video "
        f"about the product '{product_name}'. {f'Product details: {product_description}.' if product_description else ''} "
        f"Target platform: {platform_label}. "
        f"Focus on visual movement, lighting, and cinematic quality. Do NOT include hashtags or captions. "
        f"Just the visual scene description."
    )
    video_prompt = await _llm_generate(prompt_instruction, system="You are AURA, a cinematic video prompt engineer. Write vivid, concise prompts.", max_tokens=300)
    if not video_prompt or len(video_prompt) < 10:
        video_prompt = f"Professional {style_label.lower()} showcasing {product_name}. Cinematic lighting, smooth camera movement, premium feel."

    # Step 2: Call Video Orchestrator (multi-provider fallback chain)
    from services.video_orchestrator import generate_video as orchestrate_video

    result = await orchestrate_video(
        prompt=video_prompt,
        image_url=image_url,
        duration=duration,
        aspect_ratio=aspect_ratio,
        tier=check.get("tier", "enterprise"),
    )

    if result.get("error"):
        return {"error": result["error"], "message": result.get("message", ""), "video_id": video_id, "generated": False}

    video_url = result.get("video_url")

    # Step 3: Generate caption + hashtags
    caption_prompt = (
        f"Write a short, engaging social media caption for a {style_label} video about '{product_name}' "
        f"on {platform_label}. Include 5-8 relevant hashtags. Keep it under 200 characters + hashtags."
    )
    caption_text = await _llm_generate(caption_prompt, max_tokens=300)

    # Step 4: Track usage
    await _increment_usage(tenant_id, "videos_generated")

    # Step 5: Save to DB
    db = _get_db()
    record = {
        "video_id": video_id,
        "tenant_id": tenant_id,
        "product_name": product_name,
        "product_description": product_description,
        "style": style,
        "platform": platform,
        "aspect_ratio": aspect_ratio,
        "duration": duration,
        "video_prompt": video_prompt,
        "video_url": video_url,
        "image_url": image_url,
        "caption": caption_text,
        "model": result.get("model", "seedance-2-multi-reference"),
        "mode": result.get("mode", "multi-ref" if image_url else "t2v"),
        "request_id": result.get("request_id", ""),
        "status": "completed",
        "created_at": now.isoformat(),
    }
    if db:
        await db.content_engine_videos.insert_one({**record})

    return {
        "video_id": video_id,
        "video_url": video_url,
        "video_prompt": video_prompt,
        "caption": caption_text,
        "model": result.get("model", "seedance-2-multi-reference"),
        "mode": result.get("mode", "multi-ref" if image_url else "t2v"),
        "platform": platform,
        "style": style,
        "generated": True,
    }


async def get_video_history(tenant_id: str = None, limit: int = 20) -> list:
    db = _get_db()
    if not db:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    return await db.content_engine_videos.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


# ═══════════════════════════════════════════════════════════════
# ONE-CLICK CAMPAIGN — Full pipeline
# ═══════════════════════════════════════════════════════════════

async def one_click_campaign(
    campaign_name: str,
    target_audience: str,
    platforms: List[str],
    generate_images: bool = True,
    auto_schedule: bool = False,
    tenant_id: str = "aurem_platform",
) -> Dict:
    """
    One-click: generates copy + images + schedules publish.
    CRM auto-trigger endpoint for full campaign generation.
    """
    campaign_id = f"fullcamp_{secrets.token_hex(6)}"
    results = {"campaign_id": campaign_id, "phases": {}}

    # Phase 1: Generate copy
    copy_result = await generate_campaign_copy(campaign_name, target_audience, platforms, tenant_id=tenant_id)
    results["phases"]["copy"] = {"status": "done" if copy_result.get("generated") else "failed", "campaign_id": copy_result.get("campaign_id")}

    if copy_result.get("error"):
        results["phases"]["copy"]["error"] = copy_result["error"]
        return results

    # Phase 2: Generate image
    if generate_images:
        img_result = await generate_image(
            f"Professional marketing banner for: {campaign_name}. Target: {target_audience}. Clean, modern design.",
            size="1536x1024", tenant_id=tenant_id,
        )
        results["phases"]["image"] = {"status": "done" if img_result.get("generated") else "failed", "url": img_result.get("url", "")}
    else:
        results["phases"]["image"] = {"status": "skipped"}

    # Phase 3: Generate video (Enterprise only — silent skip for other tiers)
    video_check = await check_limit(tenant_id, "videos_generated")
    if video_check.get("allowed"):
        try:
            vid_result = await generate_video_content(
                product_name=campaign_name,
                product_description=target_audience,
                style="social_ad",
                platform="instagram_reels",
                tenant_id=tenant_id,
            )
            results["phases"]["video"] = {
                "status": "done" if vid_result.get("generated") else "skipped",
                "video_url": vid_result.get("video_url", ""),
                "caption": vid_result.get("caption", ""),
            }
        except Exception as e:
            results["phases"]["video"] = {"status": "error", "error": str(e)}
    else:
        results["phases"]["video"] = {"status": "tier_locked", "tier": video_check.get("tier", "starter")}

    # Phase 4: Schedule via Social Media Service
    if auto_schedule and copy_result.get("content"):
        try:
            from services.social_media_service import publish_post, set_db as set_social_db
            set_social_db(_get_db())
            pub_result = await publish_post(copy_result["content"][:2000], platforms, tenant_id=tenant_id)
            results["phases"]["publish"] = {"status": "queued", "post_id": pub_result.get("post_id"), "platforms": platforms}
        except Exception as e:
            results["phases"]["publish"] = {"status": "error", "error": str(e)}
    else:
        results["phases"]["publish"] = {"status": "pending" if not auto_schedule else "skipped"}

    # Save full campaign
    db = _get_db()
    if db:
        await db.content_engine_campaigns.insert_one({
            "campaign_id": campaign_id, "tenant_id": tenant_id,
            "campaign_name": campaign_name, "target_audience": target_audience,
            "platforms": platforms, "results": results,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return results


# ═══════════════════════════════════════════════════════════════
# CRM AUTO-TRIGGER HOOKS
# ═══════════════════════════════════════════════════════════════

async def on_new_customer(customer_name: str, business_name: str, industry: str = "", tenant_id: str = "aurem_platform") -> Dict:
    """CRM Hook: New customer added → auto-generate welcome email sequence."""
    return await generate_welcome_sequence(customer_name, business_name, industry, tenant_id)


async def on_new_lead(lead_name: str, company: str, pain_point: str = "", tenant_id: str = "aurem_platform") -> Dict:
    """CRM Hook: New lead added → auto-generate cold outreach."""
    return await generate_cold_outreach(lead_name, company, pain_point, tenant_id)


async def on_campaign_created(campaign_name: str, target_audience: str, platforms: List[str] = None, tenant_id: str = "aurem_platform") -> Dict:
    """CRM Hook: Campaign created → auto-generate full campaign."""
    return await one_click_campaign(campaign_name, target_audience, platforms or ["linkedin", "instagram"], tenant_id=tenant_id)


async def get_content_history(tenant_id: str = None, limit: int = 20) -> List[Dict]:
    db = _get_db()
    if not db:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    return await db.content_engine_outputs.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


async def get_campaign_history(tenant_id: str = None, limit: int = 10) -> List[Dict]:
    db = _get_db()
    if not db:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    return await db.content_engine_campaigns.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
