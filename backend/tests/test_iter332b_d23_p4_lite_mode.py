"""
iter 332b D-23 — Deployment escape hatch for the P4 worker.

Background:
  The user's production K8s pod was restarting in a loop. The full P4
  worker attaches 34 schedulers on every boot (QA deep, backup loop,
  daily site audit, etc.). On a 1 Gi memory-limited pod under live
  traffic + the 3 P3 schedulers + warm-prober + auto-blast cycle, the
  combined steady-state memory was close enough to the limit that
  bursts triggered OOM kills.

This module adds two env-var escape hatches:

  • AUREM_LITE_MODE=1            → skip ALL 34 P4 schedulers
  • AUREM_DISABLE_SCHEDULERS=    → comma-separated list of names to skip
      e.g. "qa_agent_deep,backup_loop,clawchief_daily_sweep"

Both are read at worker startup. The HTTP API + middleware + main
event loop are unaffected — only background loops are gated.
"""
from __future__ import annotations

import os
import importlib
from unittest.mock import patch


def test_lite_mode_skips_all_schedulers(monkeypatch):
    """When AUREM_LITE_MODE=1, the worker must skip all 34 attaches
    and mark itself as started so subsequent calls are no-ops."""
    from pillars.command_hub import worker as W
    # Reset the module-level "started" flag so the test is hermetic.
    W._worker_started = False
    W._worker_tasks.clear()

    monkeypatch.setenv("AUREM_LITE_MODE", "1")

    class FakeDB:
        pass

    result = W.start_pillar4_worker(db=FakeDB())
    assert result.get("skipped_all_lite_mode") is True
    assert result.get("started") == []
    assert W._worker_started is True


def test_disable_list_filters_specific_schedulers():
    """The `_attach` helper must close the coroutine and skip when the
    scheduler name is in the disabled set."""
    from pillars.command_hub import worker as W
    started = []
    failed = []
    # Build a "fake" coroutine that we expect to be closed (not run).
    async def _fake_coro():
        return None
    coro = _fake_coro()
    W._attach("qa_agent_deep", coro, started, failed,
              "QA Agent Deep (weekly)", disabled={"qa_agent_deep"})
    # When a coroutine is closed it can no longer be sent .send(None).
    import inspect
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
    assert started == [] and failed == []


def test_worker_module_has_env_guards():
    """File-text assertion the env-guard code lives in the worker."""
    src = open("/app/backend/pillars/command_hub/worker.py").read()
    assert "AUREM_LITE_MODE" in src
    assert "AUREM_DISABLE_SCHEDULERS" in src
    assert "skipped_all_lite_mode" in src
