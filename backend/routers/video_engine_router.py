"""
AUREM Video Engine Router — Remotion + FFmpeg Scaffold
POST /api/video/generate — queue video generation job
GET  /api/video/queue — list queue jobs
GET  /api/video/stats — queue statistics
POST /api/video/claim — Legion worker claims next job
POST /api/video/complete — worker marks job done
GET  /api/video/types — available video templates
GET  /api/video/download/{job_id} — download rendered video
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional

router = APIRouter(prefix="/api/video", tags=["Video Engine"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database
    from services.video_engine import set_db as _set
    _set(database)


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
    from services.video_engine import set_db as _set
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _set(server.db)
    except Exception:
        pass


class GenerateVideoRequest(BaseModel):
    video_type: str = "social_reel"
    title: str = "AUREM Video"
    content: Dict = {}
    priority: int = 5


@router.post("/generate")
async def generate_video(req: GenerateVideoRequest, authorization: str = Header(None)):
    """Queue a video generation job for Legion worker."""
    p = await _auth(authorization)
    _init()
    from services.video_engine import queue_video
    result = await queue_video(_tenant(p), req.video_type, req.title, req.content, req.priority)
    if not result.get("queued"):
        raise HTTPException(400, result.get("error", "Queue failed"))
    return result


@router.get("/queue")
async def queue_list(limit: int = 20, authorization: str = Header(None)):
    """List video queue jobs."""
    p = await _auth(authorization)
    _init()
    from services.video_engine import get_queue_status
    jobs = await get_queue_status(_tenant(p), limit)
    return {"jobs": jobs, "count": len(jobs)}


@router.get("/stats")
async def queue_stats(authorization: str = Header(None)):
    """Video queue statistics."""
    p = await _auth(authorization)
    _init()
    from services.video_engine import get_queue_stats
    return await get_queue_stats(_tenant(p))


@router.get("/types")
async def video_types(authorization: str = Header(None)):
    """List available video templates."""
    await _auth(authorization)
    from services.video_engine import VIDEO_TYPES
    return {"types": VIDEO_TYPES}


class ClaimRequest(BaseModel):
    worker_id: str


@router.post("/claim")
async def claim_job(req: ClaimRequest, authorization: str = Header(None)):
    """Legion worker claims next queued job."""
    await _auth(authorization)
    _init()
    from services.video_engine import claim_job
    job = await claim_job(req.worker_id)
    if not job:
        return {"claimed": False, "message": "No jobs in queue"}
    return {"claimed": True, "job": job}


class CompleteRequest(BaseModel):
    job_id: str
    output_path: str = ""
    error: str = ""


@router.post("/complete")
async def complete_job(req: CompleteRequest, authorization: str = Header(None)):
    """Worker marks job as completed or failed."""
    await _auth(authorization)
    _init()
    from services.video_engine import complete_job
    return await complete_job(req.job_id, req.output_path or None, req.error or None)


@router.get("/download/{job_id}")
async def download_video(job_id: str, authorization: str = Header(None)):
    """Download a rendered video."""
    await _auth(authorization)
    _init()
    from services.video_engine import _get_db
    db = _get_db()
    if not db:
        raise HTTPException(500, "Database unavailable")
    job = await db.video_queue.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") != "completed" or not job.get("output_path"):
        raise HTTPException(400, f"Video not ready. Status: {job.get('status')}")
    if not os.path.exists(job["output_path"]):
        raise HTTPException(404, "Video file not found on disk")
    return FileResponse(job["output_path"], media_type="video/mp4", filename=f"{job_id}.mp4")
