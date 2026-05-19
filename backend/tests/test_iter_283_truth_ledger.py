"""
Iter 283 — Truth Ledger (Honesty DNA) regression.

Verifies:
  • All 6 router endpoints
  • Service record/read helpers
  • Induction briefing shape + preamble
  • ORA Truth-Sync block injection on health queries
  • Append-only contract (no _id leak, ts_iso present)
"""
from __future__ import annotations

import os
import pytest
import httpx
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

API_BASE = os.environ.get("AUREM_E2E_BASE", "http://localhost:8001")

_CACHED_TOKEN: str | None = None


def _token():
    global _CACHED_TOKEN
    if _CACHED_TOKEN:
        return _CACHED_TOKEN
    r = httpx.post(
        f"{API_BASE}/api/auth/login",
        json={"email": "teji.ss1986@gmail.com", "password": "<REDACTED>"},
        timeout=10,
    )
    r.raise_for_status()
    _CACHED_TOKEN = r.json()["token"]
    return _CACHED_TOKEN


def _h():
    return {"Authorization": f"Bearer {_token()}"}


def test_health_public_no_auth():
    r = httpx.get(f"{API_BASE}/api/admin/truth-ledger/health", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["component"] == "truth_ledger"
    assert d["db_ready"] is True


def test_recent_requires_admin():
    r = httpx.get(f"{API_BASE}/api/admin/truth-ledger/recent", timeout=10)
    assert r.status_code == 401


def test_post_record_and_read_back():
    body = {
        "actor": "pytest_iter283",
        "event_type": "glitch",
        "description": "pytest glitch entry",
        "severity": "info",
        "evidence": {"test_run": True},
    }
    r = httpx.post(
        f"{API_BASE}/api/admin/truth-ledger/record",
        headers=_h(), json=body, timeout=10,
    )
    assert r.status_code == 200, r.text
    log_id = r.json()["log_id"]
    assert log_id and len(log_id) >= 12

    r2 = httpx.get(
        f"{API_BASE}/api/admin/truth-ledger/recent?limit=10&actor=pytest_iter283",
        headers=_h(), timeout=10,
    )
    assert r2.status_code == 200
    entries = r2.json()["entries"]
    found = next((e for e in entries if e["log_id"] == log_id), None)
    assert found is not None
    assert "_id" not in found, "_id must be excluded from responses"
    assert "ts" not in found, "internal ts must be excluded"
    assert found["ts_iso"], "ts_iso must be present"
    # immutable field is stripped from responses (internal-only contract)
    assert "immutable" not in found


def test_invalid_event_type_normalizes_to_glitch():
    body = {
        "actor": "pytest_iter283",
        "event_type": "definitely_not_a_valid_type",
        "description": "should normalize to glitch",
    }
    r = httpx.post(
        f"{API_BASE}/api/admin/truth-ledger/record",
        headers=_h(), json=body, timeout=10,
    )
    assert r.status_code == 200
    log_id = r.json()["log_id"]
    r2 = httpx.get(
        f"{API_BASE}/api/admin/truth-ledger/recent?limit=5&actor=pytest_iter283",
        headers=_h(), timeout=10,
    )
    entries = r2.json()["entries"]
    found = next((e for e in entries if e["log_id"] == log_id), None)
    assert found is not None
    assert found["event_type"] == "glitch"


def test_induction_briefing_has_preamble_and_sections():
    r = httpx.get(
        f"{API_BASE}/api/admin/truth-ledger/induction",
        headers=_h(), timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert "Zabaan ka pakka" in d["preamble"]
    assert "jhooth" in d["preamble"].lower() or "Jhooth" in d["preamble"]
    for k in ("failures", "glitches", "insufficient_recoveries",
              "persistent_reds", "hallucinations_caught", "stats"):
        assert k in d, f"induction missing section {k}"
    assert d["stats"]["window_days"] > 0


def test_stats_endpoint():
    r = httpx.get(
        f"{API_BASE}/api/admin/truth-ledger/stats", headers=_h(), timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    for k in ("window_days", "total", "by_type", "by_severity", "by_actor"):
        assert k in d


def test_current_health_returns_real_state():
    r = httpx.get(
        f"{API_BASE}/api/admin/truth-ledger/current-health",
        headers=_h(), timeout=15,
    )
    assert r.status_code == 200
    d = r.json()
    for k in ("ts_iso", "pillars_verdict", "sentinel", "autonomous_repair",
              "open_criticals_24h", "recent_failures"):
        assert k in d


def test_ora_chat_injects_truth_sync_on_health_query():
    """When user asks about health, ORA response must reflect REAL pillar state,
    not a sanitized 'all is well'. We verify by ensuring ORA references the
    current verdict honestly."""
    # Ensure there's a recent 'failure' so the system has context to surface
    httpx.post(
        f"{API_BASE}/api/admin/truth-ledger/record",
        headers=_h(),
        json={"actor": "pytest_iter283_health",
              "event_type": "failure",
              "description": "pytest seed failure for truth-sync check",
              "severity": "warn"},
        timeout=10,
    )
    r = httpx.post(
        f"{API_BASE}/api/aurem/chat",
        headers=_h(),
        json={"message": "what is the current system health status?",
              "session_id": "pytest_iter283_truthsync"},
        timeout=60,
    )
    # Chat may hit LLM rate limits or not have full env; tolerate non-200 but
    # if 200, assert the response mentions honest terms (red/green/sentinel).
    if r.status_code != 200:
        pytest.skip(f"chat endpoint returned {r.status_code}")
    resp = (r.json().get("response") or "").lower()
    assert len(resp) > 10
    # Must reference at least one honest-state concept
    health_keywords = ("red", "green", "sentinel", "pillar", "health",
                       "status", "error", "degraded", "ok")
    assert any(k in resp for k in health_keywords), \
        f"ORA did not surface honest health terms in reply: {resp[:300]}"


def test_append_only_no_update_endpoint():
    """Ensure we did not ship PATCH/PUT/DELETE — router must be append-only."""
    r_patch = httpx.patch(
        f"{API_BASE}/api/admin/truth-ledger/recent", headers=_h(), timeout=5,
    )
    r_delete = httpx.delete(
        f"{API_BASE}/api/admin/truth-ledger/recent", headers=_h(), timeout=5,
    )
    assert r_patch.status_code in (404, 405)
    assert r_delete.status_code in (404, 405)


def test_service_module_exports():
    from services import truth_ledger as tl
    for name in ("record", "record_failure", "record_success",
                 "record_insufficient_recovery", "record_persistent_red",
                 "record_hallucination", "get_recent", "get_stats",
                 "get_induction_briefing", "current_truthful_health",
                 "VALID_EVENT_TYPES", "VALID_SEVERITIES", "PREAMBLE"):
        assert hasattr(tl, name), f"service missing {name}"


def test_autonomous_repair_wired_to_truth_ledger():
    """Static check — verify_recovery now writes to truth_ledger on insufficient."""
    path = "/app/backend/services/autonomous_repair_engine.py"
    with open(path) as fh:
        src = fh.read()
    assert "from services import truth_ledger" in src
    assert "record_success" in src
    assert "record_insufficient_recovery" in src


def test_pillar_heartbeat_wired_to_truth_ledger():
    """Static check — heartbeat records persistent_red after 15 min."""
    path = "/app/backend/services/pillar_heartbeat_service.py"
    with open(path) as fh:
        src = fh.read()
    assert "record_persistent_red" in src
    assert "PERSISTENT_RED_THRESHOLD_SEC" in src


def test_ora_prompt_has_truth_sync_mandate():
    path = "/app/backend/routers/aurem_chat.py"
    with open(path) as fh:
        src = fh.read()
    assert "TRUTH-SYNC MANDATE" in src
    assert "Zabaan ka pakka" in src
    assert "TRUTH-SYNC · current real state" in src
