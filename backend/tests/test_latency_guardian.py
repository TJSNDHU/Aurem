"""Tests for the Auto-Latency Guardian (iter 322f)."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# We test the pure functions and orchestration with a fake DB; no network.
from services import latency_guardian as g


class FakeColl:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)
        return MagicMock(inserted_id="x")

    async def count_documents(self, q):
        n = 0
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if isinstance(v, dict):
                    if "$gte" in v and d.get(k, "") < v["$gte"]:
                        ok = False
                        break
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        ok = False
                        break
                    if "$in" in v and d.get(k) not in v["$in"]:
                        ok = False
                        break
                elif d.get(k) != v:
                    ok = False
                    break
            if ok:
                n += 1
        return n

    def find(self, q, proj=None):  # noqa: ARG002
        def matches(d, query):
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        return False
                    if "$gte" in v and d.get(k, "") < v["$gte"]:
                        return False
                elif d.get(k) != v:
                    return False
            return True

        async def gen():
            for d in self.docs:
                if matches(d, q):
                    yield d
        class _C:
            def __init__(self, gen): self.gen = gen
            def sort(self, *_a, **_k): return self
            def limit(self, *_a, **_k): return self
            def __aiter__(self): return self.gen
        return _C(gen())


class FakeDB:
    def __init__(self):
        self.system_pulse_actions = FakeColl()
        self.admin_alerts = FakeColl()
        self.qa_bot_endpoint_log = FakeColl()


def test_resolve_cache_prefixes_by_id():
    out = g._resolve_cache_prefixes("admin_mission_control_pixel_health", None)
    assert "mc_pixel_health" in out


def test_resolve_cache_prefixes_by_path():
    out = g._resolve_cache_prefixes(
        "unknown_id",
        "/api/admin/mission-control/tenants-summary",
    )
    assert "mc_tenants_summary" in out


def test_resolve_cache_prefixes_no_match():
    out = g._resolve_cache_prefixes("nonexistent", "/api/leads")
    assert out == []


@pytest.mark.asyncio
async def test_log_action_writes():
    db = FakeDB()
    await g._log_action(
        db,
        endpoint_id="x", path="/api/x",
        latency_before=900, latency_after=300,
        action_taken="cache_flush", success=True,
        details={"keys_removed": 3},
    )
    assert len(db.system_pulse_actions.docs) == 1
    doc = db.system_pulse_actions.docs[0]
    assert doc["endpoint_id"] == "x"
    assert doc["action_taken"] == "cache_flush"
    assert doc["latency_before_ms"] == 900
    assert doc["latency_after_ms"] == 300


@pytest.mark.asyncio
async def test_emit_admin_alert_writes_admin_alerts():
    """Legacy fallback channel (iter 322i): admin_alert is now `info`+ack=True
    (autonomous flow handles all decisions)."""
    db = FakeDB()
    await g._emit_admin_alert(
        db, endpoint_id="x", path="/api/x", latency_ms=1500,
    )
    assert len(db.admin_alerts.docs) == 1
    a = db.admin_alerts.docs[0]
    assert a["kind"] == "latency"
    assert a["severity"] == "info"
    assert a["source"] == "latency_guardian"
    assert a["ack"] is True


@pytest.mark.asyncio
async def test_skip_intentional_long_running():
    db = FakeDB()
    run_doc = {
        "started_at": "2026-05-04T00:00:00+00:00",
        "checks": [
            {"id": "seo_audit_scan", "passed": True, "latency_ms": 38000,
             "path": "/api/seo/audit"},
        ],
    }
    summary = await g.run_guardian_after_sweep(db, run_doc)
    assert summary["triaged"] == 0
    assert summary["skipped_intentional"] == 1


@pytest.mark.asyncio
async def test_triages_slow_passing_endpoints():
    db = FakeDB()
    run_doc = {
        "started_at": "2026-05-04T00:00:00+00:00",
        "checks": [
            # passing but slow → triaged
            {"id": "ep1", "passed": True, "latency_ms": 800,
             "path": "/api/admin/mission-control/pixel-health"},
            # failing → ignored (handled by separate alert path)
            {"id": "ep2", "passed": False, "latency_ms": 1000,
             "path": "/api/x"},
            # fast → ignored
            {"id": "ep3", "passed": True, "latency_ms": 120, "path": "/api/y"},
            # intentional long-running → skipped
            {"id": "seo", "passed": True, "latency_ms": 30000, "path": "/api/seo"},
        ],
    }
    # Patch the heal coroutine so we don't actually wait 60s in tests
    with patch.object(g, "_heal_one", new=AsyncMock()):
        summary = await g.run_guardian_after_sweep(db, run_doc)
    assert summary["triaged"] == 1
    assert summary["skipped_intentional"] == 1


@pytest.mark.asyncio
async def test_status_green_when_no_recent_activity():
    db = FakeDB()
    s = await g.get_guardian_status(db)
    assert s["state"] == "green"


@pytest.mark.asyncio
async def test_status_red_when_alert_admin_logged_recently():
    """Legacy alert_admin rows still trigger red (back-compat with pre-322i)."""
    db = FakeDB()
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    db.system_pulse_actions.docs.append(
        {"action_taken": "alert_admin", "ts": ts, "endpoint_id": "x"},
    )
    s = await g.get_guardian_status(db)
    assert s["state"] == "red"
    assert s["alert_count"] >= 1


@pytest.mark.asyncio
async def test_status_yellow_when_council_hold():
    """Council holds = autonomous monitoring → yellow (NOT red, no human)."""
    db = FakeDB()
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    db.system_pulse_actions.docs.append(
        {"action_taken": "council_hold", "ts": ts, "endpoint_id": "x"},
    )
    s = await g.get_guardian_status(db)
    assert s["state"] == "yellow"
    assert s["reason"] == "council_monitoring"


@pytest.mark.asyncio
async def test_status_green_when_council_accepted():
    """Council ACCEPT = case closed; status returns to green."""
    db = FakeDB()
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    db.system_pulse_actions.docs.extend([
        {"action_taken": "sweep_summary", "ts": ts, "triaged": 1},
        {"action_taken": "council_accepted", "ts": ts, "endpoint_id": "x"},
    ])
    s = await g.get_guardian_status(db)
    assert s["state"] == "green"


@pytest.mark.asyncio
async def test_council_decision_defaults_to_hold_when_llm_unavailable():
    """If convene_council fails (e.g. no LLM), guardian must default to HOLD —
    never escalate to a human."""
    db = FakeDB()
    from unittest.mock import patch
    async def boom(*_a, **_k):
        raise RuntimeError("llm-down")
    with patch("services.ora_council.convene_council", side_effect=boom):
        out = await g._council_autonomous_decision(
            db, endpoint_id="x", path="/api/x",
            latency_before=900, latency_after=850,
            actions_so_far=["cache_flush", "index_refresh"],
        )
    assert out["decision"] == "hold"
    assert "council_unavailable" in (out["notes"] or "")


@pytest.mark.asyncio
async def test_get_recent_actions_excludes_sweep_summary():
    db = FakeDB()
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    db.system_pulse_actions.docs.extend([
        {"action_taken": "sweep_summary", "ts": ts, "triaged": 1},
        {"action_taken": "cache_flush", "ts": ts, "endpoint_id": "x"},
        {"action_taken": "alert_admin", "ts": ts, "endpoint_id": "y"},
    ])
    actions = await g.get_recent_actions(db, limit=10)
    kinds = [a.get("action_taken") for a in actions]
    assert "sweep_summary" not in kinds
    # Both non-sweep actions must show up
    assert "cache_flush" in kinds
    assert "alert_admin" in kinds


def test_threshold_env_override(monkeypatch):
    # Reload module with overridden env so the constants pick up the new value
    monkeypatch.setenv("GUARDIAN_THRESHOLD_MS", "650")
    import importlib
    import services.latency_guardian as lg
    importlib.reload(lg)
    assert lg.THRESHOLD_MS == 650
    # Restore default for the rest of the test session
    monkeypatch.setenv("GUARDIAN_THRESHOLD_MS", "400")
    importlib.reload(lg)
