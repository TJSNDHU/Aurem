"""
iter 325v — ROUTE-LEVEL ROOT-CAUSE PROOF for the "system goes offline" cascade.

Tracks the production failure chain that put aurem.live into "BROKEN
FLOWS 17/23" with every component showing "BE 401":

  1. /api/admin/pillars-map/flows probes each `be_endpoint` via localhost.
  2. The probes are UN-authed (internal health pings, no Bearer header).
  3. Endpoints that legitimately require admin auth return 401.
  4. Old logic surfaced reason="HTTP 401" → admin saw "BE 401" red badges
     everywhere → believed every flow was broken.

Fix (in pillars_map_router._check_flow):
  • 401/403 from an internal probe = endpoint + server are alive
    (request reached FastAPI, auth middleware did its job).
  • be_side = green with reason "auth-gated endpoint reachable".
  • Scheduler-dead checks still run; a real outage still shows red.

This test asserts the route now reports the friendly reason. It runs
against the live preview backend so it catches any regression that
re-introduces the misleading "HTTP 401" reason.
"""
import os
import json
import httpx
import pytest


def _backend_url() -> str:
    with open("/app/frontend/.env", "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL"):
                return line.split("=", 1)[1].strip().rstrip("/")
    return os.environ.get("REACT_APP_BACKEND_URL", "")


def _login_token(api: str) -> str:
    r = httpx.post(
        f"{api}/api/auth/login",
        json={"email": "teji.ss1986@gmail.com", "password": "Aurem@Founder2026!"},
        timeout=15,
    )
    r.raise_for_status()
    d = r.json()
    return d.get("token") or d.get("access_token") or ""


@pytest.fixture(scope="module")
def flows_payload():
    api = _backend_url()
    assert api, "REACT_APP_BACKEND_URL not resolved"
    tok = _login_token(api)
    assert tok, "founder login failed — check /app/memory/test_credentials.md"
    r = httpx.get(
        f"{api}/api/admin/pillars-map/flows",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def test_401_endpoints_are_marked_green_not_red(flows_payload):
    """Auth-gated endpoints (401 on un-authed probe) must NOT cascade to red."""
    flows = flows_payload.get("flows") or []
    assert flows, "no flows returned"
    misleading = []
    for f in flows:
        be = (f.get("triple_pulse") or {}).get("backend") or {}
        if be.get("http_status") in (401, 403):
            # Auth-gated endpoint with no failed scheduler dependency must be green.
            sched_missing = be.get("schedulers_missing") or []
            if not sched_missing and be.get("status") == "red":
                misleading.append((f["id"], be))
    assert not misleading, (
        f"401/403 endpoints incorrectly marked red (regression): {misleading}"
    )


def test_401_reason_string_is_human_friendly(flows_payload):
    """The reason must say 'auth-gated endpoint reachable' — not bare 'HTTP 401'."""
    flows = flows_payload.get("flows") or []
    bare_http_reasons = []
    for f in flows:
        be = (f.get("triple_pulse") or {}).get("backend") or {}
        if be.get("http_status") in (401, 403):
            reason = (be.get("reason") or "").lower()
            if reason == "http 401" or reason == "http 403":
                bare_http_reasons.append((f["id"], be.get("reason")))
            # Must mention "auth-gated" OR "scheduler" (when sched dead is the real cause)
            elif "auth-gated" not in reason and "scheduler" not in reason:
                bare_http_reasons.append((f["id"], be.get("reason")))
    assert not bare_http_reasons, (
        f"Misleading 401/403 reasons (regression): {bare_http_reasons}"
    )


def test_summary_matches_flow_statuses(flows_payload):
    """summary.red/yellow/green must equal the counted statuses."""
    flows = flows_payload.get("flows") or []
    summary = flows_payload.get("summary") or {}
    counted = {"red": 0, "yellow": 0, "green": 0}
    for f in flows:
        s = f.get("status")
        if s in counted:
            counted[s] += 1
    for k, v in counted.items():
        assert summary.get(k) == v, (
            f"summary.{k}={summary.get(k)} != actual count {v} (flows ledger drift)"
        )


def test_no_flow_reports_html_in_reason(flows_payload):
    """No reason string should contain '<!DOCTYPE' — that would mean the
    upstream probe got an HTML error page through to our snapshot."""
    flows = flows_payload.get("flows") or []
    leaks = []
    blob = json.dumps(flows).lower()
    for needle in ("<!doctype", "<html", "<head>"):
        if needle in blob:
            leaks.append(needle)
    assert not leaks, f"HTML leaked into pillars-map snapshot: {leaks}"
