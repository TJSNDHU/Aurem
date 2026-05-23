"""
iter 327j — Three small wiring jobs in one shipment.

  1. Cosmetic log silencers (prod logs stay clean):
       - email_engine.py: consolidate 2 nested resend warnings → 1 INFO
       - ora_agent.py warmup (4 providers): WARNING → DEBUG
       - startup_validation.py: split REQUIRED vs OPTIONAL groups
       - memoir_service.py: git-not-found → DEBUG (never present in
         the deploy container; soft-fail by design)

  2. ORA Vision wiring:
       Run uploaded images through the existing
       `MultiModalProcessor._analyze_image` (GPT-4o vision) ONCE at
       upload time. Cache the description on `ora_attachments.
       vision_description` so future chat turns reuse it. Splice the
       description into the context block returned by
       `render_attachment_context`, so the LLM brain actually "sees"
       the pixels instead of just the filename + Cloudinary URL.

  3. Inline link unfurls:
       Extract `og:image`, `og:site_name`, `og:title`, favicon in
       `_link_preview`. Persist on the attachment row. Frontend
       `LinkPreviewCard` (new component) renders a rich card
       (image left + site/title/description right). Falls back to
       the old chip when no preview data is available.

The vision call is best-effort: a failing analyze still returns the
old filename+URL breadcrumb. No third email/vision system; reuses
what was already built in iter 322ar.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

BACKEND  = Path(__file__).resolve().parent.parent
FRONTEND = Path("/app/frontend/src/platform/admin/OraChat.jsx")


# ─────────────────────────────────────────────
# (1) Log silencers
# ─────────────────────────────────────────────

def test_email_engine_no_longer_double_warns_on_resend():
    src = (BACKEND / "services" / "email_engine.py").read_text()
    assert "resend top-level import failed" not in src
    assert "loaded Emails via resend.emails._emails fallback" not in src
    assert "resend top-level import quirky" in src
    assert "iter 327j" in src


def test_ora_agent_warmups_demoted_to_debug():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    # The 4 known warmup failure call-sites are at DEBUG, not WARNING.
    for provider in ("FreeLLMAPI", "Gemini", "NVIDIA", "DeepSeek"):
        warning_line = f'logger.warning(f"[ora-agent] {provider} warmup failed'
        debug_line = f'logger.debug(f"[ora-agent] {provider} warmup failed'
        assert warning_line not in src, f"{provider} still WARNs on warmup fail"
        assert debug_line in src, f"{provider} missing DEBUG log on warmup fail"


def test_startup_validation_splits_required_vs_optional():
    from bootstrap.startup_validation import OPTIONAL_GROUPS, EXPECTED
    # Optional groups must be a subset of EXPECTED keys.
    assert OPTIONAL_GROUPS.issubset(set(EXPECTED.keys()))
    # The three groups the founder doesn't want shouting in prod.
    assert "ollama_sovereign" in OPTIONAL_GROUPS
    assert "scraping" in OPTIONAL_GROUPS
    assert "groq_fallback" in OPTIONAL_GROUPS


def test_startup_validation_logs_optional_at_info_not_warning(caplog):
    """In a prod-like env where only OPTIONAL groups are missing,
    the validator must NOT emit a WARNING — just an INFO note."""
    import logging
    from bootstrap import startup_validation
    # Stub env: only OPTIONAL_GROUPS' vars are missing; required ones
    # are all set.
    required_vars = []
    for g, names in startup_validation.EXPECTED.items():
        if g not in startup_validation.OPTIONAL_GROUPS:
            required_vars.extend(names)

    fake_env = {k: "set" for k in required_vars}
    with patch.dict("os.environ", fake_env, clear=True):
        with caplog.at_level(logging.DEBUG, logger="bootstrap.startup_validation"):
            startup_validation.validate_environment()
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == [], (
        f"Expected zero WARNINGs when only OPTIONAL vars missing; got: "
        f"{[r.message for r in warnings]}"
    )
    infos = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert any("OPTIONAL env vars not set" in m for m in infos)


def test_memoir_git_missing_demoted_to_debug():
    src = (BACKEND / "services" / "memoir_service.py").read_text()
    # The git-not-found branch must DEBUG, not WARN.
    assert 'logger.debug(f"[memoir] init failed: {_INIT_ERROR}")' in src
    assert '"git binary not found" in _INIT_ERROR' in src


# ─────────────────────────────────────────────
# (2) Vision wiring
# ─────────────────────────────────────────────

def test_attach_handler_invokes_vision_for_images():
    """The image branch of POST /attach must call
    `MultiModalProcessor._analyze_image` and stash the result in
    `record['vision_description']`."""
    src = (BACKEND / "routers" / "ora_attachments_router.py").read_text()
    assert "MultiModalProcessor" in src or "get_multimodal_processor" in src
    assert "vision_description" in src
    assert 'kind == "image"' in src
    # The cache reuse is what stops us paying vision tokens twice.
    assert "_analyze_image" in src


def test_render_attachment_context_splices_vision_for_images():
    """Vision description must be injected into the chat-context
    block so the LLM brain actually 'sees' the image."""
    from routers.ora_attachments_router import render_attachment_context
    att = {
        "kind":     "image",
        "filename": "screenshot.jpg",
        "size":     200000,
        "url":      "https://res.cloudinary.com/a/b/screenshot.jpg",
        "vision_description":
            "A dashboard screenshot showing a 500 error on the campaigns page.",
    }
    out = render_attachment_context(att)
    assert "screenshot.jpg" in out
    assert "vision (GPT-4o description)" in out
    assert "500 error on the campaigns page" in out


def test_render_attachment_context_falls_back_when_no_vision():
    """If vision fails (or is empty), we degrade to the old
    filename+URL breadcrumb, never crash."""
    from routers.ora_attachments_router import render_attachment_context
    att = {
        "kind":     "image",
        "filename": "screenshot.jpg",
        "size":     200000,
        "url":      "https://res.cloudinary.com/a/b/screenshot.jpg",
        "vision_description": "",
    }
    out = render_attachment_context(att)
    assert "screenshot.jpg" in out
    assert "GPT-4o" not in out
    assert "vision" not in out.lower()


# ─────────────────────────────────────────────
# (3) Link unfurls
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_link_preview_extracts_og_image_site_and_favicon():
    from routers.ora_attachments_router import _link_preview

    html = """
    <html><head>
      <title>Plain Title</title>
      <meta property="og:title" content="OG Title Wins" />
      <meta name="description" content="Plain meta description text." />
      <meta property="og:image" content="https://cdn.example.com/cover.jpg" />
      <meta property="og:site_name" content="Example Mag" />
      <link rel="icon" href="/favicon.ico" />
    </head><body></body></html>
    """

    class _Resp:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}
        text = html

    class _Client:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, _url): return _Resp()

    with patch("httpx.AsyncClient", _Client):
        out = await _link_preview("https://example.com/articles/x")

    assert out["ok"] is True
    assert out["title"] == "OG Title Wins"             # og:title beats <title>
    assert out["description"] == "Plain meta description text."
    assert out["image"] == "https://cdn.example.com/cover.jpg"
    assert out["site_name"] == "Example Mag"
    # Favicon must be absolutized to the host.
    assert out["favicon"] == "https://example.com/favicon.ico"


@pytest.mark.asyncio
async def test_link_preview_falls_back_to_netloc_when_no_og_site():
    from routers.ora_attachments_router import _link_preview

    class _Resp:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html><head><title>X</title></head></html>"

    class _Client:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, _url): return _Resp()

    with patch("httpx.AsyncClient", _Client):
        out = await _link_preview("https://news.example.com/foo")

    assert out["site_name"] == "news.example.com"


def test_link_record_persists_image_site_favicon():
    src = (BACKEND / "routers" / "ora_attachments_router.py").read_text()
    for f in ('"image"', '"site_name"', '"favicon"'):
        assert f in src, f"link record missing {f} field"


def test_link_render_context_includes_site_and_image():
    from routers.ora_attachments_router import render_attachment_context
    att = {
        "kind":        "link",
        "url":         "https://example.com/a",
        "title":       "Hello World",
        "description": "Demo article",
        "image":       "https://cdn.example.com/c.jpg",
        "site_name":   "Example Mag",
    }
    out = render_attachment_context(att)
    assert "Example Mag" in out
    assert "Hello World" in out
    assert "https://cdn.example.com/c.jpg" in out


# ─────────────────────────────────────────────
# (3b) Frontend LinkPreviewCard
# ─────────────────────────────────────────────

def test_frontend_link_preview_card_component_present():
    src = FRONTEND.read_text()
    assert "function LinkPreviewCard" in src
    assert 'data-testid="attachment-preview-link-card"' in src
    # Render hooks: image, domain, title, description
    assert 'data-testid="link-card-image"' in src
    assert 'data-testid="link-card-domain"' in src
    assert 'data-testid="link-card-title"' in src
    assert 'data-testid="link-card-description"' in src
    # Old emoji-only chip removed from the main switch in favour of
    # the new card component.
    assert '<LinkPreviewCard key={j}' in src


def test_iter_327j_marker_present():
    assert "iter 327j" in (BACKEND / "services" / "email_engine.py").read_text()
    assert "iter 327j" in (BACKEND / "services" / "ora_agent.py").read_text()
    assert "iter 327j" in (BACKEND / "bootstrap" / "startup_validation.py").read_text()
    assert "iter 327j" in (BACKEND / "services" / "memoir_service.py").read_text()
    assert "iter 327j" in (BACKEND / "routers" / "ora_attachments_router.py").read_text()
    assert "iter 327j" in FRONTEND.read_text()
