"""
iter 305h — Email inbound auto-reply regression tests.
Covers the four guard rails: parse, dedup, founder skip, rate-limit.
"""
import os
import pytest
import httpx

import pytest
pytestmark = pytest.mark.skip(reason="stale — POST /api/email/inbound + /health were LEAN-pruned; canonical flow lives in email_inbound_router tests — quarantined iter D-86; delete or rewrite when feature re-stabilises")

API_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"


@pytest.mark.asyncio
async def test_inbound_health():
    async with httpx.AsyncClient(timeout=15) as hc:
        r = await hc.get(f"{API_URL}/api/email/inbound/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "resend_configured" in data
    assert data["max_replies_per_sender_24h"] == 3


@pytest.mark.asyncio
async def test_inbound_rejects_missing_sender():
    async with httpx.AsyncClient(timeout=15) as hc:
        r = await hc.post(f"{API_URL}/api/email/inbound", json={"subject": "x"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_inbound_dedup_by_message_id():
    mid = f"<regression-test-305h-{os.urandom(4).hex()}@aurem.live>"
    payload = {
        "from": "autotest+dedup@aurem.live",
        "to": "ora@aurem.live",
        "subject": "Re: regression test",
        "text": "test body",
        "messageId": mid,
    }
    async with httpx.AsyncClient(timeout=60) as hc:
        r1 = await hc.post(f"{API_URL}/api/email/inbound", json=payload)
        r2 = await hc.post(f"{API_URL}/api/email/inbound", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json().get("skipped") == "already_processed"


@pytest.mark.asyncio
async def test_inbound_skips_founder():
    founder = os.environ.get("FOUNDER_EMAIL", "teji.ss1986@gmail.com")
    async with httpx.AsyncClient(timeout=15) as hc:
        r = await hc.post(f"{API_URL}/api/email/inbound", json={
            "from": founder,
            "to": "ora@aurem.live",
            "subject": "self",
            "text": "self",
            "messageId": f"<founder-{os.urandom(4).hex()}@aurem.live>",
        })
    assert r.status_code == 200
    assert r.json().get("skipped") == "founder_or_self"
