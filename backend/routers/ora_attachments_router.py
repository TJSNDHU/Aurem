"""
ora_attachments_router.py — iter 327c

Single attach endpoint for the ORA-chat "+" button.

POST /api/ora/agent/attach
  multipart form-data with `file: UploadFile`   → upload file
  OR JSON  {"url": "https://..."}               → link preview only

Detects kind (image / pdf / doc / video / link), uploads file content
to Cloudinary, extracts text for documents, and stores an audit row
in `ora_attachments`. Returns a small JSON payload the chat UI
renders as a preview chip and ORA's brain reads as context on the
next turn.

Auth: founder/admin JWT via the same `get_admin_user` dep used by the
rest of the ORA chat router.
"""
from __future__ import annotations

import io
import logging
import mimetypes
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ora/agent", tags=["ora-agent-attach"])

_db = None
URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)


def set_db(database):
    global _db
    _db = database


# Reuse the admin-auth helper from the main ORA router so we share JWT logic
def _get_admin_dep():
    from routers.ora_agent_router import get_admin_user
    return get_admin_user


# ───────────────────────────────────────────────────────────────────
# Type detection
# ───────────────────────────────────────────────────────────────────

def detect_kind(filename: str, content_type: str = "") -> str:
    """Map (filename, mime) → one of: image | pdf | doc | video | other."""
    fn = (filename or "").lower()
    ct = (content_type or "").lower()
    if ct.startswith("image/") or fn.endswith((".jpg", ".jpeg", ".png",
                                                  ".gif", ".webp", ".heic", ".heif")):
        return "image"
    if ct == "application/pdf" or fn.endswith(".pdf"):
        return "pdf"
    if ct.startswith("video/") or fn.endswith((".mp4", ".mov", ".webm",
                                                  ".avi", ".mkv")):
        return "video"
    if (ct in ("application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/plain", "text/markdown")
            or fn.endswith((".doc", ".docx", ".txt", ".md", ".csv"))):
        return "doc"
    return "other"


# ───────────────────────────────────────────────────────────────────
# Content extraction (best-effort — long timeouts swallowed)
# ───────────────────────────────────────────────────────────────────

def _extract_pdf_text(blob: bytes, max_chars: int = 8000) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(blob))
        out = []
        for page in reader.pages[:20]:        # cap 20 pages
            try:
                out.append(page.extract_text() or "")
            except Exception:
                pass
            if sum(len(p) for p in out) > max_chars:
                break
        return ("\n".join(out))[:max_chars].strip()
    except Exception as e:
        logger.warning(f"[ora-attach] pdf extract failed: {e}")
        return ""


def _extract_docx_text(blob: bytes, max_chars: int = 8000) -> str:
    try:
        import docx
        d = docx.Document(io.BytesIO(blob))
        out = [p.text for p in d.paragraphs if p.text]
        return ("\n".join(out))[:max_chars].strip()
    except Exception as e:
        logger.warning(f"[ora-attach] docx extract failed: {e}")
        return ""


def _extract_text(blob: bytes, max_chars: int = 8000) -> str:
    try:
        return blob.decode("utf-8", errors="replace")[:max_chars].strip()
    except Exception:
        return ""


# ───────────────────────────────────────────────────────────────────
# Link preview
# ───────────────────────────────────────────────────────────────────

async def _link_preview(url: str) -> dict:
    out = {"url": url, "title": "", "description": "",
             "image": "", "site_name": "", "favicon": "",
             "ok": False}
    try:
        async with httpx.AsyncClient(timeout=12,
                                       follow_redirects=True,
                                       headers={
                                           "User-Agent": "Mozilla/5.0 (compatible; AUREM-OraBot/1.0)"
                                       }) as cli:
            r = await cli.get(url)
        if r.status_code >= 400:
            out["error"] = f"HTTP {r.status_code}"
            return out
        ct = r.headers.get("content-type", "").lower()
        if "text/html" not in ct:
            out["title"] = url.rsplit("/", 1)[-1] or url
            out["description"] = f"({ct or 'binary'} content)"
            out["ok"] = True
            return out
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin, urlparse
            soup = BeautifulSoup(r.text, "html.parser")
            # Title — prefer og:title for cleaner cards.
            og_title = soup.find("meta", attrs={"property": "og:title"})
            if og_title and og_title.get("content"):
                out["title"] = og_title["content"].strip()[:200]
            else:
                title_tag = soup.find("title")
                if title_tag and title_tag.string:
                    out["title"] = title_tag.string.strip()[:200]
            # Description.
            desc = (soup.find("meta", attrs={"name": "description"})
                    or soup.find("meta", attrs={"property": "og:description"}))
            if desc:
                out["description"] = (desc.get("content") or "").strip()[:400]
            # iter 327j — rich card fields: og:image, og:site_name,
            # favicon. Best-effort. All absolutized against the page
            # URL so relative paths work in the chat card.
            og_image = (soup.find("meta", attrs={"property": "og:image"})
                        or soup.find("meta", attrs={"name": "twitter:image"}))
            if og_image and og_image.get("content"):
                out["image"] = urljoin(url, og_image["content"].strip())[:800]
            og_site = soup.find("meta", attrs={"property": "og:site_name"})
            if og_site and og_site.get("content"):
                out["site_name"] = og_site["content"].strip()[:120]
            else:
                # Fall back to the netloc.
                try:
                    out["site_name"] = urlparse(url).netloc[:120]
                except Exception:
                    pass
            # Favicon — try the explicit link[rel=icon], else fall back
            # to /favicon.ico.
            icon = (soup.find("link", attrs={"rel": "icon"})
                    or soup.find("link", attrs={"rel": "shortcut icon"})
                    or soup.find("link", attrs={"rel": "apple-touch-icon"}))
            if icon and icon.get("href"):
                out["favicon"] = urljoin(url, icon["href"].strip())[:800]
            elif out.get("site_name"):
                try:
                    p = urlparse(url)
                    out["favicon"] = f"{p.scheme}://{p.netloc}/favicon.ico"
                except Exception:
                    pass
        except Exception:
            out["title"] = url
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e)[:140]}"
        return out


# ───────────────────────────────────────────────────────────────────
# Cloudinary uploader (mirrors routers/upload.py config)
# ───────────────────────────────────────────────────────────────────

async def _upload_to_cloudinary(blob: bytes, filename: str, kind: str) -> dict:
    """Best-effort upload to Cloudinary. Returns {url, public_id} or {} on fail."""
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )
        if not cloudinary.config().cloud_name:
            return {}
        # Use raw for non-image/video kinds
        rt = "image" if kind == "image" else "video" if kind == "video" else "raw"
        import asyncio
        result = await asyncio.to_thread(
            cloudinary.uploader.upload,
            blob,
            resource_type=rt,
            folder=f"ora_attachments/{datetime.now(timezone.utc):%Y-%m}",
            public_id=f"{uuid.uuid4().hex[:10]}-{filename[:32]}",
            use_filename=True,
            unique_filename=True,
        )
        return {"url": result.get("secure_url") or result.get("url"),
                "public_id": result.get("public_id"),
                "bytes":     result.get("bytes")}
    except Exception as e:
        logger.warning(f"[ora-attach] cloudinary upload failed: {e}")
        return {}


# ───────────────────────────────────────────────────────────────────
# POST /attach  (file)
# ───────────────────────────────────────────────────────────────────

@router.post("/attach")
async def attach_file(
    file: UploadFile = File(...),
    session_id: str = Form(default=""),
    user: dict = Depends(_get_admin_dep()),
):
    """Upload a single file. Auto-detects kind. Returns attachment metadata."""
    if not file.filename:
        raise HTTPException(400, "file has no filename")
    blob = await file.read()
    size = len(blob)
    if size > 25 * 1024 * 1024:                       # 25 MB cap
        raise HTTPException(413, "file too large (25 MB max)")
    kind = detect_kind(file.filename, file.content_type or "")
    extracted = ""
    if kind == "pdf":
        extracted = _extract_pdf_text(blob)
    elif kind == "doc":
        if file.filename.lower().endswith(".docx"):
            extracted = _extract_docx_text(blob)
        else:
            extracted = _extract_text(blob)

    storage = await _upload_to_cloudinary(blob, file.filename, kind)

    # iter 327j — Vision: if this is an image, run it through the
    # existing MultiModalProcessor._analyze_image (GPT-4o vision)
    # ONCE at upload time and stash the description on the
    # attachment row. Future chat turns reuse the cached description
    # so we don't pay vision tokens again for the same image. Best-
    # effort: failure here just leaves vision_description empty and
    # ORA falls back to the old "filename + URL" breadcrumb.
    vision_description = ""
    if kind == "image" and blob:
        try:
            from services.multimodal_processor import get_multimodal_processor
            proc = get_multimodal_processor()
            vision_description = await proc._analyze_image(
                blob, {"business_name": "AUREM ORA admin"}
            )
            vision_description = (vision_description or "").strip()[:2400]
        except Exception as e:
            logger.warning(f"[ora-attach] vision analysis failed: {e}")
            vision_description = ""

    attachment_id = uuid.uuid4().hex
    record = {
        "attachment_id":      attachment_id,
        "session_id":         session_id or None,
        "kind":               kind,
        "filename":           file.filename,
        "content_type":       file.content_type or
                              mimetypes.guess_type(file.filename)[0] or "",
        "size":               size,
        "url":                storage.get("url") or "",
        "storage_id":         storage.get("public_id") or "",
        "extracted_text":     extracted[:8000] if extracted else "",
        "vision_description": vision_description,
        "uploaded_by":        (user or {}).get("email") or (user or {}).get("user_id") or "",
        "ts":                 datetime.now(timezone.utc).isoformat(),
    }
    try:
        if _db is not None:
            await _db.ora_attachments.insert_one(dict(record))
    except Exception as e:
        logger.warning(f"[ora-attach] audit insert failed: {e}")
    # Strip Mongo _id before responding
    record.pop("_id", None)
    return {"ok": True, "attachment": record}


# ───────────────────────────────────────────────────────────────────
# POST /attach-link  (URL preview)
# ───────────────────────────────────────────────────────────────────

class LinkBody(BaseModel):
    url: str
    session_id: Optional[str] = ""


@router.post("/attach-link")
async def attach_link(body: LinkBody, user: dict = Depends(_get_admin_dep())):
    url = (body.url or "").strip()
    if not URL_RE.fullmatch(url):
        raise HTTPException(400, "invalid url")
    preview = await _link_preview(url)
    attachment_id = uuid.uuid4().hex
    record = {
        "attachment_id":  attachment_id,
        "session_id":     body.session_id or None,
        "kind":           "link",
        "url":            url,
        "title":          preview.get("title", ""),
        "description":    preview.get("description", ""),
        "image":          preview.get("image", ""),       # iter 327j
        "site_name":      preview.get("site_name", ""),   # iter 327j
        "favicon":        preview.get("favicon", ""),     # iter 327j
        "ok":             preview.get("ok", False),
        "error":          preview.get("error", ""),
        "uploaded_by":    (user or {}).get("email") or (user or {}).get("user_id") or "",
        "ts":             datetime.now(timezone.utc).isoformat(),
    }
    try:
        if _db is not None:
            await _db.ora_attachments.insert_one(dict(record))
    except Exception as e:
        logger.warning(f"[ora-attach-link] audit insert failed: {e}")
    record.pop("_id", None)
    return {"ok": True, "attachment": record}


# ───────────────────────────────────────────────────────────────────
# Helpers exposed for ORA's run loop
# ───────────────────────────────────────────────────────────────────

def render_attachment_context(att: dict) -> str:
    """Convert an attachment record into a short text block that gets
    appended to the user's chat message so the LLM brain can "see"
    the upload. Kept compact to save tokens."""
    if not att:
        return ""
    kind = att.get("kind", "other")
    if kind == "image":
        # iter 327j — splice the GPT-4o vision description (cached at
        # upload time) into the context block so the LLM brain
        # actually "sees" the pixels instead of just the filename.
        vision = (att.get("vision_description") or "").strip()
        header = (f"\n\n[Image attached: {att.get('filename','image')} "
                  f"({att.get('size',0)//1024} KB) — url: {att.get('url','')}]")
        if vision:
            return (
                f"{header}\n"
                f"--- vision (GPT-4o description) ---\n"
                f"{vision}\n"
                f"--- end vision ---"
            )
        return header
    if kind == "pdf":
        excerpt = (att.get("extracted_text") or "").strip()
        head = excerpt[:2500] + ("…" if len(excerpt) > 2500 else "")
        return (f"\n\n[PDF attached: {att.get('filename','document.pdf')} "
                f"({att.get('size',0)//1024} KB)]\n"
                f"--- excerpt ---\n{head}\n--- end excerpt ---")
    if kind == "doc":
        excerpt = (att.get("extracted_text") or "").strip()
        head = excerpt[:2500] + ("…" if len(excerpt) > 2500 else "")
        return (f"\n\n[Document attached: {att.get('filename','document')} "
                f"({att.get('size',0)//1024} KB)]\n"
                f"--- excerpt ---\n{head}\n--- end excerpt ---")
    if kind == "video":
        return (f"\n\n[Video attached: {att.get('filename','video.mp4')} "
                f"— url: {att.get('url','')}. Inline analysis not available; "
                f"the founder can describe what's in it.]")
    if kind == "link":
        # iter 327j — include site_name + image hint so the LLM has
        # the same context the rich-card UI shows the founder.
        parts = [f"[Link shared: {att.get('url','')}"]
        if att.get("site_name"):
            parts.append(f"Site: {att['site_name']}")
        parts.append(f"Title: {att.get('title','(no title)')}")
        if att.get("description"):
            parts.append(f"Description: {att['description']}")
        if att.get("image"):
            parts.append(f"Preview image: {att['image']}")
        return "\n\n" + "\n".join(parts) + "]"
    return ""
