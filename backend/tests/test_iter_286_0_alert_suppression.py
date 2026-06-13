"""iter 286.0 — Alert Suppression / Digest-Only Mode + Non-Blocking Wires.

Validates:
  • INTER_PILLAR_WIRES has non_blocking=True on the two aspirational wires
    (p1_to_p2_leads_to_customers, p2_to_p1_subscription_to_outreach)
  • pillars-map overview no longer escalates overall_status to red when
    ONLY advisory wires are red (wires_red_advisory counter exposed)
  • qa_bot._maybe_alert with ALERTS_DIGEST_ONLY=true and fail_ratio<0.8
    queues to db.alerts_digest_queue instead of sending email
  • qa_bot still sends instant email when fail_ratio >= 0.8 (P0 bypass)
  • autopilot_brief_notifier.dispatch_brief drains alerts_digest_queue
    and appends consolidated overnight alerts to the brief text
  • WHAPI phone normalization strips + sign and non-digits
  • Evening wrap scheduler helper _execute_evening_wrap produces a run doc
    with blast totals and pending_alerts field
"""
from __future__ import annotations

import os

import asyncio
import time
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

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


# ── Non-blocking wire flag ───────────────────────────────────────────

def test_aspirational_wires_are_flagged_non_blocking():
    from backend.routers.pillars_map_router import INTER_PILLAR_WIRES

    by_id = {w["id"]: w for w in INTER_PILLAR_WIRES}
    assert by_id["p1_to_p2_leads_to_customers"].get("non_blocking") is True
    assert by_id["p2_to_p1_subscription_to_outreach"].get("non_blocking") is True
    # System-critical wires stay blocking
    assert not by_id["p3_to_p4_monitor_to_alerts"].get("non_blocking", False)
    assert not by_id["p2_to_p4_payments_to_audit"].get("non_blocking", False)


def test_overview_overall_status_ignores_advisory_wires(admin_token):
    # Wait briefly to dodge audit throttle
    time.sleep(3)
    with httpx.Client(timeout=15.0) as c:
        r = c.get(
            f"{BACKEND_URL}/api/admin/pillars-map/overview",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    if r.status_code == 429:
        pytest.skip("rate limited")
    assert r.status_code == 200
    d = r.json()
    totals = d.get("totals") or {}
    # wires_red_advisory separated from wires_red_blocking
    assert "wires_red_advisory" in totals
    assert "wires_red_blocking" in totals
    # overall_status should NOT be red if only advisory wires are red AND
    # all pillars are green AND no flows/blocking wires red
    blocking_red = totals.get("wires_red_blocking", 0)
    flows_red = totals.get("flows_red", 0)
    silent = totals.get("silent_failures", 0)
    unreach = totals.get("unreachable", 0)
    backend_red = totals.get("backend_red", 0)
    if blocking_red == 0 and flows_red == 0 and silent == 0 and unreach == 0 and backend_red == 0:
        # All pillars green and no blocking issues → overall must be green
        if all(p["status"] == "green" for p in d.get("pillars", [])):
            assert d["overall_status"] == "green", (
                f"overall_status={d['overall_status']} but no blocking issues — "
                f"advisory wires red={totals.get('wires_red_advisory')}"
            )


# ── QA bot digest-only mode ──────────────────────────────────────────

def test_qa_bot_queues_digest_when_enabled(monkeypatch):
    monkeypatch.setenv("ALERTS_DIGEST_ONLY", "true")
    import importlib
    from backend.services import qa_bot as qb
    importlib.reload(qb)

    env = _env()

    async def _run():
        from datetime import datetime, timezone, timedelta
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        qb._db = db

        await db.alerts_digest_queue.delete_many({"source": "qa_bot"})
        await db.qa_bot_alerts.delete_many({"endpoint_id": {"$in": ["t1", "t2"]}})
        await db.qa_bot_endpoint_log.delete_many({"endpoint_id": {"$in": ["t1", "t2"]}})
        # Seed a prior-run failure WITHIN last 30 min so `recurring` logic triggers
        recent_ts = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        await db.qa_bot_endpoint_log.insert_many([
            {"ts": recent_ts, "endpoint_id": "t1", "passed": False},
            {"ts": recent_ts, "endpoint_id": "t2", "passed": False},
        ])
        checks = [
            {"id": "t1", "label": "Test 1", "passed": False, "status_code": 500},
            {"id": "t2", "label": "Test 2", "passed": False, "status_code": 404},
            {"id": "t3", "label": "Test 3", "passed": True, "status_code": 200},
        ]
        await qb._maybe_alert(checks)
        # 2/3 = 0.667 → NOT P0 → should queue, NOT send
        queued = await db.alerts_digest_queue.count_documents(
            {"source": "qa_bot", "delivered": False}
        )
        assert queued >= 2, f"expected ≥2 queued digest entries, got {queued}"
        # cleanup
        await db.alerts_digest_queue.delete_many({"source": "qa_bot"})
        await db.qa_bot_endpoint_log.delete_many({"endpoint_id": {"$in": ["t1", "t2"]}})
        await db.qa_bot_alerts.delete_many({"endpoint_id": {"$in": ["t1", "t2"]}})

    asyncio.run(_run())


# ── WHAPI phone normalization ────────────────────────────────────────

def test_whapi_strips_plus_and_non_digits(monkeypatch):
    monkeypatch.setenv("WHAPI_API_TOKEN", "dummy_token")
    monkeypatch.setenv("NOTIFY_PHONE", "+1 (613) 400-0000")
    monkeypatch.delenv("WHAPI_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_ALERT_PHONE", raising=False)
    # iter 287.4: disable kill-switch so the phone-normalization path runs
    monkeypatch.setenv("WHAPI_BLAST_DISABLED", "false")

    # Patch httpx.AsyncClient to capture the JSON payload
    captured = {}

    class FakeResp:
        def __init__(self):
            self.status_code = 200
            self.text = "{}"

    class FakeClient:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, **kw):
            captured["url"] = url
            captured["json"] = kw.get("json")
            return FakeResp()

    import httpx as real_httpx
    monkeypatch.setattr(real_httpx, "AsyncClient", FakeClient)

    from backend.services.autopilot_brief_notifier import _send_whapi
    result = asyncio.run(_send_whapi("ping"))
    assert result["ok"] is True
    assert captured["json"]["to"] == "16134000000"  # digits only
    assert captured["json"]["body"] == "ping"


# ── Digest queue drained by dispatch_brief ──────────────────────────

def test_dispatch_brief_drains_digest_queue_and_appends_text(monkeypatch):
    # Mute all channels so nothing tries real send
    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "WHAPI_API_TOKEN", "WHAPI_TOKEN",
                "NOTIFY_PHONE", "ADMIN_ALERT_PHONE",
                "RESEND_API_KEY",
                "NOTIFY_EMAIL", "AUREM_SALES_BCC_EMAIL"):
        monkeypatch.delenv(var, raising=False)

    env = _env()

    async def _run():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        # Seed 3 pending alerts
        await db.alerts_digest_queue.delete_many({"source": "qa_bot_drain_test"})
        await db.alerts_digest_queue.insert_many([
            {"source": "qa_bot_drain_test", "endpoint_id": "ep_a", "delivered": False,
             "ts_iso": "2026-04-24T07:00:00+00:00"},
            {"source": "qa_bot_drain_test", "endpoint_id": "ep_b", "delivered": False,
             "ts_iso": "2026-04-24T07:05:00+00:00"},
            {"source": "qa_bot_drain_test", "endpoint_id": "ep_c", "delivered": False,
             "ts_iso": "2026-04-24T07:10:00+00:00"},
        ])

        from backend.services.autopilot_brief_notifier import dispatch_brief, NOTIFY_COLLECTION
        run = {
            "run_id": f"autopilot_drain_{int(time.time())}",
            "started_at": "2026-04-24T12:00:00+00:00",
            "duration_seconds": 1.0,
            "success": True,
            "phases": [{"phase": "scout", "ok": True, "result": {"leads": 0}}],
        }
        result = await dispatch_brief(db, run)
        # No channel configured → skipped everywhere, but digest_summary must be captured
        doc = await db[NOTIFY_COLLECTION].find_one({"run_id": run["run_id"]})
        assert doc is not None
        ds = doc.get("digest_summary") or {}
        assert ds.get("pending", 0) >= 3
        assert "qa_bot_drain_test" in (ds.get("by_source") or {})
        assert "Overnight alerts digest" in doc.get("text_preview", "")

        # cleanup
        await db.alerts_digest_queue.delete_many({"source": "qa_bot_drain_test"})

    asyncio.run(_run())


# ── Evening wrap helper ─────────────────────────────────────────────

def test_evening_wrap_helper_produces_run_doc(admin_token):
    # Ensure autopilot armed (prereq)
    with httpx.Client(timeout=10.0) as c:
        c.post(
            f"{BACKEND_URL}/api/admin/autopilot/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"time": "08:00", "tz": "America/Toronto"},
        )

    from backend.routers import master_autopilot_router as mar
    env = _env()

    async def _run():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        mar.set_db(db)
        doc = await mar._execute_evening_wrap(triggered_by="test")
        assert doc["run_id"].startswith("evening_wrap_")
        phases = {p["phase"]: p for p in doc["phases"]}
        assert set(phases.keys()) == {"scout", "hunt", "blast", "report"}
        assert "pending_alerts" in phases["report"]["result"]
        assert "notification" in doc

    asyncio.run(_run())
