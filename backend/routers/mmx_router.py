"""
AUREM MMX Router — MiniMax Multimodal API
POST /api/mmx/image — generate image
POST /api/mmx/video — generate video (async)
POST /api/mmx/speech — text-to-speech (30+ voices)
POST /api/mmx/vision — analyze image (ORA sees)
POST /api/mmx/search — web search
POST /api/mmx/music — generate background music
GET  /api/mmx/status — config + quota
GET  /api/mmx/voices — list available TTS voices
GET  /api/mmx/usage — usage stats
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/mmx", tags=["MMX Multimodal"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        return jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _init():
    from services.mmx_service import set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass


class ImageRequest(BaseModel):
    prompt: str
    aspect: str = "1:1"


@router.post("/image")
async def generate_image(req: ImageRequest, authorization: str = Header(None)):
    await _auth(authorization)
    _init()
    from services.mmx_service import generate_image as _gen
    return await _gen(req.prompt, req.aspect)


class VideoRequest(BaseModel):
    prompt: str


@router.post("/video")
async def generate_video(req: VideoRequest, authorization: str = Header(None)):
    await _auth(authorization)
    _init()
    from services.mmx_service import generate_video as _gen
    return await _gen(req.prompt)


class SpeechRequest(BaseModel):
    text: str
    voice: str = "English_magnetic_voiced_man"


@router.post("/speech")
async def synthesize(req: SpeechRequest, authorization: str = Header(None)):
    await _auth(authorization)
    _init()
    from services.mmx_service import synthesize_speech
    return await synthesize_speech(req.text, req.voice)


class VisionRequest(BaseModel):
    url: str
    question: str = "Describe this image in detail."


@router.post("/vision")
async def vision(req: VisionRequest, authorization: str = Header(None)):
    await _auth(authorization)
    _init()
    from services.mmx_service import analyze_image_url
    return await analyze_image_url(req.url, req.question)


@router.post("/vision/upload")
async def vision_upload(
    file: UploadFile = File(...),
    question: str = Form("Describe this image in detail."),
    authorization: str = Header(None),
):
    await _auth(authorization)
    _init()
    upload_dir = "/app/backend/uploads/vision"
    os.makedirs(upload_dir, exist_ok=True)
    fpath = f"{upload_dir}/{file.filename}"
    with open(fpath, "wb") as f:
        f.write(await file.read())
    from services.mmx_service import analyze_image
    return await analyze_image(fpath, question)


class SearchRequest(BaseModel):
    query: str


@router.post("/search")
async def search(req: SearchRequest, authorization: str = Header(None)):
    await _auth(authorization)
    _init()
    from services.mmx_service import web_search
    return await web_search(req.query)


class MusicRequest(BaseModel):
    prompt: str


@router.post("/music")
async def music(req: MusicRequest, authorization: str = Header(None)):
    await _auth(authorization)
    _init()
    from services.mmx_service import generate_music
    return await generate_music(req.prompt)


@router.get("/status")
async def status(authorization: str = Header(None)):
    await _auth(authorization)
    _init()
    from services.mmx_service import get_status
    return await get_status()


@router.get("/voices")
async def voices(authorization: str = Header(None)):
    await _auth(authorization)
    from services.mmx_service import list_voices
    return await list_voices()


@router.get("/usage")
async def usage(authorization: str = Header(None)):
    await _auth(authorization)
    _init()
    from services.mmx_service import get_usage_stats
    return await get_usage_stats()
