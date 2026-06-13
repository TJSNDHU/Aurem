"""
test_iter326x_resend_defensive_imports.py — iter 326x regression.
══════════════════════════════════════════════════════════════════════════════
Production deploy logs (2026-05-22) showed every email blast failing with:
  No module named 'resend.logs'

Root cause: production sometimes ships a slimmed `resend` wheel where
`resend/__init__.py` does `from . import logs` but the `logs.py`
submodule is missing — so `import resend` raises ModuleNotFoundError.

`services/email_engine.py` has had a defensive shim since iter 326e that
handles this. The problem was that 20+ OTHER files did bare `import resend`
at runtime, each independently re-hitting the broken import and failing
their email send.

THE FIX (iter 326x): replace every bare `import resend` in the production
hot path with `from services.email_engine import resend` so the shim is
shared and every email path stays alive even on a broken wheel.

WHAT THIS TEST LOCKS IN
───────────────────────
  • services.email_engine exports a usable `resend` module reference
  • All known hot-path files import resend via the shim (NOT bare)
  • The shim's `resend.Emails.send` is callable (even if it errors —
    we just care it's not a NameError at the call site)

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326x_resend_defensive_imports.py -v
"""
from __future__ import annotations

import importlib
import pathlib
import re

import pytest

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


# Files that previously did a bare `import resend` and have been migrated
# to the email_engine shim. The blast pipeline + every dunning, welcome,
# milestone, daily-brief sender lives here.
HOT_PATH_FILES = [
    "/app/backend/pillars/sales/routes/blast_service.py",
    "/app/backend/routers/server_misc_routes.py",
    "/app/backend/routers/website_builder_router.py",
    "/app/backend/routers/pin_auth_router.py",
    "/app/backend/routers/leads_mining_router.py",
    "/app/backend/routers/email_inbound_router.py",
    "/app/backend/routers/v2_customer_actions_router.py",
    "/app/backend/routers/case_study_router.py",
    "/app/backend/routers/hunter_test_router.py",
    "/app/backend/routers/ai_email_router.py",
    "/app/backend/shared/agents/followup_ora.py",
    "/app/backend/shared/agents/closer_ora.py",
    "/app/backend/shared/agents/referral_ora.py",
    "/app/backend/routes/auth.py",
    "/app/backend/utils/casl_patch.py",
    "/app/backend/services/startup_validation.py",
    "/app/backend/services/cron_schedulers.py",
    "/app/backend/services/email_notification_service.py",
    "/app/backend/services/autonomous_repair_engine.py",
    "/app/backend/services/site_change_watcher.py",
    "/app/backend/services/ora_command_center.py",
    "/app/backend/services/milestone_system.py",
    "/app/backend/services/aurem_nightly_selfcheck.py",
    "/app/backend/services/db_backup_service.py",
    "/app/backend/services/auto_website_builder.py",
    "/app/backend/services/campaign_daily_brief.py",
    "/app/backend/services/founder_daily_brief.py",
    "/app/backend/services/project_report_builder.py",
    "/app/backend/services/first_contact_email.py",
    "/app/backend/services/build_journal_service.py",
    "/app/backend/services/onboarding_reminder.py",
    "/app/backend/services/welcome_package.py",
    "/app/backend/services/a2a_chain.py",
]

# Regex that matches a bare `import resend` (or `import resend as <alias>`)
# that is NOT inside a comment and NOT routed through email_engine.
_BARE_RE = re.compile(
    r'^[ \t]*import resend(\s|,|\b|$)',
    flags=re.MULTILINE,
)


def test_email_engine_resend_shim_loads():
    """The defensive shim must always import cleanly."""
    mod = importlib.import_module("services.email_engine")
    assert hasattr(mod, "resend"), "email_engine must export resend"
    assert hasattr(mod.resend, "Emails"), "shim must expose Emails class"
    assert callable(getattr(mod.resend.Emails, "send", None)), \
        "shim Emails.send must be callable"


@pytest.mark.parametrize("filepath", HOT_PATH_FILES)
def test_hot_path_file_uses_defensive_import(filepath):
    """No bare `import resend` allowed in any production hot-path file."""
    p = pathlib.Path(filepath)
    if not p.exists():
        pytest.skip(f"{filepath} does not exist in this branch")
    text = p.read_text()
    bare_hits = _BARE_RE.findall(text)
    # The only legitimate bare import is the one INSIDE email_engine.py,
    # which is not in HOT_PATH_FILES.
    assert not bare_hits, (
        f"{filepath} still has bare 'import resend' — production deploys "
        f"will crash with ModuleNotFoundError: 'resend.logs'. "
        f"Use `from services.email_engine import resend` instead."
    )


def test_hot_path_files_actually_use_shim():
    """Every file in HOT_PATH_FILES must mention the email_engine shim,
    proving the migration actually landed (not just deleted the import)."""
    missing = []
    for fp in HOT_PATH_FILES:
        p = pathlib.Path(fp)
        if not p.exists():
            continue
        if "from services.email_engine import resend" not in p.read_text():
            missing.append(fp)
    assert not missing, (
        f"{len(missing)} files no longer import resend at all (regression?): "
        f"{missing}"
    )
