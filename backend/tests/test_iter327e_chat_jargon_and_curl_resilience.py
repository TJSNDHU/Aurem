"""
iter 327e — Three fixes after founder reported (2026-02-23):

  1. curl_internal threw `FileNotFoundError: 'curl'` because the
     binary was missing on her Legion pod. Switched the tool to
     httpx (already a backend dep) so it survives any pod.

  2. ORA pasted raw tool-call syntax into chat —
     `curl_internal(endpoint="/api/platform/warm-prober", method="GET")`
     — instead of speaking plainly. Extended
     `_looks_like_unhandled_tool_call` to detect Python-call style
     leaks for any registered tool name.

  3. Raw tracebacks (FileNotFoundError, [Errno 2]) bled from tool
     results into the LLM context and the LLM regurgitated them
     verbatim. Added `_humanize_tool_error` so the error envelope
     reads plain English BEFORE the LLM ever sees it.

  4. (UI) Added a collapse button to the desktop ORA-CTO sidebar.
     Verified in OraAdminUnified.jsx.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent
ORA_ADMIN_UNIFIED = Path("/app/frontend/src/platform/admin/OraAdminUnified.jsx")


# ─────────────────────────────────────────────
# Fix 1: curl_internal now uses httpx
# ─────────────────────────────────────────────

def test_curl_internal_does_not_subprocess_curl():
    """The function body must no longer invoke the curl binary."""
    src = (BACKEND / "services" / "ora_tools.py").read_text()
    # Find the function
    start = src.index("async def curl_internal(")
    end = src.index("\n\n\nasync def db_count(", start)
    body = src[start:end]
    assert '"curl"' not in body, "curl_internal still references the curl binary"
    assert "httpx" in body, "curl_internal must use httpx"


@pytest.mark.asyncio
async def test_curl_internal_succeeds_via_httpx_mock():
    """No subprocess, no FileNotFoundError — httpx is the transport."""
    from services.ora_tools import curl_internal

    class _Resp:
        status_code = 200
        text = '{"ok": true, "platform": "warm-prober"}'

    class _Client:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, _url): return _Resp()

    with patch("httpx.AsyncClient", _Client):
        r = await curl_internal("/api/platform/warm-prober", method="GET")

    assert r["ok"] is True
    assert r["http_status"] == 200
    assert "warm-prober" in r["body"]


@pytest.mark.asyncio
async def test_curl_internal_rejects_external_url():
    from services.ora_tools import curl_internal
    r = await curl_internal("https://evil.com/api/x", method="GET")
    assert r["ok"] is False


# ─────────────────────────────────────────────
# Fix 2: tool-call leak detector catches python-call style
# ─────────────────────────────────────────────

def test_detector_catches_python_call_style_leak():
    from services.ora_agent import _looks_like_unhandled_tool_call
    # The exact leak the founder saw in chat
    leak = 'curl_internal(endpoint="/api/platform/warm-prober", method="GET")'
    assert _looks_like_unhandled_tool_call(leak) is True


def test_detector_catches_python_call_with_whitespace():
    from services.ora_agent import _looks_like_unhandled_tool_call
    assert _looks_like_unhandled_tool_call(
        '   view_file(path="/app/backend/server.py")  '
    ) is True


def test_detector_ignores_genuine_prose_mentioning_tool_name():
    from services.ora_agent import _looks_like_unhandled_tool_call
    # Plain English mention is fine
    assert _looks_like_unhandled_tool_call(
        "I used curl_internal to check the endpoint and it returned 200."
    ) is False


def test_detector_ignores_unknown_function_call():
    """Only registered tool names should trigger the safety net so the
    detector doesn't accidentally mute, say, code snippets shown to
    teach the founder how to write Python."""
    from services.ora_agent import _looks_like_unhandled_tool_call
    assert _looks_like_unhandled_tool_call(
        'random_helper_func(x=1, y=2)'
    ) is False


def test_detector_still_catches_json_shape():
    from services.ora_agent import _looks_like_unhandled_tool_call
    assert _looks_like_unhandled_tool_call(
        '{"type": "function", "name": "campaign_status", "parameters": {}}'
    ) is True


# ─────────────────────────────────────────────
# Fix 3: humanize tool error before it enters LLM context
# ─────────────────────────────────────────────

def test_humanize_strips_filenotfound_with_path():
    from services.ora_agent import _humanize_tool_error
    e = _humanize_tool_error(
        "FileNotFoundError: [Errno 2] No such file or directory: 'curl'"
    )
    assert "FileNotFoundError" not in e
    assert "Errno" not in e
    assert "curl" in e and "unavailable" in e


def test_humanize_strips_generic_traceback():
    from services.ora_agent import _humanize_tool_error
    raw = (
        "Traceback (most recent call last):\n"
        "  File '/app/x.py', line 12, in foo\n"
        "    raise ValueError('boom')\n"
        "ValueError: boom"
    )
    out = _humanize_tool_error(raw)
    assert "Traceback" not in out


def test_humanize_strips_errno_markers():
    from services.ora_agent import _humanize_tool_error
    out = _humanize_tool_error("ConnectionRefusedError: [Errno 111] Connection refused")
    assert "Errno" not in out
    assert "didn't answer" in out


def test_format_tool_result_humanizes_error():
    from services.ora_agent import _format_tool_result
    s = _format_tool_result(
        "curl_internal",
        {"ok": False,
         "error": "FileNotFoundError: [Errno 2] No such file or directory: 'curl'"},
    )
    # Final envelope going INTO the LLM context must be sanitized
    assert "FileNotFoundError" not in s
    assert "Errno" not in s


# ─────────────────────────────────────────────
# Fix 4: UI collapse button
# ─────────────────────────────────────────────

def test_sidebar_collapse_button_present():
    src = ORA_ADMIN_UNIFIED.read_text()
    assert 'data-testid="ora-admin-sidebar-collapse"' in src
    # Persists preference
    assert "ora_admin_sidebar_collapsed" in src
    # Uses ChevronLeft / ChevronRight from lucide
    assert "ChevronLeft" in src and "ChevronRight" in src


def test_sidebar_navbutton_supports_collapsed_prop():
    src = ORA_ADMIN_UNIFIED.read_text()
    assert "NavButton({ tab, active, onClick, collapsed" in src


def test_iter_marker_present():
    assert "iter 327e" in (BACKEND / "services" / "ora_tools.py").read_text()
    assert "iter 327e" in (BACKEND / "services" / "ora_agent.py").read_text()
    assert "iter 327e" in ORA_ADMIN_UNIFIED.read_text()
