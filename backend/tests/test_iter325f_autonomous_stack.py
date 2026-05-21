"""
Tests for the complete autonomous fix stack — iter 325f Phases 1-6.

Each Phase has its own section. Minimum 5 tests per new service per spec.
"""
import asyncio
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, "/app/backend")


# ───────────────────────────────────────────────────────────────────────
# Fake DB used across every phase. Mirrors the Motor-async surface we
# actually call: insert_one, find_one, find, update_one, count_documents.
# ───────────────────────────────────────────────────────────────────────
class _Cursor:
    def __init__(self, rows): self._rows = list(rows)
    def sort(self, *a, **k):
        # Accept both .sort("ts", -1) and .sort([("ts",-1)]).
        if a and isinstance(a[0], str):
            key, direction = a[0], (a[1] if len(a) > 1 else -1)
        elif a and isinstance(a[0], list) and a[0]:
            key, direction = a[0][0]
        else:
            return self
        self._rows.sort(key=lambda r: r.get(key) or "", reverse=(direction == -1))
        return self
    def limit(self, n): self._rows = self._rows[:n]; return self
    async def to_list(self, n): return self._rows[:n]
    def __aiter__(self):
        async def gen():
            for r in self._rows:
                yield r
        return gen()


class _Coll:
    def __init__(self):
        self.rows = []
    async def insert_one(self, doc):
        self.rows.append(dict(doc))
        return MagicMock(inserted_id="oid")
    async def insert_many(self, docs):
        for d in docs:
            self.rows.append(dict(d))
        return MagicMock()
    async def find_one(self, q=None, projection=None, sort=None):
        # Tolerant of all calls: sort=[("ts",-1)] returns most-recently
        # appended row matching the (very loose) query.
        candidates = self.rows
        if isinstance(q, dict):
            def _match(row):
                for k, v in q.items():
                    if isinstance(v, dict):
                        if "$in" in v and row.get(k) not in v["$in"]:
                            return False
                        if "$gte" in v and (row.get(k) or "") < v["$gte"]:
                            return False
                        if "$ne" in v and row.get(k) == v["$ne"]:
                            return False
                    else:
                        if row.get(k) != v:
                            return False
                return True
            candidates = [r for r in self.rows if _match(r)]
        if sort:
            candidates = sorted(
                candidates,
                key=lambda r: r.get(sort[0][0]) or "",
                reverse=(sort[0][1] == -1),
            )
        return candidates[0] if candidates else None
    def find(self, q=None, projection=None):
        return _Cursor(list(self.rows))
    async def count_documents(self, q):
        if q == {}:
            return len(self.rows)
        return len([1 for r in self.rows if all(r.get(k) == v for k, v in q.items() if not isinstance(v, dict))])
    async def update_one(self, q, update, upsert=False):
        return MagicMock(modified_count=1)


class _DB:
    def __init__(self):
        self._colls = {}
    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        c = self._colls.get(name)
        if c is None:
            c = _Coll()
            self._colls[name] = c
        return c
    def __getitem__(self, name):
        return getattr(self, name)


@pytest.fixture
def fake_db(monkeypatch):
    db = _DB()
    import server as _server_mod
    monkeypatch.setattr(_server_mod, "db", db, raising=False)
    return db


# ═══════════════════════════════════════════════════════════════════════
# Phase 1.1 — error_ledger emits to incident_bus
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_p1_error_ledger_emits_incident_bus(fake_db, monkeypatch):
    from services import error_ledger, incident_bus
    incident_bus.set_db(fake_db) if hasattr(incident_bus, "set_db") else monkeypatch.setattr(incident_bus, "_db", fake_db, raising=False)

    emitted = {}
    async def fake_report(**kw):
        emitted.update(kw)
        return {"ok": True}
    monkeypatch.setattr(incident_bus, "report", fake_report)

    try:
        raise RuntimeError("boom")
    except RuntimeError as e:
        await error_ledger.record_error(e, path="/test")
        await asyncio.sleep(0)  # let the create_task fire

    # The async-create_task may need one more loop iteration.
    for _ in range(5):
        if emitted: break
        await asyncio.sleep(0)
    assert emitted.get("category") == "crash"
    assert emitted.get("source") == "error_ledger"
    assert "RuntimeError" in (emitted.get("title") or "")


# ═══════════════════════════════════════════════════════════════════════
# Phase 1.2 — qa_bot emits to incident_bus on 2+ consecutive failures
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_p1_qa_bot_emits_incident_bus_on_recurring_failure(fake_db, monkeypatch):
    from services import qa_bot, incident_bus
    monkeypatch.setattr(qa_bot, "_db", fake_db, raising=False)
    monkeypatch.setattr(incident_bus, "_db", fake_db, raising=False)

    emitted = []
    async def fake_report(**kw):
        emitted.append(kw)
        return {"ok": True}
    monkeypatch.setattr(incident_bus, "report", fake_report)

    checks = [
        {"id": "/api/foo", "passed": False, "status_code": 500, "url": "http://x"},
        {"id": "/api/bar", "passed": True},
    ]
    # Prior failure row → recurring
    await fake_db.qa_bot_endpoint_log.insert_one(
        {"endpoint_id": "/api/foo", "passed": False, "ts": "2024-01-01"}
    )
    # Force "no throttle" by simulating empty qa_bot_alerts
    await qa_bot._maybe_alert(checks)
    cats = [e["category"] for e in emitted]
    assert "endpoint_failure" in cats
    foo_emit = [e for e in emitted if "/api/foo" in (e.get("signature") or "")]
    assert foo_emit, "must emit specifically for the failing endpoint"
    assert foo_emit[0]["source"] == "qa_bot"


# ═══════════════════════════════════════════════════════════════════════
# Phase 1.3 — shannon HIGH/CRITICAL writes pending_approvals row
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_p1_shannon_high_critical_enqueues_approval(fake_db):
    from services import shannon_security
    report = {
        "target": "https://example.com",
        "timestamp": "2024-01-01T00:00:00Z",
        "vulnerabilities": [
            {"id": "ssl-1", "title": "Weak TLS", "severity": "critical",
             "fix_suggestion": "Upgrade to TLS 1.3"},
            {"id": "low-1", "title": "Minor",   "severity": "low"},
        ],
    }
    await shannon_security.ingest_report(report)
    pa = fake_db.pending_approvals.rows
    assert len(pa) == 1, f"only critical should enqueue from ingest_report, got {len(pa)}"
    assert pa[0]["severity"] == "critical"
    assert pa[0]["type"] == "security_fix"
    assert "Upgrade to TLS 1.3" in pa[0]["detail"]


def test_p1_pending_approvals_helper_exists():
    from services.pending_approvals import create_pending_approval
    assert asyncio.iscoroutinefunction(create_pending_approval)


@pytest.mark.asyncio
async def test_p1_pending_approvals_dedupes_within_24h(fake_db):
    from services.pending_approvals import create_pending_approval
    r1 = await create_pending_approval(type="security_fix", title="X",
                                        fingerprint="fp1", source="shannon",
                                        db=fake_db)
    r2 = await create_pending_approval(type="security_fix", title="X",
                                        fingerprint="fp1", source="shannon",
                                        db=fake_db)
    assert r1.get("approval_id")
    assert r2.get("deduped") is True
    assert r2["approval_id"] == r1["approval_id"]


# ═══════════════════════════════════════════════════════════════════════
# Phase 2 — ORA CTO Repair Agent
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_p2_cto_unreachable_is_handled_gracefully(fake_db, monkeypatch):
    """When the LLM gateway returns an error, the tick should mark
    the proposal `llm_unavailable` and never raise. The legacy
    'cto_unavailable' counter is preserved for back-compat."""
    from services import ora_cto_repair_agent as agent
    await fake_db.pending_approvals.insert_one({
        "approval_id": "abc", "type": "crash", "severity": "medium",
        "status": "pending_approval", "title": "t", "detail": "d",
        "created_at": "2024-01-01",
    })
    async def fake_ask(_a):
        return {"ok": False, "error": "gateway_unavailable",
                "sensitive": False}
    monkeypatch.setattr(agent, "_ask_cto", fake_ask)

    stats = await agent.run_repair_tick(fake_db)
    assert stats["ok"] is True
    assert stats["considered"] == 1
    assert stats["llm_unavailable"] >= 1
    assert stats["cto_unavailable"] >= 1  # back-compat counter
    props = fake_db.ora_cto_proposals.rows
    assert len(props) == 1 and props[0]["status"] == "llm_unavailable"


@pytest.mark.asyncio
async def test_p2_cto_success_tier1_classifies_and_records(fake_db, monkeypatch):
    from services import ora_cto_repair_agent as agent
    await fake_db.pending_approvals.insert_one({
        "approval_id": "tier1", "type": "endpoint_failure",
        "severity": "medium", "status": "pending_approval",
        "title": "endpoint", "detail": "x", "created_at": "2024-01-01",
    })
    async def fake_ask(_a):
        return {"ok": True, "elapsed_ms": 12, "sensitive": False,
                "provider": "openrouter", "model": "deepseek/deepseek-chat-v3.1",
                "response": "PROPOSED FIX: change env var FOO single-line edit"}
    monkeypatch.setattr(agent, "_ask_cto", fake_ask)
    monkeypatch.setattr(agent, "_notify_founder", AsyncMock())

    stats = await agent.run_repair_tick(fake_db)
    assert stats["tier1"] == 1 and stats["tier2"] == 0
    # Proposal row captures gateway provider/model.
    props = fake_db.ora_cto_proposals.rows
    assert props[0]["llm_provider"] == "openrouter"
    assert props[0]["llm_model"] == "deepseek/deepseek-chat-v3.1"


@pytest.mark.asyncio
async def test_p2_sensitive_path_forces_claude_via_gateway(fake_db, monkeypatch):
    """auth/billing/JWT issues MUST be flagged sensitive so the
    gateway's privacy guard strips DeepSeek and forces Claude."""
    from services import ora_cto_repair_agent as agent
    await fake_db.pending_approvals.insert_one({
        "approval_id": "sens", "type": "security_fix",
        "severity": "medium", "status": "pending_approval",
        "title": "Stripe webhook signature verification bypass",
        "detail": "JWT token validation skipped on /api/billing",
        "created_at": "2024-01-01",
    })
    captured = {}
    async def fake_route(*, task_type, prompt, system=None, max_tokens=1500):
        captured["task_type"] = task_type
        return {"ok": True, "text": "PROPOSED FIX: rotate stripe key",
                "provider": "anthropic", "model": "claude-sonnet-4-5-20250929",
                "latency_ms": 800, "tokens_in": 100, "tokens_out": 50}
    import services.llm_gateway_v2 as gw
    monkeypatch.setattr(gw, "route", fake_route)
    monkeypatch.setattr(agent, "_notify_founder", AsyncMock())

    stats = await agent.run_repair_tick(fake_db)
    # MUST have used the sensitive task type so DeepSeek is banned.
    assert captured.get("task_type") == "auth_token_decision"
    assert stats["sensitive_routed"] == 1
    # Proposal records sensitive=True + Claude provider.
    props = fake_db.ora_cto_proposals.rows
    assert props[0]["sensitive"] is True
    assert props[0]["llm_provider"] == "anthropic"


def test_p2_is_sensitive_keywords():
    from services.ora_cto_repair_agent import _is_sensitive
    assert _is_sensitive({"title": "JWT verify failure", "detail": ""}) is True
    assert _is_sensitive({"title": "x", "detail": "Stripe webhook"}) is True
    assert _is_sensitive({"title": "TOTP wrong", "detail": ""}) is True
    assert _is_sensitive({"title": "Slow homepage", "detail": "LCP > 3s"}) is False
    assert _is_sensitive({"title": "endpoint 500", "detail": "/api/foo"}) is False


@pytest.mark.asyncio
async def test_p2_non_sensitive_uses_repair_diagnose(fake_db, monkeypatch):
    from services import ora_cto_repair_agent as agent
    await fake_db.pending_approvals.insert_one({
        "approval_id": "ns", "type": "endpoint_failure",
        "severity": "low", "status": "pending_approval",
        "title": "Slow homepage", "detail": "LCP regressed",
        "created_at": "2024-01-01",
    })
    captured = {}
    async def fake_route(*, task_type, prompt, system=None, max_tokens=1500):
        captured["task_type"] = task_type
        return {"ok": True, "text": "PROPOSED FIX: enable CDN",
                "provider": "openrouter", "model": "deepseek/deepseek-chat-v3.1",
                "latency_ms": 400, "tokens_in": 100, "tokens_out": 50}
    import services.llm_gateway_v2 as gw
    monkeypatch.setattr(gw, "route", fake_route)
    monkeypatch.setattr(agent, "_notify_founder", AsyncMock())

    await agent.run_repair_tick(fake_db)
    assert captured.get("task_type") == "repair_diagnose"


@pytest.mark.asyncio
async def test_p2_cto_high_severity_always_tier2(fake_db, monkeypatch):
    from services import ora_cto_repair_agent as agent
    await fake_db.pending_approvals.insert_one({
        "approval_id": "tier2-sec", "type": "security_fix",
        "severity": "high", "status": "pending_approval",
        "title": "vuln", "detail": "x", "created_at": "2024-01-01",
    })
    async def fake_ask(_a):
        return {"ok": True, "elapsed_ms": 9, "sensitive": False,
                "provider": "openrouter", "model": "deepseek/deepseek-chat-v3.1",
                "response": "single-line env var change"}  # would normally be tier-1
    monkeypatch.setattr(agent, "_ask_cto", fake_ask)
    notified = AsyncMock()
    monkeypatch.setattr(agent, "_notify_founder", notified)

    stats = await agent.run_repair_tick(fake_db)
    assert stats["tier2"] == 1 and stats["tier1"] == 0
    notified.assert_awaited_once()


def test_p2_classify_tier_pure_function():
    from services.ora_cto_repair_agent import _classify_tier
    assert _classify_tier("change env var SINGLE-LINE", "medium") == 1
    assert _classify_tier("change env var single-line", "critical") == 2  # severity wins
    assert _classify_tier("multi-file refactor", "medium") == 2
    assert _classify_tier("rewrite the auth module entirely", "low") == 2


def test_p2_registered_in_registry_under_300s_interval():
    src = open("/app/backend/routers/registry.py").read()
    assert 'id="ora_cto_repair_agent"' in src
    assert "_cto_repair_tick" in src or "ora_cto_repair_agent" in src
    assert "seconds=300" in src.split('id="ora_cto_repair_agent"')[0][-400:] + src.split('id="ora_cto_repair_agent"')[1][:200]


# ═══════════════════════════════════════════════════════════════════════
# Phase 3a — self-audit auto-trigger
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_p3_self_audit_emits_incident_on_low_score(fake_db, monkeypatch):
    from services import self_audit_scheduler
    monkeypatch.setenv("SELF_AUDIT_ALERT_THRESHOLD", "70")
    async def fake_run(_db):
        return {"overall_score": 40, "target": "x", "findings": [{"a": 1}]}
    import sys
    fake_mod = type(sys)("services.self_audit")
    fake_mod.run_self_audit = fake_run
    monkeypatch.setitem(sys.modules, "services.self_audit", fake_mod)

    emitted = {}
    async def fake_report(**kw):
        emitted.update(kw)
        return {"ok": True}
    from services import incident_bus
    monkeypatch.setattr(incident_bus, "report", fake_report)

    out = await self_audit_scheduler.run_self_audit_tick(fake_db)
    assert out["emitted"] is True
    assert emitted["category"] == "self_audit_low_score"
    assert emitted["severity"] == "high"  # 40 < (70-20)


@pytest.mark.asyncio
async def test_p3_self_audit_skips_emit_on_good_score(fake_db, monkeypatch):
    from services import self_audit_scheduler
    monkeypatch.setenv("SELF_AUDIT_ALERT_THRESHOLD", "70")
    async def fake_run(_db):
        return {"overall_score": 90, "target": "x"}
    import sys
    fake_mod = type(sys)("services.self_audit")
    fake_mod.run_self_audit = fake_run
    monkeypatch.setitem(sys.modules, "services.self_audit", fake_mod)
    out = await self_audit_scheduler.run_self_audit_tick(fake_db)
    assert out["emitted"] is False


def test_p3_self_audit_cron_scheduled_every_6h():
    src = open("/app/backend/routers/registry.py").read()
    assert 'id="self_audit_cron"' in src
    assert "hours=6" in src.split('id="self_audit_cron"')[0][-400:]


# ═══════════════════════════════════════════════════════════════════════
# Phase 3b — QA Guardian
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_p3_qa_guardian_escalates_on_3_consec(fake_db, monkeypatch):
    from services import qa_guardian, incident_bus
    # Latest pulse with /api/foo failing.
    await fake_db.qa_bot_runs.insert_one({
        "ts": "2024-01-01T00:03:00Z",
        "checks": [{"id": "/api/foo", "passed": False}],
    })
    for ts in ("2024-01-01T00:00:00Z", "2024-01-01T00:01:00Z", "2024-01-01T00:02:00Z"):
        await fake_db.qa_bot_endpoint_log.insert_one(
            {"endpoint_id": "/api/foo", "passed": False, "ts": ts}
        )
    emitted = []
    async def fake_report(**kw): emitted.append(kw); return {"ok": True}
    monkeypatch.setattr(incident_bus, "report", fake_report)

    out = await qa_guardian.run_guardian_tick(fake_db)
    assert out["escalations"] >= 1
    assert "/api/foo" in out["endpoint_ids"]
    assert any(e["category"] == "endpoint_failure" for e in emitted)


@pytest.mark.asyncio
async def test_p3_qa_guardian_no_escalate_without_streak(fake_db, monkeypatch):
    from services import qa_guardian
    await fake_db.qa_bot_runs.insert_one({
        "ts": "2024-01-01T00:03:00Z",
        "checks": [{"id": "/api/foo", "passed": False}],
    })
    # Only 1 prior failure → streak 2 < threshold 3.
    await fake_db.qa_bot_endpoint_log.insert_one(
        {"endpoint_id": "/api/foo", "passed": False, "ts": "2024-01-01T00:00:00Z"}
    )
    out = await qa_guardian.run_guardian_tick(fake_db)
    assert out["escalations"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Phase 4 — Shannon Autofix
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_p4_shannon_autofix_enqueues_low_medium(fake_db):
    from services import shannon_autofix
    await fake_db.shannon_reports.insert_one({
        "created_at": "2024-01-01T00:00:00Z",
        "target": "https://x",
        "vulnerabilities": [
            {"id": "a", "title": "A", "severity": "low",   "fix_suggestion": "fa"},
            {"id": "b", "title": "B", "severity": "medium","fix_suggestion": "fb"},
            {"id": "c", "title": "C", "severity": "high"},  # not enqueued here
        ],
    })
    out = await shannon_autofix.shannon_autofix_tick(fake_db)
    assert out["sev_counts"]["low"] == 1
    assert out["sev_counts"]["high"] == 1
    assert out["queued_low_med"] == 2  # low + medium


@pytest.mark.asyncio
async def test_p4_shannon_autofix_no_reports_returns_clean(fake_db):
    from services import shannon_autofix
    out = await shannon_autofix.shannon_autofix_tick(fake_db)
    assert out["ok"] is True and out["reason"] == "no_reports"


def test_p4_shannon_autofix_scheduled():
    src = open("/app/backend/routers/registry.py").read()
    assert 'id="shannon_autofix"' in src


# ═══════════════════════════════════════════════════════════════════════
# Phase 5 — React Doctor monitor
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_p5_react_doctor_emits_incident_on_big_drop(fake_db, monkeypatch):
    from services import react_doctor_monitor, incident_bus
    # Latest must come first when sorted by ts desc.
    await fake_db.react_doctor_runs.insert_one(
        {"score": 70, "ts": "2024-01-01"}
    )
    await fake_db.react_doctor_runs.insert_one(
        {"score": 60, "ts": "2024-01-02"}  # drop of 10
    )
    emitted = []
    async def fake_report(**kw): emitted.append(kw); return {"ok": True}
    monkeypatch.setattr(incident_bus, "report", fake_report)

    out = await react_doctor_monitor.react_doctor_monitor_tick(fake_db)
    assert out["drop"] == 10
    assert out["incident_emitted"] is True
    assert emitted[0]["category"] == "frontend_regression"


@pytest.mark.asyncio
async def test_p5_react_doctor_no_runs_returns_clean(fake_db):
    from services import react_doctor_monitor
    out = await react_doctor_monitor.react_doctor_monitor_tick(fake_db)
    assert out["ok"] and out["reason"] == "no_runs"


@pytest.mark.asyncio
async def test_p5_react_doctor_no_drop_no_incident(fake_db, monkeypatch):
    from services import react_doctor_monitor, incident_bus
    await fake_db.react_doctor_runs.insert_one({"score": 75, "ts": "2024-01-01"})
    await fake_db.react_doctor_runs.insert_one({"score": 74, "ts": "2024-01-02"})
    emitted = []
    async def fake_report(**kw): emitted.append(kw); return {"ok": True}
    monkeypatch.setattr(incident_bus, "report", fake_report)
    out = await react_doctor_monitor.react_doctor_monitor_tick(fake_db)
    assert out["drop"] == 1
    assert out["incident_emitted"] is False


def test_p5_react_doctor_monitor_scheduled():
    src = open("/app/backend/routers/registry.py").read()
    assert 'id="react_doctor_monitor"' in src
    assert "days=7" in src.split('id="react_doctor_monitor"')[0][-400:]


# ═══════════════════════════════════════════════════════════════════════
# Phase 6 — unified health endpoint
# ═══════════════════════════════════════════════════════════════════════
def test_p6_router_registered_with_prefix():
    from routers import system_health_full_router as r
    assert r.router.prefix == "/api/admin"
    paths = {x.path for x in r.router.routes}
    assert "/api/admin/system-health-full" in paths


@pytest.mark.asyncio
async def test_p6_health_full_requires_admin_jwt(fake_db, monkeypatch):
    from routers import system_health_full_router as r
    r.set_db(fake_db)
    monkeypatch.setenv("JWT_SECRET", "shh")
    from fastapi import HTTPException
    # Missing bearer → 401
    with pytest.raises(HTTPException) as exc:
        await r.system_health_full(authorization=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_p6_health_full_returns_all_9_sections(fake_db, monkeypatch):
    from routers import system_health_full_router as r
    r.set_db(fake_db)
    monkeypatch.setenv("JWT_SECRET", "shh")
    import jwt
    tok = jwt.encode({"is_super_admin": True, "email": "x"}, "shh", algorithm="HS256")
    out = await r.system_health_full(authorization=f"Bearer {tok}")
    for section in ("qa_bot", "error_ledger", "incident_bus", "shannon",
                    "autonomous_repair", "anomaly_detector", "campaign",
                    "react_doctor", "ora_cto"):
        assert section in out, f"missing section {section}"


# ═══════════════════════════════════════════════════════════════════════
# Iter 325g — admin ORA CTO chat now defaults to DeepSeek V3.1
# ═══════════════════════════════════════════════════════════════════════
def test_admin_chat_openrouter_defaults_to_deepseek():
    """services/llm_gateway.py is the OLDER gateway used by
    /api/ora-chat/ask (the admin CTO+Paw conversational endpoint).
    Iter 325g switched its OpenRouter primary from claude-haiku to
    DeepSeek V3.1. Customer-facing llm_gateway_v2 was already on DeepSeek."""
    src = open("/app/backend/services/llm_gateway.py", encoding="utf-8").read()
    assert "deepseek/deepseek-chat-v3.1" in src
    # And the env override hook must exist so we can swap quickly.
    assert "ORA_CTO_OPENROUTER_MODEL" in src
    assert "ORA_CTO_OPENROUTER_TEMP" in src


@pytest.mark.asyncio
async def test_admin_chat_openrouter_uses_env_override(monkeypatch):
    """Setting ORA_CTO_OPENROUTER_MODEL must override the DeepSeek
    default — useful for incident response when a model is degraded."""
    from services import llm_gateway as gw
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    monkeypatch.setenv("ORA_CTO_OPENROUTER_MODEL", "anthropic/claude-3.5-haiku")

    captured = {}

    class _Resp:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None):
            captured["model"] = json["model"]
            captured["temperature"] = json["temperature"]
            return _Resp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    out = await gw._try_openrouter("sys", "hello", 200)
    assert out == "ok"
    assert captured["model"] == "anthropic/claude-3.5-haiku"
    # Default temp is 0.3 (lower than the legacy 0.4).
    assert captured["temperature"] == 0.3
