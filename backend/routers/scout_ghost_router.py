import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
import base64

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
import jwt

from services.scout_stealth import launch_stealth_browser, warmup_decoy, close_safely
from services.scout_behavior import read_pause, maybe_abandon
from services.scout_storage import save_cold, summarize_for_cloud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scout/ghost", tags=["scout", "ghost"])
security = HTTPBearer()

_db: Optional[AsyncIOMotorDatabase] = None

def set_db(database: AsyncIOMotorDatabase):
    global _db
    _db = database

class GhostRunRequest(BaseModel):
    url: str
    decoy_level: int = Field(default=2, ge=0, le=5)
    proxy_url: Optional[str] = None
    proxy_user: Optional[str] = None
    proxy_pass: Optional[str] = None
    abandon_rate: float = Field(default=0.03, ge=0.0, le=1.0)

async def get_admin_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or invalid token")
    token = authorization.replace("Bearer ", "")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")
    
    email = (payload.get("email") or payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(status_code=401, detail="email missing in token")
    
    if payload.get("is_admin") or payload.get("is_super_admin"):
        return {"email": email, "is_admin": True}
    
    if not _db:
        raise HTTPException(status_code=500, detail="database not initialized")
    
    user = await _db.users.find_one({"email": email}, {"_id": 0, "is_admin": 1, "is_super_admin": 1})
    if not user:
        raise HTTPException(status_code=403, detail="user not found")
    if not (user.get("is_admin") or user.get("is_super_admin")):
        raise HTTPException(status_code=403, detail="admin access required")
    
    return {"email": email, "is_admin": True}

@router.get("/_/health")
async def health():
    return {"ok": True, "service": "scout-ghost", "camoufox_version": "0.4.11"}

@router.post("/run")
async def run_ghost(req: GhostRunRequest, user: dict = Depends(get_admin_user)):
    if not _db:
        raise HTTPException(status_code=500, detail="database not initialized")
    
    job_id = uuid.uuid4().hex
    cam = None
    browser = None
    
    try:
        proxy = None
        if req.proxy_url and req.proxy_user and req.proxy_pass:
            proxy = {
                "server": req.proxy_url,
                "username": req.proxy_user,
                "password": req.proxy_pass
            }
        
        cam, browser, ctx, page = await launch_stealth_browser(proxy=proxy, geoip=True)
        
        if req.decoy_level > 0:
            await warmup_decoy(page, req.decoy_level)
        
        if maybe_abandon(req.abandon_rate):
            await close_safely(cam, browser)
            logger.info(f"[scout-ghost] job {job_id} simulated_abandon")
            return {"ok": False, "job_id": job_id, "reason": "simulated_abandon"}
        
        await page.goto(req.url, wait_until="domcontentloaded")
        await read_pause(page)
        
        title = await page.title()
        html_content = await page.content()
        html_size = len(html_content)
        screenshot_bytes = await page.screenshot(full_page=False)
        
        captured_at = datetime.now(timezone.utc).isoformat()
        
        payload = {
            "job_id": job_id,
            "url": req.url,
            "title": title,
            "html_size": html_size,
            "captured_at": captured_at,
            "screenshot_b64": base64.b64encode(screenshot_bytes).decode("utf-8")
        }
        
        cold = await save_cold(job_id, payload)
        summary = summarize_for_cloud(payload)
        
        doc = {
            "job_id": job_id,
            "url": req.url,
            "title": title,
            "cold_path": cold["path"],
            "cold_sha256": cold["sha256"],
            "summary": summary,
            "captured_at": captured_at,
            "actor": user["email"]
        }
        await _db.scout_ghost_jobs.insert_one(doc)
        
        await close_safely(cam, browser)
        
        logger.info(f"[scout-ghost] job {job_id} completed: {req.url}")
        return {
            "ok": True,
            "job_id": job_id,
            "title": title,
            "html_size": html_size,
            "summary": summary,
            "cold_size_bytes": cold["size_bytes"]
        }
    
    except Exception as e:
        logger.exception(f"[scout-ghost] job {job_id} failed")
        await close_safely(cam, browser)
        return {"ok": False, "error": str(e)[:200]}

@router.get("/jobs")
async def list_jobs(limit: int = 20, user: dict = Depends(get_admin_user)):
    if not _db:
        raise HTTPException(status_code=500, detail="database not initialized")
    
    cursor = _db.scout_ghost_jobs.find(
        {},
        {"_id": 0, "job_id": 1, "url": 1, "title": 1, "captured_at": 1, "cold_size_bytes": 1}
    ).sort("captured_at", -1).limit(limit)
    
    jobs = await cursor.to_list(length=limit)
    
    for job in jobs:
        job.setdefault("cold_size_bytes", 0)
    
    return jobs