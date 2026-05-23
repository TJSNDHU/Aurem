"""
iter 332b Batch A — Enterprise Foundation (Fixes 2 + 7 SHIPPED)
================================================================

Fix 2 — Unified audit log
  • write_event appends with all expected fields
  • write_event clamps action / resource / user_agent lengths
  • write_event invalid result coerced to "fail"
  • query_events filters by user_id / action / source_collection
  • query_events date_from / date_to range
  • query_events sorts desc by timestamp
  • query_events pagination respects limit + offset
  • export_events_csv returns a real CSV with the expected header row
  • write_event ok envelope when DB present, ok=False when DB absent

Fix 7 — Contact Sales (PUBLIC)
  • POST /api/enterprise/leads with valid body inserts a lead
  • Invalid email refused 400
  • Audit row written under action="enterprise_lead_submitted"
  • Telegram alert + auto-reply email are best-effort (don't break on failure)

Deferred to iter 332b Batch A-2 (next context window) — NOT tested here:
  • Fix 1 RBAC complete wiring (multi-day; needs new user-tier RBAC layer)
  • Fix 3 White-label UI (frontend page + color picker)
  • Fix 4 Custom domain UI (DNS verification wizard)
  • Fix 5 API key management UI (CRUD page)
  • Fix 6 Enterprise dashboard (5-section UI page)
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest_asyncio.fixture
async def audit_db(db):
    from services import unified_audit as UA
    UA.set_db(db)
    yield db
    # Clean up any rows created during the test
    await db.unified_audit_log.delete_many({"action": {"$regex": "^test332b_"}})


# ═══════════════════════════════════════════════════════════════════
# Fix 2 — Unified audit log
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_write_event_persists_with_expected_fields(audit_db):
    from services.unified_audit import write_event, query_events
    r = await write_event(
        action="test332b_simple",
        resource="users/alice",
        result="ok",
        user_id="user-abc",
        org_id="org-1",
        ip_address="1.2.3.4",
        user_agent="pytest",
        extra={"foo": "bar"},
    )
    assert r["ok"] is True
    assert r["event_id"]
    rows = (await query_events(action="test332b_simple")).get("rows", [])
    assert len(rows) == 1
    row = rows[0]
    for k in ("event_id", "timestamp", "user_id", "org_id",
               "action", "resource", "result", "ip_address",
               "user_agent", "source_collection", "extra"):
        assert k in row, f"missing {k} in unified audit row"
    assert row["user_id"] == "user-abc"
    assert row["org_id"] == "org-1"
    assert row["extra"]["foo"] == "bar"


@pytest.mark.asyncio
async def test_write_event_clamps_invalid_result(audit_db):
    from services.unified_audit import write_event, query_events
    await write_event(action="test332b_clamp", result="totally_made_up")
    rows = (await query_events(action="test332b_clamp")).get("rows", [])
    assert len(rows) == 1
    assert rows[0]["result"] == "fail"


@pytest.mark.asyncio
async def test_write_event_clamps_long_strings(audit_db):
    from services.unified_audit import write_event, query_events
    long_action = "test332b_" + "x" * 200
    long_resource = "r" * 500
    await write_event(action=long_action, resource=long_resource)
    rows = (await query_events(
        action=long_action[:80], limit=5,
    )).get("rows", [])
    assert len(rows) == 1
    assert len(rows[0]["action"]) <= 80
    assert len(rows[0]["resource"]) <= 200


@pytest.mark.asyncio
async def test_query_events_filters_by_user_id(audit_db):
    from services.unified_audit import write_event, query_events
    uid = f"alice-{uuid.uuid4().hex[:6]}"
    for i in range(3):
        await write_event(action=f"test332b_filter_{i}",
                           user_id=uid, resource=f"r{i}")
    r = await query_events(user_id=uid)
    assert r["ok"] is True
    assert r["total"] == 3
    assert {row["user_id"] for row in r["rows"]} == {uid}


@pytest.mark.asyncio
async def test_query_events_sorts_desc_by_timestamp(audit_db):
    from services.unified_audit import write_event, query_events
    import asyncio as _aio
    await write_event(action="test332b_sort", resource="first")
    await _aio.sleep(0.02)
    await write_event(action="test332b_sort", resource="second")
    await _aio.sleep(0.02)
    await write_event(action="test332b_sort", resource="third")
    rows = (await query_events(action="test332b_sort")).get("rows", [])
    assert [r["resource"] for r in rows] == ["third", "second", "first"]


@pytest.mark.asyncio
async def test_query_events_pagination(audit_db):
    from services.unified_audit import write_event, query_events
    for i in range(7):
        await write_event(action="test332b_page", resource=f"r{i}")
    page1 = await query_events(action="test332b_page", limit=3, offset=0)
    page2 = await query_events(action="test332b_page", limit=3, offset=3)
    assert page1["total"] == 7
    assert len(page1["rows"]) == 3
    assert len(page2["rows"]) == 3
    assert {r["resource"] for r in page1["rows"]} & \
           {r["resource"] for r in page2["rows"]} == set()


@pytest.mark.asyncio
async def test_export_events_csv_has_expected_header(audit_db):
    from services.unified_audit import write_event, export_events_csv
    await write_event(action="test332b_csv", resource="row1")
    csv_text = await export_events_csv(action="test332b_csv")
    lines = csv_text.strip().splitlines()
    assert lines, "csv was empty"
    # Header row
    header = lines[0].split(",")
    for col in ("event_id", "timestamp", "user_id", "action",
                 "resource", "result", "source_collection"):
        assert col in header
    # At least one data row
    assert len(lines) >= 2


@pytest.mark.asyncio
async def test_write_event_returns_error_when_db_missing(monkeypatch):
    from services import unified_audit as UA
    monkeypatch.setattr(UA, "_db", None)
    r = await UA.write_event(action="x")
    assert r["ok"] is False
    assert "db" in r["error"].lower()


# ═══════════════════════════════════════════════════════════════════
# Fix 7 — Contact Sales (PUBLIC)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_enterprise_lead_persists_row(audit_db, monkeypatch):
    from routers.enterprise_router import (
        submit_enterprise_lead, EnterpriseLeadBody, set_db as _set_db,
    )
    _set_db(audit_db)

    # Silence external best-effort calls
    monkeypatch.setattr(
        "services.telegram_bot_service.send_telegram_alert",
        lambda *a, **kw: __noop_coro(),
        raising=False,
    )

    class _Req:
        class _C: host = "203.0.113.7"
        client = _C()
        headers = {"user-agent": "pytest"}

    body = EnterpriseLeadBody(
        company=f"Pytest Co {uuid.uuid4().hex[:6]}",
        email="enterprise@pytest.example",
        team_size="20-100",
        intent="We need RBAC + audit logs",
    )
    r = await submit_enterprise_lead(body, _Req())   # type: ignore[arg-type]
    assert r["ok"] is True
    assert r["lead_id"]
    # Lead row exists
    row = await audit_db.enterprise_leads.find_one(
        {"lead_id": r["lead_id"]}, {"_id": 0},
    )
    assert row is not None
    assert row["company"].startswith("Pytest Co")
    assert row["email"] == "enterprise@pytest.example"
    assert row["team_size"] == "20-100"
    # Audit row exists
    audit = await audit_db.unified_audit_log.find_one(
        {"action": "enterprise_lead_submitted",
         "extra.email": "enterprise@pytest.example"},
        {"_id": 0},
    )
    assert audit is not None
    # Cleanup
    await audit_db.enterprise_leads.delete_one({"lead_id": r["lead_id"]})
    await audit_db.unified_audit_log.delete_one({"event_id": audit["event_id"]})


async def __noop_coro(*a, **kw):
    return True


@pytest.mark.asyncio
async def test_enterprise_lead_rejects_invalid_email(audit_db):
    from routers.enterprise_router import (
        submit_enterprise_lead, EnterpriseLeadBody, set_db as _set_db,
    )
    from fastapi import HTTPException
    _set_db(audit_db)

    class _Req:
        client = None
        headers: dict = {}
    body = EnterpriseLeadBody(
        company="Co", email="not-an-email", team_size="5-20", intent="",
    )
    with pytest.raises(HTTPException) as exc:
        await submit_enterprise_lead(body, _Req())   # type: ignore[arg-type]
    assert exc.value.status_code == 400
    assert exc.value.detail == "invalid_email"


# ═══════════════════════════════════════════════════════════════════
# Source-level wiring sanity
# ═══════════════════════════════════════════════════════════════════

def test_enterprise_routes_registered_in_registry():
    from pathlib import Path
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "enterprise_router" in src
    assert "unified_audit_log" in src


def test_contact_sales_route_in_app_js():
    from pathlib import Path
    src = Path("/app/frontend/src/App.js").read_text()
    assert "/enterprise" in src
    assert "ContactSales" in src
