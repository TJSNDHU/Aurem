"""
AUREM Video Engine — Remotion + FFmpeg Scaffold
================================================
Queue system for video generation. Renders when Legion connects.
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


VIDEO_TYPES = {
    "product_showcase": {"label": "Product Showcase", "duration_s": 30, "resolution": "1080x1920", "format": "mp4"},
    "campaign_recap": {"label": "Campaign Recap", "duration_s": 45, "resolution": "1920x1080", "format": "mp4"},
    "testimonial": {"label": "Customer Testimonial", "duration_s": 20, "resolution": "1080x1080", "format": "mp4"},
    "social_reel": {"label": "Social Reel", "duration_s": 15, "resolution": "1080x1920", "format": "mp4"},
}

UPLOAD_DIR = "/app/backend/uploads/videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def queue_video(tenant_id: str, video_type: str, title: str, content: Dict, priority: int = 5) -> Dict:
    db = _get_db()
    if db is None:
        return {"queued": False, "error": "Database unavailable"}
    if video_type not in VIDEO_TYPES:
        return {"queued": False, "error": f"Unknown video type: {video_type}"}
    vtype = VIDEO_TYPES[video_type]
    job_id = f"vid_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "job_id": job_id, "tenant_id": tenant_id, "video_type": video_type,
        "title": title, "content": content, "status": "queued", "priority": priority,
        "duration_s": vtype["duration_s"], "resolution": vtype["resolution"],
        "format": vtype["format"], "output_path": None, "error": None,
        "worker_id": None, "created_at": now, "started_at": None, "completed_at": None,
    }
    await db.video_queue.insert_one(job)
    return {"queued": True, "job_id": job_id, "video_type": video_type, "status": "queued"}


async def get_queue_status(tenant_id: str = None, limit: int = 20) -> List[Dict]:
    db = _get_db()
    if db is None:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    cursor = db.video_queue.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(limit)


async def claim_job(worker_id: str) -> Optional[Dict]:
    db = _get_db()
    if db is None:
        return None
    job = await db.video_queue.find_one_and_update(
        {"status": "queued"},
        {"$set": {"status": "rendering", "worker_id": worker_id, "started_at": datetime.now(timezone.utc).isoformat()}},
        sort=[("priority", -1), ("created_at", 1)],
        return_document=True,
    )
    if job:
        job.pop("_id", None)
    return job


async def complete_job(job_id: str, output_path: str = None, error: str = None) -> Dict:
    db = _get_db()
    if db is None:
        return {"updated": False}
    status = "completed" if not error else "failed"
    await db.video_queue.update_one(
        {"job_id": job_id},
        {"$set": {"status": status, "output_path": output_path, "error": error, "completed_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"job_id": job_id, "status": status}


async def get_queue_stats(tenant_id: str = None) -> Dict:
    db = _get_db()
    if db is None:
        return {"total": 0}
    q = {"tenant_id": tenant_id} if tenant_id else {}
    total = await db.video_queue.count_documents(q)
    queued = await db.video_queue.count_documents({**q, "status": "queued"})
    rendering = await db.video_queue.count_documents({**q, "status": "rendering"})
    completed = await db.video_queue.count_documents({**q, "status": "completed"})
    failed = await db.video_queue.count_documents({**q, "status": "failed"})
    return {"total": total, "queued": queued, "rendering": rendering, "completed": completed, "failed": failed}
