"""
iter 327m — Four critical fixes from the 2026-02-23 brutal audit.

  1. Tool registry / LLM schema reconciliation.
     - Audit found 10 orphan tier entries (LLM saw, no impl) and 17
       hidden registry entries (impl present, LLM blind).
     - Removed the 10 orphans from TIER_2_APPROVE / TIER_3_HIGH_RISK.
     - Added `reconcile_tool_registry()` that runs at module import
       and logs WARN on orphans so a future regression is caught at
       startup, not by the founder seeing "I tried to call X but..."
       in chat.

  2. Vision silent-failure gate.
     - Before: `vision_description != ""` was the gate, but
       `_analyze_image` returns "Image received but analysis failed:
       ..." on error — non-empty string → badge lied "saw image
       via GPT-4o" when analysis had failed.
     - Now: failures are stored in `vision_failed_reason`,
       `vision_description` stays empty, the iter 327k provenance
       badge correctly NEVER fires for failed analyses.

  3. CASL gap in agent-direct outreach.
     - `pillars/sales/routes/auto_blast.py` already checked DNC.
     - `services/armed_outreach.py::_fire_one_lead` did NOT.
     - New shared module `services/casl_gate.py` is the single source
       of truth. `armed_outreach` now calls it BEFORE sending and
       stamps lead.status=do_not_contact on a hit.
     - Fail-closed on errors.

  4. Stripe metered-billing cron.
     - `BillingService.record_overage` was implemented + tested but
       had zero production callers — overages were tracked internally
       and Stripe was NEVER charged.
     - New daily cron `aurem_stripe_overage_daily` (03:00 UTC) in
       routers/registry.py walks every workspace with a meter event
       and a passed period_end, and posts the MeterEvent.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import mongomock_motor
import pytest

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# (1) Tool registry / LLM schema reconciliation
# ─────────────────────────────────────────────

def test_tool_registry_has_no_orphans():
    """Every tool the LLM can call MUST have an implementation."""
    from services.ora_tools import TOOL_REGISTRY
    from services.ora_agent import (
        TIER_1_AUTO, TIER_2_APPROVE, TIER_3_HIGH_RISK,
    )
    tiers = TIER_1_AUTO | TIER_2_APPROVE | TIER_3_HIGH_RISK
    orphan = sorted(tiers - set(TOOL_REGISTRY.keys()))
    assert orphan == [], (
        f"LLM-visible tools with NO impl in TOOL_REGISTRY: {orphan}. "
        f"Either add the impl OR remove from the tier set."
    )


def test_specific_orphans_audit_removed():
    """Brutally specific: the 10 names the 2026-02-23 audit called out."""
    from services.ora_agent import (
        TIER_1_AUTO, TIER_2_APPROVE, TIER_3_HIGH_RISK,
    )
    audit_orphans = {
        "delete_file", "feature_flag_set", "kv_set", "ora_rollback_list",
        "ora_rollback_restore", "prod_env_set", "save_to_github",
        "send_bulk_email", "stripe_charge", "supervisor_restart_all",
    }
    tiers = TIER_1_AUTO | TIER_2_APPROVE | TIER_3_HIGH_RISK
    still_present = audit_orphans & tiers
    assert still_present == set(), (
        f"audit orphans still in tier sets: {still_present}"
    )


def test_reconcile_function_runs_and_returns_clean(caplog):
    import logging
    from services.ora_agent import reconcile_tool_registry
    with caplog.at_level(logging.DEBUG, logger="services.ora_agent"):
        out = reconcile_tool_registry()
    assert out["ok"] is True
    # MUST be clean after the audit fixes
    assert out["orphan"] == [], f"orphan tools: {out['orphan']}"
    # Some hidden tools are intentional (e.g. github_push is locked
    # by being OFF the LLM schema) — just check the function returned them.
    assert isinstance(out["hidden"], list)


def test_reconcile_runs_at_import_time():
    """Source-level: the reconcile call site exists at module level."""
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    assert "reconcile_tool_registry()" in src
    # Must be called inside a try/except at module top-level (not just
    # defined). The marker comment is unique enough.
    assert "Run reconciliation at module import" in src


# ─────────────────────────────────────────────
# (2) Vision silent-failure gate
# ─────────────────────────────────────────────

def test_vision_gate_distinguishes_failure_from_success():
    """The badge gate condition. Reads source so we lock the
    semantic: badge fires ONLY when vision_description is a real
    description, never on the 'analysis failed' sentinel."""
    src = (BACKEND / "routers" / "ora_attachments_router.py").read_text()
    assert 'raw.startswith("Image received but analysis failed")' in src
    # Must NOT just assign the failure string into vision_description.
    assert "vision_failed_reason" in src


def test_record_persists_both_description_and_failed_reason():
    src = (BACKEND / "routers" / "ora_attachments_router.py").read_text()
    # Both fields stored — empty description on failure, reason captured.
    assert '"vision_description": vision_description' in src
    assert '"vision_failed_reason": vision_failed_reason' in src


# ─────────────────────────────────────────────
# (3) CASL gate
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_casl_blocks_when_email_in_do_not_contact():
    from services.casl_gate import is_blocked_by_casl
    db = mongomock_motor.AsyncMongoMockClient()["test_327m_casl_email"]
    await db.do_not_contact.insert_one({
        "email": "opted@out.test", "phone": None,
        "added_at": "2026-02-22T00:00:00+00:00", "reason": "user_request",
    })
    res = await is_blocked_by_casl(db, email="Opted@Out.TEST", phone=None)
    assert res["blocked"] is True
    assert res["reason"] == "on_do_not_contact_list"
    assert res["matched_field"] == "email"


@pytest.mark.asyncio
async def test_casl_blocks_when_phone_in_do_not_contact():
    from services.casl_gate import is_blocked_by_casl
    db = mongomock_motor.AsyncMongoMockClient()["test_327m_casl_phone"]
    await db.do_not_contact.insert_one({
        "email": None, "phone": "14165550100",
        "added_at": "2026-02-22T00:00:00+00:00",
    })
    # Phone normalization: digits-only, accepts +1-416-555-0100.
    res = await is_blocked_by_casl(db, email=None, phone="+1-416-555-0100")
    assert res["blocked"] is True
    assert res["matched_field"] == "phone"


@pytest.mark.asyncio
async def test_casl_blocks_when_user_marked_dnc_flag():
    """A user with dnc=True or status='opted_out' must also be blocked
    even if they're not in the do_not_contact collection yet."""
    from services.casl_gate import is_blocked_by_casl
    db = mongomock_motor.AsyncMongoMockClient()["test_327m_casl_user"]
    await db.users.insert_one(
        {"email": "user@example.com", "dnc": True})
    res = await is_blocked_by_casl(db, email="user@example.com")
    assert res["blocked"] is True
    assert res["reason"] == "user_marked_dnc"


@pytest.mark.asyncio
async def test_casl_allows_clean_recipient():
    from services.casl_gate import is_blocked_by_casl
    db = mongomock_motor.AsyncMongoMockClient()["test_327m_casl_ok"]
    res = await is_blocked_by_casl(
        db, email="fresh@example.com", phone="14165550999")
    assert res["blocked"] is False
    assert res["reason"] == "ok"


@pytest.mark.asyncio
async def test_casl_fails_closed_on_no_identifier():
    """No email AND no phone → blocked (fail-closed)."""
    from services.casl_gate import is_blocked_by_casl
    db = mongomock_motor.AsyncMongoMockClient()["test_327m_casl_noid"]
    res = await is_blocked_by_casl(db, email="", phone="")
    assert res["blocked"] is True
    assert res["reason"] == "no_identifier"


@pytest.mark.asyncio
async def test_casl_fails_closed_on_db_missing():
    from services.casl_gate import is_blocked_by_casl
    res = await is_blocked_by_casl(None, email="a@b.c")
    assert res["blocked"] is True
    assert res["reason"] == "db_unavailable"


@pytest.mark.asyncio
async def test_armed_outreach_calls_casl_gate_before_sending():
    """The agent-direct outreach path now goes through CASL."""
    from services import armed_outreach
    db = mongomock_motor.AsyncMongoMockClient()["test_327m_armed"]
    await db.campaign_leads.insert_one({
        "lead_id":       "L1",
        "business_name": "Acme Inc",
        "email":         "opted@out.test",
        "phone":         None,
    })
    await db.do_not_contact.insert_one(
        {"email": "opted@out.test", "phone": None})

    # If _exec_blast_one were called, the CASL gate failed. Trip a
    # red flag so the test fails loud.
    exec_calls = []
    async def _trapped_exec(*a, **kw):
        exec_calls.append(kw)
        return {"ok": True, "reply": "MUST NOT HAPPEN"}

    with patch("services.ora_command_center._exec_blast_one", new=_trapped_exec):
        res = await armed_outreach._fire_one_lead(db, {}, "L1")
    assert res["ok"] is False
    assert res["error"] == "casl_blocked"
    assert exec_calls == [], "send executor called despite CASL block"
    # Lead row stamped so we don't retry.
    lead = await db.campaign_leads.find_one({"lead_id": "L1"}, {"_id": 0})
    assert lead["status"] == "do_not_contact"
    assert "casl_blocked_at" in lead


# ─────────────────────────────────────────────
# (4) Stripe overage cron
# ─────────────────────────────────────────────

def test_overage_cron_is_registered_in_registry():
    src = (BACKEND / "routers" / "registry.py").read_text()
    # The job exists with the right id, hour, and calls record_overage.
    assert "aurem_stripe_overage_daily" in src
    assert "record_overage" in src
    assert "Stripe overage cron scheduled — daily 03:00 UTC" in src


def test_overage_cron_filters_to_workspaces_with_meter_event_and_period_end_past():
    src = (BACKEND / "routers" / "registry.py").read_text()
    # The query MUST require a meter_event_name (otherwise we'd call
    # record_overage on free-tier workspaces that crash on missing config).
    assert '"billing.stripe_meter_event_name"' in src
    assert '"billing.current_period_end"' in src


def test_overage_cron_handles_per_workspace_failure_without_aborting_sweep():
    """The cron must catch per-workspace exceptions so one bad
    workspace doesn't take down the whole nightly sweep."""
    src = (BACKEND / "routers" / "registry.py").read_text()
    assert "record_overage failed for" in src
    # Inner try/except inside the async for loop
    assert "except Exception as inner" in src


def test_iter_327m_marker_present():
    src1 = (BACKEND / "services" / "ora_agent.py").read_text()
    src2 = (BACKEND / "routers" / "ora_attachments_router.py").read_text()
    src3 = (BACKEND / "services" / "casl_gate.py").read_text()
    src4 = (BACKEND / "services" / "armed_outreach.py").read_text()
    src5 = (BACKEND / "routers" / "registry.py").read_text()
    for name, src in [("ora_agent.py", src1), ("ora_attachments_router.py", src2),
                       ("casl_gate.py", src3), ("armed_outreach.py", src4),
                       ("registry.py", src5)]:
        assert "iter 327m" in src, f"missing iter 327m marker in {name}"
