"""
iter 282al-21 — Tests for services.ora_god_mode (ORA God-Mode Brain)
====================================================================
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock


# ─────────── intent detection ───────────
def test_detect_intent_outreach():
    from services.ora_god_mode import _detect_intent
    assert _detect_intent("write email for this plumber") == "outreach"


def test_detect_intent_code():
    from services.ora_god_mode import _detect_intent
    assert _detect_intent("fix bug in scout_agent.py") == "code"


def test_detect_intent_greeting():
    from services.ora_god_mode import _detect_intent
    assert _detect_intent("hi") == "greeting"
    assert _detect_intent("thanks") == "greeting"


def test_detect_intent_scan():
    from services.ora_god_mode import _detect_intent
    assert _detect_intent("scan this website for me please") == "scan"


def test_detect_intent_seo():
    from services.ora_god_mode import _detect_intent
    assert _detect_intent("find unlinked mentions for this brand") == "seo"


def test_detect_intent_general_fallback():
    from services.ora_god_mode import _detect_intent
    assert _detect_intent("aurora alpine zebra wave xenon") == "general"


# ─────────── confidence ───────────
def test_calculate_confidence_high():
    from services.ora_god_mode import _calculate_confidence
    score = _calculate_confidence(
        "Hi Mike — burst pipe calls go to whoever shows up first on Google. "
        "We built your website preview already. Worth 30 seconds? "
        "aurem.live/r/abc",
        "write outreach", "outreach",
        {"business_name": "Mike's Plumbing"},
    )
    assert score >= 65


def test_calculate_confidence_low_hedging():
    from services.ora_god_mode import _calculate_confidence
    score = _calculate_confidence(
        "I think maybe this could possibly work, perhaps.",
        "write outreach", "outreach",
    )
    assert score < 60


def test_calculate_confidence_empty_zero():
    from services.ora_god_mode import _calculate_confidence
    assert _calculate_confidence("", "x", "outreach") == 0


# ─────────── validate + CASL auto-fix ───────────
mock_lead_ctx = {
    "business_name": "Mike's Plumbing", "city": "Mississauga",
    "category": "plumber", "site_score": 31, "admin": False,
}


def test_validate_adds_casl_to_outreach():
    from services.ora_god_mode import _validate_and_fix
    result = _validate_and_fix(
        "Hi, visit our site today!", "outreach",
        "write email for plumber", mock_lead_ctx,
    )
    assert result["casl_checked"] is True
    assert result["casl_passed"] is True
    assert "stop" in result["response"].lower()


def test_validate_no_casl_on_greeting():
    from services.ora_god_mode import _validate_and_fix
    result = _validate_and_fix(
        "Hi! How can I help?", "greeting", "hi", {},
    )
    assert result["casl_checked"] is False


def test_validate_preserves_existing_stop_path():
    from services.ora_god_mode import _validate_and_fix
    result = _validate_and_fix(
        "Hi Mike — quick note. Reply STOP to opt out.",
        "outreach", "x", mock_lead_ctx,
    )
    # Should NOT double-add CASL footer
    assert result["response"].lower().count("reply stop") == 1


# ─────────── skill loader ───────────
@pytest.mark.asyncio
async def test_load_relevant_skills_returns_list():
    from services.ora_god_mode import _load_relevant_skills
    skills = await _load_relevant_skills(
        "write email for plumber", "outreach", max_skills=3,
    )
    assert isinstance(skills, list)
    assert len(skills) <= 3


@pytest.mark.asyncio
async def test_load_relevant_skills_skips_snapshot():
    from services.ora_god_mode import _load_relevant_skills
    skills = await _load_relevant_skills("anything", "general", max_skills=10)
    assert all(s["name"] != "ora_knowledge_snapshot" for s in skills)


# ─────────── system prompt ───────────
def test_build_system_prompt_has_identity():
    from services.ora_god_mode import _build_system_prompt
    prompt = _build_system_prompt(
        intent="outreach", skills=[], context=mock_lead_ctx,
        snapshot="", emotion=None,
    )
    assert "ORA" in prompt
    assert "Canada" in prompt
    assert "Mississauga" in prompt
    assert "Mike's Plumbing" in prompt


def test_build_system_prompt_emotion_angry():
    from services.ora_god_mode import _build_system_prompt
    prompt = _build_system_prompt(
        intent="outreach", skills=[], context={},
        snapshot="", emotion="angry",
    )
    pl = prompt.lower()
    assert "frustrated" in pl or "patient" in pl


def test_build_system_prompt_with_snapshot():
    from services.ora_god_mode import _build_system_prompt
    prompt = _build_system_prompt(
        intent="general", skills=[], context={},
        snapshot="## TOP PERFORMING\n- plumber outreach > 12% reply rate\n",
        emotion=None,
    )
    assert "ACCUMULATED KNOWLEDGE" in prompt
    assert "12%" in prompt


# ─────────── snapshot fallback ───────────
def test_knowledge_snapshot_fallback():
    from services.ora_god_mode import _load_knowledge_snapshot
    snap = _load_knowledge_snapshot()
    assert isinstance(snap, str)


# ─────────── agency-agent extraction ───────────
def test_agency_agents_extracted():
    agents = list((Path(__file__).resolve().parent.parent / "ora_skills").glob("agent_*.md"))
    assert len(agents) >= 10, f"Only {len(agents)} agency agents extracted."


# ─────────── log to DB ───────────
@pytest.mark.asyncio
async def test_brain_session_logs_to_db():
    from services.ora_god_mode import _log_brain_session
    db = MagicMock()
    db.brain_sessions.insert_one = AsyncMock(return_value=None)
    await _log_brain_session(db, {
        "user_message": "test", "intent": "test",
        "skills_used": [], "confidence": 80,
        "casl_checked": False, "casl_passed": True,
        "emotion": None, "response_words": 20,
        "ts": datetime.now(timezone.utc),
    })
    db.brain_sessions.insert_one.assert_awaited_once()


# ─────────── full ora_think_and_respond w/ stubbed gateway ───────────
@pytest.mark.asyncio
async def test_ora_think_and_respond_full_flow(monkeypatch):
    """End-to-end with stubbed llm_gateway.call_llm — verifies CASL auto-fix +
    skills_used + db log."""
    import services.ora_god_mode as gm
    import services.llm_gateway as gw

    async def _fake_call(sys_prompt, user_prompt, max_tokens=400, **kw):
        return "Hi Mike, noticed your site has no booking form. Worth a look?"

    monkeypatch.setattr(gw, "call_llm", _fake_call, raising=False)

    db = MagicMock()
    db.brain_sessions.insert_one = AsyncMock(return_value=None)

    out = await gm.ora_think_and_respond(
        "write outreach email for Mike's Plumbing",
        context=mock_lead_ctx,
        db=db,
        session_history=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hi! How can I help?"},
        ],
        emotion="happy",
    )
    assert out["intent"] == "outreach"
    assert out["casl_checked"] is True
    assert "stop" in out["response"].lower()
    assert out["confidence"] > 0
    assert isinstance(out["skills_used"], list)


@pytest.mark.asyncio
async def test_ora_think_and_respond_returns_fallback_on_gateway_failure(monkeypatch):
    import services.ora_god_mode as gm
    import services.llm_gateway as gw

    async def _bad_call(*a, **kw):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(gw, "call_llm", _bad_call, raising=False)
    db = MagicMock()
    db.brain_sessions.insert_one = AsyncMock(return_value=None)

    out = await gm.ora_think_and_respond("anything complex here", {}, db, [], None)
    assert out["confidence"] == 0
    assert out["intent"] == "unknown"
    assert "moment" in out["response"].lower()


# ─────────── self-training ───────────
@pytest.mark.asyncio
async def test_self_training_skips_with_too_few_sessions():
    from services.ora_god_mode import ora_self_training

    class _Cursor:
        def __init__(self, r): self._r = r
        async def to_list(self, length=None): return self._r

    db = MagicMock()
    db.brain_sessions.find = MagicMock(return_value=_Cursor([
        {"intent": "outreach", "confidence": 50, "casl_passed": True, "skills_used": []},
    ]))
    db.ora_training_log.insert_one = AsyncMock(return_value=None)
    out = await ora_self_training(db)
    assert out["sessions_analyzed"] == 1
    assert out["skills_improved"] == []  # too few samples


# ─────────── health endpoint ───────────
@pytest.mark.asyncio
async def test_brain_health_grey_with_no_sessions():
    from services.ora_god_mode import ora_brain_health

    class _Cursor:
        def __init__(self, r): self._r = r
        async def to_list(self, length=None): return self._r

    db = MagicMock()
    db.brain_sessions.find = MagicMock(return_value=_Cursor([]))
    db.ora_training_log.find_one = AsyncMock(return_value=None)
    out = await ora_brain_health(db)
    assert out["status"] == "grey"
    assert out["sessions_today"] == 0
    assert out["agency_agents"] >= 10
