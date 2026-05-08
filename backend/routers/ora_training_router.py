"""
ORA Training Router — Language & Knowledge Training
=====================================================
Upload audio/docs or paste URLs to teach ORA new languages and knowledge.
"""

import os
import secrets
import logging
import aiohttp
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = "/app/backend/uploads/training"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

ALLOWED_EXTENSIONS = {
    # Audio
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".webm",
    # Documents
    ".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xlsx", ".xls", ".pptx",
    # Data
    ".json", ".xml", ".yaml", ".yml",
}

# File extensions that we can extract text from for knowledge-base training
TEXT_EXTRACTABLE = {".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml"}


def _extract_text_from_file(file_path: str, ext: str) -> str:
    """Extract plain text from an uploaded document.

    Returns empty string if the file type isn't text-extractable or extraction fails.
    Keeps imports lazy so the router boots even if a library is missing.
    """
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            parts = []
            for page in reader.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n\n".join(p for p in parts if p).strip()

        if ext == ".docx":
            import docx  # python-docx
            doc = docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs if p.text).strip()

        if ext in {".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml"}:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()

    except Exception as e:
        logger.warning(f"[ORA Training] Text extraction failed for {file_path}: {e}")
    return ""


async def _embed_single_file(file_id: str, text: str, filename: str, source_type: str):
    """Chunk + embed a single training doc and upsert vectors.

    Runs as a background task after upload so ORA can retrieve from it
    within seconds instead of waiting for a manual Force Sync.
    """
    try:
        from server import db as _db
        from services.embeddings import embed_text
        from routers.ora_knowledge_sync import _chunk_text

        chunks = _chunk_text(text, max_chars=2000)
        synced = 0
        for i, chunk in enumerate(chunks):
            try:
                embedding = embed_text(chunk)
                if embedding and any(v != 0.0 for v in embedding):
                    await _db.ora_knowledge_vectors.update_one(
                        {"file_id": file_id, "chunk_index": i},
                        {"$set": {
                            "file_id": file_id,
                            "chunk_index": i,
                            "filename": filename,
                            "source_type": source_type,
                            "text": chunk,
                            "embedding": embedding,
                            "synced_at": datetime.now(timezone.utc).isoformat(),
                        }},
                        upsert=True,
                    )
                    synced += 1
            except Exception as chunk_err:
                logger.warning(f"[ORA Training] Embed chunk {i} failed for {file_id}: {chunk_err}")

        # Mark file as ready once at least one chunk was embedded
        if synced > 0:
            await _db.ora_training_files.update_one(
                {"file_id": file_id},
                {"$set": {"status": "ready", "chunks_embedded": synced}},
            )
            logger.info(f"[ORA Training] Embedded {synced} chunks from {filename} ({file_id})")
        else:
            # Even without embeddings, keep the text available for keyword fallback
            logger.info(f"[ORA Training] No embeddings generated for {filename} — text still stored for keyword search")
    except Exception as e:
        logger.warning(f"[ORA Training] Background embedding failed for {file_id}: {e}")

LANGUAGE_OPTIONS = [
    "English", "French", "Spanish", "Arabic", "Hindi", "Punjabi",
    "Mandarin", "Cantonese", "Japanese", "Korean", "Portuguese",
    "German", "Italian", "Russian", "Turkish", "Vietnamese",
    "Thai", "Indonesian", "Malay", "Tagalog", "Urdu", "Bengali",
    "Dutch", "Swedish", "Polish", "Greek", "Hebrew", "Persian",
    "Other",
]

PURPOSE_OPTIONS = [
    "voice_clone",       # ElevenLabs voice cloning in target language
    "stt_training",      # Whisper STT improvement
    "language_pack",     # Language reference for responses
    "knowledge_base",    # Domain knowledge (docs, links)
]


def _get_user_id(authorization: Optional[str], ora_email: Optional[str] = None) -> str:
    """Identify the uploader.

    Priority:
      1. Platform JWT (Authorization: Bearer <token>) — full platform accounts
      2. ORA PWA email (from gate flow, passed as form field or header) —
         public PWA users who only completed the email/phone gate and never
         created a full platform account.

    Returns a stable user_id string so all of this user's training files land
    in the same bucket regardless of which surface they uploaded from.
    """
    import jwt

    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        if token:
            try:
                secret = os.environ.get("JWT_SECRET", "")
                payload = jwt.decode(token, secret, algorithms=["HS256"])
                return payload.get("user_id", payload.get("sub", payload.get("id", "unknown")))
            except jwt.ExpiredSignatureError:
                raise HTTPException(401, "Token expired")
            except Exception:
                # Fall through to email-based identification below
                pass

    if ora_email and "@" in ora_email:
        # PWA gate user — use a stable hashed prefix so the id is deterministic
        return f"ora_pwa:{ora_email.strip().lower()}"

    raise HTTPException(
        401,
        "Please open ORA and sign in with your email to teach it (or log into the full platform).",
    )


# ══════ UPLOAD FILE ══════════════════════════════════════════════

@router.post("/api/ora/training/upload")
async def upload_training_file(
    file: UploadFile = File(...),
    language: str = Form("English"),
    purpose: str = Form("knowledge_base"),
    notes: str = Form(""),
    ora_email: str = Form(""),
    authorization: str = Header(None),
    x_ora_email: str = Header(None, alias="X-Ora-Email"),
):
    from server import db
    # Accept either platform JWT or the ORA PWA gate email (form or header).
    user_id = _get_user_id(authorization, ora_email or x_ora_email)

    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Max {MAX_FILE_SIZE // (1024*1024)}MB")

    # Save file
    file_id = f"train_{secrets.token_urlsafe(16)}"
    safe_name = f"{file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    with open(file_path, "wb") as f:
        f.write(content)

    # Detect file category
    audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".webm"}
    file_category = "audio" if ext in audio_exts else "document"

    # Extract text for documents so the knowledge sync can embed them.
    # Without this, uploaded docs sit at status=uploaded forever and ORA
    # never actually learns from them.
    crawled_text = ""
    initial_status = "uploaded"
    if file_category == "document" and ext in TEXT_EXTRACTABLE:
        crawled_text = _extract_text_from_file(file_path, ext)
        if crawled_text:
            initial_status = "processed"  # eligible for /api/ora/knowledge/force-sync
            logger.info(f"[ORA Training] Extracted {len(crawled_text)} chars from {file.filename}")
        else:
            logger.info(f"[ORA Training] No text extracted from {file.filename} (scanned PDF or empty)")

    doc = {
        "file_id": file_id,
        "user_id": user_id,
        "source_type": "file",
        "filename": file.filename,
        "file_ext": ext,
        "file_category": file_category,
        "file_size": len(content),
        "file_path": file_path,
        "language": language,
        "purpose": purpose,
        "notes": notes,
        "status": initial_status,
        "crawled_text": crawled_text,
        "text_chars": len(crawled_text),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ora_training_files.insert_one(doc)

    # Fire-and-forget embedding so the doc is searchable immediately, not
    # only after an admin hits the Force Sync button.
    if crawled_text:
        import asyncio
        asyncio.create_task(_embed_single_file(file_id, crawled_text, file.filename, "file"))

    return {
        "file_id": file_id,
        "filename": file.filename,
        "file_category": file_category,
        "file_size": len(content),
        "text_chars": len(crawled_text),
        "language": language,
        "purpose": purpose,
        "status": initial_status,
        "message": (
            f"Training file '{file.filename}' uploaded and learning started."
            if crawled_text
            else f"Training file '{file.filename}' uploaded. No readable text extracted (scanned PDF or unsupported format)."
        ),
    }


# ══════ ADD WEB LINK ═════════════════════════════════════════════

class WebLinkRequest(BaseModel):
    url: str
    language: str = "English"
    purpose: str = "knowledge_base"
    notes: str = ""


@router.post("/api/ora/training/link")
async def add_training_link(body: WebLinkRequest, authorization: str = Header(None)):
    from server import db
    user_id = _get_user_id(authorization)

    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL — must start with http:// or https://")

    # Crawl the URL
    crawled_text = ""
    crawl_status = "pending"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20),
                                   headers={"User-Agent": "ORA-AI-Crawler/1.0"}) as resp:
                if resp.status != 200:
                    raise HTTPException(400, f"URL returned status {resp.status}")
                content_type = resp.headers.get("Content-Type", "")
                if "text" in content_type or "html" in content_type or "json" in content_type:
                    raw = await resp.text()
                    # Strip HTML tags for plain text
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(raw, "html.parser")
                    # Remove scripts/styles
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()
                    crawled_text = soup.get_text(separator="\n", strip=True)[:50000]
                    crawl_status = "crawled"
                else:
                    crawl_status = "unsupported_content"
                    crawled_text = f"Content-Type: {content_type} — binary content not parsed."
    except HTTPException:
        raise
    except Exception as e:
        crawl_status = "crawl_failed"
        crawled_text = str(e)

    file_id = f"link_{secrets.token_urlsafe(16)}"
    doc = {
        "file_id": file_id,
        "user_id": user_id,
        "source_type": "web_link",
        "url": url,
        "filename": url,
        "file_ext": ".url",
        "file_category": "web",
        "file_size": len(crawled_text),
        "crawled_text": crawled_text[:50000],
        "language": body.language,
        "purpose": body.purpose,
        "notes": body.notes,
        "status": crawl_status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ora_training_files.insert_one(doc)

    return {
        "file_id": file_id,
        "url": url,
        "file_category": "web",
        "crawled_length": len(crawled_text),
        "language": body.language,
        "purpose": body.purpose,
        "status": crawl_status,
        "message": f"Web content from '{url}' crawled ({len(crawled_text)} chars) and saved for training.",
    }


# ══════ LIST TRAINING DATA ═══════════════════════════════════════

@router.get("/api/ora/training/files")
async def list_training_files(authorization: str = Header(None)):
    from server import db
    user_id = _get_user_id(authorization)

    files = await db.ora_training_files.find(
        {"user_id": user_id},
        {"_id": 0, "file_path": 0, "crawled_text": 0}
    ).sort("created_at", -1).to_list(200)

    # Summary stats
    total = len(files)
    audio_count = sum(1 for f in files if f.get("file_category") == "audio")
    doc_count = sum(1 for f in files if f.get("file_category") == "document")
    web_count = sum(1 for f in files if f.get("file_category") == "web")
    languages = list(set(f.get("language", "Unknown") for f in files))

    return {
        "files": files,
        "total": total,
        "audio_count": audio_count,
        "doc_count": doc_count,
        "web_count": web_count,
        "languages": languages,
    }


# ══════ DELETE TRAINING FILE ═════════════════════════════════════

@router.delete("/api/ora/training/{file_id}")
async def delete_training_file(file_id: str, authorization: str = Header(None)):
    from server import db
    user_id = _get_user_id(authorization)

    doc = await db.ora_training_files.find_one(
        {"file_id": file_id, "user_id": user_id},
        {"_id": 0}
    )
    if not doc:
        # Idempotent: return success even if already deleted (race condition safe)
        return {"message": "Training file already deleted.", "file_id": file_id}

    # Delete physical file if it exists
    if doc.get("file_path") and os.path.exists(doc["file_path"]):
        os.remove(doc["file_path"])

    await db.ora_training_files.delete_one({"file_id": file_id, "user_id": user_id})

    return {"message": f"Training data '{doc.get('filename', file_id)}' deleted.", "file_id": file_id}


# ══════ GET LANGUAGES LIST ═══════════════════════════════════════

@router.get("/api/ora/training/languages")
async def get_language_options():
    return {"languages": LANGUAGE_OPTIONS, "purposes": PURPOSE_OPTIONS}



# ══════ MEDIA LINK (MOVIE/SONG) — Extract Audio & Detect Language ════

class MediaLinkRequest(BaseModel):
    url: str
    language: str = ""  # user-typed language name (overrides auto-detect)
    notes: str = ""


@router.post("/api/ora/training/media-link")
async def add_media_link(body: MediaLinkRequest, authorization: str = Header(None)):
    """
    User pastes a YouTube/media link → ORA:
    1. Extracts audio via yt-dlp
    2. Detects language via Whisper
    3. Stores as training data for voice cloning + STT
    """
    from server import db
    user_id = _get_user_id(authorization)

    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid URL — must start with http:// or https://")

    file_id = f"media_{secrets.token_urlsafe(16)}"
    audio_path = os.path.join(UPLOAD_DIR, f"{file_id}.mp3")
    now = datetime.now(timezone.utc).isoformat()

    # Step 1: Extract audio with yt-dlp
    import subprocess
    YT_DLP = "/root/.venv/bin/yt-dlp"
    try:
        result = subprocess.run(
            [YT_DLP, "--extract-audio", "--audio-format", "mp3",
             "--audio-quality", "5", "--max-filesize", "30m",
             "--no-playlist", "--js-runtimes", "node",
             "--remote-components", "ejs:github",
             "-o", audio_path, url],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            logger.warning(f"yt-dlp failed: {result.stderr[:300]}")
            raise Exception(result.stderr[:200] or "yt-dlp extraction failed")
    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Audio extraction timed out (120s limit)")
    except Exception as e:
        raise HTTPException(400, f"Could not extract audio: {str(e)[:200]}")

    if not os.path.exists(audio_path):
        raise HTTPException(400, "Audio extraction produced no output file")

    file_size = os.path.getsize(audio_path)

    # Get video title
    title = url
    try:
        info_result = subprocess.run(
            [YT_DLP, "--get-title", "--no-playlist", "--js-runtimes", "node", "--remote-components", "ejs:github", url],
            capture_output=True, text=True, timeout=15
        )
        if info_result.returncode == 0 and info_result.stdout.strip():
            title = info_result.stdout.strip()[:120]
    except Exception:
        pass

    # Step 2: Detect language — user override takes priority
    user_lang = body.language.strip() if body.language else ""
    detected_language = "Unknown"
    if user_lang:
        detected_language = user_lang
        logger.info(f"[Media] User specified language: {user_lang}")
    else:
        try:
            LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
            if LLM_KEY:
                from emergentintegrations.llm.openai import OpenAISpeechToText
                stt = OpenAISpeechToText(api_key=LLM_KEY)
                with open(audio_path, "rb") as audio_file:
                    result = await stt.transcribe(file=audio_file, response_format="verbose_json")
                if hasattr(result, 'language') and result.language:
                    detected_language = result.language.capitalize()
                elif isinstance(result, dict) and result.get('language'):
                    detected_language = result['language'].capitalize()
                logger.info(f"[Media] Whisper detected language: {detected_language} from {url}")
        except Exception as e:
            logger.warning(f"[Media] Whisper language detection failed: {e}")

    # Step 3: Store in training DB
    doc = {
        "file_id": file_id,
        "user_id": user_id,
        "source_type": "media_link",
        "url": url,
        "filename": title,
        "file_ext": ".mp3",
        "file_category": "audio",
        "file_size": file_size,
        "file_path": audio_path,
        "language": detected_language,
        "purpose": "voice_clone",
        "notes": body.notes or f"Extracted from: {title}",
        "status": "processed",
        "detected_language": detected_language,
        "original_url": url,
        "created_at": now,
    }
    await db.ora_training_files.insert_one(doc)

    return {
        "file_id": file_id,
        "title": title,
        "detected_language": detected_language,
        "file_size": file_size,
        "status": "processed",
        "message": f"Audio extracted from '{title}'. Language detected: {detected_language}. ORA is learning!",
    }
