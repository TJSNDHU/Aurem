"""
iter 326pp — silent failure alerting tests
==========================================

Three Telegram alert channels:
  1. Backup cron failure  → alert_backup_failure
  2. Scheduler job crash  → alert_scheduler_crash (via APScheduler listener)
  3. Auth 401/403 in autonomous run → alert_autonomous_401

Tests assert each helper:
  - calls send_telegram_alert with the right alert_type + fingerprint
  - never raises on missing creds / exception in transport
  - is wired into db_backup_service, registry.py, ora_agent.py
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent


# ───────────────────────────────────────────────────
# 1) Module import + public surface
# ───────────────────────────────────────────────────

def test_module_exports_three_helpers():
    from services import silent_failure_alerts as sfa
    assert hasattr(sfa, "alert_backup_failure")
    assert hasattr(sfa, "alert_scheduler_crash")
    assert hasattr(sfa, "alert_autonomous_401")
    assert callable(sfa.alert_backup_failure)
    assert callable(sfa.alert_scheduler_crash)
    assert callable(sfa.alert_autonomous_401)


# ───────────────────────────────────────────────────
# 2) alert_backup_failure
# ───────────────────────────────────────────────────

def test_backup_failure_calls_send_with_fingerprint_eq_run_id():
    from services import silent_failure_alerts as sfa

    captured = {}

    async def fake_send(message, alert_type, fingerprint):
        captured.update(
            {"message": message, "alert_type": alert_type, "fingerprint": fingerprint}
        )
        return {"ok": True, "reason": "sent"}

    with patch.object(sfa, "_send", side_effect=fake_send):
        sfa.alert_backup_failure(
            run_id="dr-20260523T030000Z",
            status="fail",
            reason="ServerSelectionTimeoutError: secondary down",
            triggered_by="scheduler_cron",
        )
    assert captured.get("alert_type") == "backup_failure"
    assert captured.get("fingerprint") == "dr-20260523T030000Z"
    assert "dr-20260523T030000Z" in captured.get("message", "")
    assert "secondary down" in captured.get("message", "")


def test_backup_failure_skips_on_status_ok():
    from services import silent_failure_alerts as sfa

    called = {"n": 0}

    async def fake_send(message, alert_type, fingerprint):
        called["n"] += 1
        return {"ok": True}

    with patch.object(sfa, "_send", side_effect=fake_send):
        sfa.alert_backup_failure("dr-x", "ok", "fine", "scheduler")
    assert called["n"] == 0  # success never alerts


def test_backup_failure_swallows_send_exceptions():
    from services import silent_failure_alerts as sfa

    async def explode(*a, **kw):
        raise RuntimeError("transport gone")

    with patch.object(sfa, "_send", side_effect=explode):
        # Must NOT raise
        sfa.alert_backup_failure("dr-x", "fail", "boom", "scheduler")


# ───────────────────────────────────────────────────
# 3) alert_scheduler_crash
# ───────────────────────────────────────────────────

def test_scheduler_crash_dedup_key_includes_job_and_exception_type():
    from services import silent_failure_alerts as sfa

    captured = {}

    async def fake_send(message, alert_type, fingerprint):
        captured.update({"alert_type": alert_type, "fingerprint": fingerprint,
                         "message": message})
        return {"ok": True}

    exc = ValueError("bad config")
    with patch.object(sfa, "_send", side_effect=fake_send):
        sfa.alert_scheduler_crash(
            job_id="aurem_dr_backup_daily",
            job_name="AUREM DR Backup",
            exception=exc,
            tb_str="Traceback (most recent call last):\n  File ...",
        )
    assert captured["alert_type"] == "scheduler_crash"
    # Fingerprint must distinguish same job crashing with different errors
    assert "aurem_dr_backup_daily" in captured["fingerprint"]
    assert "ValueError" in captured["fingerprint"]
    assert "bad config" in captured["message"]


# ───────────────────────────────────────────────────
# 4) alert_autonomous_401
# ───────────────────────────────────────────────────

def test_autonomous_401_fires_for_401_and_403():
    from services import silent_failure_alerts as sfa

    fired = []

    async def fake_send(message, alert_type, fingerprint):
        fired.append({"type": alert_type, "fp": fingerprint, "msg": message})
        return {"ok": True}

    with patch.object(sfa, "_send", side_effect=fake_send):
        sfa.alert_autonomous_401("ora_agent.gemini_call", 401, "key revoked",
                                 provider="gemini")
        sfa.alert_autonomous_401("ora_agent.gemini_call", 403, "quota burnt",
                                 provider="gemini")
    assert len(fired) == 2
    assert fired[0]["type"] == "autonomous_401"
    assert "gemini" in fired[0]["fp"]
    assert "401" in fired[0]["fp"]
    assert "403" in fired[1]["fp"]


def test_autonomous_401_skips_non_auth_status():
    from services import silent_failure_alerts as sfa

    called = {"n": 0}

    async def fake_send(*a, **kw):
        called["n"] += 1
        return {"ok": True}

    with patch.object(sfa, "_send", side_effect=fake_send):
        sfa.alert_autonomous_401("ora_agent.gemini_call", 500, "boom",
                                 provider="gemini")
        sfa.alert_autonomous_401("ora_agent.gemini_call", 200, "fine",
                                 provider="gemini")
    assert called["n"] == 0


# ───────────────────────────────────────────────────
# 5) Wire-up checks (source-level)
# ───────────────────────────────────────────────────

def test_db_backup_service_imports_alert_helper():
    src = (BACKEND / "services" / "db_backup_service.py").read_text()
    assert "alert_backup_failure" in src
    # Should be called inside the `fail` exception path AND the
    # missing-secondary fast-exit.
    assert src.count("alert_backup_failure(") >= 2


def test_registry_wires_scheduler_error_listener():
    src = (BACKEND / "routers" / "registry.py").read_text()
    assert "EVENT_JOB_ERROR" in src
    assert "alert_scheduler_crash" in src
    assert "add_listener(_on_job_error, EVENT_JOB_ERROR)" in src
    # Listener must be added AFTER scheduler.start() so it actually
    # receives events.
    start_idx = src.index("aurem_scheduler.start()")
    listener_idx = src.index("add_listener(_on_job_error, EVENT_JOB_ERROR)")
    assert listener_idx > start_idx


def test_ora_agent_fires_alert_on_gemini_401_403():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    assert "alert_autonomous_401" in src
    # Must live in the same block as `_gemini_cb_record_failure`
    # (the 401/403 detection point).
    idx_cb = src.find("_gemini_cb_record_failure(f\"HTTP {r.status_code}")
    idx_alert = src.find("alert_autonomous_401(")
    assert idx_cb != -1 and idx_alert != -1
    # alert call should immediately follow the cb-record call (within
    # ~600 chars — same try-block)
    assert 0 < (idx_alert - idx_cb) < 600


# ───────────────────────────────────────────────────
# 6) Telegram service compatibility — alert_type prefixes
# ───────────────────────────────────────────────────

def test_telegram_service_handles_new_alert_types():
    """
    `send_telegram_alert` uses a prefix-lookup dict with a default
    `[alert_type]` fallback — so our new types ("backup_failure",
    "scheduler_crash", "autonomous_401") work out-of-the-box. Test
    asserts the function tolerates them without crashing on the
    creds-missing path.
    """
    from services.telegram_bot_service import send_telegram_alert
    # Force creds-missing path by emptying env
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "",
                                 "TELEGRAM_CHAT_ID": ""}, clear=False):
        for at in ("backup_failure", "scheduler_crash", "autonomous_401"):
            result = asyncio.run(send_telegram_alert("hi", alert_type=at,
                                                    fingerprint=f"fp-{at}"))
            assert result["ok"] is False
            assert result["reason"] == "creds_missing"


# ───────────────────────────────────────────────────
# 7) End-to-end: db_backup fast-exit calls our alert
# ───────────────────────────────────────────────────

def test_db_backup_missing_secondary_url_calls_alert(monkeypatch):
    """
    Drive `run_backup` with SECONDARY_MONGO_URL unset; verify
    `alert_backup_failure` is invoked exactly once with status='fail'.
    """
    # Ensure primary is set so we hit the SECONDARY check (not the
    # earlier PRIMARY check)
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.delenv("SECONDARY_MONGO_URL", raising=False)

    calls = []

    def spy(run_id, status, reason, triggered_by="scheduler"):
        calls.append({"run_id": run_id, "status": status,
                      "reason": reason, "triggered_by": triggered_by})

    # Patch the symbol where it is LOOKED UP (lazy import inside func)
    import services.silent_failure_alerts as sfa_mod
    monkeypatch.setattr(sfa_mod, "alert_backup_failure", spy)

    from services.db_backup_service import run_backup
    report = run_backup(triggered_by="pytest_326pp")

    assert report["status"] == "fail"
    assert "SECONDARY_MONGO_URL not configured" in report["error"]
    assert len(calls) == 1
    assert calls[0]["status"] == "fail"
    assert calls[0]["triggered_by"] == "pytest_326pp"


# ───────────────────────────────────────────────────
# 8) Iter marker
# ───────────────────────────────────────────────────

def test_iter_326pp_marker_present():
    src = (BACKEND / "services" / "silent_failure_alerts.py").read_text()
    assert "326pp" in src
