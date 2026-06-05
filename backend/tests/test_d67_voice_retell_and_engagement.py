"""
test_d67_voice_retell_and_engagement.py — iter D-67
====================================================
Locks in the Retell-voice + engagement-summary additions to Campaign
Health. The founder's question was: "kya chal raha hai, kya nahi" —
this iteration makes the dashboard answer that question across ALL
channels, not just WhatsApp/email.
"""
from __future__ import annotations

import pytest


def test_full_report_includes_voice_retell_and_engagement():
    """Master report must compute the two new rows."""
    src = open("/app/backend/services/campaign_health.py").read()
    assert "_check_voice_retell" in src
    assert "_check_engagement_summary" in src
    assert "voice_retell" in src
    assert "engagement_24h" in src


def test_voice_retell_check_uses_real_env_vars():
    """Voice check must read all 3 Retell env vars and call into Mongo
    for activity. No hardcoded green."""
    src = open("/app/backend/services/campaign_health.py").read()
    # Open the function block and assert key markers.
    idx = src.find("async def _check_voice_retell")
    assert idx != -1
    block = src[idx:idx + 2500]
    assert "RETELL_API_KEY" in block
    assert "RETELL_FROM_NUMBER" in block
    assert "RETELL_AGENT_ID" in block
    assert "_retell_active_24h" in block


def test_engagement_summary_counts_every_channel():
    """The engagement-24h row must cover email + sms + whatsapp + voice
    AND opens AND replies, all from real Mongo queries."""
    src = open("/app/backend/services/campaign_health.py").read()
    idx = src.find("async def _check_engagement_summary")
    assert idx != -1
    block = src[idx:idx + 2500]
    # All four outbound channels must be counted.
    for c in ('"channel": "email"', '"channel": "sms"', '"channel": "whatsapp"'):
        assert c in block, f"missing channel filter: {c}"
    assert "_retell_active_24h" in block
    # Inbound signals.
    assert "hot_lead_signal_at" in block
    assert "^reply_" in block
    # Compute reply/open rates.
    assert "reply_rate" in block and "open_rate" in block


def test_whapi_check_acknowledges_retell_fallback():
    """When WHAPI is disabled but Retell is wired, the WA row must be
    green with a clear "voice AI is the fallback" message — not a
    misleading yellow that hides the working channel."""
    src = open("/app/backend/services/campaign_health.py").read()
    idx = src.find("async def _check_whapi")
    assert idx != -1
    block = src[idx:idx + 3500]
    assert "RETELL_API_KEY" in block
    assert "voice AI" in block.lower() or "voice ai" in block.lower()


@pytest.mark.asyncio
async def test_voice_retell_check_returns_correct_shape(monkeypatch):
    """End-to-end: voice check returns the standard row shape."""
    from services import campaign_health as ch
    monkeypatch.setenv("RETELL_API_KEY",  "rk_test")
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+14165551234")
    monkeypatch.setenv("RETELL_AGENT_ID", "agent_abc12345")

    class _NoActivityDB:
        class _Coll:
            async def count_documents(self, *a, **k): return 0
        voice_call_log = _Coll()
        agent_ledger   = _Coll()

    monkeypatch.setattr(ch, "_db", _NoActivityDB())
    row = await ch._check_voice_retell()
    assert row["component"] == "voice_retell"
    assert row["status"] == "green"
    assert "idle" in row["headline"].lower() or "ready" in row["detail"].lower()


@pytest.mark.asyncio
async def test_engagement_summary_returns_per_channel_counts(monkeypatch):
    from services import campaign_health as ch

    class _DB:
        class _Outreach:
            async def count_documents(self, q):
                ch_val = (q or {}).get("channel")
                return {"email": 4, "sms": 2, "whatsapp": 1}.get(ch_val, 0)
        class _Leads:
            async def count_documents(self, *a, **k): return 3
        class _Empty:
            async def count_documents(self, *a, **k): return 0
        outreach_history = _Outreach()
        campaign_leads   = _Leads()
        voice_call_log   = _Empty()
        agent_ledger     = _Empty()

    monkeypatch.setattr(ch, "_db", _DB())
    row = await ch._check_engagement_summary()
    assert row["component"] == "engagement_24h"
    assert row["status"] == "green"
    # email=4 sms=2 wa=1 calls=0 → 7 touches; 3 opens
    assert "7 touches" in row["headline"]
    assert "3 opens" in row["headline"]


@pytest.mark.asyncio
async def test_engagement_summary_yellow_when_zero_activity(monkeypatch):
    from services import campaign_health as ch

    class _AllZero:
        class _C:
            async def count_documents(self, *a, **k): return 0
        outreach_history = _C()
        campaign_leads   = _C()
        voice_call_log   = _C()
        agent_ledger     = _C()

    monkeypatch.setattr(ch, "_db", _AllZero())
    row = await ch._check_engagement_summary()
    assert row["component"] == "engagement_24h"
    assert row["status"] == "yellow"
    assert "no outbound" in row["headline"].lower()
    assert row["autofix"] == "topup_via_scout"
