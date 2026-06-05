"""
test_d65_scheduler_coroutine_fix.py — iter D-65
================================================
Locks in the fix for: scheduler jobs that wrapped async coroutine
functions inside `lambda` produced
    RuntimeWarning: coroutine 'X' was never awaited
…and silently skipped every scheduled run.

The right pattern is to pass the coroutine function (not a lambda) and
its args directly to `aurem_scheduler.add_job(...)`.

This file also enforces:
- `services.silent_failure_alerts._send` signature stays
  (message, alert_type, fingerprint).
- ora_nightly_self_test calls _send with all 3 args.
"""
from __future__ import annotations

import inspect

import pytest


def _registry_source() -> str:
    return open("/app/backend/routers/registry.py").read()


def test_no_lambda_wrapping_async_in_add_job():
    """Every `add_job(...)` call must NOT use a lambda that returns a
    coroutine. APScheduler doesn't await lambda-returned coroutines."""
    import re
    src = _registry_source()
    # Find every add_job block (function arg is line 1).
    add_job_blocks = re.findall(
        r"add_job\(\s*\n\s*(.{0,200}?),", src
    )
    for first_arg in add_job_blocks:
        first_arg = first_arg.strip()
        # `lambda: foo(...)` patterns are the dangerous ones.
        if first_arg.startswith("lambda"):
            # Must NOT wrap an async function. Allow lambdas that wrap sync
            # helpers — but in this codebase, every lambda we've ever used
            # wrapped an async; so the safest rule is "no lambdas at all"
            # in add_job's first arg.
            pytest.fail(
                f"add_job first arg is a lambda — pass the coroutine "
                f"function + args=[...] instead: {first_arg[:80]}"
            )


def test_self_audit_signature_keeps_db_first_arg():
    """run_self_audit(db) is what the scheduler calls — keep db first."""
    from services.self_audit import run_self_audit
    sig = inspect.signature(run_self_audit)
    params = list(sig.parameters.keys())
    assert params[0] == "db", f"run_self_audit param order changed: {params}"


def test_skill_learner_run_learning_cycle_is_async():
    """It MUST be a coroutine — non-async means scheduler doesn't need
    `args=[db]` and we should switch to lambda. Current fix assumes async."""
    from services.skill_learner import run_learning_cycle
    assert inspect.iscoroutinefunction(run_learning_cycle), (
        "run_learning_cycle stopped being async — revisit registry.add_job "
        "and decide on the right wiring."
    )


def test_silent_failure_alerts_send_signature():
    """_send is (message, alert_type, fingerprint). Drift breaks every
    caller including ora_nightly_self_test."""
    from services.silent_failure_alerts import _send
    sig = inspect.signature(_send)
    params = list(sig.parameters.keys())
    assert params == ["message", "alert_type", "fingerprint"], (
        f"_send signature drift: {params}"
    )


def test_ora_nightly_self_test_passes_alert_type():
    """The nightly self-test caller must pass `alert_type=` keyword
    or the underlying _send raises TypeError."""
    src = open("/app/backend/services/ora_nightly_self_test.py").read()
    # Find the _tg_send / _send invocation.
    assert "alert_type=" in src, (
        "ora_nightly_self_test must pass alert_type= to _send; the "
        "previous call dropped this and produced TypeError nightly."
    )


def test_registry_self_audit_uses_coroutine_function_not_lambda():
    """Specific regression: the Self-Audit hourly job must pass
    `run_self_audit` as the job function and `args=[db]` separately."""
    src = _registry_source()
    # Locate the Self-Audit block by its comment marker.
    idx = src.find("iter 282al-10")
    assert idx != -1, "Self-Audit cron block marker missing"
    block = src[idx:idx + 1000]
    assert "lambda: run_self_audit" not in block, (
        "Self-Audit still wrapped in lambda — coroutine never awaited"
    )
    assert "run_self_audit," in block and "args=[db]" in block


def test_registry_skill_learner_uses_coroutine_function_not_lambda():
    src = _registry_source()
    idx = src.find("ORA Skill Learner")
    assert idx != -1, "Skill Learner cron block marker missing"
    block = src[idx:idx + 1000]
    assert "lambda: run_learning_cycle" not in block, (
        "Skill Learner still wrapped in lambda — coroutine never awaited"
    )
    assert "run_learning_cycle," in block and "args=[db]" in block
