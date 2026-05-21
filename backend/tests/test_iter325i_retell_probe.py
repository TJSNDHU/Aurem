"""iter 325i — Retell nightly probe regression tests.

Locks in the deep probe contract that catches the iter-325h class of
silent-failure bugs (signature drift, missing env vars, runaway failure
rate). If any of these tests fail, the probe is degraded and ORA will
not catch the next outbound-call regression.
"""
from __future__ import annotations

import inspect
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from services.aurem_nightly_selfcheck import _probe_retell


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

class _FakeResp:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeHttpx:
    """Minimal httpx.AsyncClient stand-in returning canned responses."""

    def __init__(self, responses):
        # responses: dict[url_suffix] -> _FakeResp
        self._responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        for suffix, resp in self._responses.items():
            if url.endswith(suffix):
                return resp
        return _FakeResp(404, {})


def _make_db_mock(total_24h: int = 0, failed_24h: int = 0):
    db = MagicMock()
    db.auto_call_log = MagicMock()

    async def _count(filter_):
        # Detect the failure filter by looking for `$or`
        if "$or" in filter_:
            return failed_24h
        return total_24h

    db.auto_call_log.count_documents = AsyncMock(side_effect=_count)
    return db


def _patch_httpx(responses):
    """Return a context manager that patches httpx.AsyncClient inside
    the selfcheck module."""
    return patch(
        "httpx.AsyncClient",
        lambda *a, **kw: _FakeHttpx(responses),
    )


# ─────────────────────────────────────────────────────────────────
# 1. Happy path
# ─────────────────────────────────────────────────────────────────

def test_retell_probe_all_green(monkeypatch):
    monkeypatch.setenv("RETELL_API_KEY", "key_test")
    monkeypatch.setenv("RETELL_AGENT_ID", "agent_ok")
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+15555550000")

    responses = {
        "/list-agents": _FakeResp(200, [{"agent_id": "agent_ok"}]),
        "/list-phone-numbers": _FakeResp(200, [{"phone_number": "+15555550000"}]),
    }
    db = _make_db_mock(total_24h=10, failed_24h=2)  # 20% failure → ok

    with _patch_httpx(responses):
        result = asyncio.run(_probe_retell(db))

    assert result["name"] == "retell"
    assert result["ok"] is True, result
    checks = result["checks"]
    assert checks["api_reachable"]
    assert checks["agent_id_exists"]
    assert checks["from_number_exists"]
    assert checks["signature_ok"] is True
    assert checks["failure_rate_ok"] is True
    assert "warning" not in result


# ─────────────────────────────────────────────────────────────────
# 2. Missing key
# ─────────────────────────────────────────────────────────────────

def test_retell_probe_missing_key(monkeypatch):
    monkeypatch.delenv("RETELL_API_KEY", raising=False)
    result = asyncio.run(_probe_retell(None))
    assert result["ok"] is False
    assert "RETELL_API_KEY missing" in result["error"]


# ─────────────────────────────────────────────────────────────────
# 3. Agent ID missing from account (config drift)
# ─────────────────────────────────────────────────────────────────

def test_retell_probe_agent_not_in_account(monkeypatch):
    monkeypatch.setenv("RETELL_API_KEY", "key_test")
    monkeypatch.setenv("RETELL_AGENT_ID", "agent_ghost")
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+15555550000")
    responses = {
        "/list-agents": _FakeResp(200, [{"agent_id": "agent_other"}]),
        "/list-phone-numbers": _FakeResp(200, [{"phone_number": "+15555550000"}]),
    }
    with _patch_httpx(responses):
        result = asyncio.run(_probe_retell(_make_db_mock()))
    assert result["ok"] is False
    assert "not found in account" in result["warning"]
    assert result["checks"]["agent_id_exists"] is False


# ─────────────────────────────────────────────────────────────────
# 4. From number missing from account
# ─────────────────────────────────────────────────────────────────

def test_retell_probe_from_number_not_in_account(monkeypatch):
    monkeypatch.setenv("RETELL_API_KEY", "key_test")
    monkeypatch.setenv("RETELL_AGENT_ID", "agent_ok")
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+19999999999")
    responses = {
        "/list-agents": _FakeResp(200, [{"agent_id": "agent_ok"}]),
        "/list-phone-numbers": _FakeResp(200, [{"phone_number": "+15555550000"}]),
    }
    with _patch_httpx(responses):
        result = asyncio.run(_probe_retell(_make_db_mock()))
    assert result["ok"] is False
    assert "RETELL_FROM_NUMBER" in result["warning"]


# ─────────────────────────────────────────────────────────────────
# 5. Signature regression — THE iter-325h bug class
# ─────────────────────────────────────────────────────────────────

def test_retell_probe_catches_signature_drift(monkeypatch):
    """Simulate someone re-introducing the iter-325h bug — probe must
    flip to ok=False with the right warning."""
    monkeypatch.setenv("RETELL_API_KEY", "key_test")
    monkeypatch.setenv("RETELL_AGENT_ID", "agent_ok")
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+15555550000")
    responses = {
        "/list-agents": _FakeResp(200, [{"agent_id": "agent_ok"}]),
        "/list-phone-numbers": _FakeResp(200, [{"phone_number": "+15555550000"}]),
    }

    # Replace the function with a regressed signature (no lead_context)
    async def _regressed(agent_id, to_number):  # noqa: D401
        return {"ok": True, "call_id": "x"}

    with _patch_httpx(responses), \
         patch("routers.voice_agent_router._retell_create_phone_call", _regressed):
        result = asyncio.run(_probe_retell(_make_db_mock()))

    assert result["ok"] is False
    assert result["checks"]["signature_ok"] is False
    assert "lead_context" in result["checks"]["signature_missing_kwargs"]
    assert "iter-325h" in result["warning"]


# ─────────────────────────────────────────────────────────────────
# 6. High failure rate over 24h
# ─────────────────────────────────────────────────────────────────

def test_retell_probe_high_failure_rate(monkeypatch):
    monkeypatch.setenv("RETELL_API_KEY", "key_test")
    monkeypatch.setenv("RETELL_AGENT_ID", "agent_ok")
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+15555550000")
    responses = {
        "/list-agents": _FakeResp(200, [{"agent_id": "agent_ok"}]),
        "/list-phone-numbers": _FakeResp(200, [{"phone_number": "+15555550000"}]),
    }
    db = _make_db_mock(total_24h=10, failed_24h=8)  # 80% failure
    with _patch_httpx(responses):
        result = asyncio.run(_probe_retell(db))
    assert result["ok"] is False
    assert "failure rate" in result["warning"]


# ─────────────────────────────────────────────────────────────────
# 7. No traffic → not penalised
# ─────────────────────────────────────────────────────────────────

def test_retell_probe_zero_traffic_ok(monkeypatch):
    monkeypatch.setenv("RETELL_API_KEY", "key_test")
    monkeypatch.setenv("RETELL_AGENT_ID", "agent_ok")
    monkeypatch.setenv("RETELL_FROM_NUMBER", "+15555550000")
    responses = {
        "/list-agents": _FakeResp(200, [{"agent_id": "agent_ok"}]),
        "/list-phone-numbers": _FakeResp(200, [{"phone_number": "+15555550000"}]),
    }
    db = _make_db_mock(total_24h=0, failed_24h=0)
    with _patch_httpx(responses):
        result = asyncio.run(_probe_retell(db))
    assert result["ok"] is True
    assert result["checks"]["failure_rate_ok"] is True


# ─────────────────────────────────────────────────────────────────
# 8. Probe is wired into run_selfcheck and accepts `db`
# ─────────────────────────────────────────────────────────────────

def test_probe_signature_accepts_db():
    sig = inspect.signature(_probe_retell)
    assert "db" in sig.parameters
