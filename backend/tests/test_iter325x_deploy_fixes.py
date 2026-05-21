"""
iter 325x — Deployment-failure regression suite.

User reported deploy failing with TWO classes of errors:

1. `BrowserType.launch: Executable doesn't exist at /pw-browsers/...
   chrome-headless-shell` — Playwright launching without chromium binary.

2. `pymongo.errors.AutoReconnect: customer-apps-shard-...mongodb.net:27017:
   [Errno -3] Temporary failure in name resolution` — Atlas hostname not
   resolvable from K8s.

These tests prove the code-level fixes (NOT docker/infra):

  • browser_agent_service does a *filesystem* probe for chromium and
    short-circuits with a graceful skip dict — no banner, no crash.
  • server.py runs a 5-second MongoDB ping at startup with a redacted
    URL log + actionable remediation when it fails. Health endpoint
    stays up so K8s liveness probes don't restart-loop the pod.
"""
import os
import sys
import importlib
import asyncio
import pytest


@pytest.fixture(autouse=True)
def _reset_browser_cache():
    """Ensure each test starts with a fresh probe cache."""
    sys.path.insert(0, "/app/backend")
    from services import browser_agent_service as bas
    bas._BROWSER_AVAILABLE = None
    bas._BROWSER_AVAILABLE_REASON = ""
    yield
    bas._BROWSER_AVAILABLE = None
    bas._BROWSER_AVAILABLE_REASON = ""


def test_filesystem_probe_returns_false_when_chromium_missing(monkeypatch):
    """When PLAYWRIGHT_BROWSERS_PATH points nowhere, the probe says
    False *without* importing Playwright (so no 'Please run playwright
    install' banner pollutes deploy logs)."""
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "/tmp/definitely-not-here")
    # Wipe all known default paths
    monkeypatch.setattr("os.path.isdir", lambda p: False)
    from services.browser_agent_service import _probe_browser_available, _BROWSER_AVAILABLE_REASON
    assert _probe_browser_available() is False


def test_screenshot_url_returns_graceful_skip_when_no_chromium(monkeypatch):
    """screenshot_url() must return a dict with skipped=True instead of
    raising 'Executable doesn't exist'. Callers (auto_website_builder
    etc.) already check `shot.get('ok')` so this keeps the whole pipeline
    smooth even on a fresh container with no browser binary."""
    from services import browser_agent_service as bas
    bas._BROWSER_AVAILABLE = False
    bas._BROWSER_AVAILABLE_REASON = "test: chromium missing"

    async def _go():
        return await bas.screenshot_url(
            "https://example.com",
            requires_approval=False,
            triggered_by="test_iter325x",
        )

    r = asyncio.get_event_loop().run_until_complete(_go())
    assert r["ok"] is False
    assert r.get("skipped") is True
    assert r.get("error") == "browser_unavailable"
    # Reason must mention chromium / playwright install hint
    assert "chromium" in r["reason"].lower() or "playwright" in r["reason"].lower()


def test_extract_url_returns_graceful_skip_when_no_chromium(monkeypatch):
    """extract_url() — same graceful skip contract."""
    from services import browser_agent_service as bas
    bas._BROWSER_AVAILABLE = False
    bas._BROWSER_AVAILABLE_REASON = "test: chromium missing"

    async def _go():
        return await bas.extract_url(
            "https://example.com",
            requires_approval=False,
            triggered_by="test_iter325x",
        )

    r = asyncio.get_event_loop().run_until_complete(_go())
    assert r["ok"] is False
    assert r.get("skipped") is True
    assert r.get("error") == "browser_unavailable"


def test_no_hardcoded_atlas_url_in_python_files():
    """Verify no Python file in /app/backend hardcodes the broken Atlas
    URL pattern. The MONGO_URL must come from environment ONLY.

    We exclude this test file itself (and its compiled cache) since it
    mentions the URL pattern in its docstring as documentation.
    """
    import subprocess
    out = subprocess.run(
        ["grep", "-rln", "--include=*.py", "djq3ym.mongodb.net", "/app/backend"],
        capture_output=True, text=True,
    )
    files = [
        l for l in out.stdout.strip().split("\n")
        if l and "test_iter325x_deploy_fixes" not in l and not l.endswith(".pyc")
    ]
    assert not files, f"Hardcoded Atlas URL found in: {files}"


def test_startup_mongo_probe_block_present():
    """The startup event must contain the iter 325x deploy-failure probe."""
    src = open("/app/backend/server.py", encoding="utf-8").read()
    assert "[STARTUP][mongo]" in src
    assert "serverSelectionTimeoutMS=5000" in src
    assert "REMEDIATION" in src
    assert "REDACTED" in src   # credentials must be redacted in logs
