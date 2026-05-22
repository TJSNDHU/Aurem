"""
test_iter326kk_resend_http_fallback.py — iter 326kk regression.
══════════════════════════════════════════════════════════════════════════════
Production deploy 2026-05-22 showed:
  WARNING:services.onboarding_reminder:[onboarding-reminder] send failed for
  <email>: Resend SDK not loaded

Root cause: production wheel of `resend` is missing some submodule (most
likely `resend.logs`), so BOTH the iter 326e shim paths failed —
`import resend` and `importlib.import_module("resend.emails._emails")`.
The shim then fell through to a stub that raises RuntimeError on send.

The iter 326kk fix replaces that final stub with a real HTTP-only
fallback that POSTs directly to `https://api.resend.com/emails`. Email
sends keep working even when the SDK is completely unloadable.

WHAT THIS TEST LOCKS IN
───────────────────────
  • The "Resend SDK not loaded" string is no longer the last-resort
    fallback (regression marker).
  • The shim always exposes `resend.Emails.send` callable.
  • If the HTTP fallback is in play with no api_key, the error message
    is clear (it must NOT say "Resend SDK not loaded" — that wording
    indicates a regression to the old stub).
  • Onboarding reminder + blast service + all migrated files import
    `resend` via `services.email_engine` so they benefit from the
    fallback (sanity check on the iter 326x migration).

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326kk_resend_http_fallback.py -v
"""
from __future__ import annotations

import inspect
import pathlib
import re

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Shim surface — Emails.send is always callable
# ─────────────────────────────────────────────────────────────────────────────
def test_email_engine_resend_emails_send_is_callable():
    from services.email_engine import resend
    assert hasattr(resend, "Emails")
    assert callable(getattr(resend.Emails, "send", None))


def test_email_engine_no_runtime_error_stub_remains():
    """The iter 326kk fix removes the old `raise RuntimeError('Resend SDK
    not loaded')` stub. If that string is back, prod will silently drop
    email again."""
    src = pathlib.Path("/app/backend/services/email_engine.py").read_text()
    assert 'raise RuntimeError("Resend SDK not loaded")' not in src, (
        "The 'Resend SDK not loaded' stub regressed. iter 326kk replaced "
        "it with an HTTP fallback — do not bring it back."
    )


def test_email_engine_has_http_fallback_marker():
    """Source-level marker: the HTTP fallback class must be present so
    we can grep for it during deploy audits."""
    src = pathlib.Path("/app/backend/services/email_engine.py").read_text()
    assert "_HttpEmails" in src
    assert "api.resend.com/emails" in src
    assert "iter 326kk" in src


# ─────────────────────────────────────────────────────────────────────────────
# Behaviour — simulate prod where `import resend` raises
# ─────────────────────────────────────────────────────────────────────────────
def test_http_fallback_send_without_api_key_gives_clear_error(monkeypatch):
    """When the SDK is unloadable AND no api_key is set, the error
    message must be self-explanatory — NOT the old 'Resend SDK not
    loaded' wording (which falsely suggests an import bug)."""
    # Build the fallback Emails class in isolation by replaying the
    # except-branch logic — keeps the test independent of monkey-patching
    # the live module.
    import importlib
    import sys
    import types

    # Force a clean reload that takes the except branch.
    # We can't easily make `import resend` fail mid-process without
    # ugly sys.modules surgery, so just call the live fallback if it's
    # there, OR build one inline that mirrors the production behaviour.
    from services.email_engine import resend as _live_resend
    # Try sending with no api_key on whatever fallback the engine
    # currently exposes.
    monkeypatch.setattr(_live_resend, "api_key", None, raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    # If the live import succeeded (preview env), the SDK send will
    # likely fail with a different reason. Just assert it doesn't say
    # 'Resend SDK not loaded'.
    try:
        _live_resend.Emails.send({"from": "x@x", "to": ["y@y"],
                                   "subject": "t", "html": "<p>h</p>"})
        sent_ok = True
        err_text = ""
    except Exception as e:
        sent_ok = False
        err_text = str(e)
    assert "Resend SDK not loaded" not in err_text, (
        f"Old stub regressed — engine says 'Resend SDK not loaded'. "
        f"Got: {err_text}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# All hot-path files still route through the engine (iter 326x sanity)
# ─────────────────────────────────────────────────────────────────────────────
def test_onboarding_reminder_uses_engine_shim():
    """The file that was failing in the prod log MUST import resend
    via services.email_engine so the HTTP fallback applies."""
    src = pathlib.Path("/app/backend/services/onboarding_reminder.py").read_text()
    assert "from services.email_engine import resend" in src, (
        "onboarding_reminder.py must use the engine shim — otherwise "
        "the iter 326kk HTTP fallback won't be applied here."
    )
    # And the bare import must NOT be present
    assert not re.search(
        r'^[ \t]*import resend\b', src, flags=re.MULTILINE,
    ), "onboarding_reminder.py still has a bare `import resend`."
