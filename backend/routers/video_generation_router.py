"""
ReRoots AI Video Generation Router
Sora 2 powered video generation for product demos and marketing
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import secrets
import asyncio
import jwt as _jwt

router = APIRouter(prefix="/api/video-gen", tags=["video-generation"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


# Bug-fix #91 — Sora 2 video generation previously had ZERO auth and no
# rate-limit. An attacker spamming /generate with duration=12 model=sora-2-pro
# could drain the EMERGENT_LLM_KEY budget in minutes. /status leaked
# in-memory video_jobs dict including other users' prompts.
# Now: require JWT, enforce per-user daily quota (env-driven default 5),
# enforce duration<=12s ceiling, scope /status to caller.
DAILY_QUOTA_PER_USER = int(os.environ.get("VIDEO_GEN_DAILY_QUOTA", "5"))


def _verify_caller(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(503, "Auth not configured")
    try:
        payload = _jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    return payload


async def _check_quota(user_id: str) -> None:
    if db is None or not user_id:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    n = await db.video_generations.count_documents(
        {"created_by": user_id, "created_at": {"$gte": cutoff}}
    )
    if n >= DAILY_QUOTA_PER_USER:
        raise HTTPException(
            429,
            f"Daily video generation quota exceeded ({n}/{DAILY_QUOTA_PER_USER}). Try again in 24h.",
        )


class VideoGenerationRequest(BaseModel):
    prompt: str
    product_id: Optional[str] = None
    video_type: str = "product_demo"  # product_demo, testimonial, ad, tutorial
    size: str = "1280x720"  # 1280x720, 1792x1024, 1024x1792, 1024x1024
    duration: int = 4  # 4, 8, or 12 seconds
    model: str = "sora-2"  # sora-2 or sora-2-pro


class VideoStatus(BaseModel):
    video_id: str


# In-memory job tracker (in production, use Redis)
video_jobs = {}


@router.post("/generate")
async def generate_video(data: VideoGenerationRequest, background_tasks: BackgroundTasks, request: Request):
    """Start video generation job"""
    caller = _verify_caller(request)
    user_id = caller.get("user_id") or caller.get("sub") or caller.get("email") or "anon"
    await _check_quota(user_id)
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Video generation service not configured")
        
        # Validate parameters
        valid_sizes = ["1280x720", "1792x1024", "1024x1792", "1024x1024"]
        valid_durations = [4, 8, 12]
        
        if data.size not in valid_sizes:
            raise HTTPException(status_code=400, detail=f"Invalid size. Use: {valid_sizes}")
        if data.duration not in valid_durations:
            raise HTTPException(status_code=400, detail=f"Invalid duration. Use: {valid_durations}")
        
        # Create video job
        video_id = f"vid_{secrets.token_hex(12)}"
        output_path = f"/app/uploads/videos/{video_id}.mp4"
        
        # Enhance prompt for skincare context
        enhanced_prompt = enhance_video_prompt(data.prompt, data.video_type)
        
        # Store job record
        job_record = {
            "video_id": video_id,
            "prompt": data.prompt,
            "enhanced_prompt": enhanced_prompt,
            "product_id": data.product_id,
            "video_type": data.video_type,
            "size": data.size,
            "duration": data.duration,
            "model": data.model,
            "status": "processing",
            "output_path": output_path,
            "created_by": user_id,
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.video_generations.insert_one(job_record)
        video_jobs[video_id] = {"status": "processing"}
        
        # Start background generation
        background_tasks.add_task(
            generate_video_background,
            video_id, enhanced_prompt, output_path, data.model, data.size, data.duration
        )
        
        return {
            "video_id": video_id,
            "status": "processing",
            "estimated_time": f"{data.duration * 30}-{data.duration * 60} seconds",
            "message": "Video generation started. Check status endpoint for progress."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start generation: {str(e)}")


def enhance_video_prompt(prompt: str, video_type: str) -> str:
    """Enhance prompt with skincare brand context"""
    enhancements = {
        "product_demo": "Luxurious, high-end skincare product showcase with soft lighting, elegant movements, botanical elements, and premium packaging. ",
        "testimonial": "Authentic customer testimonial style, natural lighting, genuine expressions of satisfaction, before/after transformation feeling. ",
        "ad": "Eye-catching advertisement style with dynamic transitions, vibrant colors, modern aesthetic, and aspirational lifestyle imagery. ",
        "tutorial": "Clean, educational tutorial style with clear step-by-step visuals, close-up product application, and professional demonstration. "
    }
    
    prefix = enhancements.get(video_type, "")
    return f"{prefix}{prompt}"


async def generate_video_background(video_id: str, prompt: str, output_path: str, model: str, size: str, duration: int):
    """Background task for video generation"""
    try:
        from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration
        from dotenv import load_dotenv
        load_dotenv(override=False)
        
        # Ensure upload directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        video_gen = OpenAIVideoGeneration(api_key=os.environ['EMERGENT_LLM_KEY'])
        
        video_bytes = video_gen.text_to_video(
            prompt=prompt,
            model=model,
            size=size,
            duration=duration,
            max_wait_time=900  # 15 minutes max
        )
        
        if video_bytes:
            video_gen.save_video(video_bytes, output_path)
            
            # Update status
            video_jobs[video_id] = {"status": "completed", "path": output_path}
            await db.video_generations.update_one(
                {"video_id": video_id},
                {"$set": {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
        else:
            video_jobs[video_id] = {"status": "failed", "error": "No video bytes returned"}
            await db.video_generations.update_one(
                {"video_id": video_id},
                {"$set": {"status": "failed", "error": "Generation returned empty"}}
            )
            
    except Exception as e:
        video_jobs[video_id] = {"status": "failed", "error": str(e)}
        await db.video_generations.update_one(
            {"video_id": video_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )


@router.get("/status/{video_id}")
async def get_video_status(video_id: str, request: Request):
    """Check video generation status (scoped to creator)."""
    caller = _verify_caller(request)
    user_id = caller.get("user_id") or caller.get("sub") or caller.get("email") or "anon"
    is_admin = bool(caller.get("is_admin") or caller.get("is_super_admin")
                    or caller.get("role") in ("admin", "super_admin"))

    # Verify ownership before returning anything
    job = await db.video_generations.find_one({"video_id": video_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    if not is_admin and job.get("created_by") and job.get("created_by") != user_id:
        raise HTTPException(status_code=403, detail="Not your video")

    # In-memory status first
    if video_id in video_jobs:
        j = video_jobs[video_id]
        if j["status"] == "completed":
            return {
                "video_id": video_id,
                "status": "completed",
                "video_url": f"/api/video-gen/download/{video_id}"
            }
        elif j["status"] == "failed":
            return {"video_id": video_id, "status": "failed", "error": j.get("error")}
        else:
            return {"video_id": video_id, "status": "processing"}

    return {
        "video_id": video_id,
        "status": job.get("status"),
        "video_url": f"/api/video-gen/download/{video_id}" if job.get("status") == "completed" else None
    }


@router.get("/download/{video_id}")
async def download_video(video_id: str):
    """Download generated video"""
    from fastapi.responses import FileResponse
    
    job = await db.video_generations.find_one({"video_id": video_id})
    if not job:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Video not ready yet")
    
    output_path = job.get("output_path")
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"{video_id}.mp4"
    )


@router.get("/history")
async def get_video_history(limit: int = 20):
    """Get video generation history"""
    videos = await db.video_generations.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"videos": videos}


@router.post("/generate/product/{product_id}")
async def generate_product_video(product_id: str, background_tasks: BackgroundTasks, request: Request):
    """Generate video for a specific product"""
    _verify_caller(request)  # auth gate; generate_video will re-verify + quota
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Build prompt from product data
    prompt = f"Showcase video for {product.get('name', 'skincare product')}: {product.get('short_description', '')}. Highlight key benefits and luxurious packaging."

    return await generate_video(VideoGenerationRequest(
        prompt=prompt,
        product_id=product_id,
        video_type="product_demo",
        size="1280x720",
        duration=4
    ), background_tasks, request)
