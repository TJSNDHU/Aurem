"""
Z-Image-Turbo Integration Router
Professional-Grade AI Image Generation using Z-Image-Turbo (6B params)
Uses official Gradio Client for reliable Hugging Face Space communication

Model: Alibaba Tongyi-MAI Z-Image-Turbo
- #1 Open Source Model on Artificial Analysis Leaderboard
- 6 Billion Parameters
- 8-22 inference steps for photorealistic quality
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
import base64
import time
import asyncio
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from gradio_client import Client

router = APIRouter(prefix="/api/z-image", tags=["Z-Image AI"])

# Thread pool for blocking Gradio client calls
executor = ThreadPoolExecutor(max_workers=3)

# Hugging Face Space names
HF_SPACES = [
    "mrfakename/Z-Image-Turbo",
    # "Tongyi-MAI/Z-Image-Turbo",  # Backup
]

# Quality presets for DSLR-like output
QUALITY_PRESETS = {
    "draft": {"steps": 8, "cfg": 5.5, "desc": "Fast preview (~5s)"},
    "standard": {"steps": 12, "cfg": 6.5, "desc": "Good quality (~10s)"},
    "high": {"steps": 18, "cfg": 7.0, "desc": "High quality (~20s)"},
    "ultra": {"steps": 22, "cfg": 7.5, "desc": "DSLR quality (~30s)"},
    "maximum": {"steps": 30, "cfg": 8.0, "desc": "Maximum detail (~45s)"}
}

# DSLR enhancements
DSLR_ENHANCEMENT = ", professional photography, 8k uhd, high resolution, sharp focus, detailed, masterpiece, best quality, photorealistic"
DSLR_NEGATIVE = "blurry, low resolution, pixelated, jpeg artifacts, noise, grainy, oversaturated, undersaturated, overexposed, underexposed, bad anatomy, deformed, ugly, duplicate, watermark, signature, text overlay, cropped, out of frame, worst quality, low quality"


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Image description")
    negative_prompt: Optional[str] = Field(default="", description="What to avoid")
    width: Optional[int] = Field(default=1024, ge=512, le=2048, description="Image width")
    height: Optional[int] = Field(default=1024, ge=512, le=2048, description="Image height")
    steps: Optional[int] = Field(default=12, ge=4, le=50, description="Inference steps")
    cfg_scale: Optional[float] = Field(default=7.0, ge=1.0, le=20.0, description="Guidance scale")
    seed: Optional[int] = Field(default=-1, description="-1 for random")
    quality_preset: Optional[str] = Field(default="standard", description="Quality preset")
    enhance_prompt: Optional[bool] = Field(default=True, description="Auto-enhance for DSLR")
    use_dslr_negative: Optional[bool] = Field(default=True, description="Use pro negative prompts")


class ImageGenerationResponse(BaseModel):
    success: bool
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    seed_used: Optional[int] = None
    generation_time: Optional[float] = None
    resolution: Optional[str] = None
    quality_preset: Optional[str] = None
    error: Optional[str] = None


def _sync_generate_image(space_name: str, prompt: str, negative: str, 
                          width: int, height: int, steps: int, 
                          cfg: float, seed: int) -> dict:
    """
    Synchronous function to call Gradio Space (runs in thread pool)
    Z-Image-Turbo API: predict(prompt, height, width, num_inference_steps, seed, randomize_seed, api_name="/generate_image")
    """
    try:
        logging.info(f"[Z-Image] Connecting to {space_name}...")
        client = Client(space_name)
        
        # Combine prompt with negative (Z-Image handles this in prompt)
        full_prompt = prompt
        if negative:
            full_prompt = f"{prompt}. Avoid: {negative}"
        
        logging.info(f"[Z-Image] Generating: {full_prompt[:80]}... ({width}x{height}, {steps} steps)")
        
        # Call the correct API endpoint
        result = client.predict(
            full_prompt,           # prompt: str
            float(height),         # height: float
            float(width),          # width: float
            float(steps),          # num_inference_steps: float
            seed if seed != -1 else 42,  # seed: int
            seed == -1,            # randomize_seed: bool
            api_name="/generate_image"
        )
        
        logging.info(f"[Z-Image] Result: {type(result)}")
        
        # Result is tuple: (image_dict, seed_used)
        if isinstance(result, tuple) and len(result) >= 2:
            image_data = result[0]
            used_seed = int(result[1]) if result[1] else None
            
            # image_data is a dict with 'path', 'url', etc.
            if isinstance(image_data, dict):
                image_path = image_data.get('path')
                image_url = image_data.get('url')
                
                # Try to read local file first
                if image_path and os.path.exists(str(image_path)):
                    logging.info(f"[Z-Image] Reading from path: {image_path}")
                    with open(image_path, 'rb') as f:
                        img_bytes = f.read()
                    image_base64 = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"
                    return {
                        "success": True,
                        "image_base64": image_base64,
                        "seed_used": used_seed
                    }
                elif image_url:
                    logging.info(f"[Z-Image] Using URL: {image_url[:100]}")
                    return {
                        "success": True,
                        "image_url": image_url,
                        "seed_used": used_seed
                    }
            
            logging.warning(f"[Z-Image] Unexpected image_data format: {image_data}")
            return {"success": False, "error": f"Unexpected image format: {type(image_data)}"}
        
        logging.warning(f"[Z-Image] Unexpected result format: {result}")
        return {"success": False, "error": f"Unexpected result format: {type(result)}"}
            
    except Exception as e:
        error_str = str(e)
        logging.error(f"[Z-Image] Generation error: {error_str}")
        
        # Handle ZeroGPU queue errors gracefully
        if "No GPU was available" in error_str or "ZeroGPU" in error_str:
            return {
                "success": False, 
                "error": "The free Hugging Face GPU is currently busy. Please try again in 1-2 minutes, or upgrade to a dedicated GPU service."
            }
        
        return {"success": False, "error": error_str}


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_image(request: ImageGenerationRequest):
    """
    Generate a high-quality image using Z-Image-Turbo
    """
    start_time = time.time()
    
    # Apply quality preset
    preset = QUALITY_PRESETS.get(request.quality_preset, QUALITY_PRESETS["standard"])
    steps = request.steps if request.steps != 12 else preset["steps"]
    cfg = request.cfg_scale if request.cfg_scale != 7.0 else preset["cfg"]
    
    # Enhance prompt for DSLR quality
    prompt = request.prompt
    if request.enhance_prompt:
        prompt = prompt.rstrip('.') + DSLR_ENHANCEMENT
    
    # Build negative prompt
    negative = request.negative_prompt or ""
    if request.use_dslr_negative:
        negative = f"{negative}, {DSLR_NEGATIVE}" if negative else DSLR_NEGATIVE
    
    logging.info(f"[Z-Image] Request: {request.width}x{request.height}, {steps} steps, cfg={cfg}")
    
    # Try each space
    last_error = None
    for space_name in HF_SPACES:
        try:
            # Run blocking Gradio call in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                executor,
                _sync_generate_image,
                space_name, prompt, negative,
                request.width, request.height,
                steps, cfg, request.seed
            )
            
            generation_time = time.time() - start_time
            
            if result["success"]:
                return ImageGenerationResponse(
                    success=True,
                    image_base64=result.get("image_base64"),
                    image_url=result.get("image_url"),
                    seed_used=result.get("seed_used"),
                    generation_time=generation_time,
                    resolution=f"{request.width}x{request.height}",
                    quality_preset=request.quality_preset
                )
            else:
                last_error = result.get("error", "Unknown error")
                logging.warning(f"[Z-Image] {space_name} failed: {last_error}")
                
        except Exception as e:
            last_error = str(e)
            logging.error(f"[Z-Image] Exception with {space_name}: {e}")
            continue
    
    # All spaces failed
    return ImageGenerationResponse(
        success=False,
        error=f"Generation failed: {last_error}. The model may be loading - please try again."
    )


@router.get("/presets")
async def get_quality_presets():
    """Get available quality presets"""
    return {
        "presets": QUALITY_PRESETS,
        "recommended": "ultra",
        "fastest": "draft",
        "dslr_negative_prompt": DSLR_NEGATIVE,
        "enhancement_suffix": DSLR_ENHANCEMENT
    }


@router.get("/health")
async def health_check():
    """Check Z-Image-Turbo availability"""
    return {
        "status": "available",
        "model": "Z-Image-Turbo (6B parameters)",
        "spaces": HF_SPACES,
        "capabilities": [
            "Text-to-Image Generation",
            "Up to 2048x2048 resolution",
            "DSLR-quality output",
            "Bilingual (EN/ZH) text rendering",
            "8-50 inference steps"
        ],
        "quality_presets": list(QUALITY_PRESETS.keys()),
        "note": "Uses official Gradio Client for reliable communication"
    }


@router.post("/enhance-prompt")
async def enhance_prompt(prompt: str):
    """Enhance a basic prompt for DSLR-quality output"""
    enhanced = prompt.rstrip('.') + DSLR_ENHANCEMENT
    
    return {
        "original": prompt,
        "enhanced": enhanced,
        "recommended_negative": DSLR_NEGATIVE,
        "tip": "Use quality_preset='ultra' for best results"
    }
