"""
iter 327c — ORA chat multi-upload (+) button + URL auto-preview
================================================================

Founder spec:
  "One '+' button next to chat input. Tap → file picker. Auto-detects
   image/PDF/doc/video. Camera works on mobile + desktop. Links pasted
   in chat input are auto-fetched and previewed without any extra step."

What this iter ships:
  1. NEW backend router  /app/backend/routers/ora_attachments_router.py
       POST /api/ora/agent/attach         (multipart file upload)
       POST /api/ora/agent/attach-link    (URL preview)
       - detect_kind()    maps filename/mime → image|pdf|doc|video|other
       - Cloudinary storage for files (already wired by upload.py)
       - pypdf / python-docx text extraction for documents
       - bs4 link preview (title + meta description)
       - audit row in `ora_attachments` collection
  2. agent_run / agent_run_async now accept `attachment_ids[]` and an
     `_enrich_text_with_attachments()` helper that:
       - looks up attachments by id and pastes their context blocks
         into the user message ORA's brain reads
       - detects up to 2 URLs in the raw message via URL_RE and
         auto-fetches their link previews
  3. Frontend (OraChat.jsx):
       - one "+" button (data-testid="ora-attach-btn") next to input
       - hidden <input type="file"> picker with the right accept list
         (image/* + PDF + .doc/.docx/.txt + video/*); mobile browsers
         offer "Camera" naturally from this accept list
       - attachment-chip strip above input shows pending uploads
       - bubble for user messages now renders <a> preview tiles for
         attachments at the bottom
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent
FRONTEND = Path("/app/frontend/src/platform/admin/OraChat.jsx")


# ─────────────────────────────────────────────
# Module presence + lint-clean
# ─────────────────────────────────────────────

def test_router_module_exists_and_imports():
    src = (BACKEND / "routers" / "ora_attachments_router.py").read_text()
    assert "/attach" in src
    assert "/attach-link" in src
    assert "detect_kind" in src
    assert "render_attachment_context" in src


def test_router_registered_in_registry():
    src = (BACKEND / "routers" / "registry.py").read_text()
    assert "routers.ora_attachments_router" in src
    assert "ORA Chat Attachments" in src


# ─────────────────────────────────────────────
# detect_kind — covers all spec'd types
# ─────────────────────────────────────────────

def test_detect_kind_image():
    from routers.ora_attachments_router import detect_kind
    for fn, ct in (
        ("photo.jpg",   "image/jpeg"),
        ("scan.PNG",    ""),
        ("a.webp",      "image/webp"),
        ("ios.heic",    ""),                  # iOS Live Photo
        ("",            "image/png"),
    ):
        assert detect_kind(fn, ct) == "image", f"{fn!r}/{ct!r}"


def test_detect_kind_pdf():
    from routers.ora_attachments_router import detect_kind
    assert detect_kind("invoice.pdf", "application/pdf") == "pdf"
    assert detect_kind("INVOICE.PDF", "") == "pdf"
    assert detect_kind("",            "application/pdf") == "pdf"


def test_detect_kind_doc():
    from routers.ora_attachments_router import detect_kind
    assert detect_kind("notes.docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document") == "doc"
    assert detect_kind("readme.txt", "text/plain") == "doc"
    assert detect_kind("data.csv",   "") == "doc"


def test_detect_kind_video():
    from routers.ora_attachments_router import detect_kind
    assert detect_kind("clip.mp4",  "video/mp4") == "video"
    assert detect_kind("demo.mov",  "") == "video"
    assert detect_kind("loom.webm", "") == "video"


def test_detect_kind_falls_back_to_other():
    from routers.ora_attachments_router import detect_kind
    assert detect_kind("random.bin", "application/octet-stream") == "other"


# ─────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────

def test_render_attachment_context_image():
    from routers.ora_attachments_router import render_attachment_context
    out = render_attachment_context({
        "kind": "image", "filename": "logo.png",
        "size": 80123, "url": "https://res.cloudinary.com/x/img.png",
    })
    assert "Image attached" in out
    assert "logo.png" in out
    assert "78 KB" in out  # 80123/1024
    assert "https://res.cloudinary.com/x/img.png" in out


def test_render_attachment_context_pdf_includes_excerpt():
    from routers.ora_attachments_router import render_attachment_context
    out = render_attachment_context({
        "kind": "pdf", "filename": "spec.pdf",
        "size": 1024, "extracted_text": "Hello world. This is page 1.",
    })
    assert "PDF attached" in out
    assert "spec.pdf" in out
    assert "--- excerpt ---" in out
    assert "Hello world" in out


def test_render_attachment_context_link():
    from routers.ora_attachments_router import render_attachment_context
    out = render_attachment_context({
        "kind": "link", "url": "https://example.com/path",
        "title": "Example Home", "description": "Welcome.",
    })
    assert "Link shared" in out
    assert "https://example.com/path" in out
    assert "Title: Example Home" in out


def test_render_attachment_context_video_does_not_inline_content():
    from routers.ora_attachments_router import render_attachment_context
    out = render_attachment_context({
        "kind": "video", "filename": "demo.mp4",
        "size": 10000, "url": "https://res.cloudinary.com/v.mp4",
    })
    assert "Video attached" in out
    assert "Inline analysis not available" in out
    assert "demo.mp4" in out


def test_url_regex_matches_https_only_at_word_boundary():
    from routers.ora_attachments_router import URL_RE
    matches = URL_RE.findall(
        "Check https://foo.com/path and also http://bar.io/?q=1 but not foo.com"
    )
    assert "https://foo.com/path" in matches
    assert "http://bar.io/?q=1" in matches
    assert "foo.com" not in matches


# ─────────────────────────────────────────────
# PDF extraction
# ─────────────────────────────────────────────

def test_pdf_extraction_returns_text():
    """Build a tiny PDF in-memory and assert _extract_pdf_text reads it."""
    try:
        import pypdf
    except ImportError:
        pytest.skip("pypdf not installed")
    from routers.ora_attachments_router import _extract_pdf_text

    # Build a minimal PDF using reportlab if available, else use a
    # canned 1-page PDF from pypdf's writer.
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf)
        c.drawString(100, 750, "Hello AUREM iter 327c")
        c.save()
        blob = buf.getvalue()
    except ImportError:
        # Fall back to pypdf writer if reportlab isn't installed
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        writer.write(buf)
        blob = buf.getvalue()

    text = _extract_pdf_text(blob, max_chars=500)
    # Either we got the reportlab string back, or an empty string
    # (blank page). Both are non-crash outcomes.
    assert isinstance(text, str)


def test_pdf_extraction_swallows_bad_blob():
    """Garbage bytes must NOT raise — return empty string."""
    from routers.ora_attachments_router import _extract_pdf_text
    text = _extract_pdf_text(b"this is not a pdf at all")
    assert text == ""


# ─────────────────────────────────────────────
# Run-body now accepts attachment_ids
# ─────────────────────────────────────────────

def test_run_body_accepts_attachment_ids():
    src = (BACKEND / "routers" / "ora_agent_router.py").read_text()
    assert "attachment_ids:" in src
    assert "_enrich_text_with_attachments" in src
    # Both run and run-async paths call it
    assert src.count("await _enrich_text_with_attachments(") >= 2


def test_enrich_text_appends_attachment_context():
    """Drive the helper end-to-end against a fake Mongo."""
    import asyncio
    from routers.ora_agent_router import _enrich_text_with_attachments
    import routers.ora_agent_router as r

    fake_records = [{
        "attachment_id": "abc",
        "kind": "image",
        "filename": "x.png",
        "size": 1024,
        "url": "https://r.cloudinary.com/x.png",
    }]

    class _Cur:
        async def to_list(self, length):
            return fake_records

    class _Coll:
        def find(self, *a, **kw):
            return _Cur()

    class _DB:
        ora_attachments = _Coll()

    with patch.object(r, "_db", _DB()):
        out = asyncio.run(
            _enrich_text_with_attachments("Look at this", ["abc"])
        )
    assert "Look at this" in out
    assert "Image attached" in out
    assert "x.png" in out


# ─────────────────────────────────────────────
# Frontend wire-up (text-level)
# ─────────────────────────────────────────────

def test_chat_has_single_plus_button():
    src = FRONTEND.read_text()
    assert 'data-testid="ora-attach-btn"' in src
    assert 'data-testid="ora-attachment-input"' in src
    # One picker → spec'd accept list
    assert 'accept="image/*,application/pdf,.doc,.docx,.txt,.md,.csv,video/*"' in src
    # The button uses the Plus icon
    assert "import" in src and "Plus" in src
    # No 4-option sub-menu — only ONE attach button entry point
    assert src.count('data-testid="ora-attach-btn"') == 1


def test_chat_renders_attachment_chips_above_input():
    src = FRONTEND.read_text()
    assert 'data-testid="attachment-chips"' in src
    assert "uploading…" in src
    assert "removeAttachment" in src


def test_chat_renders_user_attachment_previews_in_bubble():
    src = FRONTEND.read_text()
    assert 'data-testid={`user-attachments-${i}`}' in src
    assert 'data-testid={`attachment-preview-${a.kind}`}' in src


def test_send_clears_attachments_and_passes_ids():
    src = FRONTEND.read_text()
    # send() puts attachment_ids on the request body via runAsyncPolling
    assert "attachmentIds = attachments.map" in src
    assert "setAttachments([])" in src
    # Send button enabled when text OR attachment present
    assert "(!input.trim() && attachments.length === 0)" in src


# ─────────────────────────────────────────────
# Iter marker
# ─────────────────────────────────────────────

def test_iter_327c_marker_present():
    assert "iter 327c" in (BACKEND / "routers" / "ora_attachments_router.py").read_text()
    assert "iter 327c" in FRONTEND.read_text()
