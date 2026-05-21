"""iter 325l — Startup import-error regression tests.

Locks in:
  1. ``services.recipient_guard.install_recipient_guard`` patches
     ``resend.Emails.send`` cleanly on resend 2.27.0 — and never tries
     the dead ``from resend.emails import Emails`` submodule path.
  2. ``routers.ai_email_router`` mounts without warnings (top-level
     ``import resend`` succeeds).
  3. ``routes.whatsapp_test`` imports cleanly and references
     ``AUREMBrowser`` (post-rebrand) — no stale ``RerootsBrowser`` refs
     anywhere in /app/backend except inside this lock test.
  4. ``pinchtab_browser`` exposes ``AUREMBrowser`` (the canonical name).
"""
from __future__ import annotations

import importlib
import inspect
import subprocess
import sys

import pytest


# ─────────────────────────────────────────────────────────────────
# Fix 1 — resend imports
# ─────────────────────────────────────────────────────────────────

def test_resend_top_level_import_works():
    """Sanity: resend 2.27.0 must import cleanly with Emails + logs."""
    import resend
    assert hasattr(resend, "Emails")
    assert hasattr(resend.Emails, "send")
    # resend.logs submodule must also be importable
    import resend.logs  # noqa: F401


def test_recipient_guard_drops_broken_submodule_fallback():
    """The historical `from resend.emails import Emails` fallback was
    permanently broken in 2.27.0 (resend.emails is a sub-package). The
    guard module must no longer reference it."""
    from services import recipient_guard
    src = inspect.getsource(recipient_guard)
    assert "from resend.emails import Emails" not in src, (
        "Broken submodule fallback must stay removed"
    )


def test_recipient_guard_installs_cleanly():
    """install_recipient_guard must return True on a healthy resend
    install (no warnings, monkey-patch applied, idempotent)."""
    from services import recipient_guard
    ok1 = recipient_guard.install_recipient_guard()
    assert ok1 is True
    # Idempotent: second call returns True without re-patching
    ok2 = recipient_guard.install_recipient_guard()
    assert ok2 is True
    # Confirm the patch flag is set on resend.Emails.send
    import resend
    assert getattr(resend.Emails.send, "_aurem_guarded", False) is True


def test_ai_email_router_imports_resend_directly():
    """The router must import resend at the top level — no stub fallback
    triggered on a healthy install."""
    from routers import ai_email_router
    assert ai_email_router._RESEND_AVAILABLE is True
    import resend
    assert ai_email_router.resend is resend


# ─────────────────────────────────────────────────────────────────
# Fix 2 — pinchtab_browser / RerootsBrowser
# ─────────────────────────────────────────────────────────────────

def test_pinchtab_browser_exposes_aurem_browser():
    """The post-rebrand canonical class name is AUREMBrowser."""
    import pinchtab_browser
    assert hasattr(pinchtab_browser, "AUREMBrowser")
    assert hasattr(pinchtab_browser, "BrowserToolkit")
    assert hasattr(pinchtab_browser, "detect_intent")
    assert hasattr(pinchtab_browser, "Intent")


def test_whatsapp_test_router_imports_cleanly():
    """The WhatsApp test router must import without ImportError so
    routers.registry mounts it instead of logging a warning."""
    mod = importlib.import_module("routes.whatsapp_test")
    assert hasattr(mod, "router")
    src = inspect.getsource(mod)
    assert "RerootsBrowser" not in src, "Stale RerootsBrowser ref still present"
    assert "AUREMBrowser" in src


def test_no_lingering_rerootsbrowser_references_in_backend():
    """Grep guard: no live code under /app/backend (excluding this lock
    test) should reference RerootsBrowser anymore."""
    result = subprocess.run(
        ["grep", "-rn", "RerootsBrowser", "/app/backend",
         "--include=*.py",
         "--exclude-dir=__pycache__",
         "--exclude-dir=tests"],
        capture_output=True, text=True,
    )
    # grep returns 1 when no matches found — that's the success state
    assert result.returncode == 1, (
        f"Stale RerootsBrowser refs still present:\n{result.stdout}"
    )


# ─────────────────────────────────────────────────────────────────
# End-to-end: registry import path no longer warns
# ─────────────────────────────────────────────────────────────────

def test_registry_can_import_whatsapp_test_router():
    """The exact code path routers.registry uses must succeed."""
    # Match registry.py:135 verbatim
    from routes.whatsapp_test import router as whatsapp_test_router
    assert whatsapp_test_router is not None
    # Confirm it's a real FastAPI router with at least one route
    from fastapi import APIRouter
    assert isinstance(whatsapp_test_router, APIRouter)
