"""
iter 326e — Production deploy-error regression suite.

User's 2026-05-21 production deploy logs surfaced 4 distinct code-level
breaks (no docker changes allowed). Tracking each, fixing at source,
and locking-in via tests so they never regress:

  1. `cannot import name '_send_whatsapp_digest' from
      'services.morning_digest'` — nightly evening-brief job blew up
      every night. The fn was renamed during an earlier refactor; we
      restore the contract with a thin shim that delegates to `_wa_send`.

  2. `[email_engine] resend SDK unavailable: No module named
      'resend.logs'` — production ships a slimmed resend wheel where
      `resend/__init__.py` does `from . import logs` but the `logs.py`
      submodule is missing. Fallback now imports `resend.emails._emails`
      directly so sends still work even when `resend.__init__` chokes.

  3. APScheduler "max instances reached (1)" + "missed by 0:00:33" —
      `ora_proposal_bridge` (was max_instances=1) and `periodic_flush`
      (misfire_grace_time=30s) both bumped — match the iter 325u
      pattern applied to the warm-prober.

  4. (Documented as future work — not regressed here) `/api/repair/*`
      404 in prod is a separate router-loading bug; preview works.
"""
import inspect
import sys

sys.path.insert(0, "/app/backend")


# ─── Fix 1: nightly evening-brief import contract ─────────────────────

def test_send_whatsapp_digest_importable_from_morning_digest():
    """The exact name `nightly_cycle.send_evening_brief` runtime-imports
    must exist and be an async function."""
    from services.morning_digest import _send_whatsapp_digest
    assert inspect.iscoroutinefunction(_send_whatsapp_digest)


def test_evening_brief_uses_helper():
    src = open("/app/backend/services/nightly_cycle.py",
               encoding="utf-8").read()
    # Sanity — caller still uses the same name
    assert "_send_whatsapp_digest" in src


# ─── Fix 2: defensive resend import ───────────────────────────────────

def test_email_engine_handles_missing_resend_logs():
    """`email_engine.resend` must be usable even when the top-level
    `import resend` would have raised ModuleNotFoundError('resend.logs').

    We can't easily uninstall resend mid-test, but we can assert the
    two-stage import code is present + the `Emails.send` attribute
    is reachable from the imported symbol.
    """
    src = open("/app/backend/services/email_engine.py",
               encoding="utf-8").read()
    # 2-stage strategy
    assert "resend.emails._emails" in src, (
        "fallback must import the concrete Emails class directly"
    )
    assert "_ResendStub" in src, "final stub branch must still exist"

    from services.email_engine import resend as _r
    assert hasattr(_r, "Emails")
    assert hasattr(_r.Emails, "send")


# ─── Fix 3: APScheduler tolerance bumps ───────────────────────────────

def test_periodic_flush_tolerance_bumped():
    src = open("/app/backend/services/nightly_cycle.py",
               encoding="utf-8").read()
    # Both knobs must be relaxed compared to the old 1 / 30 settings.
    assert "max_instances=2" in src
    assert "misfire_grace_time=90" in src
    # Old defaults gone for this job
    assert "max_instances=1, coalesce=True, misfire_grace_time=30" not in src


def test_ora_proposal_bridge_tolerance_bumped():
    src = open("/app/backend/routers/registry.py",
               encoding="utf-8").read()
    # The block that schedules `ora_proposal_bridge` must now allow 2
    # concurrent ticks and a 180s misfire window.
    bridge_idx = src.find('id="ora_proposal_bridge"')
    assert bridge_idx > 0, "ora_proposal_bridge add_job not found"
    block = src[bridge_idx: bridge_idx + 800]
    assert "max_instances=2" in block
    assert "misfire_grace_time=180" in block
