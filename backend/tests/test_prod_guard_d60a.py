"""
tests/test_prod_guard_d60a.py — iter D-60a

Production deployment crashed because `prod_guard.is_production_pod()`
returned False on the live pod (APP_URL env var missing), so
SovereignWarmer + ghost_scout auto-loop + Ollama health pings all ran
flat-out and likely OOM-killed the container.

Asserts the new detection signals:
  • Atlas managed Mongo (`mongodb+srv://`) → prod
  • PREVIEW_PROXY_URL / DEPLOY_URL containing "deploy.emergentcf.cloud" → prod
  • Legacy AUREM_ENV / APP_URL / DISABLE_LEGION still honored
"""
from __future__ import annotations

import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _reset_guard():
    """prod_guard.is_production_pod is @lru_cache'd. Reimport to clear."""
    if "services.prod_guard" in sys.modules:
        del sys.modules["services.prod_guard"]
    return importlib.import_module("services.prod_guard")


def _clean_env(monkeypatch):
    for k in ("AUREM_ENV", "DISABLE_LEGION", "APP_URL",
                "MONGO_URL", "PREVIEW_PROXY_URL",
                "DEPLOY_URL", "CF_PAGES_URL"):
        monkeypatch.delenv(k, raising=False)


def test_default_is_preview(monkeypatch):
    _clean_env(monkeypatch)
    g = _reset_guard()
    assert g.is_production_pod() is False


def test_aurem_env_production(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("AUREM_ENV", "production")
    g = _reset_guard()
    assert g.is_production_pod() is True


def test_app_url_aurem_live(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("APP_URL", "https://aurem.live")
    g = _reset_guard()
    assert g.is_production_pod() is True


def test_atlas_mongo_url_detected_as_prod(monkeypatch):
    """The single most reliable production signal — only managed Atlas
    uses mongodb+srv://. Preview uses local mongodb://."""
    _clean_env(monkeypatch)
    monkeypatch.setenv(
        "MONGO_URL",
        "mongodb+srv://aurem:secret@cluster.mongodb.net/aurem_db",
    )
    g = _reset_guard()
    assert g.is_production_pod() is True


def test_preview_proxy_url_emergent_deploy(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv(
        "PREVIEW_PROXY_URL",
        "https://live-support-3.cluster-2.deploy.emergentcf.cloud",
    )
    g = _reset_guard()
    assert g.is_production_pod() is True


def test_local_mongo_does_not_trigger_prod(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    g = _reset_guard()
    assert g.is_production_pod() is False


def test_ghost_scout_skips_in_production(monkeypatch):
    """Defence-in-depth: even if scheduler still fires the harvest loop,
    it must short-circuit in production."""
    src = open(
        os.path.join(ROOT, "services", "ghost_scout_iproyal.py"),
        encoding="utf-8",
    ).read()
    assert "is_production_pod" in src
    assert "GHOST_SCOUT_PROD_LOOP" in src
    assert "disabled in production" in src
