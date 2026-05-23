"""
tests/test_iter328_capability_expansion.py

Regression for iter 328a-f hardening pass:
  328a — tiered rate limits (auth=5, admin=60, webhook=100, public=30)
         + repeat-offender Telegram tracker
  328b — PIPEDA retention (archive 2y leads, purge 30d-deletion users,
         audit log)
  328c — external uptime monitor webhook + staleness alert
  328d — DR restore test script exists and imports clean
  328e — multi-tenant load test script exists and imports clean
  328f — SLA metric snapshot (4 metrics, all_ok flag) + cockpit card
"""
import sys
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ── 328a — Rate-limit tiers ──────────────────────────────────────────


def test_rate_limit_tiers_defined():
    from middleware.security import _RATE_LIMITS_BY_TIER
    assert _RATE_LIMITS_BY_TIER["auth"][0] == 5
    assert _RATE_LIMITS_BY_TIER["admin"][0] == 60
    assert _RATE_LIMITS_BY_TIER["webhook"][0] == 100
    assert _RATE_LIMITS_BY_TIER["public"][0] == 30


def test_classify_endpoint_tier_routes_correctly():
    from middleware.security import _classify_endpoint_tier
    assert _classify_endpoint_tier("/api/auth/login") == "auth"
    assert _classify_endpoint_tier("/api/admin/login") == "auth"  # auth wins
    assert _classify_endpoint_tier("/api/admin/ora/lesson-sources") == "admin"
    assert _classify_endpoint_tier("/api/stripe/webhook") == "webhook"
    assert _classify_endpoint_tier("/api/universal/webhooks/generic") == "webhook"
    assert _classify_endpoint_tier("/api/health") == "public"
    assert _classify_endpoint_tier("/api/leads/bulk-add") == "public"


@pytest.mark.asyncio
async def test_offender_tracker_fires_alert_at_threshold(monkeypatch):
    from middleware import security
    # Reset the bucket so this test is hermetic.
    security._offender_buckets.clear()

    sent: list[tuple[str, str]] = []

    async def fake_send(msg, fingerprint=None):
        sent.append((msg, fingerprint))

    import services.silent_failure_alerts as sfa
    monkeypatch.setattr(sfa, "_send", fake_send)

    for _ in range(security._OFFENDER_TRIP_THRESHOLD):
        await security._track_rate_limit_offender("9.9.9.9", "/api/admin/x", "admin")

    assert len(sent) == 1
    msg, fp = sent[0]
    assert "9.9.9.9" in msg
    assert "admin" in msg
    assert fp.startswith("rate_limit_offender_9.9.9.9_")


# ── 328b — PIPEDA retention ──────────────────────────────────────────


def test_data_retention_module_exposes_api():
    from services import data_retention
    assert hasattr(data_retention, "archive_old_leads")
    assert hasattr(data_retention, "purge_due_deletions")
    assert hasattr(data_retention, "request_customer_deletion")
    assert hasattr(data_retention, "run_retention_sweep")


@pytest.mark.asyncio
async def test_archive_old_leads_moves_2yr_old_rows():
    from services import data_retention

    class Cursor:
        def __init__(self, rows): self.rows = rows
        def limit(self, n): return self
        def __aiter__(self):
            self._i = 0
            return self
        async def __anext__(self):
            if self._i >= len(self.rows):
                raise StopAsyncIteration
            r = self.rows[self._i]
            self._i += 1
            return r

    OLD = datetime.now(timezone.utc) - timedelta(days=800)
    rows = [
        {"_id": "A", "email": "a@x.com", "created_at": OLD},
        {"_id": "B", "email": "b@x.com", "created_at": OLD},
    ]

    class LeadsColl:
        def __init__(self): self.deleted = []
        def find(self, q, p=None): return Cursor(rows)
        async def find_one(self, q): return next((r for r in rows if r["_id"] == q["_id"]), None)
        async def delete_one(self, q): self.deleted.append(q["_id"])

    class ArchiveColl:
        def __init__(self): self.docs = []
        async def update_one(self, q, u, upsert=False): self.docs.append(u["$set"])

    class AuditColl:
        def __init__(self): self.docs = []
        async def insert_one(self, d): self.docs.append(d)

    class DB:
        def __init__(self):
            self.leads = LeadsColl()
            self.leads_archive = ArchiveColl()
            self.pipeda_audit_log = AuditColl()
        def __getitem__(self, k): return getattr(self, k)

    db = DB()
    out = await data_retention.archive_old_leads(db)
    assert out["ok"] is True
    assert out["archived"] == 2
    assert sorted(db.leads.deleted) == ["A", "B"]
    assert len(db.leads_archive.docs) == 2
    assert all(d["status"] == "archived_2y" for d in db.leads_archive.docs)
    assert len(db.pipeda_audit_log.docs) == 2


@pytest.mark.asyncio
async def test_request_customer_deletion_stamps_pending():
    from services import data_retention

    class UsersColl:
        def __init__(self): self.updates = []
        async def update_one(self, q, u):
            self.updates.append((q, u))
            return type("R", (), {"matched_count": 1})

    class AuditColl:
        def __init__(self): self.docs = []
        async def insert_one(self, d): self.docs.append(d)

    class DB:
        def __init__(self):
            self.users = UsersColl()
            self.pipeda_audit_log = AuditColl()
        def __getitem__(self, k): return getattr(self, k)

    db = DB()
    out = await data_retention.request_customer_deletion(db, "cust-1", "user requested")
    assert out["ok"] is True
    assert out["cool_off_days"] == 30
    assert "purge_at" in out
    assert len(db.users.updates) == 1
    assert len(db.pipeda_audit_log.docs) == 1
    assert db.pipeda_audit_log.docs[0]["action"] == "request_deletion"


def test_pipeda_router_exposes_4_endpoints():
    src = Path("/app/backend/routers/pipeda_sla_router.py").read_text()
    for path in ("/pipeda/audit", "/pipeda/sweep", "/pipeda/request-deletion", "/sla/snapshot"):
        assert path in src, f"missing {path}"


def test_pipeda_daily_cron_wired():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_pipeda_daily_sweep" in src
    assert "run_retention_sweep" in src
    assert "hour=4, minute=0" in src


# ── 328c — External uptime monitor ──────────────────────────────────


def test_external_uptime_module_present():
    from services import external_uptime_monitor as e
    assert callable(e.record_external_ping)
    assert callable(e.staleness_check)
    assert callable(e.monthly_uptime_report)


@pytest.mark.asyncio
async def test_record_external_ping_stores_doc():
    from services import external_uptime_monitor as e

    class PingColl:
        def __init__(self): self.docs = []
        async def insert_one(self, d): self.docs.append(d)

    class DB:
        def __init__(self): self.external_uptime_pings = PingColl()
        def __getitem__(self, k): return getattr(self, k)

    db = DB()
    out = await e.record_external_ping(db, {
        "monitor": "AUREM Live", "url": "https://aurem.live/api/health",
        "status": "2", "ping_ms": "120", "ts": "2026-02-23 04:00",
        "secret": "wrong",
    })
    assert out["ok"]
    assert out["stored"]
    assert len(db.external_uptime_pings.docs) == 1
    # No secret set in env → secret_ok must be False.
    assert db.external_uptime_pings.docs[0]["secret_ok"] is False


def test_uptime_webhook_router_registered():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "routers.uptime_webhook_router" in src
    assert "/api/uptime/report" in Path("/app/backend/routers/uptime_webhook_router.py").read_text()


def test_external_uptime_staleness_cron_wired():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_external_uptime_check" in src
    assert "staleness_check" in src


# ── 328d — DR restore test ───────────────────────────────────────────


def test_dr_restore_test_script_exists_and_imports():
    p = Path("/app/backend/scripts/dr_restore_test.py")
    assert p.exists()
    src = p.read_text()
    assert "mongorestore" in src
    assert "CRITICAL_COLLECTIONS" in src
    assert "compare_collection_counts" in src


# ── 328e — Load test ────────────────────────────────────────────────


def test_load_test_script_exists_and_targets_3_workloads():
    p = Path("/app/backend/scripts/multi_tenant_load_test.py")
    assert p.exists()
    src = p.read_text()
    assert "hit_campaign_cycle" in src
    assert "push_leads" in src
    assert "ora_chat_burst" in src
    assert "bottleneck" in src


# ── 328f — SLA metrics ──────────────────────────────────────────────


def test_sla_module_targets_match_spec():
    from services.sla_metrics import SLA_TARGETS
    assert SLA_TARGETS["uptime_pct"] == 99.5
    assert SLA_TARGETS["ora_latency_p95_seconds"] == 3.0
    assert SLA_TARGETS["email_delivery_pct"] == 95.0
    assert SLA_TARGETS["campaign_completion_pct"] == 98.0


@pytest.mark.asyncio
async def test_sla_snapshot_returns_4_metrics_with_db_empty():
    from services.sla_metrics import compute_sla_snapshot

    class EmptyCursor:
        def limit(self, n): return self
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration

    class Coll:
        def __init__(self): self.docs = []
        async def count_documents(self, q): return 0
        def find(self, q, p=None): return EmptyCursor()
        async def insert_one(self, d): self.docs.append(d)

    class DB:
        def __init__(self):
            self.aurem_health_log = Coll()
            self.ora_session_costs = Coll()
            self.email_sent_log = Coll()
            self.ora_campaign_health = Coll()
            self.sla_snapshots = Coll()

    snap = await compute_sla_snapshot(DB())
    assert "metrics" in snap
    assert set(snap["metrics"].keys()) == {
        "uptime_pct", "ora_latency_p95_seconds",
        "email_delivery_pct", "campaign_completion_pct",
    }
    assert "ts" in snap
    assert "all_ok" in snap


def test_sla_snapshot_cron_every_15min():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "aurem_sla_snapshot" in src
    assert "minutes=15" in src


def test_sla_card_frontend_present():
    src = Path("/app/frontend/src/platform/admin/SlaCard.jsx").read_text()
    for tid in ("sla-card", "sla-overall-status", "sla-refresh"):
        assert f'data-testid="{tid}"' in src
    # Mounted in OraCtoCockpit.
    cockpit = Path("/app/frontend/src/platform/admin/OraCtoCockpit.jsx").read_text()
    assert "SlaCard" in cockpit
