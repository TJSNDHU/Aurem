"""
D-71 regression tests — locks the four production fixes:

1. auto_blast.py compiles (silent scheduler death)
2. aurem_config package re-exports legacy constants (LinkedIn/TestLab 500s)
3. content_engine_router tolerates missing 'price_monthly'
4. CRM / Dashboard / Agent-status read the SAME lead source (campaign_leads)
"""
from __future__ import annotations

import ast
from pathlib import Path


def test_auto_blast_module_compiles():
    """The Campaign Outbound + scheduler import auto_blast at boot. A
    SyntaxError silently kills BOTH and the customer dashboard reports
    'Last run never'. We compile the source ourselves so the failure
    mode (raised at import time, swallowed by registry.try/except) is
    caught by CI instead of the live site."""
    src = Path("/app/backend/pillars/sales/routes/auto_blast.py").read_text()
    ast.parse(src)


def test_aurem_config_exposes_legacy_constants():
    """Two callers (routers/linkedin_router.py, routers/site_qa_router.py)
    do `from aurem_config import LINKEDIN_CLIENT_ID, TEST_LAB_API_KEY`. The
    package dir at /app/backend/aurem_config/ shadows the flat module, so
    these constants must live on the package's __init__.py."""
    import aurem_config

    assert hasattr(aurem_config, "LINKEDIN_CLIENT_ID")
    assert hasattr(aurem_config, "LINKEDIN_CLIENT_SECRET")
    assert hasattr(aurem_config, "TEST_LAB_API_KEY")
    assert hasattr(aurem_config, "TEST_LAB_BASE_URL")
    assert hasattr(aurem_config, "linkedin_redirect_uri")
    assert callable(aurem_config.linkedin_redirect_uri)


def test_content_engine_tiers_tolerates_missing_price_monthly():
    """The PLAN_TIERS SSOT uses `price_cad`, not `price_monthly`. The
    route was hard-keying `plan['price_monthly']` and 500'd on every
    request. The fix is a `.get(..., fallback)` chain."""
    src = Path("/app/backend/routers/content_engine_router.py").read_text()
    assert "plan['price_monthly']" not in src, (
        "Direct dict access reintroduced — must use .get() with fallback"
    )
    assert "price_monthly" in src and "price_cad" in src, (
        "Both keys must be referenced in the fallback chain"
    )


def test_agents_status_reads_campaign_leads_for_scout():
    """Dashboard shows 'Leads Found 1264' (from campaign_leads). ORA page
    showed Scout=0. They MUST read the same collection."""
    src = Path("/app/backend/routers/aurem_routes.py").read_text()
    # Scout's tasks_completed must be sourced from campaign_leads (not just
    # the legacy db.leads collection which only stores AI-conversation captures).
    assert "campaign_leads.count_documents" in src, (
        "Scout activity stat must read campaign_leads (the Apollo/Scout output collection)"
    )


def test_lead_stats_unifies_campaign_and_legacy_leads():
    """/api/leads/stats was reading only db.leads. Now it must merge
    campaign_leads (primary) with the legacy leads collection so the CRM
    'Total Leads' card matches the Dashboard's 'Leads Found' KPI."""
    src = Path("/app/backend/services/lead_capture_service.py").read_text()
    assert "campaign_leads" in src, "Must source from campaign_leads"
    # default period should be 'all' upstream to match Dashboard
    router_src = Path("/app/backend/routers/leads_router.py").read_text()
    assert 'period: str = "all"' in router_src, (
        "Default period must be 'all' so CRM matches Dashboard's 30-day window"
    )


def test_customer_pipeline_falls_back_to_campaign_leads():
    """The CRM list page polls /api/customer/pipeline/scan-events. When
    no customer_scans exist (fresh dogfood account), it must fall back
    to campaign_leads so the list isn't empty while Dashboard shows 1k+."""
    src = Path("/app/backend/routers/customer_pipeline_router.py").read_text()
    assert "campaign_leads" in src, (
        "Customer pipeline must fall back to campaign_leads when no scans exist"
    )


def test_exception_middleware_filters_client_disconnects():
    """34k 'No response returned' incidents flooded the Live Health panel.
    These are client-side disconnects (browser nav, double-click), not
    server bugs. They must NOT be recorded as P1 backend_5xx."""
    src = Path("/app/backend/middleware/exception_to_incident.py").read_text()
    assert "CancelledError" in src, "CancelledError must be filtered out"
    assert "No response returned" in src, (
        "Starlette's 'No response returned' RuntimeError must be filtered (client disconnect)"
    )
