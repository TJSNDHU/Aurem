"""
P1 mock purge regression — Steps 4-7.

Asserts source-level invariants only (router runtime behaviour is
covered by the existing live API smoke tests on the prod deploy).
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _read(rel):
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as f:
        return f.read()


# ── Step 4 — CRM sync ────────────────────────────────────────────

def test_crm_sync_no_mock_lists():
    src = _read("routers/crm_sync_engine.py")
    for tok in ("_generate_mock_contacts", "MOCK_FIRST_NAMES",
                  "MOCK_LAST_NAMES", "MOCK_COMPANIES", '"mode": "mock"',
                  '"mode": "demo"'):
        assert tok not in src, f"forbidden token: {tok}"


def test_crm_sync_raises_503_without_credentials():
    src = _read("routers/crm_sync_engine.py")
    assert "_require_crm_credentials" in src
    assert "Add HUBSPOT_API_KEY" in src


# ── Step 5 — Recovery comms ──────────────────────────────────────

def test_recovery_comms_no_mock_send():
    src = _read("routers/recovery_comms_router.py")
    assert "_mock_send" not in src
    assert "click_to_chat_fallback" not in src
    assert '"status": "simulated"' not in src


def test_recovery_comms_no_sms_branch():
    src = _read("routers/recovery_comms_router.py")
    assert 'elif channel == "sms":' not in src
    assert "wa.me/{recipient.replace" not in src


# ── Step 6 — Enrichment ──────────────────────────────────────────

def test_enrichment_no_mock_layer():
    src = _read("routers/enrichment_service.py")
    for tok in ("_mock_enrich_contact", "MOCK_TITLES", "MOCK_COMPANIES",
                  "MOCK_INDUSTRIES", "MOCK_SENIORITY",
                  "MOCK_LINKEDIN_PREFIX", "apollo_mock",
                  '"mode": "mock"'):
        assert tok not in src, f"forbidden token: {tok}"


def test_enrichment_raises_503_without_apollo():
    src = _read("routers/enrichment_service.py")
    assert "_require_apollo" in src
    assert "Add APOLLO_API_KEY" in src


def test_enrichment_web_scrape_uses_real_html():
    src = _read("routers/enrichment_service.py")
    assert "_scrape_team_page" in src
    assert "mock_found_people" not in src
    assert "Sarah Chen" not in src


# ── Step 7 — Shopify billing ─────────────────────────────────────

# ── Step 7 — Shopify billing ─────────────────────────────────────

def test_shopify_billing_no_scaffold_branch():
    src = _read("routers/shopify_billing_router.py")
    assert '"mode": "scaffold"' not in src
    assert '"status": "scaffold"' not in src
    assert "Scaffold mode — return mock" not in src
    assert "Scaffold mode — skipping charge" not in src
    assert "Shopify OAuth not completed" in src


# ── Apollo cost dashboard ────────────────────────────────────────

def test_apollo_cost_router_paths():
    from routers import apollo_cost_router as mod
    paths = {r.path for r in mod.router.routes}
    assert "/api/admin/apollo-cost/summary" in paths
    assert "/api/admin/apollo-cost/forecast" in paths


def test_apollo_cost_logs_calls_to_mongo():
    src = _read("services/proximity_blast.py")
    assert "apollo_call_log" in src
    assert "estimated_usd" in src


def test_apollo_cost_page_present_in_frontend():
    fe_root = os.path.normpath(os.path.join(ROOT, "..", "frontend", "src"))
    p = os.path.join(fe_root, "platform", "AdminApolloCostPage.jsx")
    assert os.path.exists(p), "AdminApolloCostPage.jsx not found"
    src = open(p, "r", encoding="utf-8").read()
    assert "/api/admin/apollo-cost/summary" in src
    assert 'data-testid="admin-apollo-cost-page"' in src


def test_app_routes_wired():
    fe_root = os.path.normpath(os.path.join(ROOT, "..", "frontend", "src"))
    src = open(os.path.join(fe_root, "App.js"), "r", encoding="utf-8").read()
    assert "AdminApolloCostPage" in src
    assert "/admin/apollo-cost" in src
    shell = open(os.path.join(fe_root, "platform", "AdminShell.jsx"),
                   "r", encoding="utf-8").read()
    assert "/admin/apollo-cost" in shell
    assert "Apollo Cost" in shell
