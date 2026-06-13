"""iter 285 — extended widget audit (27 widgets), Gmail endpoint alive,
log filter active, legacy AgentCommandCenter merged into ORACommandConsole.

Validates:
  • /api/oauth/gmail/health is mounted (404 → 200 regression guard)
  • Audit widgets endpoint returns 27 entries (up from 14)
  • google_oauth_router is NOT in LEAN_MODE skip list
  • /health log filter class exists in server.py
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
import pytest

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BACKEND_URL = "http://localhost:8001"

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "backend" / "routers" / "registry.py"
SERVER_PY = REPO_ROOT / "backend" / "server.py"
A2A_AUDIT = REPO_ROOT / "backend" / "routers" / "a2a_audit_router.py"
AUREM_DASH = REPO_ROOT / "frontend" / "src" / "platform" / "AuremDashboard.jsx"
CMD_HUB = REPO_ROOT / "frontend" / "src" / "platform" / "AdminCommandHub.jsx"


def test_gmail_router_unskipped():
    """google_oauth_router must NOT be in LEAN_MODE skip list."""
    src = REGISTRY.read_text()
    # The active skip-set body ends with "}" — parse it out
    skip_block = re.search(r"_SKIP_IN_LEAN\s*=\s*\{(.*?)^\s{0,4}\}", src, re.DOTALL | re.MULTILINE)
    assert skip_block, "Could not find _SKIP_IN_LEAN block"
    body = skip_block.group(1)
    # Strip comments (commented-out entries like "# routers.google_oauth_router — RE-ENABLED")
    non_comment = "\n".join(
        line for line in body.splitlines() if not line.strip().startswith("#")
    )
    assert "google_oauth_router" not in non_comment, (
        "google_oauth_router must not be in active LEAN_MODE skip list"
    )


def test_gmail_health_endpoint_alive():
    """GET /api/oauth/gmail/health must return 200."""
    # Small retry loop — backend may hot-reload during test runs
    import time
    last_exc = None
    for _ in range(3):
        try:
            r = httpx.get(f"{BACKEND_URL}/api/oauth/gmail/health", timeout=5.0)
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
            body = r.json()
            assert "status" in body, f"Missing 'status' field: {body}"
            assert body["status"] in ("healthy", "not_configured")
            return
        except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_exc = e
            time.sleep(1.5)
    raise AssertionError(f"Backend unreachable after 3 retries: {last_exc}")


def test_audit_widgets_has_27_entries():
    """Audit registry must list at least 27 widgets (iter 285 base + extended)."""
    src = A2A_AUDIT.read_text()
    widget_block = re.search(r"WIDGET_REGISTRY\s*=\s*\[(.*?)^\]", src, re.DOTALL | re.MULTILINE)
    if not widget_block:
        widget_block = re.search(r"WIDGETS\s*=\s*\[(.*?)\]", src, re.DOTALL)
    assert widget_block, "Could not find WIDGET_REGISTRY/WIDGETS list"
    # Count tuples — each begins with `("`
    tuples = re.findall(r'\(\s*"[^"]+"\s*,', widget_block.group(1))
    assert len(tuples) >= 27, f"Expected ≥27 widget entries, found {len(tuples)}"


def test_audit_widgets_contains_gmail_integration():
    """Gmail widget must map to /api/oauth/gmail/health (not the old 404 path)."""
    src = A2A_AUDIT.read_text()
    assert '"gmail_integration"' in src and '"/api/oauth/gmail/health"' in src, (
        "gmail_integration must map to /api/oauth/gmail/health (audit wiring)"
    )
    # Regression guard — the old broken path must not be present
    assert '"/api/gmail/oauth/status"' not in src, (
        "Old 404 gmail path must not be present in audit wiring"
    )


def test_health_log_filter_installed():
    """server.py must install uvicorn.access filter for /health and /api/health."""
    src = SERVER_PY.read_text()
    assert "_HealthLogFilter" in src, "Health log filter class missing from server.py"
    assert '"GET /health ' in src and '"GET /api/health ' in src
    assert 'uvicorn.access' in src and 'addFilter' in src


def test_agent_command_center_merged():
    """AgentCommandCenter must re-import ORACommandConsole (duplicate merged)."""
    src = AUREM_DASH.read_text()
    assert (
        "import AgentCommandCenter from './ORACommandConsole'" in src
    ), "AgentCommandCenter import must be aliased to ORACommandConsole (merged duplicate)"


def test_command_hub_cockpit_link():
    """AdminCommandHub must expose a testid link to the canonical cockpit (/admin/pillars-map)."""
    src = CMD_HUB.read_text()
    assert 'data-testid="command-hub-open-cockpit"' in src
    assert 'href="/admin/pillars-map"' in src
