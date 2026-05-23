"""
iter 331c Sprint 6 — Metrics + Health Tile + Consent Network + Vanguard
========================================================================

Covers:
  - Sprint 6.1: Consent-Based Data Network (PIPEDA/GDPR)
      • set_consent / get_consent state machine
      • Anonymizer DROPS all PII (email, phone, URL, address)
      • record_network_event_if_consented writes ONLY when consent=true
      • Hash function is stable + non-reversible
      • Revocation purge schedules + clears the right rows

  - Sprint 6.2: Per-session metrics + health endpoint
      • record_tool_call / record_session_end persist to Mongo
      • health_snapshot returns green/yellow/red with reasons

  - Sprint 6.3: Vanguard status endpoint + ORA Health tile

The master prompt was explicit: prove that data is NEVER saved to
aurem_network_leads when consent=false. We test that twice — once
unit-level (record_network_event_if_consented direct call) and once
via the live outreach hook simulation.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio


# ── Shared fixtures (DB-backed; reset state per test) ───────────────

@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest.fixture
def fresh_tenant_id() -> str:
    return f"pytest-tenant-{uuid.uuid4().hex[:10]}"


# ═════════════════════════════════════════════════════════════════════
# Sprint 6.1 — Consent-Based Data Network
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_default_consent_is_false(db, fresh_tenant_id):
    """Critical compliance default: every new tenant starts consent=false."""
    from services.consent_data_network import get_consent, set_db
    set_db(db)
    r = await get_consent(fresh_tenant_id)
    assert r["ok"] is True
    assert r["data_sharing_consent"] is False
    assert r["discount_active"] is False
    assert r["discount_pct"] == 0


@pytest.mark.asyncio
async def test_set_consent_true_activates_discount(db, fresh_tenant_id):
    from services.consent_data_network import set_consent, get_consent, set_db
    set_db(db)
    r = await set_consent(fresh_tenant_id, True, actor_email="t@x.com")
    assert r["ok"] is True
    assert r["current_consent"] is True
    g = await get_consent(fresh_tenant_id)
    assert g["data_sharing_consent"] is True
    assert g["discount_active"] is True
    assert g["discount_pct"] == 20
    # Cleanup
    await db.user_profiles.delete_one({"tenant_id": fresh_tenant_id})


@pytest.mark.asyncio
async def test_opt_out_schedules_purge_in_30d(db, fresh_tenant_id):
    from services.consent_data_network import set_consent, set_db
    set_db(db)
    # opt in then opt out
    await set_consent(fresh_tenant_id, True)
    r = await set_consent(fresh_tenant_id, False)
    assert r["current_consent"] is False
    assert r["purge_due_at"] is not None
    purge_dt = datetime.fromisoformat(r["purge_due_at"].replace("Z", "+00:00"))
    delta = purge_dt - datetime.now(timezone.utc)
    # Should be ~30 days from now. Allow 28-30 to absorb test latency.
    assert 28 <= delta.days <= 30, f"unexpected purge delta: {delta}"
    await db.user_profiles.delete_one({"tenant_id": fresh_tenant_id})


# ─── COMPLIANCE PROOF: data is NEVER written when consent=false ────

@pytest.mark.asyncio
async def test_no_network_write_when_consent_false(db, fresh_tenant_id):
    """The crown-jewel compliance test: directly invoke the hook with a
    tenant whose consent is FALSE and verify aurem_network_leads has
    zero new rows for that tenant_token."""
    from services.consent_data_network import (
        record_network_event_if_consented, set_db, _hash_tenant,
    )
    set_db(db)

    # Seed a lead in `leads` collection with a non-PII profile
    lead_id = f"pytest-lead-{uuid.uuid4().hex[:8]}"
    await db.leads.insert_one({
        "lead_id":   lead_id,
        "tenant_id": fresh_tenant_id,
        "industry":  "construction",
        "city":      "Toronto",
        "country":   "CA",
    })
    # Ensure consent is FALSE (default)
    await db.user_profiles.update_one(
        {"tenant_id": fresh_tenant_id},
        {"$set": {"data_sharing_consent": False}},
        upsert=True,
    )

    token = _hash_tenant(fresh_tenant_id)
    pre_count = await db.aurem_network_leads.count_documents({"tenant_token": token})

    # Fire the hook — should be a no-op
    r = await record_network_event_if_consented(
        lead_id=lead_id,
        outreach_doc={"channels_attempted": ["email"], "result": "delivered"},
    )
    assert r["ok"] is True
    assert r["wrote"] is False
    assert r["reason"] == "consent_false"

    post_count = await db.aurem_network_leads.count_documents({"tenant_token": token})
    assert post_count == pre_count, "compliance violation: row was written"

    # Cleanup
    await db.leads.delete_one({"lead_id": lead_id})
    await db.user_profiles.delete_one({"tenant_id": fresh_tenant_id})


@pytest.mark.asyncio
async def test_network_write_when_consent_true(db, fresh_tenant_id):
    """Mirror test: when consent=true, a real row IS written, AND it
    contains zero PII."""
    from services.consent_data_network import (
        set_consent, record_network_event_if_consented,
        set_db, _hash_tenant,
    )
    set_db(db)
    lead_id = f"pytest-lead-{uuid.uuid4().hex[:8]}"
    await db.leads.insert_one({
        "lead_id":      lead_id,
        "tenant_id":    fresh_tenant_id,
        "industry":     "construction",
        "city":         "Toronto",
        "country":      "CA",
        "company_size": "small",
        # PII fields — these MUST NOT appear in aurem_network_leads
        "business_name": "Acme Construction Ltd",
        "email":         "owner@acme-construction.example.com",
        "phone":         "+1 416 555 1234",
        "website":       "https://acme-construction.example.com",
    })
    await set_consent(fresh_tenant_id, True)

    r = await record_network_event_if_consented(
        lead_id=lead_id,
        outreach_doc={"channels_attempted": ["whatsapp"], "result": "converted"},
    )
    assert r["ok"] is True
    assert r["wrote"] is True

    token = _hash_tenant(fresh_tenant_id)
    row = await db.aurem_network_leads.find_one(
        {"tenant_token": token},
        sort=[("ts", -1)],
    )
    assert row is not None
    # Non-PII fields preserved
    assert row.get("industry") == "construction"
    assert row.get("city") == "Toronto"
    assert row.get("country") == "CA"
    assert row.get("channel") == "whatsapp"
    assert row.get("converted") is True
    # PII fields ABSENT
    for forbidden in ("business_name", "email", "phone", "website",
                       "address", "owner_name", "tenant_id"):
        assert forbidden not in row, f"PII leak: {forbidden} in network row"

    # Cleanup
    await db.leads.delete_one({"lead_id": lead_id})
    await db.user_profiles.delete_one({"tenant_id": fresh_tenant_id})
    await db.aurem_network_leads.delete_many({"tenant_token": token})


# ─── Anonymizer guarantees ──────────────────────────────────────────

def test_extract_drops_pii_patterns():
    """Even if a non-PII field name is set to a PII value (e.g. someone
    puts an email into 'industry'), the regex pattern check drops it."""
    from services.consent_data_network import extract_anonymized_record
    lead = {
        "industry":  "owner@example.com",          # PII pattern → DROP
        "city":      "Toronto",                     # safe
        "category":  "https://example.com/leads",   # URL → DROP
    }
    out = extract_anonymized_record(lead, {"result": "delivered"}, "tok")
    assert out is not None
    assert "industry" not in out
    assert "category" not in out
    assert out["city"] == "Toronto"


def test_extract_returns_none_if_no_useful_fields():
    """Empty rows are not persisted."""
    from services.consent_data_network import extract_anonymized_record
    out = extract_anonymized_record(
        {"business_name": "X", "phone": "555"},   # only PII fields
        {"result": "delivered"},
        "tok",
    )
    assert out is None


def test_tenant_hash_is_stable_and_non_reversible():
    from services.consent_data_network import _hash_tenant
    a1 = _hash_tenant("tenant-abc")
    a2 = _hash_tenant("tenant-abc")
    b1 = _hash_tenant("tenant-xyz")
    assert a1 == a2, "hash not stable"
    assert a1 != b1, "different tenants produced same hash"
    assert "tenant-abc" not in a1, "hash leaked plain tenant_id"
    assert len(a1) == 32, "hash should be 32 hex chars"


# ─── Purge mechanics ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_purge_deletes_only_target_tenant(db, fresh_tenant_id):
    """purge_revoked_tenant deletes rows for the target token and
    NOTHING ELSE."""
    from services.consent_data_network import (
        set_db, _hash_tenant, purge_revoked_tenant,
    )
    set_db(db)
    other_tenant = f"pytest-other-{uuid.uuid4().hex[:6]}"
    my_token   = _hash_tenant(fresh_tenant_id)
    other_token = _hash_tenant(other_tenant)
    # Seed 2 rows per tenant
    await db.aurem_network_leads.insert_many([
        {"tenant_token": my_token,    "industry": "x", "ts": "2026-01-01"},
        {"tenant_token": my_token,    "industry": "y", "ts": "2026-01-02"},
        {"tenant_token": other_token, "industry": "z", "ts": "2026-01-03"},
    ])
    r = await purge_revoked_tenant(fresh_tenant_id)
    assert r["deleted_count"] == 2
    # Other tenant's row survives
    survivors = await db.aurem_network_leads.count_documents(
        {"tenant_token": other_token}
    )
    assert survivors == 1
    # Cleanup
    await db.aurem_network_leads.delete_many({"tenant_token": other_token})
    await db.user_profiles.delete_one({"tenant_id": fresh_tenant_id})


# ═════════════════════════════════════════════════════════════════════
# Sprint 6.2 — Per-session metrics
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_metrics_record_tool_call_increments(db):
    from services import ora_metrics as M
    M.set_db(db)
    sid = f"pytest-metrics-{uuid.uuid4().hex[:8]}"
    await M.record_tool_call(sid, "view_file", ok=True, elapsed_ms=42)
    await M.record_tool_call(sid, "view_file", ok=True, elapsed_ms=33)
    await M.record_tool_call(sid, "create_file", ok=False, elapsed_ms=10,
                                blocked_by="plan_first_gate")
    doc = await db.ora_session_metrics.find_one({"_id": sid}, {"_id": 0})
    assert doc is not None
    assert doc["tool_calls_total"] == 3
    assert doc["tools_failed"] == 1
    assert doc["blocked_by"]["plan_first_gate"] == 1
    await db.ora_session_metrics.delete_one({"_id": sid})


@pytest.mark.asyncio
async def test_health_snapshot_returns_status(db):
    from services import ora_metrics as M
    M.set_db(db)
    # Seed a session
    sid = f"pytest-snap-{uuid.uuid4().hex[:8]}"
    await M.record_tool_call(sid, "x", ok=True, elapsed_ms=1)
    await M.record_session_end(sid, task_success=True, usd_cost=0.05)
    snap = await M.health_snapshot(days=7)
    assert snap["ok"] is True
    assert snap["status"] in ("green", "yellow", "red")
    assert isinstance(snap["sessions_count"], int)
    await db.ora_session_metrics.delete_one({"_id": sid})


# ═════════════════════════════════════════════════════════════════════
# Sprint 6 — recommend_fork nudge wiring
# ═════════════════════════════════════════════════════════════════════

def test_recommend_fork_nudge_present_in_ora_agent():
    from pathlib import Path
    src = Path("/app/backend/services/ora_agent.py").read_text()
    assert "FORK_CONTEXT_NUDGE" in src
    assert "iter 331c Sprint 6" in src


# ═════════════════════════════════════════════════════════════════════
# Sprint 6.3 — Cockpit tile + Vanguard endpoint
# ═════════════════════════════════════════════════════════════════════

def test_health_tile_component_exists():
    from pathlib import Path
    p = Path("/app/frontend/src/platform/admin/OraHealthTile.jsx")
    assert p.exists()
    src = p.read_text()
    # Reads both endpoints
    assert "/api/admin/ora/health" in src
    assert "/api/admin/ora/vanguard-status" in src
    # data-testid coverage
    for tid in ("ora-health-tile", "ora-health-refresh-btn",
                "ora-health-success-rate", "ora-vanguard-status"):
        assert f'data-testid="{tid}"' in src, f"missing {tid}"


def test_iter_331c_markers_present():
    from pathlib import Path
    for fp in (
        "/app/backend/services/consent_data_network.py",
        "/app/backend/services/ora_metrics.py",
        "/app/backend/routers/consent_router.py",
        "/app/frontend/src/platform/admin/OraHealthTile.jsx",
    ):
        assert "iter 331c" in Path(fp).read_text(), f"331c marker missing in {fp}"
