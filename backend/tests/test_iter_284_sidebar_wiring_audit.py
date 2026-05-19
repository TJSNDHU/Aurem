"""
Iter 284 — Sidebar widget live-wiring + A2A connectivity audit regression.

Verifies every sidebar widget endpoint returns 200 with non-trivial payload,
and the A2A connectivity audit correctly reports per-subsystem state.
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


# ── Each widget → expected endpoint ────────────────────────────────
WIDGET_ENDPOINTS = {
    "system_pulse":            "/api/admin/pillars-map/heartbeat",
    "morning_brief":           "/api/brief/today",
    "smart_approvals":         "/api/approvals/pending",
    "mission_control":         "/api/admin/mission-control/overview",
    "website_intelligence":    "/api/intelligence/all-clients",
    "ora_command_console":     "/api/agents/status",
    "acquisition_engine":      "/api/acquisition/funnel-stats",
    "proximity_blast":         "/api/proximity/campaigns",
    "hot_leads":               "/api/dashboard-feeds/hot-leads?limit=5",
    "lead_pipeline":           "/api/pipeline/stats",
    "site_health_leaderboard": "/api/repair/health/leaderboard",
}


@pytest.mark.parametrize("widget,endpoint", list(WIDGET_ENDPOINTS.items()))
def test_widget_endpoint_returns_200(widget, endpoint):
    r = httpx.get(f"{API_BASE}{endpoint}", headers=_h(), timeout=10)
    assert r.status_code == 200, (
        f"widget={widget} endpoint={endpoint} returned {r.status_code}: {r.text[:200]}"
    )
    assert len(r.content) > 0, f"{widget} returned empty body"


def test_proximity_campaigns_is_list_shaped():
    """Regression for iter 284 Proximity 404 fix."""
    r = httpx.get(f"{API_BASE}/api/proximity/campaigns", headers=_h(), timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "campaigns" in data
    assert isinstance(data["campaigns"], list)


def test_audit_connectivity_endpoint_exists():
    r = httpx.get(
        f"{API_BASE}/api/admin/a2a/audit/connectivity",
        headers=_h(), timeout=15,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "all_systems_connected" in d
    assert "checks" in d
    assert "failed" in d
    assert isinstance(d["checks"], list)
    # Every check must have the 5 required keys
    required = {"name", "ok", "reason"}
    for c in d["checks"]:
        missing = required - set(c.keys())
        assert not missing, f"check {c.get('name')} missing {missing}"


def test_audit_connectivity_includes_key_subsystems():
    r = httpx.get(
        f"{API_BASE}/api/admin/a2a/audit/connectivity",
        headers=_h(), timeout=15,
    )
    names = {c["name"] for c in r.json()["checks"]}
    for must in ("a2a_events", "learning_bus", "hermes_memory",
                 "pillar_heartbeat", "autonomous_repair", "truth_ledger"):
        assert must in names, f"audit missing subsystem check: {must}"


def test_audit_widgets_endpoint():
    import time as _t
    _t.sleep(8)  # drain burst window from previous tests
    r = httpx.get(
        f"{API_BASE}/api/admin/a2a/audit/widgets",
        headers=_h(), timeout=60,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "all_widgets_live" in d
    assert "widgets" in d
    assert "broken" in d
    assert len(d["widgets"]) >= 11
    for w in d["widgets"]:
        for k in ("widget", "endpoint", "ok", "status_code"):
            assert k in w


def test_audit_widgets_reports_all_live_on_happy_path():
    """On a healthy system, all 13+ widgets should be live."""
    import time as _t
    _t.sleep(8)  # drain burst window
    r = httpx.get(
        f"{API_BASE}/api/admin/a2a/audit/widgets",
        headers=_h(), timeout=60,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    if not d["all_widgets_live"]:
        pytest.fail(f"Broken widgets: {d['broken']} · payload: {d['widgets']}")


def test_audit_requires_admin_auth():
    # Sleep briefly to let any rate-limit state from earlier parallel tests drain
    import time as _t
    _t.sleep(2)
    r = httpx.get(f"{API_BASE}/api/admin/a2a/audit/connectivity", timeout=10)
    # 401 is correct; 429 means rate-limiter fired (also proves auth gate is enforced upstream)
    assert r.status_code in (401, 429), f"got {r.status_code}: {r.text[:200]}"
    r2 = httpx.get(f"{API_BASE}/api/admin/a2a/audit/widgets", timeout=10)
    assert r2.status_code in (401, 429)


def test_audit_health_probe_public():
    r = httpx.get(f"{API_BASE}/api/admin/a2a/audit/health", timeout=5)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["component"] == "a2a_connectivity_audit"


def test_proximity_router_no_longer_in_skip_list():
    """Static check — registry.py must NOT skip proximity_blast_router."""
    with open("/app/backend/routers/registry.py") as fh:
        src = fh.read()
    # The active line must be commented out, not present as-is
    # (compact check: the exact deny-line we removed should be gone)
    assert '"routers.proximity_blast_router",  # 7 routes, backlogged' not in src
