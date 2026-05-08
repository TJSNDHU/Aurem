"""
AUREM MMX Service — MiniMax Multimodal CLI Wrapper
===================================================
Wraps mmx-cli (7 modalities) for ORA:
  mmx image    → product photos, social banners
  mmx video    → 30-sec promos (Enterprise tier)
  mmx speech   → TTS (30+ voices, alongside VoxCPM2)
  mmx vision   → ORA can analyze images customers send
  mmx search   → Scout Agent web search
  mmx music    → background music for videos

All calls route through subprocess → mmx CLI → MiniMax cloud.
No Legion GPU needed for video/image generation.
"""
import os
import json
import logging
import asyncio
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_db = None
MINIMAX_KEY = os.environ.get("MINIMAX_API_KEY", "")


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


def _key_flag() -> str:
    key = MINIMAX_KEY or os.environ.get("MINIMAX_API_KEY", "")
    return f"--api-key {key}" if key else ""


async def _run_mmx(args: str, timeout: int = 120) -> Dict:
    """Run mmx CLI command and parse output."""
    key = _key_flag()
    if not key:
        return {"error": "MINIMAX_API_KEY not set. Sign up free at platform.minimax.io", "configured": False}

    cmd = f"mmx {args} {key} --json 2>/dev/null || mmx {args} {key} 2>&1"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode().strip()

        # Try JSON parse
        try:
            return {"success": True, "data": json.loads(output)}
        except json.JSONDecodeError:
            if proc.returncode == 0 and output:
                return {"success": True, "data": {"raw": output}}
            return {"success": False, "error": output or stderr.decode().strip(), "exit_code": proc.returncode}

    except asyncio.TimeoutError:
        return {"success": False, "error": f"MMX command timed out ({timeout}s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# IMAGE GENERATION
# ═══════════════════════════════════════════════════════════════

async def generate_image(prompt: str, aspect: str = "1:1") -> Dict:
    """Generate image via mmx image. Returns file path."""
    result = await _run_mmx(f'image generate --prompt "{prompt}" --aspect-ratio {aspect}', timeout=60)
    if result.get("success"):
        img_id = f"mmx_img_{secrets.token_hex(6)}"
        db = _get_db()
        if db:
            await db.mmx_usage.insert_one({"type": "image", "prompt": prompt[:200], "id": img_id, "timestamp": datetime.now(timezone.utc).isoformat()})
        return {"image_id": img_id, "data": result["data"], "source": "minimax", "cost": "minimax_tokens"}
    return result


# ═══════════════════════════════════════════════════════════════
# VIDEO GENERATION (async — submit + poll + download)
# ═══════════════════════════════════════════════════════════════

async def generate_video(prompt: str) -> Dict:
    """Generate video via mmx video. Returns task_id for async polling."""
    result = await _run_mmx(f'video generate --prompt "{prompt}"', timeout=120)
    if result.get("success"):
        db = _get_db()
        if db:
            await db.mmx_usage.insert_one({"type": "video", "prompt": prompt[:200], "timestamp": datetime.now(timezone.utc).isoformat()})
    return result


async def check_video_status(task_id: str) -> Dict:
    return await _run_mmx(f'video task get --task-id {task_id}', timeout=15)


async def download_video(task_id: str) -> Dict:
    return await _run_mmx(f'video download --task-id {task_id}', timeout=60)


# ═══════════════════════════════════════════════════════════════
# SPEECH (TTS — 30+ voices)
# ═══════════════════════════════════════════════════════════════

async def synthesize_speech(text: str, voice: str = "English_magnetic_voiced_man") -> Dict:
    """TTS via mmx speech. 30+ voices available."""
    safe_text = text.replace('"', '\\"')[:2000]
    result = await _run_mmx(f'speech synthesize --text "{safe_text}" --voice {voice}', timeout=30)
    if result.get("success"):
        db = _get_db()
        if db:
            await db.mmx_usage.insert_one({"type": "speech", "chars": len(text), "voice": voice, "timestamp": datetime.now(timezone.utc).isoformat()})
    return result


async def list_voices() -> Dict:
    return await _run_mmx('speech voices', timeout=10)


# ═══════════════════════════════════════════════════════════════
# VISION (Image Understanding — ORA can SEE)
# ═══════════════════════════════════════════════════════════════

async def analyze_image(image_path: str, question: str = "Describe this image in detail.") -> Dict:
    """ORA vision — analyze an image and describe/answer questions about it."""
    safe_q = question.replace('"', '\\"')
    result = await _run_mmx(f'vision describe --file "{image_path}" --prompt "{safe_q}"', timeout=30)
    if result.get("success"):
        db = _get_db()
        if db:
            await db.mmx_usage.insert_one({"type": "vision", "question": question[:200], "timestamp": datetime.now(timezone.utc).isoformat()})
    return result


async def analyze_image_url(url: str, question: str = "Describe this image in detail.") -> Dict:
    safe_q = question.replace('"', '\\"')
    return await _run_mmx(f'vision describe --url "{url}" --prompt "{safe_q}"', timeout=30)


# ═══════════════════════════════════════════════════════════════
# SEARCH (Scout Agent web search)
# ═══════════════════════════════════════════════════════════════

async def web_search(query: str) -> Dict:
    """Web search via mmx search. Additional source for Scout Agent."""
    result = await _run_mmx(f'search query --query "{query}"', timeout=15)
    if result.get("success"):
        db = _get_db()
        if db:
            await db.mmx_usage.insert_one({"type": "search", "query": query[:200], "timestamp": datetime.now(timezone.utc).isoformat()})
    return result


# ═══════════════════════════════════════════════════════════════
# MUSIC (Background music for video content)
# ═══════════════════════════════════════════════════════════════

async def generate_music(prompt: str, duration: int = 30) -> Dict:
    """Generate background music for video content engine."""
    result = await _run_mmx(f'music generate --prompt "{prompt}"', timeout=120)
    if result.get("success"):
        db = _get_db()
        if db:
            await db.mmx_usage.insert_one({"type": "music", "prompt": prompt[:200], "timestamp": datetime.now(timezone.utc).isoformat()})
    return result


# ═══════════════════════════════════════════════════════════════
# STATUS & CONFIG
# ═══════════════════════════════════════════════════════════════

async def get_status() -> Dict:
    key = MINIMAX_KEY or os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        return {"configured": False, "setup": "Set MINIMAX_API_KEY in .env (free at platform.minimax.io)", "modalities": ["image", "video", "speech", "vision", "search", "music"]}
    quota = await _run_mmx('quota show', timeout=10)
    return {"configured": True, "version": "1.0.7", "modalities": ["image", "video", "speech", "vision", "search", "music"], "quota": quota.get("data", {})}


async def get_usage_stats() -> Dict:
    db = _get_db()
    if not db:
        return {"total": 0}
    pipeline = [{"$group": {"_id": "$type", "count": {"$sum": 1}}}, {"$project": {"_id": 0, "type": "$_id", "count": 1}}]
    results = await db.mmx_usage.aggregate(pipeline).to_list(20)
    return {"usage_by_type": {r["type"]: r["count"] for r in results}, "total": sum(r["count"] for r in results)}
