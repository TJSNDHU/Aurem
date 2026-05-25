"""
iter 332b D-24 — Auto-detect production for the P4 LITE-mode escape hatch.

The user's Emergent deployment UI doesn't expose env-var editing, so we
infer "this is production" from K8s-set signals and switch to LITE mode
by default. Preview/dev keeps the full 34-scheduler set running.

Detection signals (any of these → production):
  1. HOSTNAME contains "live-support" (Emergent prod pod name).
  2. HOSTNAME contains "emergent.host" (Emergent prod domain).
  3. KUBERNETES_SERVICE_HOST set AND REACT_APP_BACKEND_URL does NOT
     contain "preview.emergentagent.com".

Overrides:
  • AUREM_FORCE_FULL_MODE=1 → ALWAYS run all schedulers (use sparingly).
  • AUREM_LITE_MODE=1       → ALWAYS LITE mode (preview or prod).
"""
from __future__ import annotations

import pytest


def _reset_worker():
    """Reset module-level state so tests are hermetic."""
    from pillars.command_hub import worker as W
    W._worker_started = False
    W._worker_tasks.clear()


# ── Production signal 1: HOSTNAME = live-support-* ────────────────────
def test_lite_mode_engages_when_hostname_is_live_support(monkeypatch):
    _reset_worker()
    monkeypatch.setenv("HOSTNAME", "live-support-3-aurem-7b8c9d-x4")
    monkeypatch.delenv("AUREM_LITE_MODE", raising=False)
    monkeypatch.delenv("AUREM_FORCE_FULL_MODE", raising=False)
    from pillars.command_hub import worker as W
    result = W.start_pillar4_worker(db=object())
    assert result.get("skipped_all_lite_mode") is True


# ── Production signal 2: HOSTNAME contains emergent.host ──────────────
def test_lite_mode_engages_when_hostname_is_emergent_host(monkeypatch):
    _reset_worker()
    monkeypatch.setenv("HOSTNAME", "aurem.live-support.emergent.host")
    monkeypatch.delenv("AUREM_LITE_MODE", raising=False)
    monkeypatch.delenv("AUREM_FORCE_FULL_MODE", raising=False)
    from pillars.command_hub import worker as W
    result = W.start_pillar4_worker(db=object())
    assert result.get("skipped_all_lite_mode") is True


# ── Production signal 3: in K8s, no preview hostname, no preview_endpoint ─
def test_lite_mode_engages_in_k8s_without_preview_signals(monkeypatch):
    _reset_worker()
    monkeypatch.setenv("HOSTNAME", "some-random-pod")
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    monkeypatch.delenv("preview_endpoint", raising=False)
    monkeypatch.delenv("AUREM_LITE_MODE", raising=False)
    monkeypatch.delenv("AUREM_FORCE_FULL_MODE", raising=False)
    from pillars.command_hub import worker as W
    result = W.start_pillar4_worker(db=object())
    assert result.get("skipped_all_lite_mode") is True


# ── Preview MUST keep full schedulers ─────────────────────────────────
def test_full_mode_in_preview(monkeypatch):
    _reset_worker()
    monkeypatch.setenv("HOSTNAME", "agent-env-5face3c8-a8b0-4e26")
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    monkeypatch.setenv(
        "preview_endpoint",
        "https://ai-platform-preview-3.preview.emergentagent.com",
    )
    monkeypatch.delenv("AUREM_LITE_MODE", raising=False)
    monkeypatch.delenv("AUREM_FORCE_FULL_MODE", raising=False)
    from pillars.command_hub import worker as W
    monkeypatch.setattr(W, "_safe_task",
                        lambda c, n: (c.close(),) and None)
    result = W.start_pillar4_worker(db=object())
    assert "skipped_all_lite_mode" not in result, (
        "Preview must NOT engage LITE mode"
    )


# ── AUREM_FORCE_FULL_MODE overrides production detection ──────────────
def test_force_full_mode_overrides_production(monkeypatch):
    _reset_worker()
    monkeypatch.setenv("HOSTNAME", "live-support-3-aurem")
    monkeypatch.setenv("AUREM_FORCE_FULL_MODE", "1")
    monkeypatch.delenv("AUREM_LITE_MODE", raising=False)
    from pillars.command_hub import worker as W
    captured = {"started": False}
    monkeypatch.setattr(W, "_safe_task",
                        lambda c, n: (c.close(), captured.update(started=True), None)[2])
    result = W.start_pillar4_worker(db=object())
    assert "skipped_all_lite_mode" not in result


# ── AUREM_LITE_MODE=1 still forces LITE in preview ────────────────────
def test_lite_mode_env_var_still_works_in_preview(monkeypatch):
    _reset_worker()
    monkeypatch.setenv(
        "REACT_APP_BACKEND_URL",
        "https://ai-platform-preview-3.preview.emergentagent.com",
    )
    monkeypatch.setenv("AUREM_LITE_MODE", "1")
    from pillars.command_hub import worker as W
    result = W.start_pillar4_worker(db=object())
    assert result.get("skipped_all_lite_mode") is True
