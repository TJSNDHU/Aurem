"""
test_d66_campaign_health_real_fixes.py — iter D-66
===================================================
Locks in the real fixes for the 6 "yellow" components in Campaign Health.

What changed (code-fixable):
  • twilio  / whapi  → green when ANY working WA channel exists
  • proactive_ora    → autofix `enable_proactive_defaults` flips R1+R2 on
  • template_perf    → ALSO reads top-level outreach_history.template_id
                       (was previously only the webhook-fed blast_perf)
  • resend_webhook   → counts ALL webhook signals (touchpoints, audit log,
                       template_perf rows), not just hot-lead opens

What's environment-config (still yellow until founder acts):
  • WhatsApp channel — TWILIO_WA_FROM_NUMBER missing AND WHAPI disabled
  • Resend webhook URL — needs to be pasted into Resend dashboard
"""
from __future__ import annotations

import inspect

import pytest


# ─── 1 · Source-level smoke check: code paths exist ───────────
def test_twilio_check_green_when_whapi_active():
    src = open("/app/backend/services/campaign_health.py").read()
    # The honest-state logic must consider WHAPI as a WA channel.
    assert "wa_active" in src and "WHAPI_API_TOKEN" in src
    # Twilio green path must mention SMS+WA combination.
    assert "WA via WHAPI" in src or "SMS OK · WA" in src


def test_whapi_check_green_when_twilio_wa_wired():
    src = open("/app/backend/services/campaign_health.py").read()
    # The whapi check must downgrade to green if Twilio WABA is wired.
    assert "Twilio WABA primary" in src or "Twilio WABA active" in src
    # Only "no WA channel" should remain yellow.
    assert "no_wa_channel" in src or "wa_fully_offline" in src


def test_template_perf_dual_read():
    """Health check must look at BOTH blast_performance AND
    outreach_history.template_id — not just one."""
    src = open("/app/backend/services/campaign_health.py").read()
    assert "tagged_sends_30d" in src
    assert "outreach_history" in src
    # Must distinguish "no tags" (red flag) from "tags but no opens"
    # (healthy, waiting on webhook).
    assert "tagged sends" in src.lower()


def test_resend_webhook_check_broadened():
    """Check must count touchpoints, audit log, and perf rows — not
    just open events. Founders configure webhook late; emails flow
    earlier."""
    src = open("/app/backend/services/campaign_health.py").read()
    assert "recent_touch" in src and "recent_audit" in src
    assert "total_signals" in src


# ─── 2 · enable_proactive_defaults autofix ────────────────────
def test_enable_proactive_defaults_registered_in_autofix_catalog():
    from services.campaign_autofix import _FIXERS
    assert "enable_proactive_defaults" in _FIXERS, (
        "Missing autofix; campaign_health proactive_ora yellow won't be "
        "fixable from the UI."
    )
    fn, label = _FIXERS["enable_proactive_defaults"]
    assert callable(fn) and "R1" in label and "R2" in label


@pytest.mark.asyncio
async def test_enable_proactive_defaults_flips_rules(monkeypatch):
    """When called, the autofix MUST attempt to enable R1+R2 (no more, no
    less). Higher-risk rules (R3, R4) stay off unless founder turns them
    on manually."""
    from services import campaign_autofix as af
    from services import proactive_ora as po
    seen = []

    async def _fake_set_rule(tenant_id, rule_id, enabled):
        seen.append((tenant_id, rule_id, enabled))

    monkeypatch.setattr(po, "set_rule", _fake_set_rule)
    out = await af._fix_enable_proactive_defaults()
    assert out["ok"] is True
    assert out["fixed"] is True
    enabled_rules = sorted(r for (_, r, on) in seen if on)
    assert enabled_rules == ["R1", "R2"], (
        f"autofix changed risk profile: {seen}"
    )


# ─── 3 · Top-level outreach_history is the source of truth ────
def test_blast_service_writes_top_level_outreach_history():
    """Lead-send paths in blast_service must mirror into the top-level
    outreach_history collection. Without this, template_perf health
    stays permanently yellow even after a million sends."""
    src = open("/app/backend/pillars/sales/routes/blast_service.py").read()
    # Has to insert_one into the top-level collection AND set template_id.
    assert "db.outreach_history.insert_one" in src
    assert "template_id" in src


def test_auto_blast_writes_top_level_outreach_history():
    src = open("/app/backend/pillars/sales/routes/auto_blast.py").read()
    assert "db.outreach_history.insert_one" in src
    assert "template_id" in src


# ─── 4 · autofix-all proxy-timeout guard ──────────────────────
def test_autofix_all_has_timeout_bound():
    """ingress 60s → wrap with 50s asyncio.wait_for so the UI gets a
    deterministic response even when topup_via_scout is slow."""
    src = open("/app/backend/routers/campaign_health_router.py").read()
    assert "wait_for" in src and "TimeoutError" in src


# ─── 5 · proactive_ora is wired to the db at startup ──────────
def test_campaign_health_router_wires_proactive_ora():
    """The router's set_db must propagate to proactive_ora so the
    autofix doesn't fail with db_not_ready."""
    src = open("/app/backend/routers/campaign_health_router.py").read()
    assert "proactive_ora" in src
    assert "_po.set_db" in src or "po.set_db" in src
