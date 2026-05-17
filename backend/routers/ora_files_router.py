"""
ORA Files Router — iter 322es
==============================
Multi-format file upload + analyze surface for the ORA Chat "Files &
Uploads" tab. Files are stored on local disk at
/mnt/uploads/{tenant_id}/ and indexed in `ora_uploaded_files`.

Endpoints (/api/admin/ora-files):
  POST   /upload                  multipart file → save to disk + index
  GET    /list?limit=50           recent uploads (newest first)
  GET    /{file_id}               metadata + analysis (if any)
  POST   /{file_id}/analyze       run ORA analysis (uses LLM gateway)
  DELETE /{file_id}               unlink file + remove index row

Supported MIME types: PDF, DOCX, TXT, MD, JPG/PNG/WEBP, MP3/WAV,
MP4/MOV. 30 MB cap per file.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter, File, Form, Header, HTTPException, UploadFile,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/ora-files", tags=["ora-files"])

UPLOAD_ROOT = Path("/mnt/uploads")
MAX_BYTES = 30 * 1024 * 1024  # 30 MB

ALLOWED_MIME = {
    # Documents
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain", "text/markdown",
    "application/json", "text/csv",
    # Images
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/heic",
    # Audio
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/x-wav",
    "audio/mp4", "audio/mp3",
    # Video
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/webm",
}

ALLOWED_EXT = {
    ".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".json",
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic",
    ".mp3", ".wav", ".ogg", ".mp4", ".mov", ".avi", ".webm",
}


def _verify_token(authorization: Optional[str] = None) -> dict:
    """Returns decoded JWT payload. Used for tenant_id sourcing."""
    if not authorization:
        raise HTTPException(401, "Authorization required")
    import jwt
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Authorization required")
    try:
        secret = os.environ.get("JWT_SECRET") or ""
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


def _get_db():
    from server import db
    if db is None:
        raise HTTPException(500, "Database not initialized")
    return db


def _tenant_id_from_payload(p: dict) -> str:
    return (
        p.get("tenant_id")
        or p.get("bin_id")
        or p.get("organization_id")
        or p.get("user_id")
        or p.get("sub")
        or "default"
    )


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    folder: str = Form("misc"),
    authorization: Optional[str] = Header(None),
):
    payload = _verify_token(authorization)
    tenant = _tenant_id_from_payload(payload)
    db = _get_db()

    # Mime + ext validation
    ct = (file.content_type or "").lower()
    ext = Path(file.filename or "").suffix.lower()
    if (ct not in ALLOWED_MIME) and (ext not in ALLOWED_EXT):
        raise HTTPException(415, f"unsupported file type: mime={ct!r} ext={ext!r}")

    # Bounded read so a malicious uploader can't pin the worker
    contents = await file.read(MAX_BYTES + 1)
    if len(contents) > MAX_BYTES:
        raise HTTPException(413, f"file exceeds {MAX_BYTES // (1024 * 1024)}MB cap")
    if not contents:
        raise HTTPException(400, "empty file")

    # Safe filename — strip path traversal
    safe_name = Path(file.filename or f"untitled{ext}").name
    file_id = uuid.uuid4().hex[:14]
    final_name = f"{file_id}__{safe_name}"

    # Persist
    target_dir = UPLOAD_ROOT / tenant / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / final_name
    target_path.write_bytes(contents)

    doc = {
        "id":          file_id,
        "tenant_id":   tenant,
        "user_id":     payload.get("user_id") or payload.get("sub"),
        "email":       payload.get("email"),
        "filename":    safe_name,
        "stored_path": str(target_path),
        "size_bytes":  len(contents),
        "mime_type":   ct or mimetypes.guess_type(safe_name)[0],
        "ext":         ext,
        "folder":      folder,
        "ts":          datetime.now(timezone.utc).isoformat(),
        "analysis":    None,
        "analyzed_at": None,
    }
    await db.ora_uploaded_files.insert_one(doc)
    return {
        "ok": True,
        "id": file_id,
        "filename": safe_name,
        "size_bytes": len(contents),
        "mime_type": doc["mime_type"],
        "stored_path": str(target_path),
        "tenant_id": tenant,
        "ts": doc["ts"],
    }


@router.get("/list")
async def list_files(
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    payload = _verify_token(authorization)
    tenant = _tenant_id_from_payload(payload)
    db = _get_db()
    rows = []
    cursor = (
        db.ora_uploaded_files.find(
            {"tenant_id": tenant},
            {"_id": 0, "stored_path": 0},
        )
        .sort("ts", -1)
        .limit(max(1, min(limit, 200)))
    )
    async for r in cursor:
        # Trim analysis preview to keep the list lightweight
        if r.get("analysis"):
            r["analysis_preview"] = (r["analysis"] or "")[:160]
            r.pop("analysis", None)
        rows.append(r)
    total = await db.ora_uploaded_files.count_documents({"tenant_id": tenant})
    return {"ok": True, "total": total, "rows": rows}


@router.get("/{file_id}")
async def get_file(file_id: str, authorization: Optional[str] = Header(None)):
    payload = _verify_token(authorization)
    tenant = _tenant_id_from_payload(payload)
    db = _get_db()
    doc = await db.ora_uploaded_files.find_one(
        {"id": file_id, "tenant_id": tenant}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "file not found")
    return {"ok": True, "file": doc}


class AnalyzeRequest(BaseModel):
    question: str = ""


@router.post("/{file_id}/analyze")
async def analyze_file(
    file_id: str,
    req: AnalyzeRequest,
    authorization: Optional[str] = Header(None),
):
    """Read the file's textual content (best-effort) and ask ORA for a
    summary or answer."""
    payload = _verify_token(authorization)
    tenant = _tenant_id_from_payload(payload)
    db = _get_db()
    doc = await db.ora_uploaded_files.find_one({"id": file_id, "tenant_id": tenant})
    if not doc:
        raise HTTPException(404, "file not found")

    path = doc.get("stored_path")
    if not path or not Path(path).is_file():
        raise HTTPException(410, "file no longer on disk")

    # Best-effort text extraction. Falls back to {mime, size} for binary.
    text = _best_effort_text(Path(path), doc.get("mime_type") or "")
    if not text:
        text = (
            f"[binary file: {doc.get('mime_type')}, "
            f"{doc.get('size_bytes')} bytes — text extraction not available]"
        )
    text = text[:30_000]  # cap

    q = (req.question or "Summarize this file's key contents and intent in 5-7 bullets.").strip()

    sys_prompt = (
        "You are ORA, AUREM's chief engineering AI. The founder uploaded "
        "a file for you to analyze. Be concrete: quote exact sections "
        "when possible, list concrete next-actions, flag risks plainly. "
        "Cap at 8 bullets unless the founder asks for more."
    )
    user_prompt = (
        f"FILE: {doc['filename']} ({doc.get('mime_type')}, "
        f"{doc.get('size_bytes')} bytes)\n\n"
        f"QUESTION: {q}\n\n"
        f"CONTENTS (first 30KB):\n```\n{text}\n```"
    )
    try:
        from services.llm_gateway import call_llm_with_meta
        res = await call_llm_with_meta(sys_prompt, user_prompt,
                                        max_tokens=700, bypass_cache=True)
        content = res.get("content") or ""
        provider = res.get("provider")
    except Exception as e:
        raise HTTPException(500, f"analysis failed: {type(e).__name__}: {e}")

    now = datetime.now(timezone.utc).isoformat()
    await db.ora_uploaded_files.update_one(
        {"id": file_id, "tenant_id": tenant},
        {"$set": {
            "analysis":      content,
            "analyzed_at":   now,
            "analysis_provider": provider,
            "analysis_question": q,
        }},
    )
    return {"ok": True, "id": file_id, "analysis": content,
             "provider": provider, "ts": now}


@router.delete("/{file_id}")
async def delete_file(file_id: str, authorization: Optional[str] = Header(None)):
    payload = _verify_token(authorization)
    tenant = _tenant_id_from_payload(payload)
    db = _get_db()
    doc = await db.ora_uploaded_files.find_one({"id": file_id, "tenant_id": tenant})
    if not doc:
        raise HTTPException(404, "file not found")
    path = doc.get("stored_path")
    try:
        if path and Path(path).is_file():
            Path(path).unlink()
    except Exception as e:
        logger.warning(f"[ora_files] unlink failed for {path}: {e}")
    await db.ora_uploaded_files.delete_one({"id": file_id, "tenant_id": tenant})
    return {"ok": True, "deleted": file_id}


@router.get("/_/health")
async def health():
    db = _get_db()
    n = await db.ora_uploaded_files.count_documents({})
    return {"ok": True, "scope": "ora_files",
             "total_indexed": n,
             "upload_root": str(UPLOAD_ROOT),
             "max_bytes": MAX_BYTES}


# ── Helpers ─────────────────────────────────────────────────────────────


def _best_effort_text(path: Path, mime: str) -> str:
    """Try to extract textual content. PDFs/DOCX use pypdf/docx if
    importable; otherwise return empty string."""
    try:
        # Plain text family
        if mime.startswith("text/") or path.suffix.lower() in {".txt", ".md", ".csv", ".json"}:
            return path.read_text("utf-8", errors="replace")
        # PDF
        if mime == "application/pdf" or path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                return "\n".join(
                    (page.extract_text() or "") for page in reader.pages[:30]
                )
            except Exception:
                pass
        # DOCX
        if path.suffix.lower() == ".docx":
            try:
                import docx  # python-docx
                d = docx.Document(str(path))
                return "\n".join(p.text for p in d.paragraphs)
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"[ora_files] text extract failed for {path}: {e}")
    return ""
