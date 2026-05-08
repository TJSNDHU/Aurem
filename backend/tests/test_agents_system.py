"""
Regression tests for the 4-Agent Autonomous System + CASL + A2A bus.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

# Direct imports
from services.casl_compliance import (
    email_footer_html, email_footer_text,
    sms_footer, wrap_sms, wrap_whatsapp, wrap_email_html, compliance_snapshot,
)
from services.a2a_bus import A2ABus, bus as global_bus
from services.agents.hunter_ora import HunterORA, WEEKLY_ROTATION


# ─────────────────────────────────────────────
# CASL Compliance
# ─────────────────────────────────────────────

def test_email_footer_includes_required_casl_elements():
    f = email_footer_html("lead123")
    assert "AUREM Intelligence" in f
    assert "Mississauga" in f
    assert "Unsubscribe" in f
    assert "lead=lead123" in f  # lead_id is appended to unsub URL
    assert "CASL Section 6(6)" in f


def test_email_footer_text_variant():
    f = email_footer_text("lead456")
    assert "AUREM Intelligence" in f
    assert "Unsubscribe" in f
    assert "CASL" in f


def test_sms_footer_compact():
    f = sms_footer()
    assert "STOP" in f
    assert "AUREM" in f
    assert len(f) <= 80  # short enough for SMS


def test_wrap_sms_adds_footer_and_respects_length():
    wrapped = wrap_sms("Hey! Check us out.")
    assert "STOP" in wrapped
    assert len(wrapped) <= 320  # 2 SMS segments max


def test_wrap_sms_idempotent():
    already = "Check us out. Reply STOP to unsubscribe. AUREM Intelligence AI, Mississauga ON."
    assert wrap_sms(already) == already


def test_wrap_whatsapp_adds_footer():
    wrapped = wrap_whatsapp("Hi there")
    assert "STOP" in wrapped
    assert "AUREM" in wrapped


def test_wrap_email_html_adds_footer_and_is_idempotent():
    body = "<p>Hello</p>"
    once = wrap_email_html(body, "abc")
    twice = wrap_email_html(once, "abc")
    assert "Unsubscribe" in once
    assert once == twice  # calling again shouldn't double-append


def test_compliance_snapshot_has_required_keys():
    snap = compliance_snapshot()
    for key in ("legal_name", "legal_address", "unsubscribe_url", "contact_email",
                "hst_number", "casl_section", "pipeda_notice"):
        assert key in snap


# ─────────────────────────────────────────────
# A2A Bus
# ─────────────────────────────────────────────

def test_a2a_bus_emit_stores_in_tail():
    b = A2ABus()
    b.set_db(None)

    async def _go():
        await b.emit("hunter", "test_event", {"x": 1})
        await b.emit("closer", "other_event", {"y": 2})
    asyncio.run(_go())

    recent = b.recent()
    events = {r["event"] for r in recent}
    assert "test_event" in events
    assert "other_event" in events


def test_a2a_bus_fanout_to_subscribers():
    b = A2ABus()
    q = b.subscribe_queue("followup_ora")

    async def _run():
        await b.emit("hunter", "new_lead", {"lead_id": "x"}, to_agent="followup_ora")
        await asyncio.sleep(0.05)
        return q.qsize()

    assert asyncio.run(_run()) >= 1


# ─────────────────────────────────────────────
# Hunter ORA — ramp logic
# ─────────────────────────────────────────────

def test_hunter_safe_ramp_schedule():
    assert HunterORA._ramp_for_week("safe", 1) == 20
    assert HunterORA._ramp_for_week("safe", 2) == 50
    assert HunterORA._ramp_for_week("safe", 3) == 100
    assert HunterORA._ramp_for_week("safe", 4) == 200


def test_hunter_aggressive_ramp_schedule():
    assert HunterORA._ramp_for_week("aggressive", 1) == 50
    assert HunterORA._ramp_for_week("aggressive", 2) == 100
    assert HunterORA._ramp_for_week("aggressive", 3) == 200


def test_hunter_unknown_mode_defaults_to_safe():
    assert HunterORA._ramp_for_week("unknown", 1) == 20


def test_hunter_daily_limit_zero_when_disabled():
    """When auto_hunt_settings.enabled == False, daily limit is 0."""
    async def _run():
        db = MagicMock()
        db.auto_hunt_settings.find_one = AsyncMock(return_value={"enabled": False})
        hunter = HunterORA(db)
        return await hunter.get_daily_limit()
    assert asyncio.run(_run()) == 0


def test_hunter_daily_limit_respects_override():
    """daily_limit_override takes precedence over ramp."""
    async def _run():
        db = MagicMock()
        db.auto_hunt_settings.find_one = AsyncMock(return_value={
            "enabled": True, "daily_limit_override": 75, "activated_at": "2026-01-01T00:00:00+00:00",
        })
        hunter = HunterORA(db)
        return await hunter.get_daily_limit()
    assert asyncio.run(_run()) == 75


def test_weekly_rotation_has_7_days():
    assert set(WEEKLY_ROTATION.keys()) == {0, 1, 2, 3, 4, 5, 6}
    # Each day must have at least 1 territory/industry pair
    for dow, targets in WEEKLY_ROTATION.items():
        assert len(targets) >= 1
        for pair in targets:
            assert len(pair) == 2


# ─────────────────────────────────────────────
# Agent registry
# ─────────────────────────────────────────────

def test_all_agents_register_with_correct_ids():
    from services.agents import register_agents, all_agents
    register_agents(None)  # None db is OK for identity checks
    ids = {a.AGENT_ID for a in all_agents()}
    assert ids == {"hunter_ora", "followup_ora", "closer_ora", "referral_ora"}


def test_agent_pause_resume_toggles_state():
    from services.agents import register_agents, get_agent
    register_agents(None)
    hunter = get_agent("hunter_ora")
    async def _go():
        await hunter.pause()
        assert hunter.paused is True
        await hunter.resume()
        assert hunter.paused is False
    asyncio.run(_go())


def test_agent_snapshot_has_required_fields():
    from services.agents import register_agents, all_agents
    register_agents(None)
    for agent in all_agents():
        snap = agent.snapshot()
        for key in ("agent_id", "name", "emoji", "job", "status", "current_task", "today_stats"):
            assert key in snap
