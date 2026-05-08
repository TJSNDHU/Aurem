"""
Regression tests for production-URL canonicalization (iter 282y).
Ensures all health-monitor / self-scan / recovery-alert paths reference
aurem.live, not the Emergent preview URL.
"""

import os
import importlib

import pytest


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    # Clear any env that would inject a preview URL
    monkeypatch.delenv("REACT_APP_BACKEND_URL", raising=False)
    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    monkeypatch.setenv("AUREM_PUBLIC_URL", "https://aurem.live")


def test_self_scan_uses_aurem_live():
    from services import self_scan_automation as ssa
    importlib.reload(ssa)
    assert ssa._get_aurem_url() == "https://aurem.live"


def test_self_scan_falls_back_to_aurem_live_when_no_env(monkeypatch):
    monkeypatch.delenv("AUREM_PUBLIC_URL", raising=False)
    monkeypatch.delenv("REACT_APP_BACKEND_URL", raising=False)
    from services import self_scan_automation as ssa
    importlib.reload(ssa)
    assert ssa._get_aurem_url() == "https://aurem.live"


def test_browser_agent_internal_hosts_no_preview():
    from services import browser_agent_service as bas
    importlib.reload(bas)
    hosts = bas._internal_hosts()
    assert "aurem.live" in hosts
    assert "www.aurem.live" in hosts
    assert "ai-platform-preview-3.preview.emergentagent.com" not in hosts


def test_api_key_manager_internal_origins_includes_aurem_live():
    from services import api_key_manager
    importlib.reload(api_key_manager)
    src = open(api_key_manager.__file__).read()
    assert "https://aurem.live" in src
    assert "https://www.aurem.live" in src
    assert "ai-platform-preview-3.preview.emergentagent.com" not in src
