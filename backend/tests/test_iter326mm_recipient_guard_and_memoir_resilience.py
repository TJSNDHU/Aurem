"""
test_iter326mm_recipient_guard_and_memoir_resilience.py — iter 326mm.
══════════════════════════════════════════════════════════════════════════════
Production deploy logs (2026-05-22) showed three runtime warnings:

  1) services.recipient_guard:[recipient-guard] resend import failed:
     No module named 'resend.logs' — guard not installed

     Cause: recipient_guard.py still did a bare `import resend`. The
     iter 326x mass-migration to `from services.email_engine import
     resend` missed this file. Fix: route through the shim so the
     iter 326kk HTTP fallback applies; guard now installs even on the
     prod resend wheel.

  2) services.memoir_service:[memoir] init failed: memoir new exit=5:
     Failed to create store: [Errno 2] No such file or directory: 'git'

     Cause: memoir CLI shells out to `git`, but the production Docker
     image doesn't ship git. Fix: pre-check with shutil.which("git")
     and raise a clear RuntimeError before spawning the subprocess.
     Net result is the same (init returns False, app keeps running),
     but the log line is now self-explanatory.

  3) services.email_engine:[email_engine] resend SDK completely
     unavailable, using stub: No module named 'resend.logs'

     Already addressed by iter 326kk (HTTP fallback). The log line in
     the deploy output is from the OLD bundle — confirmed by checking
     preview source. No further action; user just needs to redeploy.

WHAT THIS TEST LOCKS IN
───────────────────────
  • recipient_guard.py imports resend through services.email_engine, not directly
  • recipient_guard.py log message updated to mention "shim import failed"
  • memoir_service.py pre-checks for git binary via shutil.which
  • memoir_service.py raises a clear "git binary not found" RuntimeError
    when git is absent

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326mm_recipient_guard_and_memoir_resilience.py -v
"""
from __future__ import annotations

import pathlib
import re

import pytest


_GUARD  = pathlib.Path("/app/backend/services/recipient_guard.py")
_MEMOIR = pathlib.Path("/app/backend/services/memoir_service.py")


# ─────────────────────────────────────────────────────────────────────────────
# recipient_guard.py — must route through email_engine shim
# ─────────────────────────────────────────────────────────────────────────────
def test_recipient_guard_uses_email_engine_shim():
    src = _GUARD.read_text()
    assert "from services.email_engine import resend" in src, (
        "recipient_guard.py must use the email_engine shim — otherwise "
        "the iter 326kk HTTP fallback won't apply here and the guard "
        "will silently disable on every prod boot."
    )


def test_recipient_guard_has_no_bare_import_resend():
    src = _GUARD.read_text()
    # Strip comments so the explanatory comment doesn't false-positive.
    code_only = re.sub(r"#.*$", "", src, flags=re.MULTILINE)
    assert not re.search(
        r'^[ \t]*import resend\b', code_only, flags=re.MULTILINE,
    ), "recipient_guard.py still has a bare `import resend` outside comments."


def test_recipient_guard_warning_message_updated():
    """The error message should mention 'shim' so an ops engineer
    grepping the log understands which path failed."""
    src = _GUARD.read_text()
    assert "resend shim import failed" in src or \
           "shim" in src.split("guard not installed")[0]


# ─────────────────────────────────────────────────────────────────────────────
# memoir_service.py — must pre-check for git binary
# ─────────────────────────────────────────────────────────────────────────────
def test_memoir_service_imports_shutil_for_which_check():
    src = _MEMOIR.read_text()
    assert "shutil" in src and "which" in src, (
        "memoir_service.py must shutil.which('git') before spawning the "
        "memoir subprocess — otherwise containers without git produce "
        "a confusing 'exit=5' log line."
    )


def test_memoir_service_pre_checks_git_binary():
    src = _MEMOIR.read_text()
    # The pre-check should happen BEFORE subprocess.run for memoir new.
    git_check_idx = src.find('shutil.which("git")')
    subprocess_idx = src.find('subprocess.run(\n            ["memoir", "new"')
    assert git_check_idx != -1, "git pre-check missing"
    assert subprocess_idx != -1, "memoir new subprocess call missing"
    assert git_check_idx < subprocess_idx, (
        "shutil.which('git') must run BEFORE subprocess.run([memoir, new, ...])"
    )


def test_memoir_service_raises_clear_error_when_git_missing():
    src = _MEMOIR.read_text()
    assert "git binary not found in PATH" in src, (
        "Error message should self-explain so non-tech founder reading "
        "the log understands why memoir is disabled."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Integration smoke — recipient_guard imports cleanly under the shim
# ─────────────────────────────────────────────────────────────────────────────
def test_recipient_guard_module_imports_cleanly():
    """If the shim is wired correctly, importing recipient_guard never
    raises ModuleNotFoundError even on a broken resend wheel."""
    import importlib
    import services.recipient_guard
    # Force a reload so the import side-effects run cleanly under the test.
    importlib.reload(services.recipient_guard)
    # No assertion needed — the import not raising is the test.
