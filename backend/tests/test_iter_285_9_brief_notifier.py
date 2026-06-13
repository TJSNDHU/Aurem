"""iter 285.9 — Morning Brief Notifier (post-run Telegram/WHAPI/Resend dispatch).

Validates:
  • _format_brief produces Hinglish/operator-friendly headline + phase counts
  • Each channel returns creds_missing honestly when env vars absent (Truth-Sync)
  • dispatch_brief aggregates attempts, writes to db.autopilot_notifications,
    and records truth-ledger failure when nothing delivered
  • master_autopilot._execute_morning_run calls dispatch_brief and embeds
    the result as doc["notification"]
  • fire-now endpoint returns a run whose stored doc carries notification field
"""
from __future__ import annotations

import os

import asyncio
import time
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

REPO = Path(__file__).resolve().parents[2]
BACKEND_URL = "http://localhost:8001"

ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


def _env():
    env = {}
    for line in (REPO / "backend" / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


@pytest.fixture(scope="module")
def admin_token():
    for _ in range(5):
        try:
            with httpx.Client(timeout=10.0) as c:
                r = c.post(
                    f"{BACKEND_URL}/api/auth/login",
                    json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                )
            if r.status_code == 200:
                d = r.json()
                return d.get("access_token") or d.get("token")
        except Exception:
            time.sleep(2)
    pytest.skip("Admin login unavailable")


# ───────── Pure function tests ─────────

def test_format_brief_includes_all_phase_counts():
    from backend.services.autopilot_brief_notifier import _format_brief

    run = {
        "run_id": "autopilot_test_1",
        "started_at": "2026-02-07T08:00:00+00:00",
        "duration_seconds": 12.5,
        "success": True,
        "phases": [
            {"phase": "scout",  "ok": True, "result": {"leads": 50}},
            {"phase": "hunt",   "ok": True, "result": {"qualified": 25}},
            {"phase": "blast",  "ok": True, "result": {"processed": 10, "sent": 8}},
            {"phase": "report", "ok": True, "result": {"brief_id": "brief_xyz"}},
        ],
    }
    text = _format_brief(run)
    assert "AUREM Morning Run" in text
    assert "4/4 phases OK" in text
    assert "50 leads processed" in text
    assert "8/10 sent" in text
    assert "brief_xyz" in text
    assert "autopilot_test_1" in text


def test_format_brief_degraded_run_uses_warning_emoji():
    from backend.services.autopilot_brief_notifier import _format_brief

    run = {
        "run_id": "autopilot_test_2",
        "started_at": "2026-02-07T08:00:00+00:00",
        "duration_seconds": 3.0,
        "success": False,
        "phases": [
            {"phase": "scout", "ok": False, "result": {}, "error": "boom"},
        ],
    }
    text = _format_brief(run)
    assert "⚠️" in text
    assert "0/1" in text


# ───────── Honest creds_missing ─────────

def test_channel_senders_return_creds_missing_when_env_absent(monkeypatch):
    from backend.services.autopilot_brief_notifier import (
        _send_telegram, _send_whapi, _send_email,
    )

    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "WHAPI_API_TOKEN", "WHAPI_TOKEN",
                "NOTIFY_PHONE", "ADMIN_ALERT_PHONE",
                "RESEND_API_KEY",
                "NOTIFY_EMAIL", "AUREM_SALES_BCC_EMAIL"):
        monkeypatch.delenv(var, raising=False)
    # iter 287.4: also disable the WHAPI kill-switch so the creds_missing
    # path is actually reachable (kill-switch check happens first)
    monkeypatch.setenv("WHAPI_BLAST_DISABLED", "false")

    tg = asyncio.run(_send_telegram("x"))
    wh = asyncio.run(_send_whapi("x"))
    em = asyncio.run(_send_email("s", "x"))

    for res, ch in ((tg, "telegram"), (wh, "whapi"), (em, "email")):
        assert res["ok"] is False
        assert res["channel"] == ch
        assert res["reason"] == "creds_missing"
        assert isinstance(res.get("missing"), list) and len(res["missing"]) >= 1


# ───────── dispatch_brief aggregation + DB write ─────────

def test_dispatch_brief_writes_notification_doc(monkeypatch):
    # Force all channels to creds_missing to avoid real external calls
    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "WHAPI_API_TOKEN", "WHAPI_TOKEN",
                "NOTIFY_PHONE", "ADMIN_ALERT_PHONE",
                "RESEND_API_KEY",
                "NOTIFY_EMAIL", "AUREM_SALES_BCC_EMAIL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("WHAPI_BLAST_DISABLED", "false")

    from backend.services.autopilot_brief_notifier import dispatch_brief, NOTIFY_COLLECTION

    env = _env()

    async def _run():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        run_id = f"autopilot_unit_{int(time.time())}"
        await db[NOTIFY_COLLECTION].delete_many({"run_id": run_id})

        run = {
            "run_id": run_id,
            "started_at": "2026-02-07T08:00:00+00:00",
            "duration_seconds": 1.0,
            "success": True,
            "phases": [{"phase": "scout", "ok": True, "result": {"leads": 3}}],
        }
        result = await dispatch_brief(db, run)
        assert result["ok"] is False  # no channel configured
        assert result["delivered"] == []
        assert {s["channel"] for s in result["skipped"]} == {"telegram", "whapi", "email"}
        for s in result["skipped"]:
            assert s["reason"] == "creds_missing"

        doc = await db[NOTIFY_COLLECTION].find_one({"run_id": run_id})
        assert doc is not None
        assert doc["delivered_to"] == []
        assert len(doc["skipped"]) == 3
        assert "AUREM Morning Run" in doc["text_preview"]
        await db[NOTIFY_COLLECTION].delete_many({"run_id": run_id})

    asyncio.run(_run())


def test_dispatch_brief_uses_fallback_env_names(monkeypatch):
    # WHAPI_API_TOKEN (prod name) + ADMIN_ALERT_PHONE should satisfy whapi creds check
    monkeypatch.setenv("WHAPI_API_TOKEN", "dummy_token_value")
    monkeypatch.setenv("ADMIN_ALERT_PHONE", "+10000000000")
    monkeypatch.delenv("WHAPI_TOKEN", raising=False)
    monkeypatch.delenv("NOTIFY_PHONE", raising=False)

    from backend.services.autopilot_brief_notifier import _send_whapi
    result = asyncio.run(_send_whapi("ping"))
    # creds present → will attempt real call and get http error or connect error,
    # but NOT 'creds_missing'
    assert result["reason"] != "creds_missing"


# ───────── End-to-end via fire-now ─────────

def test_fire_now_run_carries_notification_result(admin_token):
    with httpx.Client(timeout=90.0) as c:
        c.post(
            f"{BACKEND_URL}/api/admin/autopilot/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"time": "08:00", "tz": "America/Toronto"},
        )
        r = c.post(
            f"{BACKEND_URL}/api/admin/autopilot/fire-now",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=90.0,
        )
    assert r.status_code == 200
    body = r.json()
    run = body.get("run") or body
    # Run doc must include notification key (Truth-Sync: honest per-run audit)
    assert "notification" in run, f"no notification field in run: {list(run.keys())}"
    notif = run["notification"]
    assert "ok" in notif
    # Either delivered to ≥1 channel OR skipped with reasons — never silently absent
    assert isinstance(notif.get("delivered", []), list)
    assert isinstance(notif.get("skipped", []), list)


def test_notification_persisted_to_autopilot_notifications(admin_token):
    env = _env()

    async def _check():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        # Most-recent notification must exist after fire-now run above
        doc = await db.autopilot_notifications.find_one(
            sort=[("ts_iso", -1)],
        )
        assert doc is not None
        assert "run_id" in doc
        assert "text_preview" in doc
        assert "AUREM Morning Run" in doc["text_preview"]

    asyncio.run(_check())
